import datetime
import enum
import uuid

from sqlalchemy import Enum, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class GoalStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class TaskStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class HabitStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("channel", "external_id"),)

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    channel: Mapped[str] = mapped_column()
    external_id: Mapped[str] = mapped_column()
    pending_clarification: Mapped[dict | None] = mapped_column(JSONB, default=None)
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


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column()
    description: Mapped[str | None] = mapped_column(default=None)
    category: Mapped[str | None] = mapped_column(default=None)
    status: Mapped[GoalStatus] = mapped_column(
        Enum(GoalStatus, native_enum=False), default=GoalStatus.ACTIVE
    )
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    completed_at: Mapped[datetime.datetime | None] = mapped_column(default=None)
    archived_at: Mapped[datetime.datetime | None] = mapped_column(default=None)

    tasks: Mapped[list["Task"]] = relationship(back_populates="goal")
    habits: Mapped[list["Habit"]] = relationship(back_populates="goal")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    goal_id: Mapped[str | None] = mapped_column(ForeignKey("goals.id"), default=None)
    title: Mapped[str] = mapped_column()
    description: Mapped[str | None] = mapped_column(default=None)
    category: Mapped[str | None] = mapped_column(default=None)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, native_enum=False), default=TaskStatus.NOT_STARTED
    )
    due_date: Mapped[datetime.datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    completed_at: Mapped[datetime.datetime | None] = mapped_column(default=None)

    goal: Mapped[Goal | None] = relationship(back_populates="tasks")


class Habit(Base):
    __tablename__ = "habits"

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    goal_id: Mapped[str | None] = mapped_column(ForeignKey("goals.id"), default=None)
    title: Mapped[str] = mapped_column()
    description: Mapped[str | None] = mapped_column(default=None)
    category: Mapped[str | None] = mapped_column(default=None)
    frequency: Mapped[str] = mapped_column(default="daily")
    status: Mapped[HabitStatus] = mapped_column(
        Enum(HabitStatus, native_enum=False), default=HabitStatus.ACTIVE
    )
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    archived_at: Mapped[datetime.datetime | None] = mapped_column(default=None)

    goal: Mapped[Goal | None] = relationship(back_populates="habits")
    logs: Mapped[list["HabitLog"]] = relationship(back_populates="habit")


class HabitLog(Base):
    __tablename__ = "habit_logs"

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    habit_id: Mapped[str] = mapped_column(ForeignKey("habits.id"))
    notes: Mapped[str | None] = mapped_column(default=None)
    completed_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())

    habit: Mapped[Habit] = relationship(back_populates="logs")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id"), default=None)
    request_id: Mapped[str | None] = mapped_column(default=None)
    type: Mapped[str] = mapped_column()
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
