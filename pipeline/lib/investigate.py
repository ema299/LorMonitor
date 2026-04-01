"""
Investigazione profonda dei game log: board state, ink budget, sinergie, classificazione sconfitte.

enrich_games() legge i dati GIA' CALCOLATI dal loader (inkwell, ink_spent, play_detail)
e li organizza in strutture comode per i generatori downstream.
NON ricalcola nulla — prende i fatti.
"""

import re
from collections import defaultdict, Counter
from itertools import combinations


def _clear_characters(board, db):
    """Rimuovi tutti i Character da un board Counter. Item/Location restano."""
    for k in list(board.keys()):
        if board[k] <= 0:
            continue
        card_data = db.get(k, {})
        card_type = (card_data.get('type', '') or '').lower()
        if 'character' in card_type:
            board[k] = 0


def _accumulate_cleared(cleared_counter, board, db):
    """Salva quante copie di ogni character stavano nel board prima del clear."""
    for k, count in board.items():
        if count <= 0:
            continue
        card_data = db.get(k, {})
        card_type = (card_data.get('type', '') or '').lower()
        if 'character' in card_type:
            cleared_counter[k] += count


def enrich_games(games, db, ability_cost_map):
    """Arricchisce ogni game con board_state, ink_budget, turn_labels.
    Modifica games in-place.

    Usa i dati gia' estratti dal loader:
    - play_detail (ink_paid, is_shift, is_sung)
    - our_inkwell / opp_inkwell (cumulativo reale)
    - our_ink_spent / opp_ink_spent (somma ink_paid)
    """
    for g in games:
        turns = g['turns']
        max_t = g['length']

        # ── Board state cumulativo per turno ──
        # Traccia chi e' in board, gestisce shift (base consumata)
        our_board = Counter()
        opp_board = Counter()
        board_state = {}

        for t in range(1, max_t + 1):
            td = turns.get(t)
            if not td:
                board_state[t] = {'our': [], 'opp': []}
                continue

            # ── Split per half-turn: rispetta first_player dal log ──
            first = td.get('first_player', 'our')
            second = 'opp' if first == 'our' else 'our'

            # Traccia chars gia' rimossi dal mass banish (evita double-count
            # quando lo stesso nome appare in dead E viene rigiocato dopo)
            mass_cleared = {'our': Counter(), 'opp': Counter()}

            for current_side in (first, second):
                board = our_board if current_side == 'our' else opp_board

                # 1. Aggiungi play (solo carte persistenti)
                play_detail = td.get(f'{current_side}_play_detail', [])
                for p in play_detail:
                    card_data = db.get(p['name'], {})
                    card_type = (card_data.get('type', '') or '').lower()
                    if 'action' in card_type or 'song' in card_type:
                        continue
                    if p['is_shift']:
                        base_name = p['name'].split(' - ')[0] if ' - ' in p['name'] else p['name']
                        for k in list(board.keys()):
                            if k.split(' - ')[0] == base_name and board[k] > 0 and k != p['name']:
                                board[k] -= 1
                                break
                    board[p['name']] = board.get(p['name'], 0) + 1

                # Fallback se play_detail manca
                if not play_detail:
                    for n, c in td.get(f'{current_side}_plays', []):
                        card_data = db.get(n, {})
                        card_type = (card_data.get('type', '') or '').lower()
                        if 'action' in card_type or 'song' in card_type:
                            continue
                        board[n] = board.get(n, 0) + 1

                # 2. Processa ability per effetti di massa (da DB, zero hardcode)
                for ab in td.get(f'{current_side}_abilities', []):
                    card_name = ab.get('card', '')
                    card_db = db.get(card_name, {})
                    ab_text = (card_db.get('ability', '') or '').lower()

                    # Detect "banish all characters" (entrambi i lati)
                    if 'banish all characters' in ab_text \
                            and 'opposing' not in ab_text.split('banish all characters')[0]:
                        _accumulate_cleared(mass_cleared['our'], our_board, db)
                        _accumulate_cleared(mass_cleared['opp'], opp_board, db)
                        _clear_characters(our_board, db)
                        _clear_characters(opp_board, db)
                    # Detect "banish all opposing characters" (senza condizione damage)
                    elif 'banish all opposing characters' in ab_text \
                            and 'damaged' not in ab_text:
                        target_side = 'opp' if current_side == 'our' else 'our'
                        target = opp_board if current_side == 'our' else our_board
                        _accumulate_cleared(mass_cleared[target_side], target, db)
                        _clear_characters(target, db)

                    # Tuck: "putting X, Y, Z on bottom of deck"
                    eff = ab.get('effect', '')
                    m_tuck = re.search(
                        r'putting\s+(.+?)\s+on bottom of deck',
                        eff, re.IGNORECASE)
                    if m_tuck:
                        names_str = m_tuck.group(1)
                        if not re.match(r'^\d+\s+characters?$', names_str.strip()):
                            tucked = [n.strip() for n in names_str.split(',') if n.strip()]
                            target_board = opp_board if current_side == 'our' else our_board
                            for name in tucked:
                                if target_board.get(name, 0) > 0:
                                    target_board[name] -= 1

            # 3. Rimuovi morti e bouncati (fine turno)
            # Skip nomi gia' contabilizzati dal mass banish
            for n in td.get('our_dead', []):
                if mass_cleared['our'].get(n, 0) > 0:
                    mass_cleared['our'][n] -= 1
                    continue
                if our_board.get(n, 0) > 0:
                    our_board[n] -= 1
            for n in td.get('our_bounced', []):
                if our_board.get(n, 0) > 0:
                    our_board[n] -= 1
            for n in td.get('opp_dead', []):
                if mass_cleared['opp'].get(n, 0) > 0:
                    mass_cleared['opp'][n] -= 1
                    continue
                if opp_board.get(n, 0) > 0:
                    opp_board[n] -= 1
            for n in td.get('opp_bounced', []):
                if opp_board.get(n, 0) > 0:
                    opp_board[n] -= 1

            board_state[t] = {
                'our': [n for n, c in our_board.items() if c > 0 for _ in range(c)],
                'opp': [n for n, c in opp_board.items() if c > 0 for _ in range(c)],
            }
        g['board_state'] = board_state

        # ── Ink budget per turno (dai dati reali del loader) ──
        ink_budget = {}
        for t in range(1, max_t + 1):
            td = turns.get(t)
            if not td:
                ink_budget[t] = {'available': t, 'spent_play': 0, 'spent_boost': 0,
                                 'spent': 0, 'remaining': t}
                continue

            available = td.get('our_inkwell', t)  # inkwell reale dal loader
            spent_play = td.get('our_ink_spent', 0)  # ink_paid reale dal loader

            # Boost: costo ink da ability_cost_map
            spent_boost = 0
            for b in td.get('our_boost', []):
                boost_cost = ability_cost_map.get(b['card'], {}).get('costs', {}).get('boost', 0)
                spent_boost += boost_cost

            spent = spent_play + spent_boost

            ink_budget[t] = {
                'available': available,
                'spent_play': spent_play,
                'spent_boost': spent_boost,
                'spent': spent,
                'remaining': available - spent,
            }
        g['ink_budget'] = ink_budget

        # ── Turn labels per clustering (opp plays T1-T5) ──
        for t in range(1, min(max_t + 1, 6)):
            key = f'_t{t}'
            if key not in g:
                g[key] = _classify_turn(turns.get(t, {}), t, 'opp')


