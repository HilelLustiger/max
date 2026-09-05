import datetime
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from urllib.parse import urlparse

import feedparser
import httpx
from db.models import Topic
from db.topics import filter_undelivered, record_delivered
from langchain_core.messages import HumanMessage
from sqlalchemy.orm import Session

from app.llm.contract import LLMProvider

logger = logging.getLogger(__name__)

_ISRAELI_DOMAIN_SUFFIXES = (".co.il", ".org.il", ".net.il")
_FETCH_TIMEOUT_SECONDS = 5

SYSTEM_PROMPT = (
    "You curate a short news digest for one topic, for a friend catching up on their feed - "
    "not a report. You'll get the topic's keywords and a list of candidate articles (title, "
    "summary, link, origin). Keep only the articles genuinely relevant to the topic, but "
    "don't over-filter: when in doubt, lean toward including something loosely relevant "
    "over dropping it, since the reader would rather skim one extra line than miss a story.\n\n"
    "Write the digest in Hebrew, in a warm, conversational voice - like you're telling a "
    "friend what's going on, not filing a formal report. Group items by origin (see below), "
    "one bullet per item is fine, but each bullet should be 1-2 sentences with real "
    "substance - work in whatever concrete detail the summary actually gives (numbers, "
    "names, what changed and why), not just a bare restatement of the headline.\n\n"
    "Base every sentence ONLY on the given title and summary - never invent details, "
    "numbers, or context that aren't there, even to make the sentence flow better or fill "
    "it out - if the summary is thin, keep that item short rather than padding it.\n\n"
    "Mention each item's origin naturally when it adds context - say when something is "
    "from an Israeli source, and don't bother flagging the rest as anything but the "
    "implicit default (no need to say 'American' every time).\n\n"
    "End with one short, honest line: how many articles you looked at in total, and how "
    "many you left out as not relevant enough - so the reader can judge whether to loosen "
    "the topic's keywords if the digest feels thin. If none are relevant, just say so "
    "briefly in Hebrew, including the total you looked at."
)


@dataclass
class Entry:
    title: str
    link: str
    summary: str
    published_at: datetime.datetime | None
    is_israeli: bool


def _is_israeli(link: str) -> bool:
    domain = urlparse(link).netloc.lower()
    return domain.endswith(_ISRAELI_DOMAIN_SUFFIXES)


def _fetch_one(source: str) -> list[Entry]:
    try:
        if source.lstrip().startswith("<"):
            raw = source
        else:
            response = httpx.get(source, timeout=_FETCH_TIMEOUT_SECONDS, follow_redirects=True)
            response.raise_for_status()
            raw = response.content
    except Exception:
        logger.warning("news_source_fetch_failed", extra={"source": source}, exc_info=True)
        return []

    parsed = feedparser.parse(raw)
    entries = []
    for item in parsed.entries:
        published_at = None
        if getattr(item, "published_parsed", None):
            published_at = datetime.datetime(*item.published_parsed[:6], tzinfo=datetime.UTC)
        link = item.get("link", "")
        entries.append(
            Entry(
                title=item.get("title", ""),
                link=link,
                summary=item.get("summary", ""),
                published_at=published_at,
                is_israeli=_is_israeli(link),
            )
        )
    return entries


def fetch_entries(sources: list[str]) -> list[Entry]:
    """Fetch every source concurrently; a slow or failing source is skipped, not fatal."""
    if not sources:
        return []
    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        results = pool.map(_fetch_one, sources)
    return [entry for entries in results for entry in entries]


def find_new_entries(session: Session, topic: Topic) -> list[Entry]:
    """Fetch and dedup against DigestLog - no LLM call, this is the fast/cheap half."""
    entries = [e for e in fetch_entries(topic.sources) if e.link]
    undelivered_links = set(filter_undelivered(session, topic.id, [e.link for e in entries]))
    return [e for e in entries if e.link in undelivered_links]


def summarize_entries(
    session: Session, topic: Topic, entries: list[Entry], provider: LLMProvider
) -> str:
    """Summarize already-fetched, already-deduped entries and record them as delivered."""
    listing = "\n\n".join(
        f"Title: {entry.title}\nSummary: {entry.summary}\n"
        f"Origin: {'Israeli' if entry.is_israeli else 'default'}\nLink: {entry.link}"
        for entry in entries
    )
    prompt = (
        f"Topic: {topic.name}\nKeywords: {', '.join(topic.keywords)}\n\n"
        f"Candidate articles ({len(entries)} total):\n\n{listing}"
    )
    response = provider.generate([HumanMessage(content=prompt)], system=SYSTEM_PROMPT)

    record_delivered(session, topic.id, [(entry.link, entry.title) for entry in entries])
    return response.text
