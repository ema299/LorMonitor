"""Worker: import static data (cards_db, consensus) into PostgreSQL."""
import json
import logging
from pathlib import Path
from datetime import date

from sqlalchemy import text
from backend.models import SessionLocal

logger = logging.getLogger(__name__)

CARDS_DB_PATH = Path("/mnt/HC_Volume_104764377/finanza/Lor/cards_db.json")
DUELS_INK_CACHE = Path("/mnt/HC_Volume_104764377/finanza/Lor/duels_ink_cards_cache.json")

# Set code → numeric prefix for image URLs
SET_MAP = {
    "TFC": "1", "ROF": "2", "ITI": "3", "URR": "4",
    "SSK": "5", "AZU": "6", "ABM": "7", "SIX": "8",
    "TMF": "9", "PSC": "10", "FLB": "11",
}


def _load_cards_db() -> dict:
    """Load cards DB: duels.ink cache (has correct dual ink colors) merged with local.

    duels.ink cache has "amethyst/sapphire" for dual ink cards.
    Local cards_db.json has "Dual Ink" (no color info).
    Merge: duels.ink wins for ink field, local fills gaps.
    """
    local = {}
    if CARDS_DB_PATH.exists():
        with open(CARDS_DB_PATH) as f:
            local = json.load(f)

    # Merge with duels.ink cache (correct dual ink colors)
    if DUELS_INK_CACHE.exists():
        try:
            with open(DUELS_INK_CACHE) as f:
                cache = json.load(f)
            # Cache has correct ink for dual ink cards — override local
            for name, card in cache.items():
                if name in local:
                    cache_ink = card.get('ink', '')
                    local_ink = local[name].get('ink', '')
                    # Override only if local has "Dual Ink" and cache has real colors
                    if local_ink.lower() == 'dual ink' and '/' in cache_ink:
                        local[name]['ink'] = cache_ink
                else:
                    local[name] = card
            logger.info("Merged duels.ink cache (%d cards) with local DB", len(cache))
        except Exception as e:
            logger.warning("Could not load duels.ink cache: %s", e)

    return local


def import_cards_db() -> int:
    """Import cards_db into cards table (duels.ink cache + local fallback)."""
    db_data = _load_cards_db()
    if not db_data:
        logger.error("No cards data found")
        return 0

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

    # Pick the latest non-empty snapshot (archetypes has data)
    latest = None
    for candidate in reversed(snapshots):
        with open(candidate) as _f:
            _d = json.load(_f)
        if _d.get("archetypes"):
            latest = candidate
            break
    if not latest:
        logger.error("All snapshots are empty in %s", SNAPSHOT_DIR)
        return 0

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

            # Build consensus: pick the most representative real list.
            # For each list, score = total shared cards (name+qty matches) with all others.
            # The list with the highest overlap score becomes the standard.
            deck_card_sets = []
            for dk in decks:
                card_set = {(c["name"], c["qty"]) for c in dk.get("cards", [])}
                deck_card_sets.append((dk, card_set))

            best_idx, best_score = 0, -1
            for i, (_, set_i) in enumerate(deck_card_sets):
                score = sum(len(set_i & set_j) for j, (_, set_j) in enumerate(deck_card_sets) if j != i)
                if score > best_score:
                    best_score = score
                    best_idx = i

            representative = deck_card_sets[best_idx][0]
            for card in representative.get("cards", []):
                session.execute(text("""
                    INSERT INTO consensus_lists (deck, card_name, avg_qty, snapshot_date, is_current)
                    VALUES (:deck, :card, :qty, :date, true)
                    ON CONFLICT (deck, card_name, snapshot_date) DO UPDATE
                    SET avg_qty = EXCLUDED.avg_qty, is_current = true
                """), {"deck": deck_code, "card": card["name"], "qty": card["qty"], "date": snap_date})
                consensus_count += 1

            # Reference decklist: the most representative list (highest overlap with pool)
            best = representative
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
