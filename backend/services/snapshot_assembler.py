"""
Snapshot assembler — builds the full dashboard blob from PostgreSQL.

Replaces the dependency on daily_routine.py's dashboard_data.json.
Each section mirrors the exact structure the frontend expects.
"""
import json
import logging
import os
from datetime import date, datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.services import kc_spy_service, static_data_service
from backend.services.leaderboard_service import fetch_leaderboards

logger = logging.getLogger(__name__)

# Friends list (same as analisidef)
FRIENDS = {'macs', 'sbot', 'harry_pelat', 'tol_vibes', 'tol_barox', 'tol_papavale', 'tol_giorgio'}
FRIENDS_PREFIXES = ('tol_',)

# Default "core" perimeter advertised to the frontend. Flip via env at set
# rotation (Set 12 launch → APPTOOL_DEFAULT_CORE_PERIMETER=set12) so no code
# change is needed on release day. The frontend reads DATA.default_core_perimeter
# with a literal 'set11' fallback.
DEFAULT_CORE_PERIMETER = os.environ.get("APPTOOL_DEFAULT_CORE_PERIMETER", "set11").strip() or "set11"

# Perimeter config: blob_key → (db_perimeters, db_game_format, label, min_elo, player_filter)
# db_perimeters can be a list (match must be in ANY of the listed perimeters)
# player_filter: None, "friends", "top", "pro" — virtual filter on player names
PERIMETER_CONFIG = {
    "set11":            (["set11"],           "core",     "SET11 High ELO (≥1300)", 1300, None),
    "top":              (["top", "pro"],      "core",     "TOP", None, None),
    "pro":              (["pro"],             "core",     "PRO", None, None),
    "friends_core":     ([DEFAULT_CORE_PERIMETER, "top", "pro"], "core", "Friends (Core)", None, "friends"),
    "infinity":         (["inf"],             "infinity", "Infinity", None, None),
    "infinity_top":     (["inf", "top", "pro"], "infinity", "Infinity TOP", None, "top"),
    "infinity_pro":     (["inf", "top", "pro"], "infinity", "Infinity PRO", None, "pro"),
    "infinity_friends": (["inf", "top", "pro"], "infinity", "Friends (Infinity)", None, "friends"),
}
# Ensure the active default-core blob key exists in PERIMETER_CONFIG so that
# downstream consumers (and the frontend fallback) always have an entry to
# resolve. When env flips to a new set (e.g. 'set12'), the config is cloned
# from the legacy 'set11' entry with the new db_perimeter.
if DEFAULT_CORE_PERIMETER not in PERIMETER_CONFIG:
    _legacy = PERIMETER_CONFIG["set11"]
    PERIMETER_CONFIG[DEFAULT_CORE_PERIMETER] = (
        [DEFAULT_CORE_PERIMETER], _legacy[1],
        f"{DEFAULT_CORE_PERIMETER.upper()} High ELO (≥1300)",
        _legacy[3], _legacy[4],
    )

DAYS = 3  # default analysis window


def assemble(db: Session, days: int = DAYS) -> dict:
    """Assemble the full dashboard blob from PG. Returns dict matching frontend DATA shape."""
    logger.info("Assembling dashboard snapshot (days=%d)...", days)

    blob = {}
    blob["default_core_perimeter"] = DEFAULT_CORE_PERIMETER
    blob["meta"] = _build_meta(db, days)
    blob["perimeters"] = _build_perimeters(db, days)
    blob["leaderboards"] = _build_leaderboards()
    blob["pro_players"] = _build_pro_players(db, days)
    blob["consensus"] = static_data_service.get_consensus(db)
    blob["reference_decklists"] = static_data_service.get_reference_decklists(db)
    blob["player_cards"] = _build_player_cards(db, "core", days)
    blob["player_cards_infinity"] = _build_player_cards(db, "infinity", days)
    blob["tech_tornado"] = _build_tech_tornado(db, days)
    blob["matchup_trend"] = _build_matchup_trend(db, days=7)
    blob["matchup_analyzer"] = _build_matchup_analyzer(db, "core")
    blob["matchup_analyzer_infinity"] = _build_matchup_analyzer(db, "infinity")
    blob["card_images"] = static_data_service.get_card_images(db)
    blob["card_types"] = static_data_service.get_card_types(db)
    blob["card_inks"] = static_data_service.get_card_inks(db)
    blob["meta_deck"] = _build_meta_deck(db, "core")
    blob["meta_deck_infinity"] = _build_meta_deck(db, "infinity")
    blob["best_plays"] = {}  # complex replay analysis — populated if matchup_reports has them
    blob["best_plays_infinity"] = {}
    blob["team"] = _build_team(db, days)
    blob["player_lookup"] = _build_player_lookup(db, days)
    blob["kc_spy"] = _load_kc_spy(db)
    blob["emerging_decks"] = _build_emerging_decks(db)

    logger.info("Snapshot assembled: %d top-level keys", len(blob))
    return blob


# ---------------------------------------------------------------------------
# KC SPY
# ---------------------------------------------------------------------------

def _load_kc_spy(db: Session) -> dict:
    """Load KC spy report from PostgreSQL."""
    try:
        return kc_spy_service.get_latest_report(db)
    except Exception as e:
        logger.warning("Could not load kc_spy report from PG: %s", e)
    return {}


# ---------------------------------------------------------------------------
# META
# ---------------------------------------------------------------------------

def _build_meta(db: Session, days: int) -> dict:
    """Game counts per perimeter + period label."""
    rows = db.execute(text("""
        SELECT perimeter, game_format, count(*) AS cnt
        FROM matches
        WHERE played_at >= now() - make_interval(days => :days)
        GROUP BY perimeter, game_format
    """), {"days": days}).fetchall()

    games = {}
    total = 0
    for r in rows:
        key = _db_to_blob_perimeter(r.perimeter, r.game_format)
        if key:
            games[key] = r.cnt
            total += r.cnt

    games["total"] = total

    today = date.today()
    start = date.today().fromordinal(today.toordinal() - (days - 1))

    return {
        "updated": datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M"),
        "period": f"Last {days} days",
        "period_range": f"{start.strftime('%d/%m')} – {today.strftime('%d/%m')}",
        "games": games,
    }


