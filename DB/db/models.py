import datetime
import uuid

from sqlalchemy import ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("channel", "external_id"),)

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    channel: Mapped[str] = mapped_column()
    external_id: Mapped[str] = mapped_column()
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())

    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"))
    role: Mapped[str] = mapped_column()
    content: Mapped[str] = mapped_column()
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class LLMMetrics(Base):
    __tablename__ = "llm_metrics"

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"))
    request_id: Mapped[str | None] = mapped_column(default=None)
    provider: Mapped[str] = mapped_column()
    model: Mapped[str] = mapped_column()
    system_prompt: Mapped[str | None] = mapped_column(default=None)
    input_tokens: Mapped[int | None] = mapped_column(default=None)
    output_tokens: Mapped[int | None] = mapped_column(default=None)
    cache_creation_input_tokens: Mapped[int | None] = mapped_column(default=None)
    cache_read_input_tokens: Mapped[int | None] = mapped_column(default=None)
    finish_reason: Mapped[str | None] = mapped_column(default=None)
    latency_ms: Mapped[int | None] = mapped_column(default=None)
    cost_usd: Mapped[float | None] = mapped_column(default=None)
    error: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id"), default=None)
    request_id: Mapped[str | None] = mapped_column(default=None)
    type: Mapped[str] = mapped_column()
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
