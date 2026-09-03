import datetime
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import LLMMetrics, Message

_TREND_BUCKETS = ("day", "week")


@dataclass
class MetricsSummary:
    call_count: int
    avg_input_tokens_per_turn: float | None
    avg_output_tokens_per_turn: float | None
    avg_total_tokens_per_conversation: float | None
    cache_hit_rate: float | None
    total_cache_read_tokens: int
    total_cost_usd: float


def _apply_filters(stmt, start, end, conversation_ids):
    if conversation_ids is not None:
        stmt = stmt.where(Message.conversation_id.in_(conversation_ids))
    if start is not None:
        stmt = stmt.where(LLMMetrics.created_at >= start)
    if end is not None:
        stmt = stmt.where(LLMMetrics.created_at < end)
    return stmt


def summarize(
    session: Session,
    start: datetime.datetime | None = None,
    end: datetime.datetime | None = None,
    conversation_ids: list[str] | None = None,
) -> MetricsSummary:
    """Aggregate llm_metrics over an optional date range and/or conversation-ID filter.
    Rows with a recorded error are excluded - they carry no token/cost data to average."""
    per_turn_stmt = (
        select(
            func.count(LLMMetrics.id),
            func.avg(LLMMetrics.input_tokens),
            func.avg(LLMMetrics.output_tokens),
            func.coalesce(func.sum(LLMMetrics.cost_usd), 0.0),
            func.coalesce(func.sum(LLMMetrics.cache_read_input_tokens), 0),
            func.count(LLMMetrics.id).filter(LLMMetrics.cache_read_input_tokens > 0),
        )
        .select_from(LLMMetrics)
        .join(Message, LLMMetrics.message_id == Message.id)
        .where(LLMMetrics.error.is_(None))
    )
    per_turn_stmt = _apply_filters(per_turn_stmt, start, end, conversation_ids)
    call_count, avg_input, avg_output, total_cost, total_cache_read, cache_hits = session.execute(
        per_turn_stmt
    ).one()

    per_conversation_stmt = (
        select(
            func.sum(LLMMetrics.input_tokens + LLMMetrics.output_tokens).label("conversation_total")
        )
        .select_from(LLMMetrics)
        .join(Message, LLMMetrics.message_id == Message.id)
        .where(LLMMetrics.error.is_(None))
        .group_by(Message.conversation_id)
    )
    per_conversation_stmt = _apply_filters(per_conversation_stmt, start, end, conversation_ids)
    avg_per_conversation = session.execute(
        select(func.avg(per_conversation_stmt.subquery().c.conversation_total))
    ).scalar_one()

    return MetricsSummary(
        call_count=call_count,
        avg_input_tokens_per_turn=avg_input,
        avg_output_tokens_per_turn=avg_output,
        avg_total_tokens_per_conversation=avg_per_conversation,
        cache_hit_rate=(cache_hits / call_count) if call_count else None,
        total_cache_read_tokens=total_cache_read,
        total_cost_usd=total_cost,
    )


def cost_trend(
    session: Session,
    start: datetime.datetime | None = None,
    end: datetime.datetime | None = None,
    conversation_ids: list[str] | None = None,
    bucket: str = "day",
) -> list[tuple[datetime.datetime, float]]:
    """Total cost_usd grouped by day or week, oldest first."""
    if bucket not in _TREND_BUCKETS:
        raise ValueError(f"bucket must be one of {_TREND_BUCKETS}, got {bucket!r}")

    period = func.date_trunc(bucket, LLMMetrics.created_at).label("period")
    stmt = (
        select(period, func.coalesce(func.sum(LLMMetrics.cost_usd), 0.0))
        .select_from(LLMMetrics)
        .join(Message, LLMMetrics.message_id == Message.id)
        .where(LLMMetrics.error.is_(None))
        .group_by(period)
        .order_by(period)
    )
    stmt = _apply_filters(stmt, start, end, conversation_ids)
    return list(session.execute(stmt).all())


@dataclass
class ComparisonRow:
    metric: str
    before: float | None
    after: float | None
    delta: float | None
    delta_pct: float | None


def compare(before: MetricsSummary, after: MetricsSummary) -> list[ComparisonRow]:
    def _row(metric: str, b: float | None, a: float | None) -> ComparisonRow:
        delta = None if b is None or a is None else a - b
        delta_pct = None if not delta or not b else (delta / b) * 100
        return ComparisonRow(metric=metric, before=b, after=a, delta=delta, delta_pct=delta_pct)

    return [
        _row("avg_input_tokens_per_turn", before.avg_input_tokens_per_turn, after.avg_input_tokens_per_turn),
        _row(
            "avg_output_tokens_per_turn", before.avg_output_tokens_per_turn, after.avg_output_tokens_per_turn
        ),
        _row(
            "avg_total_tokens_per_conversation",
            before.avg_total_tokens_per_conversation,
            after.avg_total_tokens_per_conversation,
        ),
        _row("cache_hit_rate", before.cache_hit_rate, after.cache_hit_rate),
        _row("total_cost_usd", before.total_cost_usd, after.total_cost_usd),
    ]
