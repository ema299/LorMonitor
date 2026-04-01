"""Sezione 9: Note Strategiche (LLM Review) — valutazione, cause sconfitta, piano di gioco."""

from collections import Counter
from .formatting import short


def generate(our, opp, games, db, **ctx):
    loss_classes = ctx.get('loss_classes', [])

    L = [f"## 7. Note Strategiche (LLM Review)\n"]
    L.append(f"_Analisi automatica dei dati {our} vs {opp}._\n")

    wins = [g for g in games if g['we_won']]
    losses = [g for g in games if not g['we_won']]
    n_w, n_l = len(wins), len(losses)
    total = n_w + n_l
    wr = n_w / total * 100 if total else 0

    otp_w = [g for g in wins if g.get('we_otp')]
    otp_l = [g for g in losses if g.get('we_otp')]
    otd_w = [g for g in wins if not g.get('we_otp')]
    otd_l = [g for g in losses if not g.get('we_otp')]
    otp_wr = len(otp_w) / (len(otp_w) + len(otp_l)) * 100 if (len(otp_w) + len(otp_l)) > 0 else 0
    otd_wr = len(otd_w) / (len(otd_w) + len(otd_l)) * 100 if (len(otd_w) + len(otd_l)) > 0 else 0
    gap = otp_wr - otd_wr

    # 9a. Matchup evaluation
    L.append("### 7a. Valutazione Matchup\n")
    if wr >= 55:
        L.append(f"Matchup **favorevole** ({wr:.0f}% WR). ")
    elif wr >= 48:
        L.append(f"Matchup **equilibrato** ({wr:.0f}% WR). ")
    else:
        L.append(f"Matchup **sfavorito** ({wr:.0f}% WR). ")

    if gap >= 15:
        L.append(f"Gap OTP/OTD molto alto ({gap:.0f}pp): il coin flip conta molto. OTP {otp_wr:.0f}% vs OTD {otd_wr:.0f}%.\n")
    elif gap >= 8:
        L.append(f"Gap OTP/OTD significativo ({gap:.0f}pp): OTP {otp_wr:.0f}% vs OTD {otd_wr:.0f}%.\n")
    else:
        L.append(f"Gap OTP/OTD contenuto ({gap:.0f}pp): il matchup non dipende troppo dal coin flip.\n")

    # 9b. Why we lose (dal classify incrementale)
    L.append("### 7b. Perche' Perdiamo\n")
    if loss_classes:
        # Aggregazione cause
        all_causes = Counter()
        crit_turns = Counter()
        for lc in loss_classes:
            for c in lc['causes']:
                all_causes[c] += 1
            crit_turns[lc['critical_turn']] += 1

        # Top cause
        for cause, cnt in all_causes.most_common(5):
            pct = cnt / n_l * 100 if n_l > 0 else 0
            L.append(f"- **{cause}** in {pct:.0f}% delle sconfitte ({cnt}/{n_l})")
        L.append("")

        # Turno critico medio
        if crit_turns:
            avg_ct = sum(t * n for t, n in crit_turns.items()) / sum(crit_turns.values())
            most_common_t = crit_turns.most_common(1)[0]
            L.append(f"Turno critico medio: T{avg_ct:.1f} (piu' frequente: T{most_common_t[0]} con {most_common_t[1]} loss)\n")
    else:
        L.append("_Nessun pattern di sconfitta dominante._\n")

    # 9c. Bounce/tuck impact
    bt_games = 0
    bt_losses = 0
    bt_victims = Counter()
    for g in games:
        has_bt = False
        for t in range(1, 11):
            td = g['turns'].get(t, {})
            bounced = td.get('our_bounced', [])
            if bounced:
                has_bt = True
                for n in bounced:
                    bt_victims[n] += 1
        if has_bt:
            bt_games += 1
            if not g['we_won']:
                bt_losses += 1

    if bt_games >= 5:
        bt_wr = (bt_games - bt_losses) / bt_games * 100
        L.append("### 7c. Impatto Bounce/Tuck\n")
        L.append(f"In **{bt_games}** partite ({bt_games/total*100:.0f}%) l'avversario ci ha bouncato. ")
        L.append(f"WR in queste partite: **{bt_wr:.0f}%** (vs {wr:.0f}% generale).\n")
        if bt_victims:
            L.append("**Carte piu' colpite (vulnerabilita' STR <=2):**\n")
            L.append("| Carta | Volte rimossa | STR | Vulnerabile a UTS |")
            L.append("|---|---|---|---|")
            for name, count in bt_victims.most_common(10):
                cdata = db.get(name)
                card_str = '?'
                vuln = '?'
                if cdata:
                    s = cdata.get('str', '')
                    try:
                        s_int = int(s) if s else 0
                        card_str = str(s_int)
                        vuln = '**SI**' if s_int <= 2 else 'No'
                    except ValueError:
                        pass
                L.append(f"| {short(name)} | {count}x | {card_str} | {vuln} |")
            L.append("")

    # 9d. Key interactions
    L.append("### 7d. Interazioni Chiave\n")
    L.append("**Cosa funziona (dalle vittorie):**\n")
    for t in range(1, 6):
        win_cards = Counter()
        loss_cards = Counter()
        for g in wins:
            for name, cost in g['turns'].get(t, {}).get('our_plays', []):
                win_cards[name] += 1
        for g in losses:
            for name, cost in g['turns'].get(t, {}).get('our_plays', []):
                loss_cards[name] += 1
        diffs = []
        for card in set(win_cards) | set(loss_cards):
            wc, lc = win_cards.get(card, 0), loss_cards.get(card, 0)
            if wc + lc < 5:
                continue
            w_rate = wc / n_w if n_w else 0
            l_rate = lc / n_l if n_l else 0
            diffs.append((card, w_rate, l_rate, w_rate - l_rate))
        diffs.sort(key=lambda x: -x[3])
        if diffs and diffs[0][3] > 0.02:
            top1 = diffs[0]
            s = f"- **T{t}:** {short(top1[0])} ({top1[1]*100:.0f}% W vs {top1[2]*100:.0f}% L, +{top1[3]*100:.0f}pp)"
            if len(diffs) > 1 and diffs[1][3] > 0.02:
                top2 = diffs[1]
                s += f" | {short(top2[0])} (+{top2[3]*100:.0f}pp)"
            L.append(s)
    L.append("")

    # Traps
    L.append("**Trappole (NON giocare):**\n")
    for t in range(1, 6):
        win_cards = Counter()
        loss_cards = Counter()
        for g in wins:
            for name, cost in g['turns'].get(t, {}).get('our_plays', []):
                win_cards[name] += 1
        for g in losses:
            for name, cost in g['turns'].get(t, {}).get('our_plays', []):
                loss_cards[name] += 1
        diffs = []
        for card in set(win_cards) | set(loss_cards):
            wc, lc = win_cards.get(card, 0), loss_cards.get(card, 0)
            if wc + lc < 5:
                continue
            w_rate = wc / n_w if n_w else 0
            l_rate = lc / n_l if n_l else 0
            diffs.append((card, w_rate, l_rate, w_rate - l_rate))
        diffs.sort(key=lambda x: x[3])
        if diffs and diffs[0][3] < -0.03:
            trap = diffs[0]
            L.append(f"- **T{t}:** {short(trap[0])} ({trap[2]*100:.0f}% L vs {trap[1]*100:.0f}% W, {trap[3]*100:.0f}pp)")
    L.append("")

    # 9e. Game plan
    L.append(f"### 7e. Piano di Gioco vs {opp}\n")

    L.append("**OTP:**")
    otp_plan = []
    for t in range(1, 6):
        win_cards = Counter()
        for g in otp_w:
            for name, cost in g['turns'].get(t, {}).get('our_plays', []):
                win_cards[name] += 1
        if win_cards:
            top_card = win_cards.most_common(1)[0]
            freq = top_card[1] / len(otp_w) * 100 if otp_w else 0
            if freq >= 15:
                otp_plan.append(f"T{t} {short(top_card[0])} ({freq:.0f}%)")
    if otp_plan:
        L.append(' \u2192 '.join(otp_plan))
    L.append("")

    L.append("**OTD:**")
    otd_plan = []
    for t in range(1, 6):
        win_cards = Counter()
        for g in otd_w:
            for name, cost in g['turns'].get(t, {}).get('our_plays', []):
                win_cards[name] += 1
        if win_cards:
            top_card = win_cards.most_common(1)[0]
            freq = top_card[1] / len(otd_w) * 100 if otd_w else 0
            if freq >= 15:
                otd_plan.append(f"T{t} {short(top_card[0])} ({freq:.0f}%)")
    if otd_plan:
        L.append(' \u2192 '.join(otd_plan))
    L.append("")

    return '\n'.join(L) + '\n', {}
