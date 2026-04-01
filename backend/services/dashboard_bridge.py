"""
Dashboard bridge — reads pre-computed data from analisidef's dashboard_data.json.

This is the transitional layer: analisidef computes, App_tool serves via API.
When PostgreSQL is fully populated, these functions will be replaced by direct
DB queries without changing the API contracts.
"""
import json
from functools import lru_cache
from pathlib import Path
from time import time

from backend.config import ANALISIDEF_DAILY_DIR

DASHBOARD_JSON = ANALISIDEF_DAILY_DIR / "dashboard_data.json"

# Cache dashboard_data.json for 60 seconds to avoid re-reading on every request
_cache: dict = {"data": None, "ts": 0}
CACHE_TTL = 60


def _load_dashboard_data() -> dict:
    """Load dashboard_data.json with simple TTL cache."""
    now = time()
    if _cache["data"] is not None and (now - _cache["ts"]) < CACHE_TTL:
        return _cache["data"]

    if not DASHBOARD_JSON.exists():
        return {}

    with open(DASHBOARD_JSON) as f:
        data = json.load(f)

    _cache["data"] = data
    _cache["ts"] = now
    return data


def _get_analyzer(data: dict, game_format: str) -> dict:
    """Get the correct analyzer block for the format."""
    if game_format == "infinity":
        return data.get("matchup_analyzer_infinity", {})
    return data.get("matchup_analyzer", {})


def _deck_key(deck_code: str) -> str:
    """Normalize deck code to the key format used in dashboard_data.json."""
    return deck_code


def _matchup_key(opp_code: str) -> str:
    """Build the vs_Opp key used inside analyzer blocks."""
    return f"vs_{opp_code}"


# ── Playbook ─────────────────────────────────────────────────────────

def get_playbook(our_deck: str, opp_deck: str, game_format: str = "core") -> dict | None:
    """Get playbook (turn-by-turn opponent plan) for a matchup.

    Source: dashboard_data.json → analyzer[deck].vs_opp.playbook
    """
    data = _load_dashboard_data()
    analyzer = _get_analyzer(data, game_format)

    deck_data = analyzer.get(_deck_key(our_deck), {})
    matchup_data = deck_data.get(_matchup_key(opp_deck), {})
    playbook = matchup_data.get("playbook")

    if not playbook:
        return None

    return {
        "our_deck": our_deck,
        "opp_deck": opp_deck,
        "playbook": playbook,
    }


# ── Mulligans ────────────────────────────────────────────────────────

def get_mulligans(our_deck: str, opp_deck: str, game_format: str = "core") -> dict | None:
    """Get PRO mulligan hands for a matchup.

    Source: dashboard_data.json → analyzer[deck].vs_opp.pro_mulligans
    Each hand: {player, initial[], sent[], final[], mull, won, otp, game}
    """
    data = _load_dashboard_data()
    analyzer = _get_analyzer(data, game_format)

    deck_data = analyzer.get(_deck_key(our_deck), {})
    matchup_data = deck_data.get(_matchup_key(opp_deck), {})
    mulligans = matchup_data.get("pro_mulligans")

    if not mulligans:
        return None

    return {
        "our_deck": our_deck,
        "opp_deck": opp_deck,
        "hands": mulligans,
        "count": len(mulligans),
    }


# ── Optimizer ────────────────────────────────────────────────────────

def get_optimizer(our_deck: str, opp_deck: str, game_format: str = "core") -> dict | None:
    """Get optimized decklist for a matchup (adds/cuts vs consensus).

    Source: dashboard_data.json → analyzer[deck].vs_opp.decklist
    Structure: {full_list[], cuts[], adds[], mana_curve{}, import_text}
    """
    data = _load_dashboard_data()
    analyzer = _get_analyzer(data, game_format)

    deck_data = analyzer.get(_deck_key(our_deck), {})
    matchup_data = deck_data.get(_matchup_key(opp_deck), {})
    decklist = matchup_data.get("decklist")

    if not decklist:
        return None

    return {
        "our_deck": our_deck,
        "opp_deck": opp_deck,
        "decklist": decklist,
    }


# ── Tech Tornado ─────────────────────────────────────────────────────

def get_tech_tornado(perimeter: str = "set11", deck_code: str | None = None) -> dict | None:
    """Get tech tornado data (cards in/out vs consensus).

    Source: dashboard_data.json → tech_tornado[perimeter][deck]
    Each item: {card, players, adoption, avg_wr, type: "in"|"out"}
    """
    data = _load_dashboard_data()
    tech = data.get("tech_tornado", {})
    perim_data = tech.get(perimeter, {})

    if not perim_data:
        return None

    if deck_code:
        deck_data = perim_data.get(deck_code)
        if not deck_data:
            return None
        return {
            "perimeter": perimeter,
            "deck": deck_code,
            "total_players": deck_data.get("total_players", 0),
            "items": deck_data.get("items", []),
        }

    # Return all decks for this perimeter
    result = {}
    for dk, dv in perim_data.items():
        result[dk] = {
            "total_players": dv.get("total_players", 0),
            "items": dv.get("items", []),
        }
    return {
        "perimeter": perimeter,
        "decks": result,
    }


# ── Admin Logs ───────────────────────────────────────────────────────

LOG_DIR = ANALISIDEF_DAILY_DIR.parent  # analisidef/daily/


def get_recent_logs(level: str = "error", limit: int = 100) -> list[dict]:
    """Read recent structured log entries from audit_log table or log files.

    For now reads from the API log file. Will migrate to audit_log table.
    """
    from sqlalchemy import text
    from backend.models import SessionLocal

    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT id, event_type, user_id, ip_address, details, created_at
            FROM audit_log
            ORDER BY created_at DESC
            LIMIT :lim
        """), {"lim": limit}).fetchall()

        return [
            {
                "id": r.id,
                "event_type": r.event_type,
                "user_id": str(r.user_id) if r.user_id else None,
                "ip_address": str(r.ip_address) if r.ip_address else None,
                "details": r.details,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except Exception:
        return []
    finally:
        db.close()
