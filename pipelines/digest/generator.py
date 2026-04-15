"""Native PG-first digest generator (Sprint P1 — Liberation Day).

Replaces `analisidef/lib/gen_digest.py` as the data source for the killer-curves
prompt builder and the blind-playbook pipeline. Where the legacy generator read
stale `archive_*.json` files off the filesystem, this one starts from rows in
`matches` (PostgreSQL) and rebuilds the same compact digest structure so
downstream consumers can switch over with zero schema change.

Pipeline (per (our_deck, opp_deck, game_format) tuple):

  1. Window. `played_at >= max(current_epoch.started_at, NOW() - window_days)`
     with `current_epoch` looked up from `meta_epochs`. If no epoch row is
     present, only the N-day window applies.
  2. Candidate fetch. Filter `matches` by `(game_format, deck_a/deck_b)` in
     either orientation, restricted to perimeter set `set11/top/pro/friends`.
  3. Game materialisation. For each row we call analisidef's existing
     `loader._parse_turn_events` against the raw log blob stored in
     `matches.turns`, yielding the same per-turn dict that the legacy pipeline
     feeds into `enrich_games`. We then reuse `enrich_games`, `classify_losses`
     and `_build_aggregates` unchanged so the aggregates are identical to the
     filesystem pipeline.
  4. Legality gate. Rows whose cards reference a set outside
     `current_epoch.legal_sets` are dropped before materialisation.
  5. Loss floor. If fewer than `min_games` losses survive the filters we
     return `None` — caller decides whether to skip the matchup entirely.
  6. Compacting. Port of `analisidef/lib/gen_digest.py` lines 55-333 (all 15
     fields). Implementation is copied 1:1 except the input is the freshly
     built archive dict rather than a JSON file.

Public entry point:

    generate_digest(db, our_deck, opp_deck, game_format,
                    window_days=30, min_games=20) -> dict | None

The output dict is ready to `json.dump` into
`App_tool/output/digests/digest_{OUR}_vs_{OPP}[_inf].json`.

Shadow-only contract for P1:
  * no existing reader is modified;
  * the native output lives in a NEW directory so it can coexist with the
    legacy one for at least two weeks before cutover;
  * analisidef is still imported as a library (bridge) — this is the same
    contract as `pipelines/playbook/generator.py`.
"""
from __future__ import annotations

import json
import logging
import re
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Bridge to analisidef — we reuse the existing enrichment pipeline because
# porting ~1200 LOC of loader+investigate is explicitly out of scope for P1.
# ---------------------------------------------------------------------------
_ANALISIDEF_ROOT = Path(
    "/mnt/HC_Volume_104764377/finanza/Lor/Analisi_deck/analisidef"
)
if str(_ANALISIDEF_ROOT) not in sys.path:
    sys.path.insert(0, str(_ANALISIDEF_ROOT))

from lib import loader as _loader  # noqa: E402
from lib.gen_archive import _build_aggregates  # noqa: E402
from lib.investigate import classify_losses, enrich_games  # noqa: E402

# Project-root models/services imports.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.models.match import Match  # noqa: E402
from backend.services.meta_epoch_service import get_current_epoch  # noqa: E402

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Deck code conversions.
#
# App_tool PG uses canonical codes (`AmSa`, `EmSa`), while analisidef's
# DECK_COLORS table predates that rename and still uses `AS`, `ES`. The two
# codes describe identical color pairs — we bridge transparently so callers
# can pass either form.
# ---------------------------------------------------------------------------
PG_TO_LEGACY = {"AmSa": "AS", "EmSa": "ES"}
LEGACY_TO_PG = {v: k for k, v in PG_TO_LEGACY.items()}

# Perimeters we treat as "competitive core" — matches outside this set are
# noise for digest purposes (RUSH, SEALED, QP, ...).
PERIMETERS = {"set11", "top", "pro", "friends"}

# Mirror of `run_kc_production.DECKS`, the canonical matchup list, translated
# into App_tool (PG-canonical) deck codes.
DECKS = ["AmAm", "AmSa", "EmSa", "AbE", "AbS", "AbR", "AbSt",
         "AmySt", "SSt", "AmyE", "AmyR", "RS"]

