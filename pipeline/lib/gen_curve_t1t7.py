"""
Genera .md con curve T1-T7 sintetiche: lore gap, curva avversaria/nostra,
interazioni, co-play, pezzi morti/bounced.
"""

from collections import Counter
from .formatting import short
from .stats import (split_wins_losses, avg, cards_by_turn, coplay_global,
                    challenge_stats, ability_stats, dead_bounced_stats, lore_at_turn)
from .loader import safe_int

MAX_TURN = 7


def generate(our_deck, opp_deck, games, db):
    wins, losses = split_wins_losses(games)
    if not games:
        return "# Nessun match trovato\n"

    lines = []
    lines.append(f"# Curve T1-T{MAX_TURN}: {our_deck} vs {opp_deck}")
    lines.append(f"")
    lines.append(f"**{len(games)} games ({len(wins)}W / {len(losses)}L = {len(wins)/len(games)*100:.0f}% WR)**")
    lines.append(f"")

    # ── Situazione a T6 e T7 ──
    lines.append(f"## Situazione a T6 e T7\n")
    for check_t in (6, 7):
        lore = lore_at_turn(games, check_t)
        w_dead = [sum(len(g['turns'].get(t, {}).get('our_dead', [])) for t in range(1, check_t+1)) for g in wins]
        l_dead = [sum(len(g['turns'].get(t, {}).get('our_dead', [])) for t in range(1, check_t+1)) for g in losses]
        w_opp_dead = [sum(len(g['turns'].get(t, {}).get('opp_dead', [])) for t in range(1, check_t+1)) for g in wins]
        l_opp_dead = [sum(len(g['turns'].get(t, {}).get('opp_dead', [])) for t in range(1, check_t+1)) for g in losses]
        w_bounced = [sum(len(g['turns'].get(t, {}).get('our_bounced', [])) for t in range(1, check_t+1)) for g in wins]
        l_bounced = [sum(len(g['turns'].get(t, {}).get('our_bounced', [])) for t in range(1, check_t+1)) for g in losses]

        lines.append(f"### A T{check_t}\n")
        lines.append(f"| Metrica | WIN | LOSS | Delta |")
        lines.append(f"|---------|-----|------|-------|")
        lines.append(f"| Nostra lore | {avg(lore['w_our']):.1f} | {avg(lore['l_our']):.1f} | {avg(lore['w_our'])-avg(lore['l_our']):+.1f} |")
        lines.append(f"| Lore avversaria | {avg(lore['w_opp']):.1f} | {avg(lore['l_opp']):.1f} | {avg(lore['w_opp'])-avg(lore['l_opp']):+.1f} |")
        lines.append(f"| Gap lore (noi - avv) | {avg(lore['w_our'])-avg(lore['w_opp']):.1f} | {avg(lore['l_our'])-avg(lore['l_opp']):.1f} | |")
        lines.append(f"| Nostri pezzi morti | {avg(w_dead):.1f} | {avg(l_dead):.1f} | {avg(w_dead)-avg(l_dead):+.1f} |")
        lines.append(f"| Pezzi avv morti | {avg(w_opp_dead):.1f} | {avg(l_opp_dead):.1f} | {avg(w_opp_dead)-avg(l_opp_dead):+.1f} |")
        lines.append(f"| Nostri pezzi bounced | {avg(w_bounced):.1f} | {avg(l_bounced):.1f} | {avg(w_bounced)-avg(l_bounced):+.1f} |")
        lines.append(f"")

        lines.append(f"**Distribuzione lore gap (noi - avv) a T{check_t}:**\n")
        for thr in (5, 3, 0, -3, -5):
            w_above = sum(1 for g in wins if g['turns'].get(check_t, {}).get('our_lore', 0) - g['turns'].get(check_t, {}).get('opp_lore', 0) >= thr)
            l_above = sum(1 for g in losses if g['turns'].get(check_t, {}).get('our_lore', 0) - g['turns'].get(check_t, {}).get('opp_lore', 0) >= thr)
            w_pct = w_above / len(wins) * 100 if wins else 0
            l_pct = l_above / len(losses) * 100 if losses else 0
            lines.append(f"- Gap {thr:+d}: W {w_pct:.0f}% | L {l_pct:.0f}%")
        lines.append(f"")

    # ── Curva avversaria ──
    lines.append(f"## Curva avversaria T1-T{MAX_TURN} (WIN vs LOSS)\n")
    opp_cards = cards_by_turn(games, 'opp', MAX_TURN)
    for tn in range(1, MAX_TURN + 1):
        w_cards, l_cards = opp_cards[tn]
        all_cards = set(w_cards) | set(l_cards)
        rows = []
        for n in all_cards:
            w, l = w_cards.get(n, 0), l_cards.get(n, 0)
            if w + l < 3:
                continue
            w_pct = w / len(wins) * 100 if wins else 0
            l_pct = l / len(losses) * 100 if losses else 0
            rows.append((n, w, l, w_pct, l_pct, l_pct - w_pct, w + l))
        rows.sort(key=lambda x: -x[6])
        if not rows:
            continue
        lines.append(f"### T{tn} avversario\n")
        lines.append(f"| Carta | In W ({len(wins)}g) | In L ({len(losses)}g) | Delta% |")
        lines.append(f"|-------|------|------|--------|")
        for n, w, l, w_pct, l_pct, delta, _ in rows[:8]:
            info = db.get(n, {})
            cost = safe_int(info.get('cost', 0))
            lines.append(f"| {short(n)} (cost:{cost}) | {w} ({w_pct:.0f}%) | {l} ({l_pct:.0f}%) | {delta:+.0f}pp |")
        lines.append(f"")

    # ── Curva nostra ──
    lines.append(f"## Curva nostra T1-T{MAX_TURN} (WIN vs LOSS)\n")
    our_cards = cards_by_turn(games, 'our', MAX_TURN)
    for tn in range(1, MAX_TURN + 1):
        w_cards, l_cards = our_cards[tn]
        all_cards = set(w_cards) | set(l_cards)
        rows = []
        for n in all_cards:
            w, l = w_cards.get(n, 0), l_cards.get(n, 0)
            if w + l < 3:
                continue
            w_pct = w / len(wins) * 100 if wins else 0
            l_pct = l / len(losses) * 100 if losses else 0
            rows.append((n, w, l, w_pct, l_pct, w_pct - l_pct))
        rows.sort(key=lambda x: -abs(x[5]))
        if not rows:
            continue
        lines.append(f"### T{tn} noi\n")
        lines.append(f"| Carta | In W ({len(wins)}g) | In L ({len(losses)}g) | Delta% |")
        lines.append(f"|-------|------|------|--------|")
        for n, w, l, w_pct, l_pct, delta in rows[:8]:
            info = db.get(n, {})
            cost = safe_int(info.get('cost', 0))
            lines.append(f"| {short(n)} (cost:{cost}) | {w} ({w_pct:.0f}%) | {l} ({l_pct:.0f}%) | {delta:+.0f}pp |")
        lines.append(f"")

    # ── Interazioni ──
    lines.append(f"## Interazioni T1-T{MAX_TURN}\n")
    for label, side in [("Avversario ci challenja", 'opp'), ("NOI challengiamo", 'our')]:
        lines.append(f"### {label}\n")
        ch = challenge_stats(games, side, MAX_TURN)
        ch_rows = [(k, v) for k, v in ch.items() if v['w'] + v['l'] >= 3]
        ch_rows.sort(key=lambda x: -(x[1]['w'] + x[1]['l']))
        lines.append(f"| Attacker | Target | W (kill) | L (kill) |")
        lines.append(f"|----------|--------|----------|----------|")
        for (atk, defn), v in ch_rows[:12]:
            lines.append(f"| {short(atk)} | {short(defn)} | {v['w']} ({v['w_kill']}k) | {v['l']} ({v['l_kill']}k) |")
        lines.append(f"")

    # ── Ability avversarie ──
    lines.append(f"### Ability avversarie T1-T{MAX_TURN} (effetti che contano)\n")
    eff_rows = ability_stats(games, 'opp', MAX_TURN)
    lines.append(f"| Carta | Effetto | In W | In L |")
    lines.append(f"|-------|---------|------|------|")
    for card, eff, w, l in eff_rows[:15]:
        lines.append(f"| {short(card)} | {eff[:40]} | {w} | {l} |")
    lines.append(f"")

    # ── Co-play ──
    lines.append(f"## Co-play avversari nello stesso turno (T1-T{MAX_TURN})\n")
    cp_w, cp_l = coplay_global(games, 'opp', MAX_TURN)
    all_pairs = set(cp_w) | set(cp_l)
    pair_rows = [(p, cp_w.get(p, 0), cp_l.get(p, 0)) for p in all_pairs if cp_w.get(p, 0) + cp_l.get(p, 0) >= 3]
    pair_rows.sort(key=lambda x: -(x[1] + x[2]))
    lines.append(f"| Carta A | Carta B | In W | In L |")
    lines.append(f"|---------|---------|------|------|")
    for (a, b), w, l in pair_rows[:15]:
        lines.append(f"| {short(a)} | {short(b)} | {w} | {l} |")
    lines.append(f"")

    # ── Morti e bounced ──
    dead, bounced = dead_bounced_stats(games, 'our', MAX_TURN)
    lines.append(f"## Nostri pezzi morti T1-T{MAX_TURN}\n")
    dead_rows = [(n, v) for n, v in dead.items() if v['w'] + v['l'] >= 3]
    dead_rows.sort(key=lambda x: -(x[1]['w'] + x[1]['l']))
    lines.append(f"| Carta | Morti in W | Morti in L |")
    lines.append(f"|-------|------------|------------|")
    for n, v in dead_rows[:12]:
        lines.append(f"| {short(n)} | {v['w']} | {v['l']} |")
    lines.append(f"")

    bounced_rows = [(n, v) for n, v in bounced.items() if v['w'] + v['l'] >= 3]
    if bounced_rows:
        bounced_rows.sort(key=lambda x: -(x[1]['w'] + x[1]['l']))
        lines.append(f"## Nostri pezzi bounced T1-T{MAX_TURN}\n")
        lines.append(f"| Carta | Bounced in W | Bounced in L |")
        lines.append(f"|-------|--------------|--------------|")
        for n, v in bounced_rows[:10]:
            lines.append(f"| {short(n)} | {v['w']} | {v['l']} |")
        lines.append(f"")

    return '\n'.join(lines)
