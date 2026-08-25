# max

A personal assistant reachable through one or more channels (Telegram first), with a single reasoning core shared across all of them.

## Language

### Services

**Agent**:
The Python/FastAPI service that owns conversation state, calls the LLM, and persists everything. Channel-agnostic — it has no knowledge of Telegram or any other specific interface.
_Avoid_: Agent Core, brain, backend

**Gateway**:
A channel-specific service that translates one interface's protocol into calls against the Agent's API, and formats the Agent's replies back into that channel's format. Telegram Gateway is the first; a web frontend or Chrome extension would each be their own Gateway.
_Avoid_: bot, client, adapter

### Conversation & messages

**Conversation**:
A persisted thread of Messages scoped to a single channel (e.g. one Telegram chat = one Conversation). The same person talking to the assistant through a different channel starts a separate Conversation — unifying history across channels is a deliberate future feature, not assumed now.
_Avoid_: chat, thread, session

**Message**:
One turn within a Conversation, authored by either the user or the assistant, persisted so history can be replayed into the LLM's context.
_Avoid_: turn, update (that's the channel's raw event, not this)

### LLM layer

**LLM Provider**:
An implementation of the model-agnostic interface the Agent calls to generate a reply (e.g. the Anthropic provider). New providers are added without changing conversation or persistence logic.
_Avoid_: model, backend, vendor

**LLM Metrics**:
One recorded invocation of an LLM Provider for a single Message — captures provider, model, token counts, latency, and cost. This is the unit analytics/optimization work is built on.
_Avoid_: LLM call, request, completion, generation

### Analytics

**Event**:
An append-only record of a notable lifecycle point (message received, reply sent, error) used for usage/funnel analysis over time, distinct from LLM Metrics' per-model-invocation data.
_Avoid_: log, metric