# ---------------------------------------------------------------------------
# Cards DB + legality index — loaded lazily, cached per-process.
# ---------------------------------------------------------------------------
_CARDS_DB_CACHE: dict | None = None
_LEGAL_CARD_NAMES_BY_EPOCH: dict[tuple[int, ...], set[str]] = {}


def _load_cards_db() -> dict:
    global _CARDS_DB_CACHE
    if _CARDS_DB_CACHE is None:
        _CARDS_DB_CACHE = _loader.load_cards_db()
    return _CARDS_DB_CACHE


def _legal_card_names(legal_sets: Iterable[int]) -> set[str]:
    """Return the set of card names legal for a given list of set numbers.

    Cards whose ``set`` field (numeric) is NOT in ``legal_sets`` are excluded.
    Unknown or missing set numbers are kept as legal (fail-open) so we don't
    drop promo/enchanted printings that lack a clean set tag.
    """
    key = tuple(sorted(set(int(s) for s in legal_sets)))
    if key in _LEGAL_CARD_NAMES_BY_EPOCH:
        return _LEGAL_CARD_NAMES_BY_EPOCH[key]

    db = _load_cards_db()
    legal: set[str] = set()
    allowed = set(key)
    for name, entry in db.items():
        if not isinstance(entry, dict):
            continue
        set_num = entry.get("set")
        try:
            set_int = int(set_num) if set_num is not None else None
        except (TypeError, ValueError):
            set_int = None
        if set_int is None or set_int in allowed:
            legal.add(name)
    _LEGAL_CARD_NAMES_BY_EPOCH[key] = legal
    return legal


# ---------------------------------------------------------------------------
# Match materialisation
# ---------------------------------------------------------------------------
_CARD_EVENT_TYPES = {
    "CARD_PLAYED", "CARD_INKED", "CARD_DRAWN", "CARD_QUEST",
    "CARD_ATTACK", "INITIAL_HAND", "MULLIGAN",
    "CARD_REVEALED", "CARD_DISCARDED", "CARD_BOUNCED",
    "CARD_PUT_INTO_INKWELL", "CARD_BOOSTED",
}


def _match_uses_only_legal_cards(logs: list[dict], legal: set[str] | None) -> bool:
    """Return False if any event references a card outside ``legal``.

    ``legal`` = None disables the check (returns True).
    """
    if not legal:
        return True
    for ev in logs or ():
        if not isinstance(ev, dict):
            continue
        if ev.get("type") not in _CARD_EVENT_TYPES:
            continue
        for ref in ev.get("cardRefs", []) or ():
            if not isinstance(ref, dict):
                continue
            name = ref.get("name")
            if name and name not in legal:
                # The card is in the log but not in our legal-set index —
                # treat as illegal (conservative, matches Sprint-0 gate).
                return False
    return True


