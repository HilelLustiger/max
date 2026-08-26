import pytest
from app.main import app
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


def test_chat_reuses_conversation_history(clean_db):
    client.post("/chat", json={"channel": "test", "external_id": "user-2", "text": "first"})
    client.post("/chat", json={"channel": "test", "external_id": "user-2", "text": "second"})

    with get_session() as session:
        count = session.execute(
            text("SELECT count(*) FROM conversations WHERE channel = 'test' AND external_id = 'user-2'")
        ).scalar_one()
        assert count == 1
