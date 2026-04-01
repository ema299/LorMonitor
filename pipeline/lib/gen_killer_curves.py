"""
Genera .md con curve killer T1-T7: cosa succede nei primi 7 turni
e come la situazione a T6-T7 predice il risultato.
"""

import re
from collections import Counter, defaultdict
from .formatting import short, format_card_stats, format_ability
from .stats import (split_wins_losses, avg, coplay_by_turn,
                    lore_at_turn, card_frequency_in_losses)

MAX_TURN = 7


def _db_lookup(name, db):
    """Look up a card in the DB, with fallback fuzzy match for minor name differences."""
    if name in db:
        return db[name]
    # Normalize: strip extra commas/spaces for comparison
    norm = re.sub(r'[,\s]+', ' ', name.lower()).strip()
    for db_name, info in db.items():
        db_norm = re.sub(r'[,\s]+', ' ', db_name.lower()).strip()
        if db_norm == norm:
            return info
    return {}


def card_tactical_from_db(name, db):
    """Build tactical effect description from DB ability text (source of truth).
    Returns a concise string describing what the card ACTUALLY does.
    """
    info = _db_lookup(name, db)
    if not info:
        return ''
    ab = info.get('ability', '')
    ab_lower = ab.lower()
    ctype = info.get('type', '')
    cls = info.get('classifications', '')
    lore = info.get('lore', '')
    cost = int(info.get('cost', 0) or 0)

    parts = []

    # ═══ OFFICIAL KEYWORDS (Lorcana Comprehensive Rules §10) ═══

    # Bodyguard (§10.2): enters exerted, opponents must challenge this first
    if 'Bodyguard' in ab:
        parts.append('Bodyguard')

    # Challenger +N (§10.3): +N STR while challenging only
    cm = re.search(r'Challenger\s*\+(\d+)', ab)
    if cm:
        parts.append(f"Challenger +{cm.group(1)}")

    # Evasive (§10.4): can only be challenged by Evasive characters
    if 'Evasive' in ab:
        parts.append('Evasive')

    # Reckless (§10.5): can't quest, must challenge each turn if able
    if re.search(r'\bReckless\b', ab) and 'gains Reckless' not in ab:
        parts.append('Reckless (no quest, must challenge)')

    # Resist +N (§10.6): damage reduced by N, stacks
    rm = re.search(r'Resist\s*\+?(\d+)', ab)
    if rm:
        parts.append(f"Resist +{rm.group(1)}")

    # Rush (§10.7): can challenge the turn played
    if re.search(r'\bRush\b', ab):
        parts.append('Rush')

    # Shift N (§10.8): alt cost, play on top of same-name character
    sm = re.search(r'Shift\s+(\d+)', ab)
    if sm:
        parts.append(f"Shift {sm.group(1)}")

    # Singer N (§10.9): counts as cost N to sing songs
    singm = re.search(r'Singer\s+(\d+)', ab)
    if singm:
        parts.append(f"Singer {singm.group(1)}")

    # Sing Together N (§10.10) — handled below in Song section

    # Support (§10.11): on quest, add STR to another character this turn
    if re.search(r'\bSupport\b', ab):
        parts.append('Support')

    # Vanish (§10.12): banished when targeted by action instead of effect resolving
    if re.search(r'\bVanish\b', ab):
        parts.append('Vanish')

    # Ward (§10.13): opponents can't choose this except to challenge
    if 'Ward' in ab:
        parts.append('Ward')

    # ═══ SONG / SING TOGETHER ═══

    if 'Song' in ctype:
        stm = re.search(r'Sing Together\s+(\d+)', ab)
        if stm:
            parts.append(f"Song (SingTogether {stm.group(1)})")
        else:
            parts.append(f"Song (cantabile da cost>={cost})")

    # ═══ COMMON EFFECTS (non-keyword abilities) ═══

    # Ramp: inkwell effects
    if 'inkwell' in ab_lower or 'additional ink' in ab_lower:
        if 'additional' in ab_lower:
            parts.append('Ramp +1 ink (immediato)')
        elif 'exerted' in ab_lower:
            parts.append('Ramp +1 ink (exerted, disponibile turno dopo)')
        elif 'draw' in ab_lower:
            parts.append('Ramp +1 ink + Draw 1 (EOT, condizionale)')
        else:
            parts.append('Ramp +1 ink')

    # Draw (only if not already covered by ramp+draw combo)
    if 'draw' in ab_lower and 'inkwell' not in ab_lower:
        dm = re.search(r'draw\s+(\d+)\s+card', ab_lower)
        if dm:
            parts.append(f"Draw {dm.group(1)}")
        elif 'draw cards until' in ab_lower:
            parts.append('Draw fino a pareggio mano')
        elif 'draw a card' in ab_lower:
            parts.append('Draw 1')
        elif 'draw cards' in ab_lower:
            parts.append('Draw N')

    # Look/tutor (Vision, Develop Your Brain)
    if 'look at the top' in ab_lower and 'put one into your hand' in ab_lower:
        m = re.search(r'top\s+(\d+)\s+card', ab_lower)
        n = m.group(1) if m else '?'
        parts.append(f"Cerca (top {n}, prendi 1)")

    # Exert opposing character (Elsa Fifth Spirit, etc.)
    if 'exert chosen opposing' in ab_lower or 'exert chosen character' in ab_lower:
        parts.append('Exert bersaglio avversario')

    # Removal: banish (with restrictions)
    if 'banish' in ab_lower:
        if 'all opposing damaged' in ab_lower:
            parts.append('Banish TUTTI i damaged avversari')
        elif 'chosen item' in ab_lower:
            pay_m = re.search(r'pay\s+(\d+)', ab_lower)
            if pay_m:
                parts.append(f"Banish item (paga {pay_m.group(1)} ink)")
            else:
                parts.append('Banish item')
        elif 'banish chosen' in ab_lower:
            # Check for restrictions in the banish clause
            restriction = ''
            if 'with evasive' in ab_lower:
                restriction = ' (solo Evasive)'
            elif 'with ward' in ab_lower:
                restriction = ' (solo Ward)'
            sm2 = re.search(r'with\s+(\d+)\s+str\s+or\s+more', ab_lower)
            if sm2:
                restriction = f" (solo STR>={sm2.group(1)})"
            sm3 = re.search(r'with\s+(\d+)\s+str\s+or\s+less', ab_lower)
            if sm3:
                restriction = f" (solo STR<={sm3.group(1)})"
            if 'damaged' in ab_lower and 'all opposing' not in ab_lower:
                restriction = ' (solo damaged)'
            parts.append(f"Banish 1 bersaglio{restriction}")
        elif 'banish this' not in ab_lower:
            parts.append('Banish')

    # Bounce: return to hand
    if 'return' in ab_lower and 'hand' in ab_lower:
        # Distinguish return own vs opposing
        if 'return chosen character to their' in ab_lower:
            parts.append('Bounce 1 in mano')
        elif 'return' in ab_lower and 'your hand' in ab_lower and 'discard' in ab_lower:
            parts.append('Recupera da discard')
        else:
            parts.append('Bounce 1 in mano')

    # Shuffle into deck (You're Welcome)
    if 'shuffle' in ab_lower and 'deck' in ab_lower:
        parts.append('Shuffle bersaglio nel mazzo')

    # Tuck: bottom of deck
    if 'bottom of' in ab_lower and 'deck' in ab_lower and 'look' not in ab_lower:
        if 'all opposing' in ab_lower:
            m = re.search(r'(\d+)\s+STR or less', ab)
            if m:
                parts.append(f"Tuck tutti con STR<={m.group(1)} sotto mazzo")
            else:
                parts.append('Tuck tutti sotto mazzo')
        elif 'on the bottom' in ab_lower and 'chosen' not in ab_lower:
            pass  # self-tuck, not relevant tactically
        else:
            parts.append('Tuck sotto mazzo')

    # Targeted damage (deal N damage to chosen)
    deal_m = re.search(r'deal\s+(\d+)\s+damage\s+to\s+chosen', ab_lower)
    if deal_m:
        parts.append(f"Deal {deal_m.group(1)} danno a bersaglio")
    elif 'damage to chosen' in ab_lower and 'deal' not in ab_lower:
        dm2 = re.search(r'(\d+)\s+damage\s+to\s+chosen', ab_lower)
        if dm2:
            parts.append(f"Deal {dm2.group(1)} danno a bersaglio")

    # AoE damage (damage counter on each, damage to each opposing)
    if 'damage counter' in ab_lower or 'damage on each' in ab_lower:
        if 'each opposing' in ab_lower:
            parts.append('1 danno a OGNI pezzo avversario')
        else:
            parts.append('Danno')
    elif 'damage to each opposing' in ab_lower:
        parts.append('1 danno a OGNI pezzo avversario')

    # Move damage between characters
    if 'move' in ab_lower and 'damage' in ab_lower:
        if 'from chosen character' in ab_lower and 'to chosen opposing' in ab_lower:
            parts.append('Sposta danno su avversario')
        elif 'to chosen opposing' in ab_lower:
            parts.append('Sposta danno su avversario')

    # Heal / remove damage
    if 'remove' in ab_lower and 'damage' in ab_lower:
        rm2 = re.search(r'remove\s+(?:up\s+to\s+)?(\d+)\s+damage', ab_lower)
        if rm2:
            if 'each of your' in ab_lower:
                parts.append(f"Heal {rm2.group(1)} a tutti i nostri")
            else:
                parts.append(f"Heal {rm2.group(1)}")

    # Reckless forced on opponent
    if 'gains reckless' in ab_lower:
        parts.append('Forza Reckless su avversario')

    # Can't quest / can't challenge debuff on opposing
    if "can't quest" in ab_lower and 'opposing' in ab_lower:
        parts.append('Impedisce quest avversario')
    if "can't challenge" in ab_lower and 'opposing' in ab_lower:
        parts.append('Impedisce challenge avversario')

    # Gain lore (conditional)
    gain_lore_m = re.search(r'gain\s+(\d+)\s+lore', ab_lower)
    if gain_lore_m:
        parts.append(f"Gain {gain_lore_m.group(1)} lore")

    # Ready another character
    if 'ready chosen' in ab_lower or 'ready this character' in ab_lower:
        if 'ready chosen' in ab_lower:
            parts.append('Ready bersaglio')
        # self-ready less tactically relevant unless combo

    # Discard opponent's cards
    if 'discard' in ab_lower:
        if 'chosen opponent discards' in ab_lower or 'opponent discards' in ab_lower:
            parts.append('Discard avversario')
        elif 'discard a card' in ab_lower and 'opponent' not in ab_lower:
            pass  # self-discard cost, not relevant
        elif 'from your discard' in ab_lower:
            pass  # discard as zone reference
        else:
            parts.append('Discard avversario')

    # ═══ TACTICAL EFFECTS (buff/debuff/utility) ═══

    # Cost reduction (Grandmother Willow, Lantern, Heart of Atlantis)
    pay_less = re.search(r'pay\s+(\d+)\s+.*less', ab_lower)
    if pay_less:
        n = pay_less.group(1)
        parts.append(f"Riduce costo prossimo personaggio di {n}")

    # Play for free
    if 'play' in ab_lower and 'for free' in ab_lower:
        free_m = re.search(r'cost\s+(\d+)\s+or less', ab_lower)
        if free_m:
            parts.append(f"Gioca gratis personaggio cost<={free_m.group(1)}")
        else:
            parts.append('Gioca gratis')

    # STR buff to others (aura/static)
    str_buff = re.search(r'(?:get|gets|gain|gains)\s*\+(\d+)\s+(?:※|STR|str|strength)', ab_lower)
    if str_buff and ('your' in ab_lower and ('character' in ab_lower or 'princess' in ab_lower
                     or 'prince' in ab_lower or 'seven dwarfs' in ab_lower)):
        parts.append(f"Buff +{str_buff.group(1)} STR ai nostri")

    # LORE buff to others or self (conditional)
    lore_buff = re.search(r'(?:get|gets|gain|gains)\s*\+(\d+)\s+(?:※|LORE|lore)', ab_lower)
    if lore_buff and 'this character' in ab_lower:
        parts.append(f"+{lore_buff.group(1)} Lore (condizionale)")

    # STR debuff to opponent (Control Your Temper, etc.)
    str_debuff = re.search(r'(?:get|gets)\s*-(\d+)\s+(?:※|STR|str|strength)', ab_lower)
    if str_debuff:
        parts.append(f"Debuff -{str_debuff.group(1)} STR")

    # Voiceless (can't sing songs)
    if 'voiceless' in ab_lower or "can't exert to sing" in ab_lower:
        parts.append('Voiceless (no canto)')

    # Can't lose lore
    if "can't lose lore" in ab_lower:
        parts.append('Protezione lore')

    # Move damage (Cheshire Cat pattern: move from ANY to ANY)
    if 'move' in ab_lower and 'damage' in ab_lower and 'Sposta danno' not in '; '.join(parts):
        move_m = re.search(r'move\s+(?:up\s+to\s+)?(\d+)\s+damage', ab_lower)
        if move_m:
            parts.append(f"Sposta {move_m.group(1)} danno tra personaggi")

    # Fallback: quester
    if not parts:
        if lore:
            parts.append(f"Quester {lore}L")
        else:
            parts.append('Corpo')

    # Add trigger info where relevant
    triggers = []
    if 'when you play this character' in ab_lower or 'when this character enters' in ab_lower:
        triggers.append('ETB')
    if 'at the end of your turn' in ab_lower:
        triggers.append('EOT')
    if 'whenever this character quests' in ab_lower:
        triggers.append('on quest')
    if 'at the start of your turn' in ab_lower:
        triggers.append('SOT')
    if 'when this character is banished' in ab_lower or 'when this character leaves' in ab_lower:
        triggers.append('on death')

    result = '; '.join(parts)
    if triggers:
        result += f" [{', '.join(triggers)}]"
    return result


