import os

# Forced, not defaulted: these tests assert the fake provider's exact output,
# so they must never fall through to a real Anthropic call even if the
# environment (e.g. CI) sets LLM_PROVIDER=anthropic for other purposes.
os.environ["LLM_PROVIDER"] = "fake"
os.environ["ANTHROPIC_API_KEY"] = "test"
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://max:max@localhost:5432/max")

import pytest
from db.session import get_session
from sqlalchemy import text


@pytest.fixture
def clean_db():
    """Integration tests share one Postgres instance; keep each test isolated. Opt in explicitly
    so unit tests never need a live database connection."""
    with get_session() as session:
        session.execute(
            text(
                "TRUNCATE events, llm_metrics, messages, conversations, "
                "habit_logs, habits, tasks, goals, digest_logs, topics CASCADE"
            )
        )
    yield
