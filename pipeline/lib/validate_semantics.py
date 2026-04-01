"""
Validazione semantica: verifica che le claim LLM sulle carte corrispondano
alle ability reali nel DB.

Pipeline:
1. Estrae nomi carte da killer_curves JSON e/o report .md
2. Lookup ability: cards_db locale + duels.ink API (cross-check)
3. Genera report strutturato (JSON) con claim vs ability reali
4. L'LLM in IDE legge il report e valida/corregge

NON usa claude CLI. L'LLM e' l'IDE stesso.

Uso:
    python3 -m lib.validate_semantics output/killer_curves_AmAm_vs_ES.json
    python3 -m lib.validate_semantics reports/Amber-Amethyst/vs_Emerald-Sapphire.md

Output:
    output/semantic_check_<nome>.json  — report strutturato per l'LLM
"""

import json, sys, os, re, time, urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.cards_dict import build_cards_dict

# ── Constants ────────────────────────────────────────────────────

DUELS_INK_API = "https://duels.ink/api/cards"
DUELS_INK_CACHE = "/tmp/duels_ink_cards.json"
CACHE_MAX_AGE = 86400  # 24h in seconds

# Pattern per nomi carte Lorcana: "Nome - Sottotitolo"
_CARD_NAME_RE = re.compile(r'[A-Z][A-Za-z\'.!]+(?:\s+[A-Za-z\'.!]+)*\s+-\s+[A-Z][A-Za-z\'.!, ]+')


# ── 1. duels.ink fetch + cache ───────────────────────────────────

def fetch_duels_ink_cards():
    """Fetch cards da duels.ink API, con cache locale 24h.

    Returns:
        dict {card_name: {color, cost, inkwell, abilities: str}} oppure {}
    """
    if os.path.exists(DUELS_INK_CACHE):
        age = time.time() - os.path.getmtime(DUELS_INK_CACHE)
        if age < CACHE_MAX_AGE:
            try:
                with open(DUELS_INK_CACHE) as f:
                    raw = json.load(f)
                return _parse_duels_ink_raw(raw)
            except (json.JSONDecodeError, KeyError):
                pass

    try:
        all_cards = _fetch_all_pages(DUELS_INK_API)
        with open(DUELS_INK_CACHE, 'w') as f:
            json.dump(all_cards, f)
        return _parse_duels_ink_raw(all_cards)
    except Exception as e:
        print(f"  [WARN] duels.ink API non raggiungibile: {e}")
        return {}


def _fetch_all_pages(base_url, limit=500):
    """Fetch tutte le pagine dall'API duels.ink (paginata)."""
    all_cards = []
    offset = 0
    while True:
        url = f"{base_url}?offset={offset}&limit={limit}"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'LorcanaAnalyzer/1.0',
            'Accept': 'application/json',
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        cards = data.get('cards', []) if isinstance(data, dict) else data
        all_cards.extend(cards)
        meta = data.get('meta', {}) if isinstance(data, dict) else {}
        if not meta.get('hasMore', False) or not cards:
            break
        offset += len(cards)
    return all_cards


def _parse_duels_ink_raw(raw):
    """Parsa il JSON grezzo di duels.ink in un dizionario lookup."""
    result = {}
    cards_list = raw if isinstance(raw, list) else raw.get('cards', raw.get('data', raw))
    for card in cards_list:
        name = card.get('name') or card.get('fullName', '')
        if not name:
            continue
        abilities_parts = []
        for sa in card.get('specialAbilities', []):
            ab_name = sa.get('name', '')
            ab_effect = sa.get('effect', '')
            if ab_name and ab_effect:
                abilities_parts.append(f"{ab_name}: {ab_effect}")
            elif ab_effect:
                abilities_parts.append(ab_effect)
            elif ab_name:
                abilities_parts.append(ab_name)
        body = card.get('bodyText', '')
        if body and not abilities_parts:
            abilities_parts.append(body)

        result[name] = {
            'color': card.get('color', ''),
            'cost': card.get('cost', 0),
            'inkwell': card.get('inkwell', False),
            'abilities': ' | '.join(abilities_parts) if abilities_parts else '',
        }
    return result


