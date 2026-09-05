import pytest
from app.llm.fake_provider import FakeProvider
from app.news.pipeline import fetch_entries, find_new_entries, summarize_entries
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

# Same article as SAMPLE_FEED's first item - simulates two feeds from the same publisher
# (e.g. a general feed and a topic-specific one) both carrying the same story.
OVERLAPPING_FEED = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<item>
  <title>Article One</title>
  <link>https://example.com/1</link>
  <description>Summary one, from a different feed</description>
</item>
</channel></rss>"""

# Nothing should be listening here - exercises the "a source fails" path without a real
# network dependency or waiting out the full fetch timeout.
UNREACHABLE_SOURCE = "http://localhost:1/does-not-exist"


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


def test_fetch_entries_skips_a_failing_source_without_failing_others():
    entries = fetch_entries([SAMPLE_FEED, UNREACHABLE_SOURCE])

    assert [e.title for e in entries] == ["Article One", "Article Two"]


def test_fetch_entries_dedups_the_same_article_across_sources():
    entries = fetch_entries([SAMPLE_FEED, OVERLAPPING_FEED])

    links = [e.link for e in entries]
    assert links.count("https://example.com/1") == 1
    assert len(entries) == 2


def test_find_new_entries_excludes_already_delivered(clean_db):
    with get_session() as session:
        topic = create_topic(session, "AI", sources=[SAMPLE_FEED])
        record_delivered(session, topic.id, [("https://example.com/1", "Article One")])

        new_entries = find_new_entries(session, topic)

        assert [e.title for e in new_entries] == ["Article Two"]


def test_summarize_entries_calls_provider_and_records_delivered(clean_db):
    with get_session() as session:
        topic = create_topic(session, "AI", keywords=["ai"], sources=[SAMPLE_FEED])
        new_entries = find_new_entries(session, topic)

        provider = FakeProvider()
        result = summarize_entries(session, topic, new_entries, provider)

        assert provider.call_count == 1
        assert "Article One" in provider.last_messages[-1].content
        assert "Article Two" in provider.last_messages[-1].content
        assert result.startswith("fake reply to:")

        remaining = filter_undelivered(
            session, topic.id, ["https://example.com/1", "https://example.com/2"]
        )
        assert remaining == []
