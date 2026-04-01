"""Coach tab — matchup analysis, killer curves, threats, playbook.
Requires: pro tier or above.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.deps import get_db, require_tier
from backend.models.user import User
from backend.services import matchup_service, dashboard_bridge

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


@router.get("/playbook/{our_deck}/{opp_deck}")
def playbook(
    our_deck: str,
    opp_deck: str,
    game_format: str = Query("core"),
    user: User = Depends(require_tier("pro")),
):
    """Turn-by-turn opponent playbook (T1-T7): plays, combos, impact."""
    result = dashboard_bridge.get_playbook(our_deck, opp_deck, game_format)
    if not result:
        raise HTTPException(404, f"No playbook for {our_deck} vs {opp_deck}")
    return result
