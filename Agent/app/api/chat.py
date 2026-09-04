import logging
import uuid

from db.session import get_session
from fastapi import APIRouter, Header
from langchain_core.messages import AIMessage
from langgraph.types import Command
from pydantic import BaseModel

from app.conversation_service import (
    load_turn,
    persist_turn_clarification,
    persist_turn_failure,
    persist_turn_result,
)
from app.graph.build import build_graph
from app.graph.checkpointer import build_checkpointer
from app.llm.factory import get_provider
from app.tools import ALL_TOOLS
from app.tools.clarification import ClarificationOption

logger = logging.getLogger(__name__)
router = APIRouter()

_provider = get_provider()
_checkpointer = build_checkpointer()
_graph = build_graph(_provider, tools=ALL_TOOLS, checkpointer=_checkpointer)

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

    config = {"configurable": {"thread_id": ctx.conversation_id}}
    # Whether this turn resumes a pending clarification is the checkpointer's call, via
    # interrupt() - not a column we track ourselves (see ADR-0008).
    is_resuming = bool(_graph.get_state(config).interrupts)

    logger.info(
        "graph_call_start",
        extra={
            "event": "graph_call_start",
            "request_id": request_id,
            "conversation_id": ctx.conversation_id,
        },
    )
    try:
        if is_resuming:
            result = _graph.invoke(Command(resume=request.text), config=config)
        else:
            result = _graph.invoke({"messages": ctx.messages}, config=config)
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

    pending_interrupts = result.get("__interrupt__")
    if pending_interrupts:
        # Paused on a fresh clarification: no text reply was produced, the question/options
        # live in the interrupt's value. The carrier message is the tool-call AIMessage that
        # requested request_clarification - it still has real LLM usage/cost metadata.
        question_data = pending_interrupts[0].value
        carrier_message: AIMessage = result["messages"][-1]
        reply_text = question_data["question"]
        options = [ClarificationOption(**o) for o in question_data["options"]]
    else:
        carrier_message = result["messages"][-1]
        reply_text = carrier_message.content
        options = None

    meta = carrier_message.response_metadata or {}
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
        if pending_interrupts:
            persist_turn_clarification(session, ctx, request_id, carrier_message, reply_text)
        else:
            persist_turn_result(session, ctx, request_id, carrier_message)

    logger.info(
        "message_sent",
        extra={"event": "message_sent", "request_id": request_id, "channel": request.channel},
    )
    return ChatResponse(reply=reply_text, options=options)
