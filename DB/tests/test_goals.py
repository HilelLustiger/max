import pytest
from db.goals import archive_goal, complete_goal, create_goal, get_goal, list_goals, update_goal
from db.models import GoalStatus
from db.session import get_session

pytestmark = pytest.mark.integration


def test_get_goal_returns_none_when_absent(clean_db):
    with get_session() as session:
        assert get_goal(session, "missing") is None


def test_create_then_get_goal_round_trips(clean_db):
    with get_session() as session:
        created = create_goal(session, "Get fit", description="Run a 10k")
        found = get_goal(session, created.id)
        assert found.title == "Get fit"
        assert found.status == GoalStatus.ACTIVE


def test_list_goals_filters_by_status(clean_db):
    with get_session() as session:
        active = create_goal(session, "Active goal")
        done = create_goal(session, "Done goal")
        complete_goal(session, done.id)

        active_goals = list_goals(session, status=GoalStatus.ACTIVE)
        assert [g.id for g in active_goals] == [active.id]


def test_create_goal_with_category(clean_db):
    with get_session() as session:
        goal = create_goal(session, "Get fit", category="health")
        assert goal.category == "health"


def test_list_goals_filters_by_category(clean_db):
    with get_session() as session:
        work = create_goal(session, "Ship project", category="work")
        create_goal(session, "Get fit", category="health")

        work_goals = list_goals(session, category="work")
        assert [g.id for g in work_goals] == [work.id]


def test_update_goal_changes_fields(clean_db):
    with get_session() as session:
        goal = create_goal(session, "Old title")
        updated = update_goal(session, goal.id, title="New title", category="health")
        assert updated.title == "New title"
        assert updated.category == "health"


def test_complete_goal_sets_status_and_timestamp(clean_db):
    with get_session() as session:
        goal = create_goal(session, "Goal")
        completed = complete_goal(session, goal.id)
        assert completed.status == GoalStatus.COMPLETED
        assert completed.completed_at is not None
        assert completed.archived_at is None


def test_archive_goal_sets_status_and_timestamp(clean_db):
    with get_session() as session:
        goal = create_goal(session, "Goal")
        archived = archive_goal(session, goal.id)
        assert archived.status == GoalStatus.ARCHIVED
        assert archived.archived_at is not None
        assert archived.completed_at is None
