# ADR-0001: Multi-service architecture from day one

## Status

Accepted

## Context

The MVP is a Telegram bot, but the roadmap already includes a frontend UI, a Chrome extension, and connecting to external MCP servers for new skills. Each of those is a different interface talking to the same underlying "brain." We need to decide, at MVP time, whether to build one monolithic Telegram-coupled app or separate the interface from the reasoning core.

## Decision

We build one service per interface/concern, each in its own top-level directory in this monorepo, deployed as separate Railway services: `Agent` (Python) owns the actual agent — conversation orchestration, LLM calls, (future) MCP tool access, and exposes a generic `/chat` API with no knowledge of any specific channel. Channel-specific gateways (Telegram first) are their own top-level directories and call the Agent's API. `DB` is a shared package (not a running service) that any Python service depends on for persistence, so the schema isn't duplicated per service.

## Consequences

Easier: the Agent stays interface-agnostic, so the frontend and Chrome extension later reuse it without touching agent logic; each service can be developed, deployed, and scaled independently.

Harder: multiple services means multiple deploys, an internal network hop between a gateway and the Agent, and more operational surface than a single app for an MVP this small.

Revisit if: the network hop becomes a real latency problem, or if in practice only one interface ever gets built and the separation buys nothing.
