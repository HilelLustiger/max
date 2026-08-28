import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Task, TaskStatus


def create_task(
    session: Session,
    title: str,
    goal_id: str | None = None,
    category: str | None = None,
    description: str | None = None,
    due_date: datetime.datetime | None = None,
) -> Task:
    task = Task(
        title=title,
        goal_id=goal_id,
        category=category,
        description=description,
        due_date=due_date,
    )
    session.add(task)
    session.flush()
    return task


def get_task(session: Session, task_id: str) -> Task | None:
    return session.get(Task, task_id)


def list_tasks(
    session: Session,
    goal_id: str | None = None,
    category: str | None = None,
    status: TaskStatus | None = None,
) -> list[Task]:
    stmt = select(Task).order_by(Task.created_at.asc())
    if goal_id is not None:
        stmt = stmt.where(Task.goal_id == goal_id)
    if category is not None:
        stmt = stmt.where(Task.category == category)
    if status is not None:
        stmt = stmt.where(Task.status == status)
    return list(session.scalars(stmt))


def update_task(
    session: Session,
    task_id: str,
    title: str | None = None,
    category: str | None = None,
    description: str | None = None,
    due_date: datetime.datetime | None = None,
    status: TaskStatus | None = None,
) -> Task | None:
    task = session.get(Task, task_id)
    if task is None:
        return None
    if title is not None:
        task.title = title
    if category is not None:
        task.category = category
    if description is not None:
        task.description = description
    if due_date is not None:
        task.due_date = due_date
    if status is not None:
        task.status = status
    session.flush()
    return task


def complete_task(session: Session, task_id: str) -> Task | None:
    task = session.get(Task, task_id)
    if task is None:
        return None
    task.status = TaskStatus.DONE
    task.completed_at = datetime.datetime.now(datetime.UTC)
    session.flush()
    return task
