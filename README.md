# max

A personal assistant AI agent, reachable first via Telegram, deployed on Railway.

Built as a foundation for a larger roadmap: a frontend UI, a Chrome extension, and MCP-server-powered skills, all sharing one agent core. See [docs/DOMAIN.md](docs/DOMAIN.md) for the project glossary.

## Structure

```
max/
├── Agent/                     # Python/FastAPI — the agent, LLM calls, persistence
├── DB/                        # shared Python package — Postgres models, migrations
├── Telegram/                  # TypeScript/grammY — Telegram gateway, calls Agent's /chat
└── .github/workflows/         # CI: delegates to each service's own scripts/ci.sh
```

Each service lives in its own top-level directory (e.g. `Agent/`) and owns its own dependencies, tests, and build — the root of this repo only orchestrates (CI, docs, cross-cutting decisions). Future services (frontend, Chrome extension) will each get their own top-level directory the same way.

## Status

- `Agent`: implemented and working end-to-end locally — `/chat` persists conversation history to Postgres, calls Claude via a model-agnostic LLM layer, and records per-call metrics.
- `DB`: shared Postgres models + Alembic migrations, used by `Agent`.
- `Telegram`: scaffolded (grammY, long polling) — forwards messages to `Agent`'s `/chat`; not yet run against a live bot token.

Not yet deployed to Railway.

## CI

`.github/workflows/ci.yml` runs one job per service. Each job does minimal environment setup (Node or Python) and then hands off entirely to that service's own `scripts/ci.sh`, which owns its install/lint/test/build steps. The root workflow never encodes service-specific commands directly — that keeps each service free to change its own tooling without touching CI config at the root.
