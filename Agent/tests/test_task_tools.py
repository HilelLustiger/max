import pytest
from app.graph.build import MAX_TOOL_RESULT_CHARS, build_graph
from app.llm.fake_provider import FakeProvider
from app.tools.tasks import TASK_TOOLS
from db.models import TaskStatus
from db.session import get_session
from db.tasks import create_task as db_create_task
from db.tasks import get_task
from db.tasks import list_tasks as db_list_tasks
from langchain_core.messages import HumanMessage, ToolMessage

pytestmark = pytest.mark.integration


def _invoke_tool(name: str, args: dict) -> list:
    provider = FakeProvider(tool_calls=[{"name": name, "args": args, "id": "fake-call-1"}])
    graph = build_graph(provider, tools=TASK_TOOLS)
    result = graph.invoke({"messages": [HumanMessage(content="doesn't matter")]})
    return result["messages"]


def _tool_reply(name: str, args: dict) -> str:
    return _invoke_tool(name, args)[-1].content


def _tool_message_content(name: str, args: dict) -> str:
    messages = _invoke_tool(name, args)
    return next(m for m in messages if isinstance(m, ToolMessage)).content


def test_create_task_tool_persists_task(clean_db):
    reply = _tool_reply("create_task", {"title": "Buy milk", "category": "home"})
    assert "Buy milk" in reply

    with get_session() as session:
        tasks = db_list_tasks(session)
        assert [t.title for t in tasks] == ["Buy milk"]
        assert tasks[0].category == "home"


def test_list_tasks_tool_returns_created_tasks(clean_db):
    with get_session() as session:
        db_create_task(session, "Write report", category="work")
        db_create_task(session, "Buy milk", category="home")

    reply = _tool_reply("list_tasks", {"category": "work"})
    assert "Write report" in reply
    assert "Buy milk" not in reply


def test_list_tasks_tool_reports_no_tasks(clean_db):
    reply = _tool_reply("list_tasks", {})
    assert "no tasks" in reply.lower()


def test_list_tasks_tool_output_is_capped_for_many_tasks(clean_db):
    with get_session() as session:
        for i in range(500):
            db_create_task(session, f"Task number {i} with a fairly long descriptive title")

    content = _tool_message_content("list_tasks", {})
    assert content.endswith("... [truncated]")
    assert len(content) <= MAX_TOOL_RESULT_CHARS + len("... [truncated]")


def test_complete_task_tool_marks_done(clean_db):
    with get_session() as session:
        task = db_create_task(session, "Buy milk")

    reply = _tool_reply("complete_task", {"task_id": task.id})
    assert "Completed" in reply

    with get_session() as session:
        assert get_task(session, task.id).status == TaskStatus.DONE


def test_complete_task_tool_missing_id_returns_friendly_message(clean_db):
    reply = _tool_reply("complete_task", {"task_id": "missing"})
    assert "No task found" in reply
