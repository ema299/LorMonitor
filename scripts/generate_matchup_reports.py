#!/usr/bin/env python3
"""Native matchup report generator — D3 Liberation Day.

Generates all matchup reports from PG data + native digests,
upserts directly into PG matchup_reports table.

Replaces the analisidef bridge: daily_routine.py → import_matchup_reports.py.

Usage:
    python3 scripts/generate_matchup_reports.py --format core
    python3 scripts/generate_matchup_reports.py --format all
    python3 scripts/generate_matchup_reports.py --pair AmSa AbE --format core
    python3 scripts/generate_matchup_reports.py --format core --dry-run

Exit code: 0 on success, 1 on errors.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from itertools import product
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from sqlalchemy import text  # noqa: E402

from backend.models import SessionLocal  # noqa: E402
from pipelines.matchup_reports.generator import generate_all_reports  # noqa: E402

DECKS = "AmAm AmSa EmSa AbE AbS AbR AbSt AmySt SSt AmyE AmyR RS".split()
FORMATS = ("core", "infinity")


def log(msg):
    from datetime import datetime
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def run(args):
    db = SessionLocal()
    formats = FORMATS if args.format == "all" else (args.format,)
    pair = (args.pair[0], args.pair[1]) if args.pair else None

    t0 = time.time()
    total_reports = 0
    total_matchups = 0
    total_errors = 0

    try:
        for fmt in formats:
            log(f"--- Format: {fmt} ---")

            if pair:
                matchups = [pair]
            else:
                matchups = [(our, opp) for our, opp in product(DECKS, repeat=2) if our != opp]

            for our, opp in matchups:
                try:
                    reports = generate_all_reports(db, our, opp, fmt)
                except Exception as e:
                    log(f"  ERROR {our} vs {opp}: {e}")
                    total_errors += 1
                    continue

                if not reports:
                    continue

                total_matchups += 1
                n = len(reports)
                total_reports += n

                if args.dry_run:
                    log(f"  [DRY] {our} vs {opp}: {n} reports ({', '.join(reports.keys())})")
                    continue

                # Upsert to PG
                today = date.today()
                for report_type, data in reports.items():
                    db.execute(text("""
                        INSERT INTO matchup_reports
                            (game_format, our_deck, opp_deck, report_type, data,
                             generated_at, is_current)
                        VALUES
                            (:game_format, :our_deck, :opp_deck, :report_type,
                             CAST(:data AS jsonb), :generated_at, true)
                        ON CONFLICT (game_format, our_deck, opp_deck, report_type, generated_at)
                        DO UPDATE SET data = EXCLUDED.data, is_current = true
                    """), {
                        "game_format": fmt,
                        "our_deck": our,
                        "opp_deck": opp,
                        "report_type": report_type,
                        "data": json.dumps(data, default=str),
                        "generated_at": today,
                    })

                db.commit()

                if total_matchups % 20 == 0:
                    log(f"  ... {total_matchups} matchups processed, {total_reports} reports")

            log(f"  [{fmt}] {total_matchups} matchups, {total_reports} reports")

    finally:
        db.close()

    elapsed = time.time() - t0
    log(f"\nDone: {total_matchups} matchups, {total_reports} reports, "
        f"{total_errors} errors, {elapsed:.0f}s")
    return 1 if total_errors > 0 else 0


def main():
    p = argparse.ArgumentParser(description="Generate matchup reports (native)")
    p.add_argument("--format", choices=("core", "infinity", "all"), default="core")
    p.add_argument("--pair", nargs=2, metavar=("OUR", "OPP"))
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
