"""Extract normalized public-log artifacts and derived per-match features.

Purpose:
- keep `matches.turns` as source-of-truth raw JSONB
- derive a viewer-safe normalized log
- persist a compact feature layer for future product queries
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from sqlalchemy.orm import Session

from backend.models.log_feature import MatchLogFeature
from backend.services import static_data_service

EXTRACTOR_VERSION = 2

EVENT_GROUPS = {
    "hand_seen": {"INITIAL_HAND", "MULLIGAN", "CARD_DRAWN", "CARD_PLAYED", "CARD_INKED", "CARD_REVEALED", "CARD_LOOKED_AT"},
    "draw": {"CARD_DRAWN", "TURN_DRAW"},
    "play": {"CARD_PLAYED"},
    "ink": {"CARD_INKED", "CARD_PUT_INTO_INKWELL"},
    "quest": {"CARD_QUEST", "LORE_GAINED"},
    "attack": {"CARD_ATTACK"},
    "destroy": {"CARD_DESTROYED"},
    "discard": {"CARD_DISCARDED"},
    "return": {"CARD_RETURNED"},
    "reveal": {"CARD_REVEALED", "CARD_LOOKED_AT"},
    "ability": {"ABILITY_TRIGGERED", "ABILITY_ACTIVATED", "ABILITY_CONDITION_FAILED"},
    "damage": {"DAMAGE_DEALT", "DAMAGE_REMOVED", "DAMAGE_PREVENTED"},
    "board": {"CARD_BOOSTED", "SUPPORT_GIVEN", "CARD_PUT_UNDER", "CARD_MOVED"},
}

NUMERIC_KEYS = ("amount", "value", "damage", "lore", "count", "mulliganCount")


def _card_refs(event: dict) -> list[dict]:
    refs = []
    for ref in event.get("cardRefs") or []:
        if isinstance(ref, dict):
            refs.append(ref)
        elif ref:
            refs.append({"name": str(ref)})
    return refs


def _card_names(event: dict) -> list[str]:
    names = []
    for ref in _card_refs(event):
        name = (ref.get("name") or "").strip()
        if name:
            names.append(name)
    return names


def _card_ids(event: dict) -> list[str]:
    ids = []
    for ref in _card_refs(event):
        card_id = (ref.get("id") or "").strip()
        if card_id:
            ids.append(card_id)
    return ids


def _turn_number(event: dict, seq: int) -> int:
    turn = event.get("turnNumber")
    if isinstance(turn, int):
        return turn
    data = event.get("data") or {}
    if isinstance(data.get("turnNumber"), int):
        return data["turnNumber"]
    return seq


def _extract_numeric(data: dict[str, Any]) -> dict[str, int | float]:
    out = {}
    for key in NUMERIC_KEYS:
        value = data.get(key)
        if isinstance(value, (int, float)):
            out[key] = value
    return out


def _event_kind(event_type: str) -> str:
    for kind, members in EVENT_GROUPS.items():
        if event_type in members:
            return kind
    return "other"


def _empty_player_summary() -> dict[str, Any]:
    return {
        "event_counts": Counter(),
        "first_turns": {},
        "cards_seen": set(),
        "cards_seen_by_turn": defaultdict(set),
        "cards_played": Counter(),
        "cards_inked": Counter(),
        "cards_drawn_named": Counter(),
        "cards_discarded": Counter(),
        "cards_destroyed": Counter(),
        "cards_returned": Counter(),
        "cards_revealed": Counter(),
        "automatic_turn_draw_count": 0,
        "named_turn_draw_count": 0,
        "named_draw_events": 0,
        "mulligan_count": 0,
        "lore_gained_total": 0,
        "damage_dealt_total": 0,
        "damage_removed_total": 0,
        "damage_prevented_total": 0,
    }


def _finalize_player_summary(summary: dict[str, Any]) -> dict[str, Any]:
    cards_seen_by_turn = {
        str(turn): sorted(cards) for turn, cards in sorted(summary["cards_seen_by_turn"].items())
    }
    return {
        "event_counts": dict(summary["event_counts"]),
        "first_turns": summary["first_turns"],
        "unique_cards_seen": len(summary["cards_seen"]),
        "cards_seen": sorted(summary["cards_seen"]),
        "cards_seen_by_turn": cards_seen_by_turn,
        "cards_played": dict(summary["cards_played"]),
        "cards_inked": dict(summary["cards_inked"]),
        "cards_drawn_named": dict(summary["cards_drawn_named"]),
        "cards_discarded": dict(summary["cards_discarded"]),
        "cards_destroyed": dict(summary["cards_destroyed"]),
        "cards_returned": dict(summary["cards_returned"]),
        "cards_revealed": dict(summary["cards_revealed"]),
        "automatic_turn_draw_count": summary["automatic_turn_draw_count"],
        "named_turn_draw_count": summary["named_turn_draw_count"],
        "named_draw_events": summary["named_draw_events"],
        "mulligan_count": summary["mulligan_count"],
        "lore_gained_total": summary["lore_gained_total"],
        "damage_dealt_total": summary["damage_dealt_total"],
        "damage_removed_total": summary["damage_removed_total"],
        "damage_prevented_total": summary["damage_prevented_total"],
    }


def _is_persistent_card(card_name: str, card_types: dict[str, str]) -> bool:
    card_type = (card_types.get(card_name) or "").lower()
    return "action" not in card_type and "song" not in card_type


def _empty_board_entry(card_name: str, card_types: dict[str, str]) -> dict[str, Any]:
    card_type = card_types.get(card_name) or ""
    return {
        "name": card_name,
        "type": card_type,
        "damage": 0,
        "exerted": False,
        "shifted": False,
        "drying": True,
        "new": True,
    }


def _snapshot_board(board_state: dict[str, list[dict]]) -> dict[str, list[dict]]:
    return {
        "our": [dict(card) for card in board_state["our"]],
        "opp": [dict(card) for card in board_state["opp"]],
    }


def _find_board_entry(board_list: list[dict], card_name: str, prefer_ready: bool = False) -> dict | None:
    first = None
    for entry in board_list:
        if entry["name"] != card_name:
            continue
        if first is None:
            first = entry
        if prefer_ready and not entry.get("exerted"):
            return entry
    return first


def _normalize_effect_text(event: dict) -> str:
    data = event.get("data") or {}
    if data.get("effectDescription"):
        return str(data["effectDescription"])
    if event.get("message"):
        return str(event["message"])
    return ""


def _effect_targets(event: dict) -> list[str]:
    data = event.get("data") or {}
    targets = []
    for item in data.get("effectDescriptionKeys") or []:
        params = item.get("params") or {}
        for value in params.values():
            if isinstance(value, str) and value and value != "a card":
                targets.append(value)
    names = _card_names(event)
    # For abilities, first cardRef is usually the source card.
    return [t for t in targets if t not in names]


def _event_fx(event: dict, source_card: str | None, targets: list[str]) -> dict:
    etype = event.get("type")
    data = event.get("data") or {}
    if etype == "CARD_ATTACK":
        return {
            "kind": "challenge",
            "arrow": True,
            "damage_to_target": data.get("actualDamageToDefender"),
            "damage_to_source": data.get("actualDamageToAttacker"),
            "target_destroyed": bool(data.get("defenderBanished")),
            "source_destroyed": bool(data.get("attackerBanished")),
        }
    if etype == "CARD_QUEST":
        return {"kind": "quest", "arrow": False, "lore_gained": data.get("loreGained", 0)}
    if etype in {"CARD_PLAYED", "CARD_INKED", "CARD_PUT_INTO_INKWELL", "CARD_DRAWN", "TURN_DRAW"}:
        return {"kind": etype.lower(), "arrow": False}
    if etype in {"ABILITY_TRIGGERED", "ABILITY_ACTIVATED"}:
        return {
            "kind": "ability",
            "arrow": bool(targets),
            "effect_text": _normalize_effect_text(event),
        }
    if etype == "CARD_DESTROYED":
        return {"kind": "destroy", "arrow": bool(source_card and targets)}
    if etype == "CARD_DISCARDED":
        return {"kind": "discard", "arrow": False}
    if etype == "CARD_RETURNED":
        return {"kind": "bounce", "arrow": False}
    return {"kind": etype.lower(), "arrow": False}


def _build_viewer_timeline(match, normalized_events: list[dict], card_types: dict[str, str]) -> list[dict]:
    board = {"our": [], "opp": []}
    lore = {"our": 0, "opp": 0}
    hand = {"our": 7, "opp": 7}
    inkwell = {"our": 0, "opp": 0}
    timeline = []

    for event in normalized_events:
        player = event.get("player")
        if player not in (1, 2):
            continue
        side = "our" if player == 1 else "opp"
        other_side = "opp" if side == "our" else "our"
        board_before = _snapshot_board(board)
        data = event.get("data") or {}
        names = event.get("card_names") or []
        etype = event.get("type")
        source_card = names[0] if names else None
        targets = []
        label = etype

        if etype == "TURN_READY":
            for entry in board[side]:
                entry["exerted"] = False
                entry["drying"] = False
                entry["new"] = False
            label = f"{side} ready"
        elif etype == "TURN_DRAW":
            hand[side] += 1
            label = f"{side} draw"
        elif etype == "CARD_DRAWN":
            hand[side] += 1
            label = f"{side} draws {source_card or 'a card'}"
        elif etype in {"CARD_INKED", "CARD_PUT_INTO_INKWELL"}:
            inkwell[side] += 1
            hand[side] = max(0, hand[side] - 1)
            label = f"{side} inks {source_card or 'a card'}"
        elif etype == "CARD_PLAYED":
            hand[side] = max(0, hand[side] - 1)
            if source_card and _is_persistent_card(source_card, card_types):
                board[side].append(_empty_board_entry(source_card, card_types))
            label = f"{side} plays {source_card or 'a card'}"
        elif etype == "CARD_QUEST":
            if source_card:
                entry = _find_board_entry(board[side], source_card, prefer_ready=True)
                if entry:
                    entry["exerted"] = True
                lore[side] += data.get("loreGained", 0)
            label = f"{side} quests with {source_card or 'a card'}"
        elif etype == "CARD_ATTACK":
            attacker = names[0] if len(names) > 0 else None
            defender = names[1] if len(names) > 1 else None
            source_card = attacker
            targets = [defender] if defender else []
            if attacker:
                atk_entry = _find_board_entry(board[side], attacker, prefer_ready=True)
                if atk_entry:
                    atk_entry["exerted"] = True
                    atk_entry["damage"] = int(data.get("attackerTotalDamage") or atk_entry["damage"] or 0)
            if defender:
                def_entry = _find_board_entry(board[other_side], defender, prefer_ready=False)
                if def_entry:
                    def_entry["damage"] = int(data.get("defenderTotalDamage") or def_entry["damage"] or 0)
            label = f"{side} attacks {defender or '?'} with {attacker or '?'}"
        elif etype == "CARD_DESTROYED":
            if source_card:
                victim = _find_board_entry(board[side], source_card) or _find_board_entry(board[other_side], source_card)
                if victim:
                    if victim in board[side]:
                        board[side].remove(victim)
                    elif victim in board[other_side]:
                        board[other_side].remove(victim)
            label = f"{source_card or 'card'} destroyed"
        elif etype == "CARD_DISCARDED":
            hand[side] = max(0, hand[side] - 1)
            label = f"{side} discards {source_card or 'a card'}"
        elif etype == "CARD_RETURNED":
            if source_card:
                entry = _find_board_entry(board[side], source_card) or _find_board_entry(board[other_side], source_card)
                if entry:
                    if entry in board[side]:
                        board[side].remove(entry)
                        hand[side] += 1
                    else:
                        board[other_side].remove(entry)
                        hand[other_side] += 1
            label = f"{source_card or 'card'} returned"
        elif etype in {"ABILITY_TRIGGERED", "ABILITY_ACTIVATED"}:
            targets = _effect_targets(event)
            label = _normalize_effect_text(event) or f"{source_card or 'card'} ability"
        elif etype == "LORE_GAINED":
            lore[side] += int(data.get("amount") or data.get("loreGained") or 0)
            label = f"{side} gains lore"

        timeline.append(
            {
                "seq": event["seq"],
                "turn": event["turn"],
                "player": player,
                "side": side,
                "type": etype,
                "label": label,
                "source": {
                    "card": source_card,
                    "player": player,
                    "side": side,
                },
                "targets": [
                    {
                        "card": target,
                        "side": other_side if etype == "CARD_ATTACK" else side,
                    }
                    for target in targets if target
                ],
                "effect_text": _normalize_effect_text(event),
                "fx": _event_fx(event, source_card, targets),
                "board_before": board_before,
                "board_after": _snapshot_board(board),
                "resources": {
                    "lore": dict(lore),
                    "hand": dict(hand),
                    "inkwell": dict(inkwell),
                },
                "raw": event,
            }
        )

    return timeline


def extract_match_log_bundle(match, db: Session | None = None) -> dict[str, Any]:
    logs = match.turns or []
    per_player = {1: _empty_player_summary(), 2: _empty_player_summary()}
    event_type_counts = Counter()
    normalized_events = []
    turn_players = defaultdict(set)
    conceder = None

    for seq, event in enumerate(logs, start=1):
        if not isinstance(event, dict):
            continue
        event_type = event.get("type") or "UNKNOWN"
        player = event.get("player")
        data = event.get("data") or {}
        turn = _turn_number(event, seq)
        names = _card_names(event)
        ids = _card_ids(event)
        kind = _event_kind(event_type)

        event_type_counts[event_type] += 1
        if player in (1, 2):
            turn_players[turn].add(player)
            summary = per_player[player]
            summary["event_counts"][event_type] += 1
            summary["event_counts"][kind] += 1
            summary["first_turns"].setdefault(event_type.lower(), turn)
            summary["first_turns"].setdefault(f"{kind}_event", turn)

            if event_type == "MULLIGAN" and isinstance(data.get("mulliganCount"), int):
                summary["mulligan_count"] = max(summary["mulligan_count"], data["mulliganCount"])
            if event_type == "TURN_DRAW":
                summary["automatic_turn_draw_count"] += 1
                if names:
                    summary["named_turn_draw_count"] += 1
            if event_type == "CARD_DRAWN":
                summary["named_draw_events"] += 1
            if event_type == "LORE_GAINED":
                summary["lore_gained_total"] += _extract_numeric(data).get("amount", 0)
            if event_type == "DAMAGE_DEALT":
                summary["damage_dealt_total"] += _extract_numeric(data).get("amount", 0)
            if event_type == "DAMAGE_REMOVED":
                summary["damage_removed_total"] += _extract_numeric(data).get("amount", 0)
            if event_type == "DAMAGE_PREVENTED":
                summary["damage_prevented_total"] += _extract_numeric(data).get("amount", 0)

            for name in names:
                summary["cards_seen"].add(name)
                summary["cards_seen_by_turn"][turn].add(name)
                if event_type == "CARD_PLAYED":
                    summary["cards_played"][name] += 1
                elif event_type in {"CARD_INKED", "CARD_PUT_INTO_INKWELL"}:
                    summary["cards_inked"][name] += 1
                elif event_type == "CARD_DRAWN":
                    summary["cards_drawn_named"][name] += 1
                elif event_type == "CARD_DISCARDED":
                    summary["cards_discarded"][name] += 1
                elif event_type == "CARD_DESTROYED":
                    summary["cards_destroyed"][name] += 1
                elif event_type == "CARD_RETURNED":
                    summary["cards_returned"][name] += 1
                elif event_type in {"CARD_REVEALED", "CARD_LOOKED_AT"}:
                    summary["cards_revealed"][name] += 1

        if event_type == "GAME_CONCEDED":
            conceder = data.get("concededBy") or player

        normalized_events.append(
            {
                "seq": seq,
                "turn": turn,
                "player": player,
                "type": event_type,
                "kind": kind,
                "card_names": names,
                "card_ids": ids,
                "data": data,
                "timestamp": event.get("timestamp"),
            }
        )

    card_types = static_data_service.get_card_types(db) if db is not None else {}
    viewer_timeline = _build_viewer_timeline(match, normalized_events, card_types)

    turn_summary = []
    for turn in sorted({ev["turn"] for ev in normalized_events}):
        turn_events = [ev for ev in normalized_events if ev["turn"] == turn]
        turn_summary.append(
            {
                "turn": turn,
                "players_present": sorted(turn_players.get(turn, set())),
                "event_types": dict(Counter(ev["type"] for ev in turn_events)),
                "cards_by_player": {
                    str(player): sorted({name for ev in turn_events if ev["player"] == player for name in ev["card_names"]})
                    for player in (1, 2)
                },
            }
        )

    summary = {
        "match_id": match.id,
        "external_id": match.external_id,
        "game_format": match.game_format,
        "perimeter": match.perimeter,
        "winner": match.winner,
        "conceder_player": conceder,
        "logged_turns": max((ev["turn"] for ev in normalized_events), default=0),
        "stored_total_turns": match.total_turns,
        "total_events": len(normalized_events),
        "event_type_counts": dict(event_type_counts),
        "available_signals": {
            "has_mulligan": event_type_counts["MULLIGAN"] > 0,
            "has_named_card_draws": event_type_counts["CARD_DRAWN"] > 0,
            "has_turn_draw_events": event_type_counts["TURN_DRAW"] > 0,
            "has_damage_events": sum(event_type_counts[t] for t in ("DAMAGE_DEALT", "DAMAGE_REMOVED", "DAMAGE_PREVENTED")) > 0,
            "has_returns": event_type_counts["CARD_RETURNED"] > 0,
            "has_discards": event_type_counts["CARD_DISCARDED"] > 0,
            "has_reveals": sum(event_type_counts[t] for t in ("CARD_REVEALED", "CARD_LOOKED_AT")) > 0,
            "has_lore_events": event_type_counts["LORE_GAINED"] > 0,
            "has_support": event_type_counts["SUPPORT_GIVEN"] > 0,
            "has_put_under": event_type_counts["CARD_PUT_UNDER"] > 0,
            "has_card_moved": event_type_counts["CARD_MOVED"] > 0,
            "has_undo": sum(event_type_counts[t] for t in ("FREE_UNDO", "UNDO_REQUESTED", "UNDO_ACCEPTED", "UNDO_DENIED")) > 0,
        },
    }

    viewer_public_log = {
        "version": EXTRACTOR_VERSION,
        "match_meta": {
            "match_id": match.id,
            "external_id": match.external_id,
            "played_at": match.played_at.isoformat() if match.played_at else None,
            "game_format": match.game_format,
            "perimeter": match.perimeter,
            "winner": match.winner,
            "player_names": {
                "1": match.player_a_name,
                "2": match.player_b_name,
            },
            "mmr": {
                "1": match.player_a_mmr,
                "2": match.player_b_mmr,
            },
            "deck_codes": {
                "1": match.deck_a,
                "2": match.deck_b,
            },
        },
        "turn_summary": turn_summary,
        "normalized_events": normalized_events,
        "viewer_timeline": viewer_timeline,
    }

    return {
        "extractor_version": EXTRACTOR_VERSION,
        "match_summary": summary,
        "player1_features": _finalize_player_summary(per_player[1]),
        "player2_features": _finalize_player_summary(per_player[2]),
        "viewer_public_log": viewer_public_log,
    }


def upsert_match_log_features(db: Session, match) -> MatchLogFeature:
    bundle = extract_match_log_bundle(match, db)
    row = db.query(MatchLogFeature).filter(MatchLogFeature.match_id == match.id).first()
    if not row:
        row = MatchLogFeature(match_id=match.id)
        db.add(row)
    row.extractor_version = bundle["extractor_version"]
    row.match_summary = bundle["match_summary"]
    row.player1_features = bundle["player1_features"]
    row.player2_features = bundle["player2_features"]
    row.viewer_public_log = bundle["viewer_public_log"]
    return row
