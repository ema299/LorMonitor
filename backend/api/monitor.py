"""Monitor tab — meta game overview, matchup matrix, leaderboard.
Requires: logged in (any tier). Free users see all monitor data.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.deps import get_current_user, get_db
from backend.models.user import User
from backend.services import stats_service, players_service, dashboard_bridge

router = APIRouter()


@router.get("/meta")
def meta_share(
    game_format: str = Query("core"),
    days: int = Query(2, ge=1, le=30),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Meta game share: deck popularity and win rates."""
    return stats_service.get_meta_share(db, game_format, days)


@router.get("/deck/{deck_code}")
def deck_breakdown(
    deck_code: str,
    game_format: str = Query("core"),
    days: int = Query(7, ge=1, le=30),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Single deck breakdown: WR vs each opponent."""
    from backend.services import deck_service
    return deck_service.get_deck_breakdown(db, deck_code, game_format, days)


@router.get("/matchup-matrix")
def matchup_matrix(
    game_format: str = Query("core"),
    perimeter: str | None = Query(None),
    days: int = Query(7, ge=1, le=30),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Full matchup matrix (all deck pairs)."""
    return stats_service.get_matchup_matrix(db, game_format, perimeter, days)


@router.get("/otp-otd")
def otp_otd(
    game_format: str = Query("core"),
    perimeter: str | None = Query(None),
    days: int = Query(7, ge=1, le=30),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """OTP vs OTD win rates per matchup."""
    return stats_service.get_otp_otd(db, game_format, perimeter, days)


@router.get("/trend")
def trend(
    game_format: str = Query("core"),
    days: int = Query(5, ge=1, le=30),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Daily win rate trend per deck."""
    return stats_service.get_trend(db, game_format, days)


@router.get("/leaderboard")
def leaderboard(
    game_format: str = Query("core"),
    days: int = Query(7, ge=1, le=30),
    limit: int = Query(100, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Player leaderboard ranked by MMR."""
    return players_service.get_leaderboard(db, game_format, days, limit)


@router.get("/players/{deck_code}")
def top_players_by_deck(
    deck_code: str,
    game_format: str = Query("core"),
    days: int = Query(7, ge=1, le=30),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Top players for a specific deck."""
    results = players_service.get_top_players(db, game_format, days)
    return [p for p in results if p["deck"] == deck_code]


@router.get("/winrates")
def winrates(
    game_format: str = Query("core"),
    perimeter: str | None = Query(None),
    days: int = Query(2, ge=1, le=30),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Win rates per deck."""
    return stats_service.get_deck_winrates(db, game_format, perimeter, days)


@router.get("/tech-tornado")
def tech_tornado(
    perimeter: str = Query("set11"),
    deck: str | None = Query(None, description="Filter to a single deck"),
    game_format: str = Query("core"),
    days: int = Query(2),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Tech tornado: cards in/out vs consensus for a perimeter. Data from PostgreSQL."""
    from backend.services import tech_service
    result = tech_service.get_tech_tornado(db, perimeter, deck, game_format, days)
    if not result:
        # Fallback to dashboard bridge
        result = dashboard_bridge.get_tech_tornado(perimeter, deck)
    if not result:
        raise HTTPException(404, f"No tech tornado data for perimeter={perimeter}")
    return result
