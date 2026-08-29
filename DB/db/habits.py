import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Habit, HabitLog, HabitStatus


def create_habit(
    session: Session,
    title: str,
    goal_id: str | None = None,
    description: str | None = None,
    category: str | None = None,
    frequency: str = "daily",
) -> Habit:
    habit = Habit(
        title=title, goal_id=goal_id, description=description, category=category, frequency=frequency
    )
    session.add(habit)
    session.flush()
    return habit


def get_habit(session: Session, habit_id: str) -> Habit | None:
    return session.get(Habit, habit_id)


def list_habits(
    session: Session,
    goal_id: str | None = None,
    status: HabitStatus | None = HabitStatus.ACTIVE,
    category: str | None = None,
) -> list[Habit]:
    stmt = select(Habit).order_by(Habit.created_at.asc())
    if goal_id is not None:
        stmt = stmt.where(Habit.goal_id == goal_id)
    if status is not None:
        stmt = stmt.where(Habit.status == status)
    if category is not None:
        stmt = stmt.where(Habit.category == category)
    return list(session.scalars(stmt))


def update_habit(
    session: Session,
    habit_id: str,
    title: str | None = None,
    description: str | None = None,
    category: str | None = None,
    frequency: str | None = None,
) -> Habit | None:
    habit = session.get(Habit, habit_id)
    if habit is None:
        return None
    if title is not None:
        habit.title = title
    if description is not None:
        habit.description = description
    if category is not None:
        habit.category = category
    if frequency is not None:
        habit.frequency = frequency
    session.flush()
    return habit


def archive_habit(session: Session, habit_id: str) -> Habit | None:
    habit = session.get(Habit, habit_id)
    if habit is None:
        return None
    habit.status = HabitStatus.ARCHIVED
    habit.archived_at = datetime.datetime.now(datetime.UTC)
    session.flush()
    return habit


def complete_habit(session: Session, habit_id: str, notes: str | None = None) -> HabitLog:
    log = HabitLog(habit_id=habit_id, notes=notes)
    session.add(log)
    session.flush()
    return log


def list_logs(session: Session, habit_id: str) -> list[HabitLog]:
    stmt = (
        select(HabitLog)
        .where(HabitLog.habit_id == habit_id)
        .order_by(HabitLog.completed_at.asc())
    )
    return list(session.scalars(stmt))