def _validate_curve_ink(game, db):
    """Validate ink feasibility for opponent's plays turn by turn.
    Returns list of warning strings (empty = valid).

    Usa i dati reali dal loader: opp_inkwell, opp_play_detail (ink_paid).
    """
    warnings = []
    for t in range(1, 6):
        td = game['turns'].get(t, {})
        inkwell = td.get('opp_inkwell', t)
        spent = td.get('opp_ink_spent', 0)
        if spent > inkwell:
            # Identifica cosa ha sforato
            plays = td.get('opp_play_detail', [])
            play_names = ', '.join(f"{short(p['name'])}({p['ink_paid']})" for p in plays)
            warnings.append(
                f"T{t}: speso {spent} ink ma inkwell={inkwell} ({play_names})")
    return warnings


def generate(our, opp, games, db, **ctx):
    wins, losses = split_wins_losses(games)
    total = len(games)
    if total == 0:
        return "# Nessun match trovato\n", {'unbeatable_curves': []}

    L = []
    L.append(f"# Curve Killer T1-T{MAX_TURN}: {our} vs {opp}")
    L.append(f"")
    L.append(f"**{total} match ({len(wins)}W / {len(losses)}L = {len(wins)/total*100:.0f}% WR)**")
    L.append(f"")

    # ═══ SITUAZIONE A T6 e T7 ═══
    L.append(f"## Situazione a T6 e T7 (condizioni favorevoli?)")
    L.append(f"")
    for check_t in (6, 7):
        lore = lore_at_turn(games, check_t)
        w_dead = [sum(len(g['turns'].get(t, {}).get('our_dead', [])) for t in range(1, check_t+1)) for g in wins]
        l_dead = [sum(len(g['turns'].get(t, {}).get('our_dead', [])) for t in range(1, check_t+1)) for g in losses]
        w_opp_dead = [sum(len(g['turns'].get(t, {}).get('opp_dead', [])) for t in range(1, check_t+1)) for g in wins]
        l_opp_dead = [sum(len(g['turns'].get(t, {}).get('opp_dead', [])) for t in range(1, check_t+1)) for g in losses]
        w_bounced = [sum(len(g['turns'].get(t, {}).get('our_bounced', [])) for t in range(1, check_t+1)) for g in wins]
        l_bounced = [sum(len(g['turns'].get(t, {}).get('our_bounced', [])) for t in range(1, check_t+1)) for g in losses]

        L.append(f"### A T{check_t}")
        L.append(f"")
        L.append(f"| Metrica | WIN | LOSS | Delta |")
        L.append(f"|---------|-----|------|-------|")
        L.append(f"| Nostra lore | {avg(lore['w_our']):.1f} | {avg(lore['l_our']):.1f} | {avg(lore['w_our'])-avg(lore['l_our']):+.1f} |")
        L.append(f"| Lore avversaria | {avg(lore['w_opp']):.1f} | {avg(lore['l_opp']):.1f} | {avg(lore['w_opp'])-avg(lore['l_opp']):+.1f} |")
        L.append(f"| Gap lore (noi - avv) | {avg(lore['w_our'])-avg(lore['w_opp']):.1f} | {avg(lore['l_our'])-avg(lore['l_opp']):.1f} | |")
        L.append(f"| Nostri pezzi morti cumulati | {avg(w_dead):.1f} | {avg(l_dead):.1f} | {avg(w_dead)-avg(l_dead):+.1f} |")
        L.append(f"| Pezzi avv morti cumulati | {avg(w_opp_dead):.1f} | {avg(l_opp_dead):.1f} | {avg(w_opp_dead)-avg(l_opp_dead):+.1f} |")
        L.append(f"| Nostri pezzi bounced cumulati | {avg(w_bounced):.1f} | {avg(l_bounced):.1f} | {avg(w_bounced)-avg(l_bounced):+.1f} |")
        L.append(f"")

        L.append(f"**Distribuzione gap lore a T{check_t}:**")
        L.append(f"")
        for thr in (5, 3, 0, -3, -5):
            w_n = sum(1 for g in wins if g['turns'].get(check_t, {}).get('our_lore', 0) - g['turns'].get(check_t, {}).get('opp_lore', 0) >= thr)
            l_n = sum(1 for g in losses if g['turns'].get(check_t, {}).get('our_lore', 0) - g['turns'].get(check_t, {}).get('opp_lore', 0) >= thr)
            w_pct = w_n/len(wins)*100 if wins else 0
            l_pct = l_n/len(losses)*100 if losses else 0
            L.append(f"- Gap ≥{thr:+d}: W {w_pct:.0f}% | L {l_pct:.0f}%")
        L.append(f"")

    L.append(f"---")
    L.append(f"")

    # Curve Ricorrenti rimosse — le killer curves sono prodotte dall'LLM
    # e integrate nel report dall'assembler (output/killer_curves_*.md)
    unbeatable = []

    # ═══ PLAYBOOK AVVERSARIO T1-T7 ═══
    L.append(f"## Playbook Avversario ({opp}) T1-T{MAX_TURN}")
    L.append(f"")
    L.append(f"_Analisi tattica turno per turno: giocate chiave, combo, e vantaggi generati._")
    L.append(f"")

    for tn in range(1, MAX_TURN + 1):
        # Collect all opponent actions at this turn across all games
        card_count = Counter()       # card name → times played
        card_in_games = Counter()    # card name → number of distinct games
        ability_effects = defaultdict(Counter)  # card → {effect_desc → count}
        combo_count = Counter()      # (cardA, cardB) → count
        turn_kills = []              # names of our pieces killed
        turn_bounced = []            # names of our pieces bounced
        turn_lore = []               # lore gained by opp this turn
        games_with_action = 0

        for g in games:
            td = g['turns'].get(tn, {})
            played = [n for n, c in td.get('opp_plays', [])]
            if played or td.get('opp_abilities') or td.get('opp_challenges') or td.get('opp_quests'):
                games_with_action += 1

            seen_this_game = set()
            for n, c in td.get('opp_plays', []):
                card_count[n] += 1
                if n not in seen_this_game:
                    card_in_games[n] += 1
                    seen_this_game.add(n)

            for ab in td.get('opp_abilities', []):
                eff = ab['effect']
                if 'no effect' in eff.lower() or 'had no effect' in eff.lower():
                    continue
                ability_effects[ab['card']][eff] += 1

            # Combos: cards played together
            unique_played = list(dict.fromkeys(played))  # preserve order, dedupe
            for i in range(len(unique_played)):
                for j in range(i + 1, len(unique_played)):
                    combo_count[tuple(sorted([unique_played[i], unique_played[j]]))] += 1

            for dead_name in td.get('our_dead', []):
                turn_kills.append(dead_name)
            for b_name in td.get('our_bounced', []):
                turn_bounced.append(b_name)

            quest_lore = sum(l for _, l in td.get('opp_quests', []))
            if quest_lore > 0:
                turn_lore.append(quest_lore)

        if not card_count and not turn_kills and not turn_bounced:
            continue

        # Classify turn theme from effects
        turn_tags = []
        all_effects_flat = []
        for card, effs in ability_effects.items():
            for eff_text, cnt in effs.items():
                all_effects_flat.append((eff_text.lower(), cnt))

        has_ramp = any('ink' in e and ('additional' in e or 'grant' in e or 'inkwell' in e) for e, _ in all_effects_flat)
        has_draw = any('draw' in e or 'drew' in e for e, _ in all_effects_flat)
        has_banish = any('banish' in e for e, _ in all_effects_flat)
        has_bounce = any('return' in e for e, _ in all_effects_flat) or len(turn_bounced) > 0
        has_tuck = any('bottom' in e for e, _ in all_effects_flat)
        has_damage = any('damage' in e for e, _ in all_effects_flat)
        has_kills = len(turn_kills) > 0

        if has_ramp: turn_tags.append('Ramp')
        if has_draw: turn_tags.append('Draw')
        if has_banish or has_kills: turn_tags.append('Removal')
        if has_bounce: turn_tags.append('Bounce')
        if has_tuck: turn_tags.append('Tuck')
        if has_damage: turn_tags.append('Damage')

        theme = ' / '.join(turn_tags) if turn_tags else 'Setup'
        action_pct = games_with_action / total * 100 if total else 0

        L.append(f"### T{tn} -- {theme} (attivo in {action_pct:.0f}% delle partite)")
        L.append(f"")

        # Top cards with tactical description
        top_cards = card_in_games.most_common(6)
        L.append(f"| Giocata | Freq | Effetto tattico |")
        L.append(f"|---------|------|-----------------|")

        for card_name, n_games in top_cards:
            if n_games < 2:
                continue
            pct = n_games / total * 100
            stats = format_card_stats(card_name, db)
            tactic_str = card_tactical_from_db(card_name, db)
            L.append(f"| {short(card_name)} [{stats}] | {n_games} ({pct:.0f}%) | {tactic_str} |")
        L.append(f"")

        # Combos at this turn
        top_combos = [(pair, cnt) for pair, cnt in combo_count.most_common(5) if cnt >= 2]
        if top_combos:
            L.append(f"**Combo frequenti a T{tn}:**")
            L.append(f"")
            for (a, b), cnt in top_combos:
                eff_a = card_tactical_from_db(a, db)
                eff_b = card_tactical_from_db(b, db)
                combo_desc = f"{short(a)}: {eff_a} + {short(b)}: {eff_b}"
                L.append(f"- **{short(a)} + {short(b)}** ({cnt}x) -- {combo_desc}")
            L.append(f"")

        # Net impact on us
        if turn_kills or turn_bounced or turn_lore:
            impact_parts = []
            if turn_kills:
                kill_freq = Counter(turn_kills)
                top_killed = ', '.join(f"{short(n)} ({c}x)" for n, c in kill_freq.most_common(3))
                avg_kills = len(turn_kills) / total
                impact_parts.append(f"Nostri pezzi uccisi: {avg_kills:.1f}/partita -- top: {top_killed}")
            if turn_bounced:
                bounce_freq = Counter(turn_bounced)
                top_bounced = ', '.join(f"{short(n)} ({c}x)" for n, c in bounce_freq.most_common(3))
                avg_bounced = len(turn_bounced) / total
                impact_parts.append(f"Nostri pezzi bounced: {avg_bounced:.1f}/partita -- top: {top_bounced}")
            if turn_lore:
                avg_lore = sum(turn_lore) / len(turn_lore)
                impact_parts.append(f"Lore media questata: {avg_lore:.1f}")
            L.append(f"**Impatto su di noi a T{tn}:**")
            L.append(f"")
            for p in impact_parts:
                L.append(f"- {p}")
            L.append(f"")

        L.append(f"---")
        L.append(f"")

    # ═══ ABILITY CARTE CHIAVE DAL DB ═══
    L.append(f"## Ability carte chiave avversarie (dal DB)")
    L.append(f"")
    opp_freq = card_frequency_in_losses(games, 'opp', MAX_TURN)
    for n, cnt in opp_freq.most_common(15):
        info = db.get(n, {})
        if not info:
            continue
        ab = format_ability(n, db)
        if not ab:
            continue
        stats = format_card_stats(n, db)
        pct = cnt / len(losses) * 100 if losses else 0
        L.append(f"- **{n}** [{stats}] -- in {pct:.0f}% delle loss")
        L.append(f"  > {ab}")
        L.append(f"")

    L.append(f"---")
    L.append(f"")

    return '\n'.join(L), {'unbeatable_curves': unbeatable}
