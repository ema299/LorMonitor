"""Lab tab — card scores, optimizer, mulligans, deck analytics, deck comparator.
Some endpoints require pro tier, others are public.
"""
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.deps import get_db, require_tier
from backend.models.user import User
from backend.services import deck_service, matchup_service, lab_iwd_service

SNAPSHOT_DIR = Path("/mnt/HC_Volume_104764377/finanza/Lor/decks_db/history")
_LEGACY_NAMES = {"AS": "AmSa", "ES": "EmSa"}

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
    db: Session = Depends(get_db),
):
    """Optimized decklist for a matchup: full list, adds, cuts, mana curve."""
    result = matchup_service.get_optimizer(db, our_deck, opp_deck, game_format)
    if not result:
        raise HTTPException(404, f"No optimizer data for {our_deck} vs {opp_deck}")
    return result


@router.get("/iwd/{our_deck}/{opp_deck}")
def iwd(
    our_deck: str,
    opp_deck: str,
    game_format: str = Query("core"),
    days: int = Query(14, ge=3, le=60),
    db: Session = Depends(get_db),
):
    """Improvement When Drawn: for each top card in our_deck, how WR changes
    when the card is seen in hand by T3 vs when it isn't.

    Returns all cards passing min_drawn/min_not_drawn thresholds, sorted by
    |delta_wr| desc. If total_matches < MIN_TOTAL_MATCHES, returns low_sample=True
    and cards=[].
    """
    return lab_iwd_service.get_iwd(db, our_deck, opp_deck, game_format, days)


@router.get("/mulligans/{our_deck}/{opp_deck}")
def mulligans(
    our_deck: str,
    opp_deck: str,
    game_format: str = Query("core"),
    days: int = Query(7),
    user: User = Depends(require_tier("pro")),
    db: Session = Depends(get_db),
):
    """PRO mulligan hands: initial, sent, final, outcome, OTP/OTD. Data from PostgreSQL."""
    result = deck_service.get_pro_mulligans(db, our_deck, opp_deck, game_format, days)
    if not result:
        raise HTTPException(404, f"No mulligan data for {our_deck} vs {opp_deck}")
    return result


@router.get("/tournament-lists/{deck}")
def tournament_lists(
    deck: str,
    db: Session = Depends(get_db),
):
    """Tournament decklists for a deck archetype (from inkdecks snapshot).

    Returns up to 15 lists with player, rank, event, date, cards.
    Public endpoint — used by the Lab deck comparator.
    """
    # Normalize deck code
    reverse_legacy = {"AmSa": "AS", "EmSa": "ES"}
    snapshot_code = reverse_legacy.get(deck, deck)

    # Find latest non-empty snapshot
    snapshots = sorted(SNAPSHOT_DIR.glob("snapshot_*.json"))
    for candidate in reversed(snapshots):
        try:
            data = json.load(open(candidate))
            archs = data.get("archetypes", {})
            lists = archs.get(snapshot_code, archs.get(deck, []))
            if lists:
                result = []
                for dl in lists:
                    result.append({
                        "player": dl.get("player", ""),
                        "rank": dl.get("rank", ""),
                        "event": dl.get("event", ""),
                        "date": dl.get("date", ""),
                        "record": dl.get("record", ""),
                        "n_players": dl.get("n_players", 0),
                        "cards": dl.get("cards", []),
                    })
                return {"deck": deck, "lists": result, "source": candidate.name}
        except Exception:
            continue

    return {"deck": deck, "lists": [], "source": None}
