import pytest
from app.graph.build import build_graph
from app.llm.fake_provider import FakeProvider
from app.tools.news import NEWS_TOOLS
from db.session import get_session
from db.topics import create_topic as db_create_topic
from db.topics import list_topics as db_list_topics
from db.topics import record_delivered
from langchain_core.messages import HumanMessage

pytestmark = pytest.mark.integration

SAMPLE_FEED = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<item>
  <title>Article One</title>
  <link>https://example.com/1</link>
  <description>Summary one</description>
</item>
</channel></rss>"""


def _tool_reply(name: str, args: dict) -> str:
    provider = FakeProvider(tool_calls=[{"name": name, "args": args, "id": "fake-call-1"}])
    graph = build_graph(provider, tools=NEWS_TOOLS)
    result = graph.invoke({"messages": [HumanMessage(content="doesn't matter")]})
    return result["messages"][-1].content


def _call_tool_directly(name: str, args: dict) -> str:
    """Bypass the graph for a raw tool result, needed when chaining fetch -> summarize since
    each call above builds a fresh graph/thread and the two tools share process-level cache
    state, not per-thread state."""
    tool = next(t for t in NEWS_TOOLS if t.name == name)
    return tool.invoke(args)


def test_create_topic_tool_persists_topic(clean_db):
    reply = _tool_reply(
        "create_topic", {"name": "AI", "keywords": ["ai"], "sources": [SAMPLE_FEED]}
    )
    assert "AI" in reply

    with get_session() as session:
        topics = db_list_topics(session)
        assert [t.name for t in topics] == ["AI"]
        assert topics[0].keywords == ["ai"]


def test_list_topics_tool_returns_created_topics(clean_db):
    with get_session() as session:
        db_create_topic(session, "AI")
        db_create_topic(session, "Finance")

    reply = _tool_reply("list_topics", {})
    assert "AI" in reply
    assert "Finance" in reply


def test_list_topics_tool_reports_no_topics(clean_db):
    reply = _tool_reply("list_topics", {})
    assert "אין נושאים פעילים" in reply


def test_fetch_news_entries_reports_missing_topic(clean_db):
    reply = _call_tool_directly("fetch_news_entries", {"topic": "missing"})
    assert "לא נמצא נושא" in reply


def test_fetch_news_entries_reports_no_active_topics(clean_db):
    reply = _call_tool_directly("fetch_news_entries", {})
    assert "אין נושאים פעילים" in reply


def test_fetch_news_entries_reports_new_articles(clean_db):
    with get_session() as session:
        db_create_topic(session, "AI", sources=[SAMPLE_FEED])

    reply = _call_tool_directly("fetch_news_entries", {"topic": "AI"})
    assert "נמצאו" in reply
    assert "AI" in reply


def test_fetch_news_entries_reports_nothing_new(clean_db):
    with get_session() as session:
        topic = db_create_topic(session, "AI", sources=[SAMPLE_FEED])
        record_delivered(session, topic.id, [("https://example.com/1", "Article One")])

    reply = _call_tool_directly("fetch_news_entries", {"topic": "AI"})
    assert "אין כתבות חדשות" in reply


def test_summarize_news_without_prior_fetch_reports_nothing_cached(clean_db):
    with get_session() as session:
        db_create_topic(session, "AI", sources=[SAMPLE_FEED])

    reply = _call_tool_directly("summarize_news", {"topic": "AI"})
    assert "יש להריץ קודם fetch_news_entries" in reply


def test_summarize_news_after_fetch_returns_digest(clean_db):
    with get_session() as session:
        db_create_topic(session, "AI", sources=[SAMPLE_FEED])

    fetch_reply = _call_tool_directly("fetch_news_entries", {"topic": "AI"})
    assert "נמצאו" in fetch_reply

    summarize_reply = _call_tool_directly("summarize_news", {"topic": "AI"})
    assert "AI" in summarize_reply

    # Cache is consumed - a second summarize without a new fetch has nothing left.
    second_reply = _call_tool_directly("summarize_news", {"topic": "AI"})
    assert "יש להריץ קודם fetch_news_entries" in second_reply
