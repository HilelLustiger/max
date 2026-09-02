import logging
import uuid

from db.session import get_session
from fastapi import APIRouter, Header
from langchain_core.messages import AIMessage
from pydantic import BaseModel

from app.conversation_service import load_turn, persist_turn_failure, persist_turn_result
from app.graph.build import build_graph
from app.llm.factory import get_provider
from app.tools import ALL_TOOLS
from app.tools.clarification import ClarificationOption

logger = logging.getLogger(__name__)
router = APIRouter()

_provider = get_provider()
_graph = build_graph(_provider, tools=ALL_TOOLS)

FALLBACK_REPLY = "Sorry, I'm having trouble responding right now. Please try again in a moment."


class ChatRequest(BaseModel):
    channel: str
    external_id: str
    text: str


class ChatResponse(BaseModel):
    reply: str
    options: list[ClarificationOption] | None = None


@router.post("/chat", response_model=ChatResponse, response_model_exclude_none=True)
def chat(request: ChatRequest, x_request_id: str | None = Header(default=None)) -> ChatResponse:
    request_id = x_request_id or uuid.uuid4().hex
    logger.info(
        "message_received",
        extra={"event": "message_received", "request_id": request_id, "channel": request.channel},
    )

    with get_session() as session:
        ctx = load_turn(session, request.channel, request.external_id, request.text, request_id)

    logger.info(
        "graph_call_start",
        extra={
            "event": "graph_call_start",
            "request_id": request_id,
            "conversation_id": ctx.conversation_id,
        },
    )
    try:
        result = _graph.invoke(
            {"messages": ctx.messages, "pending_clarification": ctx.pending_clarification}
        )
        reply_message: AIMessage = result["messages"][-1]
    except Exception:
        logger.exception(
            "graph_call_failed",
            extra={
                "event": "graph_call_failed",
                "request_id": request_id,
                "conversation_id": ctx.conversation_id,
            },
        )
        with get_session() as session:
            persist_turn_failure(
                session, ctx.conversation_id, ctx.user_message_id, request_id, _provider.__class__.__name__
            )
        return ChatResponse(reply=FALLBACK_REPLY)

    meta = reply_message.response_metadata or {}
    logger.info(
        "graph_call_end",
        extra={
            "event": "graph_call_end",
            "request_id": request_id,
            "conversation_id": ctx.conversation_id,
            "provider": meta.get("provider"),
            "model": meta.get("model"),
            "latency_ms": meta.get("latency_ms"),
        },
    )

    with get_session() as session:
        persist_turn_result(session, ctx, request_id, reply_message)

    logger.info(
        "message_sent",
        extra={"event": "message_sent", "request_id": request_id, "channel": request.channel},
    )
    clarification_data = meta.get("clarification")
    options = (
        [ClarificationOption(**o) for o in clarification_data["options"]] if clarification_data else None
    )
    return ChatResponse(reply=reply_message.content, options=options)
