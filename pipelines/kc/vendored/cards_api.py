"""Unified card database — duels.ink API primary, local cards_db.json fallback.

Vendorized from analisidef/test_kc/src/cards_api.py (freeze SHA pending).
Paths adapted for App_tool.
"""

import json
import time
import urllib.request
from pathlib import Path

DUELS_INK_API = "https://duels.ink/api/cards"
CACHE_PATH = Path("/mnt/HC_Volume_104764377/finanza/Lor/duels_ink_cards_cache.json")
LOCAL_DB_PATH = Path("/mnt/HC_Volume_104764377/finanza/Lor/cards_db.json")
CACHE_MAX_AGE = 6 * 3600  # 6 hours

_db = None  # singleton cache


def _fetch_duels_ink():
    """Fetch all cards from duels.ink API (paginated)."""
    all_cards = []
    offset = 0
    limit = 100
    while True:
        url = f"{DUELS_INK_API}?limit={limit}&offset={offset}"
        req = urllib.request.Request(url, headers={"User-Agent": "LorcanaAnalyzer/1.0"})
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())
        cards = data.get("cards", [])
        all_cards.extend(cards)
        if not data.get("meta", {}).get("hasMore", False):
            break
        offset += limit
    return all_cards


def _normalize_duels_card(c):
    """Convert duels.ink card to our standard format."""
    colors = c.get("colors", [])
    if len(colors) >= 2:
        ink = "/".join(col.lower() for col in colors)
    elif colors:
        ink = colors[0].lower()
    else:
        ink = ""

    ability_parts = []
    for sa in c.get("specialAbilities", []) or []:
        name = sa.get("name", "")
        effect = sa.get("effect", "")
        if name and effect:
            ability_parts.append(f"{name} {effect}")
        elif effect:
            ability_parts.append(effect)
    for a in c.get("abilities", []) or []:
        if isinstance(a, str):
            ability_parts.append(a)
        elif isinstance(a, dict):
            kw = a.get("ability", "") or a.get("name", "")
            val = a.get("value")
            if kw and val is not None:
                ability_parts.append(f"{kw} {val}")
            elif kw:
                ability_parts.append(kw)
    ability = " | ".join(ability_parts) if ability_parts else c.get("rulesText", "")

    return {
        "id": c.get("id", ""),
        "name": c.get("name", ""),
        "title": c.get("title", ""),
        "fullName": c.get("fullName", ""),
        "ink": ink,
        "cost": c.get("cost", 0),
        "type": c.get("type", ""),
        "str": c.get("strength") or 0,
        "will": c.get("willpower") or 0,
        "lore": c.get("lore") or 0,
        "inkable": c.get("inkable", True),
        "rarity": c.get("rarity", ""),
        "ability": ability,
        "subtypes": c.get("subtypes", []),
        "set": c.get("id", "").split("-")[0] if c.get("id") else "",
        "legality": c.get("legality", []),
        "image": c.get("imageSmallUrl", ""),
    }


def _build_db_from_duels(raw_cards):
    db = {}
    for c in raw_cards:
        norm = _normalize_duels_card(c)
        full = norm["fullName"]
        short = norm["name"]
        if full:
            db[full] = norm
        if short and short not in db:
            db[short] = norm
    return db


def _load_local_db():
    if not LOCAL_DB_PATH.exists():
        return {}
    try:
        raw = json.load(open(LOCAL_DB_PATH))
        db = {}
        for name, data in raw.items():
            data = dict(data)
            if "ink" in data:
                data["ink"] = (data["ink"] or "").lower()
            db[name] = data
        return db
    except Exception:
        return {}


def refresh_cache(force=False):
    if not force and CACHE_PATH.exists():
        age = time.time() - CACHE_PATH.stat().st_mtime
        if age < CACHE_MAX_AGE:
            return True
    try:
        raw_cards = _fetch_duels_ink()
        db = _build_db_from_duels(raw_cards)
        local = _load_local_db()
        for name, data in local.items():
            if name not in db:
                db[name] = data
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_PATH, "w") as f:
            json.dump(db, f, ensure_ascii=False)
        global _db
        _db = db
        return True
    except Exception as e:
        print(f"[cards_api] duels.ink fetch failed: {e}", flush=True)
        return False


def get_cards_db():
    global _db
    if _db is not None:
        return _db
    if CACHE_PATH.exists():
        age = time.time() - CACHE_PATH.stat().st_mtime
        if age < CACHE_MAX_AGE:
            try:
                _db = json.load(open(CACHE_PATH))
                return _db
            except Exception:
                pass
    if refresh_cache():
        return _db
    _db = _load_local_db()
    if _db:
        print(f"[cards_api] Using local fallback ({len(_db)} cards)", flush=True)
    return _db


def get_card(name):
    db = get_cards_db()
    return db.get(name)


def get_ink(name):
    card = get_card(name)
    if card:
        return (card.get("ink") or "").lower()
    return ""


def get_ink_map():
    db = get_cards_db()
    return {name.lower(): (data.get("ink") or "").lower()
            for name, data in db.items()
            if data.get("ink") and data["ink"].lower() not in ("dual ink", "inkless")}