# ── 2. Card extraction ───────────────────────────────────────────

def extract_cards_from_curves(curves_path):
    """Estrae carte e contesto da un killer_curves JSON.

    Returns:
        list of {card, context, source}
    """
    with open(curves_path) as f:
        data = json.load(f)

    results = []
    seen = set()

    for curve in data.get('curves', []):
        curve_id = curve.get('id', '?')
        curve_name = curve.get('name', '?')

        # Sequence cards (opponent plays)
        sequence = curve.get('sequence', {})
        for turn_key, turn_data in sequence.items():
            plays = turn_data.get('plays', [])
            if 'card' in turn_data and 'plays' not in turn_data:
                plays = [turn_data]
            for play in plays:
                card_name = play.get('card', '')
                role = play.get('role', '')
                if card_name and card_name not in seen:
                    seen.add(card_name)
                    results.append({
                        'card': card_name,
                        'context': f"curve '{curve_name}' {turn_key}: role={role}",
                        'source': 'sequence',
                    })

        # Response cards (our cards)
        response = curve.get('response', {})
        for resp_card in response.get('cards', []):
            if resp_card and resp_card not in seen:
                seen.add(resp_card)
                results.append({
                    'card': resp_card,
                    'context': f"curve '{curve_name}' response",
                    'source': 'response',
                })

        # Response strategy text — extract card names mentioned
        strategy = response.get('strategy', '')
        if strategy:
            for match in _CARD_NAME_RE.finditer(strategy):
                card_name = match.group(0).strip()
                if card_name not in seen:
                    seen.add(card_name)
                    results.append({
                        'card': card_name,
                        'context': f"curve '{curve_name}' strategy text",
                        'source': 'strategy_text',
                    })

    return results


def extract_cards_from_report(report_path):
    """Estrae carte menzionate in un report .md.

    Returns:
        list of {card, context, source}
    """
    with open(report_path, encoding='utf-8') as f:
        text = f.read()

    results = []
    seen = set()

    for i, line in enumerate(text.split('\n'), 1):
        for match in _CARD_NAME_RE.finditer(line):
            card_name = match.group(0).strip()
            if card_name not in seen:
                seen.add(card_name)
                ctx = line.strip()[:120]
                results.append({
                    'card': card_name,
                    'context': f"L{i}: {ctx}",
                    'source': 'report',
                })

    return results


# ── 3. Card lookup ───────────────────────────────────────────────

def lookup_card_abilities(card_name, local_db, duels_db):
    """Cerca le ability reali di una carta nei due DB.

    Returns:
        dict con found=True/False e ability details
    """
    local_entry = local_db.get(card_name)
    duels_entry = duels_db.get(card_name)

    if local_entry or duels_entry:
        result = {
            'name': card_name,
            'found': True,
            'color': '',
            'cost': 0,
            'abilities_local': '',
            'abilities_duels': '',
        }
        if local_entry:
            result['color'] = local_entry.get('ink', '')
            result['cost'] = local_entry.get('cost', 0)
            result['abilities_local'] = local_entry.get('ability', '')
        if duels_entry:
            if not result['color']:
                result['color'] = duels_entry.get('color', '')
            if not result['cost']:
                result['cost'] = duels_entry.get('cost', 0)
            result['abilities_duels'] = duels_entry.get('abilities', '')
        return result

    # Fuzzy
    suggestions = []
    name_lower = card_name.lower()
    for db_name in local_db:
        if name_lower in db_name.lower() or db_name.lower() in name_lower:
            suggestions.append(db_name)
    if not suggestions:
        for db_name in duels_db:
            if name_lower in db_name.lower() or db_name.lower() in name_lower:
                suggestions.append(db_name)

    return {
        'name': card_name,
        'found': False,
        'suggestions': suggestions[:5],
    }


# ── 4. Build semantic check report ─────────────────────────────

