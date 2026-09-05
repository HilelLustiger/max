import datetime
import logging

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, trim_messages
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.pregel.main import Pregel
from langgraph.types import Command, RunnableConfig, StateSnapshot, interrupt

from app.config import settings
from app.graph.state import AgentState
from app.llm.contract import LLMProvider
from app.tools.clarification import CLARIFICATION_TOOL_NAME

logger = logging.getLogger(__name__)


def _build_system_prompt() -> str:
    today = datetime.datetime.now(datetime.UTC).date().isoformat()
    return (
        "You are Max, a personal assistant. You execute tools, but you're also a normal "
        "conversational presence, not just a command executor - answer questions warmly and "
        "directly, including questions about what was said earlier in this conversation. Never "
        "refuse or deflect a question just because it isn't a tool-executing request - if the "
        "answer is sitting in this conversation, just give it. Keep replies concise, but don't "
        "force everything into the shortest possible form at the cost of sounding cold or "
        "robotic. Don't add offers to help further after relaying a result. "
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


def heal_incomplete_run(graph: Pregel, config: RunnableConfig, state: StateSnapshot) -> bool:
    """Recover a thread left mid-step by a killed/crashed previous run (e.g. a slow tool call
    that never got to save its ToolMessage - see #43). Anthropic rejects any history with a
    tool_use block that has no tool_result immediately after it, so left alone this would
    break every future message on the thread. Distinct from a clarification interrupt (also
    leaves `next` non-empty, but with `interrupts` set) - only fires when nothing is actually
    paused, i.e. the run was simply cut off. Returns whether it healed anything."""
    if state.interrupts or not state.next:
        return False

    messages = state.values.get("messages", [])
    last_ai = next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)
    if last_ai is None or not last_ai.tool_calls:
        return False

    answered_ids = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    pending = [call for call in last_ai.tool_calls if call["id"] not in answered_ids]
    if not pending:
        return False

    healing_messages = [
        ToolMessage(content="הפעולה לא הושלמה עקב תקלה טכנית.", tool_call_id=call["id"])
        for call in pending
    ]
    # as_node="tools": this is standing in for what the tools node itself would have
    # produced, so it should route onward exactly like a real one does (its static edge
    # always goes to call_model) - not left to update_state's own node-inference guess.
    graph.update_state(config, {"messages": healing_messages}, as_node="tools")
    return True


def _route_after_model(state: AgentState) -> str:
    last_message = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", None) or []
    if any(call["name"] == CLARIFICATION_TOOL_NAME for call in tool_calls):
        return "clarification"
    if tool_calls:
        return "tools"
    return "__end__"


def _clarification_node(tool_registry: dict[str, BaseTool]):
    """Ask via interrupt() - pausing the graph and persisting the pause in the checkpoint,
    not in any state field of ours (see ADR-0008). Everything before the interrupt() call
    re-runs on every resume, so it must stay a pure read of state - no side effects."""

    def clarification_node(state: AgentState) -> AgentState:
        last_message = state["messages"][-1]
        call = next(c for c in last_message.tool_calls if c["name"] == CLARIFICATION_TOOL_NAME)
        args = call["args"]

        answer = interrupt({"question": args["question"], "options": args["options"]})

        # request_clarification's tool_use is never actually executed - Anthropic still
        # requires a tool_result immediately after it, so synthesize one here regardless
        # of whether the answer matched an option.
        tool_message = ToolMessage(content=str(answer), tool_call_id=call["id"])

        matched = next((o for o in args["options"] if o["value"] == answer), None)
        if matched is None:
            return {"messages": [tool_message, HumanMessage(content=answer)]}

        final_args = {**args["known_args"], args["field"]: matched["value"] or None}
        tool_result = tool_registry[args["tool"]].invoke(final_args)
        reply = AIMessage(content=tool_result, response_metadata={"resumed": True})
        return {"messages": [tool_message, reply]}

    return clarification_node


def _route_after_clarification(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.response_metadata.get("resumed"):
        return "__end__"
    return "call_model"


def _build_call_model(provider: LLMProvider, tools: list[BaseTool]):
    def call_model(state: AgentState) -> AgentState:
        system_prompt = _build_system_prompt()
        # The checkpoint keeps full history; only this trimmed slice goes to the LLM call.
        # "approximate" is a local char-count heuristic - LangChain's own recommendation for
        # the hot path, since the real Anthropic tokenizer is a network call per count.
        trimmed_messages = trim_messages(
            state["messages"],
            max_tokens=settings.max_history_tokens,
            token_counter="approximate",
            strategy="last",
            start_on="human",
        )
        response = provider.generate(trimmed_messages, system=system_prompt, tools=tools or None)
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


def build_graph(
    provider: LLMProvider,
    tools: list[BaseTool] | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
):
    tools = tools or []
    graph = StateGraph(AgentState)
    graph.add_node("call_model", _build_call_model(provider, tools))
    graph.add_edge(START, "call_model")

    if tools:
        tool_registry = {t.name: t for t in tools}
        graph.add_node("tools", ToolNode(tools, wrap_tool_call=_process_tool_result))
        graph.add_node("clarification", _clarification_node(tool_registry))
        graph.add_conditional_edges(
            "call_model",
            _route_after_model,
            {"tools": "tools", "clarification": "clarification", "__end__": END},
        )
        graph.add_edge("tools", "call_model")
        graph.add_conditional_edges(
            "clarification",
            _route_after_clarification,
            {"call_model": "call_model", "__end__": END},
        )
    else:
        graph.add_edge("call_model", END)

    return graph.compile(checkpointer=checkpointer)
