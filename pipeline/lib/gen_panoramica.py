"""Sezione 1: Panoramica matchup — WR, OTP/OTD, durata, progressione lore."""

from .stats import split_wins_losses, avg


def _pct(num, den):
    return f"{100*num/den:.0f}%" if den else '-'


def generate(our, opp, games, db, **ctx):
    wins, losses = split_wins_losses(games)
    n = len(games)
    if n == 0:
        return "## 1. Panoramica\n\n_Nessun match._\n", {}

    n_w = len(wins)
    n_l = len(losses)
    wr = n_w / n * 100

    otp_ms = [g for g in games if g.get('we_otp')]
    otd_ms = [g for g in games if not g.get('we_otp')]
    otp_w = sum(1 for g in otp_ms if g['we_won'])
    otd_w = sum(1 for g in otd_ms if g['we_won'])
    otp_wr = otp_w / len(otp_ms) * 100 if otp_ms else 0
    otd_wr = otd_w / len(otd_ms) * 100 if otd_ms else 0

    win_len = [g['length'] for g in wins]
    loss_len = [g['length'] for g in losses]
    avg_win = avg(win_len)
    avg_loss = avg(loss_len)

    L = [f"## 1. Panoramica\n"]
    L.append("| Metrica | Valore |")
    L.append("|---|---|")
    L.append(f"| Match totali | {n} |")
    L.append(f"| **{our} WR** | **{_pct(n_w, n)}** ({n_w}W-{n_l}L) |")
    L.append(f"| {our} WR OTP | {_pct(otp_w, len(otp_ms))} ({otp_w}W-{len(otp_ms)-otp_w}L, {len(otp_ms)}g) |")
    L.append(f"| {our} WR OTD | {_pct(otd_w, len(otd_ms))} ({otd_w}W-{len(otd_ms)-otd_w}L, {len(otd_ms)}g) |")
    if otp_ms and otd_ms:
        L.append(f"| Gap OTP/OTD | {otp_wr - otd_wr:.0f}pp |")
    L.append(f"| Durata media vittorie | {avg_win:.1f} turni |")
    L.append(f"| Durata media sconfitte | {avg_loss:.1f} turni |")

    # Progressione lore media
    L.append(f"\n### Progressione Lore Media")
    L.append(f"| Turno | {our} | {opp} | Delta |")
    L.append(f"|---|---|---|---|")
    for t in range(1, 7):
        our_l = sum(g['turns'].get(t, {}).get('our_lore', 0) for g in games) / n
        opp_l = sum(g['turns'].get(t, {}).get('opp_lore', 0) for g in games) / n
        delta = our_l - opp_l
        sign = '+' if delta >= 0 else ''
        L.append(f"| T{t} | {our_l:.1f} | {opp_l:.1f} | {sign}{delta:.1f} |")

    data = {
        'wr': wr, 'n_games': n,
        'otp_wr': otp_wr, 'otd_wr': otd_wr,
        'n_w': n_w, 'n_l': n_l,
    }
    return '\n'.join(L) + '\n', data
