"""
User service — profile, nicknames, decks, preferences, GDPR export.
All user data lives in PostgreSQL (users table + user_decks table).
"""
import uuid
from datetime import datetime

from sqlalchemy import and_
from sqlalchemy.orm import Session

from backend.models.user import User
from backend.models.user_deck import UserDeck


# ── Profile ──────────────────────────────────────────────────────────

def get_profile(user: User) -> dict:
    """Full user profile including preferences."""
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "tier": user.tier,
        "is_admin": user.is_admin,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "preferences": user.preferences or {},
    }


def update_profile(db: Session, user: User, display_name: str | None = None) -> dict:
    """Update mutable profile fields."""
    if display_name is not None:
        user.display_name = display_name.strip()[:100] if display_name else None
    db.commit()
    db.refresh(user)
    return get_profile(user)


# ── Nicknames ────────────────────────────────────────────────────────

def get_nicknames(user: User) -> dict:
    """Get linked gaming nicknames from preferences JSONB."""
    prefs = user.preferences or {}
    return {
        "duels_ink": prefs.get("nickname_duels_ink", ""),
        "lorcanito": prefs.get("nickname_lorcanito", ""),
    }


def update_nicknames(db: Session, user: User, duels_ink: str | None = None,
                     lorcanito: str | None = None) -> dict:
    """Link gaming platform nicknames to user profile."""
    prefs = dict(user.preferences or {})
    if duels_ink is not None:
        prefs["nickname_duels_ink"] = duels_ink.strip()[:100]
    if lorcanito is not None:
        prefs["nickname_lorcanito"] = lorcanito.strip()[:100]
    user.preferences = prefs
    db.commit()
    db.refresh(user)
    return get_nicknames(user)


# ── Preferences ──────────────────────────────────────────────────────

ALLOWED_PREFS = {
    "language", "default_deck", "default_format", "notifications_email",
    "notifications_push", "theme",
}


def get_preferences(user: User) -> dict:
    """Get user preferences (filtered to known keys)."""
    prefs = user.preferences or {}
    return {k: prefs.get(k) for k in ALLOWED_PREFS if k in prefs}


def update_preferences(db: Session, user: User, updates: dict) -> dict:
    """Merge preference updates (only allowed keys)."""
    prefs = dict(user.preferences or {})
    for k, v in updates.items():
        if k in ALLOWED_PREFS:
            prefs[k] = v
    user.preferences = prefs
    db.commit()
    db.refresh(user)
    return get_preferences(user)


# ── Decks ────────────────────────────────────────────────────────────

MAX_DECKS_PER_USER = 20

VALID_DECK_CODES = {
    "AmAm", "AS", "ES", "AbE", "AbS", "AbR", "AbSt", "AmySt",
    "SSt", "AmyE", "AmyR", "RS", "ERu", "RSt", "ESt",
}


def list_decks(db: Session, user_id: uuid.UUID) -> list[dict]:
    """List all active decks for a user."""
    decks = (
        db.query(UserDeck)
        .filter(UserDeck.user_id == user_id, UserDeck.is_active == True)
        .order_by(UserDeck.created_at.desc())
        .all()
    )
    return [_deck_to_dict(d) for d in decks]


def create_deck(db: Session, user_id: uuid.UUID, name: str, deck_code: str,
                cards: list[dict]) -> dict:
    """Create a new saved deck."""
    count = (
        db.query(UserDeck)
        .filter(UserDeck.user_id == user_id, UserDeck.is_active == True)
        .count()
    )
    if count >= MAX_DECKS_PER_USER:
        raise ValueError("max_decks_reached")

    if deck_code not in VALID_DECK_CODES:
        raise ValueError("invalid_deck_code")

    _validate_cards(cards)

    deck = UserDeck(
        user_id=user_id,
        name=name.strip()[:100],
        deck_code=deck_code,
        cards=cards,
    )
    db.add(deck)
    db.commit()
    db.refresh(deck)
    return _deck_to_dict(deck)


def update_deck(db: Session, user_id: uuid.UUID, deck_id: uuid.UUID,
                name: str | None = None, deck_code: str | None = None,
                cards: list[dict] | None = None) -> dict:
    """Update an existing deck."""
    deck = _get_user_deck(db, user_id, deck_id)

    if name is not None:
        deck.name = name.strip()[:100]
    if deck_code is not None:
        if deck_code not in VALID_DECK_CODES:
            raise ValueError("invalid_deck_code")
        deck.deck_code = deck_code
    if cards is not None:
        _validate_cards(cards)
        deck.cards = cards

    db.commit()
    db.refresh(deck)
    return _deck_to_dict(deck)


def delete_deck(db: Session, user_id: uuid.UUID, deck_id: uuid.UUID) -> None:
    """Soft-delete a deck."""
    deck = _get_user_deck(db, user_id, deck_id)
    deck.is_active = False
    db.commit()


# ── GDPR Export ──────────────────────────────────────────────────────

def export_user_data(db: Session, user: User) -> dict:
    """Export all user data for GDPR compliance."""
    decks = list_decks(db, user.id)
    return {
        "profile": get_profile(user),
        "nicknames": get_nicknames(user),
        "preferences": get_preferences(user),
        "decks": decks,
        "exported_at": datetime.utcnow().isoformat(),
    }


# ── Helpers ──────────────────────────────────────────────────────────

def _get_user_deck(db: Session, user_id: uuid.UUID, deck_id: uuid.UUID) -> UserDeck:
    """Fetch a deck ensuring it belongs to the user."""
    deck = (
        db.query(UserDeck)
        .filter(
            UserDeck.id == deck_id,
            UserDeck.user_id == user_id,
            UserDeck.is_active == True,
        )
        .first()
    )
    if not deck:
        raise ValueError("deck_not_found")
    return deck


def _deck_to_dict(deck: UserDeck) -> dict:
    return {
        "id": str(deck.id),
        "name": deck.name,
        "deck_code": deck.deck_code,
        "cards": deck.cards,
        "created_at": deck.created_at.isoformat() if deck.created_at else None,
        "updated_at": deck.updated_at.isoformat() if deck.updated_at else None,
    }


def _validate_cards(cards: list[dict]) -> None:
    """Basic structural validation for card list."""
    if not isinstance(cards, list):
        raise ValueError("invalid_cards_format")
    if len(cards) > 60:
        raise ValueError("too_many_cards")
    total = 0
    for c in cards:
        if not isinstance(c, dict) or "card_name" not in c:
            raise ValueError("invalid_card_entry")
        count = c.get("count", 1)
        if not isinstance(count, int) or count < 1 or count > 4:
            raise ValueError("invalid_card_count")
        total += count
    if total > 60:
        raise ValueError("deck_exceeds_60_cards")
