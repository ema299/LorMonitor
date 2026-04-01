"""
Dump completo turno-per-turno di tutte le partite per un matchup.
"""

from .formatting import short
from .stats import split_wins_losses


def _format_game(g, max_t=12):
    """Formatta una singola partita come testo."""
    lines = []
    result = "WIN" if g['we_won'] else "LOSS"
    lines.append(f"[{result}, durata T{g['length']}]")

    for tn in range(1, min(g['length'] + 1, max_t + 1)):
        t = g['turns'].get(tn)
        if not t:
            continue

        parts = [f"T{tn}"]

        opp_plays = ', '.join(f"{short(n)}({c})" for n, c in t['opp_plays']) or '-'
        our_plays = ', '.join(f"{short(n)}({c})" for n, c in t['our_plays']) or '-'
        parts.append(f"avv: {opp_plays}")
        parts.append(f"noi: {our_plays}")

        for ch in t['opp_challenges']:
            kill = "KILL" if ch['def_killed'] else ""
            atk_die = " (suicida)" if ch['atk_killed'] else ""
            parts.append(f"  avv challenge: {short(ch['attacker'])}(str:{ch['str']}+{ch['ch_bonus']}) → {short(ch['defender'])} {kill}{atk_die}")

        for ch in t['our_challenges']:
            kill = "KILL" if ch['def_killed'] else ""
            atk_die = " (suicida)" if ch['atk_killed'] else ""
            parts.append(f"  NOI challenge: {short(ch['attacker'])}(str:{ch['str']}+{ch['ch_bonus']}) → {short(ch['defender'])} {kill}{atk_die}")

        for ab in t['opp_abilities']:
            eff = ab['effect'][:60]
            if eff and 'had no effect' not in eff:
                parts.append(f"  avv ability: {short(ab['card'])} → {eff}")
        for ab in t['our_abilities']:
            eff = ab['effect'][:60]
            if eff and 'had no effect' not in eff:
                parts.append(f"  NOI ability: {short(ab['card'])} → {eff}")

        if t['opp_dead']:
            parts.append(f"  avv morti: {', '.join(short(n) for n in t['opp_dead'])}")
        if t['our_dead']:
            parts.append(f"  NOI morti: {', '.join(short(n) for n in t['our_dead'])}")

        if t.get('opp_bounced'):
            parts.append(f"  avv bounced: {', '.join(short(n) for n in t['opp_bounced'])}")
        if t.get('our_bounced'):
            parts.append(f"  NOI bounced: {', '.join(short(n) for n in t['our_bounced'])}")

        parts.append(f"  lore: noi {t['our_lore']} / avv {t['opp_lore']}")
        lines.append('\n  '.join(parts))

    return '\n'.join(lines)


def generate(our_deck, opp_deck, games, db):
    wins, losses = split_wins_losses(games)

    out = []
    out.append(f"# Sequenze Complete: {our_deck} vs {opp_deck}")
    out.append(f"")
    out.append(f"**{len(games)} games ({len(wins)}W / {len(losses)}L)**")
    out.append(f"")

    out.append(f"## LOSS ({len(losses)} games)")
    out.append(f"")
    for i, g in enumerate(losses):
        out.append(f"### Loss #{i+1}")
        out.append(f"```")
        out.append(_format_game(g))
        out.append(f"```")
        out.append(f"")

    out.append(f"## WIN ({len(wins)} games)")
    out.append(f"")
    for i, g in enumerate(wins):
        out.append(f"### Win #{i+1}")
        out.append(f"```")
        out.append(_format_game(g))
        out.append(f"```")
        out.append(f"")

    return '\n'.join(out)
