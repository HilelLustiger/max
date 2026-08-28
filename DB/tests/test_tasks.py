import pytest
from db.goals import create_goal
from db.models import TaskStatus
from db.session import get_session
from db.tasks import complete_task, create_task, get_task, list_tasks, update_task

pytestmark = pytest.mark.integration


def test_get_task_returns_none_when_absent(clean_db):
    with get_session() as session:
        assert get_task(session, "missing") is None


def test_create_then_get_task_round_trips(clean_db):
    with get_session() as session:
        created = create_task(session, "Buy running shoes")
        found = get_task(session, created.id)
        assert found.title == "Buy running shoes"
        assert found.status == TaskStatus.NOT_STARTED
        assert found.goal_id is None
        assert found.category is None


def test_create_task_with_category_and_no_goal(clean_db):
    with get_session() as session:
        task = create_task(session, "Renew passport", category="admin")
        assert task.category == "admin"
        assert task.goal_id is None


def test_create_task_linked_to_goal(clean_db):
    with get_session() as session:
        goal = create_goal(session, "Get fit")
        task = create_task(session, "Buy running shoes", goal_id=goal.id)
        assert task.goal_id == goal.id


def test_list_tasks_filters_by_goal_and_status(clean_db):
    with get_session() as session:
        goal = create_goal(session, "Get fit")
        linked = create_task(session, "Linked", goal_id=goal.id)
        create_task(session, "Unlinked")
        complete_task(session, linked.id)

        goal_tasks = list_tasks(session, goal_id=goal.id)
        assert [t.id for t in goal_tasks] == [linked.id]

        done_tasks = list_tasks(session, status=TaskStatus.DONE)
        assert [t.id for t in done_tasks] == [linked.id]


def test_list_tasks_filters_by_category(clean_db):
    with get_session() as session:
        work_task = create_task(session, "Write report", category="work")
        create_task(session, "Renew passport", category="admin")

        work_tasks = list_tasks(session, category="work")
        assert [t.id for t in work_tasks] == [work_task.id]


def test_update_task_changes_fields(clean_db):
    with get_session() as session:
        task = create_task(session, "Old title")
        updated = update_task(
            session, task.id, title="New title", category="work", status=TaskStatus.IN_PROGRESS
        )
        assert updated.title == "New title"
        assert updated.category == "work"
        assert updated.status == TaskStatus.IN_PROGRESS


def test_complete_task_sets_status_and_timestamp(clean_db):
    with get_session() as session:
        task = create_task(session, "Task")
        completed = complete_task(session, task.id)
        assert completed.status == TaskStatus.DONE
        assert completed.completed_at is not None
