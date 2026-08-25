# ADR-0003: LLMProvider Protocol as a thin wrapper over LangChain chat models

## Status

Accepted

## Context

LangChain (which LangGraph is built on) already gives model-agnosticism across chat completion providers via its chat model classes (e.g. `ChatAnthropic`). It's tempting to call those directly from graph nodes and skip writing our own abstraction. But we anticipate needs LangChain's chat model interface won't cleanly cover later — a non-LangChain or local backend, or cross-cutting logic (retries, caching, moderation) we want applied uniformly regardless of provider — and we don't want that seam to require touching graph or API code when it arrives.

## Decision

We keep a small `LLMProvider` Protocol (`generate(messages, system) -> LLMResponse`). For the MVP, exactly one implementation exists — `LangChainProvider` — which internally delegates to a LangChain chat model and maps its output (text, token counts, latency) into `LLMResponse`. The Agent's graph and API code depend only on the Protocol, never on a LangChain chat model directly.

## Consequences

Easier: adding a provider that doesn't fit LangChain's shape, or adding cross-cutting logic uniformly, is a change contained to the `llm/` package.

Harder: one extra layer of indirection for what is, today, a single implementation — a thin wrapper with no real alternative yet.

Revisit if: LangChain's abstraction always turns out sufficient and the Protocol never gains a second implementation — at that point drop it and call LangChain directly.
