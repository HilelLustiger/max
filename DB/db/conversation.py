from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Conversation, Event, LLMMetrics, Message


def get_conversation(session: Session, channel: str, external_id: str) -> Conversation | None:
    stmt = select(Conversation).where(
        Conversation.channel == channel, Conversation.external_id == external_id
    )
    return session.scalar(stmt)


def create_conversation(session: Session, channel: str, external_id: str) -> Conversation:
    conversation = Conversation(channel=channel, external_id=external_id)
    session.add(conversation)
    session.flush()
    return conversation


def recent_messages(session: Session, conversation_id: str, limit: int = 50) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
    )
    return list(session.scalars(stmt))


def add_message(session: Session, conversation_id: str, role: str, content: str) -> Message:
    message = Message(conversation_id=conversation_id, role=role, content=content)
    session.add(message)
    session.flush()
    return message


def record_llm_metrics(
    session: Session,
    message_id: str,
    provider: str,
    model: str,
    request_id: str | None = None,
    system_prompt: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cache_creation_input_tokens: int | None = None,
    cache_read_input_tokens: int | None = None,
    finish_reason: str | None = None,
    latency_ms: int | None = None,
    cost_usd: float | None = None,
    error: str | None = None,
) -> LLMMetrics:
    metrics = LLMMetrics(
        message_id=message_id,
        request_id=request_id,
        provider=provider,
        model=model,
        system_prompt=system_prompt,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_input_tokens=cache_creation_input_tokens,
        cache_read_input_tokens=cache_read_input_tokens,
        finish_reason=finish_reason,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        error=error,
    )
    session.add(metrics)
    session.flush()
    return metrics


def record_event(
    session: Session,
    type: str,
    conversation_id: str | None = None,
    request_id: str | None = None,
    payload: dict | None = None,
) -> Event:
    event = Event(
        conversation_id=conversation_id, request_id=request_id, type=type, payload=payload or {}
    )
    session.add(event)
    session.flush()
    return event
