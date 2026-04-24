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


def run(args):
    formats = FORMATS if args.format == "all" else (args.format,)
    db = SessionLocal()
    total = 0
    try:
        for fmt in formats:
            rows = db.execute(text("""
                SELECT our_deck, opp_deck, curves
                FROM killer_curves
                WHERE game_format = :fmt AND is_current = true
            """), {"fmt": fmt}).fetchall()

            for r in rows:
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
                total += 1

            # Demote any older is_current rows for this report_type/format.
            db.execute(text("""
                UPDATE matchup_reports SET is_current = false
                WHERE game_format = :fmt AND report_type = 'killer_curves'
                  AND is_current = true AND generated_at < :gen
            """), {"fmt": fmt, "gen": date.today()})
            db.commit()
            print(f"[{fmt}] refreshed {len(rows)} killer_curves matchup_reports")
    finally:
        db.close()
    print(f"DONE: {total} rows synced.")
    return 0


def main():
    p = argparse.ArgumentParser(description="Sync killer_curves PG → matchup_reports")
    p.add_argument("--format", choices=("core", "infinity", "all"), default="core")
    args = p.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
