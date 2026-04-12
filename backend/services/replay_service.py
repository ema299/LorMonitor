"""Replay service — parse duels.ink .replay.gz and extract coaching data."""
import copy
import gzip
import json
from typing import Optional


def _validate_replay(data: dict):
    """Pre-flight checks on raw replay data. Only blocks truly unprocessable
    files. Incomplete replays (disconnect, no game end) are accepted —
    if we can build snapshots, we show them."""
    errors = []

    # Hard requirements — without these we can't build anything
    if not data.get("gameId"):
        errors.append("Missing gameId")
    if "playerNames" not in data or not data["playerNames"]:
        errors.append("Missing playerNames")

    bs = data.get("baseSnapshot")
    if not bs or not isinstance(bs, dict):
        errors.append("Missing or invalid baseSnapshot")
    else:
        if not bs.get("myPlayer") or not isinstance(bs["myPlayer"], dict):
            errors.append("baseSnapshot missing myPlayer")
        if not bs.get("opponent") or not isinstance(bs["opponent"], dict):
            errors.append("baseSnapshot missing opponent")

    frames = data.get("frames")
    if not frames or not isinstance(frames, list):
        errors.append("Missing or empty frames")

    if errors:
        raise ValueError(f"Invalid replay: {'; '.join(errors)}")


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

    _validate_replay(data)

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
        action_type = frame.get("actionType", "")
        turn = frame.get("turnNumber", 0)
        player = frame.get("player", 0)

        # Analyze patches against the pre-apply state to extract the card names,
        # singer, target, ink spent and lore gained. Must run BEFORE _apply_patch
        # so the state still reflects what the patch is about to change.
        meta = _analyze_frame(patches, action_type, state, perspective, player)

        for p in patches:
            if isinstance(p, dict):
                _apply_patch(state, p)

        label = _make_label(action_type, turn, player, perspective, meta)

        snap = _snapshot(state, turn, action_type, label, perspective)
        # Enrich snapshot with structured action metadata so the frontend can
        # render detailed event log / animations without re-diffing the board.
        for k, v in meta.items():
            if v is not None and v != '':
                snap[k] = v
        snapshots.append(snap)

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
                "iid": c.get("instanceId", ""),
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

    def extract_inkwell(inkwell_list):
        """Extract ink cards with name and exerted status."""
        cards = []
        for c in (inkwell_list or []):
            if not isinstance(c, dict):
                continue
            hidden = c.get("hidden", False)
            cards.append({
                "name": c.get("fullName", c.get("name", "")) if not hidden else None,
                "cost": c.get("cost", 0) if not hidden else None,
                "exerted": c.get("exerted", False),
            })
        return cards

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
        "inkwell": {
            "our": extract_inkwell(mp.get("inkwell", [])),
            "opp": extract_inkwell(opp.get("inkwell", [])),
        },
    }


def _get_card_name(v) -> str:
    """Build fullName 'Name - Title' from a card dict in a patch/state."""
    if not isinstance(v, dict):
        return ''
    if v.get('fullName'):
        return v['fullName']
    n = v.get('name', '')
    t = v.get('title', '')
    if n and t and t not in n:
        return f"{n} - {t}"
    return n


