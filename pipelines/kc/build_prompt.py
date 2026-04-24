"""Assemble monolithic prompt for killer curves — zero file reads needed by LLM.

Vendorized from analisidef/test_kc/src/build_prompt.py.
Adapted for App_tool:
  - Reads digest from App_tool/output/digests/ (native PG-first)
  - Reads existing KC from PG (via caller passing data), not from file
  - Prompt language: ENGLISH (App_tool is English-only)
  - No analisidef path references
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DIGEST_DIR = _PROJECT_ROOT / "output" / "digests"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
CARDS_DB_PATH = Path("/mnt/HC_Volume_104764377/finanza/Lor/cards_db.json")

DECK_COLORS = {
    "AmAm": "Amber, Amethyst",   "AmSa": "Amethyst, Sapphire",
    "EmSa": "Emerald, Sapphire", "AbE": "Amber, Emerald",
    "AbS": "Amber, Sapphire",    "AbR": "Amber, Ruby",
    "AbSt": "Amber, Steel",      "AmySt": "Amethyst, Steel",
    "SSt": "Sapphire, Steel",    "AmyE": "Amethyst, Emerald",
    "AmyR": "Amethyst, Ruby",    "RS": "Ruby, Sapphire",
}

# Legacy aliases for backward compat with digest filenames
_DECK_ALIAS = {"AS": "AmSa", "ES": "EmSa"}

# Card ink maps — loaded lazily
_card_ink_lower: dict[str, str] = {}
_card_ink_original: dict[str, str] = {}
_ink_loaded = False
_core_legal_sets: set[int] | None = None


def _ensure_ink_maps():
    global _ink_loaded, _card_ink_lower, _card_ink_original
    if _ink_loaded:
        return
    _ink_loaded = True
    try:
        from pipelines.kc.vendored.cards_api import get_cards_db
        db_all = get_cards_db()
        for n, d in db_all.items():
            i = (d.get("ink") or "").lower()
            if i and i not in ("dual ink", "inkless"):
                _card_ink_lower[n.lower()] = i
                _card_ink_original[n] = i
    except Exception:
        if CARDS_DB_PATH.exists():
            for n, d in json.load(open(CARDS_DB_PATH)).items():
                i = (d.get("ink") or "").lower()
                if i and i not in ("dual ink", "inkless"):
                    _card_ink_lower[n.lower()] = i
                    _card_ink_original[n] = i


def _get_core_legal_sets() -> set[int]:
    global _core_legal_sets
    if _core_legal_sets is not None:
        return _core_legal_sets
    try:
        from backend.models import SessionLocal
        from backend.services.meta_epoch_service import get_current_epoch
        db = SessionLocal()
        try:
            epoch = get_current_epoch(db)
        finally:
            db.close()
        _core_legal_sets = set(epoch.legal_sets or []) if epoch else set()
    except Exception:
        _core_legal_sets = set()
    return _core_legal_sets


def _parse_card_set(card_info: dict | None) -> int | None:
    if not isinstance(card_info, dict):
        return None
    raw = card_info.get("set")
    try:
        return int(raw) if raw is not None and raw != "" else None
    except (TypeError, ValueError):
        return None


def _build_core_legality_guard(digest_data: dict | None = None) -> str:
    legal_sets = _get_core_legal_sets()
    if not digest_data or not legal_sets:
        return ""

    cards_db = digest_data.get("cards_db", {}) or {}
    candidates = set(digest_data.get("card_examples", {}).keys())
    for p in digest_data.get("profiles", {}).values():
        candidates.update((p.get("top_cards") or {}).keys())
    pb = digest_data.get("our_playbook", {}) or {}
    for combo in pb.get("our_key_combos", []) or []:
        candidates.update(combo.get("cards", []) or [])
    for neutralized in (pb.get("our_neutralizations") or {}).values():
        candidates.update((neutralized.get("neutralized_by") or {}).keys())
    candidates.update(((pb.get("our_disruption") or {}).get("cards_stripped") or {}).keys())

    illegal = []
    for card_name in sorted(c for c in candidates if c):
        set_num = _parse_card_set(cards_db.get(card_name))
        if set_num is not None and set_num not in legal_sets:
            illegal.append(f"  - {card_name} (set {set_num})")

    if not illegal:
        return ""

    return f"""
=== CORE LEGALITY — HARD CONSTRAINT ===

This matchup is CORE. Any card from a set outside the current legal Core rotation is ILLEGAL.
Current legal sets for Core: {", ".join(str(s) for s in sorted(legal_sets))}

KNOWN ILLEGAL CARDS DETECTED IN DIGEST CONTEXT:
{chr(10).join(illegal)}

