import pytest
from db.goals import create_goal
from db.habits import (
    archive_habit,
    complete_habit,
    create_habit,
    get_habit,
    list_habits,
    list_logs,
    update_habit,
)
from db.models import HabitStatus
from db.session import get_session

pytestmark = pytest.mark.integration


def test_get_habit_returns_none_when_absent(clean_db):
    with get_session() as session:
        assert get_habit(session, "missing") is None


def test_create_then_get_habit_round_trips(clean_db):
    with get_session() as session:
        created = create_habit(session, "Meditate")
        found = get_habit(session, created.id)
        assert found.title == "Meditate"
        assert found.frequency == "daily"
        assert found.status == HabitStatus.ACTIVE
        assert found.goal_id is None


def test_create_habit_linked_to_goal(clean_db):
    with get_session() as session:
        goal = create_goal(session, "Reduce stress")
        habit = create_habit(session, "Meditate", goal_id=goal.id)
        assert habit.goal_id == goal.id


def test_list_habits_filters_by_goal_and_excludes_archived_by_default(clean_db):
    with get_session() as session:
        goal = create_goal(session, "Reduce stress")
        linked = create_habit(session, "Meditate", goal_id=goal.id)
        unlinked = create_habit(session, "Stretch")
        archive_habit(session, unlinked.id)

        goal_habits = list_habits(session, goal_id=goal.id)
        assert [h.id for h in goal_habits] == [linked.id]

        active_habits = list_habits(session)
        assert [h.id for h in active_habits] == [linked.id]

        archived_habits = list_habits(session, status=HabitStatus.ARCHIVED)
        assert [h.id for h in archived_habits] == [unlinked.id]

        all_habits = list_habits(session, status=None)
        assert {h.id for h in all_habits} == {linked.id, unlinked.id}


def test_update_habit_changes_fields(clean_db):
    with get_session() as session:
        habit = create_habit(session, "Old title")
        updated = update_habit(session, habit.id, title="New title", frequency="weekly")
        assert updated.title == "New title"
        assert updated.frequency == "weekly"


def test_archive_habit_sets_status_and_timestamp(clean_db):
    with get_session() as session:
        habit = create_habit(session, "Meditate")
        archived = archive_habit(session, habit.id)
        assert archived.status == HabitStatus.ARCHIVED
        assert archived.archived_at is not None


def test_complete_habit_writes_log(clean_db):
    with get_session() as session:
        habit = create_habit(session, "Meditate")
        complete_habit(session, habit.id)
        complete_habit(session, habit.id, notes="felt great")

        logs = list_logs(session, habit.id)
        assert len(logs) == 2
        assert logs[0].notes is None
        assert logs[1].notes == "felt great"
