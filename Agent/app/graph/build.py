import datetime

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

from app.graph.state import AgentState
from app.llm.contract import LLMProvider
from app.tools.clarification import CLARIFICATION_TOOL_NAME, request_clarification


def _build_system_prompt() -> str:
    today = datetime.datetime.now(datetime.UTC).date().isoformat()
    return (
        "You are Max, a personal assistant whose job is to execute tools, not to chat. "
        "When a tool call succeeds, relay its result as-is: don't restate it in your own words, "
        "and don't add offers to help further. When a tool call fails, "
        "relay the error concisely and ask only for what's missing. Keep every reply short - "
        "a sentence or a compact list, never a paragraph of prose. "
        "Always reply in Hebrew, regardless of what language the tool result or user message is in. "
        f"Today's date is {today} - use it to resolve relative dates like 'today' or 'tomorrow' "
        "into ISO 8601 dates. If a tool call you make to gather information (e.g. listing "
        "existing records to build clarification options) surfaces other records unrelated to "
        "what the user is doing, ignore them - don't ask about or act on anything beyond the "
        "user's original request. If your previous reply was a clarification question, treat "
        "the user's next message as the answer to that question and finish the original request "
        "with it - don't treat it as a new, unrelated request."
    )

# Caps token usage and prompt complexity regardless of what a tool returns.
MAX_TOOL_RESULT_CHARS = 4000


def _cap_length(content: str) -> str:
    if len(content) > MAX_TOOL_RESULT_CHARS:
        return content[:MAX_TOOL_RESULT_CHARS] + "... [truncated]"
    return content


# Applied in order to every tool's raw string output before it becomes a ToolMessage.
# Add more steps here (e.g. summarization) as tools grow more varied.
_RESULT_PROCESSORS = [_cap_length]


def _process_tool_result(request: ToolCallRequest, execute) -> ToolMessage | Command:
    result = execute(request)
    if isinstance(result, ToolMessage) and isinstance(result.content, str):
        content = result.content
        for process in _RESULT_PROCESSORS:
            content = process(content)
        if content != result.content:
            result = result.model_copy(update={"content": content})
    return result


def _route_after_model(state: AgentState) -> str:
    last_message = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", None) or []
    if any(call["name"] == CLARIFICATION_TOOL_NAME for call in tool_calls):
        return "clarification"
    if tool_calls:
        return "tools"
    return "__end__"


def _clarification_node(state: AgentState) -> AgentState:
    last_message = state["messages"][-1]
    call = next(c for c in last_message.tool_calls if c["name"] == CLARIFICATION_TOOL_NAME)
    args = call["args"]
    reply = AIMessage(
        content=args["question"],
        usage_metadata=last_message.usage_metadata,
        response_metadata={
            **last_message.response_metadata,
            "clarification": {
                "field": args["field"],
                "question": args["question"],
                "options": args["options"],
            },
        },
    )
    return {"messages": [reply]}


def _build_call_model(provider: LLMProvider, tools: list[BaseTool]):
    def call_model(state: AgentState) -> AgentState:
        system_prompt = _build_system_prompt()
        response = provider.generate(state["messages"], system=system_prompt, tools=tools or None)
        reply = AIMessage(
            content=response.text,
            tool_calls=response.tool_calls,
            usage_metadata={
                "input_tokens": response.input_tokens or 0,
                "output_tokens": response.output_tokens or 0,
                "total_tokens": (response.input_tokens or 0) + (response.output_tokens or 0),
            },
            response_metadata={
                "provider": response.provider,
                "model": response.model,
                "system_prompt": system_prompt,
                "latency_ms": response.latency_ms,
                "cache_creation_input_tokens": response.cache_creation_input_tokens,
                "cache_read_input_tokens": response.cache_read_input_tokens,
                "finish_reason": response.finish_reason,
            },
        )
        return {"messages": [reply]}

    return call_model


def build_graph(provider: LLMProvider, tools: list[BaseTool] | None = None):
    tools = tools or []
    graph = StateGraph(AgentState)
    model_tools = [*tools, request_clarification] if tools else tools
    graph.add_node("call_model", _build_call_model(provider, model_tools))
    graph.add_edge(START, "call_model")

    if tools:
        graph.add_node("tools", ToolNode(tools, wrap_tool_call=_process_tool_result))
        graph.add_node("clarification", _clarification_node)
        graph.add_conditional_edges(
            "call_model",
            _route_after_model,
            {"tools": "tools", "clarification": "clarification", "__end__": END},
        )
        graph.add_edge("tools", "call_model")
        graph.add_edge("clarification", END)
    else:
        graph.add_edge("call_model", END)

    return graph.compile()
