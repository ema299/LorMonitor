#!/usr/bin/env python3
"""KC cost/usage report from killer_curves.meta JSONB.

Aggregates LLM cost + tokens across time windows and model versions.
Answers "how much am I spending on killer curves" with real data.

Usage:
    venv/bin/python scripts/kc_cost_report.py                # default: last 30 days
    venv/bin/python scripts/kc_cost_report.py --days 7       # last 7 days
    venv/bin/python scripts/kc_cost_report.py --run-id X     # drill into one batch
    venv/bin/python scripts/kc_cost_report.py --json         # machine-readable

Zero side effects. Read-only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from sqlalchemy import text  # noqa: E402


def _fetch_window(db, days: int) -> dict:
    row = db.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE meta ? 'cost_usd') AS n_with_meta,
            COUNT(*) AS n_total,
            COALESCE(SUM((meta->>'cost_usd')::float), 0) AS tot_cost,
            COALESCE(AVG((meta->>'cost_usd')::float), 0) AS avg_cost,
            COALESCE(MAX((meta->>'cost_usd')::float), 0) AS max_cost,
            COALESCE(SUM((meta->>'input_tokens')::int), 0) AS tot_in_tok,
            COALESCE(SUM((meta->>'output_tokens')::int), 0) AS tot_out_tok,
            COALESCE(AVG((meta->>'duration_s')::float), 0) AS avg_duration
        FROM killer_curves
        WHERE generated_at > CURRENT_DATE - :days
    """), {"days": days}).fetchone()
    return {
        "n_records_with_meta": row.n_with_meta,
        "n_records_total": row.n_total,
        "total_cost_usd": round(float(row.tot_cost), 4),
        "avg_cost_per_matchup_usd": round(float(row.avg_cost), 4),
        "max_cost_per_matchup_usd": round(float(row.max_cost), 4),
        "total_input_tokens": int(row.tot_in_tok),
        "total_output_tokens": int(row.tot_out_tok),
        "avg_duration_s": round(float(row.avg_duration), 2),
    }


def _fetch_by_model(db, days: int) -> list[dict]:
    rows = db.execute(text("""
        SELECT
            meta->>'model' AS model,
            COUNT(*) AS n,
            SUM((meta->>'cost_usd')::float) AS tot_cost,
            AVG((meta->>'cost_usd')::float) AS avg_cost
        FROM killer_curves
        WHERE generated_at > CURRENT_DATE - :days
          AND meta ? 'cost_usd'
        GROUP BY meta->>'model'
        ORDER BY tot_cost DESC NULLS LAST
    """), {"days": days}).fetchall()
    return [
        {"model": r.model, "n": r.n,
         "total_cost_usd": round(float(r.tot_cost), 4),
         "avg_cost_usd": round(float(r.avg_cost), 4)}
        for r in rows
    ]


def _fetch_by_run(db, days: int, limit: int = 10) -> list[dict]:
    rows = db.execute(text("""
        SELECT
            meta->>'run_id' AS run_id,
            MIN(generated_at) AS date,
            COUNT(*) AS n,
            SUM((meta->>'cost_usd')::float) AS tot_cost,
            MAX(meta->>'model') AS model
        FROM killer_curves
        WHERE generated_at > CURRENT_DATE - :days
          AND meta ? 'run_id'
        GROUP BY meta->>'run_id'
        ORDER BY MIN(generated_at) DESC
        LIMIT :limit
    """), {"days": days, "limit": limit}).fetchall()
    return [
        {"run_id": r.run_id, "date": r.date.isoformat() if r.date else None,
         "n_matchups": r.n, "total_cost_usd": round(float(r.tot_cost), 4),
         "model": r.model}
        for r in rows
    ]


def _fetch_top_expensive(db, days: int, limit: int = 5) -> list[dict]:
    rows = db.execute(text("""
        SELECT our_deck, opp_deck, generated_at,
               (meta->>'cost_usd')::float AS cost_usd,
               (meta->>'input_tokens')::int AS in_tok,
               (meta->>'output_tokens')::int AS out_tok
        FROM killer_curves
        WHERE generated_at > CURRENT_DATE - :days
          AND meta ? 'cost_usd'
        ORDER BY (meta->>'cost_usd')::float DESC NULLS LAST
        LIMIT :limit
    """), {"days": days, "limit": limit}).fetchall()
    return [
        {"matchup": f"{r.our_deck} vs {r.opp_deck}",
         "date": r.generated_at.isoformat(),
         "cost_usd": round(float(r.cost_usd or 0), 4),
         "input_tokens": r.in_tok or 0,
         "output_tokens": r.out_tok or 0}
        for r in rows
    ]


