"""
Internationalization module for the Lorcana matchup analyzer.

Translates killer curves and dashboard text. Card names from duels.ink API;
tactical prose prepared as structured JSON for the LLM in IDE to translate.

NON usa claude CLI. L'LLM e' l'IDE stesso.

Supported languages:
    en  English (default, no translation needed)
    it  Italiano
    de  Deutsch
    zh  中文
    ja  日本語

Usage:
    # Sostituisci solo nomi carte (da duels.ink, no LLM)
    python3 -m lib.i18n output/killer_curves_AmAm_vs_ES.json --lang it

    # Genera file di testi da tradurre per l'LLM
    python3 -m lib.i18n output/killer_curves_AmAm_vs_ES.json --lang it --extract
"""

import json
import os
import sys
import time
import argparse
import copy
from urllib.request import urlopen, Request
from urllib.error import URLError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_LANGS = {
    'en': 'English',
    'it': 'Italiano',
    'de': 'Deutsch',
    'zh': '中文',
    'ja': '日本語',
}

DUELS_INK_CARDS_URL = 'https://duels.ink/api/cards'
DUELS_INK_CACHE_PATH = '/tmp/duels_ink_cards.json'
DUELS_INK_CACHE_TTL = 24 * 3600  # 24 hours

# Technical terms that should NOT be translated
KEEP_TERMS = [
    'OTP', 'OTD', 'lore', 'ink', 'quest', 'challenge',
    'exert', 'shift', 'ward', 'evasive', 'rush', 'Support',
    'Challenger', 'Floodborn', 'Dreamborn', 'Storyborn',
]

# duels.ink usa 'ja_en' e 'zh_en' (non 'ja'/'zh')
_LANG_FIELD_MAP = {
    'de': 'de',
    'it': 'it',
    'ja': 'ja_en',
    'zh': 'zh_en',
    'fr': 'fr',
}


# ---------------------------------------------------------------------------
# duels.ink card cache
# ---------------------------------------------------------------------------

