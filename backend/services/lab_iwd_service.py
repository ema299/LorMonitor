"""Lab IWD service — Improvement When Drawn per card (matchup-specific).

For a given deck pair (our vs opp) we compute, for each candidate card in our
deck, how the winrate changes when the card is seen in hand by T3 vs when it
isn't.

Definition of "drawn by T3" (adapted to duels.ink logs):
A card is considered "drawn by T3" if it appears in ANY of the following event
types for player=1 with turnNumber <= 3:
  - INITIAL_HAND  (opening 7)
  - CARD_DRAWN    (ability-triggered draw)
  - CARD_PLAYED   (if played, it was in hand)
  - CARD_INKED    (if inked, it was in hand)

TURN_DRAW (automatic end-of-turn draw) has empty cardRefs in public logs,
so we infer via CARD_PLAYED / CARD_INKED. Accuracy < 17Lands but is the best
approximation possible given the log format.

Pool of candidate cards = top-30 most-seen cards across all matches of the
matchup. Data-driven, no dependency on consensus_lists.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session


# Minimum sample sizes for a card to be considered reliable
MIN_DRAWN_GAMES = 20
MIN_NOT_DRAWN_GAMES = 20
TOP_CARDS_LIMIT = 30
MIN_TOTAL_MATCHES = 80  # below this threshold the whole matchup is "low sample"


def get_iwd(
    db: Session,
    our_deck: str,
    opp_deck: str,
    game_format: str = "core",
    days: int = 14,
) -> dict:
    """Return IWD stats for our_deck vs opp_deck.

    Output:
    {
        "our": "EmSa", "opp": "AmAm",
        "total_matches": N, "wins": W, "losses": L, "overall_wr": 52.3,
        "days": 14, "min_drawn_games": 20,
        "cards": [
            {
                "card": "Grandmother Willow",
                "drawn_games": 134, "wr_drawn": 60.4,
                "not_drawn_games": 48, "wr_not_drawn": 45.8,
                "delta_wr": 14.6,
                "confidence": "high",   # high|med|low
            }, ...
        ]
    }

    Returns {..., "cards": [], "low_sample": True} if total_matches < MIN_TOTAL_MATCHES.
    """
    # 1. Total matches + wins for this matchup (our always = deck_a since that
    #    is the convention in ingest: player 1 = deck_a = "us" when we query)
    totals = db.execute(text("""
        SELECT COUNT(*) AS n,
               COUNT(*) FILTER (WHERE winner = 'deck_a') AS wins
        FROM matches
        WHERE deck_a = :our AND deck_b = :opp
          AND game_format = :fmt
          AND played_at >= now() - make_interval(days => :days)
    """), {"our": our_deck, "opp": opp_deck, "fmt": game_format, "days": days}).fetchone()

    total_matches = totals.n
    wins = totals.wins
    losses = total_matches - wins
    overall_wr = round(wins / total_matches * 100, 1) if total_matches else 0.0

    if total_matches < MIN_TOTAL_MATCHES:
        return {
            "our": our_deck,
            "opp": opp_deck,
            "game_format": game_format,
            "days": days,
            "total_matches": total_matches,
            "wins": wins,
            "losses": losses,
            "overall_wr": overall_wr,
            "cards": [],
            "low_sample": True,
            "min_total_matches": MIN_TOTAL_MATCHES,
        }

    # 2. Cards seen by T3 for player 1, aggregated per match + card
    #    then join with match result to compute WR on the drawn subset
    #    and infer the not_drawn subset via total - drawn.
    rows = db.execute(text("""
        WITH matchup AS (
            SELECT id, winner
            FROM matches
            WHERE deck_a = :our AND deck_b = :opp
              AND game_format = :fmt
              AND played_at >= now() - make_interval(days => :days)
        ),
        seen_by_t3 AS (
            SELECT DISTINCT m.id, m.winner, (c->>'name') AS card_name
            FROM matchup m
            JOIN matches mm ON mm.id = m.id,
                 jsonb_array_elements(mm.turns) evt,
                 jsonb_array_elements(evt->'cardRefs') c
            WHERE (evt->>'player')::int = 1
              AND (evt->>'turnNumber')::int <= 3
              AND evt->>'type' IN ('INITIAL_HAND','CARD_DRAWN','CARD_PLAYED','CARD_INKED')
              AND (c->>'name') IS NOT NULL
        ),
        per_card AS (
            SELECT card_name,
                   COUNT(DISTINCT id) AS drawn_games,
                   COUNT(DISTINCT id) FILTER (WHERE winner = 'deck_a') AS wins_drawn
            FROM seen_by_t3
            GROUP BY card_name
        )
        SELECT card_name, drawn_games, wins_drawn
        FROM per_card
        ORDER BY drawn_games DESC
        LIMIT :top_n
    """), {
        "our": our_deck, "opp": opp_deck, "fmt": game_format,
        "days": days, "top_n": TOP_CARDS_LIMIT,
    }).fetchall()

    cards = []
    for r in rows:
        drawn_games = r.drawn_games
        wins_drawn = r.wins_drawn
        not_drawn_games = total_matches - drawn_games
        wins_not_drawn = wins - wins_drawn

        if drawn_games < MIN_DRAWN_GAMES or not_drawn_games < MIN_NOT_DRAWN_GAMES:
            # Not enough signal for this card — skip (keeps output clean)
            continue

        wr_drawn = round(wins_drawn / drawn_games * 100, 1)
        wr_not = round(wins_not_drawn / not_drawn_games * 100, 1) if not_drawn_games else 0.0
        delta = round(wr_drawn - wr_not, 1)

        # Confidence bands (simple heuristic based on sample size)
        min_sample = min(drawn_games, not_drawn_games)
        if min_sample >= 100:
            conf = "high"
        elif min_sample >= 40:
            conf = "med"
        else:
            conf = "low"

        cards.append({
            "card": r.card_name,
            "drawn_games": drawn_games,
            "wr_drawn": wr_drawn,
            "not_drawn_games": not_drawn_games,
            "wr_not_drawn": wr_not,
            "delta_wr": delta,
            "confidence": conf,
        })

    # Sort by |delta_wr| desc (strongest signal first, either positive or negative)
    cards.sort(key=lambda c: abs(c["delta_wr"]), reverse=True)

    return {
        "our": our_deck,
        "opp": opp_deck,
        "game_format": game_format,
        "days": days,
        "total_matches": total_matches,
        "wins": wins,
        "losses": losses,
        "overall_wr": overall_wr,
        "cards": cards,
        "low_sample": False,
        "min_drawn_games": MIN_DRAWN_GAMES,
        "min_not_drawn_games": MIN_NOT_DRAWN_GAMES,
    }
