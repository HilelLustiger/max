import datetime

from db.models import TaskStatus
from db.session import get_session
from db.tasks import complete_task as db_complete_task
from db.tasks import create_task as db_create_task
from db.tasks import list_tasks as db_list_tasks
from langchain_core.tools import tool


def _parse_due_date(due_date: str | None) -> datetime.datetime | None:
    if due_date is None:
        return None
    return datetime.datetime.fromisoformat(due_date)


@tool
def create_task(title: str, category: str | None = None, due_date: str | None = None) -> str:
    """Create a new task.

    category is a free-text grouping label (e.g. "work", "health"), independent of any goal.
    due_date, if given, must be an ISO 8601 date or datetime string (e.g. "2026-09-01").

    If the user didn't specify a due_date, don't ask a free-text question for it - call
    request_clarification (field="due_date") with a few relative-date options instead
    (e.g. "Today", "Tomorrow", "Next week", "No due date"), then resolve the picked option
    to an ISO 8601 date yourself before calling this tool again.

    If the user didn't specify a category, don't ask a free-text question for it either -
    call list_tasks first to see categories already in use, then call request_clarification
    (field="category") offering those as options (plus "No category"). If no categories exist
    yet, skip clarification and leave category unset. Use list_tasks here only to collect
    category names - ignore everything else about the tasks it returns.
    """
    try:
        parsed_due_date = _parse_due_date(due_date)
    except ValueError:
        return f"תאריך יעד לא תקין '{due_date}'. יש להשתמש בפורמט ISO 8601, לדוגמה '2026-09-01'."

    with get_session() as session:
        task = db_create_task(session, title=title, category=category, due_date=parsed_due_date)
        details = [f"מזהה: {task.id}"]
        if task.category:
            details.append(f"קטגוריה: {task.category}")
        if task.due_date:
            details.append(f"יעד: {task.due_date.date().isoformat()}")
        return f"✅ המשימה '{task.title}' נוצרה ({', '.join(details)})"


@tool
def list_tasks(status: str | None = None, category: str | None = None) -> str:
    """List tasks, optionally filtered by status and/or category.

    status must be one of: not_started, in_progress, done. Omit to list all statuses.
    """
    parsed_status = None
    if status is not None:
        try:
            parsed_status = TaskStatus(status)
        except ValueError:
            valid = ", ".join(s.value for s in TaskStatus)
            return f"סטטוס לא תקין '{status}'. יש לבחור אחד מבין: {valid}."

    with get_session() as session:
        tasks = db_list_tasks(session, status=parsed_status, category=category)

    if not tasks:
        return "לא נמצאו משימות."

    lines = []
    for task in tasks:
        details = [f"סטטוס: {task.status.value}"]
        if task.category:
            details.append(f"קטגוריה: {task.category}")
        if task.due_date:
            details.append(f"יעד: {task.due_date.date().isoformat()}")
        lines.append(f"- {task.title} (מזהה: {task.id}, {', '.join(details)})")
    return "\n".join(lines)


@tool
def complete_task(task_id: str) -> str:
    """Mark a task as done, given its id."""
    with get_session() as session:
        task = db_complete_task(session, task_id)
    if task is None:
        return f"לא נמצאה משימה עם מזהה '{task_id}'."
    return f"✅ המשימה '{task.title}' הושלמה"


TASK_TOOLS = [create_task, list_tasks, complete_task]