def build_semantic_report(cards_with_claims, source_path):
    """Costruisce il report strutturato per l'LLM in IDE.

    Returns:
        dict con tutte le info per la validazione
    """
    items = []
    for item in cards_with_claims:
        card = item['card']
        lookup = item.get('lookup', {})
        entry = {
            'card': card,
            'context': item['context'],
            'source': item['source'],
        }
        if lookup.get('found'):
            entry['color'] = lookup.get('color', '')
            entry['cost'] = lookup.get('cost', 0)
            entry['abilities_local'] = lookup.get('abilities_local', '')
            entry['abilities_duels'] = lookup.get('abilities_duels', '')
        else:
            entry['not_found'] = True
            entry['suggestions'] = lookup.get('suggestions', [])
        items.append(entry)

    return {
        'source_file': os.path.basename(source_path),
        'total_cards': len(items),
        'cards': items,
    }


# ── 5. Main entry point ────────────────────────────────────────

def validate_semantics(path):
    """Genera report di validazione semantica per un file killer_curves o report.

    NON chiama LLM. Produce un JSON strutturato che l'LLM in IDE legge.

    Args:
        path: path al file (.json killer_curves o .md report)

    Returns:
        dict report oppure None se errore
    """
    if not os.path.exists(path):
        print(f"File non trovato: {path}")
        return None

    is_curves = path.endswith('.json')
    is_report = path.endswith('.md')

    if not is_curves and not is_report:
        print(f"Formato non supportato: {path} (serve .json o .md)")
        return None

    print(f"Validazione semantica: {os.path.basename(path)}")

    # Step 1: Estrai carte
    if is_curves:
        cards_found = extract_cards_from_curves(path)
    else:
        cards_found = extract_cards_from_report(path)

    if not cards_found:
        print("  Nessuna carta trovata nel file.")
        return {'source_file': os.path.basename(path), 'total_cards': 0, 'cards': []}

    print(f"  Carte estratte: {len(cards_found)}")

    # Step 2: Lookup ability dai DB
    print("  Caricamento cards_db locale...")
    local_db = build_cards_dict()
    print(f"  cards_db: {len(local_db)} carte")

    print("  Fetch duels.ink API...")
    duels_db = fetch_duels_ink_cards()
    print(f"  duels.ink: {len(duels_db)} carte")

    # Arricchisci con lookup
    cards_with_claims = []
    not_found = []
    for item in cards_found:
        lookup = lookup_card_abilities(item['card'], local_db, duels_db)
        item['lookup'] = lookup
        if lookup.get('found'):
            cards_with_claims.append(item)
        else:
            not_found.append(item)

    if not_found:
        print(f"  [WARN] {len(not_found)} carte non trovate:")
        for nf in not_found:
            suggestions = nf['lookup'].get('suggestions', [])
            hint = f" (forse: {suggestions[0]})" if suggestions else ""
            print(f"    - {nf['card']}{hint}")

    # Step 3: Genera report
    all_cards = cards_with_claims + not_found
    report = build_semantic_report(all_cards, path)

    # Salva report
    basename = os.path.splitext(os.path.basename(path))[0]
    output_path = os.path.join(os.path.dirname(path) or '.', f"semantic_check_{basename}.json")
    # Per i report .md, salva in output/
    if is_report:
        output_path = os.path.join('output', f"semantic_check_{basename}.json")

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"  Report salvato: {output_path}")
    print(f"  {len(cards_with_claims)} carte con ability, {len(not_found)} non trovate")
    print(f"  → L'LLM puo' ora leggere il report e validare le claim")

    return report


# ── 6. CLI ────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Genera report di validazione semantica (claim vs ability reali)',
    )
    parser.add_argument('path', help='Path a killer_curves .json o report .md')
    args = parser.parse_args()

    result = validate_semantics(args.path)

    if result is None:
        sys.exit(1)

    # Summary
    found = [c for c in result['cards'] if not c.get('not_found')]
    not_found = [c for c in result['cards'] if c.get('not_found')]
    print()
    print(f"  Trovate: {len(found)}  |  Non trovate: {len(not_found)}  |  Totale: {result['total_cards']}")


if __name__ == '__main__':
    main()