def _materialise_game(
    match: Match,
    our_is_a: bool,
) -> dict | None:
    """Build the per-game dict enrich_games() expects, using PG row + logs.

    Returns None when the match can't be parsed (missing logs, unknown winner,
    etc.) so callers can skip it without aborting the whole batch.
    """
    logs = match.turns
    if not isinstance(logs, list) or not logs:
        return None

    our_p = 1 if our_is_a else 2
    opp_p = 2 if our_is_a else 1

    turns, actual_max = _loader._parse_turn_events(logs, our_p, opp_p)
    if actual_max == 0:
        return None

    # Ensure all 1..actual_max keys exist (mirror loader.load_matches).
    for tn in range(1, actual_max + 1):
        if tn not in turns:
            turns[tn] = _loader._new_turn()

    # Winner direct from PG — avoids re-scanning logs.
    if match.winner == "deck_a":
        winner_p = 1
    elif match.winner == "deck_b":
        winner_p = 2
    else:
        # Fallback: scan logs (rare path for pre-import rows with NULL winner).
        winner_p = _loader._find_winner(logs)
        if winner_p not in (1, 2):
            return None

    # OTP: first TURN_START.
    we_otp = None
    for ev in logs:
        if ev.get("type") == "TURN_START" and ev.get("turnNumber") == 1:
            fp = ev.get("player")
            if fp is not None:
                we_otp = int(fp) == our_p
            break

    # Hand reveals (used by some downstream but not by digest aggregates).
    try:
        hand = _loader._parse_hand(logs, our_p)
    except Exception:
        hand = {}

    our_name = match.player_a_name if our_is_a else match.player_b_name
    opp_name = match.player_b_name if our_is_a else match.player_a_name
    our_mmr = match.player_a_mmr if our_is_a else match.player_b_mmr
    opp_mmr = match.player_b_mmr if our_is_a else match.player_a_mmr

    return {
        "we_won": winner_p == our_p,
        "length": actual_max,
        "turns": turns,
        "we_otp": we_otp,
        "hand": hand,
        "our_name": our_name or "?",
        "opp_name": opp_name or "?",
        "our_mmr": int(our_mmr or 0),
        "opp_mmr": int(opp_mmr or 0),
        # File path is used only for `date` aggregation in metadata. Fabricate
        # a path that still yields a date folder when split on '/'.
        "file": (
            f"pg/{match.played_at.strftime('%Y-%m-%d')}/PG/{match.external_id or match.id}"
        ),
        "game_format": match.game_format,
    }


def _fetch_matches(
    db: Session,
    our_deck_pg: str,
    opp_deck_pg: str,
    game_format: str,
    since: datetime,
) -> list[tuple[Match, bool]]:
    """Return (match_row, our_is_a) tuples, losses first (legacy parity).

    `our_is_a = True` when our deck appeared as ``deck_a`` in the row; this is
    what :func:`_materialise_game` needs to map ``player_a_*`` to our side.
    """
    q = (
        select(Match)
        .where(
            Match.game_format == game_format,
            Match.perimeter.in_(PERIMETERS),
            Match.played_at >= since,
            or_(
                (Match.deck_a == our_deck_pg) & (Match.deck_b == opp_deck_pg),
                (Match.deck_a == opp_deck_pg) & (Match.deck_b == our_deck_pg),
            ),
        )
        .order_by(Match.played_at.asc())
    )
    rows: list[tuple[Match, bool]] = []
    for m in db.execute(q).scalars():
        if m.deck_a == our_deck_pg and m.deck_b == opp_deck_pg:
            rows.append((m, True))
        elif m.deck_b == our_deck_pg and m.deck_a == opp_deck_pg:
            rows.append((m, False))
    return rows


# ---------------------------------------------------------------------------
# COMPACTING LOGIC — ported verbatim from analisidef/lib/gen_digest.py 55-333
# ---------------------------------------------------------------------------

TOP_CARDS_CAP = 12
NON_CHARACTER_MIN_PCT = 15


def _build_top_cards(top_cards_raw: dict, bucket_count: int, db: dict) -> dict:
    """Top 12 by frequency + any non-character >= NON_CHARACTER_MIN_PCT."""
    sorted_all = sorted(top_cards_raw.items(), key=lambda x: -x[1])
    result = dict(sorted_all[:TOP_CARDS_CAP])
    if bucket_count > 0:
        threshold = bucket_count * NON_CHARACTER_MIN_PCT / 100
        for name, count in sorted_all[TOP_CARDS_CAP:]:
            if count < threshold:
                break
            card = db.get(name, {})
            card_type = (card.get("type", "") or "").lower()
            if "character" not in card_type:
                result[name] = count
    return result


