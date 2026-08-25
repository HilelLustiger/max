# Notes

Running list of loose ideas, gaps, and things flagged in passing that need a real decision or fix later. Not a spec, not a task tracker — just a catch-all so we don't lose track of things mentioned mid-conversation. Triage into ADRs, issues, or code as they come up.

- `Agent/app/llm/langchain_provider.py` logs nothing on its own. An Anthropic API failure produces no log line until `Agent/app/api/chat.py`'s `logger.exception(...)` catches it one layer up. Probably fine for MVP, but worth adding a log line at the provider layer if we need finer-grained visibility into *where* an LLM call failed (network vs. API error vs. timeout).
- Two separate settings classes both read `DATABASE_URL` independently: `Agent/app/config.py`'s `Settings` and `DB/db/session.py`'s `DBSettings`. Not broken today, but it's duplicated config with no single source of truth — worth collapsing into one if a third consumer of `DATABASE_URL` shows up, or if the two ever need to read it differently.
- `db.conversation.get_or_create_conversation` handles both the read and the create path in one function. Hilel doesn't like this — wants a separate get and a separate create rather than one function branching on whether a row exists. Revisit the split (and how `Agent/app/api/chat.py` calls it) before this pattern gets copied to other tables.
