import app.api.chat as chat_module
import pytest
from app.graph.build import build_graph
from app.llm.fake_provider import FakeProvider
from app.main import app
from app.tools.tasks import TASK_TOOLS
from db.conversation import create_conversation, set_pending_clarification
from db.session import get_session
from fastapi.testclient import TestClient
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


def test_chat_returns_clarification_when_agent_requests_it(clean_db, monkeypatch):
    options = [{"label": "Today", "value": "2026-08-29"}, {"label": "Tomorrow", "value": "2026-08-30"}]
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
    monkeypatch.setattr(chat_module, "_graph", build_graph(provider, tools=TASK_TOOLS))

    response = client.post(
        "/chat", json={"channel": "test", "external_id": "user-5", "text": "add a task"}
    )
    assert response.status_code == 200
    assert response.json() == {"reply": "When is it due?", "options": options}

    with get_session() as session:
        pending = session.execute(
            text(
                "SELECT pending_clarification FROM conversations "
                "WHERE channel = 'test' AND external_id = 'user-5'"
            )
        ).scalar_one()
        assert pending == {
            "tool": "create_task",
            "known_args": {"title": "Buy milk"},
            "field": "due_date",
            "question": "When is it due?",
            "options": options,
        }


def test_chat_resumes_pending_clarification_deterministically(clean_db):
    with get_session() as session:
        conversation = create_conversation(session, "test", "user-6")
        set_pending_clarification(
            session,
            conversation.id,
            {
                "tool": "create_task",
                "known_args": {"title": "Buy milk"},
                "field": "due_date",
                "question": "When is it due?",
                "options": [{"label": "Today", "value": "2026-09-01"}, {"label": "No date", "value": ""}],
            },
        )

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

        pending = session.execute(
            text(
                "SELECT pending_clarification FROM conversations "
                "WHERE channel = 'test' AND external_id = 'user-6'"
            )
        ).scalar_one()
        assert pending is None

        event_types = set(
            session.execute(
                text("SELECT type FROM events WHERE conversation_id = :cid"), {"cid": conversation.id}
            ).scalars()
        )
        assert "clarification_resumed" in event_types

        metrics_count = session.execute(text("SELECT count(*) FROM llm_metrics")).scalar_one()
        assert metrics_count == 0


def test_chat_falls_through_to_llm_when_reply_does_not_match_pending_options(clean_db):
    with get_session() as session:
        conversation = create_conversation(session, "test", "user-7")
        set_pending_clarification(
            session,
            conversation.id,
            {
                "tool": "create_task",
                "known_args": {"title": "Buy milk"},
                "field": "due_date",
                "question": "When is it due?",
                "options": [{"label": "Today", "value": "2026-09-01"}],
            },
        )

    response = client.post(
        "/chat", json={"channel": "test", "external_id": "user-7", "text": "actually nevermind"}
    )
    assert response.status_code == 200
    assert response.json() == {"reply": "fake reply to: actually nevermind"}

    with get_session() as session:
        pending = session.execute(
            text(
                "SELECT pending_clarification FROM conversations "
                "WHERE channel = 'test' AND external_id = 'user-7'"
            )
        ).scalar_one()
        assert pending is None


def test_chat_reuses_conversation_history(clean_db):
    client.post("/chat", json={"channel": "test", "external_id": "user-2", "text": "first"})
    client.post("/chat", json={"channel": "test", "external_id": "user-2", "text": "second"})

    with get_session() as session:
        count = session.execute(
            text("SELECT count(*) FROM conversations WHERE channel = 'test' AND external_id = 'user-2'")
        ).scalar_one()
        assert count == 1