def _classify_turn(turn_data, turn, side='opp'):
    """Classify a turn's plays into a label for clustering."""
    plays = turn_data.get(f'{side}_plays', [])
    if not plays:
        return f"Nessun T{turn}"
    names = [n for n, c in plays]
    if len(plays) >= 3:
        return f"Tripla T{turn}"
    if len(plays) == 2:
        sn = _short(names[0])
        if len(sn) <= 20:
            return f"{sn} + altra T{turn}"
        return f"Doppia T{turn}"
    return f"{_short(names[0])} T{turn}"


def _short(name):
    if ' - ' in name:
        base, sub = name.split(' - ', 1)
        return f"{base} ({sub[:4].strip()})"
    return name[:25]


# ═══════════════════════════════════════════════════════════════
# CLASSIFY LOSSES — analisi incrementale
# ═══════════════════════════════════════════════════════════════

def classify_losses(games, db=None):
    """Per ogni sconfitta, analizza il trend di vantaggio turno per turno,
    trova il turno di svolta, e classifica le cause da TUTTI gli eventi.

    Returns: list of dict per ogni loss:
        game_idx, critical_turn, swing, causes[], cards[], trend[], detail,
        alerts[] (con severity cumulativa)
    """
    results = []
    for idx, g in enumerate(games):
        if g['we_won']:
            continue
        analysis = _analyze_loss(g, db=db)
        analysis['game_idx'] = idx
        results.append(analysis)
    return results


