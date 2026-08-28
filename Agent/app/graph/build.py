from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

from app.graph.state import AgentState
from app.llm.contract import LLMProvider

SYSTEM_PROMPT = "You are a helpful personal assistant."

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


def _build_call_model(provider: LLMProvider, tools: list[BaseTool]):
    def call_model(state: AgentState) -> AgentState:
        response = provider.generate(state["messages"], system=SYSTEM_PROMPT, tools=tools or None)
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
                "system_prompt": SYSTEM_PROMPT,
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
    graph.add_node("call_model", _build_call_model(provider, tools))
    graph.add_edge(START, "call_model")

    if tools:
        graph.add_node("tools", ToolNode(tools, wrap_tool_call=_process_tool_result))
        graph.add_conditional_edges("call_model", tools_condition, {"tools": "tools", "__end__": END})
        graph.add_edge("tools", "call_model")
    else:
        graph.add_edge("call_model", END)

    return graph.compile()
