"""Deterministic validator for Killer Curves LLM output.

Single source of truth for KC quality gating. Used by:
- ``scripts/generate_killer_curves.py`` (pre-upsert gate)
- ``scripts/audit_killer_curves.py`` (read-only DB audit)
- ``scripts/kc_spy_canary.py`` (daily canary)

Severity:
- P0 (error): blocks publication. ``quality_status='blocked'``.
- P1 (warning): publishable with warning flag. ``quality_status='warn'``.
- P2 (info): observability only, no quality impact.

Returns a structured dict — see ``validate()`` docstring.

Aligned with ``docs/KILLER_CURVES_BLINDATURA_V3.md`` Backlog P0 (riga 740+) and
``killer.md`` 3-tier rule (META | FALLBACK_CORE_LEGAL | DROP).
"""
from __future__ import annotations

import re
from typing import Any

from pipelines.kc.build_prompt import DECK_COLORS
from pipelines.kc.meta_relevance import get_meta_relevant_cards
from pipelines.kc.vendored.cards_api import get_cards_db


VALIDATOR_VERSION = "1.0"

REQUIRED_RESPONSE_V2_FIELDS = (
    "headline",
    "core_rule",
    "priority_actions",
    "what_to_avoid",
    "failure_state",
)

REQUIRED_V3_PAYLOAD_FIELDS = (
    "one_line_hook",
    "mulligan_focus",
    "turn_checklist",
    "coach_badges",
    "user_copy",
)

REQUIRED_SELF_CHECK_FIELDS = (
    "curve_specific",
    "mentions_key_card",
    "response_by_turn",
    "not_generic",
    "uses_only_prompt_cards",
)


def _deck_colors(deck_code: str | None) -> set[str]:
    if not deck_code:
        return set()
    raw = DECK_COLORS.get(deck_code)
    if not raw:
        return set()
    return {c.strip().lower() for c in raw.split(",") if c.strip()}


def _card_meta(card_name: str) -> dict | None:
    if not card_name or not isinstance(card_name, str):
        return None
    db = get_cards_db()
    card = db.get(card_name)
    return card if isinstance(card, dict) else None


def _card_set_num(card_name: str) -> int | None:
    card = _card_meta(card_name)
    if not card:
        return None
    raw = card.get("set")
    try:
        return int(raw) if raw not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _card_inks(card_name: str) -> set[str]:
    card = _card_meta(card_name)
    if not card:
        return set()
    ink = (card.get("ink", "") or "").lower().strip()
    if not ink or ink in ("dual ink", "inkless"):
        return set()
    if "/" in ink:
        return {c.strip() for c in ink.split("/") if c.strip()}
    return {ink}


def _card_on_deck_colors(card_name: str, deck_code: str | None) -> bool:
    """Return True if card's ink is fully contained in deck colors.

    Inkless / Dual Ink are treated as universal (always pass) — same
    convention as ``_card_ink_matches`` in generate_killer_curves.py.
    """
    if not deck_code:
        return False
    deck_set = _deck_colors(deck_code)
    if not deck_set:
        return False
    card = _card_meta(card_name)
    if not card:
        return False
    ink = (card.get("ink", "") or "").lower().strip()
    if ink in ("dual ink", "inkless"):
        return True
    inks = _card_inks(card_name)
    if not inks:
        return False
    return inks.issubset(deck_set)


def _is_english(text: str) -> bool:
    """Lightweight EN-only heuristic — flags strings with high ratio of
    non-ASCII letters (likely Italian/Spanish/etc). Not a hard gate."""
    if not text:
        return True
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return True
    non_ascii = sum(1 for c in letters if ord(c) > 127)
    return (non_ascii / len(letters)) < 0.05


def _combined_response_text(response: dict) -> str:
    parts: list[str] = []
    for key, value in (response or {}).items():
        if key == "cards":
            continue
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(v for v in value if isinstance(v, str))
        elif isinstance(value, dict):
            parts.extend(v for v in value.values() if isinstance(v, str))
    return "\n".join(parts)


def _response_text_includes(text: str, card_name: str) -> bool:
    if not text or not card_name:
        return False
    pattern = rf"(?<!\w){re.escape(card_name.lower())}(?!\w)"
    return bool(re.search(pattern, text.lower()))