def _compact_archive(arch: dict, db: dict) -> dict:
    """Port of analisidef/lib/gen_digest.py:generate_digest minus disk I/O."""
    meta = arch["metadata"]
    agg = arch["aggregates"]
    lp = agg.get("loss_profiles", {})
    ls = agg.get("lore_speed", {})
    games_by_id = {g["id"]: g for g in arch["games"]}

    # --- 1. Aggregati chiave (compatti) ---
    summary = {
        "matchup": f"{meta['our_deck']} vs {meta['opp_deck']}",
        "games": meta["total_games"],
        "wins": meta["wins"],
        "losses": meta["losses"],
        "format": meta.get("game_format", "core"),
        "component_primary": agg["component_primary"],
        "critical_turn_dist": agg["critical_turn_distribution"],
        "avg_trend": {
            k: [round(v, 1) for v in vals[:7]]
            for k, vals in agg["avg_trend_components"].items()
            if k in ("board", "lore", "lore_pot", "removal", "opp_lore_vel")
        },
        "alert_losses": agg["alert_summary"]["losses_per_type"],
        "lore_speed": {
            "reach_10": ls.get("reach_10", {}),
            "reach_15": ls.get("reach_15", {}),
            "fast_loss_ids": ls.get("fast_loss_ids", []),
            "top_burst": ls.get("lore_burst", [])[:3],
        },
        "card_examples": {
            name: {"count": d["count"], "avg_crit_turn": d.get("avg_critical_turn")}
            for name, d in sorted(
                agg.get("card_examples", {}).items(),
                key=lambda x: -x[1].get("count", 0),
            )[:10]
        },
        "combos": [
            {"cards": c["cards"], "count": c["count"], "turn": c.get("avg_turn")}
            for c in agg.get("combos_at_critical_turn", [])[:5]
        ],
    }

    # --- 2. Loss profiles compatti ---
    profiles: dict = {}
    for bucket_name in ("fast", "typical", "slow"):
        p = lp.get(bucket_name)
        if not p:
            continue
        top_kw = dict(
            sorted(p.get("keywords", {}).items(), key=lambda x: -x[1])[:8]
        )
        top_ab = dict(
            sorted(p.get("abilities", {}).items(), key=lambda x: -x[1])[:10]
        )
        profiles[bucket_name] = {
            "count": p["count"],
            "pct": p["pct"],
            "causes": p["causes"],
            "component": p["component_primary"],
            "alerts": p["alert_types"],
            "patterns": p["mechanics"],
            "patterns_cards": p.get("mechanics_cards", {}),
            "keywords": top_kw,
            "keywords_cards": {
                kw: cards
                for kw, cards in p.get("keywords_cards", {}).items()
                if kw in top_kw
            },
            "abilities": top_ab,
            "abilities_cards": {
                key: cards
                for key, cards in p.get("abilities_cards", {}).items()
                if key in top_ab
            },
            "wipe_rate": p["wipe_rate"],
            "lore_t4": p["lore_t4"],
            "top_cards": _build_top_cards(p["top_cards"], p["count"], db),
            "example_ids": p["example_game_ids"],
        }
    summary["profiles"] = profiles

    # --- 3. Example games compattate ---
    all_example_ids: set = set()
    for p in lp.values():
        all_example_ids.update(p.get("example_game_ids", [])[:6])
    all_example_ids.update(ls.get("fast_loss_ids", [])[:3])

    compact_games = []
    for gid in sorted(all_example_ids):
        g = games_by_id.get(gid)
        if not g or g["result"] not in ("L", "loss"):
            continue

        a = g.get("analysis", {})
        lspd = a.get("lore_speed", {})

        in_profiles = []
        for bname, bdata in lp.items():
            if gid in bdata.get("example_game_ids", []):
                in_profiles.append(bname)
        if gid in ls.get("fast_loss_ids", []):
            in_profiles.append("fast_loss")

        turns_compact = []
        cum_opp_lore = 0
        for t in g["turns"]:
            tn = t["t"]
            opp_plays = [
                (
                    p["name"],
                    p.get("ink_paid", 0),
                    p.get("is_shift", False),
                    p.get("is_sung", False),
                )
                for p in t.get("opp_plays", [])
            ]
            opp_lore = sum(q.get("lore", 0) for q in t.get("opp_quests", []))
            opp_dead = t.get("opp_dead", [])
            our_dead = t.get("our_dead", [])
            our_bounced = t.get("our_bounced", [])
            cum_opp_lore += opp_lore

            inkwell_data = t.get("inkwell", {})
            opp_inkwell = (
                inkwell_data.get("opp") if isinstance(inkwell_data, dict) else None
            )
            opp_ink_spent = None
            ink_spent_data = t.get("ink_spent", {})
            if isinstance(ink_spent_data, dict):
                opp_ink_spent = ink_spent_data.get("opp")

            key_abs = []
            for ab in t.get("opp_abilities", []):
                eff = ab.get("effect", "")
                if any(
                    kw in eff for kw in ("from discard", "plays", "Returned", "return")
                ):
                    key_abs.append(f"{ab['card']}: {eff[:35]}")

            if tn > 8:
                continue
            if not opp_plays and not opp_lore and not opp_dead and not our_dead:
                continue

            parts = []
            if opp_inkwell is not None:
                if opp_ink_spent is not None:
                    parts.append(f"[ink={opp_inkwell}/{opp_ink_spent}]")
                else:
                    parts.append(f"[ink={opp_inkwell}]")
            if opp_plays:
                play_strs = []
                for n, ink, is_shift, is_sung in opp_plays:
                    tag = ""
                    if is_shift:
                        tag = "S"
                    elif is_sung:
                        tag = "\u266a"
                    play_strs.append(f"{n}({ink}{tag})")
                parts.append("+".join(play_strs))
            if opp_lore:
                parts.append(f"\u2192{cum_opp_lore}L(+{opp_lore})")
            if opp_dead:
                parts.append(f"Odead:{','.join(opp_dead[:2])}")
            if our_dead:
                parts.append(f"Udead:{','.join(our_dead[:2])}")
            if our_bounced:
                parts.append(f"Ubounce:{','.join(our_bounced[:2])}")
            if key_abs:
                parts.append(f"ab:{';'.join(key_abs[:2])}")

            turn_str = f"T{tn}: {' | '.join(parts)}"
            turns_compact.append(turn_str)

        crits_str = ",".join(
            f"T{c['turn']}{c['component'][0]}({c['swing']})"
            for c in a.get("criticals", [])
        )

        header = (
            f"G{gid} [{','.join(in_profiles)}] len={g['length']} "
            f"r15={lspd.get('opp_reach_15', '?')} "
            f"burst={lspd.get('best_lore_burst', 0)}@T{lspd.get('best_lore_burst_turn', '?')} "
            f"crits={crits_str}"
        )

        compact_games.append({"header": header, "turns": turns_compact})

    summary["example_games"] = compact_games

    # --- 4. Cards DB per TUTTE le carte rilevanti ---
    all_cards: set = set(summary["card_examples"].keys())
    for p in profiles.values():
        all_cards.update(p.get("top_cards", {}).keys())
        # NOTE: legacy gen_digest.py reads p.get('mechanics_cards') here, but
        # the output dict was renamed to 'patterns_cards' two lines earlier.
        # Preserve the same lookup key to keep bug-for-bug parity with legacy.
        for flag_cards in p.get("mechanics_cards", {}).values():
            all_cards.update(flag_cards.keys())
    for eg in compact_games:
        for turn_str in eg.get("turns", []):
            for m in re.findall(r"([A-Za-z][^(+|]+)\(", turn_str):
                card_name = m.strip()
                if card_name in db:
                    all_cards.add(card_name)
    for combo in agg.get("combos_at_critical_turn", [])[:5]:
        for card_name in combo.get("cards", []):
            if card_name in db:
                all_cards.add(card_name)

    cards_lookup: dict = {}
    for name in sorted(all_cards):
        if name not in db:
            continue
        c = db[name]
        cost = c.get("cost", 0)
        if isinstance(cost, str):
            cost = int(cost) if cost.isdigit() else 0
        ink_raw = c.get("ink", "")
        entry = {"cost": cost, "ink": ink_raw, "type": c.get("type", "")}
        if "/" in ink_raw:
            entry["colors"] = [col.strip() for col in ink_raw.split("/")]
            entry["dual_ink"] = True
        s = c.get("str") or c.get("strength")
        w = c.get("will") or c.get("willpower")
        if s and w:
            entry["str"] = int(s) if isinstance(s, str) and s.isdigit() else s
            entry["will"] = int(w) if isinstance(w, str) and w.isdigit() else w
        lore = c.get("lore")
        if lore:
            entry["lore"] = int(lore) if isinstance(lore, str) and lore.isdigit() else lore
        ability = c.get("ability", "") or ""
        if ability:
            entry["ability"] = ability
        ab_lower = ability.lower()
        shift_match = re.search(r"\bshift\s+(\d+)", ab_lower)
        if shift_match:
            entry["shift_cost"] = int(shift_match.group(1))
        singer_match = re.search(r"\bsinger\s+(\d+)", ab_lower)
        if singer_match:
            entry["singer_cost"] = int(singer_match.group(1))
        if "song" in (c.get("type", "") or "").lower():
            entry["is_song"] = True
        kw = []
        for keyword in (
            "Bodyguard", "Challenger", "Evasive", "Reckless",
            "Resist", "Rush", "Support", "Ward", "Vanish",
        ):
            if re.search(r"\b" + keyword + r"\b", ability, re.I):
                kw.append(keyword)
        if kw:
            entry["keywords"] = kw
        cards_lookup[name] = entry

    summary["cards_db"] = cards_lookup

    return summary


