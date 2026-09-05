import app.api.chat as chat_module
import pytest
from app.graph.build import build_graph
from app.llm.fake_provider import FakeProvider
from app.main import app
from app.tools.tasks import TASK_TOOLS
from db.session import get_session
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import text

pytestmark = pytest.mark.integration

client = TestClient(app)


def test_chat_round_trip_persists_conversation(clean_db):
    response = client.post(
        "/chat", json={"channel": "test", "external_id": "user-1", "text": "hello"}
    )
    assert response.status_code == 200
    assert response.json() == {"reply": "fake reply to: hello"}

    with get_session() as session:
        messages = session.execute(text("SELECT role, content FROM messages ORDER BY created_at")).all()
        assert [tuple(m) for m in messages] == [
            ("user", "hello"),
            ("assistant", "fake reply to: hello"),
        ]
        metrics = session.execute(text("SELECT provider, model FROM llm_metrics")).all()
        assert [tuple(m) for m in metrics] == [("fake", "fake-model")]


def test_chat_uses_incoming_request_id_header(clean_db):
    response = client.post(
        "/chat",
        json={"channel": "test", "external_id": "user-3", "text": "hello"},
        headers={"X-Request-Id": "caller-supplied-id"},
    )
    assert response.status_code == 200

    with get_session() as session:
        metrics_request_id = session.execute(text("SELECT request_id FROM llm_metrics")).scalar_one()
        event_request_ids = set(session.execute(text("SELECT request_id FROM events")).scalars())
        assert metrics_request_id == "caller-supplied-id"
        assert event_request_ids == {"caller-supplied-id"}


def test_chat_generates_request_id_when_absent(clean_db):
    response = client.post(
        "/chat", json={"channel": "test", "external_id": "user-4", "text": "hello"}
    )
    assert response.status_code == 200

    with get_session() as session:
        request_id = session.execute(text("SELECT request_id FROM llm_metrics")).scalar_one()
        assert request_id is not None
        assert request_id != "caller-supplied-id"


