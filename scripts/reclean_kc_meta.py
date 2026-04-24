#!/usr/bin/env python3
"""Re-apply the meta-relevance + legality post-filter to existing killer
curves in PG, without calling OpenAI. Use after extending the filter logic
to strip out legal-but-dead cards that GPT had slipped into response.cards
or sequence.plays in prior runs.

Usage:
    python3 scripts/reclean_kc_meta.py --format core
    python3 scripts/reclean_kc_meta.py --format all
    python3 scripts/reclean_kc_meta.py --format core --dry-run
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

from backend.models import SessionLocal  # noqa: E402
from scripts.generate_killer_curves import (  # noqa: E402
    _strip_core_illegal_cards,
    _strip_non_meta_cards,
)

FORMATS = ("core", "infinity")


def log(msg):
    from datetime import datetime
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def run(args):
    formats = FORMATS if args.format == "all" else (args.format,)
    db = SessionLocal()
    total_updated = 0
    total_dropped = 0
    total_curves_emptied = 0
    try:
        for fmt in formats:
            rows = db.execute(text("""
                SELECT id, our_deck, opp_deck, curves
                FROM killer_curves
                WHERE game_format = :fmt AND is_current = true
                ORDER BY our_deck, opp_deck
            """), {"fmt": fmt}).fetchall()
            log(f"--- Format: {fmt} | {len(rows)} current rows ---")

            for row in rows:
                data = {"curves": row.curves if isinstance(row.curves, list) else json.loads(row.curves or "[]")}
                before_json = json.dumps(data, sort_keys=True)

                dropped = 0
                if fmt == "core":
                    dropped += _strip_core_illegal_cards(db, data)
                dropped += _strip_non_meta_cards(db, data, fmt)

                after_json = json.dumps(data, sort_keys=True)
                if dropped == 0 and before_json == after_json:
                    continue

                # Detect curves where response.cards is now empty as a
                # diagnostic; do not drop the curve itself — the sequence
                # may still be informative.
                emptied = sum(
                    1 for c in data.get("curves", [])
                    if isinstance((c.get("response") or {}).get("cards"), list)
                    and len((c["response"]["cards"])) == 0
                )
                total_curves_emptied += emptied
                total_dropped += dropped
                total_updated += 1

                if args.dry_run:
                    log(f"  [DRY] {row.our_deck} vs {row.opp_deck}: would drop {dropped} card refs "
                        f"({emptied} curves would end up with empty response.cards)")
                    continue

                db.execute(text("""
                    UPDATE killer_curves
                    SET curves = CAST(:curves AS jsonb)
                    WHERE id = :id
                """), {"curves": json.dumps(data["curves"]), "id": row.id})

            if not args.dry_run:
                db.commit()
            log(f"  [{fmt}] updated {total_updated} rows, dropped {total_dropped} card refs, "
                f"{total_curves_emptied} curves now have empty response.cards")

    finally:
        db.close()

    log(f"DONE: total_updated={total_updated} total_dropped={total_dropped} "
        f"curves_emptied={total_curves_emptied}")
    return 0


def main():
    p = argparse.ArgumentParser(description="Re-apply KC post-filters to existing data")
    p.add_argument("--format", choices=("core", "infinity", "all"), default="core")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
