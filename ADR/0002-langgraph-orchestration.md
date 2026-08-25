# ADR-0002: LangGraph as the agent orchestration engine

## Status

Accepted

## Context

The Agent needs to structure the model-call step now, and will need multi-step tool-calling loops later once it connects to MCP servers for new skills. Hand-rolling that loop (and its future branching/tool-call handling) is real work that a purpose-built library already solves.

## Decision

We use LangGraph's `StateGraph` to structure the Agent's reasoning, compiled **without a checkpointer** — LangGraph is not given responsibility for cross-turn conversation memory (see ADR-0004). For the MVP, the graph has a single `call_model` node.

## Consequences

Easier: gives us a natural, idiomatic place to add tool-calling nodes later for MCP-server-backed skills, without redesigning the control flow.

Harder: adds a dependency and LangGraph-specific vocabulary (nodes, state, edges) that has to be learned and kept consistent with our own domain vocabulary (docs/DOMAIN.md).

Revisit if: the single-node graph never grows past one step and the dependency stops earning its keep.