def _fetch_duels_ink_cached():
    """Fetch cards from duels.ink API with 24h file cache."""
    if os.path.exists(DUELS_INK_CACHE_PATH):
        age = time.time() - os.path.getmtime(DUELS_INK_CACHE_PATH)
        if age < DUELS_INK_CACHE_TTL:
            try:
                with open(DUELS_INK_CACHE_PATH, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

    try:
        all_cards = _fetch_all_pages(DUELS_INK_CARDS_URL)
        with open(DUELS_INK_CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump(all_cards, f, ensure_ascii=False)
        return all_cards
    except (URLError, OSError, json.JSONDecodeError) as e:
        print(f"[i18n] WARNING: failed to fetch duels.ink cards: {e}")
        if os.path.exists(DUELS_INK_CACHE_PATH):
            try:
                with open(DUELS_INK_CACHE_PATH, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return []


def _fetch_all_pages(base_url, limit=500):
    """Fetch tutte le pagine dall'API duels.ink (paginata)."""
    all_cards = []
    offset = 0
    while True:
        url = f"{base_url}?offset={offset}&limit={limit}"
        req = Request(url, headers={'User-Agent': 'LorcanaAnalyzer/1.0'})
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        cards = data.get('cards', []) if isinstance(data, dict) else data
        all_cards.extend(cards)
        meta = data.get('meta', {}) if isinstance(data, dict) else {}
        if not meta.get('hasMore', False) or not cards:
            break
        offset += len(cards)
    return all_cards


# ---------------------------------------------------------------------------
# 1. fetch_card_translations
# ---------------------------------------------------------------------------

def fetch_card_translations(lang):
    """Build mapping {english_name: translated_name} for the given language."""
    if lang == 'en' or lang not in _LANG_FIELD_MAP:
        return {}

    cards = _fetch_duels_ink_cached()
    if not cards:
        return {}

    field = _LANG_FIELD_MAP[lang]
    card_map = {}

    for card in cards:
        if not isinstance(card, dict):
            continue
        # Full name = "Name - Title", fallback to name
        en_full = card.get('fullName') or card.get('name', '')
        if not en_full:
            continue

        # Translations nested under 'translations' key
        translations = card.get('translations', {})
        trans_block = translations.get(field, {})
        if isinstance(trans_block, dict):
            trans_full = trans_block.get('fullName') or trans_block.get('name')
        else:
            trans_full = None

        if trans_full and trans_full != en_full:
            card_map[en_full] = trans_full

    return card_map


# ---------------------------------------------------------------------------
# 2. translate_card_name
# ---------------------------------------------------------------------------

def translate_card_name(en_name, card_map):
    """Look up a card's translated name. Fallback to English."""
    if not card_map:
        return en_name
    return card_map.get(en_name, en_name)


# ---------------------------------------------------------------------------
# 3. extract_texts_for_translation
# ---------------------------------------------------------------------------

def extract_texts_for_translation(curves_path):
    """Estrae tutti i testi traducibili da un killer_curves JSON.

    Returns:
        list of {key, text} — da dare all'LLM per la traduzione
    """
    with open(curves_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    texts = []
    for i, curve in enumerate(data.get('curves', [])):
        if curve.get('name'):
            texts.append({'key': f'curve_{i}_name', 'text': curve['name']})

        resp = curve.get('response', {})
        if resp.get('strategy'):
            texts.append({'key': f'curve_{i}_strategy', 'text': resp['strategy']})

        for j, combo_text in enumerate(curve.get('combo', [])):
            if combo_text:
                texts.append({'key': f'curve_{i}_combo_{j}', 'text': combo_text})

        seq = curve.get('sequence', {})
        for turn_key, turn_data in seq.items():
            if not isinstance(turn_data, dict):
                continue
            note = turn_data.get('note')
            if note:
                texts.append({'key': f'curve_{i}_{turn_key}_note', 'text': note})
            for k, play in enumerate(turn_data.get('plays', [])):
                if play.get('role'):
                    texts.append({'key': f'curve_{i}_{turn_key}_play_{k}_role', 'text': play['role']})

        val = curve.get('validation', {})
        for vkey in ('ink', 'shift', 'song', 'frequency'):
            if val.get(vkey):
                texts.append({'key': f'curve_{i}_val_{vkey}', 'text': val[vkey]})

    return texts


# ---------------------------------------------------------------------------
# 4. apply_translations
# ---------------------------------------------------------------------------

def apply_translations(curves_path, target_lang, translations, output_path=None):
    """Applica traduzioni a un killer_curves JSON.

    Args:
        curves_path: path al JSON sorgente
        target_lang: codice lingua
        translations: dict {key: translated_text} — dall'LLM
        output_path: path output (default: auto con suffisso _<lang>)

    Returns:
        path del file scritto
    """
    with open(curves_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    card_map = fetch_card_translations(target_lang)

    out_data = copy.deepcopy(data)
    out_data['metadata']['lang'] = target_lang

    for i, curve in enumerate(out_data['curves']):
        # Name
        name_key = f'curve_{i}_name'
        if name_key in translations:
            curve['name'] = translations[name_key]

        # Response strategy
        resp = curve.get('response', {})
        strat_key = f'curve_{i}_strategy'
        if strat_key in translations:
            resp['strategy'] = translations[strat_key]

        # Response cards — translate card names
        if resp.get('cards'):
            resp['cards'] = [translate_card_name(c, card_map) for c in resp['cards']]

        # Combo
        for j in range(len(curve.get('combo', []))):
            combo_key = f'curve_{i}_combo_{j}'
            if combo_key in translations:
                curve['combo'][j] = translations[combo_key]

        # Key cards
        if curve.get('key_cards'):
            curve['key_cards'] = [translate_card_name(c, card_map) for c in curve['key_cards']]

        # Sequence
        seq = curve.get('sequence', {})
        for turn_key, turn_data in seq.items():
            if not isinstance(turn_data, dict):
                continue
            note_key = f'curve_{i}_{turn_key}_note'
            if note_key in translations:
                turn_data['note'] = translations[note_key]
            for k, play in enumerate(turn_data.get('plays', [])):
                if play.get('card'):
                    play['card'] = translate_card_name(play['card'], card_map)
                role_key = f'curve_{i}_{turn_key}_play_{k}_role'
                if role_key in translations:
                    play['role'] = translations[role_key]

        # Validation text
        val = curve.get('validation', {})
        for vkey in ('ink', 'shift', 'song', 'frequency'):
            val_key = f'curve_{i}_val_{vkey}'
            if val_key in translations:
                val[vkey] = translations[val_key]

    # Output path
    if output_path is None:
        base, ext = os.path.splitext(curves_path)
        for lang_code in SUPPORTED_LANGS:
            if base.endswith(f'_{lang_code}'):
                base = base[:-len(f'_{lang_code}')]
                break
        output_path = f'{base}_{target_lang}{ext}'

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(out_data, f, indent=2, ensure_ascii=False)

    print(f"[i18n] Written: {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# 5. translate_card_names_only (no LLM needed)
# ---------------------------------------------------------------------------

def translate_card_names_only(curves_path, target_lang, output_path=None):
    """Traduce solo i nomi carte (da duels.ink), senza tradurre il testo tattico.

    Utile come step veloce: nomi carte tradotti, testo in inglese.
    """
    card_map = fetch_card_translations(target_lang)
    if not card_map:
        print(f"[i18n] Nessuna traduzione nomi carte per '{target_lang}'")
        return curves_path

    with open(curves_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    out_data = copy.deepcopy(data)
    out_data['metadata']['lang'] = target_lang
    replaced = 0

    for curve in out_data['curves']:
        # Response cards
        resp = curve.get('response', {})
        if resp.get('cards'):
            for j, c in enumerate(resp['cards']):
                new = translate_card_name(c, card_map)
                if new != c:
                    resp['cards'][j] = new
                    replaced += 1

        # Sequence plays
        seq = curve.get('sequence', {})
        for turn_data in seq.values():
            if not isinstance(turn_data, dict):
                continue
            for play in turn_data.get('plays', []):
                if play.get('card'):
                    new = translate_card_name(play['card'], card_map)
                    if new != play['card']:
                        play['card'] = new
                        replaced += 1

        # Key cards
        if curve.get('key_cards'):
            for j, c in enumerate(curve['key_cards']):
                new = translate_card_name(c, card_map)
                if new != c:
                    curve['key_cards'][j] = new
                    replaced += 1

    if output_path is None:
        base, ext = os.path.splitext(curves_path)
        for lang_code in SUPPORTED_LANGS:
            if base.endswith(f'_{lang_code}'):
                base = base[:-len(f'_{lang_code}')]
                break
        output_path = f'{base}_{target_lang}{ext}'

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(out_data, f, indent=2, ensure_ascii=False)

    print(f"[i18n] Nomi carte tradotti: {replaced} sostituzioni → {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# 6. translate_dashboard_text (card names only, no LLM)
# ---------------------------------------------------------------------------

def translate_dashboard_card_names(dashboard_data, target_lang):
    """Traduce nomi carte nel dashboard_data (solo card names, no testo tattico).

    Per tradurre il testo tattico, l'LLM in IDE legge i segmenti e li traduce.
    """
    if target_lang == 'en':
        return dashboard_data

    out = copy.deepcopy(dashboard_data)
    card_map = fetch_card_translations(target_lang)
    if not card_map:
        return out

    matchups = out.get('matchups', {})
    for mu_data in matchups.values():
        for kc in mu_data.get('killer_curves', []):
            resp = kc.get('response', {})
            if resp.get('cards'):
                resp['cards'] = [translate_card_name(c, card_map) for c in resp['cards']]
            seq = kc.get('sequence', {})
            for turn_data in seq.values():
                if not isinstance(turn_data, dict):
                    continue
                for play in turn_data.get('plays', []):
                    if play.get('card'):
                        play['card'] = translate_card_name(play['card'], card_map)

    return out


# ---------------------------------------------------------------------------
# 7. CLI main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='i18n per killer curves Lorcana.',
        usage='python3 -m lib.i18n <curves_json> --lang <code|all> [--extract]',
    )
    parser.add_argument('curves_path', help='Path to killer_curves JSON file')
    parser.add_argument('--lang', required=True,
                        help='Target language (it/de/zh/ja) or "all"')
    parser.add_argument('--extract', action='store_true',
                        help='Estrai testi da tradurre (JSON per LLM IDE)')
    parser.add_argument('--output', '-o', default=None, help='Output path')

    args = parser.parse_args()

    if not os.path.isfile(args.curves_path):
        print(f"ERROR: file not found: {args.curves_path}")
        sys.exit(1)

    if args.lang == 'all':
        langs = [l for l in SUPPORTED_LANGS if l != 'en']
    elif args.lang in SUPPORTED_LANGS:
        if args.lang == 'en':
            print("Target language is English, nothing to do.")
            sys.exit(0)
        langs = [args.lang]
    else:
        print(f"ERROR: unsupported language '{args.lang}'. "
              f"Supported: {', '.join(SUPPORTED_LANGS.keys())}")
        sys.exit(1)

    if args.extract:
        # Estrai testi da tradurre → JSON per l'LLM
        texts = extract_texts_for_translation(args.curves_path)
        base = os.path.splitext(os.path.basename(args.curves_path))[0]
        out_path = os.path.join('output', f'translate_{base}.json')
        extract_data = {
            'source': args.curves_path,
            'target_langs': langs,
            'keep_terms': KEEP_TERMS,
            'total_segments': len(texts),
            'segments': texts,
        }
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(extract_data, f, indent=2, ensure_ascii=False)
        print(f"[i18n] Estratti {len(texts)} segmenti → {out_path}")
        print(f"  → L'LLM in IDE legge questo file e traduce i segmenti")
    else:
        # Solo nomi carte (no LLM)
        for lang in langs:
            out = args.output if len(langs) == 1 else None
            translate_card_names_only(args.curves_path, lang, output_path=out)

    print("[i18n] Done.")


if __name__ == '__main__':
    main()
