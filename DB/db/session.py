import logging
from collections.abc import Iterator
from contextlib import contextmanager

from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)


class DBSettings(BaseSettings):
    database_url: str


_settings = DBSettings()
_engine = create_engine(_settings.database_url)
_SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)


def get_database_url() -> str:
    """The single source of truth for DATABASE_URL, for callers that need it directly
    (e.g. a driver that can't share SQLAlchemy's engine, like a psycopg connection pool)."""
    return _settings.database_url


@contextmanager
def get_session() -> Iterator[Session]:
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        logger.exception("db_transaction_failed", extra={"event": "db_transaction_failed"})
        session.rollback()
        raise
    finally:
        session.close()
