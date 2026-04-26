"""
User service — profile, nicknames, decks, preferences, GDPR export, my-stats.
All user data lives in PostgreSQL (users table + user_decks table).
"""
import uuid
from datetime import datetime

from sqlalchemy import and_, text
from sqlalchemy.orm import Session

from backend.models.consent import UserConsent
from backend.models.team import ReplaySessionNote, TeamReplay
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
    "notifications_push", "theme", "country",
    # Privacy layer V3 — read-only in the export pipeline. Writes go through
    # the dedicated /api/v1/user/consent and /api/v1/user/interest endpoints,
    # not through PUT /api/v1/user/preferences (update_preferences still
    # funnels through this set, so these keys remain accepted there too —
    # but the UI never writes them via the generic preferences PUT).
    "consents", "interest_to_pay",
    # B.7.0 — Coach Workspace tab Team layered rendering. Values: 'player'
    # (lighter pro view) | 'coach' (full workspace, only effective when
    # user.tier == 'coach' or alias 'team'). Default UI fallback handled in
    # frontend; backend just whitelists the key here.
    "team_view_mode",
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
    """Export all user data for GDPR compliance.

    Covers: profile, nicknames, preferences (including consents / waitlist /
    interest_to_pay), saved decks, and Board Lab replay uploads owned by
    this user. See ARCHITECTURE.md §24.9.
    """
    decks = list_decks(db, user.id)

    # Privacy §24.9: include all replays owned by this user (team_replays
    # with user_id = user.id). Replays shared with this user but owned by
    # others are intentionally excluded — they belong to the owner's export.
    replays = db.query(TeamReplay).filter(TeamReplay.user_id == user.id).all()
    replays_out = [
        {
            "id": str(r.id),
            "game_id": r.game_id,
            "player_name": r.player_name,
            "opponent_name": r.opponent_name,
            "perspective": r.perspective,
            "winner": r.winner,
            "victory_reason": r.victory_reason,
            "turn_count": r.turn_count,
            "is_private": r.is_private,
            "consent_version": r.consent_version,
            "uploaded_via": r.uploaded_via,
            "shared_with": r.shared_with or [],
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "replay_data": r.replay_data,  # full parsed payload
        }
        for r in replays
    ]

    # B.2 — Session notes are private to user_id, exported per GDPR right of
    # access. Joined with team_replays.game_id for cross-reference.
    note_rows = (
        db.query(ReplaySessionNote, TeamReplay.game_id)
        .join(TeamReplay, TeamReplay.id == ReplaySessionNote.replay_id)
        .filter(ReplaySessionNote.user_id == user.id)
        .all()
    )
    notes_out = [
        {
            "id": str(n.id),
            "replay_id": str(n.replay_id),
            "game_id": gid,
            "body": n.body,
            "body_length_chars": n.body_length_chars,
            "created_at": n.created_at.isoformat() if n.created_at else None,
            "updated_at": n.updated_at.isoformat() if n.updated_at else None,
        }
        for n, gid in note_rows
    ]

    # B.3 — Append-only consent history (all acceptances, oldest first).
    # The JSONB cache `preferences.consents.<kind>` already exposes the latest
    # acceptance per kind; this list adds the audit trail.
    consent_rows = (
        db.query(UserConsent)
        .filter(UserConsent.user_id == user.id)
        .order_by(UserConsent.accepted_at.asc())
        .all()
    )
    consents_out = [
        {
            "id": str(c.id),
            "kind": c.kind,
            "version": c.version,
            "accepted_at": c.accepted_at.isoformat() if c.accepted_at else None,
            "ip": c.ip,
            "user_agent": c.user_agent,
        }
        for c in consent_rows
    ]

    return {
        "profile": get_profile(user),
        "nicknames": get_nicknames(user),
        "preferences": get_preferences(user),
        "decks": decks,
        "team_replays": replays_out,
        "replay_session_notes": notes_out,
        "user_consents": consents_out,
        "exported_at": datetime.utcnow().isoformat(),
    }


# ── Consents (B.3 — append-only audit trail) ────────────────────────

