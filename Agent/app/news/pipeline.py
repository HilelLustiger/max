import datetime
from dataclasses import dataclass
from urllib.parse import urlparse

import feedparser
from db.models import Topic
from db.topics import filter_undelivered, record_delivered
from langchain_core.messages import HumanMessage
from sqlalchemy.orm import Session

from app.llm.contract import LLMProvider

_ISRAELI_DOMAIN_SUFFIXES = (".co.il", ".org.il", ".net.il")

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


def fetch_entries(sources: list[str]) -> list[Entry]:
    entries = []
    for source in sources:
        parsed = feedparser.parse(source)
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
        f"Title: {entry.title}\nSummary: {entry.summary}\n"
        f"Origin: {'Israeli' if entry.is_israeli else 'default'}\nLink: {entry.link}"
        for entry in new_entries
    )
    prompt = (
        f"Topic: {topic.name}\nKeywords: {', '.join(topic.keywords)}\n\n"
        f"Candidate articles ({len(new_entries)} total):\n\n{listing}"
    )
    response = provider.generate([HumanMessage(content=prompt)], system=SYSTEM_PROMPT)

    record_delivered(session, topic.id, [(entry.link, entry.title) for entry in new_entries])
    return response.text
