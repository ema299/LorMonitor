"""
build_replay_steps.py — Produce step[] pre-calcolati per il replay HTML.

Ogni step = 1 half-turn con board_start, board_after, eventi arricchiti.
Il JS legge e anima, zero logica di gioco.

Principio: il log è la fonte di verità. Board walked forward, mai ricostruito.

Board entries are dicts with per-instance state:
  {'name': str, 'damage': int, 'exerted': bool, 'shifted': bool, 'drying': bool}
This avoids the set-of-names bug where 2+ copies of the same card
would all show as exerted when only one acted.
"""

import re
from collections import Counter


# ── Card type helpers ──

def _is_character(card_db):
    return 'Character' in (card_db.get('type') or '')

def _is_action(card_db):
    return 'Action' in (card_db.get('type') or '')

def _is_song(card_db):
    return 'Song' in (card_db.get('type') or '') or 'Action - Song' in (card_db.get('type') or '')

def _is_item(name, db):
    c = db.get(name)
    if not c:
        return False
    t = (c.get('type') or '').lower()
    return 'item' in t or 'location' in t

def _is_persistent(name, db):
    """Characters, items, locations stay on board. Actions/songs don't."""
    c = db.get(name)
    if not c:
        return True  # unknown card → assume persistent
    t = (c.get('type') or '').lower()
    return 'action' not in t and 'song' not in t

def _get_resist(name, db):
    c = db.get(name)
    if not c:
        return 0
    m = re.search(r'\bResist\s*\+?(\d+)', c.get('ability') or '')
    return int(m.group(1)) if m else 0

def _get_challenger(name, db):
    c = db.get(name)
    if not c:
        return 0
    m = re.search(r'\bChallenger\s*\+?(\d+)', c.get('ability') or '')
    return int(m.group(1)) if m else 0

def _get_str(name, db):
    c = db.get(name)
    return int(c.get('str') or 0) if c else 0

def _get_will(name, db):
    c = db.get(name)
    return int(c.get('will') or 0) if c else 0


# ── Ability classification (ported from JS classifyAbility) ──

