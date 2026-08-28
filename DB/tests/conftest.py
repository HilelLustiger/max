import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://max:max@localhost:5432/max")

import pytest
from db.session import get_session
from sqlalchemy import text


@pytest.fixture
def clean_db():
    with get_session() as session:
        session.execute(
            text(
                "TRUNCATE events, llm_metrics, messages, conversations, "
                "habit_logs, habits, tasks, goals CASCADE"
            )
        )
    yield
