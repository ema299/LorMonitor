"""Profile tab — endpoints utilizzati dalla pagina Profile.

Per ora ospita solo Blind Deck Playbook (Sprint-1 Liberation Day).
Endpoint pubblici (no require_tier) coerenti con il resto del Profile.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.deps import get_db
from backend.services import playbook_service

router = APIRouter()


@router.get("/blind-playbook/{deck}")
def blind_playbook(
    deck: str,
    game_format: str = Query("core", pattern="^(core|infinity)$"),
    db: Session = Depends(get_db),
):
    """Restituisce il blind playbook (mulligan, target curves, key combos, trap plays)
    per il deck e formato richiesto. 404 se non disponibile (frontend nasconde la sezione).
    """
    pb = playbook_service.get_playbook(db, deck, game_format)
    if not pb:
        raise HTTPException(404, f"No playbook for {deck} ({game_format})")
    return pb


@router.get("/blind-playbook")
def list_playbooks(
    game_format: str = Query("core", pattern="^(core|infinity)$"),
    db: Session = Depends(get_db),
):
    """Lista deck con playbook disponibile per il formato (per debug/admin)."""
    return {"format": game_format, "decks": playbook_service.list_available(db, game_format)}