def build_slice(db: Session, blob_key: str, days: int, queue_filter: str | None) -> dict:
    """Compute {matrix, otp_otd} for a blob perimeter key, optionally restricted
    to a queue format (bo1/bo3). Reuses PERIMETER_CONFIG + _build_player_filter_sql
    so filter semantics stay identical to the full blob (otherwise "top" would
    accidentally drop the pro-folder matches, etc.).
    """
    cfg = PERIMETER_CONFIG.get(blob_key)
    if not cfg:
        return {"matrix": {}, "otp_otd": {}}
    db_perims, db_fmt, _label, min_elo, player_filter = cfg
    lb_names = _get_leaderboard_names(db)
    pf_sql, pf_names = _build_player_filter_sql(player_filter, lb_names)

    params: dict = {"perims": db_perims, "fmt": db_fmt, "days": days}
    elo_filter = ""
    if min_elo:
        elo_filter = "AND player_a_mmr >= :min_elo"
        params["min_elo"] = min_elo
    if pf_names:
        params["pf_names"] = pf_names

    queue_clause = ""
    if queue_filter == "bo3":
        queue_clause = "AND queue_name LIKE '%-BO3'"
    elif queue_filter == "bo1":
        queue_clause = "AND queue_name LIKE '%-BO1'"

    base_where = f"""
        perimeter = ANY(:perims) AND game_format = :fmt
        AND played_at >= now() - make_interval(days => :days)
        {elo_filter}
        {pf_sql}
        {queue_clause}
    """

    mx_rows = db.execute(text(f"""
        SELECT deck_a, deck_b, count(*) AS games,
               count(*) FILTER (WHERE winner = 'deck_a') AS wins
        FROM matches WHERE {base_where}
        GROUP BY deck_a, deck_b
    """), params).fetchall()
    matrix: dict = {}
    for r in mx_rows:
        matrix.setdefault(r.deck_a, {})[r.deck_b] = {"w": r.wins, "t": r.games}

    otp_rows = db.execute(text(f"""
        SELECT deck_a, deck_b, count(*) AS games,
               count(*) FILTER (WHERE winner = 'deck_a') AS otp_w,
               count(*) FILTER (WHERE winner = 'deck_b') AS otd_w
        FROM matches WHERE {base_where}
        GROUP BY deck_a, deck_b
    """), params).fetchall()
    otp_otd: dict = {}
    for r in otp_rows:
        otp_otd.setdefault(r.deck_a, {})[r.deck_b] = {
            "otp_w": r.otp_w, "otp_t": r.games,
            "otd_w": r.otd_w, "otd_t": r.games,
        }
    return {"matrix": matrix, "otp_otd": otp_otd}


def _db_to_blob_perimeter(db_perim: str, db_format: str) -> str | None:
    """Map DB (perimeter, game_format) → blob key (first non-virtual match)."""
    for blob_key, (perims, fmt, _, _, pf) in PERIMETER_CONFIG.items():
        if pf is None and db_perim in perims and fmt == db_format:
            return blob_key
    return None


# ---------------------------------------------------------------------------
# PERIMETERS
# ---------------------------------------------------------------------------

def _get_leaderboard_names(db: Session) -> dict:
    """Fetch TOP/PRO player names from leaderboard_service (cached).

    Uses the pre-computed core_top/core_pro/inf_top/inf_pro sets from the
    service (which respect TOP_N/PRO_N constants).
    """
    try:
        lb = fetch_leaderboards()
        top_names = set(lb.get("core_top", set())) | set(lb.get("inf_top", set()))
        pro_names = set(lb.get("core_pro", set())) | set(lb.get("inf_pro", set()))
        return {"top": top_names, "pro": pro_names}
    except Exception as e:
        logger.warning("Leaderboard names fetch failed: %s", e)
        return {"top": set(), "pro": set()}


def _build_player_filter_sql(player_filter: str | None, lb_names: dict) -> tuple[str, list]:
    """Return (SQL fragment, name list) for virtual perimeter player filtering."""
    if not player_filter:
        return "", []

    if player_filter == "friends":
        names = list(FRIENDS)
        # SQL: player name in friends list OR starts with prefix
        prefix_clauses = " OR ".join(
            f"lower(player_a_name) LIKE '{p}%' OR lower(player_b_name) LIKE '{p}%'"
            for p in FRIENDS_PREFIXES
        )
        return f"AND (lower(player_a_name) = ANY(:pf_names) OR lower(player_b_name) = ANY(:pf_names) OR {prefix_clauses})", names

    if player_filter in ("top", "pro"):
        names = list(lb_names.get(player_filter, set()))
        if not names:
            return "AND FALSE", []  # no leaderboard data → no results
        return "AND (lower(player_a_name) = ANY(:pf_names) OR lower(player_b_name) = ANY(:pf_names))", names

    return "", []


def _build_perimeters(db: Session, days: int) -> dict:
    """Build wr, matrix, otp_otd, trend, meta_share, top_players, elo_dist per perimeter."""
    lb_names = _get_leaderboard_names(db)
    result = {}
    for blob_key, (db_perims, db_fmt, label, min_elo, player_filter) in PERIMETER_CONFIG.items():
        pf_sql, pf_names = _build_player_filter_sql(player_filter, lb_names)
        # For top/pro perimeters, restrict top_players list to leaderboard names only
        tp_filter = None
        if blob_key in ("top", "infinity_top"):
            names = lb_names.get("top", set())
            tp_filter = names or None
        elif blob_key in ("pro", "infinity_pro"):
            names = lb_names.get("pro", set())
            tp_filter = names or None
        perim_data = _build_single_perimeter(db, db_perims, db_fmt, label, min_elo, days,
                                              player_filter_sql=pf_sql, player_filter_names=pf_names,
                                              top_players_filter=tp_filter)
        if perim_data:
            result[blob_key] = perim_data

    # Community aggregate (all core perimeters combined)
    community = _build_community(db, days)
    if community:
        result["community"] = community

    return result