def record_consent(
    db: Session,
    user: User,
    kind: str,
    version: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> UserConsent:
    """Append a consent acceptance to user_consents. The JSONB cache is
    updated separately by the API endpoint to keep that responsibility
    explicit. Truncates user_agent at 500 chars defensively.
    """
    row = UserConsent(
        user_id=user.id,
        kind=kind[:40],
        version=version[:20],
        ip=ip[:45] if ip else None,
        user_agent=user_agent[:500] if user_agent else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_latest_consents(db: Session, user: User) -> dict:
    """Return latest acceptance per kind from user_consents table.
    Returns ``{kind: {version, accepted_at}}`` — same shape as the JSONB
    cache, sourced from the table for audit-grade reads.
    """
    rows = (
        db.query(UserConsent)
        .filter(UserConsent.user_id == user.id)
        .order_by(UserConsent.kind, UserConsent.accepted_at.desc())
        .all()
    )
    latest: dict[str, dict] = {}
    for r in rows:
        if r.kind not in latest:
            latest[r.kind] = {
                "version": r.version,
                "accepted_at": r.accepted_at.isoformat() if r.accepted_at else None,
            }
    return latest


# ── My Stats ─────────────────────────────────────────────────────────

def get_my_stats(db: Session, user: User, game_format: str = "core", days: int = 30) -> dict | None:
    """Get personal stats by looking up user's duels.ink nickname in matches."""
    prefs = user.preferences or {}
    nick = prefs.get("nickname_duels_ink", "")
    if not nick:
        return None

    nick_lower = nick.lower()

    # WR per deck played
    deck_rows = db.execute(text("""
        SELECT
          CASE WHEN lower(player_a_name) = :nick THEN deck_a ELSE deck_b END AS my_deck,
          COUNT(*) AS games,
          SUM(CASE
            WHEN lower(player_a_name) = :nick AND winner = 'deck_a' THEN 1
            WHEN lower(player_b_name) = :nick AND winner = 'deck_b' THEN 1
            ELSE 0
          END) AS wins
        FROM matches
        WHERE (lower(player_a_name) = :nick OR lower(player_b_name) = :nick)
          AND played_at >= now() - make_interval(days => :days)
          AND game_format = :fmt
        GROUP BY my_deck
        ORDER BY games DESC
    """), {"nick": nick_lower, "days": days, "fmt": game_format}).fetchall()

    if not deck_rows:
        return {"nick": nick, "decks": [], "total_games": 0, "total_wins": 0, "total_wr": 0}

    decks = []
    total_g = 0
    total_w = 0
    for r in deck_rows:
        g, w = r.games, r.wins
        total_g += g
        total_w += w
        decks.append({
            "deck": r.my_deck,
            "games": g,
            "wins": w,
            "losses": g - w,
            "wr": round(w / g * 100, 1) if g else 0,
        })

    # Matchup breakdown for top deck
    matchups = []
    if decks:
        top_deck = decks[0]["deck"]
        mu_rows = db.execute(text("""
            SELECT
              CASE WHEN lower(player_a_name) = :nick THEN deck_b ELSE deck_a END AS vs_deck,
              COUNT(*) AS games,
              SUM(CASE
                WHEN lower(player_a_name) = :nick AND winner = 'deck_a' THEN 1
                WHEN lower(player_b_name) = :nick AND winner = 'deck_b' THEN 1
                ELSE 0
              END) AS wins
            FROM matches
            WHERE (lower(player_a_name) = :nick OR lower(player_b_name) = :nick)
              AND CASE WHEN lower(player_a_name) = :nick THEN deck_a ELSE deck_b END = :my_deck
              AND played_at >= now() - make_interval(days => :days)
              AND game_format = :fmt
            GROUP BY vs_deck
            ORDER BY games DESC
        """), {"nick": nick_lower, "my_deck": top_deck, "days": days, "fmt": game_format}).fetchall()

        matchups = [
            {"vs_deck": r.vs_deck, "games": r.games, "wins": r.wins,
             "wr": round(r.wins / r.games * 100, 1) if r.games else 0}
            for r in mu_rows
        ]

    # Daily trend (last 30 days)
    trend_rows = db.execute(text("""
        SELECT
          played_at::date AS day,
          COUNT(*) AS games,
          SUM(CASE
            WHEN lower(player_a_name) = :nick AND winner = 'deck_a' THEN 1
            WHEN lower(player_b_name) = :nick AND winner = 'deck_b' THEN 1
            ELSE 0
          END) AS wins
        FROM matches
        WHERE (lower(player_a_name) = :nick OR lower(player_b_name) = :nick)
          AND played_at >= now() - make_interval(days => :days)
          AND game_format = :fmt
        GROUP BY day
        ORDER BY day
    """), {"nick": nick_lower, "days": days, "fmt": game_format}).fetchall()

    daily_trend = [
        {"day": r.day.isoformat(), "games": r.games, "wins": r.wins,
         "wr": round(r.wins / r.games * 100, 1) if r.games else 0}
        for r in trend_rows
    ]

    return {
        "nick": nick,
        "total_games": total_g,
        "total_wins": total_w,
        "total_wr": round(total_w / total_g * 100, 1) if total_g else 0,
        "decks": decks,
        "matchups": matchups,
        "daily_trend": daily_trend,
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


def _validate_cards(cards) -> None:
    """Basic structural validation for card list or dict.
    Accepts:
      - dict: {"Card Name": qty, ...}  (frontend format)
      - list: [{"card_name": "x", "count": 2}, ...]  (API format)
      - empty dict/list (deck senza carte, bozza)
    """
    if isinstance(cards, dict):
        total = 0
        for name, qty in cards.items():
            if not isinstance(name, str) or not isinstance(qty, int) or qty < 1 or qty > 4:
                raise ValueError("invalid_card_entry")
            total += qty
        if total > 60:
            raise ValueError("deck_exceeds_60_cards")
    elif isinstance(cards, list):
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
    else:
        raise ValueError("invalid_cards_format")
