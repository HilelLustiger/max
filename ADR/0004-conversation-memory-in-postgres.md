# ADR-0004: Conversation memory lives in our own Postgres tables, not LangGraph's checkpointer

## Status

Accepted

## Context

LangGraph ships a built-in checkpointer mechanism (including a Postgres-backed one) that can automatically persist and restore graph state per thread. Using it for cross-turn conversation memory would mean less code to write. But the project's stated goal is to treat this as a real product — collecting queryable data to analyze and optimize performance — and LangGraph's checkpoint format is an opaque serialized blob, not something you'd want to run analytics SQL against.

## Decision

`Conversation` and `Message` (see docs/DOMAIN.md) are our own Postgres tables, owned by the shared `DB` package, and are the source of truth for conversation history. Each turn, the Agent loads recent `Message` rows itself and passes them into the LangGraph invocation explicitly. LangGraph's checkpointer is not used for cross-turn memory.

## Consequences

Easier: conversation data is fully queryable and analyzable via plain SQL from day one, and stays that way regardless of what orchestration library sits on top of it.

Harder: we write and maintain our own history-loading code instead of getting persistence for free from LangGraph.

Revisit if: the manual history-loading code becomes a real maintenance burden relative to the analytics value it provides.
