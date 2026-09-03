"""CLI over llm_metrics: a shared before/after primitive for token-efficiency work
(caching, truncation, ...) instead of hand-writing SQL per issue.

Usage:
    uv run python DB/scripts/report_metrics.py [--start ISO] [--end ISO] [--conversations id1,id2] [--trend day|week]
    uv run python DB/scripts/report_metrics.py --compare \\
        --before-start ISO --before-end ISO --after-start ISO --after-end ISO
"""

import argparse
import datetime
import sys
from collections.abc import Sequence

from db.metrics_report import MetricsSummary, compare, cost_trend, summarize
from db.session import get_session


def _parse_date(value: str) -> datetime.datetime:
    parsed = datetime.datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=datetime.UTC)


def _parse_ids(value: str | None) -> list[str] | None:
    return value.split(",") if value else None


def _print_summary(label: str, summary: MetricsSummary) -> None:
    print(f"=== {label} ===")
    print(f"calls: {summary.call_count}")
    print(f"avg input tokens/turn: {summary.avg_input_tokens_per_turn}")
    print(f"avg output tokens/turn: {summary.avg_output_tokens_per_turn}")
    print(f"avg total tokens/conversation: {summary.avg_total_tokens_per_conversation}")
    print(f"cache hit rate: {summary.cache_hit_rate}")
    print(f"total cache-read tokens: {summary.total_cache_read_tokens}")
    print(f"total cost (usd): {summary.total_cost_usd}")


def _print_comparison(rows) -> None:
    print(f"{'metric':<38}{'before':>14}{'after':>14}{'delta':>14}{'delta %':>10}")
    for row in rows:
        delta_pct = f"{row.delta_pct:+.1f}%" if row.delta_pct is not None else "n/a"
        delta = f"{row.delta:+.4f}" if row.delta is not None else "n/a"
        print(
            f"{row.metric:<38}{_fmt(row.before):>14}{_fmt(row.after):>14}{delta:>14}{delta_pct:>10}"
        )


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Report over the llm_metrics table.")
    parser.add_argument("--start", type=_parse_date, help="ISO 8601 start (inclusive)")
    parser.add_argument("--end", type=_parse_date, help="ISO 8601 end (exclusive)")
    parser.add_argument("--conversations", help="comma-separated conversation IDs to filter to")
    parser.add_argument("--trend", choices=("day", "week"), help="also print a cost trend by bucket")

    parser.add_argument("--compare", action="store_true", help="print a before/after diff instead")
    parser.add_argument("--before-start", type=_parse_date)
    parser.add_argument("--before-end", type=_parse_date)
    parser.add_argument("--before-conversations")
    parser.add_argument("--after-start", type=_parse_date)
    parser.add_argument("--after-end", type=_parse_date)
    parser.add_argument("--after-conversations")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    with get_session() as session:
        if args.compare:
            before = summarize(
                session,
                start=args.before_start,
                end=args.before_end,
                conversation_ids=_parse_ids(args.before_conversations),
            )
            after = summarize(
                session,
                start=args.after_start,
                end=args.after_end,
                conversation_ids=_parse_ids(args.after_conversations),
            )
            _print_comparison(compare(before, after))
            return 0

        conversation_ids = _parse_ids(args.conversations)
        summary = summarize(session, start=args.start, end=args.end, conversation_ids=conversation_ids)
        _print_summary("summary", summary)

        if args.trend:
            print(f"\n=== cost trend ({args.trend}) ===")
            for period, cost in cost_trend(
                session, start=args.start, end=args.end, conversation_ids=conversation_ids, bucket=args.trend
            ):
                print(f"{period}: ${cost:.4f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