BEFORE writing each curve:
1. sequence.plays[].card must be Core-legal.
2. response.cards must be Core-legal.
3. If a tempting card is illegal for Core, do NOT use it even if colors fit.

=== END CORE LEGALITY ===
"""


def _build_remember(digest_data: dict) -> str:
    """Build a REMEMBER section from our_playbook data."""
    pb = digest_data.get('our_playbook')
    if not pb:
        return ""

    lines = ["\n=== REMEMBER — data from our playbook for this matchup ===\n"
             "This data MUST influence the response.strategy of EVERY curve.\n"
             "CITE the numbers in responses (e.g. 'WR 63%', 'avg turn T7.4', 'singer Donald 67%').\n"
             "Responses without references to the data below are TOO GENERIC.\n"]

    wb = pb.get('our_win_behavior', {})
    w = wb.get('wins', {})
    l = wb.get('losses', {})
    if w and l:
        ws = w.get('songs_per_game', 0)
        ls = l.get('songs_per_game', 0)
        fst_w = w.get('first_song_turn')
        wr = w.get('removal_per_game', 0)
        lr = l.get('removal_per_game', 0)
        lines.append(f"- Songs/game: WIN={ws} vs LOSS={ls}. "
                     f"First song in wins: T{fst_w}. "
                     f"Do NOT suggest responses with songs before T{fst_w}.")
        lines.append(f"- Removal/game: WIN={wr} vs LOSS={lr}. "
                     f"{'Removal is critical.' if wr > lr * 1.3 else ''}")

    combos = pb.get('our_key_combos', [])
    if combos:
        c = combos[0]
        cards_str = ' + '.join(c['cards'])
        lines.append(f"- MAIN COMBO: {cards_str} — "
                     f"{c['games']}g, rate {c['rate_pct']}%, "
                     f"WR {c['wr']}%. Without combo: WR {c['wr_without']}%.")
        if c.get('singers'):
            best = [s for s in c['singers'] if s['verdict'] == 'best']
            traps = [s for s in c['singers'] if s['verdict'] == 'trap']
            if best:
                b = best[0]
                lines.append(f"  Best singer: {b['singer']} ({b['games']}g, WR {b['wr']}%).")
            if traps:
                t = traps[0]
                lines.append(f"  TRAP singer: {t['singer']} ({t['games']}g, WR {t['wr']}%). Do NOT suggest it.")
        if len(combos) >= 2:
            c2 = combos[1]
            lines.append(f"- COMBO #2: {' + '.join(c2['cards'])} — "
                         f"{c2['games']}g, rate {c2['rate_pct']}%, WR {c2['wr']}%.")

    dis = pb.get('our_disruption', {})
    rate = dis.get('rate_pct', 0)
    if rate >= 30:
        stripped = dis.get('cards_stripped', {})
        top3 = list(stripped.items())[:3]
        stripped_str = ', '.join(f"{n}x {card}" for card, n in top3)
        lines.append(f"- DISRUPTION: {rate}% of games. "
                     f"Cards stripped: {stripped_str}. "
                     f"Songs stripped: {dis.get('songs_stripped_pct', 0)}%.")
        if dis.get('type') == 'targeted_songs':
            lines.append("  Type: targeted (songs). Song-based combo may not work. Suggest a non-song plan B.")
        elif rate >= 50:
            lines.append(f"  Type: {dis.get('type', 'random')}. Keep few cards in hand.")
    else:
        lines.append(f"- DISRUPTION: low ({rate}%). Songs safe in hand.")

    neut = pb.get('our_neutralizations', {})
    targeted_responses = []
    for opp_card, data in neut.items():
        for remover, info in data.get('neutralized_by', {}).items():
            if info.get('type') != 'mass_removal' and info['count'] >= 10:
                targeted_responses.append((opp_card, remover, info['count'], info['avg_turn']))
    targeted_responses.sort(key=lambda x: -x[2])
    if targeted_responses:
        lines.append("- REAL NEUTRALIZATIONS (from won games, not theory):")
        for opp, rem, count, avg_t in targeted_responses[:5]:
            lines.append(f"  {rem} on {opp}: {count}x, avg turn T{avg_t}")

    lines.append("\n=== END REMEMBER ===")
    return '\n'.join(lines)


def _build_color_guard(our: str, opp: str, digest_data: dict | None = None) -> str:
    _ensure_ink_maps()
    our_colors_str = DECK_COLORS[our]
    our_set = {c.strip().lower() for c in our_colors_str.split(",")}

    forbidden = []
    if digest_data:
        prominent = set(digest_data.get('card_examples', {}).keys())
        for p in digest_data.get('profiles', {}).values():
            prominent.update(p.get('top_cards', {}).keys())

        cards_db = digest_data.get('cards_db', {})
        for card_name in sorted(prominent):
            card_info = cards_db.get(card_name)
            if isinstance(card_info, dict):
                ink = (card_info.get('ink', '') or '').lower()
            else:
                ink = _card_ink_lower.get(card_name.lower(), '')
            if '/' in ink:
                ink_ours = all(c.strip() in our_set for c in ink.split('/'))
            else:
                ink_ours = ink in our_set or ink in ('dual ink', 'inkless')
            if ink and not ink_ours:
                forbidden.append(f"  - {card_name} ({ink.upper()})")

    if not forbidden:
        return ""

    return f"""