def _count_discards_from_abilities(td, side):
    """Conta carte scartate da ability (draw N + discard N = card selection, net 0)."""
    n = 0
    for ab in td.get(f'{side}_abilities', []):
        eff = (ab.get('effect', '') or '').lower()
        if 'discard' in eff:
            m = re.search(r'discards?\s+(\d+)', eff)
            if m:
                n += int(m.group(1))
    return n


def _compute_trend(g, db=None):
    """Calcola il vantaggio (nostro - avversario) turno per turno.

    6 componenti:
    - board: pezzi nostri - pezzi avversari (legacy)
    - lore: lore nostra - lore avversaria (legacy)
    - draw: draw NET cumulato (draw - discard da ability) (legacy, corretto)
    - lore_pot: lore potenziale board (somma lore value dei pezzi)
    - removal: removal pressure cumulativo (loro rimossi - nostri rimossi)
    - hand: stima carte in mano avversario (net) + carte filtrate cumulativo
    """
    turns = g['turns']
    max_t = min(g['length'], 12)
    bs = g.get('board_state', {})

    our_draw_cum = 0
    opp_draw_cum = 0
    our_discard_cum = 0
    opp_discard_cum = 0
    cum_our_removed = 0
    cum_opp_removed = 0
    opp_filtered_cum = 0  # carte totali viste da selection (draw+discard)
    opp_hand_est = 7  # stima mano avversario (7 iniziali)
    prev_our_lore = 0
    prev_opp_lore = 0
    trend = []

    for t in range(1, max_t + 1):
        td = turns.get(t, {})

        # ═══ LEGACY: board count ═══
        our_board_names = bs.get(t, {}).get('our', [])
        opp_board_names = bs.get(t, {}).get('opp', [])
        board_adv = len(our_board_names) - len(opp_board_names)

        # ═══ LEGACY: lore ═══
        our_lore = td.get('our_lore', 0)
        opp_lore = td.get('opp_lore', 0)
        lore_adv = our_lore - opp_lore

        # ═══ LEGACY (corrected): draw NET (draw - discard da ability) ═══
        our_drawn_t = len(td.get('our_drawn', []))
        opp_drawn_t = len(td.get('opp_drawn', []))
        our_discard_t = _count_discards_from_abilities(td, 'our')
        opp_discard_t = _count_discards_from_abilities(td, 'opp')
        our_draw_cum += our_drawn_t - our_discard_t
        opp_draw_cum += opp_drawn_t - opp_discard_t
        draw_adv = our_draw_cum - opp_draw_cum

        # ═══ NUOVO 1: lore potential (clock) ═══
        if db:
            our_lore_pot = sum(int(db.get(c, {}).get('lore', 0) or 0)
                               for c in our_board_names)
            opp_lore_pot = sum(int(db.get(c, {}).get('lore', 0) or 0)
                               for c in opp_board_names)
        else:
            # Fallback: stima 1L per pezzo
            our_lore_pot = len(our_board_names)
            opp_lore_pot = len(opp_board_names)
        lore_pot_adv = our_lore_pot - opp_lore_pot

        # ═══ NUOVO 2: removal pressure (attrito cumulativo) ═══
        our_dead_n = len(td.get('our_dead', []))
        our_bounced_n = len(td.get('our_bounced', []))
        opp_dead_n = len(td.get('opp_dead', []))
        opp_bounced_n = len(td.get('opp_bounced', []))
        cum_our_removed += our_dead_n + our_bounced_n
        cum_opp_removed += opp_dead_n + opp_bounced_n
        removal_adv = cum_opp_removed - cum_our_removed

        # ═══ NUOVO 3: hand pressure (risorse + qualità) ═══
        # Stima mano avversario
        if t > 1:
            opp_hand_est += 1  # normal draw
        opp_played_t = len(td.get('opp_plays', []))
        opp_net_draw = opp_drawn_t - opp_discard_t
        opp_hand_est += opp_net_draw - opp_played_t - 1  # -1 for inking
        opp_hand_est = max(0, opp_hand_est)

        # Card selection: carte totali filtrate (anche se scartate)
        opp_filtered_cum += opp_discard_t  # solo la parte scartata = selection

        # Lore velocity (delta questo turno)
        opp_lore_vel = opp_lore - prev_opp_lore
        our_lore_vel = our_lore - prev_our_lore
        prev_our_lore = our_lore
        prev_opp_lore = opp_lore

        advantage = board_adv + lore_adv + draw_adv
        trend.append({
            'turn': t,
            'advantage': advantage,
            # Legacy
            'board_adv': board_adv,
            'lore_adv': lore_adv,
            'draw_adv': draw_adv,
            # Nuovi
            'lore_pot_adv': lore_pot_adv,
            'opp_lore_pot': opp_lore_pot,
            'our_lore_pot': our_lore_pot,
            'removal_adv': removal_adv,
            'opp_hand_est': opp_hand_est,
            'opp_filtered_cum': opp_filtered_cum,
            'opp_lore_vel': opp_lore_vel,
        })

    return trend


