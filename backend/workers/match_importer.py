"""Worker: import new match JSON files into PostgreSQL."""
import json
import logging
from pathlib import Path
from datetime import datetime

from sqlalchemy import text
from backend.config import MATCHES_DIR
from backend.models import SessionLocal

logger = logging.getLogger(__name__)

BATCH_SIZE = 500
DATE_FOLDERS_PATTERN = "[0-9][0-9][0-9][0-9][0-9][0-9]"
CARD_OBS_EVENT_TYPES = {"CARD_PLAYED", "CARD_INKED", "INITIAL_HAND", "CARD_DRAWN", "MULLIGAN"}


def get_format_from_folder(folder_name: str) -> str:
    mapping = {"SET11": "core", "TOP": "core", "PRO": "core", "FRIENDS": "core", "INF": "infinity"}
    return mapping.get(folder_name, "other")


def get_perimeter_from_folder(folder_name: str) -> str:
    mapping = {"SET11": "set11", "TOP": "top", "PRO": "pro", "FRIENDS": "friends", "INF": "infinity"}
    return mapping.get(folder_name, "other")


def _extract_cards_seen(logs: list[dict], player_num: int) -> list[str]:
    """Rebuild observed deck cards from raw public logs."""
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


def import_new_matches(days_back: int = 3) -> dict:
    """Scan recent match folders and import new files."""
    db = SessionLocal()
    stats = {"scanned": 0, "imported": 0, "skipped": 0, "errors": 0}

    try:
        # Get existing external_ids
        existing = set()
        rows = db.execute(text("SELECT external_id FROM matches WHERE external_id IS NOT NULL")).fetchall()
        existing = {r[0] for r in rows}
        logger.info("Found %d existing matches in DB", len(existing))

        # Scan date folders
        date_dirs = sorted(MATCHES_DIR.glob(DATE_FOLDERS_PATTERN), reverse=True)[:days_back * 2]

        batch = []
        for date_dir in date_dirs:
            for sub_folder in date_dir.iterdir():
                if not sub_folder.is_dir():
                    continue
                game_format = get_format_from_folder(sub_folder.name)
                perimeter = get_perimeter_from_folder(sub_folder.name)

                for json_file in sub_folder.glob("*.json"):
                    stats["scanned"] += 1
                    ext_id = json_file.stem

                    if ext_id in existing:
                        stats["skipped"] += 1
                        continue

                    try:
                        match_data = _parse_match_file(json_file, game_format, perimeter, ext_id)
                        if match_data:
                            batch.append(match_data)
                            existing.add(ext_id)
                    except Exception as e:
                        stats["errors"] += 1
                        logger.warning("Error parsing %s: %s", json_file, e)

                    if len(batch) >= BATCH_SIZE:
                        _insert_batch(db, batch)
                        stats["imported"] += len(batch)
                        batch = []

        if batch:
            _insert_batch(db, batch)
            stats["imported"] += len(batch)

        db.commit()
        logger.info("Import complete: %s", stats)
        return stats

    finally:
        db.close()


def _parse_match_file(path: Path, game_format: str, perimeter: str, ext_id: str) -> dict | None:
    with open(path) as f:
        data = json.load(f)

    gi = data.get("game_info", {})
    if not gi:
        return None

    logs = (data.get("log_data") or {}).get("logs") or data.get("turns") or []
    cards_a = data.get("cards_a") or _extract_cards_seen(logs, 1)
    cards_b = data.get("cards_b") or _extract_cards_seen(logs, 2)

    return {
        "external_id": ext_id,
        "played_at": gi.get("date", datetime.now().isoformat()),
        "game_format": game_format,
        "queue_name": gi.get("queueShortName", ""),
        "perimeter": perimeter,
        "deck_a": gi.get("player1", {}).get("deck", ""),
        "deck_b": gi.get("player2", {}).get("deck", ""),
        "winner": gi.get("winner", ""),
        "player_a_name": gi.get("player1", {}).get("name", ""),
        "player_b_name": gi.get("player2", {}).get("name", ""),
        "player_a_mmr": gi.get("player1", {}).get("mmr"),
        "player_b_mmr": gi.get("player2", {}).get("mmr"),
        "total_turns": len(logs),
        "lore_a_final": gi.get("player1", {}).get("lore_final"),
        "lore_b_final": gi.get("player2", {}).get("lore_final"),
        "turns": json.dumps(logs),
        "cards_a": json.dumps(cards_a),
        "cards_b": json.dumps(cards_b),
    }


def _insert_batch(db, batch: list[dict]):
    if not batch:
        return
    db.execute(
        text("""
            INSERT INTO matches (external_id, played_at, game_format, queue_name, perimeter,
                deck_a, deck_b, winner, player_a_name, player_b_name,
                player_a_mmr, player_b_mmr, total_turns, lore_a_final, lore_b_final,
                turns, cards_a, cards_b)
            VALUES (:external_id, :played_at, :game_format, :queue_name, :perimeter,
                :deck_a, :deck_b, :winner, :player_a_name, :player_b_name,
                :player_a_mmr, :player_b_mmr, :total_turns, :lore_a_final, :lore_b_final,
                :turns::jsonb, :cards_a::jsonb, :cards_b::jsonb)
            ON CONFLICT (external_id) DO NOTHING
        """),
        batch,
    )


def refresh_views(db=None):
    """Refresh materialized views after import."""
    close = False
    if db is None:
        db = SessionLocal()
        close = True
    try:
        db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_meta_share"))
        db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_matchup_matrix"))
        db.commit()
        logger.info("Materialized views refreshed")
    except Exception as e:
        logger.error("View refresh failed: %s", e)
    finally:
        if close:
            db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    stats = import_new_matches()
    print(f"Import: {stats}")
    refresh_views()