def _build_single_perimeter(db: Session, db_perims: list[str], db_fmt: str,
                             label: str, min_elo: int | None, days: int,
                             player_filter_sql: str = "",
                             player_filter_names: list | None = None,
                             top_players_filter: set | None = None) -> dict | None:
    """Build stats for one perimeter.

    Every match has two sides (deck_a / deck_b).  We unfold each match into
    two rows so that every deck is counted regardless of which side it sits on.
    The CTE ``sides`` does the unfolding; all downstream queries build on it.
    """
    params = {"perims": db_perims, "fmt": db_fmt, "days": days}
    elo_filter = ""
    if min_elo:
        elo_filter = "AND player_a_mmr >= :min_elo"
        params["min_elo"] = min_elo
    if player_filter_names is not None:
        params["pf_names"] = player_filter_names

    # ---------- base filter (used by all queries) ----------
    base_where = f"""
        perimeter = ANY(:perims) AND game_format = :fmt
        AND played_at >= now() - make_interval(days => :days)
        {elo_filter}
        {player_filter_sql}
    """

    # ---------- WR per deck (both sides) ----------
    rows = db.execute(text(f"""
        WITH sides AS (
            SELECT deck_a AS deck, CASE WHEN winner = 'deck_a' THEN 1 ELSE 0 END AS win
            FROM matches WHERE {base_where}
            UNION ALL
            SELECT deck_b AS deck, CASE WHEN winner = 'deck_b' THEN 1 ELSE 0 END AS win
            FROM matches WHERE {base_where}
        )
        SELECT deck, count(*) AS games, sum(win) AS w
        FROM sides GROUP BY deck HAVING count(*) >= 5
        ORDER BY games DESC
    """), params).fetchall()

    if not rows:
        return None

    wr = {}
    total_games = sum(r.games for r in rows)
    for r in rows:
        wr[r.deck] = {"w": r.w, "l": r.games - r.w, "games": r.games,
                       "wr": round(r.w / r.games * 100, 2) if r.games else 0}

    # ---------- Matrix (deck_a perspective — intentionally one-sided) ----------
    # Each match gives exactly one row in the matrix: deck_a beat/lost to deck_b.
    # The frontend shows both directions because matrix[A][B] + matrix[B][A] exist.
    mx_rows = db.execute(text(f"""
        SELECT deck_a, deck_b, count(*) AS games,
               count(*) FILTER (WHERE winner = 'deck_a') AS wins
        FROM matches
        WHERE {base_where}
        GROUP BY deck_a, deck_b
    """), params).fetchall()

    matrix = {}
    for r in mx_rows:
        matrix.setdefault(r.deck_a, {})[r.deck_b] = {"w": r.wins, "t": r.games}

    # ---------- OTP/OTD (deck_a = on the play, deck_b = on the draw) ----------
    otp_rows = db.execute(text(f"""
        SELECT deck_a, deck_b, count(*) AS games,
               count(*) FILTER (WHERE winner = 'deck_a') AS otp_w,
               count(*) FILTER (WHERE winner = 'deck_b') AS otd_w
        FROM matches
        WHERE {base_where}
        GROUP BY deck_a, deck_b
    """), params).fetchall()

    otp_otd = {}
    for r in otp_rows:
        otp_otd.setdefault(r.deck_a, {})[r.deck_b] = {
            "otp_w": r.otp_w, "otp_t": r.games, "otd_w": r.otd_w, "otd_t": r.games,
        }

    # ---------- Trend (per day, both sides) ----------
    trend_rows = db.execute(text(f"""
        WITH sides AS (
            SELECT played_at::date AS day, deck_a AS deck,
                   CASE WHEN winner = 'deck_a' THEN 1 ELSE 0 END AS win,
                   CASE WHEN winner = 'deck_b' THEN 1 ELSE 0 END AS loss
            FROM matches WHERE {base_where}
            UNION ALL
            SELECT played_at::date AS day, deck_b AS deck,
                   CASE WHEN winner = 'deck_b' THEN 1 ELSE 0 END AS win,
                   CASE WHEN winner = 'deck_a' THEN 1 ELSE 0 END AS loss
            FROM matches WHERE {base_where}
        )
        SELECT day, deck, sum(win) AS w, sum(loss) AS l
        FROM sides GROUP BY day, deck ORDER BY day
    """), params).fetchall()

    trend = {}
    for r in trend_rows:
        day_str = r.day.strftime("%d/%m")
        trend.setdefault(day_str, {})[r.deck] = {"w": r.w, "l": r.l}

    # ---------- Meta share ----------
    meta_share = {}
    for deck, data in wr.items():
        share = round(data["games"] / total_games * 100, 1) if total_games else 0
        daily = {}
        for day_str, day_data in trend.items():
            day_total = sum(d["w"] + d["l"] for d in day_data.values())
            dg = day_data.get(deck, {})
            deck_day_games = dg.get("w", 0) + dg.get("l", 0)
            if day_total:
                daily[day_str] = round(deck_day_games / day_total * 100, 1)
        meta_share[deck] = {"share": share, "games": data["games"], "daily": daily}

    # ---------- Top players (both sides) ----------
    top_rows = db.execute(text(f"""
        WITH sides AS (
            SELECT player_a_name AS name, deck_a AS deck,
                   player_a_mmr AS mmr,
                   CASE WHEN winner = 'deck_a' THEN 1 ELSE 0 END AS win
            FROM matches WHERE {base_where} AND player_a_name IS NOT NULL
            UNION ALL
            SELECT player_b_name AS name, deck_b AS deck,
                   player_b_mmr AS mmr,
                   CASE WHEN winner = 'deck_b' THEN 1 ELSE 0 END AS win
            FROM matches WHERE {base_where} AND player_b_name IS NOT NULL
        )
        SELECT name, deck, max(mmr) AS mmr,
               count(*) AS games, sum(win) AS w,
               count(*) - sum(win) AS l,
               round(((sum(win)::numeric / count(*) * 100) * (count(*)::numeric / 10)), 1) AS score
        FROM sides GROUP BY name, deck
        HAVING count(*) >= 1
        ORDER BY score DESC
        LIMIT 500
    """), params).fetchall()

    top_players = []
    for r in top_rows:
        # If leaderboard filter active, only show players actually in the leaderboard
        if top_players_filter is not None and r.name.lower() not in top_players_filter:
            continue
        wr_val = round(r.w / r.games * 100, 1) if r.games else 0
        top_players.append({
            "name": r.name, "w": r.w, "l": r.l, "wr": wr_val,
            "mmr": r.mmr, "deck": r.deck, "is_pro": False,
            "matchups": {}, "score": round(wr_val * (r.games / 10), 1),
            "bo3": r.games,
        })

    # ELO distribution
    elo_dist = _build_elo_dist(db, base_where, params)

    # Deck Fitness Score: meta-weighted WR, normalized 0-100
    fitness = _compute_fitness(matrix, meta_share, min_games=15)

    return {
        "label": label,
        "wr": wr,
        "matrix": matrix,
        "otp_otd": otp_otd,
        "trend": trend,
        "meta_share": meta_share,
        "top_players": top_players,
        "elo_dist": elo_dist,
        "fitness": fitness,
    }


