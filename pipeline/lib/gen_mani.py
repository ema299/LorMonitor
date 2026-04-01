"""Sezione 3: Mani vincenti — frequenza carte, mulligan, coppie vincenti."""

from collections import Counter
from .formatting import short


def _pct(num, den):
    return f"{100*num/den:.0f}%" if den else '-'


def generate(our, opp, games, db, **ctx):
    L = [f"## 3. Mani Vincenti {our} OTD\n"]

    otd_wins = [g for g in games if g['we_won'] and not g.get('we_otp') and g.get('hand')]
    otd_all = [g for g in games if not g.get('we_otp')]

    L.append(f"> {len(otd_wins)} vittorie OTD con dati mano (su {len(otd_all)} match OTD, WR {_pct(sum(1 for g in otd_all if g['we_won']), len(otd_all))})\n")

    if len(otd_wins) < 2:
        L.append("_Dati insufficienti per analisi mani._\n")
        return '\n'.join(L) + '\n', {}

    card_freq = Counter()
    kept_freq = Counter()
    mulled_freq = Counter()
    mull_counts = []

    for g in otd_wins:
        h = g['hand']
        for c in h.get('final', []):
            card_freq[c] += 1
        for c in h.get('kept', []):
            kept_freq[c] += 1
        for c in h.get('sent', []):
            mulled_freq[c] += 1
        mull_counts.append(h.get('mull', 0))

    n = len(otd_wins)

    # Card frequency
    L.append("### Frequenza Carte nella Mano Finale")
    L.append("| Carta | Freq | % |")
    L.append("|---|---|---|")
    for card, cnt in card_freq.most_common(15):
        L.append(f"| {card} | {cnt} | {cnt/n*100:.0f}% |")

    # Mulligan sweet spot
    L.append(f"\n### Sweet Spot Mulligan")
    L.append("| Mull | N | % |")
    L.append("|---|---|---|")
    mc = Counter(mull_counts)
    for k in sorted(mc.keys()):
        marker = ' ← sweet spot' if mc[k] == max(mc.values()) else ''
        L.append(f"| {k} | {mc[k]} | {mc[k]/n*100:.0f}%{marker} |")
    L.append(f"| **Media** | **{sum(mull_counts)/n:.1f}** | |")

    # Kept cards
    L.append(f"\n### Carte Tenute (nelle vittorie)")
    L.append("| Carta | Tenuta | % |")
    L.append("|---|---|---|")
    for card, cnt in kept_freq.most_common(10):
        L.append(f"| {card} | {cnt} | {cnt/n*100:.0f}% |")

    # Winning pairs
    L.append(f"\n### Coppie Vincenti nella Mano")
    L.append("| Coppia | Freq | % |")
    L.append("|---|---|---|")
    pair_freq = Counter()
    for g in otd_wins:
        unique = sorted(set(g['hand'].get('final', [])))
        for i in range(len(unique)):
            for j in range(i + 1, len(unique)):
                pair_freq[(unique[i], unique[j])] += 1
    for (a, b), cnt in pair_freq.most_common(10):
        if cnt >= 2:
            L.append(f"| {short(a)} + {short(b)} | {cnt} | {cnt/n*100:.0f}% |")

    return '\n'.join(L) + '\n', {}
