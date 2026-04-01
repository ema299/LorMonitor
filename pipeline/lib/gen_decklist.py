"""Sezione 8: Decklist ottimizzata per il matchup — score MU, tagli, aggiunte, 60 carte."""

import os, json
from collections import defaultdict, Counter
from .formatting import short


def _safe_int(v):
    try:
        return int(v)
    except (ValueError, TypeError):
        return 0


def generate(our, opp, games, db, **ctx):
    our_pool = ctx.get('our_pool', {})
    our_decks = ctx.get('our_decks', [])

    L = [f"## 6. Decklist Ottimizzata vs {opp}\n"]

    if not our_decks:
        L.append(f"_Nessuna decklist trovata per {our} nel DB._\n")
        return '\n'.join(L) + '\n', {}

    wins = [g for g in games if g['we_won']]
    losses = [g for g in games if not g['we_won']]

    if not wins or not losses:
        L.append("_Dati insufficienti._\n")
        return '\n'.join(L) + '\n', {}

    # Step 1: Card matchup scores
    card_scores = {}
    for t in range(1, 7):
        win_c = Counter()
        loss_c = Counter()
        for g in wins:
            seen = set()
            for n, c in g['turns'].get(t, {}).get('our_plays', []):
                if n not in seen:
                    win_c[n] += 1
                    seen.add(n)
        for g in losses:
            seen = set()
            for n, c in g['turns'].get(t, {}).get('our_plays', []):
                if n not in seen:
                    loss_c[n] += 1
                    seen.add(n)
        for card in set(win_c) | set(loss_c):
            wc = win_c[card]
            lc = loss_c[card]
            if wc + lc < 2:
                continue
            wr = wc / len(wins)
            lr = lc / len(losses)
            delta = wr - lr
            weight = 2.0 if t <= 3 else 1.0
            if card not in card_scores:
                card_scores[card] = {'delta_sum': 0, 'appearances': 0, 'win_apps': 0, 'loss_apps': 0}
            card_scores[card]['delta_sum'] += delta * weight
            card_scores[card]['appearances'] += wc + lc
            card_scores[card]['win_apps'] += wc
            card_scores[card]['loss_apps'] += lc

    # Step 2: Best base deck
    best_deck = None
    best_deck_score = -999
    for deck in our_decks:
        dscore = 0
        for name, qty in deck['cards'].items():
            if name in card_scores:
                dscore += card_scores[name]['delta_sum'] * qty
        if dscore > best_deck_score:
            best_deck_score = dscore
            best_deck = deck

    if not best_deck:
        L.append("_Impossibile selezionare una decklist base._\n")
        return '\n'.join(L) + '\n', {}

    # Step 3: Core/engine cards
    core_cards = set()
    engine_cards = set()
    all_play_counter = Counter()
    early_play_counter = Counter()
    for g in wins:
        seen_all = set()
        seen_early = set()
        for t in range(1, 7):
            for n, c in g['turns'].get(t, {}).get('our_plays', []):
                if n not in seen_all:
                    all_play_counter[n] += 1
                    seen_all.add(n)
                if t <= 2 and n not in seen_early:
                    early_play_counter[n] += 1
                    seen_early.add(n)

    n_wins = len(wins)
    if n_wins >= 5:
        for name, cnt in all_play_counter.items():
            if cnt >= n_wins * 0.50:
                core_cards.add(name)
        for name, cnt in early_play_counter.items():
            if cnt >= n_wins * 0.30:
                engine_cards.add(name)

    L.append(f"### Base: {best_deck['player']} ({best_deck['rank']})")
    L.append(f"_Selezionata perche' contiene le carte piu' correlate a vincere._\n")

    if engine_cards or core_cards:
        L.append(f"### Carte Protette (intoccabili)\n")
        if engine_cards:
            eng_str = ', '.join(f"**{short(n)}**" for n in sorted(engine_cards))
            L.append(f"**Engine T1-T2** (≥30% vittorie early): {eng_str}")
        if core_cards - engine_cards:
            core_str = ', '.join(f"**{short(n)}**" for n in sorted(core_cards - engine_cards))
            L.append(f"**Core** (≥50% vittorie): {core_str}")
        L.append(f"\n_Queste carte non vengono tagliate._\n")

    # Step 3b: Score each card in base
    base_cards = dict(best_deck['cards'])
    scored_list = []
    for name, qty in base_cards.items():
        sc = card_scores.get(name, {})
        delta = sc.get('delta_sum', 0)
        apps = sc.get('appearances', 0)
        cost = _safe_int(db.get(name, {}).get('cost', 0))
        scored_list.append((name, qty, delta, apps, cost))
    scored_list.sort(key=lambda x: x[2])

    # Step 4: Cuts
    cuts = []
    for name, qty, delta, apps, cost in scored_list:
        if name in engine_cards:
            continue
        if name in core_cards:
            if delta < -0.15 and qty > 2:
                cuts.append((name, 1, delta, cost))
            continue
        if delta < -0.1 and apps >= 3:
            cuts.append((name, min(2, qty), delta, cost))
        elif delta < 0 and apps >= 5:
            cuts.append((name, 1, delta, cost))

    total_cuts = sum(q for _, q, _, _ in cuts)
    while total_cuts > 8:
        cuts.pop()
        total_cuts = sum(q for _, q, _, _ in cuts)

    # Step 5: Additions
    additions = []
    for name, info in our_pool.items():
        if name in base_cards and base_cards[name] >= 4:
            continue
        sc = card_scores.get(name, {})
        delta = sc.get('delta_sum', 0)
        apps = sc.get('appearances', 0)
        if delta > 0.1 and apps >= 3:
            current_qty = base_cards.get(name, 0)
            max_add = min(4 - current_qty, 2)
            if max_add > 0:
                additions.append((name, max_add, delta, info['cost']))
        elif delta > 0.2 and apps >= 2:
            current_qty = base_cards.get(name, 0)
            max_add = min(4 - current_qty, 2)
            if max_add > 0:
                additions.append((name, max_add, delta, info['cost']))
    additions.sort(key=lambda x: -x[2])

    total_adds = sum(q for _, q, _, _ in additions)
    while total_adds > total_cuts and additions:
        name, qty, delta, cost = additions[-1]
        if qty > 1:
            additions[-1] = (name, qty - 1, delta, cost)
        else:
            additions.pop()
        total_adds = sum(q for _, q, _, _ in additions)

    if total_adds < total_cuts:
        for i, (name, qty, delta, cost) in enumerate(additions):
            if total_adds >= total_cuts:
                break
            current = base_cards.get(name, 0) + qty
            can_add = min(4 - current, total_cuts - total_adds)
            if can_add > 0:
                additions[i] = (name, qty + can_add, delta, cost)
                total_adds += can_add

        if total_adds < total_cuts:
            existing_add_names = {n for n, _, _, _ in additions}
            for name, info in sorted(our_pool.items(), key=lambda x: -card_scores.get(x[0], {}).get('delta_sum', 0)):
                if total_adds >= total_cuts:
                    break
                if name in existing_add_names:
                    continue
                sc = card_scores.get(name, {})
                delta = sc.get('delta_sum', 0)
                if delta < -0.1:
                    continue
                current = base_cards.get(name, 0)
                can_add = min(4 - current, total_cuts - total_adds)
                if can_add > 0:
                    additions.append((name, can_add, delta, info['cost']))
                    total_adds += can_add

    while total_adds < total_cuts and cuts:
        name, qty, delta, cost = cuts[-1]
        if qty > 1:
            cuts[-1] = (name, qty - 1, delta, cost)
        else:
            cuts.pop()
        total_cuts = sum(q for _, q, _, _ in cuts)
        total_adds = sum(q for _, q, _, _ in additions)

    # Step 6: Build final deck
    final_deck = dict(base_cards)
    for name, qty, _, _ in cuts:
        final_deck[name] = max(0, final_deck.get(name, 0) - qty)
    for name, qty, _, _ in additions:
        final_deck[name] = final_deck.get(name, 0) + qty
    final_deck = {n: q for n, q in final_deck.items() if q > 0}
    total = sum(final_deck.values())

    if total < 60:
        for name, qty, delta, apps, cost in sorted(scored_list, key=lambda x: -x[2]):
            if total >= 60:
                break
            cur = final_deck.get(name, 0)
            if 0 < cur < 4 and delta >= 0:
                add = min(4 - cur, 60 - total)
                final_deck[name] = cur + add
                total += add
    elif total > 60:
        for name, qty, delta, apps, cost in scored_list:
            if total <= 60:
                break
            cur = final_deck.get(name, 0)
            if cur > 1:
                remove = min(cur - 1, total - 60)
                final_deck[name] = cur - remove
                total -= remove

    # Output
    if cuts or additions:
        L.append(f"### Modifiche Suggerite\n")
        if cuts:
            L.append(f"**Tagli:**")
            for name, qty, delta, cost in cuts:
                L.append(f"- -{qty}x **{name}** (c{cost}) — score MU: {delta:+.2f}")
        if additions:
            L.append(f"\n**Aggiunte:**")
            for name, qty, delta, cost in additions:
                L.append(f"- +{qty}x **{name}** (c{cost}) — score MU: {delta:+.2f}")
        L.append(f"\n_Bilancio: -{sum(q for _,q,_,_ in cuts)} / +{sum(q for _,q,_,_ in additions)} carte_")
    else:
        L.append(f"_La decklist base e' gia' ben posizionata._")

    # Full decklist
    L.append(f"\n### Decklist Completa ({sum(final_deck.values())} carte)\n")
    sorted_deck = sorted(final_deck.items(),
                         key=lambda x: (_safe_int(db.get(x[0], {}).get('cost', 0)), x[0]))

    by_type = defaultdict(list)
    for name, qty in sorted_deck:
        ctype = db.get(name, {}).get('type', 'Other')
        if 'Character' in ctype:
            ctype = 'Character'
        elif 'Action' in ctype:
            ctype = 'Action'
        elif 'Item' in ctype:
            ctype = 'Item'
        elif 'Location' in ctype:
            ctype = 'Location'
        by_type[ctype].append((name, qty))

    for ctype in ['Character', 'Action', 'Item', 'Location']:
        if ctype not in by_type:
            continue
        type_cards = by_type[ctype]
        type_total = sum(q for _, q in type_cards)
        L.append(f"**{ctype} ({type_total})**")
        L.append(f"| Qty | Carta | Costo | Score MU |")
        L.append(f"|---|---|---|---|")
        for name, qty in type_cards:
            cost = _safe_int(db.get(name, {}).get('cost', 0))
            sc = card_scores.get(name, {})
            delta = sc.get('delta_sum', 0)
            base_qty = base_cards.get(name, 0)
            change = ""
            if qty > base_qty:
                change = f" ↑+{qty-base_qty}"
            elif qty < base_qty:
                change = f" ↓-{base_qty-qty}"
            score_str = f"{delta:+.2f}" if delta != 0 else "—"
            L.append(f"| {qty}{change} | {name} | {cost} | {score_str} |")
        L.append("")

    # Mana curve
    L.append(f"### Curva di Mana")
    L.append(f"| Costo | Carte |")
    L.append(f"|---|---|")
    mana_curve = Counter()
    for name, qty in final_deck.items():
        cost = _safe_int(db.get(name, {}).get('cost', 0))
        mana_curve[cost] += qty
    for cost in sorted(mana_curve.keys()):
        bar = '\u2588' * mana_curve[cost]
        L.append(f"| {cost} | {bar} {mana_curve[cost]} |")

    # Import format
    L.append(f"\n### Import Deck (copia-incolla)")
    L.append(f"```")
    for name, qty in sorted(final_deck.items(),
                             key=lambda x: (_safe_int(db.get(x[0], {}).get('cost', 0)), x[0])):
        L.append(f"{qty} {name}")
    L.append(f"```")

    # Save scores
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scores_dir = os.path.join(base_dir, 'scores')
    os.makedirs(scores_dir, exist_ok=True)
    scores_out = {
        'our': our, 'opp': opp, 'n_matches': len(games),
        'n_wins': len(wins), 'n_losses': len(losses),
        'wr': len(wins) / len(games) if games else 0,
        'card_scores': {n: {'delta': s['delta_sum'], 'apps': s['appearances'],
                            'win_apps': s['win_apps'], 'loss_apps': s['loss_apps']}
                        for n, s in card_scores.items()},
    }
    scores_path = os.path.join(scores_dir, f"{our}_vs_{opp}.json")
    with open(scores_path, 'w') as f:
        json.dump(scores_out, f, indent=2)

    return '\n'.join(L) + '\n', {'card_scores': card_scores, 'final_deck': final_deck}
