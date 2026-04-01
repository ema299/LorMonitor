"""
Caricamento match JSON e cards_db. Unica sorgente di verità per:
- DECK_COLORS
- Parsing dei log di gioco
- Caricamento cards_db
"""

import json, os, re
from collections import defaultdict

MATCHES_DIR = "/mnt/HC_Volume_104764377/finanza/Lor/matches"
CARDS_DB_PATH = "/mnt/HC_Volume_104764377/finanza/Lor/cards_db.json"
DECKS_DB_DIR = "/mnt/HC_Volume_104764377/finanza/Lor/decks_db"
LEGAL_SETS = {'WIS', 'ROJ', 'WITW', 'SHS', 'AZS', 'WUN', 'ARI', 'Q1', 'Q2', 'FAB', 'ROTF', 'ITI', 'URR', 'TFC',
              '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '1TFC'}  # numeric IDs from duels.ink

# Macro-perimetri formato
# core = Core-Constructed (SET11 + TOP + PRO + FRIENDS), infinity = Infinity (INF)
FORMAT_FOLDERS = {
    'core': {'SET11', 'TOP', 'PRO', 'FRIENDS'},
    'infinity': {'INF'},
}
VALID_FORMATS = set(FORMAT_FOLDERS.keys())  # {'core', 'infinity'}

# Queue prefixes valide per ogni formato (safety net: filtra match finiti
# nella cartella sbagliata, es. JA-BO1/ZH-BO1 in SET11)
FORMAT_QUEUE_PREFIXES = {
    'core': ('S11-',),
    'infinity': ('INF-', 'JA-', 'ZH-'),
}

DECK_FOLDER = {
    'AS': 'AS', 'ES': 'ES', 'AbS': 'AbS', 'AmAm': 'AmAm', 'AbE': 'AbE',
    'AbSt': 'AbSt', 'AmySt': 'AmySt', 'SSt': 'SSt', 'AbR': 'AbR',
    'AmyR': 'AmyR', 'AmyE': 'AmyE', 'RS': 'RS', 'ER': 'ER', 'ESt': 'ESt', 'RSt': 'RSt',
}

DECK_COLORS = {
    'AS':    ('amethyst', 'sapphire'),
    'ES':    ('emerald', 'sapphire'),
    'AbS':   ('amber', 'sapphire'),
    'AmAm':  ('amber', 'amethyst'),
    'AbE':   ('amber', 'emerald'),
    'AbSt':  ('amber', 'steel'),
    'AmySt': ('amethyst', 'steel'),
    'SSt':   ('sapphire', 'steel'),
    'AbR':   ('amber', 'ruby'),
    'AmyR':  ('amethyst', 'ruby'),
    'AmyE':  ('amethyst', 'emerald'),
    'RS':    ('ruby', 'sapphire'),
    'ER':    ('emerald', 'ruby'),
    'ESt':   ('emerald', 'steel'),
    'RSt':   ('ruby', 'steel'),
}

DECK_LONG_NAMES = {
    'AS':    'Amethyst-Sapphire',
    'ES':    'Emerald-Sapphire',
    'AbS':   'Amber-Sapphire',
    'AmAm':  'Amber-Amethyst',
    'AbE':   'Amber-Emerald',
    'AbSt':  'Amber-Steel',
    'AmySt': 'Amethyst-Steel',
    'SSt':   'Sapphire-Steel',
    'AbR':   'Amber-Ruby',
    'AmyR':  'Amethyst-Ruby',
    'AmyE':  'Amethyst-Emerald',
    'RS':    'Ruby-Sapphire',
    'ER':    'Emerald-Ruby',
    'ESt':   'Emerald-Steel',
    'RSt':   'Ruby-Steel',
}


def deck_long(short_key):
    """Ritorna il nome lungo di un deck. Es: 'ES' → 'Emerald-Sapphire'."""
    return DECK_LONG_NAMES.get(short_key, short_key)


def resolve_deck(name):
    """Risolve un nome deck case-insensitive. Accetta sia sigle che nomi lunghi."""
    # Prova sigla diretta
    lookup = {k.lower(): k for k in DECK_COLORS}
    if name.lower() in lookup:
        return lookup[name.lower()]
    # Prova nome lungo
    long_lookup = {v.lower(): k for k, v in DECK_LONG_NAMES.items()}
    return long_lookup.get(name.lower())


def match_colors(ink_colors, target):
    return tuple(sorted(c.lower() for c in ink_colors)) == tuple(sorted(target))


def safe_int(v):
    try:
        return int(v)
    except (ValueError, TypeError):
        return 0


def load_cards_db():
    """Load card database — duels.ink primary (cached), local cards_db.json fallback."""
    try:
        from test_kc.src.cards_api import get_cards_db
        db = get_cards_db()
        if db and len(db) > 100:
            return db
    except Exception:
        pass
    # Fallback to local file
    with open(CARDS_DB_PATH) as f:
        return json.load(f)


def _identify_sides(game_info, our_colors, opp_colors):
    """Identifica quale player è nostro e quale avversario. Ritorna (our_p, opp_p) o (None, None)."""
    p1c = game_info.get('player1', {}).get('inkColors', [])
    p2c = game_info.get('player2', {}).get('inkColors', [])
    if match_colors(p1c, our_colors) and match_colors(p2c, opp_colors):
        return 1, 2
    elif match_colors(p2c, our_colors) and match_colors(p1c, opp_colors):
        return 2, 1
    return None, None


def _find_winner(logs):
    """Trova il vincitore dai log. Ritorna 1, 2 o None."""
    winner = None
    for e in logs:
        if e.get('type') in ('GAME_END', 'GAME_CONCEDED'):
            w = (e.get('data') or {}).get('winner') or e.get('winner')
            if w in (1, 2):
                winner = int(w)
    return winner


def _new_turn():
    """Template per un turno vuoto con tutti i campi."""
    return {
        # ── Campi originali (retrocompatibili) ──
        'our_plays': [], 'opp_plays': [],           # [(nome, cardCost_stampato)]
        'our_challenges': [], 'opp_challenges': [],  # [{attacker, defender, str, ch_bonus, def_killed, atk_killed}]
        'our_abilities': [], 'opp_abilities': [],    # [{card, target, effect, ability}]
        'our_quests': [], 'opp_quests': [],          # [(nome, lore_gained)]
        'our_dead': [], 'opp_dead': [],              # [nome]
        'our_bounced': [], 'opp_bounced': [],        # [nome]
        'our_lore': 0, 'opp_lore': 0,               # int cumulativo

        # ── Campi nuovi: dettaglio play ──
        'our_play_detail': [], 'opp_play_detail': [],
        # [{name, card_cost, ink_paid, is_shift, shift_cost, is_sung}]
        # ink_paid = costo realmente pagato (shift_cost se shift, 0 se sung, card_cost altrimenti)

        # ── Campi nuovi: inkwell ──
        'our_inked': [], 'opp_inked': [],   # [nome] carte messe in inkwell (1/turno normale)
        'our_ramp': [], 'opp_ramp': [],     # [nome] ramp extra (CARD_PUT_INTO_INKWELL)

        # ── Campi nuovi: draw ──
        'our_drawn': [], 'opp_drawn': [],   # [(nome, costo)] draw da ability (CARD_DRAWN)

        # ── Campi nuovi: altro ──
        'our_damage': [], 'opp_damage': [],     # [{source, target, amount}] (DAMAGE_DEALT)
        'our_support': [], 'opp_support': [],   # [(supporter, supported)] (SUPPORT_GIVEN)
        'our_discard': [], 'opp_discard': [],   # [nome] (CARD_DISCARDED)
        'our_boost': [], 'opp_boost': [],       # [{card, cards_under}] (CARD_BOOSTED)
        'our_revealed': [], 'opp_revealed': [],  # [{name, destination, source}] (CARD_REVEALED)

        # ── Event log ordinato per half-turn (check/review layer) ──
        # Ogni evento ha: {type, side, card, ...dati specifici}
        # Ordine = ordine del raw log. Usato dal replay per verificare animazioni.
        'event_log': [],  # [{type, side, half, ...}]  half='first'|'second'
    }


def _build_name_normalizer(cards_db):
    """Costruisce un dizionario di normalizzazione nomi log → nomi DB.
    Gestisce differenze di capitalizzazione, punteggiatura (virgole), spazi."""
    norm_map = {}
    # Pre-computa versioni normalizzate dei nomi DB
    db_norms = {}
    for db_name in cards_db:
        key = db_name.lower().replace(',', '').replace('  ', ' ').strip()
        db_norms[key] = db_name

    def normalize(log_name):
        if log_name in cards_db:
            return log_name  # match esatto
        if log_name in norm_map:
            return norm_map[log_name]  # cache
        key = log_name.lower().replace(',', '').replace('  ', ' ').strip()
        db_name = db_norms.get(key)
        if db_name:
            norm_map[log_name] = db_name
            return db_name
        norm_map[log_name] = log_name  # cache il miss
        return log_name

    return normalize


# Module-level normalizer, set by load_matches
_normalize_name = None


def _strip_undone_events(logs):
    """
    Pre-processa i log rimuovendo eventi annullati da UNDO.
    Pattern: EVENT → UNDO_REQUESTED (1+) → UNDO_ACCEPTED = rimuovi EVENT
             EVENT → UNDO_REQUESTED (1+) → UNDO_DENIED   = tieni EVENT

    Ritorna la lista di log pulita (senza UNDO_REQUESTED/ACCEPTED/DENIED
    e senza gli eventi annullati).
    """
    # Tipi di eventi che possono essere "undone" (azioni del giocatore)
    UNDOABLE = {
        'CARD_PLAYED', 'CARD_INKED', 'CARD_QUEST', 'CARD_ATTACK',
        'ABILITY_TRIGGERED', 'ABILITY_ACTIVATED', 'DAMAGE_DEALT',
        'CARD_PUT_INTO_INKWELL',
        'CARD_DISCARDED', 'CARD_BOOSTED', 'SUPPORT_GIVEN',
    }

    cleaned = []
    i = 0
    while i < len(logs):
        e = logs[i]
        etype = e.get('type', '')

        if etype == 'UNDO_REQUESTED':
            # Cerca la risoluzione: UNDO_ACCEPTED o UNDO_DENIED
            # Salta eventuali UNDO_REQUESTED consecutivi e TIMER_*
            j = i + 1
            while j < len(logs):
                jtype = logs[j].get('type', '')
                if jtype == 'UNDO_ACCEPTED':
                    # Rimuovi l'ultimo evento undoable dello stesso player
                    undo_player = e.get('player')
                    # Cerca all'indietro nell'output pulito
                    removed = False
                    for k in range(len(cleaned) - 1, -1, -1):
                        if (cleaned[k].get('type', '') in UNDOABLE and
                                cleaned[k].get('player') == undo_player):
                            cleaned.pop(k)
                            removed = True
                            break
                    i = j + 1  # salta oltre UNDO_ACCEPTED
                    break
                elif jtype == 'UNDO_DENIED':
                    # L'azione resta, saltiamo solo i marker UNDO
                    i = j + 1
                    break
                elif jtype == 'UNDO_REQUESTED':
                    # UNDO multipli consecutivi, continua a cercare
                    j += 1
                else:
                    # TIMER_STARTED, TIMER_INCREMENT, etc — skip
                    j += 1
            else:
                # Nessuna risoluzione trovata, ignora l'UNDO
                i += 1
            continue

        elif etype in ('UNDO_ACCEPTED', 'UNDO_DENIED'):
            # Orfani (già gestiti sopra), skip
            i += 1
            continue

        cleaned.append(e)
        i += 1

    return cleaned


def _parse_turn_events(logs, our_p, opp_p, max_turn=None):
    """
    Parsa tutti gli eventi per turno dai log.
    Se max_turn è specificato, ignora i turni oltre quel limite.
    Ritorna dict {turn_number: turn_data} e il turno massimo trovato.
    """
    # Pre-processing: rimuovi eventi annullati da UNDO
    logs = _strip_undone_events(logs)

    turns = {}
    actual_max = 0

    # Pre-scan: per ogni turnNumber, trova chi fa TURN_START per primo
    # e traccia i confini tra first/second half (basato su TURN_START)
    first_player_per_turn = {}
    turn_start_indices = {}  # {tn: [idx1, idx2]} — indici dei TURN_START
    for i_pre, e in enumerate(logs):
        tn = e.get('turnNumber', 0)
        if tn < 1:
            continue
        if e.get('type') == 'TURN_START':
            p = e.get('player')
            if p is not None:
                if tn not in first_player_per_turn:
                    first_player_per_turn[tn] = 'our' if p == our_p else 'opp'
                turn_start_indices.setdefault(tn, []).append(i_pre)

    # Mappa evento_idx → half ('first' o 'second')
    # Eventi prima del secondo TURN_START = first half, dopo = second half
    def _get_half(tn, ei_raw):
        starts = turn_start_indices.get(tn, [])
        if len(starts) < 2:
            return 'first'
        return 'first' if ei_raw < starts[1] else 'second'

    for ei, e in enumerate(logs):
        tn = e.get('turnNumber', 0)
        if tn < 1:
            continue
        if max_turn and tn > max_turn:
            continue
        actual_max = max(actual_max, tn)

        if tn not in turns:
            t_new = _new_turn()
            t_new['first_player'] = first_player_per_turn.get(tn, 'our')
            turns[tn] = t_new

        t = turns[tn]
        etype = e.get('type', '')
        player = e.get('player')
        refs = e.get('cardRefs', [])
        data = e.get('data') or {}
        c1_raw = refs[0].get('name', '?') if refs and isinstance(refs[0], dict) else '?'
        c2_raw = refs[1].get('name', '?') if len(refs) > 1 and isinstance(refs[1], dict) else '?'
        c1 = _normalize_name(c1_raw) if _normalize_name else c1_raw
        c2 = _normalize_name(c2_raw) if _normalize_name else c2_raw

        side = 'our' if player == our_p else 'opp' if player == opp_p else None
        if side is None:
            continue

        if etype == 'CARD_PLAYED':
            card_cost = safe_int(data.get('cardCost', 0))
            is_shift = bool(data.get('usedShift'))
            shift_cost = safe_int(data.get('shiftCost', 0)) if is_shift else 0
            is_sung = bool(data.get('isSung'))

            # Costo realmente pagato
            if is_sung:
                ink_paid = 0
            elif is_shift:
                ink_paid = shift_cost
            else:
                ink_paid = card_cost

            # Campo originale (retrocompatibile)
            t[f'{side}_plays'].append((c1, card_cost))
            # Campo nuovo (dettaglio completo)
            detail = {
                'name': c1,
                'card_cost': card_cost,
                'ink_paid': ink_paid,
                'is_shift': is_shift,
                'shift_cost': shift_cost,
                'is_sung': is_sung,
            }
            # Per le song, c2 è il singer (chi canta)
            if is_sung and c2 != '?':
                detail['singer'] = c2
            t[f'{side}_play_detail'].append(detail)

        elif etype == 'CARD_ATTACK':
            # Il log genera 2 CARD_ATTACK per challenge:
            # 1° con solo cardCost (annuncio) — registra in event_log, poi skip
            # 2° con attackerBaseStrength + risultato combattimento — tieni
            if 'attackerBaseStrength' not in data:
                half = _get_half(tn, ei)
                t['event_log'].append({
                    'type': 'challenge', 'side': side, 'half': half,
                    'attacker': c1, 'defender': c2,
                })
                continue
            t[f'{side}_challenges'].append({
                'attacker': c1, 'defender': c2,
                'str': safe_int(data.get('attackerBaseStrength', 0)),
                'ch_bonus': safe_int(data.get('attackerChallengerBonus', 0)),
                'def_killed': data.get('defenderBanished', False),
                'atk_killed': data.get('attackerBanished', False),
            })
        elif etype == 'ABILITY_TRIGGERED':
            target = c2
            # Lookahead: se target='?' e l'effetto contiene "damage",
            # cerca il DAMAGE_DEALT successivo nello stesso turno per risolvere il target.
            # Salta eventuali ABILITY_TRIGGERED intermedie della stessa carta
            # (es. HHT: "deals 4 damage" + "grants Challenger +2" → poi DAMAGE_DEALT)
            eff_lower = (data.get('effectDescription', '')).lower()
            if (target == '?' or not target) and 'damage' in eff_lower:
                for nxt in logs[ei+1:ei+8]:
                    if nxt.get('turnNumber', 0) != tn:
                        break
                    if nxt.get('type') == 'ABILITY_TRIGGERED':
                        # Stessa carta con altra ability — continua a cercare
                        nrefs_ab = nxt.get('cardRefs', [])
                        ab_name = nrefs_ab[0].get('name', '') if nrefs_ab and isinstance(nrefs_ab[0], dict) else ''
                        if (_normalize_name(ab_name) if _normalize_name else ab_name) == c1:
                            continue
                        break  # Ability di altra carta — stop
                    if nxt.get('type') == 'DAMAGE_DEALT':
                        nrefs = nxt.get('cardRefs', [])
                        dmg_target_raw = nrefs[0].get('name', '?') if nrefs and isinstance(nrefs[0], dict) else '?'
                        dmg_source_raw = nrefs[1].get('name', '?') if len(nrefs) > 1 and isinstance(nrefs[1], dict) else '?'
                        # Verifica che il source del danno sia la stessa carta dell'ability
                        dmg_source = _normalize_name(dmg_source_raw) if _normalize_name else dmg_source_raw
                        if dmg_source == c1:
                            target = _normalize_name(dmg_target_raw) if _normalize_name else dmg_target_raw
                        break
                    if nxt.get('type') not in ('ABILITY_TRIGGERED', 'DAMAGE_DEALT'):
                        break  # Evento diverso — stop lookahead
            # Exert target: NON risolto qui — inferito nel replay JS
            # confrontando i defender delle challenge con lo stato exerted del turno precedente.
            # Un defender che era READY e viene challengato → era il target dell'exert.
            t[f'{side}_abilities'].append({
                'card': c1, 'target': target,
                'effect': data.get('effectDescription', ''),
                'ability': data.get('abilityName', ''),
            })
        elif etype == 'ABILITY_ACTIVATED':
            # Abilita' attivate volontariamente (es. Angel GOOD AIM, Yzma FEEL THE POWER,
            # Lantern BIRTHDAY LIGHTS, Black Cauldron, Elsa Fifth Spirit, ecc.)
            # Non hanno effectDescription — lookahead sempre per DAMAGE_DEALT.
            target = c2
            if target == '?' or not target:
                for nxt in logs[ei+1:ei+8]:
                    if nxt.get('turnNumber', 0) != tn:
                        break
                    if nxt.get('type') == 'DAMAGE_DEALT':
                        nrefs = nxt.get('cardRefs', [])
                        dmg_target_raw = nrefs[0].get('name', '?') if nrefs and isinstance(nrefs[0], dict) else '?'
                        dmg_source_raw = nrefs[1].get('name', '?') if len(nrefs) > 1 and isinstance(nrefs[1], dict) else '?'
                        dmg_source = _normalize_name(dmg_source_raw) if _normalize_name else dmg_source_raw
                        if dmg_source == c1:
                            target = _normalize_name(dmg_target_raw) if _normalize_name else dmg_target_raw
                        break
                    if nxt.get('type') not in ('ABILITY_ACTIVATED', 'ABILITY_TRIGGERED', 'DAMAGE_DEALT'):
                        break
            t[f'{side}_abilities'].append({
                'card': c1, 'target': target,
                'effect': data.get('effectDescription', ''),
                'ability': data.get('abilityName', ''),
            })
        elif etype == 'CARD_QUEST':
            lore = safe_int(data.get('loreGained', 0))
            total = safe_int(data.get('newLoreTotal', 0))
            t[f'{side}_quests'].append((c1, lore))
            t[f'{side}_lore'] = total
        elif etype == 'CARD_DESTROYED':
            t[f'{side}_dead'].append(c1)
        elif etype == 'CARD_RETURNED':
            if data.get('fromZone', '') == 'field':
                t[f'{side}_bounced'].append(c1)

        # ── Nuovi eventi ──
        elif etype == 'CARD_INKED':
            t[f'{side}_inked'].append(c1)
        elif etype == 'CARD_PUT_INTO_INKWELL':
            t[f'{side}_ramp'].append(c1 if c1 != '?' else 'unknown')
        elif etype == 'CARD_DRAWN':
            cost = safe_int(data.get('cardCost', 0))
            t[f'{side}_drawn'].append((c1, cost))
        elif etype == 'DAMAGE_DEALT':
            amount = safe_int(data.get('damageAmount', data.get('damage', data.get('amount', 0))))
            t[f'{side}_damage'].append({'source': c1, 'target': c2, 'amount': amount})
        elif etype == 'SUPPORT_GIVEN':
            t[f'{side}_support'].append((c1, c2))
        elif etype == 'CARD_DISCARDED':
            t[f'{side}_discard'].append(c1)
        elif etype == 'CARD_BOOSTED':
            cards_under = safe_int(data.get('cardsUnderCount', 0))
            t[f'{side}_boost'].append({'card': c1, 'cards_under': cards_under})
        elif etype == 'CARD_REVEALED':
            dest = data.get('revealDestination', '')
            source = data.get('sourceAbilityName', '')
            if dest or source:  # solo se ha info utile
                t[f'{side}_revealed'].append({
                    'name': c1, 'destination': dest, 'source': source,
                })

        # ── Event log: registra eventi significativi nell'ordine del raw log ──
        half = _get_half(tn, ei)
        ev_entry = None
        if etype == 'CARD_PLAYED':
            ev_entry = {'type': 'play', 'side': side, 'half': half,
                        'card': c1, 'cost': safe_int(data.get('cardCost', 0)),
                        'is_sung': bool(data.get('isSung')),
                        'singer': c2 if data.get('isSung') else None}
        elif etype in ('ABILITY_TRIGGERED', 'ABILITY_ACTIVATED'):
            ev_entry = {'type': 'ability', 'side': side, 'half': half,
                        'card': c1, 'ability': data.get('abilityName', ''),
                        'effect': data.get('effectDescription', ''),
                        'activated': etype == 'ABILITY_ACTIVATED'}
        elif etype == 'DAMAGE_DEALT':
            amt = safe_int(data.get('damageAmount', data.get('damage', data.get('amount', 0))))
            # cardRefs[0] = receiver, cardRefs[1] = dealer
            ev_entry = {'type': 'damage', 'side': side, 'half': half,
                        'receiver': c1, 'dealer': c2, 'amount': amt}
        elif etype == 'CARD_DESTROYED':
            ev_entry = {'type': 'destroyed', 'side': side, 'half': half, 'card': c1}
        elif etype == 'CARD_QUEST':
            lore_ev = safe_int(data.get('loreGained', 0))
            ev_entry = {'type': 'quest', 'side': side, 'half': half,
                        'card': c1, 'lore': lore_ev}
        elif etype == 'CARD_RETURNED' and data.get('fromZone', '') == 'field':
            ev_entry = {'type': 'bounce', 'side': side, 'half': half, 'card': c1}
        elif etype == 'CARD_INKED':
            ev_entry = {'type': 'ink', 'side': side, 'half': half, 'card': c1}
        elif etype == 'CARD_DRAWN':
            ev_entry = {'type': 'draw', 'side': side, 'half': half,
                        'card': c1, 'cost': safe_int(data.get('cardCost', 0))}
        elif etype == 'CARD_PUT_INTO_INKWELL':
            ev_entry = {'type': 'ramp', 'side': side, 'half': half,
                        'card': c1 if c1 != '?' else 'unknown'}
        elif etype == 'CARD_DISCARDED':
            ev_entry = {'type': 'discard', 'side': side, 'half': half, 'card': c1}
        elif etype == 'SUPPORT_GIVEN':
            ev_entry = {'type': 'support', 'side': side, 'half': half,
                        'supporter': c1, 'supported': c2}
        if ev_entry is not None:
            t['event_log'].append(ev_entry)

    # Fill lore forward
    our_lore = 0
    opp_lore = 0
    for tn in sorted(turns.keys()):
        t = turns[tn]
        if t['our_lore'] > 0:
            our_lore = t['our_lore']
        else:
            t['our_lore'] = our_lore
        if t['opp_lore'] > 0:
            opp_lore = t['opp_lore']
        else:
            t['opp_lore'] = opp_lore

    # ── Calcola inkwell reale per turno ──
    # Conta cumulativa: CARD_INKED + CARD_PUT_INTO_INKWELL
    our_inkwell = 0
    opp_inkwell = 0
    for tn in sorted(turns.keys()):
        t = turns[tn]
        our_inkwell += len(t['our_inked']) + len(t['our_ramp'])
        opp_inkwell += len(t['opp_inked']) + len(t['opp_ramp'])
        t['our_inkwell'] = our_inkwell
        t['opp_inkwell'] = opp_inkwell

        # Ink speso questo turno: clamp sequenziale per gestire riduzioni costo
        # Se il totale cardCost supera l'inkwell, le carte hanno avuto riduzioni
        for side_key, iw in [('our', our_inkwell), ('opp', opp_inkwell)]:
            details = t[f'{side_key}_play_detail']
            raw_total = sum(p['ink_paid'] for p in details)
            if raw_total > iw and details:
                # Clamp sequenziale: distribuisci l'ink disponibile
                remaining = iw
                for p in details:
                    actual = min(p['ink_paid'], remaining)
                    p['ink_paid'] = actual
                    remaining -= actual

        raw_our = sum(p['ink_paid'] for p in t['our_play_detail'])
        raw_opp = sum(p['ink_paid'] for p in t['opp_play_detail'])
        t['our_ink_spent'] = raw_our
        t['opp_ink_spent'] = raw_opp

    return turns, actual_max


def _get_singer_value(card_name, cards_db):
    """Ritorna il valore Singer di una carta, o 0 se non è singer."""
    card = cards_db.get(card_name, {})
    ab = card.get('ability', '')
    m = re.search(r'Singer\s+(\d+)', ab)
    return int(m.group(1)) if m else 0


def _get_shift_bases(card_name, cards_db):
    """Ritorna i possibili nomi base per uno shift (stesso personaggio, costo minore)."""
    card = cards_db.get(card_name, {})
    if not card:
        return []
    # Il base name è la parte prima di " - "
    base = card_name.split(' - ')[0] if ' - ' in card_name else card_name
    cost = safe_int(card.get('cost', 99))
    bases = []
    for name, data in cards_db.items():
        if name == card_name:
            continue
        if name.split(' - ')[0] == base and safe_int(data.get('cost', 99)) < cost:
            bases.append(name)
    return bases


def _is_song(card_name, cards_db):
    """Ritorna True se la carta è una Song."""
    card = _db_lookup(card_name, cards_db)
    return 'song' in (card.get('type', '') or '').lower()


def _sing_together_value(card_name, cards_db):
    """Ritorna il valore Sing Together, o 0 se non è Sing Together."""
    card = _db_lookup(card_name, cards_db)
    ab = card.get('ability', '')
    m = re.search(r'Sing Together\s+(\d+)', ab)
    return int(m.group(1)) if m else 0


def _db_lookup(card_name, cards_db):
    """Lookup carta nel DB, gestisce differenze di capitalizzazione e punteggiatura."""
    if card_name in cards_db:
        return cards_db[card_name]
    # Normalizzazione: lowercase, rimuovi virgole extra, normalizza spazi
    norm = card_name.lower().replace(',', '').replace('  ', ' ').strip()
    for db_name, data in cards_db.items():
        db_norm = db_name.lower().replace(',', '').replace('  ', ' ').strip()
        if db_norm == norm:
            return data
    return {}


def validate_turn_plays(turns, cards_db, game_label=''):
    """
    Valida le giocate turno per turno. Controlla:
    1. Sung: c'è un singer valido in board (non dry) con Singer >= song_cost?
    2. Shift: c'è la carta base in board?
    3. Ink: ink_spent <= inkwell?

    Traccia board state incrementale per entrambi i lati.
    Ritorna lista di warning strings.
    """
    warnings = []
    # Board state tracking: {card_name: count}
    our_board = defaultdict(int)
    opp_board = defaultdict(int)
    # Cards played THIS turn (dry — can't sing, can't challenge)
    our_dry = set()
    opp_dry = set()

    for tn in sorted(turns.keys()):
        t = turns[tn]
        our_dry.clear()
        opp_dry.clear()

        for side, board, dry in [('our', our_board, our_dry),
                                  ('opp', opp_board, opp_dry)]:
            for p in t[f'{side}_play_detail']:
                name = p['name']
                card_cost = p['card_cost']

                # ── Check SUNG ──
                if p['is_sung']:
                    if not _is_song(name, cards_db):
                        warnings.append(
                            f"{game_label}T{tn} {side}: {name} sung ma non è una Song")
                    else:
                        sing_together = _sing_together_value(name, cards_db)
                        if sing_together > 0:
                            # Sing Together: somma i costi di character non-dry in board
                            total_cost = 0
                            for bname, cnt in board.items():
                                if cnt <= 0 or bname in dry:
                                    continue
                                bcard = _db_lookup(bname, cards_db)
                                btype = (bcard.get('type', '') or '').lower()
                                if 'character' not in btype:
                                    continue
                                bc = safe_int(bcard.get('cost', 0))
                                total_cost += bc * cnt
                            if total_cost < sing_together:
                                warnings.append(
                                    f"{game_label}T{tn} {side}: {name} "
                                    f"(Sing Together {sing_together}) "
                                    f"sung ma costi board={total_cost} < {sing_together}")
                        else:
                            # Song normale: serve 1 character con Singer >= cost
                            # o character con card_cost >= song_cost
                            found_singer = False
                            for bname, cnt in board.items():
                                if cnt <= 0 or bname in dry:
                                    continue
                                sv = _get_singer_value(bname, cards_db)
                                if sv >= card_cost:
                                    found_singer = True
                                    break
                                bc = safe_int(_db_lookup(bname, cards_db).get('cost', 0))
                                if bc >= card_cost:
                                    found_singer = True
                                    break
                            if not found_singer:
                                active = {k: v for k, v in board.items() if v > 0}
                                warnings.append(
                                    f"{game_label}T{tn} {side}: {name} (cost {card_cost}) "
                                    f"sung ma nessun singer valido in board "
                                    f"(board: {active}, dry: {dry})")

                # ── Check SHIFT ──
                if p['is_shift']:
                    base_char = name.split(' - ')[0] if ' - ' in name else name
                    found_base = False
                    for bname, cnt in board.items():
                        if cnt <= 0:
                            continue
                        if bname.split(' - ')[0] == base_char:
                            found_base = True
                            # Shift consuma la base
                            board[bname] -= 1
                            break
                    if not found_base:
                        warnings.append(
                            f"{game_label}T{tn} {side}: {name} shift ma nessuna "
                            f"base '{base_char}' in board")

                # Aggiungi carta al board (persistent) o a dry
                card_data = _db_lookup(name, cards_db)
                card_type = (card_data.get('type', '') or '').lower()
                if 'action' not in card_type and 'song' not in card_type:
                    board[name] += 1
                    # Shift NON è dry: il character era già in gioco
                    if not p['is_shift']:
                        dry.add(name)

            # ── Rimuovi morti e bounced ──
            for dead_name in t.get(f'{side}_dead', []):
                if board[dead_name] > 0:
                    board[dead_name] -= 1
            for bounced_name in t.get(f'{side}_bounced', []):
                if board[bounced_name] > 0:
                    board[bounced_name] -= 1

        # ── Check INK ──
        if t['our_ink_spent'] > t.get('our_inkwell', 99):
            warnings.append(
                f"{game_label}T{tn}: our ink_spent {t['our_ink_spent']} > "
                f"inkwell {t['our_inkwell']}")
        if t['opp_ink_spent'] > t.get('opp_inkwell', 99):
            warnings.append(
                f"{game_label}T{tn}: opp ink_spent {t['opp_ink_spent']} > "
                f"inkwell {t['opp_inkwell']}")

    return warnings


def _parse_hand(logs, our_p):
    """Extract hand info from logs."""
    init_hand = None
    mulligan = None
    for e in logs:
        ep = e.get('player')
        if ep is not None:
            ep = int(ep)
        t = e.get('type', '')
        if t == 'INITIAL_HAND' and ep == our_p:
            init_hand = e.get('cardRefs', [])
        elif t == 'MULLIGAN' and ep == our_p:
            refs = e.get('cardRefs', [])
            mc = (e.get('data') or {}).get('mulliganCount')
            if mc is None:
                mc = e.get('mulliganCount', 0)
            mulligan = {'count': int(mc), 'refs': refs}

    if init_hand is None and mulligan is None:
        return None

    extract = lambda refs: [c.get('name', c.get('id', '?')) if isinstance(c, dict) else str(c) for c in refs]
    extract_ids = lambda refs: [c.get('id', '?') if isinstance(c, dict) else str(c) for c in refs]

    mc = mulligan['count'] if mulligan else 0
    if init_hand and mulligan and mc > 0:
        sb_names = extract(mulligan['refs'][:mc])
        sb_ids = extract_ids(mulligan['refs'][:mc])
        recv_names = extract(mulligan['refs'][mc:])
        init_ids = extract_ids(init_hand)
        init_names = extract(init_hand)
        sb_copy = list(sb_ids)
        kept = []
        for i, cid in enumerate(init_ids):
            if cid in sb_copy:
                sb_copy.remove(cid)
            else:
                kept.append(init_names[i])
        return {'mull': mc, 'kept': kept, 'sent': sb_names, 'recv': recv_names,
                'final': kept + recv_names, 'initial': init_names}
    elif init_hand:
        names = extract(init_hand)
        return {'mull': 0, 'kept': names, 'sent': [], 'recv': [], 'final': names, 'initial': names}
    elif mulligan:
        names = extract(mulligan['refs'])
        return {'mull': mc, 'kept': names, 'sent': [], 'recv': [], 'final': names, 'initial': None}
    return None


def _get_perimeter_from_path(fpath):
    """Estrae il perimetro (SET11, TOP, PRO, INF) dal path del file match."""
    parts = fpath.split('/')
    # path: .../matches/<DATE>/<PERIMETER>/.../<file>.json
    # PERIMETER è il primo livello dopo la cartella data
    for i, p in enumerate(parts):
        if p in ('SET11', 'TOP', 'PRO', 'INF'):
            return p
    return None


def load_matches(our_deck, opp_deck, max_turn=None, game_format='core'):
    """
    Carica tutti i match per un matchup.

    Args:
        our_deck: chiave deck nostro (es. 'AmAm')
        opp_deck: chiave deck avversario (es. 'ES')
        max_turn: se specificato, parsa solo fino a quel turno
        game_format: 'core' (SET11+TOP+PRO) o 'infinity' (INF). Default 'core'.

    Returns:
        lista di dict con chiavi: we_won, length, turns, game_format
    """
    global _normalize_name
    our_colors = DECK_COLORS[our_deck]
    opp_colors = DECK_COLORS[opp_deck]
    # Inizializza normalizzatore nomi carte (log → DB)
    _db = load_cards_db()
    _normalize_name = _build_name_normalizer(_db)
    games = []

    # Cartelle valide per questo formato
    if game_format not in FORMAT_FOLDERS:
        raise ValueError(f"Formato sconosciuto: {game_format}. Validi: {', '.join(VALID_FORMATS)}")
    allowed_folders = FORMAT_FOLDERS[game_format]

    for date_dir in sorted(os.listdir(MATCHES_DIR)):
        date_path = os.path.join(MATCHES_DIR, date_dir)
        if not os.path.isdir(date_path):
            continue
        for root, dirs, files in os.walk(date_path):
            # Filtro per perimetro: salta cartelle non nel formato richiesto
            perim = _get_perimeter_from_path(root)
            if perim is not None and perim not in allowed_folders:
                continue

            for f in files:
                if not f.endswith('.json'):
                    continue
                fpath = os.path.join(root, f)
                try:
                    m = json.load(open(fpath))
                except Exception:
                    continue

                gi = m.get('game_info', {})

                # Safety net: verifica queueShortName per escludere match
                # di altri formati finiti nella cartella sbagliata (es. JA/ZH in SET11)
                queue_prefixes = FORMAT_QUEUE_PREFIXES.get(game_format)
                if queue_prefixes:
                    queue_name = gi.get('queueShortName', '')
                    # TOP/PRO/FRIENDS non hanno filtro queue (contengono mix di queue)
                    if perim in allowed_folders - {'TOP', 'PRO', 'FRIENDS'} and queue_name:
                        if not queue_name.startswith(queue_prefixes):
                            continue

                our_p, opp_p = _identify_sides(gi, our_colors, opp_colors)
                if our_p is None:
                    continue

                logs = m.get('log_data', {}).get('logs', [])
                winner = _find_winner(logs)
                if winner is None:
                    continue

                turns, actual_max = _parse_turn_events(logs, our_p, opp_p, max_turn)

                # Assicura che tutti i turni fino a max_turn esistano
                limit = max_turn or actual_max
                for tn in range(1, limit + 1):
                    if tn not in turns:
                        turns[tn] = _new_turn()

                # OTP: scan for TURN_START turnNumber=1
                we_otp = None
                for e in logs:
                    if e.get('type') == 'TURN_START' and e.get('turnNumber') == 1:
                        first_player = e.get('player')
                        if first_player is not None:
                            we_otp = (int(first_player) == our_p)
                        break

                # Hand info
                hand = _parse_hand(logs, our_p)

                # Player info
                our_info = gi.get(f'player{our_p}', {})
                opp_info = gi.get(f'player{opp_p}', {})

                games.append({
                    'we_won': winner == our_p,
                    'length': actual_max,
                    'turns': turns,
                    'we_otp': we_otp,
                    'hand': hand,
                    'our_name': our_info.get('name', '?'),
                    'opp_name': opp_info.get('name', '?'),
                    'our_mmr': safe_int(our_info.get('mmr', 0)),
                    'opp_mmr': safe_int(opp_info.get('mmr', 0)),
                    'file': fpath,
                    'game_format': game_format,
                })

    return games


def load_cards_db_extended():
    """Loads cards_db + builds ability_cost_map and id_map."""
    db = load_cards_db()
    id_map = {}
    for name, data in db.items():
        if data.get('id'):
            id_map[data['id']] = name
        cid = f"{data.get('set','')}-{data.get('number','')}"
        if cid != '-':
            id_map[cid] = name

    ability_cost_map = _build_ability_cost_map(db)
    return db, ability_cost_map, id_map


def _parse_ability_cost(ability_text):
    """Parse ability costs from text. Returns dict with boost/shift/singer/exert."""
    if not ability_text:
        return {}
    costs = {}
    m = re.search(r'Boost (\d+)', ability_text, re.IGNORECASE)
    if m:
        costs['boost'] = int(m.group(1))
    m = re.search(r'Shift (\d+)', ability_text, re.IGNORECASE)
    if m:
        costs['shift'] = int(m.group(1))
    m = re.search(r'Singer (\d+)', ability_text, re.IGNORECASE)
    if m:
        costs['singer'] = int(m.group(1))
    if re.search(r'Exert\s*[-–—]', ability_text):
        costs['exert'] = True
    return costs


def _build_ability_cost_map(cards_db):
    """Build card_name -> {costs, ability, play_cost} map."""
    cost_map = {}
    for name, data in cards_db.items():
        ability = data.get('ability', '')
        if not ability:
            continue
        costs = _parse_ability_cost(ability)
        if costs:
            cost_map[name] = {
                'costs': costs,
                'ability': ability,
                'play_cost': safe_int(data.get('cost', 0)),
            }
    return cost_map


def load_deck_pool(deck_code, cards_db):
    """Load card pool from tournament decklists in decks_db/."""
    from collections import Counter as _Counter
    folder = DECK_FOLDER.get(deck_code)
    if not folder:
        return {}, []
    deck_dir = os.path.join(DECKS_DB_DIR, folder)
    if not os.path.isdir(deck_dir):
        return {}, []

    card_pool = _Counter()
    deck_count = 0
    all_decks = []
    for f in sorted(os.listdir(deck_dir)):
        if not f.endswith('.json'):
            continue
        try:
            d = json.load(open(os.path.join(deck_dir, f)))
        except Exception:
            continue
        deck_count += 1
        deck_cards = {}
        for c in d.get('cards', []):
            name = c.get('name', '')
            qty = c.get('qty', 0)
            card_pool[name] += qty
            deck_cards[name] = qty
        all_decks.append({
            'player': d.get('player', '?'),
            'rank': d.get('rank', '?'),
            'cards': deck_cards,
        })

    if not deck_count:
        return {}, []

    pool = {}
    for name, total_qty in card_pool.items():
        db_entry = cards_db.get(name, {})
        cost = safe_int(db_entry.get('cost', 0))
        pool[name] = {
            'cost': cost,
            'type': db_entry.get('type', ''),
            'lore': safe_int(db_entry.get('lore', 0)),
            'str': safe_int(db_entry.get('str', 0)),
            'will': safe_int(db_entry.get('will', 0)),
            'ability': db_entry.get('ability', ''),
            'avg_qty': total_qty / deck_count,
            'total_qty': total_qty,
            'in_decks': sum(1 for d in all_decks if name in d['cards']),
            'n_decks': deck_count,
        }
    return pool, all_decks


def build_extended_pool(deck_code, cards_db):
    """Build extended pool with ALL legal cards in deck colors (set 5+)."""
    colors = DECK_COLORS.get(deck_code)
    if not colors:
        return {}
    pool = {}
    for name, d in cards_db.items():
        ink = d.get('ink', '').lower()
        if ink not in colors and ink != 'dual ink':
            continue
        sets = d.get('set', '').split('\n')
        if not any(s in LEGAL_SETS for s in sets):
            continue
        cost = safe_int(d.get('cost', 0))
        if cost == 0:
            continue
        pool[name] = {
            'cost': cost,
            'type': d.get('type', ''),
            'lore': safe_int(d.get('lore', 0)),
            'str': safe_int(d.get('str', 0)),
            'will': safe_int(d.get('will', 0)),
            'ability': d.get('ability', ''),
            'ink': d.get('ink', ''),
            'set': sets[-1],
            'avg_qty': 0,
            'in_decks': 0,
            'n_decks': 1,
        }
    return pool
