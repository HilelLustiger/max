import pytest
from db.conversation import (
    add_message,
    create_conversation,
    get_conversation,
    record_event,
    record_llm_metrics,
)
from db.session import get_session

pytestmark = pytest.mark.integration


def test_get_conversation_returns_none_when_absent(clean_db):
    with get_session() as session:
        assert get_conversation(session, "test", "missing") is None


def test_create_then_get_conversation_round_trips(clean_db):
    with get_session() as session:
        created = create_conversation(session, "test", "user-1")
        found = get_conversation(session, "test", "user-1")
        assert found.id == created.id


def test_record_llm_metrics_and_event(clean_db):
    with get_session() as session:
        conversation = create_conversation(session, "test", "user-1")
        message = add_message(session, conversation.id, role="user", content="hi")

        metrics = record_llm_metrics(
            session, message_id=message.id, provider="fake", model="fake-model", input_tokens=1, output_tokens=1
        )
        event = record_event(session, "message_received", conversation_id=conversation.id)

        assert metrics.provider == "fake"
        assert event.type == "message_received"
