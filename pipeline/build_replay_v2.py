#!/usr/bin/env python3
"""
build_replay_v2.py — Genera replay HTML con step[] pre-calcolati.

Il JS nel template legge e anima, zero logica di gioco.

Uso:
    python3 build_replay_v2.py AbSt AmAm
    python3 build_replay_v2.py AmAm ES
"""

import json
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

OUTPUT_DIR = os.path.join(SCRIPT_DIR, 'Html_viewer')
CARDS_DB_PATH = '/mnt/HC_Volume_104764377/finanza/Lor/cards_db.json'

from lib.loader import load_matches, load_cards_db, resolve_deck, deck_long
from lib.investigate import enrich_games
from lib.build_replay_steps import build_game_steps, validate_steps


def build_slim_cards_db(games, full_db):
    """Estrae solo le carte che appaiono nelle partite, con campi essenziali."""
    names = set()
    for g in games:
        for td in g.get('turns', {}).values():
            for side in ('our', 'opp'):
                for p in td.get(f'{side}_play_detail', []):
                    names.add(p.get('name', ''))
                names.update(td.get('board_state', {}).get(side, []) if 'board_state' in td else [])
                names.update(td.get(f'{side}_dead', []))
                names.update(td.get(f'{side}_bounced', []))
                for q in td.get(f'{side}_quests', []):
                    names.add(q[0] if isinstance(q, (list, tuple)) else q.get('name', ''))
                for c in td.get(f'{side}_challenges', []):
                    names.add(c.get('attacker', ''))
                    names.add(c.get('defender', ''))
                for a in td.get(f'{side}_abilities', []):
                    names.add(a.get('card', ''))
                for d in td.get(f'{side}_drawn', []):
                    names.add(d[0] if isinstance(d, (list, tuple)) else d.get('name', ''))
            bs = g.get('board_state', {}).get(td.get('t', 0), {})
            names.update(bs.get('our', []))
            names.update(bs.get('opp', []))
    names.discard('')

    slim = {}
    for name in names:
        card = full_db.get(name)
        if card:
            slim[name] = {
                'cost': card.get('cost', ''),
                'type': card.get('type', ''),
                'ink': card.get('ink', ''),
                'str': card.get('str', ''),
                'will': card.get('will', ''),
                'lore': card.get('lore', ''),
                'ability': card.get('ability', ''),
                'classifications': card.get('classifications', ''),
                'set': card.get('set', ''),
                'number': card.get('number', ''),
            }
    return slim


def build_replay_v2(our, opp):
    our_long = deck_long(resolve_deck(our))
    opp_long = deck_long(resolve_deck(opp))
    print(f"Loading matches: {our} vs {opp}")

    full_db = load_cards_db()
    games = load_matches(our, opp)
    if not games:
        print(f"Nessuna partita trovata per {our} vs {opp}")
        return

    print(f"Partite: {len(games)}")
    enrich_games(games, full_db, {})

    # Build slim cards DB
    slim_db = build_slim_cards_db(games, full_db)
    print(f"Carte nel matchup: {len(slim_db)}")

    # Build steps for each game
    all_game_data = []
    total_warnings = 0
    for i, g in enumerate(games):
        steps = build_game_steps(g, full_db)
        warnings = validate_steps(steps, g, full_db)
        total_warnings += len(warnings)

        # Game metadata
        game_meta = {
            'id': i + 1,
            'result': 'W' if g.get('we_won') else 'L',
            'we_otp': g.get('we_otp', False),
            'our_name': g.get('our_name', 'Noi'),
            'opp_name': g.get('opp_name', 'Opp'),
            'our_mmr': g.get('our_mmr', 0),
            'opp_mmr': g.get('opp_mmr', 0),
            'length': g.get('length', 0),
            'steps': steps,
        }
        all_game_data.append(game_meta)

    print(f"Validazione: {total_warnings} warnings su {len(games)} partite")

    # Build the data payload
    payload = {
        'metadata': {
            'our_deck': our,
            'opp_deck': opp,
            'our_long': our_long,
            'opp_long': opp_long,
            'total_games': len(games),
        },
        'games': all_game_data,
    }

    # Serialize
    payload_json = json.dumps(payload, ensure_ascii=True, separators=(',', ':')).replace('</script>', '<\\/script>')
    db_json = json.dumps(slim_db, ensure_ascii=True, separators=(',', ':')).replace('</script>', '<\\/script>')

    print(f"Payload JSON: {len(payload_json) // 1024} KB")
    print(f"Cards DB JSON: {len(db_json) // 1024} KB")

    # Load template
    template_path = os.path.join(SCRIPT_DIR, 'replay_template_v2.html')
    with open(template_path) as f:
        html = f.read()

    html = html.replace('/*__REPLAY_DATA__*/null', payload_json)
    html = html.replace('/*__CARDS_DB__*/null', db_json)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f'replay_{our}_vs_{opp}.html')
    with open(out_path, 'w') as f:
        f.write(html)

    print(f"Scritto: {out_path} ({os.path.getsize(out_path) // 1024} KB)")
    return out_path


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Uso: python3 build_replay_v2.py <our_deck> <opp_deck>")
        sys.exit(1)
    build_replay_v2(sys.argv[1], sys.argv[2])
