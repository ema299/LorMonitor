"""
Import matchup report data from dashboard_data.json → matchup_reports table.

Imports all report types found in each matchup block.

Usage:
    python -m scripts.import_matchup_reports [--dry-run] [--format core|infinity]
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

# Allow running as module from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import ANALISIDEF_DAILY_DIR
from backend.models import SessionLocal

DASHBOARD_JSON = ANALISIDEF_DAILY_DIR / "dashboard_data.json"

# Report types to import (keys in each matchup block)
REPORT_TYPES = [
    "overview",
    "playbook",
    "decklist",
    "loss_analysis",
    "winning_hands",
    "board_state",
    "killer_responses",
    "ability_cards",
    "killer_curves",
    "threats_llm",
    "card_scores",
    "pro_mulligans",
]


def load_dashboard_data() -> dict:
    if not DASHBOARD_JSON.exists():
        print(f"ERROR: {DASHBOARD_JSON} not found")
        sys.exit(1)
    with open(DASHBOARD_JSON) as f:
        return json.load(f)


def import_reports(game_format: str = "core", dry_run: bool = False):
    data = load_dashboard_data()

    key = "matchup_analyzer_infinity" if game_format == "infinity" else "matchup_analyzer"
    analyzer = data.get(key, {})

    today = date.today()
    rows = []

    for deck_code, deck_data in analyzer.items():
        if not isinstance(deck_data, dict):
            continue
        if deck_code in ("available_decks", "all_decks"):
            continue

        for matchup_key, matchup_data in deck_data.items():
            if not matchup_key.startswith("vs_"):
                continue
            if not isinstance(matchup_data, dict):
                continue

            opp_deck = matchup_key[3:]  # strip "vs_"

            for report_type in REPORT_TYPES:
                report_data = matchup_data.get(report_type)
                if not report_data:
                    continue

                rows.append({
                    "game_format": game_format,
                    "our_deck": deck_code,
                    "opp_deck": opp_deck,
                    "report_type": report_type,
                    "data": json.dumps(report_data),
                    "generated_at": today,
                    "is_current": True,
                })

    print(f"Format: {game_format} | Reports to import: {len(rows)}")

    if dry_run:
        # Show summary by type
        from collections import Counter
        counts = Counter(r["report_type"] for r in rows)
        for rt, c in sorted(counts.items()):
            print(f"  {rt}: {c}")
        print("Dry run — no changes made.")
        return

    db = SessionLocal()
    try:
        # Mark old reports as not current
        db.execute(
            __import__("sqlalchemy").text(
                "UPDATE matchup_reports SET is_current = false "
                "WHERE game_format = :fmt AND is_current = true"
            ),
            {"fmt": game_format},
        )

        # Batch insert
        from sqlalchemy import text
        insert_sql = text("""
            INSERT INTO matchup_reports
                (game_format, our_deck, opp_deck, report_type, data, generated_at, is_current)
            VALUES
                (:game_format, :our_deck, :opp_deck, :report_type, CAST(:data AS jsonb), :generated_at, :is_current)
            ON CONFLICT (game_format, our_deck, opp_deck, report_type, generated_at)
            DO UPDATE SET data = EXCLUDED.data, is_current = true
        """)

        batch_size = 100
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            for row in batch:
                db.execute(insert_sql, row)
            db.flush()

        db.commit()
        print(f"Imported {len(rows)} reports into matchup_reports.")

        # Show summary
        from collections import Counter
        counts = Counter(r["report_type"] for r in rows)
        for rt, c in sorted(counts.items()):
            print(f"  {rt}: {c}")

    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import matchup reports from dashboard_data.json")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be imported")
    parser.add_argument("--format", default="core", choices=["core", "infinity"],
                        help="Game format to import (default: core)")
    args = parser.parse_args()

    import_reports(game_format=args.format, dry_run=args.dry_run)
