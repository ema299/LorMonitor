"""Post-check for response card colors in killer curves JSON.

Vendorized from analisidef/test_kc/src/postfix_response_colors.py.
Adapted for App_tool: uses vendored cards_api.
"""

import json
import re
from pathlib import Path

from pipelines.kc.vendored.cards_api import get_ink_map

CARDS_DB_PATH = Path("/mnt/HC_Volume_104764377/finanza/Lor/cards_db.json")

DECK_COLORS = {
    "AmAm": {"amber", "amethyst"}, "AmSa": {"amethyst", "sapphire"},
    "EmSa": {"emerald", "sapphire"}, "AbE": {"amber", "emerald"},
    "AbS": {"amber", "sapphire"}, "AbR": {"amber", "ruby"},
    "AbSt": {"amber", "steel"}, "AmySt": {"amethyst", "steel"},
    "SSt": {"sapphire", "steel"}, "AmyE": {"amethyst", "emerald"},
    "AmyR": {"amethyst", "ruby"}, "RS": {"ruby", "sapphire"},
    # Legacy aliases
    "AS": {"amethyst", "sapphire"}, "ES": {"emerald", "sapphire"},
}

_card_ink = None


def _get_card_ink():
    global _card_ink
    if _card_ink is None:
        try:
            _card_ink = get_ink_map()
        except Exception:
            _card_ink = {}
            if CARDS_DB_PATH.exists():
                _db = json.load(open(CARDS_DB_PATH))
                for name, data in _db.items():
                    ink = (data.get("ink") or "").lower()
                    if ink and ink not in ("dual ink", "inkless"):
                        _card_ink[name.lower()] = ink
    return _card_ink


def _strip_color_tags(text):
    return re.sub(r'\s*\[(AMBER|AMETHYST|EMERALD|RUBY|SAPPHIRE|STEEL)\]', '', text)


def _strip_tags_from_json(data):
    if isinstance(data, str):
        return _strip_color_tags(data)
    elif isinstance(data, list):
        return [_strip_tags_from_json(item) for item in data]
    elif isinstance(data, dict):
        return {_strip_color_tags(k): _strip_tags_from_json(v) for k, v in data.items()}
    return data


def check_data(data, drop_invalid=False):
    """Check killer curves dict for color violations.

    Returns (n_ok, n_bad, details). If drop_invalid, removes bad cards in-place.
    """
    data_clean = _strip_tags_from_json(data)
    if data_clean != data:
        data.clear()
        data.update(data_clean)

    matchup = data.get("matchup", "")
    if " vs " in matchup:
        our = matchup.split(" vs ")[0]
    elif "metadata" in data:
        our = data["metadata"].get("our_deck", "")
    else:
        our = ""

    if not our:
        return 0, 0, []
    our_colors = DECK_COLORS.get(our)
    if not our_colors:
        return 0, 0, []

    card_ink = _get_card_ink()
    details = []
    total_ok = 0
    total_bad = 0

    for ci, curve in enumerate(data.get("curves", [])):
        resp = curve.get("response", {})
        cards = resp.get("cards", [])
        if not isinstance(cards, list):
            continue

        bad_indices = []
        for i, card in enumerate(cards):
            cname = card if isinstance(card, str) else card.get("card", card.get("name", ""))
            clower = cname.lower()
            ink = card_ink.get(clower, "")
            if '/' in ink:
                ink_ok = all(c.strip() in our_colors for c in ink.split('/'))
            else:
                ink_ok = not ink or ink in our_colors or ink == 'dual ink'
            if not ink_ok:
                details.append({
                    "curve": ci + 1,
                    "curve_name": curve.get("name", "?"),
                    "card": cname,
                    "card_ink": ink,
                    "our_colors": sorted(our_colors),
                })
                total_bad += 1
                bad_indices.append(i)
            else:
                total_ok += 1

        if drop_invalid and bad_indices:
            resp["cards"] = [c for i, c in enumerate(cards) if i not in bad_indices]

    return total_ok, total_bad, details
