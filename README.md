# max

A personal assistant AI agent, reachable first via Telegram, deployed on Railway.

Built as a foundation for a larger roadmap: a frontend UI, a Chrome extension, and MCP-server-powered skills, all sharing one agent core. See [PLAN.md](PLAN.md) for the full architecture, data model, and rationale (ADRs land in `ADR/` as the project grows).

## Structure

```
max/
├── PLAN.md                    # architecture plan and roadmap
├── ADR/                       # architecture decision records (coming as services are built)
├── Agent/                     # Python/FastAPI — the agent, LLM calls, persistence
└── .github/workflows/         # CI: delegates to each service's own scripts/ci.sh
```

Each service lives in its own top-level directory (e.g. `Agent/`) and owns its own dependencies, tests, and build — the root of this repo only orchestrates (CI, docs, cross-cutting decisions). The Telegram gateway and future services (frontend, Chrome extension) will each get their own top-level directory the same way.

## Status

Scaffolding stage — services are not yet implemented. Check `PLAN.md` for what's coming next.

## CI

`.github/workflows/ci.yml` runs one job per service. Each job does minimal environment setup (Node or Python) and then hands off entirely to that service's own `scripts/ci.sh`, which owns its install/lint/test/build steps. The root workflow never encodes service-specific commands directly — that keeps each service free to change its own tooling without touching CI config at the root.
