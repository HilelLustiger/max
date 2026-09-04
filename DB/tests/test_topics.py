import pytest
from db.session import get_session
from db.topics import (
    create_topic,
    filter_undelivered,
    get_topic_by_name,
    list_topics,
    record_delivered,
)

pytestmark = pytest.mark.integration


def test_create_then_get_topic_round_trips(clean_db):
    with get_session() as session:
        created = create_topic(
            session, "AI", keywords=["artificial intelligence"], sources=["https://example.com/feed"]
        )
        found = get_topic_by_name(session, "AI")
        assert found.id == created.id
        assert found.keywords == ["artificial intelligence"]
        assert found.sources == ["https://example.com/feed"]
        assert found.active is True


def test_get_topic_by_name_returns_none_when_absent(clean_db):
    with get_session() as session:
        assert get_topic_by_name(session, "missing") is None


def test_list_topics_filters_by_active(clean_db):
    with get_session() as session:
        active = create_topic(session, "AI")
        archived = create_topic(session, "Archived")
        archived.active = False
        session.flush()

        active_topics = list_topics(session, active=True)
        assert [t.id for t in active_topics] == [active.id]


def test_filter_undelivered_excludes_already_logged_urls(clean_db):
    with get_session() as session:
        topic = create_topic(session, "AI")
        record_delivered(session, topic.id, [("https://example.com/a", "A")])

        remaining = filter_undelivered(
            session, topic.id, ["https://example.com/a", "https://example.com/b"]
        )
        assert remaining == ["https://example.com/b"]


def test_filter_undelivered_scopes_by_topic(clean_db):
    with get_session() as session:
        topic_a = create_topic(session, "AI")
        topic_b = create_topic(session, "Finance")
        record_delivered(session, topic_a.id, [("https://example.com/a", "A")])

        remaining = filter_undelivered(session, topic_b.id, ["https://example.com/a"])
        assert remaining == ["https://example.com/a"]