def _drill_run(db, run_id: str) -> dict:
    rows = db.execute(text("""
        SELECT our_deck, opp_deck, game_format, generated_at, meta
        FROM killer_curves
        WHERE meta->>'run_id' = :rid
        ORDER BY generated_at, our_deck, opp_deck
    """), {"rid": run_id}).fetchall()
    matchups = []
    total = 0.0
    for r in rows:
        m = r.meta or {}
        c = float(m.get("cost_usd") or 0)
        total += c
        matchups.append({
            "matchup": f"{r.our_deck} vs {r.opp_deck}",
            "format": r.game_format,
            "date": r.generated_at.isoformat(),
            "cost_usd": round(c, 4),
            "input_tokens": m.get("input_tokens"),
            "output_tokens": m.get("output_tokens"),
            "duration_s": m.get("duration_s"),
            "n_curves": m.get("n_curves"),
        })
    return {"run_id": run_id, "n_matchups": len(matchups),
            "total_cost_usd": round(total, 4), "matchups": matchups}


def _render_text(report: dict) -> str:
    out = []
    w = report["window"]
    out.append(f"=== KC cost report (last {w['days']} days) ===")
    out.append(f"Records in window: {w['n_records_total']} "
               f"(with meta: {w['n_records_with_meta']})")
    out.append(f"Coverage: {w['n_records_with_meta']}/{w['n_records_total']} "
               f"= {(w['n_records_with_meta'] / max(w['n_records_total'], 1) * 100):.1f}%")
    out.append("")
    out.append(f"Total cost: ${w['total_cost_usd']:.4f}")
    out.append(f"Avg per matchup: ${w['avg_cost_per_matchup_usd']:.4f}")
    out.append(f"Max per matchup: ${w['max_cost_per_matchup_usd']:.4f}")
    out.append(f"Total tokens: in={w['total_input_tokens']:,} "
               f"out={w['total_output_tokens']:,}")
    out.append(f"Avg duration: {w['avg_duration_s']:.1f}s")
    out.append("")

    if report.get("by_model"):
        out.append("--- by model ---")
        for m in report["by_model"]:
            out.append(f"  {m['model']}: n={m['n']} "
                       f"tot=${m['total_cost_usd']:.4f} "
                       f"avg=${m['avg_cost_usd']:.4f}")
        out.append("")

    if report.get("recent_runs"):
        out.append(f"--- recent runs (top {len(report['recent_runs'])}) ---")
        for r in report["recent_runs"]:
            out.append(f"  {r['date']} {r['run_id'][:24]} "
                       f"n={r['n_matchups']} ${r['total_cost_usd']:.4f} "
                       f"{r['model']}")
        out.append("")

    if report.get("top_expensive"):
        out.append(f"--- top {len(report['top_expensive'])} expensive matchups ---")
        for m in report["top_expensive"]:
            out.append(f"  {m['date']} {m['matchup']}: "
                       f"${m['cost_usd']:.4f} "
                       f"({m['input_tokens']}→{m['output_tokens']} tok)")
    return "\n".join(out)


def main() -> int:
    p = argparse.ArgumentParser(description="KC cost/usage report")
    p.add_argument("--days", type=int, default=30, help="Window in days (default 30)")
    p.add_argument("--run-id", help="Drill into a single run_id")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    args = p.parse_args()

    from backend.models import SessionLocal
    db = SessionLocal()
    try:
        if args.run_id:
            report = _drill_run(db, args.run_id)
        else:
            report = {
                "window": {"days": args.days, **_fetch_window(db, args.days)},
                "by_model": _fetch_by_model(db, args.days),
                "recent_runs": _fetch_by_run(db, args.days),
                "top_expensive": _fetch_top_expensive(db, args.days),
            }
    finally:
        db.close()

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        if args.run_id:
            print(json.dumps(report, indent=2, default=str))
        else:
            print(_render_text(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
