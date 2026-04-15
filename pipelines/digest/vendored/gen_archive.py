# VENDORED da legacy gen_archive.py @ commit 58288f36a6e41b1830efab0941223e7160b84450
# Congelato 15/04/2026 per Sprint P1.5 — NON MODIFICARE LOGICA.
# Fix applicati: solo import paths. Vedi docs/SPRINT_P1.5_VENDORED.md.
"""
Genera l'archivio JSON strutturato per un matchup.
L'archivio contiene tutte le partite con dettaglio turno per turno
e gli aggregati precalcolati. Pensato per essere letto dall'LLM.
"""

import json, os
from collections import Counter, defaultdict
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')


def generate_archive(our, opp, our_long, opp_long, games, loss_classes,
                      game_format='core', db=None):
    """Genera e salva l'archivio JSON.

    Args:
        our, opp: sigle deck (es. 'AmAm', 'ES')
        our_long, opp_long: nomi lunghi (es. 'Amber-Amethyst', 'Emerald-Sapphire')
        games: lista game arricchiti da enrich_games()
        loss_classes: output di classify_losses()
        game_format: 'core' o 'infinity'
        db: cards_db dict (per detection dinamica meccaniche)

    Returns:
        path del file salvato
    """
    loss_by_idx = {lc['game_idx']: lc for lc in loss_classes}

    archive = {
        'metadata': _build_metadata(our, opp, our_long, opp_long, games, game_format),
        'games': [_build_game(idx, g, loss_by_idx.get(idx)) for idx, g in enumerate(games)],
        'aggregates': _build_aggregates(games, loss_classes, db=db),
    }

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    # infinity: suffisso _inf nel nome file
    fmt_suffix = '_inf' if game_format == 'infinity' else ''
    out_path = os.path.join(OUTPUT_DIR, f'archive_{our}_vs_{opp}{fmt_suffix}.json')
    with open(out_path, 'w') as f:
        json.dump(archive, f, indent=2, default=str)

    return out_path


def _build_metadata(our, opp, our_long, opp_long, games, game_format='core'):
    # Date delle partite
    dates = Counter()
    for g in games:
        date_folder = g.get('file', '').split('/')[-3] if g.get('file') else 'unknown'
        dates[date_folder] += 1

    return {
        'our_deck': our,
        'opp_deck': opp,
        'our_long': our_long,
        'opp_long': opp_long,
        'game_format': game_format,
        'last_updated': datetime.now().strftime('%Y-%m-%d'),
        'total_games': len(games),
        'wins': sum(1 for g in games if g['we_won']),
        'losses': sum(1 for g in games if not g['we_won']),
        'games_by_date': dict(sorted(dates.items())),
    }


def _build_game(idx, g, loss_analysis):
    game_entry = {
        'id': idx,
        'file': g.get('file', '').split('/')[-1],
        'date': g.get('file', '').split('/')[-3] if g.get('file') else '',
        'result': 'W' if g['we_won'] else 'L',
        'we_otp': g.get('we_otp'),
        'our_name': g.get('our_name', '?'),
        'opp_name': g.get('opp_name', '?'),
        'our_mmr': g.get('our_mmr', 0),
        'opp_mmr': g.get('opp_mmr', 0),
        'length': g['length'],
        'turns': [],
    }

    for t in range(1, min(g['length'] + 1, 13)):
        game_entry['turns'].append(_build_turn(g, t))

    if loss_analysis:
        game_entry['analysis'] = {
            'criticals': loss_analysis['criticals'],
            'causes': loss_analysis['causes'],
            'cards': loss_analysis['cards'],
            'detail': loss_analysis['detail'],
            'trend_components': loss_analysis['trend_components'],
            'trend_total': loss_analysis['trend'],
            'lore_speed': loss_analysis.get('lore_speed', {}),
            'alerts': loss_analysis.get('alerts', []),
        }

    return game_entry


