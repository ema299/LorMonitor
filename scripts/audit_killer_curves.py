#!/usr/bin/env python3
"""Read-only audit of current killer_curves rows against the hard validator.

Usage:
    venv/bin/python3 scripts/audit_killer_curves.py [--format core|infinity|all]
                                                    [--out /tmp/kc_audit.json]
                                                    [--verbose]

Writes a structured JSON report (default ``/tmp/kc_audit.json``) and a stdout
summary. Does not modify the database — pure dry-run.

Aligned with ``pipelines/kc/validator.py`` and the P0 backlog in
``docs/KILLER_CURVES_BLINDATURA_V3.md``.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.models import SessionLocal  # noqa: E402
from backend.models.analysis import KillerCurve  # noqa: E402
from pipelines.kc.validator import quality_summary, validate  # noqa: E402


def _summarize(results: list[dict]) -> dict:
    by_status: Counter[str] = Counter()
    error_codes: Counter[str] = Counter()
    warning_codes: Counter[str] = Counter()
    drop_totals: dict[str, int] = defaultdict(int)
    completeness_buckets = {
        "response_v2_full": 0,
        "v3_full": 0,
        "self_check_full": 0,
    }
    for entry in results:
        r = entry["validation"]
        by_status[r["quality_status"]] += 1
        for e in r.get("errors") or []:
            error_codes[e.get("code", "unknown")] += 1
        for w in r.get("warnings") or []:
            warning_codes[w.get("code", "unknown")] += 1
        for k, v in (r.get("drop_metrics") or {}).items():
            drop_totals[k] += v
        comp = r.get("completeness") or {}
        n = comp.get("n_curves", 0) or 0
        if n and comp.get("response_v2_complete", 0) == n:
            completeness_buckets["response_v2_full"] += 1
        if n and comp.get("v3_payload_complete", 0) == n:
            completeness_buckets["v3_full"] += 1
        if n and comp.get("self_check_complete", 0) == n:
            completeness_buckets["self_check_full"] += 1
    return {
        "by_status": dict(by_status),
        "error_codes_top20": dict(error_codes.most_common(20)),
        "warning_codes_top20": dict(warning_codes.most_common(20)),
        "drop_totals": dict(drop_totals),
        "completeness_full_rows": completeness_buckets,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=["core", "infinity", "all"], default="all")
    parser.add_argument("--out", default="/tmp/kc_audit.json")
    parser.add_argument("--verbose", action="store_true",
                        help="print per-row summary line during run")
    parser.add_argument("--limit", type=int, default=0,
                        help="limit rows audited (0 = all)")
    args = parser.parse_args()

    db = SessionLocal()
    q = db.query(KillerCurve).filter(KillerCurve.is_current == True)  # noqa: E712
    if args.format != "all":
        q = q.filter(KillerCurve.game_format == args.format)
    q = q.order_by(KillerCurve.generated_at.desc(),
                   KillerCurve.our_deck, KillerCurve.opp_deck)
    if args.limit:
        q = q.limit(args.limit)
    rows = q.all()
    print(f"audit: {len(rows)} rows (format={args.format})")

    results: list[dict] = []
    for i, row in enumerate(rows, 1):
        data = {
            "metadata": {
                "our_deck": row.our_deck,
                "opp_deck": row.opp_deck,
                "game_format": row.game_format,
            },
            "curves": row.curves or [],
        }
        try:
            r = validate(data, row.our_deck, row.opp_deck, row.game_format, db)
        except Exception as exc:
            r = {
                "validator_version": "ERR",
                "quality_status": "blocked",
                "errors": [{"code": "validator_exception", "severity": "P0",
                             "curve_id": None, "detail": str(exc)}],
                "warnings": [], "info": [],
                "drop_metrics": {}, "completeness": {},
            }
        entry = {
            "row_id": row.id,
            "format": row.game_format,
            "our_deck": row.our_deck,
            "opp_deck": row.opp_deck,
            "generated_at": str(row.generated_at) if row.generated_at else None,
            "validation": r,
        }
        results.append(entry)
        if args.verbose:
            print(f"  [{i:3d}/{len(rows)}] {row.game_format:8s} {row.our_deck:>5s} vs {row.opp_deck:<5s} "
                  f"({row.generated_at}) -> {quality_summary(r)}")

    summary = _summarize(results)
    out = {
        "audited_rows": len(results),
        "format_filter": args.format,
        "summary": summary,
        "rows": results,
    }
    out_path = Path(args.out)
    out_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"audit report written to {out_path} ({out_path.stat().st_size // 1024} KB)")
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  rows audited: {len(results)}")
    print(f"  by status   : {summary['by_status']}")
    print(f"  full-row v2 : {summary['completeness_full_rows']['response_v2_full']}")
    print(f"  full-row v3 : {summary['completeness_full_rows']['v3_full']}")
    print(f"  full-row sc : {summary['completeness_full_rows']['self_check_full']}")
    print(f"  top P0 errors:")
    for code, n in summary["error_codes_top20"].items():
        print(f"    {n:5d}  {code}")
    print(f"  top P1 warnings:")
    for code, n in summary["warning_codes_top20"].items():
        print(f"    {n:5d}  {code}")
    print(f"  drop totals (response/sequence card filtering):")
    for k, v in sorted(summary["drop_totals"].items()):
        if v:
            print(f"    {v:5d}  {k}")
    db.close()


if __name__ == "__main__":
    main()