def _check_top_level(
    data: dict,
    our_deck: str,
    opp_deck: str,
    game_format: str,
) -> list[dict]:
    errors: list[dict] = []
    if not isinstance(data, dict):
        errors.append({"code": "data_not_dict", "severity": "P0", "curve_id": None,
                       "detail": "validator received non-dict payload"})
        return errors

    metadata = data.get("metadata") or {}
    if metadata:
        m_our = metadata.get("our_deck")
        m_opp = metadata.get("opp_deck")
        m_fmt = metadata.get("game_format")
        if m_our and m_our != our_deck:
            errors.append({"code": "deck_mismatch_our", "severity": "P0", "curve_id": None,
                           "detail": f"metadata.our_deck={m_our} != expected {our_deck}"})
        if m_opp and m_opp != opp_deck:
            errors.append({"code": "deck_mismatch_opp", "severity": "P0", "curve_id": None,
                           "detail": f"metadata.opp_deck={m_opp} != expected {opp_deck}"})
        if m_fmt and m_fmt != game_format:
            errors.append({"code": "format_mismatch", "severity": "P0", "curve_id": None,
                           "detail": f"metadata.game_format={m_fmt} != expected {game_format}"})

    curves = data.get("curves")
    if not isinstance(curves, list):
        errors.append({"code": "curves_not_list", "severity": "P0", "curve_id": None,
                       "detail": "data.curves missing or not a list"})
    elif len(curves) == 0:
        errors.append({"code": "curves_empty", "severity": "P0", "curve_id": None,
                       "detail": "data.curves is empty"})
    elif len(curves) > 12:
        errors.append({"code": "curves_excess", "severity": "P1", "curve_id": None,
                       "detail": f"unusual curve count: {len(curves)} (>12)"})
    return errors


def _check_curve_response(
    curve: dict,
    our_deck: str,
    game_format: str,
    legal_sets: set[int],
    meta_cards: set[str],
    fallback_cards: set[str],
) -> tuple[list[dict], dict]:
    errors: list[dict] = []
    drop = {
        "response_cards_off_color": 0,
        "response_cards_core_illegal": 0,
        "response_cards_not_in_db": 0,
        "response_cards_non_meta": 0,
        "response_cards_kept_meta": 0,
        "response_cards_kept_fallback": 0,
    }
    cid = curve.get("id")
    response = curve.get("response") or {}

    if not isinstance(response, dict) or not response:
        errors.append({"code": "response_missing", "severity": "P0", "curve_id": cid,
                       "detail": "curve.response missing or empty"})
        return errors, drop

    # Response v2 required fields
    missing_v2 = [k for k in REQUIRED_RESPONSE_V2_FIELDS if not response.get(k)]
    if missing_v2:
        errors.append({"code": "response_v2_incomplete", "severity": "P0", "curve_id": cid,
                       "detail": f"missing v2 fields: {missing_v2}"})

    fmt_ver = response.get("format_version")
    if fmt_ver and fmt_ver != "v2":
        errors.append({"code": "response_format_version_bad", "severity": "P1", "curve_id": cid,
                       "detail": f"format_version={fmt_ver} (expected v2)"})

    # Cards validation
    cards = response.get("cards")
    if cards is not None and not isinstance(cards, list):
        errors.append({"code": "response_cards_not_list", "severity": "P0", "curve_id": cid,
                       "detail": "response.cards must be a list"})
        cards = []
    cards = cards or []

    for card_name in cards:
        if not isinstance(card_name, str) or not card_name.strip():
            continue
        meta = _card_meta(card_name)
        if not meta:
            drop["response_cards_not_in_db"] += 1
            errors.append({"code": "card_not_in_db", "severity": "P0", "curve_id": cid,
                           "detail": f"response card not in cards DB: {card_name}"})
            continue
        if game_format == "core" and legal_sets:
            set_num = _card_set_num(card_name)
            if set_num is not None and set_num not in legal_sets:
                drop["response_cards_core_illegal"] += 1
                errors.append({"code": "card_core_illegal", "severity": "P0", "curve_id": cid,
                               "detail": f"response card set={set_num} not in legal_sets {sorted(legal_sets)}: {card_name}"})
                continue
        if not _card_on_deck_colors(card_name, our_deck):
            drop["response_cards_off_color"] += 1
            errors.append({"code": "card_off_color_response", "severity": "P0", "curve_id": cid,
                           "detail": f"response card off-color for {our_deck}: {card_name}"})
            continue
        # 3-tier (killer.md): META first, FALLBACK second, DROP third
        if card_name in meta_cards:
            drop["response_cards_kept_meta"] += 1
        elif game_format == "core" and card_name in fallback_cards:
            drop["response_cards_kept_fallback"] += 1
        else:
            drop["response_cards_non_meta"] += 1
            errors.append({"code": "card_non_meta", "severity": "P1", "curve_id": cid,
                           "detail": f"response card not in current meta nor fallback pool: {card_name}"})

    # Mention rule (killer.md): if response.cards != [], at least one must be named
    valid_cards = [c for c in cards if isinstance(c, str) and c.strip()]
    if valid_cards:
        text = _combined_response_text(response)
        if not any(_response_text_includes(text, c) for c in valid_cards):
            errors.append({"code": "response_missing_named_card", "severity": "P0", "curve_id": cid,
                           "detail": f"response.cards={valid_cards} but no card name in readable text"})

    # English-only heuristic
    text = _combined_response_text(response)
    if not _is_english(text):
        errors.append({"code": "response_not_english", "severity": "P1", "curve_id": cid,
                       "detail": "response text appears non-English"})

    # priority_actions / what_to_avoid array length
    pa = response.get("priority_actions") or []
    if isinstance(pa, list) and len(pa) < 2:
        errors.append({"code": "priority_actions_too_short", "severity": "P1", "curve_id": cid,
                       "detail": f"priority_actions has {len(pa)} items (<2)"})
    wta = response.get("what_to_avoid") or []
    if isinstance(wta, list) and len(wta) < 1:
        errors.append({"code": "what_to_avoid_empty", "severity": "P1", "curve_id": cid,
                       "detail": "what_to_avoid is empty"})

    return errors, drop


