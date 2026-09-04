import pytest
from app.llm.fake_provider import FakeProvider
from app.news.pipeline import build_digest, fetch_entries
from db.session import get_session
from db.topics import create_topic, filter_undelivered, record_delivered

pytestmark = pytest.mark.integration

SAMPLE_FEED = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<item>
  <title>Article One</title>
  <link>https://example.com/1</link>
  <description>Summary one</description>
  <pubDate>Mon, 01 Jan 2026 00:00:00 GMT</pubDate>
</item>
<item>
  <title>Article Two</title>
  <link>https://example.com/2</link>
  <description>Summary two</description>
</item>
</channel></rss>"""

EMPTY_FEED = """<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>"""


def test_fetch_entries_parses_feed_items():
    entries = fetch_entries([SAMPLE_FEED])

    assert [e.title for e in entries] == ["Article One", "Article Two"]
    assert entries[0].link == "https://example.com/1"
    assert entries[0].summary == "Summary one"
    assert entries[0].published_at is not None
    assert entries[1].published_at is None


def test_fetch_entries_merges_multiple_sources():
    entries = fetch_entries([SAMPLE_FEED, EMPTY_FEED])

    assert len(entries) == 2


def test_build_digest_returns_none_when_no_new_entries(clean_db):
    with get_session() as session:
        topic = create_topic(session, "AI", sources=[SAMPLE_FEED])
        record_delivered(
            session,
            topic.id,
            [("https://example.com/1", "Article One"), ("https://example.com/2", "Article Two")],
        )

        provider = FakeProvider()
        result = build_digest(session, topic, provider)

        assert result is None
        assert provider.call_count == 0


def test_build_digest_summarizes_only_new_entries_and_records_them(clean_db):
    with get_session() as session:
        topic = create_topic(session, "AI", keywords=["ai"], sources=[SAMPLE_FEED])
        record_delivered(session, topic.id, [("https://example.com/1", "Article One")])

        provider = FakeProvider()
        result = build_digest(session, topic, provider)

        assert provider.call_count == 1
        assert "Article Two" in provider.last_messages[-1].content
        assert "Article One" not in provider.last_messages[-1].content
        assert result.startswith("fake reply to:")

        remaining = filter_undelivered(session, topic.id, ["https://example.com/2"])
        assert remaining == []
