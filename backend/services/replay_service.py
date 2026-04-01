"""Replay service — parse duels.ink .replay.gz and extract coaching data."""
import copy
import gzip
import json
from typing import Optional


def parse_replay_gz(file_bytes: bytes) -> dict:
    """Decompress .replay.gz and build frame-by-frame snapshots.

    Input: raw bytes of a duels-replay-v1 gzipped file.
    Returns: dict with metadata, initial_hand, mulligan, snapshots[].
    Each snapshot = {board, hand, lore, ink, turn, action_type, label}.
    """
    try:
        raw = gzip.decompress(file_bytes)
    except Exception:
        raw = file_bytes
    try:
        data = json.loads(raw)
    except Exception as e:
        raise ValueError(f"Invalid replay file: {e}")

    if data.get("format") != "duels-replay-v1":
        raise ValueError(f"Unsupported format: {data.get('format')}")

    perspective = data.get("perspective", 1)
    bs = data.get("baseSnapshot", {})
    frames = data.get("frames", [])
    logs = data.get("logs", [])

    # Initial hand
    mp = bs.get("myPlayer", {})
    initial_hand = [
        {"name": c.get("fullName", c.get("name", "")), "id": c.get("id", ""), "cost": c.get("cost", 0)}
        for c in mp.get("hand", [])
    ]

    # Mulligan from logs
    mulligan = _extract_mulligan(logs)

    # Apply patches frame by frame to reconstruct full state
    state = copy.deepcopy(bs)
    snapshots = []

    # Snapshot 0: initial state
    snapshots.append(_snapshot(state, 0, "INITIAL", "Start", perspective))

    for frame in frames:
        patches = frame.get("patch", [])
        for p in patches:
            if isinstance(p, dict):
                _apply_patch(state, p)

        action_type = frame.get("actionType", "")
        turn = frame.get("turnNumber", 0)
        player = frame.get("player", 0)
        label = _make_label(action_type, turn, player, perspective, state)

        snapshots.append(_snapshot(state, turn, action_type, label, perspective))

    # Build hand_at_turn from snapshots
    hand_at_turn = {}
    for s in snapshots:
        t = str(s["turn"])
        if t not in hand_at_turn:
            hand_at_turn[t] = s["hand"]

    return {
        "game_id": data.get("gameId", ""),
        "perspective": perspective,
        "player_names": data.get("playerNames", {}),
        "winner": data.get("winner"),
        "victory_reason": data.get("victoryReason", ""),
        "turn_count": data.get("turnCount", 0),
        "initial_hand": initial_hand,
        "mulligan": mulligan,
        "snapshots": snapshots,
        "hand_at_turn": hand_at_turn,
    }


def _snapshot(state: dict, turn: int, action_type: str, label: str, perspective: int) -> dict:
    """Extract coaching-relevant state from the full game state."""
    mp = state.get("myPlayer", {})
    opp = state.get("opponent", {})

    def extract_cards(field_list):
        cards = []
        for c in (field_list or []):
            cards.append({
                "name": c.get("fullName", c.get("name", "")),
                "id": c.get("id", ""),
                "cost": c.get("cost", 0),
                "damage": c.get("damage", 0),
                "exerted": c.get("exerted", False),
                "strength": c.get("strength", 0),
                "willpower": c.get("willpower", 0),
                "lore": c.get("lore", 0),
            })
        return cards

    def extract_hand(hand_list):
        return [c.get("fullName", c.get("name", "")) for c in (hand_list or []) if isinstance(c, dict)]

    return {
        "turn": turn,
        "action_type": action_type,
        "label": label,
        "board": {
            "our": extract_cards(mp.get("field", [])),
            "opp": extract_cards(opp.get("field", [])),
        },
        "items": {
            "our": extract_cards(mp.get("items", [])),
            "opp": extract_cards(opp.get("items", [])),
        },
        "hand": extract_hand(mp.get("hand", [])),
        "hand_count_opp": opp.get("handCount", 0),
        "lore": {
            "our": mp.get("lore", 0),
            "opp": opp.get("lore", 0),
        },
        "ink": {
            "our": len(mp.get("inkwell", [])),
            "opp": len(opp.get("inkwell", [])),
        },
    }


