import datetime

from app.graph.build import MAX_TOOL_RESULT_CHARS, _process_tool_result, build_graph
from app.llm.fake_provider import FakeProvider
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool


def test_graph_invokes_provider_and_returns_reply():
    graph = build_graph(FakeProvider())
    result = graph.invoke({"messages": [HumanMessage(content="hello")]})
    reply = result["messages"][-1]
    assert reply.content == "fake reply to: hello"
    assert reply.response_metadata["provider"] == "fake"


def test_graph_includes_todays_date_in_system_prompt():
    graph = build_graph(FakeProvider())
    result = graph.invoke({"messages": [HumanMessage(content="hello")]})
    reply = result["messages"][-1]
    today = datetime.datetime.now(datetime.UTC).date().isoformat()
    assert today in reply.response_metadata["system_prompt"]


@tool
def get_time() -> str:
    """Return a fixed time, for testing the tool-calling loop."""
    return "12:00"


def test_graph_runs_full_tool_call_round_trip():
    provider = FakeProvider(tool_calls=[{"name": "get_time", "args": {}, "id": "fake-call-1"}])
    graph = build_graph(provider, tools=[get_time])
    result = graph.invoke({"messages": [HumanMessage(content="what time is it?")]})

    message_types = [type(m).__name__ for m in result["messages"]]
    assert "ToolMessage" in message_types

    tool_message = next(m for m in result["messages"] if isinstance(m, ToolMessage))
    assert tool_message.content == "12:00"

    reply = result["messages"][-1]
    assert reply.content == "fake reply using tool result: 12:00"


def test_graph_routes_clarification_tool_call_without_executing_it():
    options = [
        {"label": "Today", "value": "2026-08-29"},
        {"label": "Tomorrow", "value": "2026-08-30"},
    ]
    provider = FakeProvider(
        tool_calls=[
            {
                "name": "request_clarification",
                "args": {
                    "tool": "create_task",
                    "known_args": {"title": "Buy milk"},
                    "field": "due_date",
                    "question": "When is it due?",
                    "options": options,
                },
                "id": "fake-call-1",
            }
        ]
    )
    graph = build_graph(provider, tools=[get_time])
    result = graph.invoke({"messages": [HumanMessage(content="add a task")]})

    reply = result["messages"][-1]
    assert reply.content == "When is it due?"
    assert reply.response_metadata["clarification"] == {
        "tool": "create_task",
        "known_args": {"title": "Buy milk"},
        "field": "due_date",
        "question": "When is it due?",
        "options": options,
    }
    assert "ToolMessage" not in [type(m).__name__ for m in result["messages"]]


def test_graph_resumes_pending_clarification_that_matches_without_calling_the_provider():
    pending = {
        "tool": "get_time",
        "known_args": {},
        "field": "confirm",
        "question": "Sure?",
        "options": [{"label": "Yes", "value": "yes"}],
    }
    provider = FakeProvider()
    graph = build_graph(provider, tools=[get_time])
    result = graph.invoke(
        {"messages": [HumanMessage(content="yes")], "pending_clarification": pending}
    )

    reply = result["messages"][-1]
    assert reply.content == "12:00"
    assert reply.response_metadata["resumed"] is True
    assert provider.call_count == 0


def test_graph_falls_through_to_model_when_message_does_not_match_pending_options():
    pending = {
        "tool": "get_time",
        "known_args": {},
        "field": "confirm",
        "question": "Sure?",
        "options": [{"label": "Yes", "value": "yes"}],
    }
    provider = FakeProvider()
    graph = build_graph(provider, tools=[get_time])
    result = graph.invoke(
        {"messages": [HumanMessage(content="actually nevermind")], "pending_clarification": pending}
    )

    reply = result["messages"][-1]
    assert reply.content == "fake reply to: actually nevermind"
    assert provider.call_count == 1


def test_call_model_trims_history_sent_to_the_provider_but_keeps_full_state(monkeypatch):
    monkeypatch.setattr("app.graph.build.settings.max_history_tokens", 30)
    provider = FakeProvider()
    graph = build_graph(provider)

    old_turns = [
        HumanMessage(content="first question " * 20),
        AIMessage(content="first answer " * 20),
        HumanMessage(content="second question " * 20),
        AIMessage(content="second answer " * 20),
    ]
    latest = HumanMessage(content="third question")

    result = graph.invoke({"messages": [*old_turns, latest]})

    # The provider only saw a trimmed, human-starting slice - not the full history.
    assert len(provider.last_messages) < len(old_turns) + 1
    assert isinstance(provider.last_messages[0], HumanMessage)
    assert provider.last_messages[-1] is latest

    # The graph's own state (what a checkpointer would persist) keeps everything.
    assert len(result["messages"]) == len(old_turns) + 2  # +1 latest, +1 new reply


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
