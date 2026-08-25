# Personal Assistant Agent — MVP Foundation

## Context

Greenfield project (`/Users/hilel/Projects/max` is empty, not yet a git repo). Goal: a personal assistant AI agent reachable via Telegram, deployed on Railway, built as a **solid foundation** for a much larger roadmap (frontend UI, Chrome extension, MCP-server-powered skills) and treated **as a real product** — meaning data collection/analytics for performance optimization is part of the MVP, not an afterthought.

Confirmed decisions (via user Q&A):
- **Two services from day one**: a TypeScript Telegram gateway + a Python agent core. Future interfaces (frontend, extension) will become additional services talking to the same core.
- **LLM**: model-agnostic from day one via a small provider interface; only Anthropic Claude is implemented now, but swapping/adding a provider should not touch calling code.
- **Database**: Postgres (Railway-managed) — doubles as durable conversation state *and* the analytics store.
- **Memory**: full message history persisted per Telegram chat, replayed into context.

This plan defines the ADRs, Definition of Done, and the working scaffolding for both services.

## Repo Layout (monorepo, Railway multi-service via per-service root dir)

```
max/
├── ADR/
│   ├── template.md
│   ├── 0001-multi-service-architecture.md
│   ├── 0002-postgres-as-state-and-analytics-store.md
│   ├── 0003-anthropic-claude-direct-integration.md
│   └── 0004-telegram-long-polling-for-mvp.md
├── DEFINITION_OF_DONE.md
├── README.md
├── .gitignore
├── services/
│   ├── telegram-gateway/        (TypeScript, grammY)
│   │   ├── src/{index.ts,bot.ts,agentClient.ts,config.ts}
│   │   ├── package.json, tsconfig.json, Dockerfile, .env.example
│   └── agent-core/              (Python, FastAPI)
│       ├── app/
│       │   ├── main.py                # FastAPI app, /health, router mount
│       │   ├── api/chat.py            # POST /chat
│       │   ├── llm/base.py            # LLMProvider Protocol: generate(messages) -> LLMResponse
│       │   ├── llm/anthropic_provider.py # Claude implementation of LLMProvider
│       │   ├── llm/factory.py         # get_provider() reads LLM_PROVIDER env var
│       │   ├── agent/conversation.py  # loads history, builds prompt, persists turn
│       │   ├── db/models.py           # SQLAlchemy: conversations, messages, llm_metrics, events
│       │   ├── db/session.py
│       │   └── config.py
│       ├── alembic/ (migrations) + alembic.ini
│       ├── pyproject.toml, Dockerfile, .env.example
```

## Data Model (Postgres — this IS the analytics foundation)

- `conversations`: id, telegram_chat_id (unique), created_at
- `messages`: id, conversation_id FK, role (user/assistant), content, created_at
- `llm_metrics`: id, message_id FK, provider, model, input_tokens, output_tokens, latency_ms, cost_usd, error (nullable), created_at — the row that lets you later analyze cost/latency/quality trends, including across providers
- `events`: id, conversation_id FK nullable, type, payload (jsonb), created_at — generic append-only log (message received, reply sent, error) for future funnel/usage analysis

Alembic manages migrations from the start so schema evolution is trackable (important since more services/features are coming).

## LLM Provider Abstraction

To keep the agent model-agnostic without over-engineering the MVP:

- `llm/base.py` defines a minimal `LLMProvider` Protocol: one method, `generate(messages: list[Message], system: str) -> LLMResponse`, where `LLMResponse` carries `text, model, input_tokens, output_tokens, latency_ms`. No streaming, no tool-calling abstraction yet — just enough surface for the current chat flow.
- `llm/anthropic_provider.py` is the only concrete implementation for MVP, wrapping the Anthropic SDK and filling in token/latency fields from the SDK response.
- `llm/factory.py` exposes `get_provider()`, selecting the implementation from an `LLM_PROVIDER` env var (default `anthropic`). Adding OpenAI/Gemini/etc. later means writing one new file that satisfies the Protocol and registering it in the factory — no changes to `conversation.py`, the DB layer, or the API route.
- `llm_metrics.model` (see Data Model) is stored per-call, not assumed constant, so analytics stay correct even after a provider switch or A/B test between models.

## Observability & Metrics

Two complementary layers, both live from the MVP, not bolted on later:

1. **Structured logs (operational/debugging)** — both services log structured JSON lines to stdout (no logging infra to stand up; Railway captures stdout automatically and shows it, filterable, in its dashboard per-service). Every request gets a `request_id` (generated in the gateway, passed to agent-core in a header) so a single Telegram message can be traced end-to-end across both services' logs. Log fields include: request_id, telegram_chat_id, event (e.g. `message_received`, `llm_call_start`, `llm_call_end`, `error`), and relevant timings.

