"""PG-first rogue / emerging deck discovery.

Porting target from `analisidef/lib/rogue_scout.py`, adapted to App_tool
runtime constraints:
- PostgreSQL as primary source
- consensus from PG
- optional leaderboard-assisted identity filtering

This service is currently exposed only through an admin/debug endpoint.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from math import sqrt

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.services import static_data_service
from backend.services.leaderboard_service import fetch_leaderboards

SUPPORTED_PERIMETERS = {
    "set11": ["set11"],
    "top": ["top", "pro"],
    "pro": ["pro"],
    "friends_core": ["set11", "top", "pro"],
    "infinity": ["inf"],
    "infinity_top": ["inf", "top", "pro"],
    "infinity_pro": ["inf", "top", "pro"],
}


@dataclass(frozen=True)
class RogueScoutConfig:
    game_format: str = "core"
    days: int = 7
    min_games: int = 10
    min_wr: float = 0.55
    min_mmr: int = 1400
    min_jaccard: float = 0.40
    tier0_count: int = 3
    tier0_perimeter: str = "set11"
    min_tier0_games: int = 5
    min_tier0_wr: float = 0.55
    min_delta_vs_self: float = 0.0
    max_mmr_spread: int = 400
    mmr_tolerance: int = 200
    min_archetype_players: int = 3
    min_archetype_shared: int = 3
    off_meta_validated_jaccard: float = 0.40
    off_meta_validated_wr_lb: float = 0.50
    off_meta_radar_jaccard: float = 0.60
    off_meta_radar_wr_lb: float = 0.40
    off_meta_min_games: int = 15


def round_opt(value: float | None, digits: int = 3) -> float | None:
    return round(value, digits) if value is not None else None


def wilson_lb(wins: int, n: int, z: float = 1.96) -> float | None:
    """95% Wilson lower bound for a binomial winrate."""
    if n <= 0:
        return None
    p = wins / n
    z2 = z * z
    denom = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    spread = z * sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return max(0.0, center - spread)


def jaccard_distance(a: set[str], b: set[str]) -> float | None:
    """Distance 0-1 between observed list and consensus list."""
    if not a or not b:
        return None
    union = len(a | b)
    if union == 0:
        return None
    return 1 - (len(a & b) / union)


def _extract_seen_cards(raw_cards) -> set[str]:
    """Normalize cards_a/cards_b JSON into a flat set of card names."""
    if not raw_cards:
        return set()
    if isinstance(raw_cards, dict):
        return {str(name) for name in raw_cards.keys() if str(name).strip()}
    if isinstance(raw_cards, list):
        return {str(name) for name in raw_cards if str(name).strip()}
    return set()


def _cluster_archetypes(survivors: list[dict], min_players: int, min_shared: int) -> list[tuple[str, list[dict]]]:
    """Connected-components clustering on shared extra-vs-consensus packages."""
    by_deck: dict[str, list[dict]] = defaultdict(list)
    for item in survivors:
        if item.get("has_consensus") and len(item.get("extra_vs_consensus", [])) >= min_shared:
            by_deck[item["deck"]].append(item)

    clusters: list[tuple[str, list[dict]]] = []
    for deck, brewers in by_deck.items():
        if len(brewers) < min_players:
            continue
        adj: dict[int, set[int]] = defaultdict(set)
        for i in range(len(brewers)):
            a = set(brewers[i]["extra_vs_consensus"])
            for j in range(i + 1, len(brewers)):
                b = set(brewers[j]["extra_vs_consensus"])
                if len(a & b) >= min_shared:
                    adj[i].add(j)
                    adj[j].add(i)

        visited = set()
        for start in range(len(brewers)):
            if start in visited:
                continue
            stack = [start]
            comp = []
            while stack:
                node = stack.pop()
                if node in visited:
                    continue
                visited.add(node)
                comp.append(node)
                stack.extend(adj[node])
            if len(comp) >= min_players:
                clusters.append((deck, [brewers[i] for i in comp]))
    return clusters


def _build_archetype_entry(deck: str, members: list[dict]) -> dict:
    """Aggregate one emerging archetype cluster."""
    n_members = len(members)
    card_count: dict[str, int] = defaultdict(int)
    for member in members:
        for card in member.get("extra_vs_consensus", []):
            card_count[card] += 1

    sig_threshold = max(2, int(n_members * 0.8 + 0.999))
    flex_threshold = max(2, int(n_members * 0.4 + 0.999))
    signature_cards = sorted([card for card, cnt in card_count.items() if cnt >= sig_threshold])
    flex_cards = sorted(
        [{"card": card, "n_players": cnt} for card, cnt in card_count.items()
         if cnt >= flex_threshold and card not in signature_cards],
        key=lambda item: -item["n_players"],
    )

    total_games = sum(m["games"] for m in members)
    total_wins = sum(m["wins"] for m in members)
    agg_wr = (total_wins / total_games) if total_games else 0
    agg_wr_lb = wilson_lb(total_wins, total_games)

    t0_games = sum(m["tier0_games"] for m in members)
    t0_wins = sum(m["tier0_wins"] for m in members)
    t0_wr = (t0_wins / t0_games) if t0_games else None
    t0_wr_lb = wilson_lb(t0_wins, t0_games)

    avg_mmr = round(sum(m["avg_mmr"] * m["games"] for m in members) / total_games) if total_games else 0
    avg_jaccard = sum(m["jaccard_distance"] or 0 for m in members) / n_members if n_members else 0

    return {
        "deck": deck,
        "n_players": n_members,
        "total_games": total_games,
        "total_wins": total_wins,
        "agg_wr": round(agg_wr, 3),
        "agg_wr_wilson_lb": round_opt(agg_wr_lb),
        "avg_mmr": avg_mmr,
        "avg_jaccard": round(avg_jaccard, 3),
        "signature_cards": signature_cards,
        "signature_size": len(signature_cards),
        "signature_threshold": sig_threshold,
        "flex_cards": flex_cards,
        "flex_threshold": flex_threshold,
        "vs_tier0": {
            "games": t0_games,
            "wins": t0_wins,
            "wr": round_opt(t0_wr),
            "wr_wilson_lb": round_opt(t0_wr_lb),
        },
        "players": [
            {
                "player": member["player"],
                "games": member["games"],
                "wins": member["wins"],
                "wr": member["wr"],
                "wr_wilson_lb": member["wr_wilson_lb"],
                "avg_mmr": member["avg_mmr"],
                "jaccard": member["jaccard_distance"],
            }
            for member in sorted(members, key=lambda item: -item["games"])
        ],
    }


def get_tier0_codes(
    db: Session,
    game_format: str = "core",
    perimeter: str = "set11",
    days: int = 7,
    count: int = 3,
) -> list[str]:
    """Top-N decks by meta share from PG, used as Tier 0 reference."""
    db_perims = SUPPORTED_PERIMETERS.get(perimeter, [perimeter])
    rows = db.execute(text("""
        WITH sides AS (
            SELECT deck_a AS deck
            FROM matches
            WHERE game_format = :fmt
              AND perimeter = ANY(:perims)
              AND played_at >= now() - make_interval(days => :days)
            UNION ALL
            SELECT deck_b AS deck
            FROM matches
            WHERE game_format = :fmt
              AND perimeter = ANY(:perims)
              AND played_at >= now() - make_interval(days => :days)
        )
        SELECT deck, count(*) AS games
        FROM sides
        GROUP BY deck
        ORDER BY games DESC
        LIMIT :lim
    """), {"fmt": game_format, "perims": db_perims, "days": days, "lim": count}).fetchall()
    return [r.deck for r in rows]


def _load_leaderboard_mmr_ref() -> dict[str, int]:
    """Best-effort leaderboard MMR reference by player name."""
    try:
        return fetch_leaderboards().get("mmr_ref", {}) or {}
    except Exception:
        return {}


def get_candidate_preview(db: Session, cfg: RogueScoutConfig = RogueScoutConfig()) -> dict:
    """Main PG-first rogue scout payload.

    The name is kept for backward compatibility with the existing debug endpoint,
    but the output is now close to the full rogue_scout structure.
    """
    consensus = static_data_service.get_consensus(db)
    tier0_codes = get_tier0_codes(
        db,
        game_format=cfg.game_format,
        perimeter=cfg.tier0_perimeter,
        days=cfg.days,
        count=cfg.tier0_count,
    )
    mmr_ref = _load_leaderboard_mmr_ref()

    rows = db.execute(text("""
        SELECT deck_a, deck_b, winner,
               player_a_name, player_b_name,
               player_a_mmr, player_b_mmr,
               cards_a, cards_b
        FROM matches
        WHERE game_format = :fmt
          AND played_at >= now() - make_interval(days => :days)
    """), {"fmt": cfg.game_format, "days": cfg.days}).fetchall()

    player_deck: dict[tuple[str, str], dict] = {}
    player_totals: dict[str, dict] = {}
    deck_totals: dict[str, dict] = {}

    def _touch(mapping: dict, key, factory):
        if key not in mapping:
            mapping[key] = factory()
        return mapping[key]

    def _pd_factory():
        return {
            "w": 0, "l": 0, "cards": set(), "mmr_sum": 0, "mmr_n": 0,
            "mmr_min": None, "mmr_max": None, "display": "", "t0_w": 0, "t0_l": 0,
        }

    def _tot_factory():
        return {"w": 0, "l": 0}

    total_matches = 0
    matches_with_any_cards = 0
    for r in rows:
        total_matches += 1
        side_a_cards = _extract_seen_cards(r.cards_a)
        side_b_cards = _extract_seen_cards(r.cards_b)
        if side_a_cards or side_b_cards:
            matches_with_any_cards += 1
        sides = [
            {
                "player": (r.player_a_name or "").strip(),
                "deck": r.deck_a,
                "mmr": r.player_a_mmr or 0,
                "cards": side_a_cards,
                "won": r.winner == "deck_a",
                "opp_deck": r.deck_b,
            },
            {
                "player": (r.player_b_name or "").strip(),
                "deck": r.deck_b,
                "mmr": r.player_b_mmr or 0,
                "cards": side_b_cards,
                "won": r.winner == "deck_b",
                "opp_deck": r.deck_a,
            },
        ]
        for side in sides:
            if not side["player"] or not side["deck"] or side["mmr"] < cfg.min_mmr:
                continue
            pd = _touch(player_deck, (side["player"].lower(), side["deck"]), _pd_factory)
            pt = _touch(player_totals, side["player"].lower(), _tot_factory)
            dt = _touch(deck_totals, side["deck"], _tot_factory)
            pd["display"] = side["player"]
            pd["cards"] |= side["cards"]
            pd["mmr_sum"] += side["mmr"]
            pd["mmr_n"] += 1
            pd["mmr_min"] = side["mmr"] if pd["mmr_min"] is None else min(pd["mmr_min"], side["mmr"])
            pd["mmr_max"] = side["mmr"] if pd["mmr_max"] is None else max(pd["mmr_max"], side["mmr"])
            if side["won"]:
                pd["w"] += 1
                pt["w"] += 1
                dt["w"] += 1
            else:
                pd["l"] += 1
                pt["l"] += 1
                dt["l"] += 1
            if side["opp_deck"] in tier0_codes:
                if side["won"]:
                    pd["t0_w"] += 1
                else:
                    pd["t0_l"] += 1

    dropped_by_leaderboard = 0
    if mmr_ref:
        to_drop = []
        for (player_lower, deck), s in player_deck.items():
            if player_lower not in mmr_ref or not s["mmr_n"]:
                continue
            avg_mmr = s["mmr_sum"] / s["mmr_n"]
            if abs(avg_mmr - mmr_ref[player_lower]) > cfg.mmr_tolerance:
                to_drop.append((player_lower, deck))
        for key in to_drop:
            del player_deck[key]
        dropped_by_leaderboard = len(to_drop)

    player_ranges: dict[str, dict] = defaultdict(lambda: {"min": None, "max": None})
    for (player_lower, _), s in player_deck.items():
        pr = player_ranges[player_lower]
        if s["mmr_min"] is not None:
            pr["min"] = s["mmr_min"] if pr["min"] is None else min(pr["min"], s["mmr_min"])
        if s["mmr_max"] is not None:
            pr["max"] = s["mmr_max"] if pr["max"] is None else max(pr["max"], s["mmr_max"])

    hard_spread_drop = max(cfg.max_mmr_spread + 200, 600)
    dropped_by_spread = 0
    for key in list(player_deck.keys()):
        pr = player_ranges[key[0]]
        if pr["min"] is not None and pr["max"] is not None and (pr["max"] - pr["min"]) > hard_spread_drop:
            del player_deck[key]
            dropped_by_spread += 1

    survivors = []
    for (player_lower, deck), s in player_deck.items():
        games = s["w"] + s["l"]
        if games < cfg.min_games:
            continue
        wr = s["w"] / games
        if wr < cfg.min_wr:
            continue
        survivors.append((player_lower, deck, s, games, wr))

    results = []
    for player_lower, deck, s, games, wr in survivors:
        cons = set((consensus.get(deck) or {}).keys())
        jd = jaccard_distance(s["cards"], cons) if cons else None
        wr_lb = wilson_lb(s["w"], games)
        t0_games = s["t0_w"] + s["t0_l"]
        t0_wr = (s["t0_w"] / t0_games) if t0_games else None
        t0_wr_lb = wilson_lb(s["t0_w"], t0_games)

        pt = player_totals[player_lower]
        base_w = pt["w"] - s["w"]
        base_l = pt["l"] - s["l"]
        base_n = base_w + base_l
        base_wr = (base_w / base_n) if base_n else None
        base_wr_lb = wilson_lb(base_w, base_n)
        delta_vs_self = (wr - base_wr) if base_wr is not None else None

        dt = deck_totals[deck]
        other_w = dt["w"] - s["w"]
        other_l = dt["l"] - s["l"]
        other_n = other_w + other_l
        deck_avg_wr = (other_w / other_n) if other_n else None
        delta_vs_deck = (wr - deck_avg_wr) if deck_avg_wr is not None else None

        mmr_spread = (s["mmr_max"] - s["mmr_min"]) if (s["mmr_min"] is not None and s["mmr_max"] is not None) else 0
        noise_flags = []
        if games < 20:
            noise_flags.append("small_sample_overall")
        if t0_games < 8:
            noise_flags.append("small_sample_tier0")
        if base_n == 0:
            noise_flags.append("baseline_mono_deck")
        elif base_n < 10:
            noise_flags.append("baseline_too_small")
        if mmr_spread > cfg.max_mmr_spread:
            noise_flags.append("mmr_spread_high")
        if (wr_lb or 0) < 0.50:
            noise_flags.append("low_wilson_confidence")

        entry = {
            "player": s["display"] or player_lower,
            "player_key": player_lower,
            "deck": deck,
            "games": games,
            "wins": s["w"],
            "wr": round(wr, 3),
            "wr_wilson_lb": round_opt(wr_lb),
            "avg_mmr": round(s["mmr_sum"] / s["mmr_n"]) if s["mmr_n"] else 0,
            "mmr_spread": mmr_spread,
            "cards_seen": len(s["cards"]),
            "consensus_size": len(cons),
            "jaccard_distance": round_opt(jd),
            "has_consensus": bool(cons),
            "tier0_games": t0_games,
            "tier0_wins": s["t0_w"],
            "tier0_wr": round_opt(t0_wr),
            "tier0_wr_wilson_lb": round_opt(t0_wr_lb),
            "player_baseline_games": base_n,
            "player_baseline_wr": round_opt(base_wr),
            "player_baseline_wr_wilson_lb": round_opt(base_wr_lb),
            "delta_vs_self": round_opt(delta_vs_self),
            "deck_avg_wr_others": round_opt(deck_avg_wr),
            "deck_avg_games_others": other_n,
            "delta_vs_deck": round_opt(delta_vs_deck),
            "extra_vs_consensus": sorted(s["cards"] - cons),
            "missing_vs_consensus": sorted(cons - s["cards"]),
            "noise_flags": noise_flags,
            "rogue_score": round(((wr_lb or 0) - 0.5) * ((jd or 1.0)) * games, 2) if wr_lb is not None else 0.0,
        }
        results.append(entry)

    survivor_pairs_with_observed_cards = sum(1 for _, _, s, _, _ in survivors if s["cards"])
    results_with_jaccard = sum(1 for r in results if r["jaccard_distance"] is not None)
    limitations = []
    status = "debug_admin_preview"
    if total_matches and matches_with_any_cards == 0:
        status = "debug_admin_preview_limited_no_decklists"
        limitations.append(
            "matches.cards_a/cards_b are empty for the selected window; consensus-distance buckets cannot populate yet"
        )
    elif results and results_with_jaccard == 0:
        status = "debug_admin_preview_limited_low_decklist_coverage"
        limitations.append(
            "survivors have no usable observed card sets; emerging/solo/off-meta buckets are currently underpowered"
        )

    unusual_color_pairs = sorted(
        [r for r in results if not r["has_consensus"]],
        key=lambda r: -(r["wr_wilson_lb"] or 0),
    )

    clusters = _cluster_archetypes(results, cfg.min_archetype_players, cfg.min_archetype_shared)
    emerging_archetypes = [_build_archetype_entry(deck, members) for deck, members in clusters]
    emerging_archetypes.sort(key=lambda item: (-item["n_players"], -(item["agg_wr_wilson_lb"] or 0)))

    players_in_clusters = {(m["player"], deck) for deck, members in clusters for m in members}
    solo_brews = sorted(
        [
            r for r in results
            if r["has_consensus"]
            and (r["jaccard_distance"] or 0) >= cfg.min_jaccard
            and (r["player"], r["deck"]) not in players_in_clusters
        ],
        key=lambda r: -r["rogue_score"],
    )

    tier0_killers_high_confidence = []
    tier0_killers_noisy = []
    for r in results:
        if r["tier0_games"] < cfg.min_tier0_games:
            continue
        wr_raw = r["tier0_wr"] or 0
        wr_lb = r["tier0_wr_wilson_lb"] or 0
        if wr_raw < cfg.min_tier0_wr:
            continue
        skill_ok = (r["delta_vs_self"] is None) or (r["delta_vs_self"] >= cfg.min_delta_vs_self)
        if wr_lb >= cfg.min_tier0_wr and skill_ok:
            tier0_killers_high_confidence.append(r)
        else:
            tier0_killers_noisy.append(r)
    tier0_killers_high_confidence.sort(key=lambda r: (-(r["tier0_wr_wilson_lb"] or 0), -(r["delta_vs_self"] or 0)))
    tier0_killers_noisy.sort(key=lambda r: (-(r["tier0_wr"] or 0), -r["tier0_games"]))

    tier0_internal = set(tier0_codes)

    def _is_off_meta(item: dict) -> bool:
        return item["deck"] not in tier0_internal

    off_meta_validated = sorted(
        [
            r for r in results
            if _is_off_meta(r)
            and r["has_consensus"]
            and (r["jaccard_distance"] or 0) >= cfg.off_meta_validated_jaccard
            and (r["wr_wilson_lb"] or 0) >= cfg.off_meta_validated_wr_lb
            and r["games"] >= cfg.off_meta_min_games
        ],
        key=lambda r: (-((r["tier0_wr_wilson_lb"] or 0) * (r["jaccard_distance"] or 0)), -(r["wr_wilson_lb"] or 0)),
    )

    off_meta_radar = sorted(
        [
            r for r in results
            if _is_off_meta(r)
            and r["has_consensus"]
            and (r["jaccard_distance"] or 0) >= cfg.off_meta_radar_jaccard
            and (r["wr_wilson_lb"] or 0) >= cfg.off_meta_radar_wr_lb
            and r["games"] >= cfg.off_meta_min_games
        ],
        key=lambda r: (-(r["jaccard_distance"] or 0), -r["games"]),
    )

    return {
        "meta": {
            **asdict(cfg),
            "tier0_codes": tier0_codes,
            "source": "postgresql_port",
            "status": status,
            "confidence_method": "wilson_95_lower_bound",
            "limitations": limitations,
            "data_quality": {
                "leaderboard_mmr_ref_names": len(mmr_ref),
                "leaderboard_mmr_ref_active": bool(mmr_ref),
                "mmr_tolerance_leaderboard": cfg.mmr_tolerance,
                "max_mmr_spread_flag": cfg.max_mmr_spread,
                "mmr_spread_hard_drop": hard_spread_drop,
                "dropped_by_leaderboard_mmr": dropped_by_leaderboard,
                "dropped_by_mmr_spread": dropped_by_spread,
                "matches_with_any_cards": matches_with_any_cards,
                "match_card_coverage_ratio": round_opt(matches_with_any_cards / total_matches) if total_matches else None,
                "survivor_pairs_with_observed_cards": survivor_pairs_with_observed_cards,
                "survivor_observed_card_ratio": round_opt(survivor_pairs_with_observed_cards / len(survivors)) if survivors else None,
                "results_with_jaccard": results_with_jaccard,
                "results_with_jaccard_ratio": round_opt(results_with_jaccard / len(results)) if results else None,
            },
            "total_matches": total_matches,
            "total_pairs": len(player_deck),
            "survivors": len(survivors),
        },
        "preview_candidates": results[:50],
        "emerging_archetypes": emerging_archetypes,
        "solo_brews": solo_brews[:50],
        "off_meta_validated": off_meta_validated[:50],
        "off_meta_radar": off_meta_radar[:50],
        "unusual_color_pairs": unusual_color_pairs[:50],
        "tier0_killers_high_confidence": tier0_killers_high_confidence[:50],
        "tier0_killers_noisy": tier0_killers_noisy[:50],
    }
