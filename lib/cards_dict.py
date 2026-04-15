"""Minimal cards_dict helpers ported from analisidef/lib/cards_dict.py.

Only the 4 helpers required by pipelines/playbook/generator.py:
  - _classify_removal(ability) -> str | None
  - _is_draw(ability) -> bool
  - _is_ramp(ability) -> bool
  - _parse_shift_cost(ability) -> int | None

Source: analisidef/lib/cards_dict.py (lines 46-167). Copied verbatim so behaviour
stays identical; see that file for the full dictionary builder.
"""
from __future__ import annotations

import re


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


def _parse_shift_cost(ability):
    """Estrae costo shift. Returns int o None."""
    if not ability:
        return None
    m = re.search(r'\bShift\s+(\d+)', ability, re.IGNORECASE)
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
