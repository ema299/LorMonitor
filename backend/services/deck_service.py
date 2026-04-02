"""
Deck service — card scores, optimizer, mulligan stats.
Computes card-level analytics from match turn data in PostgreSQL.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session


def get_card_scores(db: Session, our_deck: str, opp_deck: str,
                    game_format: str = "core", days: int = 7):
    """Card win-rate contribution: how often each card appears in wins vs losses.

    Extracts card plays from JSONB turns data via PostgreSQL.
    """
    rows = db.execute(text("""
        WITH card_plays AS (
            SELECT m.id, m.winner,
                   jsonb_array_elements(
                       jsonb_path_query_array(m.turns, '$[*] ? (@.type == "CARD_PLAYED" && @.player == 1).cardRefs[0].name')
                   ) #>> '{}' AS card_name
            FROM matches m
            WHERE m.game_format = :fmt
              AND m.deck_a = :our AND m.deck_b = :opp
              AND m.played_at >= now() - make_interval(days => :days)
        )
        SELECT card_name,
               COUNT(DISTINCT id) AS games_seen,
               COUNT(DISTINCT id) FILTER (WHERE winner = 'deck_a') AS wins_with,
               COUNT(DISTINCT id) FILTER (WHERE winner = 'deck_b') AS losses_with
        FROM card_plays
        GROUP BY card_name
        HAVING COUNT(DISTINCT id) >= 2
        ORDER BY COUNT(DISTINCT id) DESC
    """), {"fmt": game_format, "our": our_deck, "opp": opp_deck, "days": days}).fetchall()

    return [
        {
            "card": r.card_name,
            "games_seen": r.games_seen,
            "wins_with": r.wins_with,
            "losses_with": r.losses_with,
            "wr_with": round(r.wins_with / r.games_seen * 100, 1) if r.games_seen else 0,
        }
        for r in rows
    ]


def get_deck_breakdown(db: Session, deck_code: str, game_format: str = "core", days: int = 7):
    """Overall deck stats: WR, avg turns, avg lore, record vs each opponent."""
    rows = db.execute(text("""
        SELECT deck_b AS opp_deck,
               COUNT(*) AS games,
               COUNT(*) FILTER (WHERE winner = 'deck_a') AS wins,
               ROUND(AVG(total_turns), 1) AS avg_turns
        FROM matches
        WHERE game_format = :fmt
          AND deck_a = :deck
          AND played_at >= now() - make_interval(days => :days)
        GROUP BY deck_b
        ORDER BY games DESC
    """), {"fmt": game_format, "deck": deck_code, "days": days}).fetchall()

    total_games = sum(r.games for r in rows)
    total_wins = sum(r.wins for r in rows)

    return {
        "deck": deck_code,
        "total_games": total_games,
        "total_wins": total_wins,
        "total_losses": total_games - total_wins,
        "wr": round(total_wins / total_games * 100, 1) if total_games else 0,
        "matchups": [
            {
                "opp_deck": r.opp_deck,
                "games": r.games,
                "wins": r.wins,
                "wr": round(r.wins / r.games * 100, 1) if r.games else 0,
                "avg_turns": float(r.avg_turns) if r.avg_turns else 0,
            }
            for r in rows
        ],
    }


def get_history_snapshots(db: Session, perimeter: str = "full", days: int = 30):
    """Historical snapshots from daily_snapshots table."""
    rows = db.execute(text("""
        SELECT snapshot_date, data
        FROM daily_snapshots
        WHERE perimeter = :perim
          AND snapshot_date >= (now() - make_interval(days => :days))::date
        ORDER BY snapshot_date DESC
    """), {"perim": perimeter, "days": days}).fetchall()

    return [
        {"date": r.snapshot_date.isoformat(), "data": r.data}
        for r in rows
    ]


def get_pro_mulligans(db: Session, our_deck: str, opp_deck: str,
                      game_format: str = "core", days: int = 7) -> dict | None:
    """PRO mulligan hands from matches.turns JSONB.

    Extracts INITIAL_HAND + MULLIGAN events for pro/top perimeters.
    Returns: {our_deck, opp_deck, hands: [...], count: int}.
    """
    # Get matching pro/top games
    rows = db.execute(text("""
        SELECT id, player_a_name, player_b_name, deck_a, deck_b, winner, turns
        FROM matches
        WHERE game_format = :fmt
          AND ((deck_a = :our AND deck_b = :opp) OR (deck_a = :opp AND deck_b = :our))
          AND perimeter IN ('pro', 'top')
          AND played_at >= now() - make_interval(days => :days)
        LIMIT 200
    """), {"fmt": game_format, "our": our_deck, "opp": opp_deck, "days": days}).fetchall()

    if not rows:
        return None

    hands = []
    for match in rows:
        # Determine which player is "our"
        if match.deck_a == our_deck:
            our_player = 1
            player_name = match.player_a_name
        else:
            our_player = 2
            player_name = match.player_b_name

        won = (match.winner == 'deck_a' and our_player == 1) or \
              (match.winner == 'deck_b' and our_player == 2)

        # Extract hand events for our player
        initial = []
        sent = []
        final = []
        mull_count = 0
        otp = None

        for ev in match.turns:
            etype = ev.get("type")
            eplayer = ev.get("player")

            if etype == "INITIAL_HAND" and eplayer == our_player:
                initial = [c.get("name", "") for c in ev.get("cardRefs", [])]

            elif etype == "MULLIGAN" and eplayer == our_player:
                data = ev.get("data", {})
                mull_count = data.get("mulliganCount", 0)
                cards = [c.get("name", "") for c in ev.get("cardRefs", [])]
                if mull_count > 0 and cards:
                    sent = cards[:mull_count]
                    received = cards[mull_count:]
                    # Final hand = initial - sent + received
                    final_hand = [c for c in initial if c not in sent]
                    final_hand.extend(received)
                    final = final_hand
                else:
                    final = list(initial)

            elif etype == "TURN_START" and otp is None:
                # First TURN_START tells us who goes first
                otp = (eplayer == our_player)

        if not initial:
            continue

        if not final:
            final = list(initial)

        hands.append({
            "player": player_name or "",
            "initial": initial,
            "sent": sent,
            "final": final,
            "mull": mull_count,
            "won": won,
            "otp": otp,
            "game": match.id,
        })

    if not hands:
        return None

    return {
        "our_deck": our_deck,
        "opp_deck": opp_deck,
        "hands": hands,
        "count": len(hands),
    }
