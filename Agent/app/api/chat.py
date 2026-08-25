import logging
import uuid

from db.conversation import (
    add_message,
    get_or_create_conversation,
    recent_messages,
    record_event,
    record_llm_metrics,
)
from db.session import get_session
from fastapi import APIRouter
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from app.graph.build import build_graph
from app.llm.factory import get_provider
from app.llm.pricing import estimate_cost_usd

logger = logging.getLogger(__name__)
router = APIRouter()

_provider = get_provider()
_graph = build_graph(_provider)

FALLBACK_REPLY = "Sorry, I'm having trouble responding right now. Please try again in a moment."


class ChatRequest(BaseModel):
    channel: str
    external_id: str
    text: str


class ChatResponse(BaseModel):
    reply: str


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    request_id = uuid.uuid4().hex
    logger.info("request_id=%s channel=%s message_received", request_id, request.channel)

    with get_session() as session:
        conversation = get_or_create_conversation(session, request.channel, request.external_id)
        history = [
            AIMessage(content=m.content) if m.role == "assistant" else HumanMessage(content=m.content)
            for m in recent_messages(session, conversation.id)
        ]
        user_message = add_message(session, conversation.id, role="user", content=request.text)
        record_event(
            session, "message_received", conversation_id=conversation.id, request_id=request_id
        )

    try:
        result = _graph.invoke({"messages": [*history, HumanMessage(content=request.text)]})
        reply_message = result["messages"][-1]
    except Exception:
        logger.exception(
            "request_id=%s conversation_id=%s llm_call_failed", request_id, conversation.id
        )
        with get_session() as session:
            record_llm_metrics(
                session,
                message_id=user_message.id,
                request_id=request_id,
                provider=_provider.__class__.__name__,
                model="unknown",
                error="llm_call_failed",
            )
            record_event(
                session, "error", conversation_id=conversation.id, request_id=request_id
            )
        return ChatResponse(reply=FALLBACK_REPLY)

    usage = reply_message.usage_metadata or {}
    meta = reply_message.response_metadata or {}
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    cache_creation_input_tokens = meta.get("cache_creation_input_tokens")
    cache_read_input_tokens = meta.get("cache_read_input_tokens")
    provider_name = meta.get("provider", "unknown")
    model_name = meta.get("model", "unknown")

    with get_session() as session:
        add_message(session, conversation.id, role="assistant", content=reply_message.content)
        record_llm_metrics(
            session,
            message_id=user_message.id,
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
        record_event(
            session, "message_sent", conversation_id=conversation.id, request_id=request_id
        )

    logger.info("request_id=%s channel=%s message_sent", request_id, request.channel)
    return ChatResponse(reply=reply_message.content)
