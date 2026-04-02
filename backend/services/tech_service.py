"""Tech service — tech tornado, player card usage, consensus comparison.

Replaces dashboard_bridge.get_tech_tornado() with PostgreSQL queries.
Data source: matches.turns JSONB (CARD_PLAYED events) + consensus_lists table.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.services.cache import cache_get, cache_set

CACHE_TTL = 300  # 5 min


def get_player_cards(db: Session, game_format: str = "core", perimeters: list[str] | None = None,
                     days: int = 2, min_games: int = 2) -> dict:
    """Extract per-player card usage from CARD_PLAYED events in matches.turns JSONB.

    Returns: {player_lower: {deck: {card_name: n_games_seen}}}
    """
    if perimeters is None:
        perimeters = ["set11", "top", "pro"] if game_format == "core" else ["infinity"]

    cache_key = f"tech:player_cards:{game_format}:{','.join(perimeters)}:{days}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    # Extract CARD_PLAYED card names from turns JSONB
    # Note: single quotes in JSON keys must use E'' or the 'player' syntax
    # SQLAlchemy text() treats :word as params, so we use literal SQL for JSON operators
    sql = """
        WITH played AS (
            SELECT
                m.id,
                lower(CASE WHEN (t->>'player')::int = 1 THEN m.player_a_name
                           ELSE m.player_b_name END) AS player_name,
                CASE WHEN (t->>'player')::int = 1 THEN m.deck_a ELSE m.deck_b END AS deck,
                t->'cardRefs'->0->>'name' AS card_name
            FROM matches m,
                 jsonb_array_elements(m.turns) AS t
            WHERE m.game_format = :fmt
              AND m.perimeter = ANY(:perimeters)
              AND m.played_at >= now() - make_interval(days => :days)
              AND t->>'type' = 'CARD_PLAYED'
              AND t->'cardRefs'->0->>'name' IS NOT NULL
        )
        SELECT player_name, deck, card_name, COUNT(DISTINCT id) AS games_seen
        FROM played
        WHERE player_name IS NOT NULL
        GROUP BY player_name, deck, card_name
        HAVING COUNT(DISTINCT id) >= :min_games
    """
    rows = db.execute(text(sql), {"fmt": game_format, "perimeters": perimeters, "days": days, "min_games": min_games}).fetchall()

    result = {}
    for r in rows:
        result.setdefault(r.player_name, {}).setdefault(r.deck, {})[r.card_name] = r.games_seen

    cache_set(cache_key, result, CACHE_TTL)
    return result


def get_tech_tornado(db: Session, perimeter: str = "set11", deck_code: str | None = None,
                     game_format: str = "core", days: int = 2) -> dict | None:
    """Tech tornado: cards in/out vs consensus for a perimeter.

    Algorithm:
    1. Get player card usage from matches
    2. Get consensus from consensus_lists table
    3. IN = non-standard cards used by >=2 players
    4. OUT = standard cards (avg_qty >= 2.0) dropped by >=2 players
    """
    cache_key = f"tech:tornado:{perimeter}:{deck_code or 'all'}:{game_format}:{days}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    perimeters = [perimeter] if perimeter not in ("set11",) else ["set11", "top", "pro"]
    player_cards = get_player_cards(db, game_format, perimeters, days)

    # Get consensus
    consensus_rows = db.execute(text(
        "SELECT deck, card_name, avg_qty FROM consensus_lists WHERE is_current = true"
    )).fetchall()
    consensus = {}
    for r in consensus_rows:
        consensus.setdefault(r.deck, {})[r.card_name] = float(r.avg_qty)

    # Build tech tornado per deck
    decks_to_process = [deck_code] if deck_code else list(consensus.keys())
    result = {}

    for deck in decks_to_process:
        deck_consensus = consensus.get(deck, {})
        if not deck_consensus:
            continue

        standard_cards = {c for c, q in deck_consensus.items() if q >= 2.0}
        all_players_for_deck = {}

        # Gather players who play this deck
        for player, player_decks in player_cards.items():
            if deck in player_decks:
                all_players_for_deck[player] = player_decks[deck]

        total_players = len(all_players_for_deck)
        if total_players < 2:
            continue

        # IN: non-standard cards used by multiple players
        card_adoption = {}
        for player, cards in all_players_for_deck.items():
            for card in cards:
                if card not in standard_cards:
                    card_adoption.setdefault(card, set()).add(player)

        items_in = []
        for card, players in card_adoption.items():
            if len(players) >= 2:
                items_in.append({
                    "card": card,
                    "players": len(players),
                    "adoption": round(len(players) / total_players * 100),
                    "type": "in",
                })

        # OUT: standard cards dropped by multiple players
        card_drops = {}
        for player, cards in all_players_for_deck.items():
            played_cards = set(cards.keys())
            for std_card in standard_cards:
                if std_card not in played_cards:
                    card_drops.setdefault(std_card, set()).add(player)

        items_out = []
        for card, players in card_drops.items():
            if len(players) >= 2:
                items_out.append({
                    "card": card,
                    "players": len(players),
                    "adoption": round((1 - len(players) / total_players) * 100),
                    "type": "out",
                })

        items = sorted(items_in, key=lambda x: -x["players"]) + sorted(items_out, key=lambda x: x["players"])
        result[deck] = {"total_players": total_players, "items": items}

    if deck_code:
        deck_data = result.get(deck_code)
        if not deck_data:
            return None
        output = {"perimeter": perimeter, "deck": deck_code, **deck_data}
    else:
        output = {"perimeter": perimeter, "decks": result}

    cache_set(cache_key, output, CACHE_TTL)
    return output
