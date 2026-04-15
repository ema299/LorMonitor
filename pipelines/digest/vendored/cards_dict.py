# VENDORED da legacy cards_dict.py @ commit 58288f36a6e41b1830efab0941223e7160b84450
# Congelato 15/04/2026 per Sprint P1.5 — NON MODIFICARE LOGICA.
# Fix applicati: solo import paths. Vedi docs/SPRINT_P1.5_VENDORED.md.
"""
Dizionario carte normalizzato per double-check nella pipeline.

Costruisce un lookup {nome_carta → CardEntry} con:
- Dati base: cost, type, str, will, lore, ink, set, classifications
- Flag derivati: is_song, is_floodborn, is_character, is_item, is_location, is_action
- Keyword parsate: shift_cost, singer_cost, keywords[] (Ward, Evasive, Rush, Resist, Bodyguard, Reckless, Support, Vanish)
- Resist value
- Ramp flag (carte che aggiungono ink all'inkwell)
- Draw flag (carte che pescano)
- Removal info (tipo di removal dal testo ability)

Uso:
    from lib.cards_dict import build_cards_dict
    cards = build_cards_dict()          # tutte le carte legali
    cards = build_cards_dict(db=db)     # passa db gia' caricato

    c = cards['Elsa - Snow Queen']
    c['cost']           # 4
    c['keywords']       # ['Ward']
    c['is_floodborn']   # False
    c['shift_cost']     # None
    c['removal_type']   # 'damage_etb'
"""

import re

from .loader import LEGAL_SETS, load_cards_db


# ── Keyword parsing ──────────────────────────────────────────

_KEYWORD_PATTERNS = {
    'Bodyguard':  r'\bBodyguard\b',
    'Challenger': r'\bChallenger\b',
    'Evasive':    r'\bEvasive\b',
    'Reckless':   r'\bReckless\b',
    'Resist':     r'\bResist\b',
    'Rush':       r'\bRush\b',
    'Shift':      r'\bShift\s+\d+',
    'Singer':     r'\bSinger\s+\d+',
    'Support':    r'\bSupport\b',
    'Vanish':     r'\bVanish\b',
    'Ward':       r'\bWard\b',
}

_RAMP_PATTERNS = [
    r'additional ink',
    r'put.*into.*inkwell',
    r'card into your inkwell',
    r'into your inkwell exerted',
]

_DRAW_PATTERNS = [
    r'draw\s+\d+\s+card',
    r'draw\s+a\s+card',
    r'draws?\s+card',
    r'look at the top.*put.*into your hand',
]

_REMOVAL_PATTERNS = [
    ('banish_etb',     r'when.*play.*banish'),
    ('banish_etb',     r'when.*enters.*banish'),
    ('damage_etb',     r'when.*play.*deal\s+\d+\s+damage'),
    ('damage_etb',     r'when.*enters.*deal\s+\d+\s+damage'),
    ('damage_etb',     r'when.*play.*\d+\s+damage\s+to'),
    ('exert_etb',      r'when.*play.*exert.*chosen'),
    ('exert_etb',      r'when.*enters.*exert.*chosen'),
    ('bounce',         r'return.*chosen.*to.*hand'),
    ('bounce',         r'return.*to their player'),
    ('tuck',           r'put.*chosen.*on.*top.*deck'),
    ('tuck',           r'put.*chosen.*bottom.*deck'),
    ('tuck',           r'put.*on the bottom of.*deck'),
    ('tuck',           r'shuffle.*chosen.*into.*deck'),
    ('tuck',           r'shuffle chosen.*into their'),
    ('damage_all',     r'deal\s+\d+\s+damage.*each\s+opposing'),
    ('damage_all',     r'\d+\s+damage\s+to\s+each\s+opposing'),
    ('banish_all',     r'banish\s+all\s+opposing'),
    ('banish_cond',    r'banish.*all.*damaged'),
    ('tuck_all',       r'put\s+all\s+opposing.*bottom.*deck'),
    ('tuck_all',       r'put\s+all\s+opposing.*on the bottom'),
    ('damage_counter', r'put.*damage\s+counter'),
    ('banish_spell',   r'banish\s+chosen'),
    ('damage_spell',   r'deal\s+\d+\s+damage.*chosen'),
    ('damage_spell',   r'deal damage to chosen.*equal'),
]


def _safe_int(v):
    try:
        return int(v)
    except (ValueError, TypeError):
        return 0


