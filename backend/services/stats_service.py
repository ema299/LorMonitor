"""
Stats service — win rates, matchup matrix, meta share, OTP/OTD.
All queries hit PostgreSQL instead of scanning JSON files.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session


def get_meta_share(db: Session, game_format: str = "core", days: int = 2):
    """Meta share: % of games per deck."""
    rows = db.execute(text("""
        SELECT deck_a AS deck, COUNT(*) AS games,
               COUNT(*) FILTER (WHERE winner = 'deck_a') AS wins
        FROM matches
        WHERE game_format = :fmt AND played_at >= now() - make_interval(days => :days)
        GROUP BY deck_a
        ORDER BY games DESC
    """), {"fmt": game_format, "days": days}).fetchall()

    total = sum(r.games for r in rows)
    return [
        {
            "deck": r.deck,
            "games": r.games,
            "wins": r.wins,
            "losses": r.games - r.wins,
            "wr": round(r.wins / r.games * 100, 1) if r.games else 0,
            "meta_share": round(r.games / total * 100, 1) if total else 0,
        }
        for r in rows
    ]


def get_deck_winrates(db: Session, game_format: str = "core", perimeter: str | None = None, days: int = 2):
    """Win rate per deck, optionally filtered by perimeter."""
    params = {"fmt": game_format, "days": days}
    where_perim = ""
    if perimeter:
        where_perim = "AND perimeter = :perim"
        params["perim"] = perimeter

    rows = db.execute(text(f"""
        SELECT deck_a AS deck,
               COUNT(*) AS games,
               COUNT(*) FILTER (WHERE winner = 'deck_a') AS wins
        FROM matches
        WHERE game_format = :fmt
          AND played_at >= now() - make_interval(days => :days)
          {where_perim}
        GROUP BY deck_a
        ORDER BY games DESC
    """), params).fetchall()

    return [
        {
            "deck": r.deck,
            "games": r.games,
            "wins": r.wins,
            "losses": r.games - r.wins,
            "wr": round(r.wins / r.games * 100, 1) if r.games else 0,
        }
        for r in rows
    ]


def get_matchup_matrix(db: Session, game_format: str = "core", perimeter: str | None = None, days: int = 7):
    """Full matchup matrix: WR for every deck_a vs deck_b pair."""
    params = {"fmt": game_format, "days": days}
    where_perim = ""
    if perimeter:
        where_perim = "AND perimeter = :perim"
        params["perim"] = perimeter

    rows = db.execute(text(f"""
        SELECT deck_a, deck_b,
               COUNT(*) AS games,
               COUNT(*) FILTER (WHERE winner = 'deck_a') AS wins_a,
               ROUND(AVG(total_turns), 1) AS avg_turns
        FROM matches
        WHERE game_format = :fmt
          AND played_at >= now() - make_interval(days => :days)
          {where_perim}
        GROUP BY deck_a, deck_b
        ORDER BY deck_a, deck_b
    """), params).fetchall()

    matrix = {}
    for r in rows:
        if r.deck_a not in matrix:
            matrix[r.deck_a] = {}
        matrix[r.deck_a][r.deck_b] = {
            "games": r.games,
            "wins": r.wins_a,
            "wr": round(r.wins_a / r.games * 100, 1) if r.games else 0,
            "avg_turns": float(r.avg_turns) if r.avg_turns else 0,
        }
    return matrix


def get_otp_otd(db: Session, game_format: str = "core", perimeter: str | None = None, days: int = 7):
    """OTP (on-the-play) vs OTD (on-the-draw) win rates per deck.

    In the match DB, deck_a is always player 1 (first to play = OTP).
    So deck_a wins as OTP = winner='deck_a', and deck_b wins as OTD = winner='deck_b'.
    """
    params = {"fmt": game_format, "days": days}
    where_perim = ""
    if perimeter:
        where_perim = "AND perimeter = :perim"
        params["perim"] = perimeter

    rows = db.execute(text(f"""
        SELECT deck_a, deck_b,
               COUNT(*) AS games,
               COUNT(*) FILTER (WHERE winner = 'deck_a') AS otp_wins,
               COUNT(*) FILTER (WHERE winner = 'deck_b') AS otd_wins
        FROM matches
        WHERE game_format = :fmt
          AND played_at >= now() - make_interval(days => :days)
          {where_perim}
        GROUP BY deck_a, deck_b
    """), params).fetchall()

    result = {}
    for r in rows:
        if r.deck_a not in result:
            result[r.deck_a] = {}
        result[r.deck_a][r.deck_b] = {
            "games": r.games,
            "otp_wins": r.otp_wins,
            "otd_wins": r.otd_wins,
            "otp_wr": round(r.otp_wins / r.games * 100, 1) if r.games else 0,
            "otd_wr": round(r.otd_wins / r.games * 100, 1) if r.games else 0,
        }
    return result


def get_trend(db: Session, game_format: str = "core", days: int = 5):
    """Daily win rate trend per deck over last N days."""
    rows = db.execute(text("""
        SELECT played_at::date AS day, deck_a AS deck,
               COUNT(*) AS games,
               COUNT(*) FILTER (WHERE winner = 'deck_a') AS wins
        FROM matches
        WHERE game_format = :fmt
          AND played_at >= now() - make_interval(days => :days)
        GROUP BY played_at::date, deck_a
        ORDER BY day, deck_a
    """), {"fmt": game_format, "days": days}).fetchall()

    trend = {}
    for r in rows:
        day_str = r.day.isoformat()
        if day_str not in trend:
            trend[day_str] = {}
        trend[day_str][r.deck] = {
            "games": r.games,
            "wins": r.wins,
            "wr": round(r.wins / r.games * 100, 1) if r.games else 0,
        }
    return trend
