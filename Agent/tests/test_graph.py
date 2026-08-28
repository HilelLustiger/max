from app.graph.build import MAX_TOOL_RESULT_CHARS, _process_tool_result, build_graph
from app.llm.fake_provider import FakeProvider
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool


def test_graph_invokes_provider_and_returns_reply():
    graph = build_graph(FakeProvider())
    result = graph.invoke({"messages": [HumanMessage(content="hello")]})
    reply = result["messages"][-1]
    assert reply.content == "fake reply to: hello"
    assert reply.response_metadata["provider"] == "fake"


@tool
def get_time() -> str:
    """Return a fixed time, for testing the tool-calling loop."""
    return "12:00"


def test_graph_runs_full_tool_call_round_trip():
    graph = build_graph(FakeProvider(), tools=[get_time])
    result = graph.invoke({"messages": [HumanMessage(content="what time is it?")]})

    message_types = [type(m).__name__ for m in result["messages"]]
    assert "ToolMessage" in message_types

    tool_message = next(m for m in result["messages"] if isinstance(m, ToolMessage))
    assert tool_message.content == "12:00"

    reply = result["messages"][-1]
    assert reply.content == "fake reply using tool result: 12:00"


def test_process_tool_result_truncates_long_output():
    long_content = "x" * (MAX_TOOL_RESULT_CHARS + 500)

    def fake_execute(request):
        return ToolMessage(content=long_content, tool_call_id="call_1")

    result = _process_tool_result(object(), fake_execute)
    assert result.content.endswith("... [truncated]")
    assert len(result.content) <= MAX_TOOL_RESULT_CHARS + len("... [truncated]")


def test_process_tool_result_leaves_short_output_untouched():
    def fake_execute(request):
        return ToolMessage(content="short", tool_call_id="call_1")

    result = _process_tool_result(object(), fake_execute)
    assert result.content == "short"
