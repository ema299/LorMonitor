"""
Import matches from match_archive.db (SQLite) into PostgreSQL.
This gives us ~122K matches with 1 month of history (Feb 23 - Mar 27, 2026).

Usage: python scripts/import_from_archive.py [--dry-run]
"""
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from backend.models import SessionLocal

ARCHIVE_DB = "/mnt/HC_Volume_104764377/finanza/Lor/match_archive.db"

# Normalize deck codes: archive uses AmSt/AmR/AmE, we use AmySt/AmyR/AmyE
DECK_CODE_MAP = {
    "AmSt": "AmySt",
    "AmR": "AmyR",
    "AmE": "AmyE",
}


def normalize_deck(code):
    return DECK_CODE_MAP.get(code, code)


def import_archive(dry_run=False):
    conn = sqlite3.connect(ARCHIVE_DB)
    conn.row_factory = sqlite3.Row

    total = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
    print(f"Archive: {total} matches")

    cursor = conn.execute("""
        SELECT gid, date, queue, turns, avg_elo, winner, victory_reason, otp,
               p1_name, p1_mmr, p1_colors, p1_deck,
               p2_name, p2_mmr, p2_colors, p2_deck,
               p1_lore, p2_lore
        FROM matches
        WHERE p1_deck IS NOT NULL AND p2_deck IS NOT NULL
        ORDER BY date
    """)

    rows = []
    for r in cursor:
        deck_a = normalize_deck(r["p1_deck"])
        deck_b = normalize_deck(r["p2_deck"])

        # Determine winner as deck_a/deck_b
        winner = None
        if r["winner"] == 1:
            winner = "deck_a"
        elif r["winner"] == 2:
            winner = "deck_b"

        # Parse date
        try:
            played_at = datetime.strptime(r["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue

        # Determine perimeter from queue
        queue = r["queue"] or ""
        if queue.startswith("INF-") or queue.startswith("JA-") or queue.startswith("ZH-"):
            game_format = "infinity"
            perimeter = "inf"
        else:
            game_format = "core"
            perimeter = "set11"

        rows.append({
            "external_id": r["gid"],
            "played_at": played_at,
            "game_format": game_format,
            "queue_name": queue,
            "perimeter": perimeter,
            "deck_a": deck_a,
            "deck_b": deck_b,
            "winner": winner,
            "player_a_name": r["p1_name"],
            "player_b_name": r["p2_name"],
            "player_a_mmr": r["p1_mmr"],
            "player_b_mmr": r["p2_mmr"],
            "total_turns": r["turns"],
            "lore_a_final": r["p1_lore"],
            "lore_b_final": r["p2_lore"],
            "turns": "[]",
            "cards_a": None,
            "cards_b": None,
        })

    conn.close()
    print(f"Parsed {len(rows)} matches with valid decks")

    if dry_run:
        print("[DRY RUN] No data written.")
        return

    db = SessionLocal()
    BATCH_SIZE = 2000
    inserted = 0
    skipped = 0

    try:
        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i:i + BATCH_SIZE]
            for row in batch:
                result = db.execute(
                    text("""
                        INSERT INTO matches
                            (external_id, played_at, game_format, queue_name, perimeter,
                             deck_a, deck_b, winner, player_a_name, player_b_name,
                             player_a_mmr, player_b_mmr, total_turns, lore_a_final, lore_b_final,
                             turns, cards_a, cards_b)
                        VALUES
                            (:external_id, :played_at, :game_format, :queue_name, :perimeter,
                             :deck_a, :deck_b, :winner, :player_a_name, :player_b_name,
                             :player_a_mmr, :player_b_mmr, :total_turns, :lore_a_final, :lore_b_final,
                             :turns, :cards_a, :cards_b)
                        ON CONFLICT (external_id) DO NOTHING
                    """),
                    row,
                )
                if result.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1

            db.commit()
            print(f"  Batch {i // BATCH_SIZE + 1}: processed {min(i + BATCH_SIZE, len(rows))}")

        # Refresh materialized views
        print("Refreshing materialized views...")
        db.execute(text("REFRESH MATERIALIZED VIEW mv_meta_share"))
        db.execute(text("REFRESH MATERIALIZED VIEW mv_matchup_matrix"))
        db.commit()

        print(f"\nDone: {inserted} inserted, {skipped} already existed (dedup)")
    finally:
        db.close()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    t0 = time.time()
    import_archive(dry_run=dry_run)
    print(f"Total time: {time.time() - t0:.1f}s")
