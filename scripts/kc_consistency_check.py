#!/usr/bin/env python3
"""Consistency check: killer_curves -> matchup_reports -> dashboard blob.

Detects drift between the three layers that power the V3 "How to Respond"
surface. Read-only by default. Failure modes covered:

- Triple `(format, our, opp)` in ``killer_curves is_current`` but missing
  in ``matchup_reports report_type='killer_curves' is_current``.
- Triple in ``matchup_reports`` orphaned (no live source in ``killer_curves``).
- Curve count mismatch between source and report.
- Format leak (Core triple appearing in Infinity report or vice versa).
- Quality status drift: source has ``quality_status='blocked'`` but report still
  publishes the row.

Exit code 1 if any P0 drift is detected. Aligned with
``docs/KILLER_CURVES_BLINDATURA_V3.md`` §5 "Trasporto verso matchup_reports".

Usage:
    venv/bin/python3 scripts/kc_consistency_check.py [--out /tmp/kc_consistency.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.models import SessionLocal  # noqa: E402
from sqlalchemy import text  # noqa: E402


def _load_kc_index(db) -> dict[tuple[str, str, str], dict]:
    """Return {(format, our, opp): {curves_count, quality_status, generated_at}}."""
    rows = db.execute(text("""
        SELECT game_format, our_deck, opp_deck,
               jsonb_array_length(curves) AS n_curves,
               (meta->>'quality_status') AS quality_status,
               (meta->>'validator_version') AS validator_version,
               generated_at
        FROM killer_curves
        WHERE is_current = true
    """)).fetchall()
    return {
        (r.game_format, r.our_deck, r.opp_deck): {
            "n_curves": r.n_curves or 0,
            "quality_status": r.quality_status,
            "validator_version": r.validator_version,
            "generated_at": str(r.generated_at) if r.generated_at else None,
        }
        for r in rows
    }


def _load_mr_index(db) -> dict[tuple[str, str, str], dict]:
    """Return {(format, our, opp): {curves_count, generated_at}} for
    report_type='killer_curves' is_current rows."""
    rows = db.execute(text("""
        SELECT game_format, our_deck, opp_deck,
               jsonb_array_length(data) AS n_curves,
               generated_at
        FROM matchup_reports
        WHERE report_type = 'killer_curves' AND is_current = true
    """)).fetchall()
    return {
        (r.game_format, r.our_deck, r.opp_deck): {
            "n_curves": r.n_curves or 0,
            "generated_at": str(r.generated_at) if r.generated_at else None,
        }
        for r in rows
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="/tmp/kc_consistency.json")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress per-row drift detail in stdout")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        kc_idx = _load_kc_index(db)
        mr_idx = _load_mr_index(db)
    finally:
        db.close()

    # Format buckets
    kc_by_fmt: dict[str, int] = defaultdict(int)
    mr_by_fmt: dict[str, int] = defaultdict(int)
    for k in kc_idx:
        kc_by_fmt[k[0]] += 1
    for k in mr_idx:
        mr_by_fmt[k[0]] += 1

    # Drift detection
    missing_in_mr: list[dict] = []     # P0: in kc with curves > 0, not in mr
    ghost_in_kc: list[dict] = []        # P1: in kc with 0 curves (legacy/empty rows)
    orphan_in_mr: list[dict] = []       # P0: in mr, not in kc
    curve_count_mismatch: list[dict] = []
    blocked_but_published: list[dict] = []

    kc_keys = set(kc_idx)
    mr_keys = set(mr_idx)

    for k in sorted(kc_keys - mr_keys):
        fmt, our, opp = k
        kc_curves = kc_idx[k]["n_curves"]
        entry = {
            "format": fmt, "our": our, "opp": opp,
            "kc_quality": kc_idx[k]["quality_status"],
            "kc_curves": kc_curves,
        }
        if kc_curves > 0:
            missing_in_mr.append(entry)
        else:
            ghost_in_kc.append(entry)

    for k in sorted(mr_keys - kc_keys):
        fmt, our, opp = k
        orphan_in_mr.append({"format": fmt, "our": our, "opp": opp,
                             "mr_curves": mr_idx[k]["n_curves"]})

    for k in sorted(kc_keys & mr_keys):
        fmt, our, opp = k
        kc_n = kc_idx[k]["n_curves"]
        mr_n = mr_idx[k]["n_curves"]
        if kc_n != mr_n:
            curve_count_mismatch.append({
                "format": fmt, "our": our, "opp": opp,
                "kc_curves": kc_n, "mr_curves": mr_n,
            })
        if kc_idx[k]["quality_status"] == "blocked":
            blocked_but_published.append({
                "format": fmt, "our": our, "opp": opp,
                "kc_quality": "blocked",
            })

    summary = {
        "kc_by_format": dict(kc_by_fmt),
        "mr_by_format": dict(mr_by_fmt),
        "missing_in_mr_count": len(missing_in_mr),
        "ghost_in_kc_count": len(ghost_in_kc),
        "orphan_in_mr_count": len(orphan_in_mr),
        "curve_count_mismatch_count": len(curve_count_mismatch),
        "blocked_but_published_count": len(blocked_but_published),
    }

    out = {
        "summary": summary,
        "missing_in_mr": missing_in_mr,
        "ghost_in_kc": ghost_in_kc,
        "orphan_in_mr": orphan_in_mr,
        "curve_count_mismatch": curve_count_mismatch,
        "blocked_but_published": blocked_but_published,
    }

    out_path = Path(args.out)
    out_path.write_text(json.dumps(out, indent=2, default=str))

    print("=" * 60)
    print("KC CONSISTENCY CHECK")
    print("=" * 60)
    print(f"  killer_curves is_current  : {dict(kc_by_fmt)}")
    print(f"  matchup_reports is_current: {dict(mr_by_fmt)}")
    print(f"  missing_in_mr (drift P0)  : {len(missing_in_mr)}  (kc has curves, mr empty)")
    print(f"  ghost_in_kc (P2 info)     : {len(ghost_in_kc)}  (kc rows with 0 curves)")
    print(f"  orphan_in_mr (drift P0)   : {len(orphan_in_mr)}")
    print(f"  curve_count_mismatch (P0) : {len(curve_count_mismatch)}")
    print(f"  blocked_but_published (P1): {len(blocked_but_published)}")
    if not args.quiet:
        if missing_in_mr:
            print(f"\n  Top 5 missing_in_mr (P0):")
            for m in missing_in_mr[:5]:
                print(f"    {m}")
        if ghost_in_kc:
            print(f"\n  Top 5 ghost_in_kc (P2 — sync correctly skipped):")
            for m in ghost_in_kc[:5]:
                print(f"    {m}")
        if orphan_in_mr:
            print(f"\n  Top 5 orphan_in_mr:")
            for m in orphan_in_mr[:5]:
                print(f"    {m}")
        if curve_count_mismatch:
            print(f"\n  Top 5 curve_count_mismatch:")
            for m in curve_count_mismatch[:5]:
                print(f"    {m}")
        if blocked_but_published:
            print(f"\n  Top 5 blocked_but_published:")
            for m in blocked_but_published[:5]:
                print(f"    {m}")
    print(f"\nReport written to {out_path}")

    has_p0 = (
        len(missing_in_mr) > 0
        or len(orphan_in_mr) > 0
        or len(curve_count_mismatch) > 0
    )
    sys.exit(1 if has_p0 else 0)


if __name__ == "__main__":
    main()