def _detect_alerts(trend):
    """Genera alert per turno basati sui 6 componenti. Severity cumulativa.

    Returns: list of {turn, severity, alerts[], detail}
    Severity: 'warning' (1 alert), 'danger' (2), 'critical' (3+)
    """
    all_alerts = []
    for pt in trend:
        t = pt['turn']
        alerts = []

        # CLOCK: lore potential avversario alta, gap lore non sufficiente
        if pt['opp_lore_pot'] >= 5 and pt['lore_adv'] <= 3:
            alerts.append(f"CLOCK: avv genera {pt['opp_lore_pot']}L/turno, gap lore solo {pt['lore_adv']:+d}")

        # RUSH: lore pot alta + mano vuota
        if pt['opp_lore_pot'] >= 5 and pt['opp_hand_est'] <= 1:
            if pt['opp_filtered_cum'] >= 6:
                alerts.append(f"RUSH SELETTIVO: mano~{pt['opp_hand_est']} ma filtrate {pt['opp_filtered_cum']} carte, pezzi in board scelti")
            else:
                alerts.append(f"RUSH PURO: mano~{pt['opp_hand_est']}, si esaurisce")

        # ENGINE: lore pot alta + mano piena (card advantage reale)
        if pt['opp_lore_pot'] >= 5 and pt['opp_hand_est'] >= 4:
            alerts.append(f"ENGINE: mano~{pt['opp_hand_est']} con {pt['opp_lore_pot']}L/turno, non si esaurisce")

        # ATTRITO: removal pressure pesante
        if pt['removal_adv'] <= -4:
            alerts.append(f"ATTRITO: {pt['removal_adv']:+d} removal cumulato, ci dissanguano")

        # BURST: lore velocity alta
        if pt['opp_lore_vel'] >= 5:
            alerts.append(f"BURST: +{pt['opp_lore_vel']}L questo turno")

        # FALSO POSITIVO: vecchio trend positivo ma situazione reale negativa
        if pt['advantage'] >= 10 and pt['lore_pot_adv'] <= -5:
            alerts.append(f"FALSO POSITIVO: trend +{pt['advantage']} ma lore_pot {pt['lore_pot_adv']:+d}")

        if alerts:
            n = len(alerts)
            severity = 'critical' if n >= 3 else ('danger' if n >= 2 else 'warning')
            all_alerts.append({
                'turn': t,
                'severity': severity,
                'alerts': alerts,
                'n_alerts': n,
            })

    return all_alerts


def _find_critical_turn_component(trend, component):
    """Trova il turno critico per UNA componente (board_adv, lore_adv, draw_adv).

    Cerca il primo turno dove la componente cala e non risale piu'.
    Returns (turn, swing) o (None, 0) se non c'e' calo permanente.
    """
    if len(trend) < 2:
        return None, 0

    best_critical = None
    best_swing = 0

    for i in range(1, len(trend)):
        drop = trend[i][component] - trend[i-1][component]
        if drop >= 0:
            continue

        # Controlla se risale dopo
        pre_level = trend[i-1][component]
        recovers = False
        for j in range(i + 1, len(trend)):
            if trend[j][component] >= pre_level:
                recovers = True
                break

        if not recovers and drop < best_swing:
            best_swing = drop
            best_critical = trend[i]['turn']

    return best_critical, best_swing


