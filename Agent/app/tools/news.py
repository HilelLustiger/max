from db.session import get_session
from db.topics import create_topic as db_create_topic
from db.topics import get_topic_by_name
from db.topics import list_topics as db_list_topics
from langchain_core.tools import tool

from app.llm.factory import get_provider
from app.news.pipeline import build_digest

_provider = get_provider()


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
def get_latest_news(topic: str | None = None) -> str:
    """Get the latest news digest for a topic, or across all active topics if omitted.

    topic must match an existing topic's name exactly - call list_topics first if unsure.
    Only returns genuinely new articles since the last digest for that topic; if there's
    nothing new, says so instead of repeating old news.
    """
    with get_session() as session:
        if topic is not None:
            found = get_topic_by_name(session, topic)
            if found is None:
                return f"לא נמצא נושא בשם '{topic}'."
            topics = [found]
        else:
            topics = db_list_topics(session, active=True)

        if not topics:
            return "אין נושאים פעילים."

        digests = []
        for t in topics:
            if not t.sources:
                continue
            digest = build_digest(session, t, _provider)
            if digest:
                digests.append(f"## {t.name}\n{digest}")

    if not digests:
        return "אין חדשות חדשות כרגע."
    return "\n\n".join(digests)


NEWS_TOOLS = [create_topic, list_topics, get_latest_news]