def _build_turn(g, t):
    td = g['turns'].get(t, {})
    bs = g.get('board_state', {}).get(t, {})

    return {
        't': t,
        'opp_plays': [
            {k: v for k, v in {
                'name': p['name'], 'ink_paid': p['ink_paid'],
                'is_shift': p['is_shift'], 'shift_cost': p['shift_cost'],
                'is_sung': p['is_sung'], 'singer': p.get('singer', '')
            }.items() if v or k in ('name', 'ink_paid')}
            for p in td.get('opp_play_detail', [])
        ],
        'our_plays': [
            {k: v for k, v in {
                'name': p['name'], 'ink_paid': p['ink_paid'],
                'is_shift': p['is_shift'], 'is_sung': p['is_sung'],
                'singer': p.get('singer', '')
            }.items() if v or k in ('name', 'ink_paid')}
            for p in td.get('our_play_detail', [])
        ],
        'opp_abilities': [
            {k: v for k, v in {'card': a['card'], 'effect': a['effect'],
             'ability': a.get('ability', ''), 'target': a.get('target', '')}.items()
             if v or k in ('card', 'effect')}
            for a in td.get('opp_abilities', [])
            if 'had no effect' not in a.get('effect', '').lower()
        ],
        'our_abilities': [
            {k: v for k, v in {'card': a['card'], 'effect': a['effect'],
             'ability': a.get('ability', ''), 'target': a.get('target', '')}.items()
             if v or k in ('card', 'effect')}
            for a in td.get('our_abilities', [])
            if 'had no effect' not in a.get('effect', '').lower()
        ],
        'opp_drawn': [{'name': n, 'cost': c} for n, c in td.get('opp_drawn', [])],
        'our_drawn': [{'name': n, 'cost': c} for n, c in td.get('our_drawn', [])],
        'opp_quests': [{'name': n, 'lore': l} for n, l in td.get('opp_quests', [])],
        'our_quests': [{'name': n, 'lore': l} for n, l in td.get('our_quests', [])],
        'our_dead': td.get('our_dead', []),
        'opp_dead': td.get('opp_dead', []),
        'our_bounced': td.get('our_bounced', []),
        'opp_bounced': td.get('opp_bounced', []),
        'opp_challenges': [
            {'attacker': c['attacker'], 'defender': c['defender'],
             'def_killed': c['def_killed'], 'atk_killed': c['atk_killed']}
            for c in td.get('opp_challenges', [])
        ],
        'our_challenges': [
            {'attacker': c['attacker'], 'defender': c['defender'],
             'def_killed': c['def_killed'], 'atk_killed': c['atk_killed']}
            for c in td.get('our_challenges', [])
        ],
        'opp_revealed': td.get('opp_revealed', []),
        'our_revealed': td.get('our_revealed', []),
        'opp_damage': td.get('opp_damage', []),
        'our_damage': td.get('our_damage', []),
        'opp_support': [(s[0], s[1]) for s in td.get('opp_support', [])],
        'our_support': [(s[0], s[1]) for s in td.get('our_support', [])],
        'board_state': {
            'our': sorted(bs.get('our', [])),
            'opp': sorted(bs.get('opp', [])),
        },
        'inkwell': {'our': td.get('our_inkwell', t), 'opp': td.get('opp_inkwell', t)},
        'ink_spent': {'our': td.get('our_ink_spent', 0), 'opp': td.get('opp_ink_spent', 0)},
        'lore': {'our': td.get('our_lore', 0), 'opp': td.get('opp_lore', 0)},
        'first_player': td.get('first_player', 'our'),
        # Event log ordinato per half-turn (check/review layer per replay)
        'event_log': td.get('event_log', []),
    }


