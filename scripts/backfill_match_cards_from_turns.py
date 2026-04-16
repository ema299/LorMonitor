"""Backfill matches.cards_a/cards_b from stored turns JSONB.

Useful after early imports that saved `turns` but left cards_a/cards_b empty.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from backend.models import SessionLocal

CARD_OBS_EVENT_TYPES = {"CARD_PLAYED", "CARD_INKED", "INITIAL_HAND", "CARD_DRAWN", "MULLIGAN"}
BATCH_SIZE = 1000


def extract_cards_seen(logs, player_num: int) -> list[str]:
    cards = set()
    for event in logs or []:
        if not isinstance(event, dict) or event.get("player") != player_num:
            continue
        if event.get("type") not in CARD_OBS_EVENT_TYPES:
            continue
        for ref in event.get("cardRefs") or []:
            if isinstance(ref, dict):
                name = ref.get("name")
            else:
                name = str(ref) if ref else None
            if name:
                cards.add(name)
    return sorted(cards)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=None, help="Limit scan to recent played_at window")
    parser.add_argument("--limit", type=int, default=None, help="Cap rows scanned for debugging")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    scanned = 0
    eligible = 0
    updated = 0
    skipped = 0

    where = [
        "(cards_a IS NULL OR cards_b IS NULL OR cards_a = '[]'::jsonb OR cards_b = '[]'::jsonb)",
        "turns IS NOT NULL",
        "jsonb_typeof(turns) = 'array'",
        "jsonb_array_length(turns) > 0",
    ]
    params = {}
    if args.days is not None:
        where.append("played_at >= now() - make_interval(days => :days)")
        params["days"] = args.days

    limit_sql = ""
    if args.limit is not None:
        limit_sql = " LIMIT :lim"
        params["lim"] = args.limit

    query = text(f"""
        SELECT id, turns, cards_a, cards_b
        FROM matches
        WHERE {' AND '.join(where)}
        ORDER BY played_at DESC
        {limit_sql}
    """)

    rows = db.execute(query, params).fetchall()
    batch = []
    for row in rows:
        scanned += 1
        logs = row.turns or []
        derived_a = extract_cards_seen(logs, 1)
        derived_b = extract_cards_seen(logs, 2)
        if not derived_a and not derived_b:
            skipped += 1
            continue
        eligible += 1
        batch.append(
            {
                "id": row.id,
                "cards_a": json.dumps(derived_a),
                "cards_b": json.dumps(derived_b),
            }
        )
        if len(batch) >= BATCH_SIZE:
            if not args.dry_run:
                db.execute(
                    text("""
                        UPDATE matches
                        SET cards_a = :cards_a::jsonb,
                            cards_b = :cards_b::jsonb
                        WHERE id = :id
                    """),
                    batch,
                )
                db.commit()
            updated += len(batch)
            batch = []

    if batch:
        if not args.dry_run:
            db.execute(
                text("""
                    UPDATE matches
                    SET cards_a = :cards_a::jsonb,
                        cards_b = :cards_b::jsonb
                    WHERE id = :id
                """),
                batch,
            )
            db.commit()
        updated += len(batch)

    db.close()
    print(
        {
            "scanned": scanned,
            "eligible": eligible,
            "updated": updated,
            "skipped_no_card_refs": skipped,
            "dry_run": args.dry_run,
        }
    )


if __name__ == "__main__":
    main()
