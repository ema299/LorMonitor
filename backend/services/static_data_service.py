"""Static data service — cards, consensus, reference decklists from PostgreSQL."""
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.services.cache import cache_get, cache_set

CACHE_TTL = 3600  # 1 hour — static data changes rarely


def get_card_images(db: Session) -> dict:
    """Card name → image path for thumbnail URLs. Replaces dashboard_data['card_images']."""
    cached = cache_get("static:card_images")
    if cached:
        return cached

    rows = db.execute(text(
        "SELECT name, image_path FROM cards WHERE image_path IS NOT NULL AND image_path != ''"
    )).fetchall()

    result = {r.name: r.image_path for r in rows}
    cache_set("static:card_images", result, CACHE_TTL)
    return result


def get_card_types(db: Session) -> dict:
    """Card name → type (Character, Action, Song, etc.). Replaces dashboard_data['card_types']."""
    cached = cache_get("static:card_types")
    if cached:
        return cached

    rows = db.execute(text("SELECT name, card_type FROM cards")).fetchall()
    result = {r.name: r.card_type for r in rows}
    cache_set("static:card_types", result, CACHE_TTL)
    return result


def get_card_inks(db: Session) -> dict:
    """Card name → ink color. Replaces dashboard_data['card_inks']."""
    cached = cache_get("static:card_inks")
    if cached:
        return cached

    rows = db.execute(text("SELECT name, ink FROM cards")).fetchall()
    result = {r.name: r.ink for r in rows}
    cache_set("static:card_inks", result, CACHE_TTL)
    return result


def get_consensus(db: Session, deck: str | None = None) -> dict:
    """Deck consensus lists. Replaces dashboard_data['consensus']."""
    cache_key = f"static:consensus:{deck or 'all'}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    if deck:
        rows = db.execute(text(
            "SELECT card_name, avg_qty FROM consensus_lists WHERE deck = :deck AND is_current = true"
        ), {"deck": deck}).fetchall()
        result = {deck: {r.card_name: float(r.avg_qty) for r in rows}}
    else:
        rows = db.execute(text(
            "SELECT deck, card_name, avg_qty FROM consensus_lists WHERE is_current = true"
        )).fetchall()
        result = {}
        for r in rows:
            result.setdefault(r.deck, {})[r.card_name] = float(r.avg_qty)

    cache_set(cache_key, result, CACHE_TTL)
    return result


def get_reference_decklists(db: Session) -> dict:
    """Reference tournament decklists. Replaces dashboard_data['reference_decklists']."""
    cached = cache_get("static:reference_decklists")
    if cached:
        return cached

    rows = db.execute(text("""
        SELECT deck, player, rank, event, event_date, record, cards
        FROM reference_decklists WHERE is_current = true
        ORDER BY deck, rank
    """)).fetchall()

    result = {}
    for r in rows:
        result.setdefault(r.deck, []).append({
            "player": r.player,
            "rank": r.rank,
            "event": r.event,
            "event_date": r.event_date,
            "record": r.record,
            "cards": r.cards,
        })

    cache_set("static:reference_decklists", result, CACHE_TTL)
    return result


def get_card_by_name(db: Session, name: str) -> dict | None:
    """Get single card details."""
    row = db.execute(text("SELECT * FROM cards WHERE name = :name"), {"name": name}).fetchone()
    if not row:
        return None
    return dict(row._mapping)
