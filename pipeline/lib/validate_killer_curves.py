"""
Validatore per killer curves scritte dall'LLM.

Prende un JSON con le curve proposte e verifica:
- Ink fattibile turno per turno
- Shift: base con stesso nome in board
- Song: singer con cost >= song cost, ready
- Carte esistono nel cards_db e nei colori avversario
- Max 4 copie per carta

Supporta il formato multi-carta per turno:
  "T2": {
    "plays": [
      {"card": "...", "ink_cost": 2, "role": "..."},
      {"card": "...", "ink_cost": 0, "role": "...", "is_shift": true}
    ],
    "total_ink": 2, "lore_this_turn": 1
  }

Backward-compatible con il vecchio formato single-card:
  "T2": {"card": "...", "ink_cost": 2, "role": "..."}

Uso:
    python3 -m lib.validate_killer_curves output/killer_curves_AmAm_vs_ES.json

Oppure da codice:
    from lib.validate_killer_curves import validate_curves
    warnings = validate_curves(curves_json_path)
"""

import json, sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.loader import load_cards_db, DECK_COLORS
from lib.cards_dict import build_cards_dict


def _normalize_turn(turn_data):
    """Convert old single-card format to new multi-card format.

    Old: {"card": "X", "ink_cost": 2, "role": "...", "is_shift": true}
    New: {"plays": [{"card": "X", "ink_cost": 2, "role": "...", "is_shift": true}], "total_ink": 2}
    """
    if 'plays' in turn_data:
        return turn_data
    # Old format: single card
    card = turn_data.get('card', '')
    if not card:
        return {'plays': [], 'total_ink': 0}
    play = {
        'card': card,
        'ink_cost': turn_data.get('ink_cost', 0),
        'role': turn_data.get('role', ''),
    }
    if turn_data.get('is_shift'):
        play['is_shift'] = True
    if turn_data.get('is_sung'):
        play['is_sung'] = True
    if turn_data.get('note'):
        play['note'] = turn_data['note']
    return {
        'plays': [play],
        'total_ink': turn_data.get('ink_cost', 0),
        'lore_this_turn': turn_data.get('lore_this_turn', 0),
    }


