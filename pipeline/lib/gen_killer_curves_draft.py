"""
Genera draft delle Minacce Principali dagli aggregati del classify.
Produce markdown tabellare: minaccia → turno → risposta.
Se esiste un file LLM raffinato (output/killer_curves_*.md), quello ha priorita'.
"""

import os
from collections import Counter, defaultdict
from .formatting import short

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')


def generate(our, opp, games, db, **ctx):
    """Genera la sezione Minacce Principali.

    Se esiste output/killer_curves_{our}_vs_{opp}.md (scritto dall'LLM),
    lo usa direttamente. Altrimenti genera un draft dagli aggregati.
    """
    # ── Priorita' al file LLM se esiste ──
    game_format = ctx.get('game_format', 'core')
    fmt_suffix = '_inf' if game_format == 'infinity' else ''
    llm_path = os.path.join(OUTPUT_DIR, f"killer_curves_{our}_vs_{opp}{fmt_suffix}.md")
    if os.path.exists(llm_path):
        with open(llm_path) as f:
            content = f.read().strip()
        if content:
            return content + '\n', {}

    # ── Draft automatico dagli aggregati del classify ──
    loss_classes = ctx.get('loss_classes', [])
    if not loss_classes:
        return '', {}

    losses = [g for g in games if not g['we_won']]
    n_loss = len(losses)
    if n_loss < 3:
        return '', {}

    L = []
    L.append(f"## Minacce Principali — {our} vs {opp}")
    L.append(f"")

    # Tipo matchup dal trend
    avg_trend = _avg_trend(loss_classes)
    if avg_trend and avg_trend[0] < -0.5:
        L.append(f"**Tipo matchup: PRESSIONE.** Sotto fin da T1. Lore race.")
    elif avg_trend and any(v > 1 for v in avg_trend[:5]):
        L.append(f"**Tipo matchup: SVOLTA.** Avanti nei primi turni, poi crollo.")
    else:
        L.append(f"**Tipo matchup: EQUILIBRATO.**")
    L.append(f"")

    # ── Lore Rush (se matchup pressione) ──
    fast_losses = [lc for lc in loss_classes
                   if lc.get('lore_speed', {}).get('opp_reach_15') and
                   lc['lore_speed']['opp_reach_15'] <= 6]
    if fast_losses:
        fastest = min(fast_losses, key=lambda lc: lc['lore_speed']['opp_reach_15'])
        reach = fastest['lore_speed']['opp_reach_15']
        L.append(f"### Lore Rush")
        L.append(f"")
        L.append(f"In **{len(fast_losses)}** loss l'avversario raggiunge 15 lore entro T6. "
                 f"Caso peggiore: **T{reach}** (game #{fastest['game_idx']}).")
        L.append(f"")

    # ── Cluster per carta chiave ──
    card_clusters = defaultdict(list)
    for lc in loss_classes:
        if lc['cards']:
            card_clusters[lc['cards'][0]].append(lc)

    threats = []
    for card, analyses in sorted(card_clusters.items(), key=lambda x: -len(x[1])):
        if len(analyses) < 3:
            continue
        avg_ct = sum(a['critical_turn'] for a in analyses) / len(analyses)
        causes = Counter()
        for a in analyses:
            for c in a['causes']:
                causes[c] += 1
        top_cause = causes.most_common(1)[0][0] if causes else 'unknown'
        comp = Counter(a['criticals'][0]['component'] for a in analyses if a.get('criticals'))
        primary_comp = comp.most_common(1)[0][0] if comp else 'unknown'

        threats.append({
            'card': card,
            'count': len(analyses),
            'pct': len(analyses) / n_loss * 100,
            'avg_turn': avg_ct,
            'component': primary_comp,
            'top_cause': top_cause,
            'causes': causes,
        })

    if not threats:
        L.append("_Non abbastanza dati per identificare minacce ricorrenti._")
        return '\n'.join(L) + '\n', {}

    # ── Tabella minacce ──
    for i, t in enumerate(threats[:5]):
        card_short = short(t['card'])
        L.append(f"### Minaccia #{i+1}: {t['card']}")
        L.append(f"")
        L.append(f"**Turno critico: T{t['avg_turn']:.0f}** | "
                 f"**Componente: {t['component']}** | "
                 f"**{t['count']}/{n_loss} loss ({t['pct']:.0f}%)**")
        L.append(f"")

        # Cause
        cause_str = ', '.join(f"{c}" for c, _ in t['causes'].most_common(3))
        L.append(f"Cause: {cause_str}")
        L.append(f"")

        # Tabella turno → 3 opzioni di risposta (placeholder per LLM)
        L.append(f"| Turno | Avversario | Risposta A | Risposta B | Risposta C |")
        L.append(f"|-------|-----------|-----------|-----------|-----------|")
        crit_t = round(t['avg_turn'])
        for t_offset in range(-2, 2):
            turn = crit_t + t_offset
            if turn < 1:
                continue
            if turn == crit_t:
                L.append(f"| **T{turn}** | **{card_short} — TRIGGER** | _(LLM)_ | _(LLM)_ | _(LLM)_ |")
            else:
                L.append(f"| T{turn} | setup | _(LLM)_ | _(LLM)_ | _(LLM)_ |")
        L.append(f"")

    # ── Riepilogo ──
    L.append(f"### Riepilogo Minacce")
    L.append(f"")
    L.append(f"| Minaccia | Turno | Componente | Freq | Risposta A | Risposta B | Risposta C |")
    L.append(f"|----------|-------|-----------|------|-----------|-----------|-----------|")
    for t in threats[:5]:
        L.append(f"| {short(t['card'])} | T{t['avg_turn']:.0f} | {t['component']} | {t['count']}/{n_loss} | _(LLM)_ | _(LLM)_ | _(LLM)_ |")
    L.append(f"")

    L.append(f"_Risposte da completare con analisi LLM (vedi ISTRUZIONI_KILLER_CURVES.md)._")
    L.append(f"")

    return '\n'.join(L) + '\n', {}


def _avg_trend(loss_classes):
    """Calcola trend medio totale."""
    if not loss_classes:
        return []
    max_len = max(len(lc['trend']) for lc in loss_classes)
    avg = []
    for i in range(min(max_len, 8)):
        vals = [lc['trend'][i] for lc in loss_classes if i < len(lc['trend'])]
        avg.append(sum(vals) / len(vals) if vals else 0)
    return avg
