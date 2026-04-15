"""Legality service — valida la legalita' delle carte nei match rispetto al formato.

Ported from analisidef/audit_legality.py (11/04/2026) — reso autonomo da analisidef
leggendo direttamente il cache duels.ink che App_tool gia' mantiene aggiornato
via backend/workers/static_importer.py.

Uso tipico (import pipeline):

    from backend.services.legality_service import get_checker

    checker = get_checker('core')
    is_legal, violations = checker.check_match(logs)
    if not is_legal:
        # skip insert, log counter
        ...

Uso CLI audit manuale: vedi scripts/audit_legality.py.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Callable, Iterable

logger = logging.getLogger(__name__)

# Stesso cache file popolato da backend/workers/static_importer.py (refresh settimanale).
# Contiene il campo `legality` originale di duels.ink, che App_tool non salva in PG.
CACHE_PATH = Path("/mnt/HC_Volume_104764377/finanza/Lor/duels_ink_cards_cache.json")

# Event types che referenziano carte (log duels.ink)
CARD_EVENTS = {
    "CARD_PLAYED", "CARD_INKED", "CARD_DRAWN", "CARD_QUEST",
    "CARD_ATTACK", "INITIAL_HAND", "MULLIGAN",
    "CARD_REVEALED", "CARD_DISCARDED", "CARD_BOUNCED",
    "CARD_PUT_INTO_INKWELL", "CARD_BOOSTED",
}

# Queue-prefix safety net: match finiti nella cartella sbagliata
FORMAT_QUEUE_PREFIXES = {
    "core": ("S11-", "S12-"),
    "infinity": ("INF-", "JA-", "ZH-"),
}


def _load_cards_cache() -> dict:
    """Carica il cache duels.ink (stesso file usato da static_importer)."""
    if not CACHE_PATH.exists():
        logger.warning("duels.ink cache not found at %s — legality check disabled", CACHE_PATH)
        return {}
    try:
        with open(CACHE_PATH) as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("Failed to load duels.ink cache: %s", exc)
        return {}


def _legality_matches(leg_value: str, format_name: str) -> bool:
    """True se il tag duels.ink rappresenta legalita' nel formato richiesto.

    Accetta:
      - exact match: 'core' per core, 'infinity' per infinity
      - season variant: 'core_s12', 'infinity_s12', 'core_s13', ...
    Rifiuta:
      - lingue tradotte: 'core_zh', 'core_ja' (sono regional, non legality)
    """
    if leg_value == format_name:
        return True
    prefix = format_name + "_s"
    if leg_value.startswith(prefix):
        suffix = leg_value[len(prefix):]
        return suffix.isdigit()
    return False


def _build_index(cards_db: dict, format_name: str) -> tuple[dict, dict, set]:
    """Suddivide le carte in legali/illegali/unknown per il formato.

    duels.ink emette sia tag 'base' (es. 'core') sia variant per stagione
    (es. 'core_s12') e per lingua (es. 'core_zh'). Consideriamo legale
    solo i primi due (vedi _legality_matches).
    """
    legal, illegal, unknown = {}, {}, set()
    for name, data in cards_db.items():
        if not isinstance(data, dict):
            continue
        lower = name.lower()
        leg = data.get("legality") or []
        if not leg:
            unknown.add(name)
            continue
        is_legal = any(_legality_matches(l, format_name) for l in leg)
        if is_legal:
            legal[lower] = name
        else:
            illegal[lower] = {
                "name": name,
                "legality": leg,
                "set": data.get("set", "?"),
            }
    return legal, illegal, unknown


def _build_matcher(legal: dict, illegal: dict, cards_db: dict) -> Callable:
    """Ritorna funzione (replay_name) -> (canonical, is_legal, confidence).

    Chain: exact -> normalized (lower, strip commas) -> fuzzy base name.
    """
    db_norm = {}
    for name in cards_db:
        key = name.lower().replace(",", "").replace("  ", " ").strip()
        db_norm[key] = name

    base_index = defaultdict(list)
    for name in cards_db:
        base = name.split(" - ")[0].strip().lower()
        base_index[base].append(name)

    cache: dict[str, tuple] = {}

    def match(replay_name: str):
        if replay_name in cache:
            return cache[replay_name]
        low = replay_name.lower()
        if low in legal:
            result = (legal[low], True, "exact")
        elif low in illegal:
            result = (illegal[low]["name"], False, "exact")
        else:
            norm_key = low.replace(",", "").replace("  ", " ").strip()
            if norm_key in db_norm:
                db_name = db_norm[norm_key]
                is_legal = db_name.lower() in legal
                result = (db_name, is_legal, "normalized")
            else:
                base = replay_name.split(" - ")[0].strip().lower()
                candidates = base_index.get(base, [])
                if len(candidates) == 1:
                    db_name = candidates[0]
                    is_legal = db_name.lower() in legal
                    result = (db_name, is_legal, "fuzzy")
                else:
                    result = (replay_name, None, "unknown")
        cache[replay_name] = result
        return result

    return match


class LegalityChecker:
    """Checker per un formato specifico. Thread-safe dopo build."""

    def __init__(self, format_name: str, cards_db: dict | None = None):
        self.format_name = format_name
        db = cards_db if cards_db is not None else _load_cards_cache()
        self._available = bool(db)
        if not self._available:
            logger.warning("LegalityChecker for '%s' initialized without DB — will pass all",
                           format_name)
            self.legal = {}
            self.illegal = {}
            self.unknown_db = set()
            self._matcher = lambda name: (name, True, "no-db")
        else:
            self.legal, self.illegal, self.unknown_db = _build_index(db, format_name)
            self._matcher = _build_matcher(self.legal, self.illegal, db)
        self._queue_prefixes = FORMAT_QUEUE_PREFIXES.get(format_name, ())

    @property
    def available(self) -> bool:
        return self._available

    def check_queue(self, queue_name: str | None) -> bool:
        """True se la queue matcha il formato, False se e' un match mis-filed."""
        if not self._queue_prefixes or not queue_name:
            return True
        return queue_name.startswith(self._queue_prefixes)

    def check_match(self, logs: Iterable[dict]) -> tuple[bool, list[dict]]:
        """Scansiona i log e ritorna (is_legal, violations).

        is_legal = False se *almeno una* carta illegale e' stata giocata/inkata/pescata.
        Carte 'unknown' (non nel DB) NON sono trattate come illegali — sono silent.
        """
        if not self._available:
            return True, []

        violations: list[dict] = []
        seen = set()
        for event in logs or ():
            etype = event.get("type", "")
            if etype not in CARD_EVENTS:
                continue
            for ref in event.get("cardRefs", []) or ():
                if not isinstance(ref, dict):
                    continue
                card_name = ref.get("name", "")
                if not card_name or card_name in seen:
                    continue
                seen.add(card_name)
                canonical, is_legal, confidence = self._matcher(card_name)
                if is_legal is False:
                    card_id = ref.get("id", "")
                    violations.append({
                        "card": canonical,
                        "card_id": card_id,
                        "set": card_id.split("-")[0] if card_id else "?",
                        "player": event.get("player"),
                        "event": etype,
                        "confidence": confidence,
                    })
        return len(violations) == 0, violations


# Singleton per formato, lazy.
_CHECKERS: dict[str, LegalityChecker] = {}


def get_checker(format_name: str) -> LegalityChecker:
    """Restituisce un checker condiviso per il formato. Lazy + cached."""
    if format_name not in _CHECKERS:
        _CHECKERS[format_name] = LegalityChecker(format_name)
    return _CHECKERS[format_name]


def reset_checkers() -> None:
    """Usato da static_importer dopo refresh cards cache: forza reload al prossimo get_checker."""
    _CHECKERS.clear()