def _build_aggregates(games, loss_classes, db=None):
    all_causes = Counter()
    crit_turns = Counter()
    card_at_crit = Counter()
    combo_at_crit = Counter()
    component_primary = Counter()

    for lc in loss_classes:
        for c in lc['causes']:
            all_causes[c] += 1
        crit_turns[lc['critical_turn']] += 1
        if lc.get('criticals'):
            component_primary[lc['criticals'][0]['component']] += 1
        if lc['cards']:
            card_at_crit[lc['cards'][0]] += 1

        # Combo al turno critico
        g = games[lc['game_idx']]
        ct = lc['critical_turn']
        td = g['turns'].get(ct, {})
        combo_cards = []
        for p in td.get('opp_play_detail', []):
            tag = p['name']
            if p['is_shift']:
                tag += ' [SHIFT]'
            elif p['is_sung']:
                tag += ' [SONG]'
            combo_cards.append(tag)
        if len(combo_cards) >= 2:
            impact = len(td.get('our_dead', [])) + len(td.get('our_bounced', [])) + len(td.get('opp_drawn', []))
            if impact >= 2:
                combo_at_crit[tuple(sorted(combo_cards))] += 1

    # Trend medio per componente (legacy + nuovi)
    all_comps = ['draw', 'board', 'lore', 'lore_pot', 'removal',
                 'opp_hand', 'opp_lore_pot', 'opp_filtered', 'opp_lore_vel']
    avg_trends = {c: [] for c in all_comps}
    for i in range(12):
        for comp in all_comps:
            vals = [lc['trend_components'][comp][i] for lc in loss_classes
                    if comp in lc['trend_components'] and i < len(lc['trend_components'][comp])]
            avg_trends[comp].append(round(sum(vals) / len(vals), 1) if vals else 0)

    # Alert aggregati: frequenza per severity, tipo e turno
    alert_freq = Counter()
    alert_by_turn = defaultdict(list)
    alert_type_freq = Counter()  # CLOCK, RUSH, ENGINE, ATTRITO, BURST, FALSO POSITIVO
    alert_type_by_turn = defaultdict(lambda: Counter())
    losses_with_alert_type = defaultdict(set)  # type -> set of game_idx
    for lc in loss_classes:
        for a in lc.get('alerts', []):
            alert_freq[a['severity']] += 1
            alert_by_turn[a['turn']].append(a['severity'])
            for alert_text in a.get('alerts', []):
                # Extract alert type from text (first word before ':')
                atype = alert_text.split(':')[0].strip()
                alert_type_freq[atype] += 1
                alert_type_by_turn[a['turn']][atype] += 1
                losses_with_alert_type[atype].add(lc['game_idx'])

    # Ability piu' triggerate nelle loss
    ability_freq = Counter()
    for lc in loss_classes:
        g = games[lc['game_idx']]
        for crit in lc['criticals']:
            td = g['turns'].get(crit['turn'], {})
            for ab in td.get('opp_abilities', []):
                eff = ab.get('effect', '').lower()
                if 'had no effect' in eff:
                    continue
                ability_freq[ab['card'] + ': ' + ab['effect'][:60]] += 1

    # Partite esempio per carta chiave
    # Per ogni carta top, scegli la partita con swing piu' netto (piu' chiara)
    card_examples = {}
    card_losses = defaultdict(list)
    for lc in loss_classes:
        if lc['cards']:
            card_losses[lc['cards'][0]].append(lc)

    for card, analyses in card_losses.items():
        if len(analyses) < 2:
            continue
        # Ordina per swing (piu' negativo = piu' chiaro)
        best = sorted(analyses, key=lambda a: a['swing'])[:2]
        card_examples[card] = {
            'count': len(analyses),
            'avg_critical_turn': round(sum(a['critical_turn'] for a in analyses) / len(analyses), 1),
            'example_game_ids': [a['game_idx'] for a in best],
            'top_causes': dict(Counter(c for a in analyses for c in a['causes']).most_common(4)),
            'component_primary': Counter(a['criticals'][0]['component'] for a in analyses).most_common(1)[0][0],
        }

    # Partite esempio per combo
    combo_examples = []
    combo_losses = defaultdict(list)
    for lc in loss_classes:
        g = games[lc['game_idx']]
        ct = lc['critical_turn']
        td = g['turns'].get(ct, {})
        cards = []
        for p in td.get('opp_play_detail', []):
            tag = p['name']
            if p['is_shift']:
                tag += ' [SHIFT]'
            elif p['is_sung']:
                tag += ' [SONG]'
            cards.append(tag)
        if len(cards) >= 2:
            impact = len(td.get('our_dead', [])) + len(td.get('our_bounced', [])) + len(td.get('opp_drawn', []))
            if impact >= 2:
                key = tuple(sorted(cards))
                combo_losses[key].append({'game_idx': lc['game_idx'], 'turn': ct,
                                           'impact_dead': len(td.get('our_dead', [])),
                                           'impact_bounced': len(td.get('our_bounced', [])),
                                           'impact_drawn': len(td.get('opp_drawn', []))})

    for combo, entries in sorted(combo_losses.items(), key=lambda x: -len(x[1])):
        if len(entries) < 2:
            continue
        avg_dead = sum(e['impact_dead'] for e in entries) / len(entries)
        avg_bounced = sum(e['impact_bounced'] for e in entries) / len(entries)
        avg_drawn = sum(e['impact_drawn'] for e in entries) / len(entries)
        combo_examples.append({
            'cards': list(combo),
            'count': len(entries),
            'avg_turn': round(sum(e['turn'] for e in entries) / len(entries), 1),
            'avg_impact': {'dead': round(avg_dead, 1), 'bounced': round(avg_bounced, 1), 'drawn': round(avg_drawn, 1)},
            'example_game_ids': [entries[0]['game_idx'], entries[-1]['game_idx']],
        })
    combo_examples.sort(key=lambda x: -x['count'])

    # ── Lore speed: aggregato da classify_losses (ogni loss ha lore_speed) ──
    reach_10 = Counter()
    reach_15 = Counter()
    loss_lengths = Counter()
    fast_loss_ids = []
    lore_bursts = []

    for lc in loss_classes:
        ls = lc.get('lore_speed', {})
        gl = ls.get('game_length', 0)
        if gl:
            loss_lengths[gl] += 1
        r10 = ls.get('opp_reach_10')
        r15 = ls.get('opp_reach_15')
        if r10:
            reach_10[r10] += 1
        if r15:
            reach_15[r15] += 1
            if r15 <= 6:
                fast_loss_ids.append(lc['game_idx'])
        burst = ls.get('best_lore_burst', 0)
        burst_t = ls.get('best_lore_burst_turn', 0)
        if burst >= 5:
            lore_bursts.append({'game_id': lc['game_idx'], 'turn': burst_t, 'lore': burst})

    lore_bursts.sort(key=lambda x: -x['lore'])

    lore_speed = {
        'reach_10': dict(sorted(reach_10.items())),
        'reach_15': dict(sorted(reach_15.items())),
        'loss_length': dict(sorted(loss_lengths.items())),
        'lore_burst': lore_bursts[:10],
        'fast_loss_ids': sorted(set(fast_loss_ids))[:5],
    }

    # ── Build cards_dict for dynamic mechanic detection ──
    from pipelines.digest.vendored.cards_dict import build_cards_dict
    cards_dict = build_cards_dict(db, legal_only=False) if db else {}

    # Pre-compute sets of mass-removal cards from DB (no hardcoded names)
    _MASS_REMOVAL_TYPES = {'banish_all', 'banish_cond', 'tuck_all', 'damage_all'}
    mass_removal_cards = {
        name for name, c in cards_dict.items()
        if c.get('removal_type') in _MASS_REMOVAL_TYPES
    }
    # Cards with sing_together (e.g. Under the Sea, Circle of Life)
    sing_together_cards = {
        name for name, c in cards_dict.items()
        if c.get('sing_together_cost')
    }
    # Recursion cards: ability mentions "from discard" or "return"
    recursion_ability_cards = {
        name for name, c in cards_dict.items()
        if c.get('ability') and any(
            w in c['ability'].lower()
            for w in ['from your discard', 'from their discard',
                       'from discard', 'play a character from']
        )
    }
    # Hand strip cards: ability forces opponent discard
    hand_strip_ability_cards = {
        name for name, c in cards_dict.items()
        if c.get('ability') and 'discard' in c['ability'].lower()
        and any(w in c['ability'].lower()
                for w in ['chosen opposing', 'each opponent', 'opponent discards',
                          'opposing player', 'choose and discard'])
    }

    # ── Analisi 3 livelli per ogni loss ──
    def _tag_mechanics(lc, g):
        """Tag a loss with 3-level analysis: patterns, keywords, abilities.

        Returns dict with 3 keys:
            'patterns':  {flag: set(card_names)}  — composite multi-turn patterns (WIPE, RECURSION, etc.)
            'keywords':  Counter(keyword)         — keyword counts from played cards (Ward, Rush, etc.)
            'keywords_cards': {kw: Counter(card)} — which cards contributed each keyword
            'abilities': Counter(trigger_effect)   — ability profile counts (etb_banish, quest_draw, etc.)
            'abilities_cards': {key: Counter(card)} — which cards contributed each ability

        Detection is fully dynamic via cards_db — zero hardcoded card names.
        """
        # ── Level 3: Patterns (composite, multi-turn) ──
        flags = {}  # flag → set of responsible cards
        # ── Level 1: Keywords (static card properties) ──
        kw_counts = Counter()           # keyword → total plays
        kw_cards = defaultdict(Counter)  # keyword → {card: count}
        # ── Level 2: Abilities (triggered/activated effects) ──
        ab_counts = Counter()           # "trigger_effect" → total fires
        ab_cards = defaultdict(Counter)  # "trigger_effect" → {card: count}

        turns = g.get('turns', {})
        length = g.get('length', 0)

        def _add_flag(flag, card=''):
            if flag not in flags:
                flags[flag] = set()
            if card:
                flags[flag].add(card)

        opp_card_plays = Counter()  # card → times played
        max_dead_bounced = 0       # worst single-turn removal
        has_free_deploy = False
        multi_ability_turns = 0
        synergy_cards = set()      # cards involved in ability chains
        recursion_cards = set()    # cards involved in recursion

        for t_num in range(1, length + 1):
            td = turns.get(t_num, {})
            raw_plays = td.get('opp_play_detail', td.get('opp_plays', []))
            opp_abilities = td.get('opp_abilities', [])
            our_dead = td.get('our_dead', [])
            our_bounced = td.get('our_bounced', [])

            # Normalize plays to (name, ink_paid)
            plays_norm = []
            for p in raw_plays:
                if isinstance(p, dict):
                    plays_norm.append((p.get('name', ''), p.get('ink_paid', 99)))
                elif isinstance(p, str):
                    plays_norm.append((p, 99))
                elif isinstance(p, (tuple, list)) and len(p) >= 2:
                    plays_norm.append((str(p[0]), p[1] if isinstance(p[1], int) else 99))

            # ── Level 1: Track keywords from played cards ──
            for name, ink_paid in plays_norm:
                card_info = cards_dict.get(name, {})
                for kw in card_info.get('keywords', []):
                    kw_counts[kw] += 1
                    kw_cards[kw][name] += 1

            # ── Level 2: Track ability profiles from played cards ──
            for name, ink_paid in plays_norm:
                card_info = cards_dict.get(name, {})
                profile = card_info.get('ability_profile')
                if profile:
                    trigger = profile['trigger']
                    for eff in profile['effects']:
                        key = f"{trigger}_{eff}"
                        ab_counts[key] += 1
                        ab_cards[key][name] += 1

            # Also track abilities that actually fired (from ability log)
            for ab in opp_abilities:
                if not isinstance(ab, dict):
                    continue
                card_name = ab.get('card', '')
                if not card_name:
                    continue
                card_info = cards_dict.get(card_name, {})
                profile = card_info.get('ability_profile')
                if profile:
                    trigger = profile['trigger']
                    for eff in profile['effects']:
                        key = f"{trigger}_{eff}"
                        # Only count if not already counted from plays
                        # (ETB fires once on play, but activated/quest fire multiple times)
                        if trigger not in ('etb',):
                            ab_counts[key] += 1
                            ab_cards[key][card_name] += 1

            # ── Level 3: Pattern detection (existing logic) ──

            # Count plays
            free_this_turn = 0
            for name, ink_paid in plays_norm:
                opp_card_plays[name] += 1
                if ink_paid == 0:
                    free_this_turn += 1

            # Removal per turn
            removed = len(our_dead) + len(our_bounced)
            if removed > max_dead_bounced:
                max_dead_bounced = removed

            # WIPE: >=3 pieces removed in one turn → attribute to plays
            if removed >= 3:
                wipe_cards = [n for n, _ in plays_norm]
                for name in wipe_cards:
                    _add_flag('WIPE', name)
                if not wipe_cards:
                    _add_flag('WIPE')

            # WIPE: mass removal card played (detected from cards_db removal_type)
            for name, _ in plays_norm:
                if name in mass_removal_cards:
                    _add_flag('WIPE', name)

            # SING_TOGETHER: card with sing_together ability played
            for name, _ in plays_norm:
                if name in sing_together_cards:
                    _add_flag('SING_TOGETHER', name)

            # Abilities count (ETB triggers, activated, etc.)
            if len(opp_abilities) >= 3:
                multi_ability_turns += 1
                for ab in opp_abilities:
                    if isinstance(ab, dict) and ab.get('card'):
                        synergy_cards.add(ab['card'])

            # Free deploys (cost reduction chains)
            if free_this_turn >= 2:
                has_free_deploy = True
                for name, ink_paid in plays_norm:
                    if ink_paid == 0:
                        _add_flag('RAMP_CHAIN', name)

            # Recursion indicators from ability log
            for ab in opp_abilities:
                effect = ''
                card_name = ''
                if isinstance(ab, dict):
                    effect = (ab.get('effect', '') or '').lower()
                    card_name = ab.get('card', '')
                elif isinstance(ab, str):
                    effect = ab.lower()
                if any(w in effect for w in ['from discard', 'return', 'returned']):
                    if card_name:
                        recursion_cards.add(card_name)

            # Recursion: card with recursion ability played
            for name, _ in plays_norm:
                if name in recursion_ability_cards:
                    recursion_cards.add(name)

            # HAND_STRIP: detected from ability log OR from cards_db
            for ab in opp_abilities:
                if not isinstance(ab, dict):
                    continue
                effect = (ab.get('effect', '') or '').lower()
                card_name = ab.get('card', '')
                if 'discard' in effect and ('opponent' in effect or 'hand' in effect):
                    _add_flag('HAND_STRIP', card_name)
            for name, _ in plays_norm:
                if name in hand_strip_ability_cards:
                    _add_flag('HAND_STRIP', name)

        # RAMP_CHAIN
        if has_free_deploy and 'RAMP_CHAIN' not in flags:
            _add_flag('RAMP_CHAIN')

        # RECURSION: from ability log + card played 3+ times (likely recursion)
        for card in recursion_cards:
            _add_flag('RECURSION', card)
        for card, cnt in opp_card_plays.items():
            if cnt >= 3:
                _add_flag('RECURSION', card)

        # WIPE fallback: >=2 removed if no other wipe detected
        if max_dead_bounced >= 2 and 'WIPE' not in flags:
            _add_flag('WIPE')

        # SYNERGY_BURST: turns with many abilities chained (>=3 abilities, >=2 turns)
        if multi_ability_turns >= 2:
            for card in synergy_cards:
                _add_flag('SYNERGY_BURST', card)
            if not synergy_cards:
                _add_flag('SYNERGY_BURST')

        # LORE_FLOOD: >=8 lore gained in a single turn
        for t_num in range(2, length + 1):
            td = turns.get(t_num, {})
            td_prev = turns.get(t_num - 1, {})
            lore_now = td.get('lore', {}).get('opp', 0)
            lore_prev = td_prev.get('lore', {}).get('opp', 0)
            if lore_now - lore_prev >= 8:
                raw_plays = td.get('opp_play_detail', td.get('opp_plays', []))
                for p in raw_plays:
                    name = p.get('name', '') if isinstance(p, dict) else str(p)
                    if name:
                        _add_flag('LORE_FLOOD', name)
                for q in td.get('opp_quests', []):
                    if isinstance(q, dict) and q.get('card'):
                        _add_flag('LORE_FLOOD', q['card'])
                if 'LORE_FLOOD' not in flags:
                    _add_flag('LORE_FLOOD')
                break

        return {
            'patterns': flags,
            'keywords': dict(kw_counts.most_common()),
            'keywords_cards': {kw: dict(cards.most_common(3)) for kw, cards in kw_cards.items()},
            'abilities': dict(ab_counts.most_common()),
            'abilities_cards': {key: dict(cards.most_common(3)) for key, cards in ab_cards.items()},
        }

    # Tag every loss
    for lc in loss_classes:
        g = games[lc['game_idx']]
        lc['_mech_flags'] = _tag_mechanics(lc, g)

    # ── Loss profiles: raggruppa per velocità (FAST / TYPICAL / SLOW) ──
    # Usa percentili di game length per definire i bucket
    lengths_all = sorted(lc.get('lore_speed', {}).get('game_length', 99)
                         for lc in loss_classes)
    n = len(lengths_all)
    loss_profiles = {}

    if n >= 8:
        p25 = lengths_all[n // 4]
        p75 = lengths_all[3 * n // 4]

        buckets = {
            'fast': ('≤{}T'.format(p25), []),
            'typical': ('{}T-{}T'.format(p25 + 1, p75), []),
            'slow': ('≥{}T'.format(p75 + 1), []),
        }
        for lc in loss_classes:
            gl = lc.get('lore_speed', {}).get('game_length', 99)
            if gl <= p25:
                buckets['fast'][1].append(lc)
            elif gl > p75:
                buckets['slow'][1].append(lc)
            else:
                buckets['typical'][1].append(lc)

        for bucket_name, (label, bucket_lcs) in buckets.items():
            if not bucket_lcs:
                continue

            b_n = len(bucket_lcs)
            # Cause
            b_causes = Counter()
            for lc in bucket_lcs:
                for c in lc['causes']:
                    b_causes[c] += 1
            # Component primary
            b_comp = Counter()
            for lc in bucket_lcs:
                if lc.get('criticals'):
                    b_comp[lc['criticals'][0]['component']] += 1
            # Alert types (unique per loss)
            b_alerts = Counter()
            for lc in bucket_lcs:
                seen = set()
                for a in lc.get('alerts', []):
                    for txt in a.get('alerts', []):
                        atype = txt.split(':')[0].strip()
                        if atype not in seen:
                            b_alerts[atype] += 1
                            seen.add(atype)
            # Wipe: >=2 our pieces removed in 1 turn
            b_wipe = 0
            for lc in bucket_lcs:
                g = games[lc['game_idx']]
                for t_num in range(1, g['length'] + 1):
                    td = g['turns'].get(t_num, {})
                    dead_n = len(td.get('our_dead', []))
                    bounced_n = len(td.get('our_bounced', []))
                    if dead_n + bounced_n >= 2:
                        b_wipe += 1
                        break
            # Top cards: ALL opponent cards played (not just classify causes)
            b_cards = Counter()
            for lc in bucket_lcs:
                g = games[lc['game_idx']]
                for t_num in range(1, g['length'] + 1):
                    td = g['turns'].get(t_num, {})
                    # opp_play_detail has dicts, opp_plays may be strings
                    for p in td.get('opp_play_detail', td.get('opp_plays', [])):
                        if isinstance(p, dict):
                            b_cards[p.get('name', '')] += 1
                        elif isinstance(p, str):
                            b_cards[p] += 1
            # Lore@T4 distribution
            b_lore_t4 = []
            for lc in bucket_lcs:
                tc = lc.get('trend_components', {})
                lore_arr = tc.get('lore', [])
                if len(lore_arr) >= 4:
                    b_lore_t4.append(lore_arr[3])
            b_lore_t4.sort()

            # ── 3-level aggregate for this bucket ──
            # Level 3: Patterns (composite flags)
            b_mech = Counter()         # flag → count of losses
            b_mech_cards = defaultdict(Counter)  # flag → {card: count}
            # Level 1: Keywords (static card properties)
            b_keywords = Counter()     # keyword → total plays across losses
            b_kw_cards = defaultdict(Counter)
            # Level 2: Abilities (triggered effects)
            b_abilities = Counter()    # trigger_effect → total fires across losses
            b_ab_cards = defaultdict(Counter)

            for lc in bucket_lcs:
                mech_data = lc.get('_mech_flags', {})
                # Patterns (backward compat: old format was flat dict)
                patterns = mech_data.get('patterns', mech_data) if isinstance(mech_data, dict) and 'patterns' in mech_data else mech_data
                if isinstance(patterns, dict):
                    for flag, cards in patterns.items():
                        if isinstance(cards, (set, list)):
                            b_mech[flag] += 1
                            for card in cards:
                                if card:
                                    b_mech_cards[flag][card] += 1
                # Keywords
                for kw, cnt in mech_data.get('keywords', {}).items():
                    b_keywords[kw] += cnt
                for kw, cards in mech_data.get('keywords_cards', {}).items():
                    for card, cnt in cards.items():
                        b_kw_cards[kw][card] += cnt
                # Abilities
                for key, cnt in mech_data.get('abilities', {}).items():
                    b_abilities[key] += cnt
                for key, cards in mech_data.get('abilities_cards', {}).items():
                    for card, cnt in cards.items():
                        b_ab_cards[key][card] += cnt

            # ── Example game IDs: diversified selection ──
            # Each loss goes into ALL its pattern flag groups (not just one)
            flag_groups = defaultdict(list)
            for lc in bucket_lcs:
                mech_data = lc.get('_mech_flags', {})
                patterns = mech_data.get('patterns', mech_data) if isinstance(mech_data, dict) and 'patterns' in mech_data else mech_data
                if not patterns or not isinstance(patterns, dict):
                    flag_groups['_NONE'].append(lc)
                else:
                    for f in patterns:
                        flag_groups[f].append(lc)

            # Pick examples ensuring mechanical coverage
            selected = []
            selected_ids = set()
            # First pass: 2 worst-swing from each flag with >=10% frequency
            for flag in ['WIPE', 'RECURSION', 'SYNERGY_BURST', 'HAND_STRIP',
                         'LORE_FLOOD', 'RAMP_CHAIN', '_NONE']:
                group = flag_groups.get(flag, [])
                if len(group) < max(2, b_n * 0.10):  # skip rare flags (<10%)
                    continue
                by_swing = sorted(group, key=lambda x: x.get('swing', 0))
                picked = 0
                for lc in by_swing:
                    if lc['game_idx'] not in selected_ids:
                        selected.append(lc)
                        selected_ids.add(lc['game_idx'])
                        picked += 1
                        if picked >= 2:
                            break

            # Fill remaining slots with worst-swing overall (up to 12)
            by_swing_all = sorted(bucket_lcs, key=lambda x: x.get('swing', 0))
            for lc in by_swing_all:
                if len(selected) >= 12:
                    break
                if lc['game_idx'] not in selected_ids:
                    selected.append(lc)
                    selected_ids.add(lc['game_idx'])

            loss_profiles[bucket_name] = {
                'label': label,
                'count': b_n,
                'pct': round(b_n / n * 100),
                'causes': dict(b_causes.most_common(6)),
                'component_primary': dict(b_comp.most_common()),
                'alert_types': dict(b_alerts.most_common()),
                'wipe_rate': round(b_wipe / b_n * 100),
                'top_cards': dict(b_cards.most_common(20)),
                'mechanics': dict(b_mech.most_common()),
                'mechanics_cards': {flag: dict(cards.most_common(3))
                                    for flag, cards in b_mech_cards.items()},
                'keywords': dict(b_keywords.most_common()),
                'keywords_cards': {kw: dict(cards.most_common(3))
                                   for kw, cards in b_kw_cards.items()},
                'abilities': dict(b_abilities.most_common()),
                'abilities_cards': {key: dict(cards.most_common(3))
                                    for key, cards in b_ab_cards.items()},
                'lore_t4': {
                    'p5': round(b_lore_t4[max(0, len(b_lore_t4)//20)]) if b_lore_t4 else 0,
                    'p50': round(b_lore_t4[len(b_lore_t4)//2]) if b_lore_t4 else 0,
                    'p95': round(b_lore_t4[min(len(b_lore_t4)-1, len(b_lore_t4)*19//20)]) if b_lore_t4 else 0,
                },
                'example_game_ids': [lc['game_idx'] for lc in selected],
            }

    return {
        'cause_frequency': dict(all_causes.most_common()),
        'critical_turn_distribution': dict(sorted(crit_turns.items())),
        'component_primary': dict(component_primary.most_common()),
        'card_at_critical_turn': dict(card_at_crit.most_common(15)),
        'card_examples': card_examples,
        'combos_at_critical_turn': combo_examples[:10],
        'avg_trend_components': avg_trends,
        'top_abilities_at_critical': dict(ability_freq.most_common(15)),
        'lore_speed': lore_speed,
        'loss_profiles': loss_profiles,
        'alert_summary': {
            'severity_counts': dict(alert_freq),
            'type_counts': dict(alert_type_freq.most_common()),
            'losses_per_type': {atype: len(gids) for atype, gids in
                                sorted(losses_with_alert_type.items(), key=lambda x: -len(x[1]))},
            'by_turn': {str(t): dict(Counter(sevs))
                        for t, sevs in sorted(alert_by_turn.items())},
            'type_by_turn': {str(t): dict(counts)
                             for t, counts in sorted(alert_type_by_turn.items())},
        },
    }
