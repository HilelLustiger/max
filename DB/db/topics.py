from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import DigestLog, Topic


def create_topic(
    session: Session,
    name: str,
    keywords: list[str] | None = None,
    sources: list[str] | None = None,
) -> Topic:
    topic = Topic(name=name, keywords=keywords or [], sources=sources or [])
    session.add(topic)
    session.flush()
    return topic


def get_topic_by_name(session: Session, name: str) -> Topic | None:
    stmt = select(Topic).where(Topic.name == name)
    return session.scalars(stmt).first()


def list_topics(session: Session, active: bool | None = None) -> list[Topic]:
    stmt = select(Topic).order_by(Topic.created_at.asc())
    if active is not None:
        stmt = stmt.where(Topic.active == active)
    return list(session.scalars(stmt))


def filter_undelivered(
    session: Session, topic_id: str, article_urls: list[str]
) -> list[str]:
    if not article_urls:
        return []
    stmt = select(DigestLog.article_url).where(
        DigestLog.topic_id == topic_id, DigestLog.article_url.in_(article_urls)
    )
    already_delivered = set(session.scalars(stmt))
    return [url for url in article_urls if url not in already_delivered]


def record_delivered(
    session: Session,
    topic_id: str,
    entries: list[tuple[str, str]],
) -> None:
    for article_url, title in entries:
        session.add(DigestLog(topic_id=topic_id, article_url=article_url, title=title))
    session.flush()
