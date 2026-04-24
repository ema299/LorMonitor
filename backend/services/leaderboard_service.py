"""Leaderboard service — fetch from duels.ink API, cache in Redis."""
import json
import logging
import urllib.request

from backend.config import DUELS_SESSION
from backend.services.cache import cache_get, cache_set

logger = logging.getLogger(__name__)

CACHE_TTL = 3600  # 1 hour

LEADERBOARD_QUEUES = {
    "core_bo1": "core-bo1",
    "core_bo3": "core-bo3",
    "infinity_bo1": "infinity-bo1-beta",
    "infinity_bo3": "infinity-bo3-beta",
}

TOP_N = 100
PRO_N = 50


def fetch_leaderboards() -> dict:
    """Fetch leaderboards from duels.ink API (4 queues).

    Returns: {
        "core_top": [names], "core_pro": [names],
        "inf_top": [names], "inf_pro": [names],
        "raw": {queue_key: [player_dicts]},
        "mmr_ref": {name_lower: best_mmr}
    }
    """
    cached = cache_get("leaderboard:all")
    if cached:
        return cached

    if not DUELS_SESSION:
        logger.warning("DUELS_SESSION not configured; leaderboard fetch disabled")
        empty = {
            "core_top": [],
            "core_pro": [],
            "inf_top": [],
            "inf_pro": [],
            "mmr_ref": {},
            "raw": {},
        }
        cache_set("leaderboard:all", empty, 300)
        return empty

    cookie = f"__Secure-better-auth.session_token={DUELS_SESSION}"
    raw = {}

    for queue_key, queue_id in LEADERBOARD_QUEUES.items():
        url = f"https://duels.ink/api/leaderboard?queue={queue_id}"
        try:
            req = urllib.request.Request(url, headers={
                "Cookie": cookie,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            players = data.get("leaderboard", [])
            raw[queue_key] = [
                {
                    "rank": p.get("rank", 0),
                    "name": p.get("username") or "",
                    "mmr": p.get("mmr", 0),
                    "peak_mmr": p.get("peakMmr", 0),
                    "wins": p.get("wins", 0),
                    "losses": p.get("losses", 0),
                    "wr": p.get("winRate", 0),
                    "games": p.get("gamesPlayed", 0),
                    "tier": p.get("tier", {}).get("name", ""),
                }
                for p in players
            ]
            logger.info("leaderboard %s: %d players", queue_id, len(players))
        except Exception as e:
            logger.warning("leaderboard %s fetch failed: %s", queue_id, e)
            raw[queue_key] = []

    core_lists = [raw.get("core_bo1", []), raw.get("core_bo3", [])]
    inf_lists = [raw.get("infinity_bo1", []), raw.get("infinity_bo3", [])]

    # MMR reference
    mmr_ref = {}
    for queue_players in [*core_lists, *inf_lists]:
        for p in queue_players:
            name = (p.get("name", "") or "").strip().lower()
            mmr = p.get("mmr", 0) or 0
            if name and mmr:
                if name not in mmr_ref or mmr > mmr_ref[name]:
                    mmr_ref[name] = mmr

    result = {
        "core_top": list(_names_from_raw(core_lists, TOP_N)),
        "core_pro": list(_names_from_raw(core_lists, PRO_N)),
        "inf_top": list(_names_from_raw(inf_lists, TOP_N)),
        "inf_pro": list(_names_from_raw(inf_lists, PRO_N)),
        "mmr_ref": mmr_ref,
        "raw": raw,
    }

    # If every queue came back empty the fetch effectively failed — short TTL
    # so the next request retries instead of poisoning the dashboard blob for 1h.
    all_empty = not any(result[k] for k in ("core_top", "core_pro", "inf_top", "inf_pro"))
    cache_set("leaderboard:all", result, 120 if all_empty else CACHE_TTL)
    return result


def _names_from_raw(raw_lists: list[list[dict]], top_n: int) -> set[str]:
    """Extract top N unique names (by best rank) from union of lists."""
    best_rank = {}
    for plist in raw_lists:
        for p in plist:
            name = (p.get("name", "") or "").strip().lower()
            if not name:
                continue
            rank = p.get("rank", 999)
            if name not in best_rank or rank < best_rank[name]:
                best_rank[name] = rank
    sorted_names = sorted(best_rank.keys(), key=lambda n: best_rank[n])
    return set(sorted_names[:top_n])


def get_cached_leaderboards() -> dict:
    """Get leaderboards, fetching if not cached."""
    return fetch_leaderboards()