def _check_curve_sequence(
    curve: dict,
    opp_deck: str,
    game_format: str,
    legal_sets: set[int],
) -> tuple[list[dict], dict]:
    errors: list[dict] = []
    drop = {
        "sequence_plays_wrong_side": 0,
        "sequence_plays_off_color": 0,
        "sequence_plays_core_illegal": 0,
        "sequence_plays_not_in_db": 0,
    }
    cid = curve.get("id")
    sequence = curve.get("sequence") or {}
    if not isinstance(sequence, dict) or not sequence:
        errors.append({"code": "sequence_missing", "severity": "P0", "curve_id": cid,
                       "detail": "curve.sequence missing or empty"})
        return errors, drop

    total_plays = 0
    for turn_key, turn_data in sequence.items():
        if not isinstance(turn_data, dict):
            continue
        plays = turn_data.get("plays")
        if not isinstance(plays, list):
            continue
        for play in plays:
            if not isinstance(play, dict):
                continue
            total_plays += 1
            card_name = play.get("card")
            if not card_name or not isinstance(card_name, str):
                continue
            meta = _card_meta(card_name)
            if not meta:
                drop["sequence_plays_not_in_db"] += 1
                errors.append({"code": "sequence_card_not_in_db", "severity": "P0", "curve_id": cid,
                               "detail": f"sequence card not in cards DB at {turn_key}: {card_name}"})
                continue
            if game_format == "core" and legal_sets:
                set_num = _card_set_num(card_name)
                if set_num is not None and set_num not in legal_sets:
                    drop["sequence_plays_core_illegal"] += 1
                    errors.append({"code": "sequence_card_core_illegal", "severity": "P0", "curve_id": cid,
                                   "detail": f"sequence card set={set_num} not in legal_sets at {turn_key}: {card_name}"})
                    continue
            if not _card_on_deck_colors(card_name, opp_deck):
                drop["sequence_plays_off_color"] += 1
                errors.append({"code": "sequence_card_off_color", "severity": "P0", "curve_id": cid,
                               "detail": f"sequence card off-color for opp={opp_deck} at {turn_key}: {card_name}"})

    if total_plays == 0:
        errors.append({"code": "sequence_no_plays", "severity": "P0", "curve_id": cid,
                       "detail": "sequence has no concrete plays"})

    # key_cards, combo, recursion_sources should be on opp colors
    for field in ("key_cards", "combo", "recursion_sources"):
        cards = curve.get(field) or []
        if not isinstance(cards, list):
            continue
        for card_name in cards:
            if not isinstance(card_name, str) or not card_name.strip():
                continue
            if not _card_meta(card_name):
                continue  # P0 already caught elsewhere if relevant
            if not _card_on_deck_colors(card_name, opp_deck):
                errors.append({"code": f"{field}_off_color", "severity": "P1", "curve_id": cid,
                               "detail": f"{field} card off-color for opp={opp_deck}: {card_name}"})

    return errors, drop


