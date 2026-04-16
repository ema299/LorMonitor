"""Monitor tab — meta game overview, matchup matrix, leaderboard.
Requires: logged in (any tier). Free users see all monitor data.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.deps import get_current_user, get_db, require_admin
from backend.models.user import User
from backend.services import stats_service, players_service, rogue_scout_service

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


@router.get("/deck-fitness")
def deck_fitness(
    game_format: str = Query("core"),
    perimeter: str | None = Query(None),
    days: int = Query(7, ge=1, le=30),
    min_games_per_matchup: int = Query(15, ge=5, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deck Fitness Score (0-100): meta-weighted winrate per deck.

    fitness(D) = Σ (wr[D vs X] × share[X]) / Σ share[X]
    Ranks all decks. 50 = meta break-even.
    """
    return stats_service.get_deck_fitness(
        db,
        game_format=game_format,
        perimeter=perimeter,
        days=days,
        min_games_per_matchup=min_games_per_matchup,
    )


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
        raise HTTPException(404, f"No tech tornado data for perimeter={perimeter}")
    return result


@router.get("/rogue-scout-preview")
def rogue_scout_preview(
    game_format: str = Query("core"),
    days: int = Query(7, ge=1, le=30),
    min_games: int = Query(10, ge=3, le=100),
    min_wr: float = Query(0.55, ge=0.0, le=1.0),
    min_mmr: int = Query(1400, ge=0, le=4000),
    min_jaccard: float = Query(0.40, ge=0.0, le=1.0),
    tier0_count: int = Query(3, ge=1, le=10),
    tier0_perimeter: str = Query("set11"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin/debug PG-first preview of rogue / emerging deck candidates."""
    cfg = rogue_scout_service.RogueScoutConfig(
        game_format=game_format,
        days=days,
        min_games=min_games,
        min_wr=min_wr,
        min_mmr=min_mmr,
        min_jaccard=min_jaccard,
        tier0_count=tier0_count,
        tier0_perimeter=tier0_perimeter,
    )
    return rogue_scout_service.get_candidate_preview(db, cfg)