def _compute_fitness(matrix: dict, meta_share: dict, min_games: int = 15) -> list:
    """Deck Fitness Score: meta-weighted WR, 0-100 scale (50 = break-even).

    fitness(D) = Σ (wr[D vs X] × share[X]) / Σ share[X]
    Only opponents X with >= min_games games are counted.
    Returns list sorted by fitness desc, with rank and coverage.
    """
    results = []
    for deck, opp_map in matrix.items():
        deck_share_data = meta_share.get(deck)
        if not deck_share_data:
            continue

        weighted_wr = 0.0
        total_weight = 0.0
        covered = 0

        for opp, cell in opp_map.items():
            t = cell.get("t", 0)
            if opp == deck or t < min_games:
                continue
            opp_share_data = meta_share.get(opp)
            if not opp_share_data:
                continue
            opp_share = opp_share_data.get("share", 0)
            if opp_share <= 0:
                continue
            wr = (cell.get("w", 0) / t) * 100 if t > 0 else 0
            weighted_wr += wr * opp_share
            total_weight += opp_share
            covered += 1

        fitness = round(weighted_wr / total_weight, 1) if total_weight > 0 else None

        results.append({
            "deck": deck,
            "fitness": fitness,
            "games": deck_share_data.get("games", 0),
            "meta_share": deck_share_data.get("share", 0),
            "covered_matchups": covered,
            "coverage_pct": round(total_weight, 1),
        })

    results.sort(
        key=lambda r: (r["fitness"] if r["fitness"] is not None else -1),
        reverse=True,
    )
    for i, r in enumerate(results):
        r["rank"] = i + 1 if r["fitness"] is not None else None

    return results


def _build_elo_dist(db: Session, base_where: str, params: dict) -> dict:
    """ELO distribution per deck."""
    bins = ["1300-1399", "1400-1499", "1500-1599", "1600-1699", "1700-1799", "1800+"]
    thresholds = [1300, 1400, 1500, 1600, 1700, 1800, 99999]

    rows = db.execute(text(f"""
        SELECT deck_a AS deck, player_a_mmr AS mmr
        FROM matches
        WHERE {base_where}
          AND player_a_mmr IS NOT NULL AND player_a_mmr >= 1300
        UNION ALL
        SELECT deck_b AS deck, player_b_mmr AS mmr
        FROM matches
        WHERE {base_where}
          AND player_b_mmr IS NOT NULL AND player_b_mmr >= 1300
    """), params).fetchall()

    dist = {}
    for r in rows:
        deck = r.deck
        if deck not in dist:
            dist[deck] = {"bins": bins, "counts": [0] * len(bins), "total_mmr": 0, "n": 0}
        for i in range(len(thresholds) - 1):
            if thresholds[i] <= r.mmr < thresholds[i + 1]:
                dist[deck]["counts"][i] += 1
                break
        dist[deck]["total_mmr"] += r.mmr
        dist[deck]["n"] += 1

    result = {}
    for deck, d in dist.items():
        result[deck] = {
            "bins": d["bins"],
            "counts": d["counts"],
            "avg": round(d["total_mmr"] / d["n"]) if d["n"] else 0,
        }
    return result


def _build_community(db: Session, days: int) -> dict | None:
    """Community aggregate stats (all core perimeters)."""
    row = db.execute(text("""
        SELECT count(*) AS total,
               count(DISTINCT player_a_name) AS players,
               round(count(*) FILTER (WHERE winner = 'deck_a')::numeric / count(*) * 100, 1) AS otp_wr
        FROM matches
        WHERE game_format = 'core'
          AND played_at >= now() - make_interval(days => :days)
    """), {"days": days}).fetchone()

    if not row or row.total == 0:
        return None

    today = date.today()
    yesterday = date.today().fromordinal(today.toordinal() - 1)

    # WR and matrix for community (all core, both sides)
    wr_rows = db.execute(text("""
        WITH sides AS (
            SELECT deck_a AS deck, CASE WHEN winner = 'deck_a' THEN 1 ELSE 0 END AS win
            FROM matches WHERE game_format = 'core'
              AND played_at >= now() - make_interval(days => :days)
            UNION ALL
            SELECT deck_b AS deck, CASE WHEN winner = 'deck_b' THEN 1 ELSE 0 END AS win
            FROM matches WHERE game_format = 'core'
              AND played_at >= now() - make_interval(days => :days)
        )
        SELECT deck, count(*) AS games, sum(win) AS w
        FROM sides GROUP BY deck HAVING count(*) >= 5
        ORDER BY games DESC
    """), {"days": days}).fetchall()

    wr = {}
    for r in wr_rows:
        wr[r.deck] = {"w": r.w, "l": r.games - r.w, "games": r.games,
                       "wr": round(r.w / r.games * 100, 2) if r.games else 0}

    mx_rows = db.execute(text("""
        SELECT deck_a, deck_b, count(*) AS games,
               count(*) FILTER (WHERE winner = 'deck_a') AS wins
        FROM matches
        WHERE game_format = 'core'
          AND played_at >= now() - make_interval(days => :days)
        GROUP BY deck_a, deck_b
    """), {"days": days}).fetchall()

    matrix = {}
    for r in mx_rows:
        matrix.setdefault(r.deck_a, {})[r.deck_b] = {"w": r.wins, "t": r.games}

    return {
        "total_games": row.total,
        "players": row.players,
        "otp_wr": float(row.otp_wr) if row.otp_wr else 50.0,
        "period": f"{today.strftime('%d/%m')} + {yesterday.strftime('%d/%m')}",
        "wr": wr,
        "matrix": matrix,
    }