def _find_critical_turns(trend):
    """Trova i turni critici per OGNI componente separatamente.

    Returns: list of {component, turn, swing}, ordinati per turno.
    Il primo e' la causa primaria (arriva prima).
    """
    criticals = []

    for comp, label in [('draw_adv', 'draw'), ('board_adv', 'board'), ('lore_adv', 'lore')]:
        turn, swing = _find_critical_turn_component(trend, comp)
        if turn is not None and swing < -1:  # soglia minima: calo > 1
            criticals.append({
                'component': label,
                'turn': turn,
                'swing': swing,
            })

    # Ordina per turno (la causa primaria e' quella che arriva prima)
    criticals.sort(key=lambda x: x['turn'])

    # Fallback: se nessuna componente ha calo netto, usa il vantaggio aggregato
    if not criticals:
        worst = min(trend, key=lambda x: x['advantage'])
        worst_idx = trend.index(worst)
        prev_idx = max(0, worst_idx - 1)
        swing = worst['advantage'] - trend[prev_idx]['advantage']
        criticals.append({
            'component': 'overall',
            'turn': worst['turn'],
            'swing': swing,
        })

    return criticals


def _classify_causes_at_turn(g, turn):
    """Guarda TUTTO quello che e' successo al turno critico e classifica le cause.

    Returns: (causes_list, cards_list, detail_string)
    """
    td = g['turns'].get(turn, {})
    causes = []
    cards = []

    # ── Dai play avversari ──
    for p in td.get('opp_play_detail', []):
        if p['is_shift']:
            causes.append('shift')
            cards.append(p['name'])
        elif p['is_sung']:
            causes.append('song')
            cards.append(p['name'])
        else:
            cards.append(p['name'])

    # ── Dai quester avversari (chi genera lore) ──
    quest_lore = sum(l for _, l in td.get('opp_quests', []))
    for name, lore in td.get('opp_quests', []):
        if lore >= 2 and name not in cards:
            cards.append(name)

    # ── Dalle ability avversarie ──
    for ab in td.get('opp_abilities', []):
        eff = ab.get('effect', '').lower()
        if 'had no effect' in eff or 'option' in eff:
            continue
        if 'draw' in eff or 'drew' in eff:
            causes.append('draw_engine')
        if 'inkwell' in eff or 'additional ink' in eff:
            causes.append('ramp')
        if 'damage' in eff:
            causes.append('ability_damage')
        if 'exert' in eff:
            causes.append('ability_exert')
        if 'banish' in eff:
            causes.append('ability_banish')
        if 'return' in eff or 'bottom' in eff or 'shuffle' in eff:
            causes.append('ability_bounce')

    # ── Dai challenge avversari (killano nostri pezzi) ──
    for ch in td.get('opp_challenges', []):
        if ch.get('def_killed'):
            causes.append('challenge_kill')

    # ── Dai nostri pezzi rimossi ──
    n_dead = len(td.get('our_dead', []))
    n_bounced = len(td.get('our_bounced', []))
    if n_dead >= 2:
        causes.append('multi_kill')
    elif n_dead == 1:
        causes.append('removal')
    if n_bounced >= 2:
        causes.append('mass_bounce')
    elif n_bounced == 1:
        causes.append('bounced')

    # ── Dalla lore avversaria ──
    if quest_lore >= 4:
        causes.append('lore_burst')
    elif quest_lore >= 2:
        causes.append('lore_pressure')

    # ── Dal draw advantage avversario ──
    if td.get('opp_drawn'):
        causes.append('card_advantage')

    # ── Dal ramp avversario ──
    if td.get('opp_ramp'):
        causes.append('ramp')

    # ── Dal support avversario ──
    if td.get('opp_support'):
        causes.append('support')

    # Deduplica
    causes = list(dict.fromkeys(causes))
    cards = list(dict.fromkeys(cards))

    # Costruisci detail leggibile
    detail_parts = []
    if 'shift' in causes:
        shift_cards = [p['name'] for p in td.get('opp_play_detail', []) if p['is_shift']]
        detail_parts.append(f"shift {', '.join(_short(c) for c in shift_cards)}")
    if 'song' in causes:
        song_cards = [p['name'] for p in td.get('opp_play_detail', []) if p['is_sung']]
        detail_parts.append(f"song {', '.join(_short(c) for c in song_cards)}")
    if 'draw_engine' in causes or 'card_advantage' in causes:
        n_drawn = len(td.get('opp_drawn', []))
        detail_parts.append(f"draw +{n_drawn}")
    if n_dead:
        dead_names = ', '.join(_short(n) for n in td['our_dead'][:3])
        detail_parts.append(f"kill {dead_names}")
    if n_bounced:
        bounce_names = ', '.join(_short(n) for n in td['our_bounced'][:3])
        detail_parts.append(f"tuck {bounce_names}")
    if 'lore_burst' in causes or 'lore_pressure' in causes:
        detail_parts.append(f"+{quest_lore}L")
    if 'ramp' in causes:
        detail_parts.append("ramp")

    detail = '; '.join(detail_parts) if detail_parts else 'vantaggio graduale'

    return causes, cards, detail


