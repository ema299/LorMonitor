"""
Validatore curve killer: verifica combo reali, sing/shift patterns,
ink budget, ability dal DB, sequenze sample.
"""

from collections import defaultdict, Counter
from .formatting import (short, is_song, is_floodborn, get_shift_cost,
                         get_sing_cost, get_card_cost)
from .stats import split_wins_losses, avg, ink_budget_per_turn, card_frequency_in_losses


def _analyze_coplay_patterns(games, db):
    """Analizza co-play, sing, shift patterns dalle loss."""
    losses = [m for m in games if not m['we_won']]

    coplay = Counter()
    sing_patterns = Counter()
    shift_same_turn = defaultdict(Counter)

    for g in losses:
        for tn, t in g['turns'].items():
            # Co-play
            names = [n for n, c in t['opp_plays']]
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    coplay[tuple(sorted([names[i], names[j]]))] += 1

            # Ability-based sing/shift detection
            for ab in t['opp_abilities']:
                eff = ab.get('effect', '')
                # Basic detection from ability data
                if 'sing' in eff.lower() or 'song' in ab.get('ability', '').lower():
                    sing_patterns[(ab['card'], ab.get('target', '?'))] += 1

    return coplay, sing_patterns, shift_same_turn


def generate(our_deck, opp_deck, games, db):
    wins, losses = split_wins_losses(games)
    if not games:
        return "# Nessun match trovato\n"

    coplay, sing_patterns, shift_same_turn = _analyze_coplay_patterns(games, db)
    ink_budget = ink_budget_per_turn(games, 'opp', 10)

    lines = []
    lines.append(f"# Validazione Curve Killer: {our_deck} vs {opp_deck}")
    lines.append(f"")
    lines.append(f"**Match analizzati:** {len(games)} ({len(wins)}W / {len(losses)}L)")
    lines.append(f"")

    # ── 1. Combo reali ──
    lines.append(f"## 1. Combo reali nello stesso turno (dalle loss)")
    lines.append(f"")
    lines.append(f"### Co-play più frequenti (≥3x)")
    lines.append(f"")
    lines.append(f"| Carta A | Carta B | Volte |")
    lines.append(f"|---------|---------|-------|")
    for (a, b), count in coplay.most_common(25):
        if count >= 3:
            lines.append(f"| {a[:35]} | {b[:35]} | {count} |")
    lines.append(f"")

    # ── 2. Ink budget ──
    lines.append(f"## 2. Ink budget reale per turno (solo loss)")
    lines.append(f"")
    lines.append(f"| Turno | Ink disponibile | Ink medio speso | Max speso | N games |")
    lines.append(f"|-------|-----------------|-----------------|-----------|---------|")
    for t in sorted(ink_budget.keys()):
        if t > 10:
            break
        costs = ink_budget[t]
        lines.append(f"| T{t} | {t} (+ramp) | {avg(costs):.1f} | {max(costs)} | {len(costs)} |")
    lines.append(f"")

    # ── 3. Carte chiave — ability reali ──
    lines.append(f"## 3. Carte chiave avversarie — ability reali dal DB")
    lines.append(f"")
    opp_freq = card_frequency_in_losses(games, 'opp')
    for name, count in opp_freq.most_common(20):
        info = db.get(name, {})
        if not info:
            continue
        cost = get_card_cost(info)
        ctype = info.get('type', '')
        ab = info.get('ability', '')
        cls = info.get('classifications', '')
        shift_c = get_shift_cost(info)

        flags = []
        if is_floodborn(info):
            flags.append(f"Floodborn, Shift {shift_c}")
        if is_song(info):
            flags.append(f"Song")
            st = get_sing_cost(info)
            if st:
                flags.append(f"Sing Together {st}")
        flag_str = f" [{', '.join(flags)}]" if flags else ""

        s, w, l = info.get('str', ''), info.get('will', ''), info.get('lore', '')

        lines.append(f"- **{name}** — cost:{cost} {ctype}{flag_str}")
        if s and w:
            lines.append(f"  Stats: {s}/{w} lore:{l}")
        if cls:
            lines.append(f"  Class: {cls}")
        if ab:
            lines.append(f"  Ability: {ab[:200]}")
        lines.append(f"  Giocata in {count}/{len(losses)} loss ({count/len(losses)*100:.0f}%)")
        lines.append(f"")

    # ── 4. Sequenze sample ──
    lines.append(f"## 4. Sequenze reali turno per turno (top 5 loss)")
    lines.append(f"")
    for idx, g in enumerate(losses[:5]):
        lines.append(f"### Loss #{idx + 1}")
        lines.append(f"```")
        for tn in sorted(g['turns'].keys()):
            if tn > 10:
                break
            t = g['turns'][tn]
            plays = t['opp_plays']
            total_cost = t.get('opp_ink_spent', sum(c for _, c in plays))
            inkwell = t.get('opp_inkwell', tn)
            # Usa play_detail se disponibile per mostrare costo reale
            details = t.get('opp_play_detail', [])
            if details:
                play_str = ', '.join(
                    f"{p['name']} ({'shift '+str(p['shift_cost']) if p['is_shift'] else 'song' if p['is_sung'] else 'cost:'+str(p['ink_paid'])})"
                    for p in details) or '-'
            else:
                play_str = ', '.join(f"{n} (cost:{c})" for n, c in plays) or '-'
            ab_list = [a for a in t['opp_abilities'] if 'had no effect' not in a.get('effect', '')]
            ab_str = ', '.join(f"{a['card']}:{a['effect'][:30]}" for a in ab_list[:3]) if ab_list else ''

            line = f"T{tn} [ink:{inkwell}, spent:{total_cost}] play: {play_str}"
            if ab_str:
                line += f" | eff: {ab_str}"
            lines.append(line)
        lines.append(f"```")
        lines.append(f"")

    # ── 5. Warning ──
    lines.append(f"## 5. Warning automatici")
    lines.append(f"")
    has_warning = False
    for t in sorted(ink_budget.keys()):
        if t > 10:
            break
        costs = ink_budget[t]
        over_budget = sum(1 for c in costs if c > t)
        if over_budget > 0:
            pct = over_budget / len(costs) * 100
            if pct > 10:
                lines.append(f"- **T{t}**: {over_budget}/{len(costs)} game ({pct:.0f}%) spendono più di {t} ink → ramp attivo")
                has_warning = True
    if not has_warning:
        lines.append(f"_Nessun warning rilevato_")
    lines.append(f"")

    return '\n'.join(lines)