=== RESPONSE CARD DOMAIN — HARD CONSTRAINT ===

For response.cards, you may use ONLY cards whose ink is {our_colors_str}.
This is a HARD RULE — no exceptions.

FORBIDDEN CARDS (these appear in the digest but are NOT {our_colors_str} — DO NOT USE in response.cards):
{chr(10).join(sorted(forbidden))}

BEFORE writing each response.cards array:
1. Check every card: is its ink {our_colors_str}? If NOT → remove it.
2. Never include cards from the opponent's ink ({DECK_COLORS[opp]}).
3. Prefer a simpler legal answer over a stronger illegal answer.

=== END RESPONSE CARD DOMAIN ===
"""


def _build_sequence_guard(our: str, opp: str, digest_data: dict | None = None) -> str:
    _ensure_ink_maps()
    our_colors_str = DECK_COLORS[our]
    opp_colors_str = DECK_COLORS[opp]
    our_set = {c.strip().lower() for c in our_colors_str.split(",")}

    candidates = set()
    if digest_data:
        pb = digest_data.get('our_playbook', {}) or {}
        for combo in pb.get('our_key_combos', []) or []:
            for card in combo.get('cards', []) or []:
                if card:
                    candidates.add(card)
        for _, ndata in (pb.get('our_neutralizations') or {}).items():
            for remover in (ndata.get('neutralized_by') or {}).keys():
                if remover:
                    candidates.add(remover)
        stripped = (pb.get('our_disruption') or {}).get('cards_stripped', {}) or {}
        for card in list(stripped.keys())[:10]:
            if card:
                candidates.add(card)

    if not candidates:
        return ""

    forbidden = []
    cards_db = (digest_data or {}).get('cards_db', {}) or {}
    for card_name in sorted(candidates):
        card_info = cards_db.get(card_name)
        if isinstance(card_info, dict):
            ink = (card_info.get('ink', '') or '').lower()
        else:
            ink = _card_ink_lower.get(card_name.lower(), '')
        if not ink or ink in ('inkless', 'dual ink'):
            continue
        if '/' in ink:
            ink_ours = all(c.strip() in our_set for c in ink.split('/'))
        else:
            ink_ours = ink in our_set
        if ink_ours:
            forbidden.append(f"  - {card_name} ({ink.upper()})")

    if not forbidden:
        return ""

    return f"""
=== SEQUENCE DOMAIN — HARD CONSTRAINT ===

For curve.sequence.plays[].card, you may use ONLY cards whose ink is {opp_colors_str}.
This is a HARD RULE — no exceptions.