# ---------------------------------------------------------------------------
# LEADERBOARDS
# ---------------------------------------------------------------------------

def _build_leaderboards() -> dict:
    """Leaderboards from duels.ink API (cached).

    Returns raw queue data plus named player lists (core_top, core_pro, etc.)
    so the frontend can show "Best players of the format".
    """
    try:
        lb = fetch_leaderboards()
        raw = lb.get("raw", {})
        # Include top/pro name lists (sorted by rank from raw data)
        result = dict(raw)  # core_bo1, core_bo3, infinity_bo1, infinity_bo3
        for key in ("core_top", "core_pro", "inf_top", "inf_pro"):
            names = lb.get(key, set())
            # Convert set to sorted list (sort by rank from raw data)
            result[key] = _sort_names_by_rank(names, raw, key)
        return result
    except Exception as e:
        logger.warning("Leaderboard fetch failed: %s", e)
        return {}


def _sort_names_by_rank(names: set, raw: dict, key: str) -> list[dict]:
    """Sort player names by their best rank across relevant queues.

    Returns list of {name, rank, mmr, tier} for frontend display.
    """
    if not names:
        return []
    # Pick relevant raw queues
    if key.startswith("core"):
        queues = [raw.get("core_bo1", []), raw.get("core_bo3", [])]
    else:
        queues = [raw.get("infinity_bo1", []), raw.get("infinity_bo3", [])]

    best = {}
    for q in queues:
        for p in q:
            n = (p.get("name") or "").strip().lower()
            if n not in names:
                continue
            rank = p.get("rank", 999)
            if n not in best or rank < best[n]["rank"]:
                best[n] = {
                    "name": p.get("name", "").strip(),
                    "rank": rank,
                    "mmr": p.get("mmr", 0),
                    "tier": p.get("tier", ""),
                }
    return sorted(best.values(), key=lambda x: x["rank"])


# ---------------------------------------------------------------------------
# PRO PLAYERS
# ---------------------------------------------------------------------------

