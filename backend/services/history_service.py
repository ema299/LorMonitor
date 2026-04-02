"""History service — daily snapshots, meta trends from PostgreSQL."""
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.services.cache import cache_get, cache_set

CACHE_TTL = 600  # 10 min


def get_daily_trend(db: Session, game_format: str = "core", perimeter: str = "set11",
                    days: int = 30) -> list[dict]:
    """Daily WR trend per deck over the last N days.

    Returns: [{date, decks: [{deck, games, wins, wr}]}]
    """
    cache_key = f"history:trend:{game_format}:{perimeter}:{days}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    rows = db.execute(text("""
        SELECT played_at::date AS day, deck_a AS deck,
               COUNT(*) AS games,
               COUNT(*) FILTER (WHERE winner = 'deck_a') AS wins
        FROM matches
        WHERE game_format = :fmt AND perimeter = :perim
          AND played_at >= now() - make_interval(days => :days)
        GROUP BY day, deck_a
        ORDER BY day, games DESC
    """), {"fmt": game_format, "perim": perimeter, "days": days}).fetchall()

    # Group by day
    by_day = {}
    for r in rows:
        day_str = r.day.isoformat()
        by_day.setdefault(day_str, []).append({
            "deck": r.deck,
            "games": r.games,
            "wins": r.wins,
            "wr": round(r.wins / r.games * 100, 1) if r.games > 0 else 0,
        })

    result = [{"date": d, "decks": decks} for d, decks in sorted(by_day.items())]
    cache_set(cache_key, result, CACHE_TTL)
    return result


def get_matchup_trend(db: Session, our_deck: str, opp_deck: str,
                      game_format: str = "core", days: int = 30) -> list[dict]:
    """Daily WR trend for a specific matchup.

    Returns: [{date, games, wins, wr}]
    """
    cache_key = f"history:matchup_trend:{our_deck}:{opp_deck}:{game_format}:{days}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    rows = db.execute(text("""
        SELECT played_at::date AS day,
               COUNT(*) AS games,
               COUNT(*) FILTER (WHERE winner = 'deck_a') AS wins
        FROM matches
        WHERE game_format = :fmt
          AND deck_a = :our AND deck_b = :opp
          AND played_at >= now() - make_interval(days => :days)
        GROUP BY day
        ORDER BY day
    """), {"fmt": game_format, "our": our_deck, "opp": opp_deck, "days": days}).fetchall()

    result = [{
        "date": r.day.isoformat(),
        "games": r.games,
        "wins": r.wins,
        "wr": round(r.wins / r.games * 100, 1) if r.games > 0 else 0,
    } for r in rows]

    cache_set(cache_key, result, CACHE_TTL)
    return result


def get_snapshots(db: Session, perimeter: str = "set11", days: int = 30) -> list[dict]:
    """Historical daily snapshots from daily_snapshots table.

    Returns: [{date, data: {...}}]
    """
    rows = db.execute(text("""
        SELECT snapshot_date, data FROM daily_snapshots
        WHERE perimeter = :perim
          AND snapshot_date >= now()::date - :days
        ORDER BY snapshot_date DESC
    """), {"perim": perimeter, "days": days}).fetchall()

    return [{"date": r.snapshot_date.isoformat(), "data": r.data} for r in rows]
