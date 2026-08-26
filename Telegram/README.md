# telegram-gateway

TypeScript/grammY service — receives Telegram messages via long polling and forwards them to the Agent's `/chat` API. Holds no conversation state or LLM logic itself; see [PLAN.md](../PLAN.md).

## Run locally

```
npm install
cp .env.example .env   # fill in TELEGRAM_BOT_TOKEN, get one from @BotFather
npm run dev
```

Requires the Agent service running (see [../Agent/README.md](../Agent/README.md)) and reachable at `AGENT_URL`.