def _build_pro_players(db: Session, days: int) -> list:
    """Top players across all core perimeters (both sides of each match)."""
    rows = db.execute(text("""
        WITH sides AS (
            SELECT player_a_name AS name, deck_a AS deck,
                   player_a_mmr AS mmr,
                   CASE WHEN winner = 'deck_a' THEN 1 ELSE 0 END AS win
            FROM matches
            WHERE game_format = 'core' AND perimeter IN ('top', 'pro')
              AND played_at >= now() - make_interval(days => :days)
              AND player_a_name IS NOT NULL
            UNION ALL
            SELECT player_b_name AS name, deck_b AS deck,
                   player_b_mmr AS mmr,
                   CASE WHEN winner = 'deck_b' THEN 1 ELSE 0 END AS win
            FROM matches
            WHERE game_format = 'core' AND perimeter IN ('top', 'pro')
              AND played_at >= now() - make_interval(days => :days)
              AND player_b_name IS NOT NULL
        )
        SELECT name, deck, max(mmr) AS mmr,
               count(*) AS games, sum(win) AS w,
               count(*) - sum(win) AS l
        FROM sides GROUP BY name, deck
        HAVING count(*) >= 3
        ORDER BY max(mmr) DESC
        LIMIT 100
    """), {"days": days}).fetchall()

    return [
        {
            "name": r.name, "deck": r.deck, "mmr": r.mmr,
            "games": r.games, "w": r.w, "l": r.l,
            "wr": round(r.w / r.games * 100, 1) if r.games else 0,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# PLAYER CARDS & TECH TORNADO
# ---------------------------------------------------------------------------

def _build_player_cards(db: Session, game_format: str, days: int) -> dict:
    """Per-player card usage. Uses tech_service logic but returns raw dict."""
    from backend.services.tech_service import get_player_cards
    try:
        perimeters = (
            [DEFAULT_CORE_PERIMETER, "top", "pro"]
            if game_format == "core"
            else ["inf", "top", "pro"]
        )
        return get_player_cards(db, game_format, perimeters, days)
    except Exception as e:
        logger.warning("player_cards failed for %s: %s", game_format, e)
        return {}


def _build_tech_tornado(db: Session, days: int) -> dict:
    """Tech tornado per perimeter group."""
    from backend.services.tech_service import get_tech_tornado
    result = {}
    for perim_key in [DEFAULT_CORE_PERIMETER, "top", "pro", "infinity", "infinity_top", "infinity_pro"]:
        cfg = PERIMETER_CONFIG.get(perim_key)
        if not cfg:
            continue
        db_perims, db_fmt = cfg[0], cfg[1]
        try:
            # get_tech_tornado expects a single perimeter string;
            # use the first one as representative (it expands internally)
            data = get_tech_tornado(db, db_perims[0], None, db_fmt, days)
            if data and "decks" in data:
                result[perim_key] = data["decks"]
        except Exception:
            logger.exception("tech_tornado failed for %s", perim_key)
    return result


# ---------------------------------------------------------------------------
# MATCHUP TREND
# ---------------------------------------------------------------------------

def _build_matchup_trend(db: Session, days: int = 7) -> dict:
    """Per-deck matchup WR trend: recent window vs previous window.

    Returns {perim: {deck: {opp: {current_wr, prev_wr, delta, recent_games}}}}.
    recent = last 3 days, prev = 3 days before that (days 4-6).
    """
    recent_days = 3
    result = {}
    for group_key, perimeters, fmt in [
        (DEFAULT_CORE_PERIMETER, [DEFAULT_CORE_PERIMETER], "core"),
        ("top", ["top", "pro"], "core"),
        ("pro", ["pro"], "core"),
        ("infinity", ["inf"], "infinity"),
    ]:
        rows = db.execute(text("""
            SELECT deck_a, deck_b, winner,
                   CASE WHEN played_at >= now() - make_interval(days => :recent)
                        THEN 'recent' ELSE 'prev' END AS period
            FROM matches
            WHERE perimeter = ANY(:perims) AND game_format = :fmt
              AND played_at >= now() - make_interval(days => :days)
        """), {"perims": perimeters, "fmt": fmt, "days": days, "recent": recent_days}).fetchall()

        # Aggregate: {deck: {opp: {recent: {w,t}, prev: {w,t}}}}
        mu = {}
        for r in rows:
            d1, d2, winner, period = r.deck_a, r.deck_b, r.winner, r.period
            if not d1 or not d2:
                continue
            for deck, opp, won in [(d1, d2, winner == 'deck_a'), (d2, d1, winner == 'deck_b')]:
                bucket = mu.setdefault(deck, {}).setdefault(opp, {
                    "recent": {"w": 0, "t": 0}, "prev": {"w": 0, "t": 0}
                })
                bucket[period]["t"] += 1
                if won:
                    bucket[period]["w"] += 1

        perim_data = {}
        for deck, opps in mu.items():
            deck_trend = {}
            for opp, stats in opps.items():
                rec = stats["recent"]
                prev = stats["prev"]
                if rec["t"] < 3:
                    continue
                recent_wr = round(rec["w"] / rec["t"] * 100, 1)
                prev_wr = round(prev["w"] / prev["t"] * 100, 1) if prev["t"] >= 3 else None
                delta = round(recent_wr - prev_wr, 1) if prev_wr is not None else None
                deck_trend[opp] = {
                    "current_wr": recent_wr,
                    "prev_wr": prev_wr,
                    "delta": delta,
                    "recent_games": rec["t"],
                }
            if deck_trend:
                perim_data[deck] = deck_trend

        if perim_data:
            result[group_key] = perim_data

    return result


# ---------------------------------------------------------------------------
# MATCHUP ANALYZER (from matchup_reports table)
# ---------------------------------------------------------------------------

def _build_matchup_analyzer(db: Session, game_format: str) -> dict:
    """Assemble matchup_analyzer dict from matchup_reports table."""
    rows = db.execute(text("""
        SELECT our_deck, opp_deck, report_type, data
        FROM matchup_reports
        WHERE game_format = :fmt AND is_current = true
    """), {"fmt": game_format}).fetchall()

    analyzer = {}
    all_decks = set()

    for r in rows:
        all_decks.add(r.our_deck)
        all_decks.add(r.opp_deck)
        deck_block = analyzer.setdefault(r.our_deck, {})
        matchup_key = f"vs_{r.opp_deck}"
        matchup_block = deck_block.setdefault(matchup_key, {})
        matchup_block[r.report_type] = r.data

    analyzer["available_decks"] = sorted(all_decks)
    analyzer["all_decks"] = sorted(all_decks)

    # Build available_matchups for each deck
    for deck_code, deck_block in analyzer.items():
        if not isinstance(deck_block, dict) or deck_code in ("available_decks", "all_decks"):
            continue
        deck_block["available_matchups"] = sorted(
            k[3:] for k in deck_block if k.startswith("vs_")
        )

    return analyzer


# ---------------------------------------------------------------------------
# META DECK (consensus-based optimal decklist)
# ---------------------------------------------------------------------------
# PLAYER LOOKUP — lightweight per-player stats across ALL perimeters
# ---------------------------------------------------------------------------

def _build_player_lookup(db: Session, days: int) -> dict:
    """Per-player stats split by game_format (no leaderboard filter).

    Returns {"core": {player: {deck: {w,l,mmr}}}, "infinity": {...}}
    for Profile "My Stats". Last N days, >= 2 games per deck.
    """
    rows = db.execute(text("""
        WITH sides AS (
            SELECT lower(player_a_name) AS name, deck_a AS deck,
                   player_a_mmr AS mmr, game_format AS fmt,
                   CASE WHEN winner = 'deck_a' THEN 1 ELSE 0 END AS win
            FROM matches
            WHERE played_at >= now() - make_interval(days => :days)
              AND player_a_name IS NOT NULL
            UNION ALL
            SELECT lower(player_b_name) AS name, deck_b AS deck,
                   player_b_mmr AS mmr, game_format AS fmt,
                   CASE WHEN winner = 'deck_b' THEN 1 ELSE 0 END AS win
            FROM matches
            WHERE played_at >= now() - make_interval(days => :days)
              AND player_b_name IS NOT NULL
        )
        SELECT fmt, name, deck, max(mmr) AS mmr,
               sum(win)::int AS w, (count(*) - sum(win))::int AS l
        FROM sides
        GROUP BY fmt, name, deck
        HAVING count(*) >= 2
    """), {"days": days}).fetchall()

    result = {"core": {}, "infinity": {}}
    for r in rows:
        fmt_key = r.fmt if r.fmt in ("core", "infinity") else "core"
        result[fmt_key].setdefault(r.name, {})[r.deck] = {
            "w": r.w, "l": r.l, "mmr": r.mmr or 0,
        }
    return result


# ---------------------------------------------------------------------------

def _build_meta_deck(db: Session, game_format: str) -> dict:
    """Per-deck consensus decklist with cuts/adds from matchup_reports 'decklist' type."""
    consensus = static_data_service.get_consensus(db)
    result = {}

    for deck, cards in consensus.items():
        if not cards:
            continue

        # Build final_deck from consensus (cards with avg_qty >= 1.5 rounded)
        final_deck = {}
        total = 0
        for card, qty in sorted(cards.items(), key=lambda x: -x[1]):
            rounded = round(qty)
            if rounded >= 1 and total + rounded <= 60:
                final_deck[card] = rounded
                total += rounded

        # Mana curve from cards table
        mana_curve = {}
        if final_deck:
            card_names = list(final_deck.keys())
            placeholders = ", ".join(f":c{i}" for i in range(len(card_names)))
            params = {f"c{i}": name for i, name in enumerate(card_names)}
            cost_rows = db.execute(text(f"""
                SELECT name, cost FROM cards WHERE name IN ({placeholders})
            """), params).fetchall()
            cost_map = {r.name: r.cost for r in cost_rows}
            for card, qty in final_deck.items():
                cost = cost_map.get(card, 0) or 0
                cost_key = str(min(cost, 7))
                mana_curve[cost_key] = mana_curve.get(cost_key, 0) + qty

        # Import text
        import_text = "\n".join(f"{qty} {card}" for card, qty in sorted(final_deck.items()))

        result[deck] = {
            "final_deck": final_deck,
            "total_cards": total,
            "cuts": [],
            "adds": [],
            "protected": [],
            "coverage": {},
            "mana_curve": mana_curve,
            "import_text": import_text,
            "singer_tips": {},
        }

    return result


# ---------------------------------------------------------------------------
# TEAM
# ---------------------------------------------------------------------------

def _build_team(db: Session, days: int) -> dict:
    """Team stats from roster — mirrors analisidef/daily/team_training.py logic.

    Searches all core perimeters (set11, top, pro) for matches involving
    roster players, then builds per-player stats + team overview.
    """
    try:
        # Load roster
        roster_rows = db.execute(text("SELECT name, role FROM team_roster")).fetchall()
        if not roster_rows:
            return {}
        roster = [{"name": r.name, "role": r.role or ""} for r in roster_rows]

        # Fetch all matches involving roster players (both sides, all core perimeters)
        names_lower = [r["name"].lower() for r in roster]
        match_rows = db.execute(text("""
            SELECT player_a_name, player_b_name, deck_a, deck_b,
                   player_a_mmr, player_b_mmr, winner,
                   played_at::date AS day
            FROM matches
            WHERE game_format = 'core'
              AND played_at >= now() - make_interval(days => :days)
              AND (lower(player_a_name) = ANY(:names) OR lower(player_b_name) = ANY(:names))
        """), {"days": days, "names": names_lower}).fetchall()

        if not match_rows:
            return {"overview": {}, "players": [], "roster_count": len(roster)}

        # Build per-player stats
        player_stats = []
        for entry in roster:
            pname = entry["name"]
            plow = pname.lower()

            # Normalise each match: our side vs opponent side
            pmatches = []
            for m in match_rows:
                if (m.player_a_name or "").lower() == plow:
                    pmatches.append({
                        "our_deck": m.deck_a, "opp_deck": m.deck_b,
                        "our_mmr": m.player_a_mmr or 0,
                        "won": m.winner == "deck_a",
                        "otp": True,  # deck_a = on the play
                        "day": m.day.strftime("%d%m%y") if m.day else "",
                    })
                elif (m.player_b_name or "").lower() == plow:
                    pmatches.append({
                        "our_deck": m.deck_b, "opp_deck": m.deck_a,
                        "our_mmr": m.player_b_mmr or 0,
                        "won": m.winner == "deck_b",
                        "otp": False,
                        "day": m.day.strftime("%d%m%y") if m.day else "",
                    })

            if not pmatches:
                continue

            total = len(pmatches)
            wins = sum(1 for m in pmatches if m["won"])
            losses = total - wins

            # Main deck (most played)
            from collections import defaultdict, Counter
            deck_counts = Counter(m["our_deck"] for m in pmatches if m["our_deck"])
            main_deck = deck_counts.most_common(1)[0][0] if deck_counts else None

            best_mmr = max((m["our_mmr"] for m in pmatches if m["our_mmr"]), default=0)

            # OTP / OTD
            otp_g = [m for m in pmatches if m["otp"]]
            otd_g = [m for m in pmatches if not m["otp"]]
            _wr = lambda w, t: round(w / t * 100, 1) if t else 0.0
            otp_wr = _wr(sum(1 for m in otp_g if m["won"]), len(otp_g))
            otd_wr = _wr(sum(1 for m in otd_g if m["won"]), len(otd_g))

            # Matchups
            vs = defaultdict(lambda: {"w": 0, "l": 0})
            for m in pmatches:
                opp = m["opp_deck"]
                if not opp:
                    continue
                if m["won"]:
                    vs[opp]["w"] += 1
                else:
                    vs[opp]["l"] += 1
            matchups = {}
            for opp, s in sorted(vs.items(), key=lambda x: -(x[1]["w"] + x[1]["l"])):
                t = s["w"] + s["l"]
                matchups[opp] = {"w": s["w"], "l": s["l"], "wr": _wr(s["w"], t), "games": t}

            # Worst / best matchup (min 3 games)
            worst_mu = min((o for o, s in matchups.items() if s["games"] >= 3),
                           key=lambda o: matchups[o]["wr"], default=None)
            best_mu = max((o for o, s in matchups.items() if s["games"] >= 3),
                          key=lambda o: matchups[o]["wr"], default=None)

            # Daily WR
            day_stats = defaultdict(lambda: {"w": 0, "t": 0})
            for m in pmatches:
                day_stats[m["day"]]["t"] += 1
                if m["won"]:
                    day_stats[m["day"]]["w"] += 1
            daily = [{"day": d, "wr": _wr(s["w"], s["t"]), "games": s["t"]}
                     for d, s in sorted(day_stats.items())]

            # Alerts
            alerts = []
            wr_val = _wr(wins, total)
            if worst_mu and matchups[worst_mu]["wr"] < 40:
                mu = matchups[worst_mu]
                alerts.append({"type": "danger",
                               "msg": f"WR {mu['wr']}% vs {worst_mu} ({mu['games']}g)"})
            if otp_wr - otd_wr > 15:
                alerts.append({"type": "warning",
                               "msg": f"OTP/OTD gap: {round(otp_wr - otd_wr, 1)}pp — soffre OTD"})
            if total >= 5 and wr_val < 45:
                alerts.append({"type": "danger",
                               "msg": f"WR complessivo {wr_val}% su {total} partite"})

            player_stats.append({
                "name": pname, "deck": main_deck, "games": total,
                "wins": wins, "losses": losses, "wr": wr_val,
                "mmr": best_mmr, "otp_wr": otp_wr, "otd_wr": otd_wr,
                "otp_otd_gap": round(otp_wr - otd_wr, 1),
                "matchups": matchups, "worst_matchup": worst_mu,
                "best_matchup": best_mu, "daily": daily,
                "alerts": alerts, "role": entry["role"],
            })

        if not player_stats:
            return {"overview": {}, "players": [], "roster_count": len(roster)}

        # Team overview
        total_games = sum(p["games"] for p in player_stats)
        total_wins = sum(p["wins"] for p in player_stats)
        avg_wr = round(total_wins / total_games * 100, 1) if total_games else 0

        best_p = max(player_stats, key=lambda p: p["wr"])
        worst_p = min(player_stats, key=lambda p: p["wr"])

        # Weakness overlap
        opp_decks = set()
        for p in player_stats:
            opp_decks.update(p["matchups"].keys())
        weakness_overlap = {}
        team_alerts = []
        for opp in sorted(opp_decks):
            weak = [p["name"] for p in player_stats
                    if opp in p["matchups"] and p["matchups"][opp]["games"] >= 2
                    and p["matchups"][opp]["wr"] < 45]
            if weak:
                weakness_overlap[opp] = weak
            if len(weak) >= 2:
                team_alerts.append({
                    "type": "danger",
                    "msg": f"{len(weak)}/{len(player_stats)} giocatori sotto 45% vs {opp}",
                    "players": weak, "deck": opp,
                })

        return {
            "overview": {
                "total_games": total_games, "avg_wr": avg_wr,
                "player_count": len(player_stats),
                "best_player": {"name": best_p["name"], "wr": best_p["wr"]},
                "worst_player": {"name": worst_p["name"], "wr": worst_p["wr"]},
                "weakness_overlap": weakness_overlap,
                "alerts": team_alerts,
            },
            "players": player_stats,
            "roster_count": len(roster),
        }
    except Exception as e:
        logger.warning("team stats failed: %s", e)
        import traceback; traceback.print_exc()
        return {}


def _build_emerging_decks(db: Session) -> dict:
    """Lightweight rogue scout payload for the dashboard blob.

    Returns a compact structure for the Monitor tab 'Emerging & Rogue' section.

    Freshness rules:
    - 3-day window (not 7) so daily rotation actually rotates
    - drop players in the leaderboard pro-tier (top 50) of the same format —
      they're already known, "emerging" should surface the under-the-radar
    """
    try:
        from backend.services import rogue_scout_service
        from backend.services.leaderboard_service import fetch_leaderboards

        try:
            lb = fetch_leaderboards()
        except Exception:
            lb = {}
        exclude_by_fmt = {
            "core": {n.lower() for n in lb.get("core_pro", [])},
            "infinity": {n.lower() for n in lb.get("inf_pro", [])},
        }

        def _keep(tile: dict, fmt: str) -> bool:
            label = (tile.get("label") or "").strip().lower()
            return bool(label) and label not in exclude_by_fmt.get(fmt, set())

        result = {"core": [], "infinity": []}
        for fmt in ("core", "infinity"):
            cfg = rogue_scout_service.RogueScoutConfig(
                game_format=fmt,
                days=3,
                min_games=8,
                min_wr=0.52,
                min_mmr=1300,
                off_meta_min_games=10,
            )
            raw = rogue_scout_service.get_candidate_preview(db, cfg)
            tier0 = set(raw.get("meta", {}).get("tier0_codes", []))

            tiles = []

            # 1. OFF-META WINNERS — non-tier0 deck with validated WR
            for r in raw.get("off_meta_validated", [])[:3]:
                tiles.append({
                    "type": "off_meta",
                    "deck": r.get("deck", "?"),
                    "label": r.get("player", "?"),
                    "players": 1,
                    "wr": r.get("wr"),
                    "wr_lb": r.get("wr_wilson_lb"),
                    "cards": r.get("extra_vs_consensus", [])[:4],
                    "games": r.get("games", 0),
                    "mmr": r.get("avg_mmr", 0),
                })

            # 2. BREW WATCH — high jaccard distance variants with good WR
            for sb in raw.get("solo_brews", [])[:3]:
                # Skip if already covered as off-meta
                if any(t["deck"] == sb.get("deck") and t["label"] == sb.get("player") for t in tiles):
                    continue
                tiles.append({
                    "type": "brew",
                    "deck": sb.get("deck", "?"),
                    "label": sb.get("player", "?"),
                    "players": 1,
                    "wr": sb.get("wr"),
                    "wr_lb": sb.get("wr_wilson_lb"),
                    "cards": sb.get("extra_vs_consensus", [])[:4],
                    "games": sb.get("games", 0),
                    "mmr": sb.get("avg_mmr", 0),
                })

            # 3. NEW COLORS — unusual ink combos without consensus
            for uc in raw.get("unusual_color_pairs", [])[:2]:
                tiles.append({
                    "type": "new_colors",
                    "deck": uc.get("deck", "?"),
                    "label": uc.get("player", "?"),
                    "players": 1,
                    "wr": uc.get("wr"),
                    "wr_lb": uc.get("wr_wilson_lb"),
                    "cards": [],
                    "games": uc.get("games", 0),
                    "mmr": uc.get("avg_mmr", 0),
                })

            # Drop leaderboard pro-tier players ("under-the-radar" only)
            tiles = [t for t in tiles if _keep(t, fmt)]

            # Sort by WR wilson lb descending, cap at 6
            tiles.sort(key=lambda t: -(t.get("wr_lb") or 0))
            result[fmt] = tiles[:6]

        return result
    except Exception as e:
        logger.warning("emerging_decks failed: %s", e)
        return {"core": [], "infinity": []}
