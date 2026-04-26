"""User profile — profile, nicknames, decks, preferences, GDPR export.
Requires: logged in (any tier).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.deps import get_current_user, get_db
from backend.models.user import User
from backend.services import user_service

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────

class UpdateProfileRequest(BaseModel):
    display_name: str | None = Field(None, max_length=100)


class UpdateNicknamesRequest(BaseModel):
    duels_ink: str | None = Field(None, max_length=100)
    lorcanito: str | None = Field(None, max_length=100)


class UpdatePreferencesRequest(BaseModel):
    language: str | None = None
    default_deck: str | None = None
    default_format: str | None = None
    notifications_email: bool | None = None
    notifications_push: bool | None = None
    theme: str | None = None
    country: str | None = None


class CreateDeckRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    deck_code: str = Field(min_length=2, max_length=10)
    cards: dict | list = Field(default_factory=dict)


class UpdateDeckRequest(BaseModel):
    name: str | None = Field(None, max_length=100)
    deck_code: str | None = Field(None, max_length=10)
    cards: dict | list | None = None


class InterestRequest(BaseModel):
    """Soft paywall / waitlist intent — user clicks "Unlock Pro" / "Unlock Coach"
    before we have Stripe/Paddle live. See ARCHITECTURE.md §24.8."""
    # B.7.0 — `team` removed from the new-signup interest pattern: existing
    # paganti keep tier='team' (aliased to coach capability via TIER_LEVEL),
    # but no fresh signup picks `team` going forward.
    tier: str = Field(..., pattern="^(pro|coach)$")


class ConsentRequest(BaseModel):
    """Record a consent acceptance. See ARCHITECTURE.md §24.3.2."""
    kind: str = Field(..., pattern="^(tos|privacy|replay_upload|marketing)$")
    version: str = Field(..., min_length=1, max_length=10)


# ── Profile ──────────────────────────────────────────────────────────

@router.get("/profile")
def get_profile(user: User = Depends(get_current_user)):
    """Full user profile."""
    return user_service.get_profile(user)


@router.put("/profile")
def update_profile(
    body: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update profile fields (display_name)."""
    return user_service.update_profile(db, user, display_name=body.display_name)


# ── Nicknames ────────────────────────────────────────────────────────

@router.get("/nicknames")
def get_nicknames(user: User = Depends(get_current_user)):
    """Get linked gaming nicknames."""
    return user_service.get_nicknames(user)


@router.put("/nicknames")
def update_nicknames(
    body: UpdateNicknamesRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Link duels.ink / lorcanito nicknames."""
    return user_service.update_nicknames(db, user, duels_ink=body.duels_ink, lorcanito=body.lorcanito)


# ── Preferences ──────────────────────────────────────────────────────

@router.get("/preferences")
def get_preferences(user: User = Depends(get_current_user)):
    """Get user preferences."""
    return user_service.get_preferences(user)


@router.put("/preferences")
def update_preferences(
    body: UpdatePreferencesRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update user preferences (language, default deck, notifications, theme)."""
    updates = body.model_dump(exclude_none=True)
    return user_service.update_preferences(db, user, updates)


# ── Decks ────────────────────────────────────────────────────────────

@router.get("/decks")
def list_decks(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all saved decks."""
    return user_service.list_decks(db, user.id)


@router.post("/decks", status_code=201)
def create_deck(
    body: CreateDeckRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save a new deck."""
    try:
        return user_service.create_deck(db, user.id, body.name, body.deck_code, body.cards)
    except ValueError as e:
        detail = str(e)
        code = 400
        if detail == "max_decks_reached":
            code = 409
        raise HTTPException(status_code=code, detail=detail)


@router.put("/decks/{deck_id}")
def update_deck(
    deck_id: uuid.UUID,
    body: UpdateDeckRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an existing deck."""
    try:
        return user_service.update_deck(
            db, user.id, deck_id,
            name=body.name, deck_code=body.deck_code, cards=body.cards,
        )
    except ValueError as e:
        detail = str(e)
        code = 404 if detail == "deck_not_found" else 400
        raise HTTPException(status_code=code, detail=detail)


@router.delete("/decks/{deck_id}", status_code=204)
def delete_deck(
    deck_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a saved deck (soft-delete)."""
    try:
        user_service.delete_deck(db, user.id, deck_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="deck_not_found")


# ── My Stats ─────────────────────────────────────────────────────────

@router.get("/my-stats")
def my_stats(
    game_format: str = Query("core"),
    days: int = Query(30, ge=1, le=90),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Personal stats based on duels.ink nickname: WR per deck, matchups, trend."""
    result = user_service.get_my_stats(db, user, game_format, days)
    if not result:
        raise HTTPException(404, "Set your duels.ink nickname first")
    return result


# ── GDPR Export ──────────────────────────────────────────────────────

@router.get("/export")
def export_data(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GDPR: export all user data as JSON."""
    return user_service.export_user_data(db, user)


# ── Consents ─────────────────────────────────────────────────────────

@router.post("/consent")
def register_consent(
    payload: ConsentRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record a consent acceptance.

    B.3 dual-write: the canonical audit trail lives in ``user_consents``
    (append-only, includes ip/user_agent for legal forensics). The
    ``users.preferences.consents.<kind>`` JSONB cache is kept in sync as a
    fast-read pointer to "latest acceptance per kind" for UI checks.

    See ARCHITECTURE.md §24.3.2.
    """
    from sqlalchemy.orm.attributes import flag_modified

    # 1) Append-only history row
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    row = user_service.record_consent(
        db, user, kind=payload.kind, version=payload.version, ip=ip, user_agent=ua
    )

    # 2) JSONB cache (latest-per-kind) — kept for backward compat with code
    #    paths that read preferences.consents.<kind> without DB hit.
    prefs = dict(user.preferences or {})
    consents = dict(prefs.get("consents", {}))
    consents[payload.kind] = {
        "version": payload.version,
        "accepted_at": row.accepted_at.isoformat() if row.accepted_at else None,
    }
    prefs["consents"] = consents
    user.preferences = prefs
    flag_modified(user, "preferences")
    db.commit()

    return {
        "ok": True,
        "kind": payload.kind,
        "version": payload.version,
        "accepted_at": consents[payload.kind]["accepted_at"],
    }


@router.get("/consents")
def list_consents(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the latest accepted consent per kind, sourced from the
    ``user_consents`` table (audit-grade, not the JSONB cache).
    """
    return {"latest": user_service.get_latest_consents(db, user)}


# ── Soft paywall / waitlist (pre-monetization) ───────────────────────

@router.post("/interest")
def register_interest(
    payload: InterestRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record user intent to upgrade tier, before Stripe/Paddle is live.

    See ARCHITECTURE.md §24.8 (Fake Paywall / Waitlist).

    Writes to users.preferences.interest_to_pay = { tier, at }.
    Overwrites on each call (only the most recent intent is kept).
    Use this to size demand before enabling real billing.
    """
    from datetime import datetime, timezone

    prefs = dict(user.preferences or {})
    prefs["interest_to_pay"] = {
        "tier": payload.tier,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    user.preferences = prefs
    # Mark the JSONB column as modified so SQLAlchemy flushes the change.
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(user, "preferences")
    db.commit()
    return {"ok": True, "tier": payload.tier}
