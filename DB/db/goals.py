import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Goal, GoalStatus


def create_goal(
    session: Session, title: str, description: str | None = None, category: str | None = None
) -> Goal:
    goal = Goal(title=title, description=description, category=category)
    session.add(goal)
    session.flush()
    return goal


def get_goal(session: Session, goal_id: str) -> Goal | None:
    return session.get(Goal, goal_id)


def list_goals(
    session: Session, status: GoalStatus | None = None, category: str | None = None
) -> list[Goal]:
    stmt = select(Goal).order_by(Goal.created_at.asc())
    if status is not None:
        stmt = stmt.where(Goal.status == status)
    if category is not None:
        stmt = stmt.where(Goal.category == category)
    return list(session.scalars(stmt))


def update_goal(
    session: Session,
    goal_id: str,
    title: str | None = None,
    description: str | None = None,
    category: str | None = None,
) -> Goal | None:
    goal = session.get(Goal, goal_id)
    if goal is None:
        return None
    if title is not None:
        goal.title = title
    if description is not None:
        goal.description = description
    if category is not None:
        goal.category = category
    session.flush()
    return goal


def complete_goal(session: Session, goal_id: str) -> Goal | None:
    goal = session.get(Goal, goal_id)
    if goal is None:
        return None
    goal.status = GoalStatus.COMPLETED
    goal.completed_at = datetime.datetime.now(datetime.UTC)
    session.flush()
    return goal


def archive_goal(session: Session, goal_id: str) -> Goal | None:
    goal = session.get(Goal, goal_id)
    if goal is None:
        return None
    goal.status = GoalStatus.ARCHIVED
    goal.archived_at = datetime.datetime.now(datetime.UTC)
    session.flush()
    return goal
