import datetime
from dataclasses import dataclass

import feedparser
from db.models import Topic
from db.topics import filter_undelivered, record_delivered
from langchain_core.messages import HumanMessage
from sqlalchemy.orm import Session

from app.llm.contract import LLMProvider

SYSTEM_PROMPT = (
    "You curate a short news digest for one topic. You'll get the topic's keywords and a "
    "list of candidate articles (title, summary, link). Keep only the articles genuinely "
    "relevant to the topic, rank them by relevance, and write the digest in Hebrew: for "
    "each kept article, a natural sentence with the title and a one-sentence summary - not "
    "a technical dump of fields. Skip articles that aren't relevant. If none are relevant, "
    "say so briefly in Hebrew."
)


@dataclass
class Entry:
    title: str
    link: str
    summary: str
    published_at: datetime.datetime | None


def fetch_entries(sources: list[str]) -> list[Entry]:
    entries = []
    for source in sources:
        parsed = feedparser.parse(source)
        for item in parsed.entries:
            published_at = None
            if getattr(item, "published_parsed", None):
                published_at = datetime.datetime(*item.published_parsed[:6], tzinfo=datetime.UTC)
            entries.append(
                Entry(
                    title=item.get("title", ""),
                    link=item.get("link", ""),
                    summary=item.get("summary", ""),
                    published_at=published_at,
                )
            )
    return entries


def build_digest(session: Session, topic: Topic, provider: LLMProvider) -> str | None:
    """Fetch, dedup against DigestLog, and summarize into a digest.

    Returns None when there are no new (undelivered) articles - a real LLM call isn't
    worth making just to say "nothing new".
    """
    entries = [e for e in fetch_entries(topic.sources) if e.link]
    undelivered_links = set(filter_undelivered(session, topic.id, [e.link for e in entries]))
    new_entries = [e for e in entries if e.link in undelivered_links]
    if not new_entries:
        return None

    listing = "\n\n".join(
        f"Title: {entry.title}\nSummary: {entry.summary}\nLink: {entry.link}"
        for entry in new_entries
    )
    prompt = (
        f"Topic: {topic.name}\nKeywords: {', '.join(topic.keywords)}\n\n"
        f"Candidate articles:\n\n{listing}"
    )
    response = provider.generate([HumanMessage(content=prompt)], system=SYSTEM_PROMPT)

    record_delivered(session, topic.id, [(entry.link, entry.title) for entry in new_entries])
    return response.text