def classify_ability(ev, db):
    """Classify an ability event using DB ability text. Returns fx dict for animation."""
    card_name = ev.get('card', '')
    effect_raw = ev.get('effect') or ''
    effect = effect_raw.lower()
    target = ev.get('target', '?')
    activated = ev.get('activated', False)
    card = db.get(card_name) or {}
    db_ab = (card.get('ability') or '').lower()

    # Mass banish all characters (both sides)
    if 'banish all characters' in db_ab and 'opposing' not in db_ab.split('banish all characters')[0]:
        return {'type': 'banish_all', 'scope': 'all_characters', 'targets': [],
                'label': 'BANISH ALL', 'icon': '\u2620', 'color': 'var(--red)', 'prominent': True}
    # Mass banish opposing damaged
    if 'banish all opposing damaged' in db_ab:
        return {'type': 'banish_damaged', 'scope': 'opposing_damaged', 'targets': [],
                'label': 'BANISH DAMAGED', 'icon': '\u2620', 'color': 'var(--red)', 'prominent': True}
    # Mass banish opposing
    if 'banish all opposing' in db_ab:
        return {'type': 'banish_opp', 'scope': 'all_opposing', 'targets': [],
                'label': 'BANISH OPP', 'icon': '\u2620', 'color': 'var(--red)', 'prominent': True}

    # Mass damage: X damage to each opposing character
    m = (re.search(r'(?:deal|put)\w*\s+(\d+)\s+damage\s+counter\w*\s+on\s+each\s+opposing', db_ab, re.I)
         or re.search(r'(?:deal|put)\w*\s+(\d+)\s+damage\s+(?:to|on)\s+each\s+opposing', db_ab, re.I))
    if m:
        return {'type': 'mass_damage', 'scope': 'each_opposing', 'targets': [],
                'amount': int(m.group(1)),
                'label': f'{m.group(1)} DMG ALL', 'icon': '\U0001f4a5', 'color': 'var(--red)', 'prominent': True}

    # Exert all opposing
    if 'exert all opposing' in db_ab or 'exert each opposing' in db_ab:
        return {'type': 'exert_all', 'scope': 'all_opposing', 'targets': [],
                'label': 'EXERT ALL', 'icon': '\U0001f504', 'color': 'var(--yellow)', 'prominent': True}
    # Exert chosen
    if 'exert chosen opposing' in db_ab or 'exerts a character' in effect:
        targets = [target] if target and target != '?' else []
        return {'type': 'exert', 'scope': 'chosen', 'targets': targets,
                'label': 'EXERT', 'icon': '\U0001f504', 'color': 'var(--yellow)',
                'prominent': True, 'activated': True}

    # Targeted damage (activated abilities: Angel GOOD AIM, Yzma, etc.)
    if not effect or 'damage' in effect:
        m2 = (re.search(r'(?:deal|do)\w*\s+(\d+)\s+damage\s+to\s+chosen\s+(?:character|opposing)', db_ab, re.I)
              or re.search(r'discard\s+a\s+card\s+to\s+deal\s+(\d+)\s+damage\s+to\s+chosen', db_ab, re.I))
        if m2:
            targets = [target] if target and target != '?' else []
            return {'type': 'damage', 'scope': 'chosen', 'targets': targets,
                    'amount': int(m2.group(1)),
                    'label': f'{m2.group(1)} DMG', 'icon': '\U0001f4a5', 'color': 'var(--red)',
                    'prominent': False, 'activated': True}

    # Banish chosen/target
    if not effect or 'banish' in effect:
        if re.search(r'banish\s+(?:chosen|target|an?\s+opposing)\s+character', db_ab, re.I):
            targets = [target] if target and target != '?' else []
            return {'type': 'banish_target', 'scope': 'chosen', 'targets': targets,
                    'label': 'BANISH', 'icon': '\u2620', 'color': 'var(--red)',
                    'prominent': False, 'activated': True}

    # Return to hand (bounce)
    if not effect or 'return' in effect or 'hand' in effect:
        if re.search(r'return\s+(?:chosen|target|an?\s+opposing)\s+character\s+to', db_ab, re.I):
            targets = [target] if target and target != '?' else []
            return {'type': 'bounce', 'scope': 'chosen', 'targets': targets,
                    'label': 'TO HAND', 'icon': '\u21a9', 'color': 'var(--emerald)',
                    'prominent': False, 'activated': True}

    # Draw cards
    m3 = re.search(r'draw\s+(\d+)\s+card', db_ab, re.I)
    if m3 and not effect:
        return {'type': 'draw', 'scope': 'self', 'targets': [],
                'amount': int(m3.group(1)),
                'label': f'DRAW {m3.group(1)}', 'icon': '\U0001f0cf', 'color': 'var(--sapphire)', 'prominent': False}

    # Gain lore
    m4 = re.search(r'gain\s+(\d+)\s+lore', db_ab, re.I)
    if m4 and not effect:
        return {'type': 'lore', 'scope': 'self', 'targets': [],
                'amount': int(m4.group(1)),
                'label': f'+{m4.group(1)} LORE', 'icon': '\u2b50', 'color': 'var(--gold)', 'prominent': False}

    # ── Log-based fallback ──

    # Move damage: "moves X damage from A to B"
    m_move = re.search(r'moves?\s+(\d+)\s+damage\s+from\s+(.+?)\s+to\s+(.+?)(?:\s*\(|$)', effect_raw, re.I)
    if m_move:
        amount = int(m_move.group(1))
        source_card = m_move.group(2).strip()
        dest_card = m_move.group(3).strip()
        return {'type': 'move_damage', 'scope': 'chosen', 'targets': [dest_card],
                'source_card': source_card, 'amount': amount,
                'label': f'{amount} DMG', 'icon': '\U0001f4a5', 'color': 'var(--red)',
                'prominent': False, 'activated': True}

    if 'banish' in effect:
        return {'type': 'banish', 'scope': 'unknown', 'targets': [],
                'label': 'BANISH', 'icon': '\u2620', 'color': 'var(--red)', 'prominent': False}
    m5 = re.search(r'putting\s+(.+?)\s+on bottom of deck', effect_raw, re.I)
    if m5:
        raw_names = m5.group(1)
        # "putting 4 characters on bottom" — numeric count, no names
        if re.match(r'^\d+\s+characters?$', raw_names, re.I):
            return {'type': 'tuck', 'scope': 'all', 'targets': [],
                    'label': 'TO DECK', 'icon': '\u2b07', 'color': 'var(--sapphire)', 'prominent': True}
        names = [n.strip() for n in raw_names.split(',') if n.strip()]
        return {'type': 'tuck', 'scope': 'targets', 'targets': names,
                'label': 'TO DECK', 'icon': '\u2b07', 'color': 'var(--sapphire)', 'prominent': True}
    # Hades "optionPutOnBottomDeck" — target is the chosen opposing character
    if 'optionputonbottomdeck' in effect.replace(' ', '').lower():
        targets = [target] if target and target != '?' else []
        return {'type': 'tuck', 'scope': 'chosen', 'targets': targets,
                'label': 'TO DECK', 'icon': '\u2b07', 'color': 'var(--sapphire)', 'prominent': False}
    m6 = re.search(r'(?:deals?|puts?)\s+(\d+)\s+damage', effect)
    if m6:
        return {'type': 'damage', 'scope': 'single', 'targets': [],
                'amount': int(m6.group(1)),
                'label': f'{m6.group(1)} DMG', 'icon': '\U0001f4a5', 'color': 'var(--red)', 'prominent': False}
    m7 = re.search(r'draws?\s+(\d+)\s+cards?', effect)
    if m7:
        return {'type': 'draw', 'scope': 'self', 'targets': [],
                'amount': int(m7.group(1)),
                'label': f'DRAW {m7.group(1)}', 'icon': '\U0001f0cf', 'color': 'var(--sapphire)', 'prominent': False}
    if 'draws a card' in effect:
        return {'type': 'draw', 'scope': 'self', 'targets': [],
                'amount': 1, 'label': 'DRAW 1', 'icon': '\U0001f0cf', 'color': 'var(--sapphire)', 'prominent': False}

    # Targeted ability with known target
    if target and target != '?':
        return {'type': 'targeted', 'scope': 'chosen', 'targets': [target],
                'label': ev.get('ability', 'ABILITY'), 'icon': '\u2728', 'color': 'var(--amethyst)', 'prominent': False}

    # Generic / non-targeting
    return {'type': 'self', 'scope': 'self', 'targets': [],
            'label': '', 'icon': '\u2728', 'color': 'var(--amethyst)', 'prominent': False}