def _parse_keywords(ability):
    """Estrae keyword list dall'ability text."""
    if not ability:
        return []
    found = []
    for kw, pat in _KEYWORD_PATTERNS.items():
        if re.search(pat, ability, re.IGNORECASE):
            found.append(kw)
    return found


def _parse_shift_cost(ability):
    """Estrae costo shift. Returns int o None."""
    if not ability:
        return None
    m = re.search(r'\bShift\s+(\d+)', ability, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _parse_singer_cost(ability):
    """Estrae costo singer. Returns int o None."""
    if not ability:
        return None
    m = re.search(r'\bSinger\s+(\d+)', ability, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _parse_sing_together_cost(ability):
    """Estrae costo Sing Together. Returns int o None."""
    if not ability:
        return None
    m = re.search(r'\bSing Together\s+(\d+)', ability, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _parse_challenger_bonus(ability):
    """Estrae bonus challenger. Returns int o None."""
    if not ability:
        return None
    m = re.search(r'\bChallenger\s*\+(\d+)', ability, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _parse_resist_value(ability):
    """Estrae valore resist. Returns int o None."""
    if not ability:
        return None
    m = re.search(r'\bResist\s*\+(\d+)', ability, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _is_ramp(ability):
    if not ability:
        return False
    a = ability.lower()
    return any(re.search(p, a) for p in _RAMP_PATTERNS)


def _is_draw(ability):
    if not ability:
        return False
    a = ability.lower()
    return any(re.search(p, a) for p in _DRAW_PATTERNS)


def _classify_removal(ability):
    """Ritorna il tipo di removal o None."""
    if not ability:
        return None
    a = ability.lower()
    for rtype, pat in _REMOVAL_PATTERNS:
        if re.search(pat, a):
            return rtype
    return None


# ── Ability profile parsing ──────────────────────────────────

_TRIGGER_PATTERNS = [
    ('etb',        r'when you play this|when this character enters|when (?:he|she|it|they) enters'),
    ('quest',      r'whenever this character quests|while this character quests|when this character quests'),
    ('challenge',  r'whenever this character challenges|when this character challenges|during a challenge'),
    ('banished',   r'when this character is banished|whenever this character is banished'),
    ('activated',  r'⬡|exert\b.*\bto\b'),
]
# If none matches → 'passive'

_EFFECT_PATTERNS = [
    ('draw',           r'draw \d+ cards?|draw a card|put .* into your hand'),
    ('ramp',           r'into your inkwell|additional ink|pay \d+ ⬡ less|costs? \d+ ⬡? ?less'),
    ('damage',         r'deal \d+ damage|deals? \d+ damage'),
    ('banish',         r'banish(?:es)?\s'),
    ('bounce',         r'return.*to.*(?:hand|player)|put.*into.*hand'),
    ('tuck',           r'(?:bottom|top) of (?:their|your|the) deck|shuffle.*into.*deck'),
    ('buff',           r'gets? \+\d+|get \+\d+|gains? \+\d+'),
    ('heal',           r'remove \d+ damage|heal'),
    ('discard_opp',    r'(?:chosen )?opposing player.*discard|each opponent.*discard|opponent discards'),
    ('play_from_disc', r'play.*from.*discard|from (?:your |their )?discard'),
    ('search',         r'search your deck'),
    ('protect',        r"can't be challenged|can't be banished|gains? (?:Ward|Resist)"),
    ('lore_gain',      r'gain \d+ (?:additional )?lore'),
    ('exert_opp',      r'exert (?:chosen|all|each) (?:opposing )?character'),
    ('ready',          r'ready (?:this|chosen|your)'),
]

_SCOPE_PATTERNS = [
    ('all_opposing', r'(?:all|each) opposing|all (?:opposing )?characters'),
    ('all',          r'(?:all|each) characters|all characters'),
    ('self',         r'this character|gains?\b'),
]
# Default → 'single'


def _parse_ability_profile(ability):
    """Parsa ability text in profilo strutturato {trigger, effects, scope}.

    Detection generica basata su pattern — nuove carte vengono auto-classificate.
    Se un effetto non matcha nessun pattern, non viene incluso (evita rumore).
    """
    if not ability:
        return None
    a = ability.lower()

    # Trigger
    trigger = 'passive'
    for trig_name, pat in _TRIGGER_PATTERNS:
        if re.search(pat, a, re.IGNORECASE):
            trigger = trig_name
            break

    # Effects (può averne multipli)
    effects = []
    for eff_name, pat in _EFFECT_PATTERNS:
        if re.search(pat, a, re.IGNORECASE):
            effects.append(eff_name)
    if not effects:
        return None  # nessun effetto riconosciuto → skip

    # Scope
    scope = 'single'
    for scope_name, pat in _SCOPE_PATTERNS:
        if re.search(pat, a, re.IGNORECASE):
            scope = scope_name
            break

    return {
        'trigger': trigger,
        'effects': effects,
        'scope': scope,
    }


# ── Builder principale ────────────────────────────────────────

def build_cards_dict(db=None, legal_only=True):
    """Costruisce dizionario carte normalizzato.

    Args:
        db: cards_db dict. Se None, lo carica.
        legal_only: se True, filtra solo carte dei set legali.

    Returns:
        dict {nome_carta: CardEntry dict}
    """
    if db is None:
        db = load_cards_db()

    cards = {}
    for name, d in db.items():
        # Filtro set legali
        if legal_only:
            sets = d.get('set', '').split('\n')
            if not any(s in LEGAL_SETS for s in sets):
                continue

        ability = d.get('ability', '') or ''
        card_type = d.get('type', '')
        classifications = d.get('classifications', '') or ''
        # API uses subtypes list; local DB uses classifications string
        subtypes = d.get('subtypes', []) or []
        subtypes_str = ' '.join(subtypes) if isinstance(subtypes, list) else str(subtypes)

        cards[name] = {
            # Dati base
            'cost':            _safe_int(d.get('cost', 0)),
            'type':            card_type,
            'str':             _safe_int(d.get('str', 0)),
            'will':            _safe_int(d.get('will', 0)),
            'lore':            _safe_int(d.get('lore', 0)),
            'ink':             d.get('ink', ''),
            'set':             d.get('set', '').split('\n')[-1],
            'classifications': classifications,
            'ability':         ability,

            # Flag tipo — check both type string and subtypes (API vs local)
            'is_character':    card_type.lower() in ('character',) or 'Character' in card_type,
            'is_action':       'action' in card_type.lower() or 'Action' in card_type,
            'is_song':         'Song' in card_type or 'Song' in subtypes_str,
            'is_item':         card_type.lower() == 'item' or card_type == 'Item',
            'is_location':     'location' in card_type.lower() or 'Location' in card_type,
            'is_floodborn':    'Floodborn' in classifications or 'Floodborn' in subtypes_str,

            # Keyword
            'keywords':        _parse_keywords(ability),
            'shift_cost':      _parse_shift_cost(ability),
            'singer_cost':     _parse_singer_cost(ability),
            'sing_together_cost': _parse_sing_together_cost(ability),
            'challenger_bonus': _parse_challenger_bonus(ability),
            'resist_value':    _parse_resist_value(ability),

            # Ruoli tattici
            'is_ramp':         _is_ramp(ability),
            'is_draw':         _is_draw(ability),
            'removal_type':    _classify_removal(ability),

            # Ability profile (trigger + effects + scope)
            'ability_profile':  _parse_ability_profile(ability),

            # Derivati utili
            'base_name':       name.split(' - ')[0] if ' - ' in name else name,
            'subtitle':        name.split(' - ')[1] if ' - ' in name else '',
        }

    return cards


def lookup(cards, name):
    """Cerca una carta per nome esatto o parziale. Returns (name, entry) o None."""
    if name in cards:
        return name, cards[name]
    # Cerca per base name
    nl = name.lower()
    for cn, ce in cards.items():
        if cn.lower() == nl:
            return cn, ce
    # Cerca parziale
    matches = [(cn, ce) for cn, ce in cards.items() if nl in cn.lower()]
    if len(matches) == 1:
        return matches[0]
    return None


def validate_card_name(cards, name):
    """Verifica che una carta esista nel dizionario. Returns True/False."""
    if name in cards:
        return True
    return any(cn.lower() == name.lower() for cn in cards)


def get_shift_bases(cards, name):
    """Per un Floodborn, trova tutte le versioni base con lo stesso nome."""
    entry = cards.get(name)
    if not entry or not entry['is_floodborn']:
        return []
    base = entry['base_name']
    return [(cn, ce) for cn, ce in cards.items()
            if ce['base_name'] == base and not ce['is_floodborn'] and ce['is_character']]


def get_singers_for(cards, song_cost):
    """Trova tutti i personaggi che possono cantare una song di costo dato."""
    result = []
    for cn, ce in cards.items():
        if not ce['is_character']:
            continue
        # Singer keyword
        if ce['singer_cost'] and ce['singer_cost'] >= song_cost:
            result.append((cn, ce, 'singer'))
        # Printed cost >= song cost
        elif ce['cost'] >= song_cost:
            result.append((cn, ce, 'cost'))
    return result