FORBIDDEN CARDS IN SEQUENCE (these are OUR cards — {our_colors_str} — they belong in OUR playbook, NEVER in the opponent's sequence):
{chr(10).join(sorted(forbidden))}

BEFORE writing each sequence.plays entry:
1. Check: is this card's ink {opp_colors_str}? If NOT → this is OUR card, it belongs in response.cards only.
2. The sequence describes what the OPPONENT plays against us. Never swap sides.
3. our_playbook combo cards (shown above) are especially tempting — they are NOT opponent moves.

=== END OPPONENT SEQUENCE GUARD ===
"""


def build_prompt(our: str, opp: str, game_format: str = 'core',
                 existing_kc: dict | None = None) -> str:
    """Build the full prompt for OpenAI killer curves generation.

    Args:
        our: Our deck code (e.g. "AmSa", "RS")
        opp: Opponent deck code
        game_format: "core" or "infinity"
        existing_kc: Existing KC dict from PG (optional, for update mode)
    """
    our = _DECK_ALIAS.get(our, our)
    opp = _DECK_ALIAS.get(opp, opp)
    sfx = '_inf' if game_format == 'infinity' else ''

    rules = (PROMPTS_DIR / "rules_compact.md").read_text()
    istruzioni = (PROMPTS_DIR / "istruzioni_compact.md").read_text()

    digest_file = DIGEST_DIR / f"digest_{our}_vs_{opp}{sfx}.json"
    with open(digest_file) as f:
        digest_data = json.load(f)

    # Build ink map from digest's own cards_db
    cards_db_section = digest_data.get('cards_db', {})
    digest_ink_map = {}
    for cname, cinfo in cards_db_section.items():
        if isinstance(cinfo, dict):
            ink = (cinfo.get('ink', '') or '').upper()
            if ink and ink not in ('DUAL INK', 'INKLESS'):
                digest_ink_map[cname] = ink.split('/')[0] if '/' in ink else ink

    # Tag card colors only in example_games
    games_text = json.dumps(digest_data.get('example_games', []), indent=2, ensure_ascii=False)
    for card in sorted(digest_ink_map.keys(), key=len, reverse=True):
        ink = digest_ink_map[card]
        pattern = re.escape(card) + r'(?!\s*\[)'
        games_text = re.sub(pattern, f"{card} [{ink}]", games_text)

    # Assemble digest
    digest_data.pop('example_games', None)
    digest_data.pop('cards_db', None)
    digest = json.dumps(digest_data, indent=2, ensure_ascii=False).rstrip().rstrip('}')
    digest += ',\n  "example_games": ' + games_text
    digest += ',\n  "cards_db": ' + json.dumps(cards_db_section, indent=2, ensure_ascii=False)
    digest += '\n}'

    our_colors = DECK_COLORS[our]
    opp_colors = DECK_COLORS[opp]
    today = date.today().isoformat()

    existing_section = ""
    if existing_kc:
        existing_json = json.dumps(existing_kc, indent=2, ensure_ascii=False)
        existing_section = f"""
=== EXISTING CURVES (base to update) ===

These curves were generated previously. Use them as a base:
- Keep the sequences (opponent cards turn by turn) if confirmed by digest
- ALWAYS REWRITE the response block using our_playbook data (REMEMBER): real timing, our combos, singer tips, disruption. The old responses are generic — improve them with specific data
- Update metadata.date to "{today}" and the frequencies
- If different patterns emerge → modify/add/remove curves

{existing_json}

=== END EXISTING CURVES ===
"""

    _digest_for_guard = {**digest_data, 'cards_db': cards_db_section}
    color_guard = _build_color_guard(our, opp, digest_data=_digest_for_guard)
    sequence_guard = _build_sequence_guard(our, opp, digest_data=_digest_for_guard)
    legality_guard = _build_core_legality_guard(_digest_for_guard) if game_format == 'core' else ""

    prompt = f"""You are a tactical analyst for Disney Lorcana. Generate killer curves for {our} vs {opp}.

DECK COLORS — memorize BEFORE reading any data:
- OUR deck ({our}): {our_colors} — cards in response.cards MUST be ONLY of these colors
- OPPONENT deck ({opp}): {opp_colors} — cards in sequence are of these colors
- If a card is NOT {our_colors}, it CANNOT appear in response.cards
{color_guard}
{sequence_guard}
{legality_guard}
Today's date: {today}

=== LORCANA RULES ===

{rules}

=== END RULES ===

=== KILLER CURVES INSTRUCTIONS ===

{istruzioni}

=== END INSTRUCTIONS ===

=== MATCHUP DIGEST ===

{digest}

=== END DIGEST ===
{existing_section}
=== FINAL INSTRUCTIONS ===

1. Follow phases 0-8 of the killer curves instructions
2. Output the killer curves JSON directly
3. Do NOT explain your reasoning — write only the JSON
4. Do NOT read other files — everything you need is already in this prompt
5. The [AMBER], [STEEL], [RUBY] etc. tags in the digest are ONLY for your reference — do NOT include them in card names in the JSON output. Write only the pure card name (e.g. "Grandmother Willow - Ancient Advisor", NOT "Grandmother Willow - Ancient Advisor [AMBER]")
6. The digest contains `our_playbook` — use it for responses (see REMEMBER below)
7. Write all response-facing text in ENGLISH
{_build_remember(digest_data)}
=== STRUCTURAL FINAL CHECK ===
Before writing each curve, verify:
- sequence.plays[].card → ONLY {opp_colors} ink (opponent's moves)
- response.cards → ONLY {our_colors} ink (our answers)
- if format is Core: every card in sequence and response must be legal in the current Core rotation
- our_playbook data is FOR enriching the response block, NOT for populating sequence
- response.strategy = one-line summary only
- detailed response fields must stay tied to this exact curve, not generic matchup coaching
Swapping sides is the most common LLM failure — double-check before output.
"""
    return prompt