def _check_v3_payload(curve: dict) -> list[dict]:
    cid = curve.get("id")
    payload = curve.get("v3_payload")
    if not payload:
        return [{"code": "v3_payload_missing", "severity": "P1", "curve_id": cid,
                 "detail": "curve.v3_payload absent (post-25/04 contract)"}]
    if not isinstance(payload, dict):
        return [{"code": "v3_payload_not_dict", "severity": "P1", "curve_id": cid,
                 "detail": "curve.v3_payload not a dict"}]
    missing = [k for k in REQUIRED_V3_PAYLOAD_FIELDS if not payload.get(k)]
    if missing:
        return [{"code": "v3_payload_incomplete", "severity": "P1", "curve_id": cid,
                 "detail": f"v3_payload missing: {missing}"}]
    user_copy = payload.get("user_copy") or {}
    if isinstance(user_copy, dict) and not (user_copy.get("short") and user_copy.get("expanded")):
        return [{"code": "v3_payload_user_copy_incomplete", "severity": "P1", "curve_id": cid,
                 "detail": "user_copy missing short or expanded"}]
    return []


def _check_self_check(curve: dict) -> list[dict]:
    cid = curve.get("id")
    sc = curve.get("self_check")
    if not sc:
        return [{"code": "self_check_missing", "severity": "P2", "curve_id": cid,
                 "detail": "curve.self_check absent"}]
    if not isinstance(sc, dict):
        return [{"code": "self_check_not_dict", "severity": "P2", "curve_id": cid,
                 "detail": "curve.self_check not a dict"}]
    missing = [k for k in REQUIRED_SELF_CHECK_FIELDS if k not in sc]
    if missing:
        return [{"code": "self_check_incomplete", "severity": "P2", "curve_id": cid,
                 "detail": f"self_check missing: {missing}"}]
    return []


def _summarize_completeness(curves: list[dict]) -> dict:
    n = len(curves)
    if n == 0:
        return {"n_curves": 0}
    response_v2_complete = sum(
        1 for c in curves
        if isinstance(c, dict)
        and isinstance(c.get("response"), dict)
        and all(c["response"].get(k) for k in REQUIRED_RESPONSE_V2_FIELDS)
    )
    v3_complete = sum(
        1 for c in curves
        if isinstance(c, dict)
        and isinstance(c.get("v3_payload"), dict)
        and all(c["v3_payload"].get(k) for k in REQUIRED_V3_PAYLOAD_FIELDS)
    )
    sc_complete = sum(
        1 for c in curves
        if isinstance(c, dict)
        and isinstance(c.get("self_check"), dict)
        and all(k in c["self_check"] for k in REQUIRED_SELF_CHECK_FIELDS)
    )
    return {
        "n_curves": n,
        "response_v2_complete": response_v2_complete,
        "response_v2_complete_pct": round(100 * response_v2_complete / n, 1),
        "v3_payload_complete": v3_complete,
        "v3_payload_complete_pct": round(100 * v3_complete / n, 1),
        "self_check_complete": sc_complete,
        "self_check_complete_pct": round(100 * sc_complete / n, 1),
    }