def _analyze_loss(g, db=None):
    """Analisi completa di una sconfitta con metodo incrementale.

    Trova turni critici per OGNI componente (draw, board, lore) separatamente.
    Il critical_turn principale e' quello della prima componente a crollare.
    """
    trend = _compute_trend(g, db=db)
    criticals = _find_critical_turns(trend)

    # Turno critico principale = primo a crollare
    primary = criticals[0]
    critical_turn = primary['turn']

    # Raccogli cause e carte da TUTTI i turni critici
    all_causes = []
    all_cards = []
    all_details = []

    for crit in criticals:
        causes, cards, detail = _classify_causes_at_turn(g, crit['turn'])
        if causes:
            all_causes.extend(causes)
            all_cards.extend(cards)
            all_details.append(f"T{crit['turn']} {crit['component']}: {detail}")

    # Se ancora vuote, guarda turni intorno al primo critico
    if not all_causes:
        for t_offset in [1, -1, 2]:
            t_check = critical_turn + t_offset
            if 1 <= t_check <= g['length']:
                causes, cards, detail = _classify_causes_at_turn(g, t_check)
                if causes:
                    all_causes = causes
                    all_cards = cards
                    all_details = [detail]
                    break
        if not all_causes:
            all_causes = ['gradual']
            all_details = ['vantaggio graduale avversario']

    # Deduplica mantenendo ordine
    all_causes = list(dict.fromkeys(all_causes))
    all_cards = list(dict.fromkeys(all_cards))

    # ── Lore speed: a che turno l'avversario raggiunge 10/15/20 lore ──
    turns = g['turns']
    max_t = g['length']
    opp_reach_10 = None
    opp_reach_15 = None
    opp_reach_20 = None
    best_lore_burst = 0
    best_lore_burst_turn = 0

    for t in range(1, min(max_t + 1, 13)):
        td = turns.get(t, {})
        opp_lore = td.get('opp_lore', 0)
        if opp_lore >= 10 and opp_reach_10 is None:
            opp_reach_10 = t
        if opp_lore >= 15 and opp_reach_15 is None:
            opp_reach_15 = t
        if opp_lore >= 20 and opp_reach_20 is None:
            opp_reach_20 = t
        # Lore burst: lore questata in un singolo turno
        quest_lore_t = sum(l for _, l in td.get('opp_quests', []))
        if quest_lore_t > best_lore_burst:
            best_lore_burst = quest_lore_t
            best_lore_burst_turn = t

    # ── Alert detection ──
    alerts = _detect_alerts(trend)

    return {
        'critical_turn': critical_turn,
        'swing': primary['swing'],
        'causes': all_causes,
        'cards': all_cards,
        'detail': ' | '.join(all_details),
        'trend': [t['advantage'] for t in trend],
        'trend_components': {
            'board': [t['board_adv'] for t in trend],
            'lore': [t['lore_adv'] for t in trend],
            'draw': [t['draw_adv'] for t in trend],
            'lore_pot': [t['lore_pot_adv'] for t in trend],
            'removal': [t['removal_adv'] for t in trend],
            'opp_hand': [t['opp_hand_est'] for t in trend],
            'opp_lore_pot': [t['opp_lore_pot'] for t in trend],
            'opp_filtered': [t['opp_filtered_cum'] for t in trend],
            'opp_lore_vel': [t['opp_lore_vel'] for t in trend],
        },
        'alerts': alerts,
        'criticals': criticals,
        'lore_speed': {
            'game_length': max_t,
            'opp_reach_10': opp_reach_10,
            'opp_reach_15': opp_reach_15,
            'opp_reach_20': opp_reach_20,
            'best_lore_burst': best_lore_burst,
            'best_lore_burst_turn': best_lore_burst_turn,
        },
    }


