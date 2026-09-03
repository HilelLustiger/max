import datetime

import pytest
from db.conversation import add_message, create_conversation, record_llm_metrics
from db.metrics_report import MetricsSummary, compare, cost_trend, summarize
from db.session import get_session
from sqlalchemy import text

pytestmark = pytest.mark.integration


def _seed_call(
    session, conversation_id, *, input_tokens, output_tokens, cost_usd, cache_read=None, error=None
):
    message = add_message(session, conversation_id, role="user", content="hi")
    return record_llm_metrics(
        session,
        message_id=message.id,
        provider="fake",
        model="fake-model",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_input_tokens=cache_read,
        cost_usd=cost_usd,
        error=error,
    )


def test_summarize_averages_per_turn_and_per_conversation(clean_db):
    with get_session() as session:
        conv_a = create_conversation(session, "test", "user-a")
        conv_b = create_conversation(session, "test", "user-b")
        _seed_call(session, conv_a.id, input_tokens=100, output_tokens=10, cost_usd=0.01)
        _seed_call(session, conv_a.id, input_tokens=200, output_tokens=20, cost_usd=0.02)
        _seed_call(session, conv_b.id, input_tokens=300, output_tokens=30, cost_usd=0.03)

    with get_session() as session:
        summary = summarize(session)

    assert summary.call_count == 3
    assert summary.avg_input_tokens_per_turn == pytest.approx(200)
    assert summary.avg_output_tokens_per_turn == pytest.approx(20)
    # conv_a totals 330, conv_b totals 330 -> avg across the 2 conversations is 330
    assert summary.avg_total_tokens_per_conversation == pytest.approx(330)
    assert summary.total_cost_usd == pytest.approx(0.06)


def test_summarize_computes_cache_hit_rate_and_total(clean_db):
    with get_session() as session:
        conv = create_conversation(session, "test", "user-1")
        _seed_call(session, conv.id, input_tokens=100, output_tokens=10, cost_usd=0.0, cache_read=80)
        _seed_call(session, conv.id, input_tokens=100, output_tokens=10, cost_usd=0.0, cache_read=0)
        _seed_call(session, conv.id, input_tokens=100, output_tokens=10, cost_usd=0.0, cache_read=None)

    with get_session() as session:
        summary = summarize(session)

    assert summary.cache_hit_rate == pytest.approx(1 / 3)
    assert summary.total_cache_read_tokens == 80


def test_summarize_excludes_error_rows(clean_db):
    with get_session() as session:
        conv = create_conversation(session, "test", "user-1")
        _seed_call(session, conv.id, input_tokens=100, output_tokens=10, cost_usd=0.01)
        _seed_call(session, conv.id, input_tokens=None, output_tokens=None, cost_usd=None, error="llm_call_failed")

    with get_session() as session:
        summary = summarize(session)

    assert summary.call_count == 1
    assert summary.avg_input_tokens_per_turn == pytest.approx(100)


def test_summarize_filters_by_conversation_ids(clean_db):
    with get_session() as session:
        conv_a = create_conversation(session, "test", "user-a")
        conv_b = create_conversation(session, "test", "user-b")
        _seed_call(session, conv_a.id, input_tokens=100, output_tokens=10, cost_usd=0.01)
        _seed_call(session, conv_b.id, input_tokens=999, output_tokens=999, cost_usd=9.0)

    with get_session() as session:
        summary = summarize(session, conversation_ids=[conv_a.id])

    assert summary.call_count == 1
    assert summary.avg_input_tokens_per_turn == pytest.approx(100)


def test_summarize_filters_by_date_range(clean_db):
    with get_session() as session:
        conv = create_conversation(session, "test", "user-1")
        old_call = _seed_call(session, conv.id, input_tokens=100, output_tokens=10, cost_usd=0.01)
        new_call = _seed_call(session, conv.id, input_tokens=200, output_tokens=20, cost_usd=0.02)
        session.execute(
            text("UPDATE llm_metrics SET created_at = :ts WHERE id = :id"),
            {"ts": datetime.datetime(2020, 1, 1, tzinfo=datetime.UTC), "id": old_call.id},
        )
        session.execute(
            text("UPDATE llm_metrics SET created_at = :ts WHERE id = :id"),
            {"ts": datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC), "id": new_call.id},
        )

    with get_session() as session:
        summary = summarize(session, start=datetime.datetime(2025, 1, 1, tzinfo=datetime.UTC))

    assert summary.call_count == 1
    assert summary.avg_input_tokens_per_turn == pytest.approx(200)


def test_cost_trend_groups_by_day(clean_db):
    with get_session() as session:
        conv = create_conversation(session, "test", "user-1")
        day1_call = _seed_call(session, conv.id, input_tokens=1, output_tokens=1, cost_usd=0.01)
        day2_call_a = _seed_call(session, conv.id, input_tokens=1, output_tokens=1, cost_usd=0.02)
        day2_call_b = _seed_call(session, conv.id, input_tokens=1, output_tokens=1, cost_usd=0.03)
        for call, ts in [
            (day1_call, datetime.datetime(2026, 1, 1, 10, tzinfo=datetime.UTC)),
            (day2_call_a, datetime.datetime(2026, 1, 2, 9, tzinfo=datetime.UTC)),
            (day2_call_b, datetime.datetime(2026, 1, 2, 15, tzinfo=datetime.UTC)),
        ]:
            session.execute(
                text("UPDATE llm_metrics SET created_at = :ts WHERE id = :id"), {"ts": ts, "id": call.id}
            )

    with get_session() as session:
        trend = cost_trend(session, bucket="day")

    costs_by_day = {period.date(): cost for period, cost in trend}
    assert costs_by_day[datetime.date(2026, 1, 1)] == pytest.approx(0.01)
    assert costs_by_day[datetime.date(2026, 1, 2)] == pytest.approx(0.05)


def test_cost_trend_rejects_unknown_bucket(clean_db):
    with get_session() as session, pytest.raises(ValueError):
        cost_trend(session, bucket="month")


def test_compare_computes_delta_and_delta_pct():
    before = MetricsSummary(
        call_count=10,
        avg_input_tokens_per_turn=1000,
        avg_output_tokens_per_turn=100,
        avg_total_tokens_per_conversation=5000,
        cache_hit_rate=0.0,
        total_cache_read_tokens=0,
        total_cost_usd=1.00,
    )
    after = MetricsSummary(
        call_count=10,
        avg_input_tokens_per_turn=800,
        avg_output_tokens_per_turn=100,
        avg_total_tokens_per_conversation=4000,
        cache_hit_rate=0.5,
        total_cache_read_tokens=4000,
        total_cost_usd=0.75,
    )

    rows = {row.metric: row for row in compare(before, after)}

    assert rows["avg_input_tokens_per_turn"].delta == pytest.approx(-200)
    assert rows["avg_input_tokens_per_turn"].delta_pct == pytest.approx(-20.0)
    assert rows["avg_output_tokens_per_turn"].delta == pytest.approx(0)
    assert rows["avg_output_tokens_per_turn"].delta_pct is None  # zero delta -> no meaningful percent
    assert rows["total_cost_usd"].delta == pytest.approx(-0.25)
