from db.habits import complete_habit as db_complete_habit
from db.habits import create_habit as db_create_habit
from db.habits import get_habit as db_get_habit
from db.habits import list_habits as db_list_habits
from db.models import HabitStatus
from db.session import get_session
from langchain_core.tools import tool


@tool
def create_habit(title: str, frequency: str = "daily") -> str:
    """Create a new recurring habit to track (e.g. frequency: "daily", "weekly")."""
    with get_session() as session:
        habit = db_create_habit(session, title=title, frequency=frequency)
        return f"✅ ההרגל '{habit.title}' נוצר (מזהה: {habit.id}, תדירות: {habit.frequency})"


@tool
def list_habits(status: str | None = None) -> str:
    """List habits. status must be 'active' or 'archived'; defaults to 'active'."""
    parsed_status = HabitStatus.ACTIVE
    if status is not None:
        try:
            parsed_status = HabitStatus(status)
        except ValueError:
            valid = ", ".join(s.value for s in HabitStatus)
            return f"סטטוס לא תקין '{status}'. יש לבחור אחד מבין: {valid}."

    with get_session() as session:
        habits = db_list_habits(session, status=parsed_status)

    if not habits:
        return "לא נמצאו הרגלים."

    return "\n".join(
        f"- {habit.title} (מזהה: {habit.id}, תדירות: {habit.frequency})" for habit in habits
    )


@tool
def log_habit(habit_id: str, notes: str | None = None) -> str:
    """Log a completion for a habit, given its id, with optional notes."""
    with get_session() as session:
        habit = db_get_habit(session, habit_id)
        if habit is None:
            return f"לא נמצא הרגל עם מזהה '{habit_id}'."
        log = db_complete_habit(session, habit_id, notes=notes)
        return f"✅ ההרגל '{habit.title}' נרשם ({log.completed_at.date().isoformat()})"


HABIT_TOOLS = [create_habit, list_habits, log_habit]
