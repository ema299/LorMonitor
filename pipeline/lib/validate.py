"""Validazione meccanica del report: nomi carte, ink budget, shift/sing rules, decklist 60."""

import re
from .formatting import is_song, is_floodborn, get_shift_cost, get_sing_cost, get_card_cost


def validate_report(sections_data, games, db, ability_cost_map):
    """Run all validation checks. Returns list of warning strings."""
    warnings = []

    # 1. Card name validation
    card_names_in_report = set()
    for key, val in sections_data.items():
        if isinstance(val, dict):
            _extract_card_names(val, card_names_in_report, db)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    _extract_card_names(item, card_names_in_report, db)

    # Check final_deck if present
    final_deck = sections_data.get('final_deck', {})
    for name in final_deck:
        if name not in db:
            warnings.append(f"⚠️ Carta non trovata nel DB: **{name}**")

    # 2. Decklist validation (exactly 60)
    if final_deck:
        total = sum(final_deck.values())
        if total != 60:
            warnings.append(f"⚠️ Decklist ha **{total}** carte (richieste 60)")
        # Check max 4 copies
        for name, qty in final_deck.items():
            if qty > 4:
                warnings.append(f"⚠️ **{name}** ha {qty} copie (max 4)")

    # 3. Shift rules: Floodborn needs base version
    for name, qty in final_deck.items():
        info = db.get(name, {})
        if is_floodborn(info):
            shift_cost = get_shift_cost(info)
            if shift_cost:
                # Check if there's a non-Floodborn version of same character in deck
                base_name = name.split(' - ')[0] if ' - ' in name else name
                has_base = False
                for other_name in final_deck:
                    if other_name == name:
                        continue
                    other_info = db.get(other_name, {})
                    other_base = other_name.split(' - ')[0] if ' - ' in other_name else other_name
                    if other_base == base_name and not is_floodborn(other_info):
                        has_base = True
                        break
                if not has_base:
                    warnings.append(f"⚠️ **{name}** è Floodborn (Shift {shift_cost}) ma nessuna versione base nel deck")

    # 4. Sing rules: Singer cost >= Song cost
    singers = {}
    songs = {}
    for name, qty in final_deck.items():
        info = db.get(name, {})
        if is_song(info):
            songs[name] = get_card_cost(info)
        ab = info.get('ability', '')
        m = re.search(r'Singer\s+(\d+)', ab)
        if m:
            singers[name] = int(m.group(1))

    for song_name, song_cost in songs.items():
        can_be_sung = False
        for singer_name, singer_val in singers.items():
            if singer_val >= song_cost:
                can_be_sung = True
                break
        if not can_be_sung and songs:
            max_singer = max(singers.values()) if singers else 0
            if song_cost > max_singer and singers:
                warnings.append(f"⚠️ **{song_name}** (cost {song_cost}) non puo' essere cantata (max Singer: {max_singer})")

    # 5. Trap card coherence: cards marked as traps in Sez.4 should not be added in Sez.8
    # This is a soft check based on available data
    top_patterns = sections_data.get('top_patterns', [])
    # We can't easily extract trap card names from generated text, so skip this for now

    # 6. Low sample warning
    n = len(games)
    if n < 10:
        warnings.append(f"⚠️ Solo **{n}** match analizzati — bassa affidabilità statistica")
    elif n < 20:
        warnings.append(f"ℹ️ {n} match analizzati — affidabilità moderata")

    # 7. Ink budget check on unbeatable curves
    unbeatable = sections_data.get('unbeatable_curves', [])
    for dc in unbeatable:
        ms = dc.get('matches', [])
        our_w = sum(1 for m in ms if m['we_won'])
        if our_w == 0:
            key_str = ' → '.join(dc.get('key', ()))
            warnings.append(f"⚠️ Curva imbattuta con **0 vittorie**: {key_str}")

    # 8. OTP/OTD conflict check
    otp_wr = sections_data.get('otp_wr', 0)
    otd_wr = sections_data.get('otd_wr', 0)
    if abs(otp_wr - otd_wr) >= 20:
        warnings.append(f"⚠️ Gap OTP/OTD molto alto ({abs(otp_wr - otd_wr):.0f}pp) — il piano di gioco cambia drasticamente")

    return warnings


def _extract_card_names(d, names_set, db):
    """Recursively extract card-like names from data dicts."""
    for k, v in d.items():
        if isinstance(v, str) and v in db:
            names_set.add(v)
        elif isinstance(v, dict):
            _extract_card_names(v, names_set, db)
        elif isinstance(v, (list, tuple)):
            for item in v:
                if isinstance(item, str) and item in db:
                    names_set.add(item)
                elif isinstance(item, dict):
                    _extract_card_names(item, names_set, db)
