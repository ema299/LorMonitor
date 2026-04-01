"""Lab tab — card scores, optimizer, mulligans, deck analytics.
Requires: pro tier or above.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.deps import get_db, require_tier
from backend.models.user import User
from backend.services import deck_service, dashboard_bridge

router = APIRouter()


@router.get("/card-scores/{our_deck}/{opp_deck}")
def card_scores(
    our_deck: str,
    opp_deck: str,
    game_format: str = Query("core"),
    days: int = Query(7, ge=1, le=30),
    user: User = Depends(require_tier("pro")),
    db: Session = Depends(get_db),
):
    """Card-level win rate contribution for a matchup."""
    return deck_service.get_card_scores(db, our_deck, opp_deck, game_format, days)


@router.get("/history")
def history_snapshots(
    perimeter: str = Query("full"),
    days: int = Query(30, ge=1, le=90),
    user: User = Depends(require_tier("pro")),
    db: Session = Depends(get_db),
):
    """Historical daily snapshots."""
    return deck_service.get_history_snapshots(db, perimeter, days)


@router.get("/optimizer/{our_deck}/{opp_deck}")
def optimizer(
    our_deck: str,
    opp_deck: str,
    game_format: str = Query("core"),
    user: User = Depends(require_tier("pro")),
):
    """Optimized decklist for a matchup: full list, adds, cuts, mana curve."""
    result = dashboard_bridge.get_optimizer(our_deck, opp_deck, game_format)
    if not result:
        raise HTTPException(404, f"No optimizer data for {our_deck} vs {opp_deck}")
    return result


@router.get("/mulligans/{our_deck}/{opp_deck}")
def mulligans(
    our_deck: str,
    opp_deck: str,
    game_format: str = Query("core"),
    user: User = Depends(require_tier("pro")),
):
    """PRO mulligan hands: initial, sent, final, outcome, OTP/OTD."""
    result = dashboard_bridge.get_mulligans(our_deck, opp_deck, game_format)
    if not result:
        raise HTTPException(404, f"No mulligan data for {our_deck} vs {opp_deck}")
    return result
