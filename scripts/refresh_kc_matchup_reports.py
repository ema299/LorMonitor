#!/usr/bin/env python3
"""Copy current rows from `killer_curves` PG table into the `killer_curves`
report_type rows of `matchup_reports`. Used after reclean_kc_meta.py to
push the cleaned data into the dashboard blob without rerunning the full
8-report-type matchup generator.

Usage:
    python3 scripts/refresh_kc_matchup_reports.py --format core
    python3 scripts/refresh_kc_matchup_reports.py --format all
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from sqlalchemy import text  # noqa: E402

from backend.models import SessionLocal  # noqa: E402

FORMATS = ("core", "infinity")


def _should_skip(quality_status: str | None, mode: str) -> bool:
    """Decide whether to skip a row based on its meta.quality_status.

    Modes:
        - none      : copy every row (legacy behavior).
        - blocked   : skip rows with quality_status='blocked' (default).
        - non-pass  : copy only quality_status='pass' (most aggressive).

    Rows without ``quality_status`` (legacy, pre-validator-26/04) are always
    copied — they were generated before the gate existed and have no signal.
    """
    if mode == "none" or quality_status is None:
        return False
    if mode == "blocked":
        return quality_status == "blocked"
    if mode == "non-pass":
        return quality_status != "pass"
    return False


def run(args):
    formats = FORMATS if args.format == "all" else (args.format,)
    db = SessionLocal()
    total = 0
    skipped_total = 0
    skipped_by_status: dict[str, int] = {}
    try:
        for fmt in formats:
            rows = db.execute(text("""
                SELECT our_deck, opp_deck, curves, meta
                FROM killer_curves
                WHERE game_format = :fmt AND is_current = true
            """), {"fmt": fmt}).fetchall()

            synced = 0
            skipped = 0
            for r in rows:
                meta_obj = r.meta or {}
                quality_status = (meta_obj or {}).get("quality_status")
                if _should_skip(quality_status, args.quality_filter):
                    skipped += 1
                    skipped_total += 1
                    skipped_by_status[quality_status or "none"] = (
                        skipped_by_status.get(quality_status or "none", 0) + 1
                    )
                    continue
                curves = r.curves if isinstance(r.curves, list) else json.loads(r.curves or "[]")
                db.execute(text("""
                    INSERT INTO matchup_reports
                        (game_format, our_deck, opp_deck, report_type, data,
                         generated_at, is_current)
                    VALUES
                        (:fmt, :our, :opp, 'killer_curves', CAST(:data AS jsonb),
                         :gen, true)
                    ON CONFLICT (game_format, our_deck, opp_deck, report_type, generated_at)
                    DO UPDATE SET data = EXCLUDED.data, is_current = true
                """), {
                    "fmt": fmt, "our": r.our_deck, "opp": r.opp_deck,
                    "data": json.dumps(curves), "gen": date.today(),
                })
                synced += 1
                total += 1

            # Demote any older is_current rows for this report_type/format.
            db.execute(text("""
                UPDATE matchup_reports SET is_current = false
                WHERE game_format = :fmt AND report_type = 'killer_curves'
                  AND is_current = true AND generated_at < :gen
            """), {"fmt": fmt, "gen": date.today()})
            db.commit()
            print(f"[{fmt}] synced={synced} skipped={skipped} (quality_filter={args.quality_filter})")
    finally:
        db.close()
    print(f"DONE: {total} rows synced, {skipped_total} skipped.")
    if skipped_by_status:
        print(f"  skipped by quality_status: {skipped_by_status}")
    return 0


def main():
    p = argparse.ArgumentParser(description="Sync killer_curves PG → matchup_reports")
    p.add_argument("--format", choices=("core", "infinity", "all"), default="core")
    p.add_argument(
        "--quality-filter",
        choices=("none", "blocked", "non-pass"),
        default="blocked",
        help="Skip rows by meta.quality_status: none=copy all, blocked=skip blocked (default), non-pass=copy only 'pass'.",
    )
    args = p.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
