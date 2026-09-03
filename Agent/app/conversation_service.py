from dataclasses import dataclass

from db.conversation import (
    add_message,
    clear_pending_clarification,
    create_conversation,
    get_conversation,
    record_event,
    record_llm_metrics,
    set_pending_clarification,
)
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlalchemy.orm import Session

from app.llm.pricing import estimate_cost_usd


@dataclass
class TurnContext:
    conversation_id: str
    messages: list[BaseMessage]
    pending_clarification: dict | None
    user_message_id: str


def load_turn(session: Session, channel: str, external_id: str, text: str, request_id: str) -> TurnContext:
    """Load everything the graph needs for one turn, and persist the incoming user message.
    Prior-turn history is no longer reconstructed here - the graph's checkpointer (keyed by
    conversation_id as thread_id, see ADR-0007) supplies it automatically."""
    conversation = get_conversation(session, channel, external_id)
    if conversation is None:
        conversation = create_conversation(session, channel, external_id)

    messages = [HumanMessage(content=text)]

    pending_clarification = conversation.pending_clarification
    user_message = add_message(session, conversation.id, role="user", content=text)
    record_event(session, "message_received", conversation_id=conversation.id, request_id=request_id)

    return TurnContext(
        conversation_id=conversation.id,
        messages=messages,
        pending_clarification=pending_clarification,
        user_message_id=user_message.id,
    )


def persist_turn_result(
    session: Session, ctx: TurnContext, request_id: str, reply_message: AIMessage
) -> None:
    """Persist the graph's result. A resumed turn (no LLM call) and a normal LLM turn are
    told apart by `resumed` in the reply's response_metadata, set by the graph itself."""
    meta = reply_message.response_metadata or {}
    add_message(session, ctx.conversation_id, role="assistant", content=reply_message.content)

    if meta.get("resumed"):
        clear_pending_clarification(session, ctx.conversation_id)
        record_event(
            session, "clarification_resumed", conversation_id=ctx.conversation_id, request_id=request_id
        )
        return

    clarification_data = meta.get("clarification")
    if clarification_data:
        set_pending_clarification(session, ctx.conversation_id, clarification_data)
    else:
        clear_pending_clarification(session, ctx.conversation_id)

    usage = reply_message.usage_metadata or {}
    provider_name = meta.get("provider", "unknown")
    model_name = meta.get("model", "unknown")
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    cache_creation_input_tokens = meta.get("cache_creation_input_tokens")
    cache_read_input_tokens = meta.get("cache_read_input_tokens")

    record_llm_metrics(
        session,
        message_id=ctx.user_message_id,
        request_id=request_id,
        provider=provider_name,
        model=model_name,
        system_prompt=meta.get("system_prompt"),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_input_tokens=cache_creation_input_tokens,
        cache_read_input_tokens=cache_read_input_tokens,
        finish_reason=meta.get("finish_reason"),
        latency_ms=meta.get("latency_ms"),
        cost_usd=estimate_cost_usd(
            provider_name,
            model_name,
            input_tokens,
            output_tokens,
            cache_creation_input_tokens,
            cache_read_input_tokens,
        ),
    )
    record_event(session, "message_sent", conversation_id=ctx.conversation_id, request_id=request_id)


def persist_turn_failure(
    session: Session, conversation_id: str, user_message_id: str, request_id: str, provider_name: str
) -> None:
    record_llm_metrics(
        session,
        message_id=user_message_id,
        request_id=request_id,
        provider=provider_name,
        model="unknown",
        error="llm_call_failed",
    )
    record_event(session, "error", conversation_id=conversation_id, request_id=request_id)
