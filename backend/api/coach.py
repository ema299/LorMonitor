"""Coach tab — matchup analysis, killer curves, threats, playbook.
Requires: pro tier or above.
"""
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.deps import get_db, require_tier
from backend.models.user import User
from backend.services import matchup_service

router = APIRouter()


@router.get("/matchup/{our_deck}/{opp_deck}")
def matchup_detail(
    our_deck: str,
    opp_deck: str,
    game_format: str = Query("core"),
    days: int = Query(7, ge=1, le=30),
    user: User = Depends(require_tier("pro")),
    db: Session = Depends(get_db),
):
    """Detailed matchup stats (WR, avg turns, lore, fast wins/losses)."""
    result = matchup_service.get_matchup_detail(db, our_deck, opp_deck, game_format, days)
    if not result:
        raise HTTPException(404, f"No data for {our_deck} vs {opp_deck}")
    return result


@router.get("/killer-curves/{our_deck}/{opp_deck}")
def killer_curves(
    our_deck: str,
    opp_deck: str,
    game_format: str = Query("core"),
    user: User = Depends(require_tier("pro")),
    db: Session = Depends(get_db),
):
    """Killer curves: turn-by-turn threat analysis (pre-generated LLM data)."""
    result = matchup_service.get_killer_curves(db, our_deck, opp_deck, game_format)
    if not result:
        raise HTTPException(404, f"No killer curves for {our_deck} vs {opp_deck}")
    return result


@router.get("/threats/{our_deck}/{opp_deck}")
def threats(
    our_deck: str,
    opp_deck: str,
    game_format: str = Query("core"),
    user: User = Depends(require_tier("pro")),
    db: Session = Depends(get_db),
):
    """Threat analysis (pre-generated LLM data)."""
    result = matchup_service.get_threats(db, our_deck, opp_deck, game_format)
    if not result:
        raise HTTPException(404, f"No threat data for {our_deck} vs {opp_deck}")
    return result


@router.get("/history/{our_deck}/{opp_deck}")
def matchup_history(
    our_deck: str,
    opp_deck: str,
    game_format: str = Query("core"),
    days: int = Query(30, ge=1, le=90),
    user: User = Depends(require_tier("pro")),
    db: Session = Depends(get_db),
):
    """Daily WR trend for a specific matchup."""
    return matchup_service.get_matchup_history(db, our_deck, opp_deck, game_format, days)


@router.get("/deck-history/{deck_code}")
def deck_history(
    deck_code: str,
    game_format: str = Query("core"),
    perimeter: str = Query("set11"),
    days: int = Query(5, ge=1, le=30),
    db: Session = Depends(get_db),
):
    """Daily WR trend for a deck over the last N days."""
    rows = db.execute(text("""
        WITH sides AS (
            SELECT played_at::date AS day, deck_a AS deck,
                   CASE WHEN winner = 'deck_a' THEN 1 ELSE 0 END AS win
            FROM matches
            WHERE game_format = :fmt
              AND perimeter = :perim
              AND played_at >= now() - make_interval(days => :days)
            UNION ALL
            SELECT played_at::date AS day, deck_b AS deck,
                   CASE WHEN winner = 'deck_b' THEN 1 ELSE 0 END AS win
            FROM matches
            WHERE game_format = :fmt
              AND perimeter = :perim
              AND played_at >= now() - make_interval(days => :days)
        )
        SELECT day, COUNT(*) AS games, SUM(win)::int AS wins
        FROM sides
        WHERE deck = :deck
        GROUP BY day
        ORDER BY day
    """), {"fmt": game_format, "perim": perimeter, "days": days, "deck": deck_code}).fetchall()

    by_day = {r.day.isoformat(): {"games": r.games, "wins": r.wins, "wr": round(r.wins / r.games * 100, 1) if r.games else None}
              for r in rows}

    end = date.today()
    start = end - timedelta(days=days - 1)
    daily = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        row = by_day.get(day.isoformat())
        if row:
            daily.append({"date": day.isoformat(), **row})
        else:
            daily.append({"date": day.isoformat(), "games": 0, "wins": 0, "wr": None})

    return {
        "deck": deck_code,
        "game_format": game_format,
        "perimeter": perimeter,
        "days": days,
        "daily": daily,
    }


@router.get("/playbook/{our_deck}/{opp_deck}")
def playbook(
    our_deck: str,
    opp_deck: str,
    game_format: str = Query("core"),
    user: User = Depends(require_tier("pro")),
    db: Session = Depends(get_db),
):
    """Turn-by-turn opponent playbook (T1-T7): plays, combos, impact."""
    result = matchup_service.get_playbook(db, our_deck, opp_deck, game_format)
    if not result:
        raise HTTPException(404, f"No playbook for {our_deck} vs {opp_deck}")
    return result
