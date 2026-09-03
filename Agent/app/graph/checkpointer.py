from db.session import get_database_url
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


def _psycopg_conninfo() -> str:
    # PostgresSaver wants a plain psycopg DSN; DB's DATABASE_URL is SQLAlchemy-dialect-prefixed.
    return get_database_url().replace("postgresql+psycopg://", "postgresql://")


def build_checkpointer() -> PostgresSaver:
    """A single connection pool for the lifetime of the process - separate from SQLAlchemy's
    own engine/pool in db.session, since PostgresSaver drives its own psycopg connections."""
    pool = ConnectionPool(
        conninfo=_psycopg_conninfo(),
        min_size=1,
        max_size=5,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=True,
    )
    checkpointer = PostgresSaver(pool)
    checkpointer.setup()
    return checkpointer