# ---------------------------------------------------------------------------
# Archive assembly (pre-compact step)
# ---------------------------------------------------------------------------

def _build_archive(
    our_deck_pg: str,
    opp_deck_pg: str,
    game_format: str,
    games: list[dict],
    loss_classes: list[dict],
    db: dict,
) -> dict:
    """Assemble the legacy archive dict from enriched games + loss classes.

    Mirrors `analisidef/lib/gen_archive.py:generate_archive` but without any
    file I/O. Uses the canonical deck codes as both short and long names so
    downstream readers see App_tool-canonical strings.
    """
    # Per-game entry (mirror gen_archive._build_game).
    loss_by_idx = {lc["game_idx"]: lc for lc in loss_classes}
    games_out = []
    for idx, g in enumerate(games):
        la = loss_by_idx.get(idx)
        entry = {
            "id": idx,
            "file": g.get("file", "").split("/")[-1],
            "date": g.get("file", "").split("/")[-3] if g.get("file") else "",
            "result": "W" if g["we_won"] else "L",
            "we_otp": g.get("we_otp"),
            "our_name": g.get("our_name", "?"),
            "opp_name": g.get("opp_name", "?"),
            "our_mmr": g.get("our_mmr", 0),
            "opp_mmr": g.get("opp_mmr", 0),
            "length": g["length"],
            "turns": [],
        }
        # Build per-turn entries the same way gen_archive._build_turn does;
        # we reuse the function for pixel parity.
        from lib.gen_archive import _build_turn as _ga_build_turn  # noqa: E402
        for t in range(1, min(g["length"] + 1, 13)):
            entry["turns"].append(_ga_build_turn(g, t))
        if la:
            entry["analysis"] = {
                "criticals": la["criticals"],
                "causes": la["causes"],
                "cards": la["cards"],
                "detail": la["detail"],
                "trend_components": la["trend_components"],
                "trend_total": la["trend"],
                "lore_speed": la.get("lore_speed", {}),
                "alerts": la.get("alerts", []),
            }
        games_out.append(entry)

    # Metadata — no file-folder derivation, we use played_at.
    dates: Counter = Counter()
    for g in games:
        date_folder = g.get("file", "").split("/")[-3] if g.get("file") else "unknown"
        dates[date_folder] += 1

    metadata = {
        "our_deck": our_deck_pg,
        "opp_deck": opp_deck_pg,
        "our_long": our_deck_pg,
        "opp_long": opp_deck_pg,
        "game_format": game_format,
        "last_updated": date.today().strftime("%Y-%m-%d"),
        "total_games": len(games),
        "wins": sum(1 for g in games if g["we_won"]),
        "losses": sum(1 for g in games if not g["we_won"]),
        "games_by_date": dict(sorted(dates.items())),
    }

    aggregates = _build_aggregates(games, loss_classes, db=db)
    return {"metadata": metadata, "games": games_out, "aggregates": aggregates}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_digest(
    db: Session,
    our_deck: str,
    opp_deck: str,
    game_format: str,
    window_days: int = 30,
    min_games: int = 20,
) -> dict | None:
    """Produce the compact digest for a single (our, opp, format) tuple.

    Parameters
    ----------
    db: live SQLAlchemy session against App_tool's PG.
    our_deck, opp_deck: either canonical (`AmSa`) or legacy (`AS`) codes;
        both are accepted and normalised internally.
    game_format: 'core' or 'infinity'.
    window_days: lookback floor (intersected with epoch.started_at).
    min_games: minimum LOSS count — below this we return None.

    Returns
    -------
    dict with the 15 top-level digest fields, or None if the matchup is below
    the loss floor (caller should skip it in the batch runner).
    """
    # Normalise deck codes: accept both canonical PG ('AmSa', 'EmSa') and
    # legacy analisidef ('AS', 'ES') forms. PG queries use the canonical
    # form (matches import_matches); metadata/output uses the canonical form.
    our_pg = LEGACY_TO_PG.get(our_deck, our_deck)
    opp_pg = LEGACY_TO_PG.get(opp_deck, opp_deck)

    # --- 1. Epoch bounds ---
    epoch = get_current_epoch(db)
    now = datetime.now(timezone.utc)
    window_floor = now - timedelta(days=window_days)
    if epoch is not None:
        epoch_start = datetime.combine(
            epoch.started_at, datetime.min.time(), tzinfo=timezone.utc
        )
        since = max(window_floor, epoch_start)
        legal_names = _legal_card_names(epoch.legal_sets)
    else:
        since = window_floor
        legal_names = None

    # --- 2. Fetch candidate rows ---
    rows = _fetch_matches(db, our_pg, opp_pg, game_format, since)

    if not rows:
        logger.info(
            "[DIGEST] our=%s opp=%s fmt=%s no matches since %s",
            our_deck, opp_deck, game_format, since.isoformat(),
        )
        return None

    # --- 3. Materialise games + apply legality gate ---
    # Seed the loader's module-level name-normaliser (required by _parse_turn_events).
    cards_db = _load_cards_db()
    _loader._normalize_name = _loader._build_name_normalizer(cards_db)

    games: list[dict] = []
    dropped_illegal = 0
    dropped_unparseable = 0
    for match, our_is_a in rows:
        if not _match_uses_only_legal_cards(match.turns, legal_names):
            dropped_illegal += 1
            continue
        g = _materialise_game(match, our_is_a)
        if g is None:
            dropped_unparseable += 1
            continue
        games.append(g)

    losses = sum(1 for g in games if not g["we_won"])
    if losses < min_games:
        logger.info(
            "[DIGEST] our=%s opp=%s fmt=%s below floor (losses=%d < %d)",
            our_deck, opp_deck, game_format, losses, min_games,
        )
        return None

    # --- 4. Run enrichment + aggregation pipeline (reused from analisidef) ---
    db_ext, ability_cost_map, _id_map = _loader.load_cards_db_extended()
    enrich_games(games, db_ext, ability_cost_map)
    loss_classes = classify_losses(games, db=db_ext)

    # Use canonical PG codes in the metadata so downstream readers see the
    # App_tool-native form.
    archive = _build_archive(
        our_pg, opp_pg, game_format, games, loss_classes, db_ext
    )

    # --- 5. Compact to digest schema ---
    digest = _compact_archive(archive, cards_db)

    # Provenance tag — NOT in legacy schema (extra field). We keep it separate
    # so diff_digests.py can ignore it, and flag it explicitly.
    digest["_provenance"] = {
        "source": "pg_native_p1",
        "window_days": window_days,
        "since": since.isoformat(),
        "epoch_id": epoch.id if epoch else None,
        "epoch_name": epoch.name if epoch else None,
        "dropped_illegal": dropped_illegal,
        "dropped_unparseable": dropped_unparseable,
        "generated_at": now.isoformat(),
    }
    return digest


__all__ = ["generate_digest", "DECKS"]
