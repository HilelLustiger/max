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


@contextmanager
def get_session() -> Iterator[Session]:
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        logger.exception("DB transaction failed, rolling back")
        session.rollback()
        raise
    finally:
        session.close()
