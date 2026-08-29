import pytest
from app.graph.build import build_graph
from app.llm.fake_provider import FakeProvider
from app.tools.habits import HABIT_TOOLS
from db.habits import create_habit as db_create_habit
from db.habits import list_habits as db_list_habits
from db.habits import list_logs
from db.session import get_session
from langchain_core.messages import HumanMessage

pytestmark = pytest.mark.integration


def _tool_reply(name: str, args: dict) -> str:
    provider = FakeProvider(tool_calls=[{"name": name, "args": args, "id": "fake-call-1"}])
    graph = build_graph(provider, tools=HABIT_TOOLS)
    result = graph.invoke({"messages": [HumanMessage(content="doesn't matter")]})
    return result["messages"][-1].content


def test_create_habit_tool_persists_habit(clean_db):
    reply = _tool_reply("create_habit", {"title": "Meditate", "frequency": "daily"})
    assert "Meditate" in reply

    with get_session() as session:
        habits = db_list_habits(session)
        assert [h.title for h in habits] == ["Meditate"]


def test_list_habits_tool_returns_active_habits(clean_db):
    with get_session() as session:
        db_create_habit(session, "Meditate")

    reply = _tool_reply("list_habits", {})
    assert "Meditate" in reply


def test_list_habits_tool_reports_no_habits(clean_db):
    reply = _tool_reply("list_habits", {})
    assert "לא נמצאו הרגלים" in reply


def test_log_habit_tool_records_completion(clean_db):
    with get_session() as session:
        habit = db_create_habit(session, "Meditate")

    reply = _tool_reply("log_habit", {"habit_id": habit.id, "notes": "felt great"})
    assert "Meditate" in reply

    with get_session() as session:
        logs = list_logs(session, habit.id)
        assert len(logs) == 1
        assert logs[0].notes == "felt great"


def test_log_habit_tool_missing_id_returns_friendly_message(clean_db):
    reply = _tool_reply("log_habit", {"habit_id": "missing"})
    assert "לא נמצא הרגל" in reply