def validate(
    data: dict,
    our_deck: str,
    opp_deck: str,
    game_format: str,
    db,
    *,
    meta_days: int = 30,
    meta_min_plays: int = 20,
) -> dict:
    """Run all deterministic checks on a KC payload.

    Args:
        data: KC dict (top-level: ``metadata``, ``curves[]``).
        our_deck, opp_deck: expected deck codes.
        game_format: 'core' | 'infinity'.
        db: SQLAlchemy session (used by ``meta_relevance`` and legality lookup).
        meta_days, meta_min_plays: pass-through to ``get_meta_relevant_cards``.

    Returns:
        {
            "validator_version": str,
            "quality_status": "pass" | "warn" | "blocked",
            "errors": [...P0...],
            "warnings": [...P1...],
            "info": [...P2...],
            "drop_metrics": {...},
            "completeness": {...}
        }
    """
    all_errors: list[dict] = []
    drop_totals: dict[str, int] = {}

    # Top-level checks
    all_errors.extend(_check_top_level(data, our_deck, opp_deck, game_format))

    curves = (data.get("curves") if isinstance(data, dict) else None) or []
    if not isinstance(curves, list):
        curves = []

    # Reference data
    legal_sets: set[int] = set()
    meta_cards: set[str] = set()
    fallback_cards: set[str] = set()
    if game_format == "core":
        try:
            from backend.services.meta_epoch_service import get_current_epoch
            epoch = get_current_epoch(db)
            legal_sets = set(epoch.legal_sets or []) if epoch else set()
        except Exception:
            legal_sets = set()
        try:
            # Local import to avoid circular dependency at module load
            from scripts.generate_killer_curves import _core_legal_fallback_cards
            fallback_cards = _core_legal_fallback_cards(our_deck)
        except Exception:
            fallback_cards = set()
    try:
        meta_cards = get_meta_relevant_cards(db, game_format=game_format,
                                              days=meta_days, min_plays=meta_min_plays) or set()
    except Exception:
        meta_cards = set()

    # Per-curve checks
    for curve in curves:
        if not isinstance(curve, dict):
            all_errors.append({"code": "curve_not_dict", "severity": "P0",
                               "curve_id": None, "detail": "curve is not a dict"})
            continue
        cid = curve.get("id")

        # Required fields presence
        for required in ("name", "sequence", "response"):
            if not curve.get(required):
                all_errors.append({"code": f"curve_missing_{required}", "severity": "P0",
                                   "curve_id": cid, "detail": f"required curve.{required} absent"})

        resp_errors, resp_drop = _check_curve_response(
            curve, our_deck, game_format, legal_sets, meta_cards, fallback_cards
        )
        all_errors.extend(resp_errors)
        for k, v in resp_drop.items():
            drop_totals[k] = drop_totals.get(k, 0) + v

        seq_errors, seq_drop = _check_curve_sequence(
            curve, opp_deck, game_format, legal_sets
        )
        all_errors.extend(seq_errors)
        for k, v in seq_drop.items():
            drop_totals[k] = drop_totals.get(k, 0) + v

        all_errors.extend(_check_v3_payload(curve))
        all_errors.extend(_check_self_check(curve))

    # Partition by severity
    errors = [e for e in all_errors if e.get("severity") == "P0"]
    warnings = [e for e in all_errors if e.get("severity") == "P1"]
    info = [e for e in all_errors if e.get("severity") == "P2"]

    if errors:
        quality_status = "blocked"
    elif warnings:
        quality_status = "warn"
    else:
        quality_status = "pass"

    return {
        "validator_version": VALIDATOR_VERSION,
        "quality_status": quality_status,
        "errors": errors,
        "warnings": warnings,
        "info": info,
        "drop_metrics": drop_totals,
        "completeness": _summarize_completeness(curves),
    }


def quality_summary(result: dict) -> str:
    """One-line human-readable summary of a validate() result."""
    status = result.get("quality_status", "?")
    n_err = len(result.get("errors") or [])
    n_warn = len(result.get("warnings") or [])
    comp = result.get("completeness") or {}
    return (
        f"[{status.upper()}] curves={comp.get('n_curves',0)} "
        f"v2={comp.get('response_v2_complete_pct',0)}% "
        f"v3={comp.get('v3_payload_complete_pct',0)}% "
        f"errors={n_err} warnings={n_warn}"
    )