2. **Durable metrics (analytics/optimization — queryable, not just grep-able)** — this is the `llm_metrics` and `events` tables in Postgres:
   - `llm_metrics` row per model call: provider, model, input_tokens, output_tokens, latency_ms, error. This alone answers "what's my token spend/cost trend", "which model/latency distribution", "error rate over time" via plain SQL.
   - `events` row per notable lifecycle point (message received, reply sent, error) with a jsonb payload, giving you a generic timeline for later funnel/usage analysis (e.g. daily active chats, messages/day) without needing a third-party analytics tool yet.
   - Both tables carry `created_at`, so time-series analysis is just SQL `GROUP BY date_trunc(...)`. You can point any BI tool (Metabase, a notebook, Railway's Postgres directly via `psql`) at these tables later — no export/ETL step needed since it's already relational.
   - Cost tracking: `agent-core` computes an approximate `cost_usd` at insert time from a small static price table keyed by `(provider, model)`, so cost analysis doesn't require re-deriving it from token counts later.

This gives you two views for two purposes: logs to debug a single request right now, DB tables to analyze trends over time — which is the "track and optimize like a real product" ask.

## Request Flow (MVP)

1. `telegram-gateway` runs grammY in **long-polling** mode (simplest for MVP; no public webhook plumbing needed — see ADR-0004) and receives a message.
2. Gateway POSTs `{telegram_chat_id, text, telegram_user}` to `agent-core`'s `/chat` (via Railway private network URL `agent-core.railway.internal`, configurable through `AGENT_CORE_URL` env var).
3. `agent-core`: upserts `conversations` row, loads recent `messages` for that conversation, calls Claude with history, records the exchange in `messages`, records timing/token usage in `llm_metrics`, logs an `events` row.
4. Gateway receives `{reply}` and sends it back to the Telegram user; on any failure from agent-core, gateway sends a friendly fallback message rather than crashing.

## ADRs to write

1. **0001 — Multi-service architecture**: TS gateway (interface-specific, matches future frontend/extension JS stack) + Python agent-core (single reusable "brain", best LLM/MCP ecosystem). Rationale + consequence: extra network hop and two deploys, accepted for long-term reuse across interfaces.
2. **0002 — Postgres as state + analytics store**: one database serves durable conversation memory and product analytics for now; revisit only if analytics volume/needs outgrow OLTP Postgres.
3. **0003 — Model-agnostic LLM layer, Anthropic as first implementation**: a minimal `LLMProvider` Protocol isolates the rest of the app from any single vendor SDK; Anthropic Claude is the only implementation built for MVP (fits the planned "connect more MCP servers for skills" roadmap since Claude is MCP-native), but adding/switching providers later is a single new file, not a refactor.
4. **0004 — Telegram long polling for MVP**: avoids webhook/public-HTTPS/route setup complexity; acceptable at personal-assistant scale; note as revisit trigger if latency/scale demands webhooks.

Each ADR uses the standard Status/Context/Decision/Consequences shape (template.md included).

## Definition of Done (MVP)

Written to `DEFINITION_OF_DONE.md`, includes concrete, testable bullets such as:
- Message → Telegram bot → Claude-generated reply round trip works end-to-end on Railway.
- Conversation history survives a service restart (proven by DB row, not memory).
- Every LLM call has a corresponding `llm_metrics` row with provider, model, latency, token counts, and estimated cost.
- Switching `LLM_PROVIDER` (or adding a second `LLMProvider` implementation) requires no changes outside the `llm/` package.
- Logs are structured JSON with a `request_id` traceable across both services for a single Telegram message.
- Both services have Railway health checks and deploy independently from the monorepo.
- No secrets committed; `.env.example` documents required vars for each service.
- Claude API failure produces a user-visible fallback message, not a crash/silent drop.
- README covers local dev (run both services + local/hosted Postgres) and Railway deploy steps.

## Verification

- Local: run agent-core (`uvicorn app.main:app`) against a local/Railway Postgres, `curl` the `/chat` endpoint directly to confirm a Claude reply + DB rows appear.
- Local: run telegram-gateway against a real bot token (test bot) pointed at local agent-core, message it from Telegram, confirm round trip.
- Inspect `llm_metrics`/`events` tables after a few exchanges to confirm analytics data is captured.
- Note: actual Railway deploy and Telegram bot token/Anthropic key provisioning require user-owned credentials — I'll scaffold Railway config (`railway.toml` per service) but cannot execute the deploy or create the bot token myself.

## Open items I will decide pragmatically while building (flagging, not blocking)

- Use `grammY` (TS) and `python-telegram-bot`-free approach — agent-core has no Telegram dependency at all, just a generic `/chat` API, keeping it interface-agnostic for future frontend/extension use.
- `git init` the repo and make an initial commit once scaffolding is in place (only after showing you the result — I won't push anywhere).
