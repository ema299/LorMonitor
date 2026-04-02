"""Worker: import static data (cards_db, consensus) into PostgreSQL."""
import json
import logging
from pathlib import Path
from datetime import date

from sqlalchemy import text
from backend.models import SessionLocal

logger = logging.getLogger(__name__)

CARDS_DB_PATH = Path("/mnt/HC_Volume_104764377/finanza/Lor/cards_db.json")

# Set code → numeric prefix for image URLs
SET_MAP = {
    "TFC": "1", "ROF": "2", "ITI": "3", "URR": "4",
    "SSK": "5", "AZU": "6", "ABM": "7", "SIX": "8",
    "TMF": "9", "PSC": "10", "FLB": "11",
}


def import_cards_db() -> int:
    """Import cards_db.json into cards table."""
    if not CARDS_DB_PATH.exists():
        logger.error("cards_db.json not found at %s", CARDS_DB_PATH)
        return 0

    with open(CARDS_DB_PATH) as f:
        db_data = json.load(f)

    session = SessionLocal()
    count = 0
    try:
        for name, card in db_data.items():
            set_code = card.get("set", "")
            number = card.get("number", "")
            set_num = SET_MAP.get(set_code, "")
            image_path = f"{set_num}/{number}" if set_num and number else ""

            cost = _safe_int(card.get("cost"))
            strength = _safe_int(card.get("str"))
            will_val = _safe_int(card.get("will"))
            lore_val = _safe_int(card.get("lore"))

            session.execute(text("""
                INSERT INTO cards (name, ink, card_type, cost, str, will, lore,
                    ability, classifications, set_code, card_number, rarity, image_path)
                VALUES (:name, :ink, :type, :cost, :str, :will, :lore,
                    :ability, :classifications, :set_code, :number, :rarity, :image_path)
                ON CONFLICT (name) DO UPDATE SET
                    ink = EXCLUDED.ink, card_type = EXCLUDED.card_type,
                    cost = EXCLUDED.cost, str = EXCLUDED.str, will = EXCLUDED.will,
                    lore = EXCLUDED.lore, ability = EXCLUDED.ability,
                    classifications = EXCLUDED.classifications,
                    set_code = EXCLUDED.set_code, card_number = EXCLUDED.card_number,
                    rarity = EXCLUDED.rarity, image_path = EXCLUDED.image_path,
                    updated_at = now()
            """), {
                "name": name,
                "ink": card.get("ink", ""),
                "type": card.get("type", ""),
                "cost": cost,
                "str": strength,
                "will": will_val,
                "lore": lore_val,
                "ability": card.get("ability", ""),
                "classifications": card.get("classifications", ""),
                "set_code": set_code,
                "number": number,
                "rarity": card.get("rarity", ""),
                "image_path": image_path,
            })
            count += 1

        session.commit()
        logger.info("Imported %d cards into cards table", count)
        return count
    except Exception as e:
        session.rollback()
        logger.error("Cards import failed: %s", e)
        raise
    finally:
        session.close()


def _safe_int(val) -> int | None:
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


SNAPSHOT_DIR = Path("/mnt/HC_Volume_104764377/finanza/Lor/decks_db/history")

_LEGACY_NAMES = {"AS": "AmSa", "ES": "EmSa"}


def import_consensus() -> int:
    """Import latest inkdecks snapshot into consensus_lists and reference_decklists."""
    snapshots = sorted(SNAPSHOT_DIR.glob("snapshot_*.json"))
    if not snapshots:
        logger.error("No inkdecks snapshots found in %s", SNAPSHOT_DIR)
        return 0

    latest = snapshots[-1]
    # Extract date from filename: snapshot_20260325.json
    snap_date_str = latest.stem.replace("snapshot_", "")
    snap_date = date(int(snap_date_str[:4]), int(snap_date_str[4:6]), int(snap_date_str[6:8]))

    with open(latest) as f:
        data = json.load(f)

    archs = data.get("archetypes", {})
    session = SessionLocal()
    consensus_count = 0
    ref_count = 0

    try:
        # Mark old consensus as not current
        session.execute(text("UPDATE consensus_lists SET is_current = false WHERE is_current = true"))
        session.execute(text("UPDATE reference_decklists SET is_current = false WHERE is_current = true"))

        for arch, decks in archs.items():
            if not decks:
                continue

            # Normalize legacy names
            deck_code = _LEGACY_NAMES.get(arch, arch)

            # Build consensus: card average qty across decks (present in >=50%)
            from collections import defaultdict
            card_total = defaultdict(int)
            card_count = defaultdict(int)
            n = len(decks)

            for dk in decks:
                for card in dk.get("cards", []):
                    name = card["name"]
                    card_total[name] += card["qty"]
                    card_count[name] += 1

            for name in card_total:
                if card_count[name] >= n * 0.5:
                    avg_qty = round(card_total[name] / n, 1)
                    session.execute(text("""
                        INSERT INTO consensus_lists (deck, card_name, avg_qty, snapshot_date, is_current)
                        VALUES (:deck, :card, :qty, :date, true)
                        ON CONFLICT (deck, card_name, snapshot_date) DO UPDATE
                        SET avg_qty = EXCLUDED.avg_qty, is_current = true
                    """), {"deck": deck_code, "card": name, "qty": avg_qty, "date": snap_date})
                    consensus_count += 1

            # Reference decklists: top decklist per archetype (first = best ranked)
            best = decks[0]
            session.execute(text("""
                INSERT INTO reference_decklists (deck, player, rank, event, event_date, record, cards, snapshot_date, is_current)
                VALUES (:deck, :player, :rank, :event, :event_date, :record, CAST(:cards AS jsonb), :date, true)
                ON CONFLICT (deck, player, snapshot_date) DO UPDATE
                SET cards = EXCLUDED.cards, is_current = true, rank = EXCLUDED.rank
            """), {
                "deck": deck_code,
                "player": best.get("player", ""),
                "rank": best.get("rank", ""),
                "event": best.get("event", ""),
                "event_date": best.get("date", ""),
                "record": best.get("record", ""),
                "cards": json.dumps(best.get("cards", [])),
                "date": snap_date,
            })
            ref_count += 1

        session.commit()
        logger.info("Imported %d consensus cards, %d reference decklists from %s", consensus_count, ref_count, latest.name)
        return consensus_count
    except Exception as e:
        session.rollback()
        logger.error("Consensus import failed: %s", e)
        raise
    finally:
        session.close()


def import_all():
    """Run all static imports."""
    cards = import_cards_db()
    consensus = import_consensus()
    return {"cards": cards, "consensus": consensus}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = import_all()
    print(f"Imported: {result}")