# ── Board helpers (per-instance tracking) ──

def _mk_entry(name, damage=0, exerted=False, shifted=False, drying=False):
    """Create a board entry dict."""
    return {'name': name, 'damage': damage, 'exerted': exerted,
            'shifted': shifted, 'drying': drying}


def _find_entry(board_side, name, prefer_ready=False, prefer_exerted=False):
    """Find a board entry by name. Returns (index, entry) or (-1, None).

    prefer_ready: pick a non-exerted copy first (for quest/challenge/sing actions)
    prefer_exerted: pick an exerted copy first (for targeting exerted chars)
    """
    candidates = [(i, e) for i, e in enumerate(board_side) if e['name'] == name]
    if not candidates:
        return -1, None
    if prefer_ready:
        for i, e in candidates:
            if not e['exerted']:
                return i, e
    if prefer_exerted:
        for i, e in candidates:
            if e['exerted']:
                return i, e
    return candidates[0]


def _find_any_entry(board, name):
    """Find entry across both sides. Returns (side, index, entry) or (None, -1, None)."""
    for side in ('our', 'opp'):
        i, e = _find_entry(board[side], name)
        if e:
            return side, i, e
    return None, -1, None


def _remove_entry(board_side, name):
    """Remove first entry with given name. Returns the removed entry or None."""
    for i, e in enumerate(board_side):
        if e['name'] == name:
            return board_side.pop(i)
    return None


