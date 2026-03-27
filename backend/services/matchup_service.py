"""
Matchup service — killer curves, threats, matchup details.
Serves pre-existing LLM data from DB (no API calls).
"""
from sqlalchemy import text
from sqlalchemy.orm import Session


def get_matchup_detail(db: Session, our_deck: str, opp_deck: str,
                       game_format: str = "core", days: int = 7):
    """Detailed matchup stats for our_deck vs opp_deck."""
    row = db.execute(text("""
        SELECT COUNT(*) AS games,
               COUNT(*) FILTER (WHERE winner = 'deck_a') AS wins,
               COUNT(*) FILTER (WHERE winner = 'deck_b') AS losses,
               ROUND(AVG(total_turns), 1) AS avg_turns,
               ROUND(AVG(lore_a_final), 1) AS avg_lore_a,
               ROUND(AVG(lore_b_final), 1) AS avg_lore_b,
               COUNT(*) FILTER (WHERE winner = 'deck_a' AND total_turns <= 6) AS fast_wins,
               COUNT(*) FILTER (WHERE winner = 'deck_b' AND total_turns <= 6) AS fast_losses
        FROM matches
        WHERE game_format = :fmt
          AND deck_a = :our AND deck_b = :opp
          AND played_at >= now() - make_interval(days => :days)
    """), {"fmt": game_format, "our": our_deck, "opp": opp_deck, "days": days}).fetchone()

    if not row or row.games == 0:
        return None

    return {
        "our_deck": our_deck,
        "opp_deck": opp_deck,
        "games": row.games,
        "wins": row.wins,
        "losses": row.losses,
        "wr": round(row.wins / row.games * 100, 1),
        "avg_turns": float(row.avg_turns) if row.avg_turns else 0,
        "avg_lore_a": float(row.avg_lore_a) if row.avg_lore_a else 0,
        "avg_lore_b": float(row.avg_lore_b) if row.avg_lore_b else 0,
        "fast_wins": row.fast_wins,
        "fast_losses": row.fast_losses,
    }


def get_killer_curves(db: Session, our_deck: str, opp_deck: str, game_format: str = "core"):
    """Get current killer curves for a matchup (pre-generated LLM data)."""
    row = db.execute(text("""
        SELECT curves, match_count, loss_count, generated_at
        FROM killer_curves
        WHERE game_format = :fmt
          AND our_deck = :our AND opp_deck = :opp
          AND is_current = true
        ORDER BY generated_at DESC
        LIMIT 1
    """), {"fmt": game_format, "our": our_deck, "opp": opp_deck}).fetchone()

    if not row:
        return None

    return {
        "our_deck": our_deck,
        "opp_deck": opp_deck,
        "curves": row.curves,
        "match_count": row.match_count,
        "loss_count": row.loss_count,
        "generated_at": row.generated_at.isoformat(),
    }


def get_threats(db: Session, our_deck: str, opp_deck: str, game_format: str = "core"):
    """Get current threat analysis (pre-generated LLM data)."""
    row = db.execute(text("""
        SELECT threats, generated_at
        FROM threats_llm
        WHERE game_format = :fmt
          AND our_deck = :our AND opp_deck = :opp
          AND is_current = true
        ORDER BY generated_at DESC
        LIMIT 1
    """), {"fmt": game_format, "our": our_deck, "opp": opp_deck}).fetchone()

    if not row:
        return None

    return {
        "our_deck": our_deck,
        "opp_deck": opp_deck,
        "threats": row.threats,
        "generated_at": row.generated_at.isoformat(),
    }


def get_matchup_history(db: Session, our_deck: str, opp_deck: str,
                        game_format: str = "core", days: int = 30):
    """Daily WR trend for a specific matchup."""
    rows = db.execute(text("""
        SELECT played_at::date AS day,
               COUNT(*) AS games,
               COUNT(*) FILTER (WHERE winner = 'deck_a') AS wins
        FROM matches
        WHERE game_format = :fmt
          AND deck_a = :our AND deck_b = :opp
          AND played_at >= now() - make_interval(days => :days)
        GROUP BY played_at::date
        ORDER BY day
    """), {"fmt": game_format, "our": our_deck, "opp": opp_deck, "days": days}).fetchall()

    return [
        {
            "day": r.day.isoformat(),
            "games": r.games,
            "wins": r.wins,
            "wr": round(r.wins / r.games * 100, 1) if r.games else 0,
        }
        for r in rows
    ]
