"""
Calcoli statistici su match caricati: co-play, challenge, lore gap, etc.
"""

from collections import defaultdict, Counter


def split_wins_losses(games):
    wins = [g for g in games if g['we_won']]
    losses = [g for g in games if not g['we_won']]
    return wins, losses


def avg(lst):
    return sum(lst) / len(lst) if lst else 0


def coplay_by_turn(games, side='opp', max_turn=7):
    """
    Calcola co-play (coppie giocate nello stesso turno) per turno.
    side: 'opp' o 'our'
    Ritorna (coplay_w, coplay_l) dove ciascuno è {turn: Counter((a,b) -> count)}
    """
    coplay_w = defaultdict(Counter)
    coplay_l = defaultdict(Counter)
    for g in games:
        target = coplay_w if g['we_won'] else coplay_l
        for tn in range(1, max_turn + 1):
            t = g['turns'].get(tn)
            if not t:
                continue
            names = [n for n, c in t[f'{side}_plays']]
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    target[tn][tuple(sorted([names[i], names[j]]))] += 1
    return coplay_w, coplay_l


def coplay_global(games, side='opp', max_turn=7):
    """Co-play aggregato su tutti i turni. Ritorna (Counter_w, Counter_l)."""
    coplay_w = Counter()
    coplay_l = Counter()
    for g in games:
        target = coplay_w if g['we_won'] else coplay_l
        for tn in range(1, max_turn + 1):
            t = g['turns'].get(tn)
            if not t:
                continue
            names = [n for n, c in t[f'{side}_plays']]
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    target[tuple(sorted([names[i], names[j]]))] += 1
    return coplay_w, coplay_l


def cards_by_turn(games, side, max_turn=7):
    """
    Frequenza carte per turno, separate W/L.
    Ritorna {turn: (Counter_w, Counter_l)}
    """
    result = {}
    for tn in range(1, max_turn + 1):
        w_cards = Counter()
        l_cards = Counter()
        for g in games:
            t = g['turns'].get(tn)
            if not t:
                continue
            for n, c in t[f'{side}_plays']:
                if g['we_won']:
                    w_cards[n] += 1
                else:
                    l_cards[n] += 1
        result[tn] = (w_cards, l_cards)
    return result


def challenge_stats(games, side, max_turn=7):
    """
    Statistiche challenge aggregati.
    Ritorna dict {(attacker, defender): {w, l, w_kill, l_kill}}
    """
    agg = defaultdict(lambda: {'w': 0, 'l': 0, 'w_kill': 0, 'l_kill': 0})
    for g in games:
        for tn in range(1, max_turn + 1):
            t = g['turns'].get(tn)
            if not t:
                continue
            for ch in t[f'{side}_challenges']:
                k = (ch['attacker'], ch['defender'])
                if g['we_won']:
                    agg[k]['w'] += 1
                    if ch['def_killed']:
                        agg[k]['w_kill'] += 1
                else:
                    agg[k]['l'] += 1
                    if ch['def_killed']:
                        agg[k]['l_kill'] += 1
    return dict(agg)


def ability_stats(games, side, max_turn=7, min_count=5):
    """
    Statistiche ability aggregate (card, effect_troncato).
    Ritorna lista [(card, effect, w_count, l_count)] ordinata per frequenza.
    """
    agg = defaultdict(lambda: {'w': 0, 'l': 0})
    for g in games:
        for tn in range(1, max_turn + 1):
            t = g['turns'].get(tn)
            if not t:
                continue
            for ab in t[f'{side}_abilities']:
                eff = ab['effect'][:50]
                if 'had no effect' in eff:
                    continue
                k = (ab['card'], eff)
                if g['we_won']:
                    agg[k]['w'] += 1
                else:
                    agg[k]['l'] += 1
    rows = [(card, eff, v['w'], v['l'])
            for (card, eff), v in agg.items()
            if v['w'] + v['l'] >= min_count]
    rows.sort(key=lambda x: -(x[2] + x[3]))
    return rows


def dead_bounced_stats(games, side, max_turn=7):
    """
    Statistiche pezzi morti e bounced.
    Ritorna (dead_dict, bounced_dict) dove ciascuno è {name: {w, l}}
    """
    dead = defaultdict(lambda: {'w': 0, 'l': 0})
    bounced = defaultdict(lambda: {'w': 0, 'l': 0})
    wl = 'w' if True else 'l'
    for g in games:
        s = 'w' if g['we_won'] else 'l'
        for tn in range(1, max_turn + 1):
            t = g['turns'].get(tn)
            if not t:
                continue
            for n in t[f'{side}_dead']:
                dead[n][s] += 1
            for n in t[f'{side}_bounced']:
                bounced[n][s] += 1
    return dict(dead), dict(bounced)


def lore_at_turn(games, turn):
    """
    Lore a un turno specifico, separati W/L.
    Ritorna {w_our, l_our, w_opp, l_opp} come liste.
    """
    w_our, l_our, w_opp, l_opp = [], [], [], []
    for g in games:
        t = g['turns'].get(turn)
        if not t:
            continue
        if g['we_won']:
            w_our.append(t['our_lore'])
            w_opp.append(t['opp_lore'])
        else:
            l_our.append(t['our_lore'])
            l_opp.append(t['opp_lore'])
    return {'w_our': w_our, 'l_our': l_our, 'w_opp': w_opp, 'l_opp': l_opp}


def ink_budget_per_turn(games, side='opp', max_turn=10):
    """
    Ink totale speso per turno nelle loss.
    Usa ink_spent reale dal loader (shift/song/pieno).
    Ritorna {turn: [total_cost_per_game]}
    """
    result = defaultdict(list)
    for g in games:
        if g['we_won']:
            continue
        for tn in range(1, max_turn + 1):
            t = g['turns'].get(tn)
            if not t:
                continue
            # Usa il costo reale se disponibile, altrimenti fallback al vecchio
            total = t.get(f'{side}_ink_spent', sum(c for _, c in t.get(f'{side}_plays', [])))
            if total > 0:
                result[tn].append(total)
    return dict(result)


def card_frequency_in_losses(games, side='opp', max_turn=None):
    """
    Frequenza carte (per game, non per play) nelle loss.
    Ritorna Counter {name: n_games}.
    """
    freq = Counter()
    for g in games:
        if g['we_won']:
            continue
        seen = set()
        turns = g['turns']
        for tn in sorted(turns.keys()):
            if max_turn and tn > max_turn:
                break
            for n, c in turns[tn].get(f'{side}_plays', []):
                if n not in seen:
                    freq[n] += 1
                    seen.add(n)
    return freq