def _has_entry(board_side, name):
    """Check if any entry with given name exists."""
    return any(e['name'] == name for e in board_side)


# ── Board snapshot ──

def _snapshot_board(board):
    """Produce board state dict for JSON serialization."""
    result = {}
    for side in ('our', 'opp'):
        result[side] = [
            {'name': e['name'], 'damage': e['damage'], 'exerted': e['exerted'],
             'shifted': e['shifted'], 'drying': e['drying'], 'new': False}
            for e in board[side]
        ]
    return result


# ── Core step builder ──

def build_game_steps(game, db):
    """Build step[] for one game. Each step = 1 half-turn."""
    steps = []
    raw_turns = game.get('turns', {})
    # Normalize: turns can be a list of dicts with 't' key or a dict keyed by int
    if isinstance(raw_turns, list):
        turns = {td['t']: td for td in raw_turns if 't' in td}
    else:
        turns = raw_turns
    length = game.get('length', max(turns.keys()) if turns else 0)

    # Persistent state across steps
    # Board entries: list of dicts with per-instance state
    board = {'our': [], 'opp': []}
    discard = {'our': [], 'opp': []}
    hand = {'our': 7, 'opp': 7}
    lore = {'our': 0, 'opp': 0}
    inkwell = {'our': 0, 'opp': 0}

    for t_num in range(1, length + 1):
        td = turns.get(t_num)
        if not td:
            continue

        first = td.get('first_player', 'our')
        second = 'opp' if first == 'our' else 'our'

        for active_side in (first, second):
            passive_side = 'opp' if active_side == 'our' else 'our'

            # ── Ready phase: active side's characters un-exert + clear drying ──
            for entry in board[active_side]:
                entry['exerted'] = False
                entry['drying'] = False

            # ── Draw phase (T1 special: only OTD player draws) ──
            if t_num == 1:
                if active_side == second:  # OTD draws
                    hand[active_side] += 1
            else:
                hand[active_side] += 1

            # ── Snapshot board_start ──
            board_start = _snapshot_board(board)

            # ── Filter event_log for this half ──
            half_label = 'first' if active_side == first else 'second'
            raw_events = [ev for ev in td.get('event_log', []) if ev.get('half') == half_label]

            # ── Process events ──
            enriched_events = []
            ink_spent = {'our': 0, 'opp': 0}
            new_cards = {'our': set(), 'opp': set()}

            for ev in raw_events:
                etype = ev['type']
                ev_side = ev.get('side', active_side)

                if etype == 'ink':
                    inkwell[ev_side] += 1
                    enriched_events.append({
                        'type': 'ink', 'side': ev_side, 'card': ev.get('card', ''),
                        'anim': 'ink',
                    })

                elif etype == 'ramp':
                    inkwell[ev_side] += 1
                    enriched_events.append({
                        'type': 'ramp', 'side': ev_side, 'card': ev.get('card', ''),
                        'anim': 'ink_add',
                    })

                elif etype == 'play':
                    card_name = ev['card']
                    cost = ev.get('cost', 0)
                    is_sung = ev.get('is_sung', False)
                    singer = ev.get('singer')
                    is_spell = not _is_persistent(card_name, db)
                    is_shift = False
                    # Detect shift from play_detail
                    for pd in td.get(f'{ev_side}_play_detail', []):
                        if pd.get('name') == card_name and pd.get('is_shift'):
                            is_shift = True
                            cost = pd.get('ink_paid', cost)
                            break
                    else:
                        # Fallback: check play_detail for ink_paid
                        for pd in td.get(f'{ev_side}_play_detail', []):
                            if pd.get('name') == card_name:
                                cost = pd.get('ink_paid', cost)
                                break

                    ink_spent[ev_side] += cost

                    # Singer exerts (prefer a ready copy)
                    if is_sung and singer:
                        _, singer_entry = _find_entry(board[ev_side], singer, prefer_ready=True)
                        if singer_entry:
                            singer_entry['exerted'] = True

                    # Board update
                    if is_spell:
                        discard[ev_side].append(card_name)
                    else:
                        if is_shift:
                            # Remove one base from board (prefer ready copy)
                            base_name = card_name.split(' - ')[0] if ' - ' in card_name else card_name
                            removed = False
                            for i, entry in enumerate(board[ev_side]):
                                if entry['name'].split(' - ')[0] == base_name and entry['name'] != card_name:
                                    board[ev_side].pop(i)
                                    removed = True
                                    break
                            board[ev_side].append(_mk_entry(card_name, shifted=True))
                        else:
                            board[ev_side].append(_mk_entry(card_name, drying=True))
                        new_cards[ev_side].add(card_name)

                    # Hand update
                    hand[ev_side] = max(0, hand[ev_side] - 1)

                    play_ev = {
                        'type': 'play', 'side': ev_side, 'card': card_name,
                        'cost': cost, 'spell': is_spell, 'shift': is_shift,
                        'sung': is_sung, 'singer': singer,
                        'anim': 'spell_overlay' if is_spell else 'reveal',
                    }
                    # For spells: lookahead to attach fx from subsequent ability events
                    if is_spell:
                        spell_fx_list = []
                        for la_ev in raw_events[raw_events.index(ev)+1:]:
                            if la_ev.get('type') == 'ability' and la_ev.get('card') == card_name:
                                spell_fx_list.append(classify_ability(la_ev, db))
                            elif la_ev.get('type') not in ('ability', 'damage', 'destroyed'):
                                break
                        # Use the most specific fx (first with targets, or first prominent)
                        if spell_fx_list:
                            best = next((f for f in spell_fx_list if f.get('targets')), spell_fx_list[0])
                            play_ev['fx'] = best
                    enriched_events.append(play_ev)

                elif etype == 'ability':
                    fx = classify_ability(ev, db)

                    # ── Infer missing targets ──
                    # Exert chosen with target='?': lookahead for challenge defender
                    if fx.get('type') == 'exert' and not fx.get('targets'):
                        for la_ev in raw_events[raw_events.index(ev)+1:]:
                            if la_ev.get('type') == 'challenge' and la_ev.get('side') == ev_side:
                                defender = la_ev.get('defender', '')
                                if defender and _has_entry(board[passive_side], defender):
                                    fx['targets'] = [defender]
                                    break
                            elif la_ev.get('type') not in ('ability', 'challenge', 'damage', 'destroyed'):
                                break
                    # Targeted damage/banish with target='?': lookahead for damage/destroyed
                    if fx.get('type') in ('damage', 'banish_target') and not fx.get('targets'):
                        for la_ev in raw_events[raw_events.index(ev)+1:]:
                            if la_ev.get('type') == 'damage':
                                fx['targets'] = [la_ev.get('receiver', '')]
                                break
                            elif la_ev.get('type') == 'destroyed':
                                fx['targets'] = [la_ev.get('card', '')]
                                break
                            elif la_ev.get('type') not in ('ability', 'damage', 'destroyed'):
                                break

                    # ── Apply board side-effects from ability ──
                    fx_type = fx.get('type', '')
                    target_side = passive_side if ev_side == active_side else active_side

                    if fx_type == 'banish_all':
                        # Banish ALL characters (both sides)
                        targets = []
                        for s in ('our', 'opp'):
                            to_remove = [e for e in board[s]
                                         if _is_persistent(e['name'], db) and not _is_item(e['name'], db)]
                            for entry in to_remove:
                                targets.append(entry['name'])
                                board[s].remove(entry)
                                discard[s].append(entry['name'])
                        fx['targets'] = targets

                    elif fx_type == 'banish_opp':
                        # Banish all OPPOSING characters
                        targets = []
                        to_remove = [e for e in board[target_side]
                                     if _is_persistent(e['name'], db) and not _is_item(e['name'], db)]
                        for entry in to_remove:
                            targets.append(entry['name'])
                            board[target_side].remove(entry)
                            discard[target_side].append(entry['name'])
                        fx['targets'] = targets

                    elif fx_type == 'banish_damaged':
                        # Banish all opposing DAMAGED characters
                        targets = []
                        to_remove = [e for e in board[target_side]
                                     if e['damage'] > 0 and _is_persistent(e['name'], db)
                                     and not _is_item(e['name'], db)]
                        for entry in to_remove:
                            targets.append(entry['name'])
                            board[target_side].remove(entry)
                            discard[target_side].append(entry['name'])
                        fx['targets'] = targets

                    elif fx_type == 'tuck':
                        # Put targets on bottom of deck
                        for tname in fx.get('targets', []):
                            for s in ('our', 'opp'):
                                removed = _remove_entry(board[s], tname)
                                if removed:
                                    break

                    elif fx_type == 'bounce' and fx.get('targets'):
                        for tname in fx['targets']:
                            removed = _remove_entry(board[target_side], tname)
                            if removed:
                                hand[target_side] += 1

                    elif fx_type == 'exert_all':
                        targets = []
                        for entry in board[target_side]:
                            if _is_persistent(entry['name'], db) and not _is_item(entry['name'], db):
                                entry['exerted'] = True
                                targets.append(entry['name'])
                        fx['targets'] = targets

                    elif fx_type == 'exert' and fx.get('targets'):
                        for tname in fx['targets']:
                            _, entry = _find_entry(board[target_side], tname, prefer_ready=True)
                            if entry:
                                entry['exerted'] = True

                    enriched_events.append({
                        'type': 'ability', 'side': ev_side, 'card': ev['card'],
                        'ability_name': ev.get('ability', ''),
                        'effect': ev.get('effect', ''),
                        'activated': ev.get('activated', False),
                        'fx': fx,
                        'anim': 'ability_overlay' if fx.get('prominent') else
                                ('ability_arrow' if fx.get('activated') and fx.get('targets') else 'ability_flash'),
                    })

                elif etype == 'damage':
                    receiver = ev['receiver']
                    amount = ev.get('amount', 0)
                    recv_side = ev_side
                    # Update damage on the entry
                    _, entry = _find_entry(board[recv_side], receiver)
                    if entry:
                        entry['damage'] += amount
                        total = entry['damage']
                    else:
                        total = amount

                    enriched_events.append({
                        'type': 'damage', 'side': recv_side, 'card': receiver,
                        'dealer': ev.get('dealer', ''),
                        'amount': amount, 'total': total,
                        'will': _get_will(receiver, db),
                        'anim': 'damage_badge',
                    })

                elif etype == 'destroyed':
                    card_name = ev['card']
                    dest_side = ev_side
                    # Remove from board (may already be gone if banish_all preceded)
                    removed = _remove_entry(board[dest_side], card_name)
                    if removed:
                        discard[dest_side].append(card_name)

                    enriched_events.append({
                        'type': 'destroyed', 'side': dest_side, 'card': card_name,
                        'anim': 'death',
                    })

                elif etype == 'quest':
                    card_name = ev['card']
                    quest_lore = ev.get('lore', 0)
                    # Exert: prefer a ready copy (the one actually questing)
                    _, entry = _find_entry(board[ev_side], card_name, prefer_ready=True)
                    if entry:
                        entry['exerted'] = True
                    lore[ev_side] += quest_lore

                    enriched_events.append({
                        'type': 'quest', 'side': ev_side, 'card': card_name,
                        'lore': quest_lore,
                        'anim': 'exert',
                    })

                elif etype == 'challenge':
                    attacker = ev.get('attacker', '')
                    defender = ev.get('defender', '')
                    # Find full challenge data from turn aggregates
                    ch_data = None
                    for ch in td.get(f'{ev_side}_challenges', []):
                        if ch['attacker'] == attacker and ch['defender'] == defender:
                            ch_data = ch
                            break

                    atk_str = _get_str(attacker, db) + _get_challenger(attacker, db)
                    def_str = _get_str(defender, db)
                    dmg_to_def = max(0, atk_str - _get_resist(defender, db))
                    dmg_to_atk = max(0, def_str - _get_resist(attacker, db))
                    def_killed = ch_data.get('def_killed', False) if ch_data else False
                    atk_killed = ch_data.get('atk_killed', False) if ch_data else False

                    # Exert attacker (prefer a ready copy)
                    _, atk_entry = _find_entry(board[ev_side], attacker, prefer_ready=True)
                    if atk_entry:
                        atk_entry['exerted'] = True

                    enriched_events.append({
                        'type': 'challenge', 'side': ev_side,
                        'attacker': attacker, 'defender': defender,
                        'atk_str': atk_str, 'def_str': def_str,
                        'dmg_to_def': dmg_to_def, 'dmg_to_atk': dmg_to_atk,
                        'def_killed': def_killed, 'atk_killed': atk_killed,
                        'anim': 'combat_arrow',
                    })

                elif etype == 'bounce':
                    card_name = ev['card']
                    bounce_side = ev_side
                    removed = _remove_entry(board[bounce_side], card_name)
                    if removed:
                        hand[bounce_side] += 1

                    enriched_events.append({
                        'type': 'bounce', 'side': bounce_side, 'card': card_name,
                        'anim': 'bounce',
                    })

                elif etype == 'draw':
                    hand[ev_side] += 1
                    enriched_events.append({
                        'type': 'draw', 'side': ev_side,
                        'card': ev.get('card', ''),
                        'cost': ev.get('cost', 0),
                        'anim': 'draw',
                    })

                elif etype == 'discard':
                    hand[ev_side] = max(0, hand[ev_side] - 1)
                    enriched_events.append({
                        'type': 'discard', 'side': ev_side, 'card': ev.get('card', ''),
                        'anim': 'discard',
                    })

                elif etype == 'support':
                    enriched_events.append({
                        'type': 'support', 'side': ev_side,
                        'supporter': ev.get('supporter', ''),
                        'supported': ev.get('supported', ''),
                        'anim': 'support',
                    })

            # ── Snapshot board_after ──
            board_after = _snapshot_board(board)

            # Mark new cards in board_after
            for side in ('our', 'opp'):
                for card in board_after[side]:
                    if card['name'] in new_cards[side]:
                        card['new'] = True

            # ── Build step ──
            step = {
                'turn': t_num,
                'who': active_side,
                'label': f'T{t_num} {"Noi" if active_side == "our" else "Opp"}',
                'board_start': board_start,
                'board_after': board_after,
                'inkwell': {
                    'our': {'total': inkwell['our'], 'spent': ink_spent['our']},
                    'opp': {'total': inkwell['opp'], 'spent': ink_spent['opp']},
                },
                'lore': {'our': lore['our'], 'opp': lore['opp']},
                'hand': {'our': max(0, hand['our']), 'opp': max(0, hand['opp'])},
                'discard': {'our': list(discard['our']), 'opp': list(discard['opp'])},
                'events': enriched_events,
            }
            steps.append(step)

    return steps


# ── Validation ──

def validate_steps(steps, game, db):
    """Compare step board_after with investigate board_state at end of each turn."""
    board_state = game.get('board_state', {})
    warnings = []

    # Group steps by turn
    turn_steps = {}
    for s in steps:
        t = s['turn']
        if t not in turn_steps:
            turn_steps[t] = []
        turn_steps[t].append(s)

    for t_num, t_steps in sorted(turn_steps.items()):
        if t_num not in board_state:
            continue
        expected = board_state[t_num]
        last_step = t_steps[-1]  # second half = end of turn
        actual_after = last_step['board_after']

        for side in ('our', 'opp'):
            expected_names = sorted(expected.get(side, []))
            actual_names = sorted(c['name'] for c in actual_after.get(side, []))
            if expected_names != actual_names:
                warnings.append(
                    f"T{t_num} {side}: expected {expected_names}, got {actual_names}"
                )

    return warnings


# ── Entry point ──

def build_all_steps(games, db):
    """Build step[] for all games. Returns list of (steps, warnings) per game."""
    results = []
    for game in games:
        steps = build_game_steps(game, db)
        warnings = validate_steps(steps, game, db)
        results.append((steps, warnings))
    return results