def _clarification_tool_call(options):
    return {
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


def _conversation_id(channel: str, external_id: str) -> str:
    with get_session() as session:
        return session.execute(
            text("SELECT id FROM conversations WHERE channel = :channel AND external_id = :external_id"),
            {"channel": channel, "external_id": external_id},
        ).scalar_one()


def test_chat_returns_clarification_when_agent_requests_it(clean_db, monkeypatch):
    options = [{"label": "Today", "value": "2026-08-29"}, {"label": "Tomorrow", "value": "2026-08-30"}]
    provider = FakeProvider(tool_calls=[_clarification_tool_call(options)])
    graph = build_graph(provider, tools=TASK_TOOLS, checkpointer=InMemorySaver())
    monkeypatch.setattr(chat_module, "_graph", graph)

    response = client.post(
        "/chat", json={"channel": "test", "external_id": "user-5", "text": "add a task"}
    )
    assert response.status_code == 200
    assert response.json() == {"reply": "When is it due?", "options": options}

    # Pending state now lives only in the checkpoint (ADR-0008), not a DB column.
    conversation_id = _conversation_id("test", "user-5")
    config = {"configurable": {"thread_id": conversation_id}}
    assert graph.get_state(config).interrupts


def test_chat_resumes_pending_clarification_deterministically(clean_db, monkeypatch):
    options = [{"label": "Today", "value": "2026-09-01"}, {"label": "No date", "value": ""}]
    provider = FakeProvider(tool_calls=[_clarification_tool_call(options)])
    graph = build_graph(provider, tools=TASK_TOOLS, checkpointer=InMemorySaver())
    monkeypatch.setattr(chat_module, "_graph", graph)

    ask_response = client.post(
        "/chat", json={"channel": "test", "external_id": "user-6", "text": "add a task: buy milk"}
    )
    assert ask_response.json()["options"] == options

    response = client.post(
        "/chat", json={"channel": "test", "external_id": "user-6", "text": "2026-09-01"}
    )
    assert response.status_code == 200
    body = response.json()
    assert "Buy milk" in body["reply"]
    assert "options" not in body

    with get_session() as session:
        task = session.execute(
            text("SELECT title, due_date FROM tasks WHERE title = 'Buy milk'")
        ).one()
        assert task.due_date is not None

        conversation_id = session.execute(
            text("SELECT id FROM conversations WHERE channel = 'test' AND external_id = 'user-6'")
        ).scalar_one()
        event_types = set(
            session.execute(
                text("SELECT type FROM events WHERE conversation_id = :cid"), {"cid": conversation_id}
            ).scalars()
        )
        assert "clarification_asked" in event_types
        assert "clarification_resumed" in event_types

        # One row for the ask turn (a real LLM call); the resumed turn calls the tool directly.
        metrics_count = session.execute(text("SELECT count(*) FROM llm_metrics")).scalar_one()
        assert metrics_count == 1

    assert not graph.get_state({"configurable": {"thread_id": conversation_id}}).interrupts


def test_chat_falls_through_to_llm_when_reply_does_not_match_pending_options(clean_db, monkeypatch):
    options = [{"label": "Today", "value": "2026-09-01"}]
    provider = FakeProvider(tool_calls=[_clarification_tool_call(options)])
    graph = build_graph(provider, tools=TASK_TOOLS, checkpointer=InMemorySaver())
    monkeypatch.setattr(chat_module, "_graph", graph)

    ask_response = client.post(
        "/chat", json={"channel": "test", "external_id": "user-7", "text": "add a task: buy milk"}
    )
    assert ask_response.json()["options"] == options

    response = client.post(
        "/chat", json={"channel": "test", "external_id": "user-7", "text": "actually nevermind"}
    )
    assert response.status_code == 200
    assert response.json() == {"reply": "fake reply to: actually nevermind"}

    conversation_id = _conversation_id("test", "user-7")
    assert not graph.get_state({"configurable": {"thread_id": conversation_id}}).interrupts


def test_chat_heals_a_conversation_stuck_mid_tool_call(clean_db, monkeypatch):
    """Simulates #43: a previous turn's tool call never got its ToolMessage saved (e.g. the
    process was killed mid-tool-call), leaving a dangling tool_use with no tool_result -
    exactly what a real Anthropic call rejects. The next message should heal and succeed
    instead of repeating that failure forever."""
    provider = FakeProvider()
    graph = build_graph(provider, tools=TASK_TOOLS, checkpointer=InMemorySaver())
    monkeypatch.setattr(chat_module, "_graph", graph)

    client.post("/chat", json={"channel": "test", "external_id": "user-stuck", "text": "hello"})
    conversation_id = _conversation_id("test", "user-stuck")
    config = {"configurable": {"thread_id": conversation_id}}

    stuck_ai_message = AIMessage(
        content="",
        tool_calls=[{"name": "list_tasks", "args": {}, "id": "dangling-call-1"}],
    )
    graph.update_state(
        config,
        {"messages": [HumanMessage(content="what are my tasks"), stuck_ai_message]},
        as_node="call_model",
    )
    stuck_state = graph.get_state(config)
    assert stuck_state.next  # sanity: genuinely stuck before healing
    assert not stuck_state.interrupts

    response = client.post(
        "/chat", json={"channel": "test", "external_id": "user-stuck", "text": "still there?"}
    )
    assert response.status_code == 200
    assert response.json() == {"reply": "fake reply to: still there?"}

    healed_messages = graph.get_state(config).values["messages"]
    healed_tool_message = next(
        m
        for m in healed_messages
        if isinstance(m, ToolMessage) and m.tool_call_id == "dangling-call-1"
    )
    assert healed_tool_message.content


def test_chat_reuses_conversation_history(clean_db):
    client.post("/chat", json={"channel": "test", "external_id": "user-2", "text": "first"})
    client.post("/chat", json={"channel": "test", "external_id": "user-2", "text": "second"})

    with get_session() as session:
        count = session.execute(
            text("SELECT count(*) FROM conversations WHERE channel = 'test' AND external_id = 'user-2'")
        ).scalar_one()
        assert count == 1
