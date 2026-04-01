"""Sezione 5: Toolkit Nostro — carte disponibili organizzate per ruolo tattico.
Serve come catalogo per Claude (LLM) per ragionare su risposte alle minacce avversarie."""

import re
from .formatting import short
from .gen_killer_curves import card_tactical_from_db


def _safe_int(v):
    try:
        return int(v)
    except (ValueError, TypeError):
        return 0


def _classify_card_role(name, info):
    """Classify card into tactical roles based on real abilities."""
    ab = info.get('ability', '').lower()
    ctype = info.get('type', '').lower()
    roles = []
    downsides = []

    if "can't ready" in ab or "can't quest" in ab:
        downsides.append('cant_ready')
    if 'enters play with' in ab and 'damage' in ab:
        downsides.append('self_damage')
    if 'while you have a character named' in ab:
        downsides.append('conditional')

    is_etb = 'when you play' in ab or 'when this character enters' in ab
    if is_etb:
        if any(kw in ab for kw in [
            'banish chosen character', 'banish chosen item',
            'damage to chosen opposing', 'damage to another chosen opposing',
            'deal damage to chosen', 'exert chosen opposing',
            'return chosen character to their',
        ]):
            roles.append('removal_etb')
        elif 'damage' in ab and 'opposing' in ab:
            roles.append('removal_etb')

    has_move_damage = 'move' in ab and 'damage' in ab and 'opposing' in ab
    if has_move_damage:
        if is_etb and 'removal_etb' not in roles:
            roles.append('removal_etb')
        elif not is_etb:
            roles.append('removal_recurring')

    if 'removal_recurring' not in roles:
        if any(kw in ab for kw in ['at the start of your turn', 'whenever this character quests']) and \
           any(kw in ab for kw in ['exert chosen opposing', 'damage to chosen opposing', 'banish chosen']):
            roles.append('removal_recurring')

    if 'song' in ctype or 'action' in ctype:
        if any(kw in ab for kw in ['banish chosen', 'deal', 'damage to', 'return chosen character']):
            roles.append('removal_spell')

    if re.search(r'\brush\b', ab):
        roles.append('rush')
    if 'challenger' in ab:
        roles.append('challenger')

    if 'evasive' in ab:
        roles.append('evasive')
    if re.search(r'\bward\b', ab):
        roles.append('ward')
    if 'resist' in ab:
        roles.append('resist')
    if 'bodyguard' in ab:
        roles.append('bodyguard')
    if any(kw in ab for kw in ['draw a card', 'draw 2', 'draw cards']):
        roles.append('draw')
    if 'inkwell' in ab or 'additional ink' in ab:
        roles.append('ramp')

    lore = _safe_int(info.get('lore', 0))
    if lore >= 2:
        roles.append('lore_engine')

    return roles, downsides


ROLE_ORDER = [
    ('removal_etb', 'Removal ETB (on play)'),
    ('removal_spell', 'Removal Spell (action/song)'),
    ('removal_recurring', 'Removal Ricorrente'),
    ('rush', 'Rush'),
    ('challenger', 'Challenger'),
    ('ward', 'Ward'),
    ('resist', 'Resist'),
    ('evasive', 'Evasive'),
    ('bodyguard', 'Bodyguard'),
    ('draw', 'Draw'),
    ('ramp', 'Ramp'),
    ('lore_engine', 'Lore Engine (2+ lore)'),
]


def generate(our, opp, games, db, **ctx):
    our_pool = ctx.get('our_pool', {})
    ext_pool = ctx.get('ext_pool', {})

    L = [f"## 5. Toolkit Nostro ({our})\n"]
    L.append(f"_Carte disponibili organizzate per ruolo tattico. Ability dal DB._")
    L.append(f"_Usare per ragionare su risposte alle minacce del Playbook avversario._\n")

    if not our_pool:
        L.append(f"_Nessuna decklist trovata per {our}._\n")
        return '\n'.join(L) + '\n', {}

    # Build merged pool: torneo + off-meta
    merged = {}
    for name, info in our_pool.items():
        merged[name] = dict(info)
        merged[name]['source'] = 'torneo'
    for name, info in ext_pool.items():
        if name not in merged:
            merged[name] = dict(info)
            merged[name]['source'] = 'off-meta'

    # Classify all cards, primary role only (first match)
    role_buckets = {role: [] for role, _ in ROLE_ORDER}
    role_buckets['utility'] = []
    placed_cards = set()

    for name, info in sorted(merged.items(), key=lambda x: x[1]['cost']):
        roles, downsides = _classify_card_role(name, info)

        placed = False
        for role_key, _ in ROLE_ORDER:
            if role_key in roles and name not in placed_cards:
                role_buckets[role_key].append((name, info, downsides, roles))
                placed_cards.add(name)
                placed = True
                break

        if not placed and name not in placed_cards:
            role_buckets['utility'].append((name, info, downsides, roles))
            placed_cards.add(name)

    # Output each role section
    for role_key, role_label in ROLE_ORDER + [('utility', 'Utility / Quester')]:
        cards = role_buckets.get(role_key, [])
        if not cards:
            continue

        # Torneo first, then by cost
        cards.sort(key=lambda x: (0 if x[1].get('source') == 'torneo' else 1, x[1]['cost']))

        # Cap off-meta to 5 per role
        torneo = [c for c in cards if c[1].get('source') == 'torneo']
        offmeta = [c for c in cards if c[1].get('source') == 'off-meta'][:5]
        cards = torneo + offmeta

        if not cards:
            continue

        L.append(f"### {role_label}\n")
        L.append(f"| Carta | Cost | Body | Copie | Ability |")
        L.append(f"|-------|------|------|-------|---------|")

        for name, info, downsides, roles in cards:
            src = '' if info.get('source') == 'torneo' else ' off-meta'
            avg_q = info.get('avg_qty', 0)
            copies = f"{avg_q:.0f}x" if avg_q > 0 else '-'

            s = _safe_int(info.get('str', 0))
            w = _safe_int(info.get('will', 0))
            lore = _safe_int(info.get('lore', 0))
            body_parts = []
            if s > 0 or w > 0:
                body_parts.append(f"{s}/{w}")
            if lore > 0:
                body_parts.append(f"{lore}L")
            body = ' '.join(body_parts) if body_parts else '-'

            tactic = card_tactical_from_db(name, db)
            ds = f" **!{','.join(downsides)}**" if downsides else ''

            L.append(f"| {name}{src} | {info['cost']} | {body} | {copies} | {tactic}{ds} |")

        L.append(f"")

    return '\n'.join(L) + '\n', {}