def _get_at(state: dict, path_parts):
    """Navigate nested state by a list of path segments. Returns None on miss."""
    cur = state
    for p in path_parts:
        if cur is None:
            return None
        if isinstance(cur, list):
            try:
                cur = cur[int(p)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(p)
        else:
            return None
    return cur


def _analyze_frame(patches, action_type, state, perspective, player):
    """Inspect a frame's JSON patches to extract card-level metadata.

    Must be called BEFORE the patches are applied — the state argument
    must reflect the pre-frame snapshot, so we can still read the cards
    that a 'remove' operation is about to delete or read instanceIds
    of cards referenced by an activeChallenge.
    """
    meta = {}
    side = 'myPlayer' if player == perspective else 'opponent'

    ink_spent = 0
    field_adds = []      # (owner_side, 'field'|'items', idx, value)
    field_removes = []   # (owner_side, 'field'|'items', idx)
    discard_adds = []    # (owner_side, idx, value)
    exerted_true = []    # (owner_side, 'field'|'items', idx)
    lore_updates = {}    # owner_side -> new_value
    damage_updates = []  # (owner_side, idx, new_value)
    prompt_source_card = None
    active_challenge = None
    waiting_for_opp = None
    inkwell_add = None   # first add-to-inkwell value

    for p in patches:
        if not isinstance(p, dict):
            continue
        op = p.get('op', '')
        path = (p.get('path') or '').strip('/')
        val = p.get('value')
        if not path:
            continue
        parts = path.split('/')

        # Ink spent: covers both `inkwell/N/exerted` and `inkwell/N/card/exerted`
        if op == 'replace' and 'inkwell' in parts and parts[-1] == 'exerted' and val is True:
            ink_spent += 1

        # Field / items / discard changes
        if op == 'add' and len(parts) == 3 and parts[1] in ('field', 'items'):
            field_adds.append((parts[0], parts[1], parts[2], val))
        elif op == 'remove' and len(parts) == 3 and parts[1] in ('field', 'items'):
            field_removes.append((parts[0], parts[1], parts[2]))
        elif op == 'add' and len(parts) == 3 and parts[1] == 'discard':
            discard_adds.append((parts[0], parts[2], val))

        # Characters/items becoming exerted (quest, singer, attack, ability)
        if (op == 'replace' and len(parts) >= 4
                and parts[1] in ('field', 'items')
                and parts[-1] == 'exerted' and val is True):
            exerted_true.append((parts[0], parts[1], parts[2]))

        # Lore update
        if op == 'replace' and len(parts) == 2 and parts[1] == 'lore':
            lore_updates[parts[0]] = val

        # Damage update
        if (op == 'replace' and len(parts) >= 4
                and parts[1] == 'field' and parts[-1] == 'damage'):
            damage_updates.append((parts[0], parts[2], val))

        # Prompt / challenge / waiting state
        if op == 'replace' and path == 'promptSourceCard':
            prompt_source_card = val
        elif op == 'replace' and path == 'activeChallenge':
            active_challenge = val
        elif op == 'replace' and path == 'waitingForOpponent':
            waiting_for_opp = val

        # Inkwell add (for ADD_TO_INK)
        if op == 'add' and len(parts) >= 3 and parts[1] == 'inkwell' and inkwell_add is None:
            inkwell_add = val

    meta['ink_spent'] = ink_spent

    if action_type == 'PLAY_CARD':
        # 1) Character / item: first add to field or items
        if field_adds:
            owner_f, zone_f, idx_f, v = field_adds[0]
            played = _get_card_name(v)
            meta['played_card'] = played
            meta['played_card_cost'] = (v.get('cost') if isinstance(v, dict) else 0) or 0
            if zone_f == 'items':
                meta['is_item'] = True
            # Shift: find a removed card on the same side+zone whose base name matches
            base_played = played.split(' - ')[0] if ' - ' in played else played
            for owner_r, zone_r, idx_r in field_removes:
                if owner_r != owner_f or zone_r != zone_f:
                    continue
                rem = _get_at(state, [owner_r, zone_r, idx_r])
                rem_name = _get_card_name(rem)
                if not rem_name:
                    continue
                rem_base = rem_name.split(' - ')[0] if ' - ' in rem_name else rem_name
                if rem_base and rem_base == base_played:
                    meta['is_shift'] = True
                    meta['shift_base'] = rem_name
                    break
        # 2) Song / non-persistent action: no field add, only promptSourceCard
        elif prompt_source_card:
            meta['played_card'] = _get_card_name(prompt_source_card)
            meta['played_card_cost'] = (
                prompt_source_card.get('cost') if isinstance(prompt_source_card, dict) else 0
            ) or 0
            meta['is_song'] = True
            # Singer = a character on the same side that just became exerted
            for owner_e, zone_e, idx_e in exerted_true:
                if owner_e != side or zone_e != 'field':
                    continue
                ch = _get_at(state, [owner_e, zone_e, idx_e])
                nm = _get_card_name(ch)
                if nm:
                    meta['singer'] = nm
                    break

    elif action_type == 'QUEST':
        for owner_e, zone_e, idx_e in exerted_true:
            if owner_e != side or zone_e != 'field':
                continue
            ch = _get_at(state, [owner_e, zone_e, idx_e])
            nm = _get_card_name(ch)
            if nm:
                meta['quest_card'] = nm
                break
        if side in lore_updates:
            before = _get_at(state, [side, 'lore']) or 0
            meta['lore_gained'] = max(0, int(lore_updates[side] or 0) - int(before))

    elif action_type == 'ATTACK':
        if isinstance(active_challenge, dict):
            atk_id = active_challenge.get('attackerInstanceId')
            def_id = active_challenge.get('defenderInstanceId')
            for s in ('myPlayer', 'opponent'):
                field_list = _get_at(state, [s, 'field']) or []
                for c in field_list:
                    if not isinstance(c, dict):
                        continue
                    if c.get('instanceId') == atk_id:
                        meta['attacker'] = _get_card_name(c)
                    if c.get('instanceId') == def_id:
                        meta['defender'] = _get_card_name(c)
        # Damage delivered to defender side (not attacker's counter-damage)
        defender_side = 'myPlayer' if side == 'opponent' else 'opponent'
        for owner_d, idx_d, amt in damage_updates:
            if owner_d == defender_side and meta.get('defender'):
                meta['damage_dealt'] = amt
                break
        # Defender killed if it appears in a discard add
        if meta.get('defender'):
            for owner_x, idx_x, v in discard_adds:
                if _get_card_name(v) == meta['defender']:
                    meta['defender_killed'] = True
                    break

    elif action_type == 'ACTIVATE_ABILITY':
        # 1) Source = first card that got exerted (item or character)
        for owner_e, zone_e, idx_e in exerted_true:
            src = _get_at(state, [owner_e, zone_e, idx_e])
            nm = _get_card_name(src)
            if nm:
                meta['ability_card'] = nm
                break
        # 2) Fallback: the card that self-banishes (remove from field/items)
        #    This covers abilities that banish their own source card (e.g. Guidebook's Boost 2).
        if not meta.get('ability_card'):
            for owner_r, zone_r, idx_r in field_removes:
                if owner_r != side:
                    continue
                src = _get_at(state, [owner_r, zone_r, idx_r])
                nm = _get_card_name(src)
                if nm:
                    meta['ability_card'] = nm
                    break
        if isinstance(waiting_for_opp, dict):
            name = waiting_for_opp.get('cardName')
            if name:
                meta['ability_name'] = name
            src = waiting_for_opp.get('sourceCard')
            if not meta.get('ability_card') and isinstance(src, dict):
                meta['ability_card'] = _get_card_name(src)
        if not meta.get('ability_card') and isinstance(prompt_source_card, dict):
            meta['ability_card'] = _get_card_name(prompt_source_card)

    elif action_type == 'ADD_TO_INK':
        if isinstance(inkwell_add, dict):
            card = inkwell_add.get('card') if isinstance(inkwell_add.get('card'), dict) else inkwell_add
            nm = _get_card_name(card)
            if nm:
                meta['inked_card'] = nm

    elif action_type == 'RESPOND_TO_PROMPT':
        if isinstance(prompt_source_card, dict):
            meta['ability_card'] = _get_card_name(prompt_source_card)
        if isinstance(waiting_for_opp, dict):
            name = waiting_for_opp.get('cardName')
            if name:
                meta['ability_name'] = name
        if discard_adds:
            owner_x, idx_x, v = discard_adds[0]
            nm = _get_card_name(v)
            if nm:
                meta['response_card_to_discard'] = nm

    return meta


def _make_label(action_type: str, turn: int, player: int, perspective: int, meta: dict) -> str:
    """Human-readable label describing exactly what the frame does.

    Uses metadata extracted from the frame's patches (card names, singer,
    target, ink spent, lore gained). Falls back to a generic label only
    when no actionable context is available.
    """
    who = "You" if player == perspective else "Opp"
    base = f"T{turn} {who}"
    ink = f" ({meta.get('ink_spent', 0)}💧)" if meta.get('ink_spent') else ''

    if action_type == 'CHOOSE_STARTING_PLAYER':
        return "Coin toss"
    if action_type == 'GAME_FINISH':
        return "Game Over"
    if action_type == 'MULLIGAN':
        return f"{base} Mulligan"
    if action_type == 'END_TURN':
        return f"{base} End turn"
    if action_type == 'BOOST':
        return f"{base} Boost"

    if action_type == 'PLAY_CARD':
        card = meta.get('played_card', '')
        if not card:
            return f"{base} Play"
        if meta.get('is_song'):
            singer = meta.get('singer')
            suffix = f" (sung by {singer})" if singer else ""
            return f"{base} Song {card}{suffix}"
        if meta.get('is_shift'):
            return f"{base} Shift {card} onto {meta.get('shift_base', '?')}{ink}"
        return f"{base} Play {card}{ink}"

    if action_type == 'QUEST':
        q = meta.get('quest_card', '')
        lore = meta.get('lore_gained')
        lore_suffix = f" (+{lore}⭐)" if lore else ''
        return f"{base} Quest {q}{lore_suffix}" if q else f"{base} Quest"

    if action_type == 'ATTACK':
        atk = meta.get('attacker', '?')
        dfn = meta.get('defender', '?')
        dmg = meta.get('damage_dealt')
        dmg_suffix = f" (-{dmg})" if dmg else ''
        kill = ' ☠' if meta.get('defender_killed') else ''
        return f"{base} Attack {atk} → {dfn}{dmg_suffix}{kill}"

    if action_type == 'ACTIVATE_ABILITY':
        card = meta.get('ability_card', '')
        name = meta.get('ability_name', '')
        if card and name:
            return f"{base} Ability {card}: {name}"
        if card:
            return f"{base} Ability {card}"
        return f"{base} Ability"

    if action_type == 'ADD_TO_INK':
        card = meta.get('inked_card', '')
        return f"{base} Ink {card}" if card else f"{base} Ink"

    if action_type == 'RESPOND_TO_PROMPT':
        card = meta.get('ability_card', '')
        name = meta.get('ability_name', '')
        if card:
            return f"{base} Respond ({card}{': '+name if name else ''})"
        return f"{base} Respond"

    return f"{base} {action_type}"


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
