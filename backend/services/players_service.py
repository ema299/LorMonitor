"""
Players service — top players, leaderboard, player details.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session


def get_top_players(db: Session, game_format: str = "core", days: int = 7,
                    min_games: int = 3, min_mmr: int = 1500, limit: int = 70):
    """Top players ranked by win rate (minimum games threshold)."""
    rows = db.execute(text("""
        SELECT player_a_name AS player, deck_a AS deck,
               MAX(player_a_mmr) AS mmr,
               COUNT(*) AS games,
               COUNT(*) FILTER (WHERE winner = 'deck_a') AS wins
        FROM matches
        WHERE game_format = :fmt
          AND played_at >= now() - make_interval(days => :days)
          AND player_a_mmr >= :min_mmr
        GROUP BY player_a_name, deck_a
        HAVING COUNT(*) >= :min_games
        ORDER BY COUNT(*) FILTER (WHERE winner = 'deck_a')::float / COUNT(*) DESC
        LIMIT :lim
    """), {
        "fmt": game_format, "days": days,
        "min_games": min_games, "min_mmr": min_mmr, "lim": limit,
    }).fetchall()

    return [
        {
            "player": r.player,
            "deck": r.deck,
            "mmr": r.mmr,
            "games": r.games,
            "wins": r.wins,
            "losses": r.games - r.wins,
            "wr": round(r.wins / r.games * 100, 1) if r.games else 0,
        }
        for r in rows
    ]


def get_player_detail(db: Session, player_name: str, game_format: str = "core", days: int = 7):
    """Detailed stats for a single player: matchup breakdown."""
    rows = db.execute(text("""
        SELECT deck_a AS our_deck, deck_b AS opp_deck,
               COUNT(*) AS games,
               COUNT(*) FILTER (WHERE winner = 'deck_a') AS wins
        FROM matches
        WHERE game_format = :fmt
          AND played_at >= now() - make_interval(days => :days)
          AND player_a_name = :name
        GROUP BY deck_a, deck_b
        ORDER BY games DESC
    """), {"fmt": game_format, "days": days, "name": player_name}).fetchall()

    return [
        {
            "our_deck": r.our_deck,
            "opp_deck": r.opp_deck,
            "games": r.games,
            "wins": r.wins,
            "wr": round(r.wins / r.games * 100, 1) if r.games else 0,
        }
        for r in rows
    ]


def get_leaderboard(db: Session, game_format: str = "core", days: int = 7, limit: int = 100):
    """Leaderboard: all players ranked by MMR."""
    rows = db.execute(text("""
        SELECT player_a_name AS player,
               MAX(player_a_mmr) AS mmr,
               MODE() WITHIN GROUP (ORDER BY deck_a) AS main_deck,
               COUNT(*) AS games,
               COUNT(*) FILTER (WHERE winner = 'deck_a') AS wins
        FROM matches
        WHERE game_format = :fmt
          AND played_at >= now() - make_interval(days => :days)
          AND player_a_mmr IS NOT NULL
        GROUP BY player_a_name
        HAVING COUNT(*) >= 3
        ORDER BY MAX(player_a_mmr) DESC
        LIMIT :lim
    """), {"fmt": game_format, "days": days, "lim": limit}).fetchall()

    return [
        {
            "rank": i + 1,
            "player": r.player,
            "mmr": r.mmr,
            "main_deck": r.main_deck,
            "games": r.games,
            "wins": r.wins,
            "wr": round(r.wins / r.games * 100, 1) if r.games else 0,
        }
        for i, r in enumerate(rows)
    ]