def _make_label(action_type: str, turn: int, player: int, perspective: int, state: dict) -> str:
    """Human-readable label for an action."""
    who = "You" if player == perspective else "Opp"
    labels = {
        "CHOOSE_STARTING_PLAYER": "Coin toss",
        "MULLIGAN": f"T{turn} {who} Mulligan",
        "END_TURN": f"T{turn} {who} End turn",
        "ADD_TO_INK": f"T{turn} {who} Ink",
        "PLAY_CARD": f"T{turn} {who} Play",
        "QUEST": f"T{turn} {who} Quest",
        "ATTACK": f"T{turn} {who} Attack",
        "ACTIVATE_ABILITY": f"T{turn} {who} Ability",
        "RESPOND_TO_PROMPT": f"T{turn} {who} Response",
        "BOOST": f"T{turn} {who} Boost",
        "GAME_FINISH": "Game Over",
    }
    return labels.get(action_type, f"T{turn} {who} {action_type}")


def _apply_patch(obj: dict, patch: dict):
    """Apply a single JSON Patch operation (add/remove/replace) to obj in-place."""
    op = patch.get("op", "")
    path = patch.get("path", "")
    value = patch.get("value")

    if not path or path == "/":
        return

    parts = path.strip("/").split("/")
    target = obj

    # Navigate to parent
    for i, part in enumerate(parts[:-1]):
        if isinstance(target, list):
            try:
                idx = int(part)
                if 0 <= idx < len(target):
                    target = target[idx]
                else:
                    return
            except (ValueError, IndexError):
                return
        elif isinstance(target, dict):
            if part not in target:
                if op == "add":
                    target[part] = {} if not parts[i + 1].isdigit() else []
                    target = target[part]
                else:
                    return
            else:
                target = target[part]
        else:
            return

    key = parts[-1]

    if isinstance(target, list):
        try:
            idx = int(key)
        except ValueError:
            if key == "-" and op == "add":
                target.append(value)
            return

        if op == "add":
            if idx >= len(target):
                target.append(value)
            else:
                target.insert(idx, value)
        elif op == "remove":
            if 0 <= idx < len(target):
                target.pop(idx)
        elif op == "replace":
            if 0 <= idx < len(target):
                target[idx] = value

    elif isinstance(target, dict):
        if op == "add" or op == "replace":
            target[key] = value
        elif op == "remove":
            target.pop(key, None)


def _extract_mulligan(logs: list) -> dict:
    """Extract mulligan sent/received from logs."""
    sent, received = [], []
    for ev in logs:
        if ev.get("type") != "MULLIGAN":
            continue
        refs = ev.get("cardRefs", [])
        count = ev.get("data", {}).get("mulliganCount", 0)
        if count and refs:
            sent = [r.get("name", "") for r in refs[:count]]
            received = [r.get("name", "") for r in refs[count:]]
            break
    return {"sent": sent, "received": received}


def reconstruct_hand_per_turn(initial_hand: list, mulligan: dict, actions: list) -> dict:
    """Reconstruct the player's hand at the start of each turn."""
    hand = [c["name"] for c in initial_hand]
    if mulligan.get("sent"):
        for card in mulligan["sent"]:
            if card in hand:
                hand.remove(card)
        hand.extend(mulligan["received"])

    result = {"1": list(hand)}
    current_turn = 1

    for a in actions:
        turn = a.get("turn", 0)
        if turn > current_turn:
            current_turn = turn
            result[str(current_turn)] = list(hand)
        card = a.get("card")
        if not card:
            continue
        if a["type"] in ("DRAW", "ABILITY_DRAW"):
            hand.append(card)
        elif a["type"] in ("PLAY_CARD", "ADD_TO_INK"):
            if card in hand:
                hand.remove(card)
    return result


def auto_match_player(player_names: dict, roster: list) -> Optional[str]:
    """Match replay player names against team roster."""
    roster_names = {p["name"].lower(): p["name"] for p in roster}
    for pnum, pname in player_names.items():
        if pname.lower() in roster_names:
            return roster_names[pname.lower()]
    return None
