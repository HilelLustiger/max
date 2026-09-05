import datetime

from db.models import Topic
from db.session import get_session
from db.topics import create_topic as db_create_topic
from db.topics import get_topic_by_name
from db.topics import list_topics as db_list_topics
from langchain_core.tools import tool

from app.llm.factory import get_provider
from app.news.pipeline import Entry, find_new_entries, summarize_entries

_provider = get_provider()

# In-process cache bridging the two tool calls below - single-replica deployment only (see
# #43's plan: splitting fetch from summarize keeps each tool call fast and independently
# checkpointed, but the summarize step needs what the fetch step already found without asking
# the LLM to transcribe raw articles through its own tool-call arguments).
_CACHE_TTL = datetime.timedelta(minutes=5)
_fetched_entries: dict[str, tuple[datetime.datetime, Topic, list[Entry]]] = {}


def _resolve_topics(session, topic: str | None) -> list[Topic] | str:
    """Returns the resolved topic list, or a Hebrew error string if resolution failed."""
    if topic is not None:
        found = get_topic_by_name(session, topic)
        if found is None:
            return f"לא נמצא נושא בשם '{topic}'."
        return [found]
    topics = db_list_topics(session, active=True)
    if not topics:
        return "אין נושאים פעילים."
    return topics


@tool
def create_topic(
    name: str, keywords: list[str] | None = None, sources: list[str] | None = None
) -> str:
    """Create a news topic to track, with optional keywords and RSS feed source URLs.

    sources must be actual RSS feed URLs (not homepage URLs) - if the user doesn't have any
    yet, create the topic without sources and let them add it later; never guess a feed URL.

    The result includes the topic's internal id ("מזהה") for your own bookkeeping - never
    mention it to the user, they don't need it.
    """
    with get_session() as session:
        topic = db_create_topic(session, name=name, keywords=keywords, sources=sources)
        details = [f"מזהה: {topic.id}", f"מספר מקורות: {len(topic.sources)}"]
        if topic.keywords:
            details.append(f"מילות מפתח: {', '.join(topic.keywords)}")
        return f"✅ הנושא '{topic.name}' נוצר ({', '.join(details)})"


@tool
def list_topics() -> str:
    """List all active news topics.

    When presenting the result to the user, phrase it naturally rather than dumping raw
    fields - mention each topic's name and, if it has keywords, weave those in naturally.
    """
    with get_session() as session:
        topics = db_list_topics(session, active=True)

    if not topics:
        return "אין נושאים פעילים."

    lines = []
    for topic in topics:
        details = [f"מספר מקורות: {len(topic.sources)}"]
        if topic.keywords:
            details.append(f"מילות מפתח: {', '.join(topic.keywords)}")
        lines.append(f"- {topic.name} ({', '.join(details)})")
    return "\n".join(lines)


@tool
def fetch_news_entries(topic: str | None = None) -> str:
    """Check a topic (or all active topics, if omitted) for new articles since the last digest.

    topic must match an existing topic's name exactly - call list_topics first if unsure.
    This only checks and reports how many new articles were found - it does NOT summarize
    them. If this reports new articles for a topic, call summarize_news with that same topic
    next to get the actual digest; never try to write the digest yourself from this result.
    """
    with get_session() as session:
        topics = _resolve_topics(session, topic)
        if isinstance(topics, str):
            return topics

        reports = []
        for t in topics:
            if not t.sources:
                continue
            entries = find_new_entries(session, t)
            if entries:
                _fetched_entries[t.id] = (datetime.datetime.now(datetime.UTC) + _CACHE_TTL, t, entries)
                reports.append(f"נמצאו {len(entries)} כתבות חדשות בנושא {t.name}.")
            else:
                reports.append(f"אין כתבות חדשות בנושא {t.name}.")

    if not reports:
        return "אין נושאים פעילים עם מקורות מוגדרים."
    return "\n".join(reports)


@tool
def summarize_news(topic: str | None = None) -> str:
    """Summarize the new articles a prior fetch_news_entries call found, for a topic (or all
    topics that had new articles, if omitted).

    Only works right after fetch_news_entries reported new articles - if nothing is cached for
    the requested topic (or fetch_news_entries wasn't called yet), this says so; call
    fetch_news_entries first in that case.
    """
    now = datetime.datetime.now(datetime.UTC)
    if topic is not None:
        with get_session() as session:
            found = get_topic_by_name(session, topic)
        if found is None:
            return f"לא נמצא נושא בשם '{topic}'."
        cached = _fetched_entries.get(found.id)
        if cached is None or cached[0] < now:
            return f"אין כתבות ממתינות לסיכום בנושא {topic} - יש להריץ קודם fetch_news_entries."
        topic_ids = [found.id]
    else:
        topic_ids = [tid for tid, (expires_at, _, _) in _fetched_entries.items() if expires_at >= now]
        if not topic_ids:
            return "אין כתבות ממתינות לסיכום - יש להריץ קודם fetch_news_entries."

    with get_session() as session:
        digests = []
        for topic_id in topic_ids:
            _, t, entries = _fetched_entries.pop(topic_id)
            digest = summarize_entries(session, t, entries, _provider)
            digests.append(f"## {t.name}\n{digest}")

    return "\n\n".join(digests)


NEWS_TOOLS = [create_topic, list_topics, fetch_news_entries, summarize_news]
