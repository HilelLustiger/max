# ADR-0005: DB as a shared top-level package, not code inside Agent

## Status

Accepted

## Context

Postgres is meant to be shared foundation for the whole project as it grows — more services beyond the Agent, more data beyond conversations. If the schema and persistence code live inside `Agent/`, any future Python service needing the same data would either duplicate that code or import across service boundaries in an ad hoc way, and the schema/migration history could drift between copies.

## Decision

`DB/` is a standalone top-level package (not a running service) owning the SQLAlchemy models, Alembic migrations, and session/repository helper functions. It's a member of a repo-root `uv` workspace. Any Python service — starting with `Agent/` — takes `DB` as a workspace dependency and talks to persistence only through its repository functions; no service owns its own copy of the schema.

## Consequences

Easier: one schema, one migration history, no drift between services as more Python services get added.

Harder: introduces `uv` workspace/packaging structure earlier than strictly needed for a single-service MVP.

Revisit if: no second Python service materializes for a long time and the workspace split turns out to have bought nothing.
