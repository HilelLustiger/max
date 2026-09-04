import datetime

from app.graph.build import MAX_TOOL_RESULT_CHARS, _process_tool_result, build_graph
from app.llm.fake_provider import FakeProvider
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command


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


def _clarification_tool_call(options):
    return {
        "name": "request_clarification",
        "args": {
            "tool": "get_time",
            "known_args": {},
            "field": "confirm",
            "question": "Sure?",
            "options": options,
        },
        "id": "fake-call-1",
    }


def test_graph_pauses_on_clarification_tool_call_without_executing_it():
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
    graph = build_graph(provider, tools=[get_time], checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "pause-test"}}

    result = graph.invoke({"messages": [HumanMessage(content="add a task")]}, config=config)

    assert "ToolMessage" not in [type(m).__name__ for m in result["messages"]]
    interrupt_value = result["__interrupt__"][0].value
    assert interrupt_value == {"question": "When is it due?", "options": options}
    assert graph.get_state(config).interrupts


def _assert_tool_use_is_immediately_followed_by_its_tool_result(messages) -> None:
    """Anthropic rejects any request where a tool_use block isn't immediately followed by a
    tool_result for the same id - request_clarification is intercepted and never truly
    executed, so the graph must synthesize that tool_result itself (see #30 live-testing)."""
    tool_call_message = next(m for m in messages if getattr(m, "tool_calls", None))
    call_id = tool_call_message.tool_calls[0]["id"]
    index = messages.index(tool_call_message)
    next_message = messages[index + 1]
    assert isinstance(next_message, ToolMessage)
    assert next_message.tool_call_id == call_id


def test_graph_resumes_clarification_that_matches_without_calling_the_provider():
    provider = FakeProvider(tool_calls=[_clarification_tool_call([{"label": "Yes", "value": "yes"}])])
    graph = build_graph(provider, tools=[get_time], checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "resume-match-test"}}
    graph.invoke({"messages": [HumanMessage(content="set a reminder")]}, config=config)
    calls_before_resume = provider.call_count

    result = graph.invoke(Command(resume="yes"), config=config)

    reply = result["messages"][-1]
    assert reply.content == "12:00"
    assert reply.response_metadata["resumed"] is True
    assert provider.call_count == calls_before_resume  # no extra provider call to resume
    assert not graph.get_state(config).interrupts
    _assert_tool_use_is_immediately_followed_by_its_tool_result(result["messages"])


def test_graph_falls_through_to_model_when_answer_does_not_match_any_option():
    provider = FakeProvider(tool_calls=[_clarification_tool_call([{"label": "Yes", "value": "yes"}])])
    graph = build_graph(provider, tools=[get_time], checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "resume-no-match-test"}}
    graph.invoke({"messages": [HumanMessage(content="set a reminder")]}, config=config)
    calls_before_resume = provider.call_count

    result = graph.invoke(Command(resume="actually nevermind"), config=config)

    reply = result["messages"][-1]
    assert reply.content == "fake reply to: actually nevermind"
    assert provider.call_count == calls_before_resume + 1
    _assert_tool_use_is_immediately_followed_by_its_tool_result(result["messages"])


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