def validate_curves(curves_path, cards=None):
    """Valida le killer curves da un JSON.

    Args:
        curves_path: path al JSON delle curves
        cards: dizionario carte (opzionale, lo carica se None)

    Returns:
        list of {curve_id, check, status, message}
    """
    with open(curves_path) as f:
        data = json.load(f)

    if cards is None:
        cards = build_cards_dict()

    opp_deck = data.get('metadata', {}).get('opp_deck', '')
    opp_colors = DECK_COLORS.get(opp_deck, ())
    our_deck = data.get('metadata', {}).get('our_deck', '')
    our_colors = DECK_COLORS.get(our_deck, ())

    results = []

    for curve in data.get('curves', []):
        curve_id = curve.get('id', '?')
        curve_name = curve.get('name', '?')
        sequence = curve.get('sequence', {})

        # ── Validate turno per turno ──
        inkwell = 0
        board = {}  # name → count
        singers_used = set()
        all_plays = []  # collect all plays for global checks

        for turn_key in sorted(sequence.keys(), key=lambda x: int(x.replace('T', ''))):
            turn_num = int(turn_key.replace('T', ''))
            turn_data = _normalize_turn(sequence[turn_key])
            plays = turn_data.get('plays', [])

            # Inkwell: +1 per turno (base)
            inkwell = turn_num

            turn_ink_spent = 0

            for play in plays:
                card_name = play.get('card', '')
                ink_cost = play.get('ink_cost', 0)
                is_shift = play.get('is_shift', False)
                is_sung = play.get('is_sung', False)

                if not card_name:
                    continue

                all_plays.append(play)

                # Check 1: carta esiste
                card_entry = cards.get(card_name)
                if not card_entry:
                    matches = [cn for cn in cards if card_name.lower() in cn.lower()]
                    if matches:
                        results.append({
                            'curve_id': curve_id, 'check': 'card_exists',
                            'status': 'WARNING',
                            'message': f"T{turn_num}: '{card_name}' non trovata esatta. Intendevi: {matches[0]}?"
                        })
                        card_entry = cards.get(matches[0])
                    else:
                        results.append({
                            'curve_id': curve_id, 'check': 'card_exists',
                            'status': 'FAIL',
                            'message': f"T{turn_num}: '{card_name}' non esiste nel cards_db"
                        })
                        continue

                # Check 2: colori avversario
                if opp_colors:
                    card_ink = card_entry.get('ink', '').lower()
                    if card_ink not in opp_colors and card_ink != 'dual ink':
                        results.append({
                            'curve_id': curve_id, 'check': 'card_color',
                            'status': 'FAIL',
                            'message': f"T{turn_num}: '{card_name}' e' {card_ink}, avversario e' {opp_colors}"
                        })

                # Check 3: shift prerequisiti
                if is_shift:
                    base_name = card_entry.get('base_name', '')
                    has_base = False
                    for k, cnt in board.items():
                        if cnt > 0:
                            base_entry = cards.get(k)
                            if base_entry and base_entry.get('base_name') == base_name and k != card_name:
                                has_base = True
                                board[k] -= 1
                                break
                    if not has_base:
                        results.append({
                            'curve_id': curve_id, 'check': 'shift_base',
                            'status': 'FAIL',
                            'message': f"T{turn_num}: shift '{card_name}' ma nessuna base '{base_name}' in board"
                        })

                    real_shift = card_entry.get('shift_cost')
                    if real_shift and ink_cost != real_shift:
                        results.append({
                            'curve_id': curve_id, 'check': 'shift_cost',
                            'status': 'WARNING',
                            'message': f"T{turn_num}: shift cost dichiarato {ink_cost} ma cards_db dice {real_shift}"
                        })

                # Check 4: song prerequisiti
                if is_sung:
                    song_cost = card_entry.get('cost', 0)
                    has_singer = False
                    for k, cnt in board.items():
                        if cnt <= 0 or k in singers_used:
                            continue
                        singer_entry = cards.get(k)
                        if not singer_entry or not singer_entry.get('is_character'):
                            continue
                        singer_cost = singer_entry.get('singer_cost') or singer_entry.get('cost', 0)
                        if singer_cost >= song_cost:
                            has_singer = True
                            singers_used.add(k)
                            break
                    if not has_singer:
                        results.append({
                            'curve_id': curve_id, 'check': 'song_singer',
                            'status': 'FAIL',
                            'message': f"T{turn_num}: song '{card_name}' (cost {song_cost}) ma nessun singer ready con cost >= {song_cost}"
                        })

                turn_ink_spent += ink_cost

                # Aggiungi al board
                board[card_name] = board.get(card_name, 0) + 1

            # Check 5: ink fattibile per il turno intero
            total_ink = turn_data.get('total_ink')
            if total_ink is not None and total_ink > inkwell:
                results.append({
                    'curve_id': curve_id, 'check': 'ink_feasible',
                    'status': 'WARNING',
                    'message': f"T{turn_num}: total_ink={total_ink} ma ink base = {inkwell} (serve ramp)"
                })
            elif total_ink is None and turn_ink_spent > inkwell:
                results.append({
                    'curve_id': curve_id, 'check': 'ink_feasible',
                    'status': 'WARNING',
                    'message': f"T{turn_num}: ink speso ~{turn_ink_spent} ma ink base = {inkwell} (serve ramp)"
                })

        # ── Check globali sulla curva ──

        # Check 6: max 4 copie
        card_counts = {}
        for play in all_plays:
            cn = play.get('card', '')
            if cn:
                card_counts[cn] = card_counts.get(cn, 0) + 1
        for cn, count in card_counts.items():
            if count > 4:
                results.append({
                    'curve_id': curve_id, 'check': 'max_copies',
                    'status': 'FAIL',
                    'message': f"'{cn}' appare {count} volte nella curva (max 4 nel deck)"
                })

        # Check 7: worst_case_validated flag
        if not curve.get('worst_case_validated'):
            results.append({
                'curve_id': curve_id, 'check': 'validated_flag',
                'status': 'WARNING',
                'message': 'worst_case_validated non impostato a true'
            })

        # Check 8: response presente
        response = curve.get('response', {})
        if not response or not response.get('cards'):
            results.append({
                'curve_id': curve_id, 'check': 'response',
                'status': 'WARNING',
                'message': 'Nessuna risposta proposta per questa curva'
            })

        # Check 9: response cards devono appartenere ai colori del NOSTRO deck
        if our_colors and response.get('cards'):
            for resp_card in response['cards']:
                resp_entry = cards.get(resp_card)
                if not resp_entry:
                    # Fuzzy match
                    matches = [cn for cn in cards if resp_card.lower() in cn.lower()]
                    if matches:
                        resp_entry = cards.get(matches[0])
                if resp_entry:
                    resp_ink = resp_entry.get('ink', '').lower()
                    if resp_ink and resp_ink not in our_colors and resp_ink != 'dual ink':
                        results.append({
                            'curve_id': curve_id, 'check': 'response_color',
                            'status': 'FAIL',
                            'message': f"Response card '{resp_card}' e' {resp_ink}, ma il nostro deck {our_deck} e' {our_colors}"
                        })

        # Se nessun errore, segnala OK
        curve_results = [r for r in results if r['curve_id'] == curve_id]
        if not curve_results:
            results.append({
                'curve_id': curve_id, 'check': 'all',
                'status': 'OK',
                'message': f'Curva "{curve_name}" validata con successo'
            })

    return results


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 -m lib.validate_killer_curves <path_killer_curves.json>")
        sys.exit(1)

    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"File non trovato: {path}")
        sys.exit(1)

    results = validate_curves(path)

    fails = [r for r in results if r['status'] == 'FAIL']
    warnings = [r for r in results if r['status'] == 'WARNING']
    oks = [r for r in results if r['status'] == 'OK']

    print(f"Validazione killer curves: {path}")
    print(f"  {len(oks)} OK, {len(warnings)} WARNING, {len(fails)} FAIL")
    print()

    for r in fails:
        print(f"  FAIL    curve #{r['curve_id']}: [{r['check']}] {r['message']}")
    for r in warnings:
        print(f"  WARNING curve #{r['curve_id']}: [{r['check']}] {r['message']}")
    for r in oks:
        print(f"  OK      curve #{r['curve_id']}: {r['message']}")

    if fails:
        sys.exit(1)


if __name__ == '__main__':
    main()
