"""Exercises the actual contract the Telegram gateway depends on: a real
Agent process, talking to a real Postgres, called the same way
Telegram/src/agentClient.ts calls it."""

import httpx
from db.session import get_session
from sqlalchemy import text


def test_chat_round_trip_through_real_agent_process(agent_server, clean_db):
    response = httpx.post(
        f"{agent_server}/chat",
        json={"channel": "telegram", "external_id": "12345", "text": "hello"},
        timeout=10,
    )

    assert response.status_code == 200
    assert response.json() == {"reply": "fake reply to: hello"}

    with get_session() as session:
        conversation = session.execute(
            text("SELECT channel, external_id FROM conversations")
        ).one()
        assert tuple(conversation) == ("telegram", "12345")


def test_request_id_header_propagates_to_stored_metrics(agent_server, clean_db):
    """Telegram/src/agentClient.ts sends X-Request-Id - confirm the real Agent
    process picks it up instead of generating its own, so one message is
    traceable end-to-end by grepping a single request_id."""
    response = httpx.post(
        f"{agent_server}/chat",
        json={"channel": "telegram", "external_id": "12345", "text": "hello"},
        headers={"X-Request-Id": "gateway-generated-id"},
        timeout=10,
    )
    assert response.status_code == 200

    with get_session() as session:
        request_id = session.execute(text("SELECT request_id FROM llm_metrics")).scalar_one()
        assert request_id == "gateway-generated-id"