def analyze_synergies(games, db, ability_cost_map):
    """Analisi globale sinergie. Ritorna dict con combo intra-turno, setup-payoff, ink efficiency."""
    total_w = sum(1 for g in games if g['we_won'])
    total_l = len(games) - total_w
    baseline_wr = total_w / len(games) * 100 if games else 50

    # Intra-turn combos
    combo_w = Counter()
    combo_l = Counter()
    combo_turns = defaultdict(list)

    for g in games:
        for t in range(1, min(g['length'] + 1, 11)):
            td = g['turns'].get(t)
            if not td:
                continue
            active = set()
            for n, c in td.get('our_plays', []):
                active.add(n)
            for n, lore in td.get('our_quests', []):
                active.add(n)
            for ch in td.get('our_challenges', []):
                active.add(ch['attacker'])
            for ab in td.get('our_abilities', []):
                active.add(ab['card'])

            for pair in combinations(sorted(active), 2):
                key = pair
                if g['we_won']:
                    combo_w[key] += 1
                else:
                    combo_l[key] += 1
                combo_turns[key].append(t)

    intra_combos = []
    for key in set(combo_w) | set(combo_l):
        w, l = combo_w.get(key, 0), combo_l.get(key, 0)
        total = w + l
        if total < 3:
            continue
        wr = w / total * 100
        avg_t = sum(combo_turns[key]) / len(combo_turns[key])
        intra_combos.append({
            'cards': key, 'wins': w, 'losses': l, 'total': total,
            'wr': wr, 'delta': wr - baseline_wr, 'avg_turn': avg_t,
        })
    intra_combos.sort(key=lambda x: -x['delta'])

    # Setup-payoff cross-turn
    setup_w = Counter()
    setup_l = Counter()
    for g in games:
        bs = g.get('board_state', {})
        for t in range(2, min(g['length'] + 1, 11)):
            board_prev = bs.get(t - 1, {}).get('our', [])
            if not board_prev:
                continue
            td = g['turns'].get(t, {})
            actors = set()
            for n, c in td.get('our_plays', []):
                actors.add(n)
            for ab in td.get('our_abilities', []):
                actors.add(ab['card'])
            for ch in td.get('our_challenges', []):
                actors.add(ch['attacker'])

            for actor in actors:
                for setup in board_prev:
                    if setup == actor:
                        continue
                    key = (setup, actor)
                    if g['we_won']:
                        setup_w[key] += 1
                    else:
                        setup_l[key] += 1

    setup_payoff = []
    for key in set(setup_w) | set(setup_l):
        w, l = setup_w.get(key, 0), setup_l.get(key, 0)
        total = w + l
        if total < 3:
            continue
        wr = w / total * 100
        setup_payoff.append({
            'setup': key[0], 'payoff': key[1],
            'wins': w, 'losses': l, 'total': total,
            'wr': wr, 'delta': wr - baseline_wr,
        })
    setup_payoff.sort(key=lambda x: -x['delta'])

    # Ink efficiency W vs L (ora con dati reali dal loader)
    ink_eff = {}
    for t in range(1, 8):
        w_spend = []
        l_spend = []
        for g in games:
            td = g['turns'].get(t)
            if not td:
                continue
            spent = td.get('our_ink_spent', 0)
            if g['we_won']:
                w_spend.append(spent)
            else:
                l_spend.append(spent)
        ink_eff[t] = {
            'w_avg': sum(w_spend) / len(w_spend) if w_spend else 0,
            'l_avg': sum(l_spend) / len(l_spend) if l_spend else 0,
        }

    return {
        'intra_turn_combos': intra_combos[:30],
        'setup_payoff': setup_payoff[:30],
        'ink_efficiency': ink_eff,
        'baseline_wr': baseline_wr,
    }
