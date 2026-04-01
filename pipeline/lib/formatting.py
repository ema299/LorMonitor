"""
Funzioni di formattazione per nomi carte e statistiche dal cards_db.
"""

import re


def short(name):
    """Nome abbreviato: 'Elsa - Snow Queen' → 'Elsa (Snow Q)'"""
    if ' - ' in name:
        base, sub = name.split(' - ', 1)
        return f"{base} ({sub[:6].strip()})"
    return name[:30]


def format_card_stats(name, db):
    """Formatta stats sintetiche: 'cost:4 | 3/5 | lore:2'"""
    info = db.get(name, {})
    if not info:
        return ''
    parts = []
    cost = info.get('cost', '')
    if cost:
        parts.append(f"cost:{cost}")
    cls = info.get('classifications', '')
    if 'Floodborn' in cls:
        ab = info.get('ability', '')
        m = re.search(r'Shift\s+(\d+)', ab)
        if m:
            parts.append(f"shift:{m.group(1)}")
    ctype = info.get('type', '')
    if 'Song' in ctype:
        parts.append('song')
    if ctype.startswith('Character'):
        s, w, l = info.get('str', ''), info.get('will', ''), info.get('lore', '')
        if s and w:
            parts.append(f"{s}/{w}")
        if l:
            parts.append(f"lore:{l}")
    return ' | '.join(parts)


def format_ability(name, db, max_len=200):
    """Testo ability troncato."""
    info = db.get(name, {})
    ab = info.get('ability', '')
    if len(ab) > max_len:
        return ab[:max_len] + '...'
    return ab


def is_song(card_info):
    ctype = card_info.get('type', '')
    return 'Song' in ctype


def is_floodborn(card_info):
    cls = card_info.get('classifications', '')
    return 'Floodborn' in cls


def get_shift_cost(card_info):
    ab = card_info.get('ability', '')
    m = re.search(r'Shift\s+(\d+)', ab)
    return int(m.group(1)) if m else None


def get_sing_cost(card_info):
    ab = card_info.get('ability', '')
    m = re.search(r'Sing Together\s+(\d+)', ab)
    return int(m.group(1)) if m else None


def get_card_cost(card_info):
    try:
        return int(card_info.get('cost', '0'))
    except (ValueError, TypeError):
        return 0
