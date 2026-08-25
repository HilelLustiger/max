from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph

from app.graph.state import AgentState
from app.llm.contract import LLMProvider

SYSTEM_PROMPT = "You are a helpful personal assistant."


def _build_call_model(provider: LLMProvider):
    def call_model(state: AgentState) -> AgentState:
        response = provider.generate(state["messages"], system=SYSTEM_PROMPT)
        reply = AIMessage(
            content=response.text,
            usage_metadata={
                "input_tokens": response.input_tokens or 0,
                "output_tokens": response.output_tokens or 0,
                "total_tokens": (response.input_tokens or 0) + (response.output_tokens or 0),
            },
            response_metadata={
                "provider": response.provider,
                "model": response.model,
                "system_prompt": SYSTEM_PROMPT,
                "latency_ms": response.latency_ms,
                "cache_creation_input_tokens": response.cache_creation_input_tokens,
                "cache_read_input_tokens": response.cache_read_input_tokens,
                "finish_reason": response.finish_reason,
            },
        )
        return {"messages": [reply]}

    return call_model


def build_graph(provider: LLMProvider):
    graph = StateGraph(AgentState)
    graph.add_node("call_model", _build_call_model(provider))
    graph.add_edge(START, "call_model")
    graph.add_edge("call_model", END)
    return graph.compile()
