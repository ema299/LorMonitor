"""Team service — player stats, overview, weaknesses from matches."""
from sqlalchemy import text
from sqlalchemy.orm import Session


def get_player_stats(db: Session, player_name: str, game_format: str = "core", days: int = 30) -> dict:
    """Get WR per deck for a team player."""
    nick = player_name.lower()
    rows = db.execute(text("""
        SELECT
          CASE WHEN lower(player_a_name) = :nick THEN deck_a ELSE deck_b END AS my_deck,
          COUNT(*) AS games,
          SUM(CASE
            WHEN lower(player_a_name) = :nick AND winner = 'deck_a' THEN 1
            WHEN lower(player_b_name) = :nick AND winner = 'deck_b' THEN 1
            ELSE 0
          END) AS wins
        FROM matches
        WHERE (lower(player_a_name) = :nick OR lower(player_b_name) = :nick)
          AND game_format = :fmt
          AND played_at >= now() - make_interval(days => :days)
        GROUP BY my_deck
        ORDER BY games DESC
    """), {"nick": nick, "fmt": game_format, "days": days}).fetchall()

    decks = []
    for r in rows:
        decks.append({
            "deck": r.my_deck,
            "games": r.games,
            "wins": r.wins,
            "wr": round(r.wins / r.games * 100, 1) if r.games > 0 else 0,
        })

    return {"player": player_name, "format": game_format, "days": days, "decks": decks}


def get_team_overview(db: Session, roster_names: list[str], game_format: str = "core", days: int = 30) -> list[dict]:
    """Get overview stats for all roster players."""
    results = []
    for name in roster_names:
        stats = get_player_stats(db, name, game_format, days)
        total_games = sum(d["games"] for d in stats["decks"])
        total_wins = sum(d["wins"] for d in stats["decks"])
        results.append({
            "player": name,
            "games": total_games,
            "wins": total_wins,
            "wr": round(total_wins / total_games * 100, 1) if total_games > 0 else 0,
            "main_deck": stats["decks"][0]["deck"] if stats["decks"] else None,
        })
    return results


def get_team_weaknesses(db: Session, roster_names: list[str], game_format: str = "core", days: int = 30) -> list[dict]:
    """Find worst matchups across the team."""
    weaknesses = []
    for name in roster_names:
        nick = name.lower()
        rows = db.execute(text("""
            SELECT
              CASE WHEN lower(player_a_name) = :nick THEN deck_a ELSE deck_b END AS my_deck,
              CASE WHEN lower(player_a_name) = :nick THEN deck_b ELSE deck_a END AS vs_deck,
              COUNT(*) AS games,
              SUM(CASE
                WHEN lower(player_a_name) = :nick AND winner = 'deck_a' THEN 1
                WHEN lower(player_b_name) = :nick AND winner = 'deck_b' THEN 1
                ELSE 0
              END) AS wins
            FROM matches
            WHERE (lower(player_a_name) = :nick OR lower(player_b_name) = :nick)
              AND game_format = :fmt
              AND played_at >= now() - make_interval(days => :days)
            GROUP BY my_deck, vs_deck
            HAVING COUNT(*) >= 3
            ORDER BY (SUM(CASE
                WHEN lower(player_a_name) = :nick AND winner = 'deck_a' THEN 1
                WHEN lower(player_b_name) = :nick AND winner = 'deck_b' THEN 1
                ELSE 0
              END)::float / COUNT(*)) ASC
            LIMIT 5
        """), {"nick": nick, "fmt": game_format, "days": days}).fetchall()

        for r in rows:
            wr = round(r.wins / r.games * 100, 1) if r.games > 0 else 0
            if wr < 45:
                weaknesses.append({
                    "player": name,
                    "deck": r.my_deck,
                    "vs": r.vs_deck,
                    "games": r.games,
                    "wr": wr,
                })

    weaknesses.sort(key=lambda x: x["wr"])
    return weaknesses[:10]
