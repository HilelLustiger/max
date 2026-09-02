import pytest
from db.conversation import (
    add_message,
    clear_pending_clarification,
    create_conversation,
    get_conversation,
    recent_messages,
    record_event,
    record_llm_metrics,
    set_pending_clarification,
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


def test_recent_messages_ordered_and_limited(clean_db):
    with get_session() as session:
        conversation = create_conversation(session, "test", "user-1")
        for i in range(3):
            add_message(session, conversation.id, role="user", content=f"msg-{i}")

        messages = recent_messages(session, conversation.id, limit=2)
        assert [m.content for m in messages] == ["msg-0", "msg-1"]


def test_set_and_clear_pending_clarification(clean_db):
    with get_session() as session:
        conversation = create_conversation(session, "test", "user-1")
        data = {
            "tool": "create_task",
            "known_args": {"title": "Buy milk"},
            "field": "due_date",
            "question": "מתי היעד?",
            "options": [{"label": "היום", "value": "2026-08-29"}],
        }

        set_pending_clarification(session, conversation.id, data)
        found = get_conversation(session, "test", "user-1")
        assert found.pending_clarification == data

        clear_pending_clarification(session, conversation.id)
        found = get_conversation(session, "test", "user-1")
        assert found.pending_clarification is None


def test_new_conversation_has_no_pending_clarification(clean_db):
    with get_session() as session:
        conversation = create_conversation(session, "test", "user-1")
        assert conversation.pending_clarification is None


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
