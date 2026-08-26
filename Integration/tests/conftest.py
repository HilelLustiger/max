import os
import subprocess
import time
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://max:max@localhost:5432/max")

from db.session import get_session

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_URL = "http://127.0.0.1:8099"


@pytest.fixture(scope="session")
def agent_server():
    env = {
        **os.environ,
        "LLM_PROVIDER": "fake",
        "ANTHROPIC_API_KEY": "test",
    }
    process = subprocess.Popen(
        [
            "uv", "run", "--package", "agent", "uvicorn", "app.main:app",
            "--app-dir", "Agent", "--port", "8099",
        ],
        cwd=REPO_ROOT,
        env=env,
    )
    try:
        for _ in range(60):
            try:
                if httpx.get(f"{AGENT_URL}/health", timeout=1).status_code == 200:
                    break
            except httpx.TransportError:
                pass
            time.sleep(1)
        else:
            raise RuntimeError("agent-core did not become healthy in time")
        yield AGENT_URL
    finally:
        process.terminate()
        process.wait(timeout=10)


@pytest.fixture
def clean_db():
    with get_session() as session:
        session.execute(text("TRUNCATE events, llm_metrics, messages, conversations CASCADE"))
    yield
