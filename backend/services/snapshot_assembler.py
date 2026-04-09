"""
Snapshot assembler — builds the full dashboard blob from PostgreSQL.

Replaces the dependency on daily_routine.py's dashboard_data.json.
Each section mirrors the exact structure the frontend expects.
"""
import logging
from datetime import date, datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.services import static_data_service
from backend.services.leaderboard_service import fetch_leaderboards

logger = logging.getLogger(__name__)

# Perimeter config: blob_key → (db_perimeter, db_game_format, label, min_elo)
PERIMETER_CONFIG = {
    "set11":            ("set11", "core",     "SET11 High ELO (≥1300)", 1300),
    "top":              ("top",   "core",     "TOP", None),
    "pro":              ("pro",   "core",     "PRO", None),
    "friends_core":     ("friends", "core",   "Friends (Core)", None),
    "infinity":         ("inf",   "infinity", "Infinity", None),
    "infinity_top":     ("top",   "infinity", "Infinity TOP", None),
    "infinity_pro":     ("pro",   "infinity", "Infinity PRO", None),
    "infinity_friends": ("friends", "infinity", "Friends (Infinity)", None),
}

DAYS = 2  # default analysis window


def assemble(db: Session, days: int = DAYS) -> dict:
    """Assemble the full dashboard blob from PG. Returns dict matching frontend DATA shape."""
    logger.info("Assembling dashboard snapshot (days=%d)...", days)

    blob = {}
    blob["meta"] = _build_meta(db, days)
    blob["perimeters"] = _build_perimeters(db, days)
    blob["leaderboards"] = _build_leaderboards()
    blob["pro_players"] = _build_pro_players(db, days)
    blob["consensus"] = static_data_service.get_consensus(db)
    blob["reference_decklists"] = static_data_service.get_reference_decklists(db)
    blob["player_cards"] = _build_player_cards(db, days)
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
    blob["kc_spy"] = {}
    blob["analysis"] = ""

    logger.info("Snapshot assembled: %d top-level keys", len(blob))
    return blob


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
    yesterday = date.today().fromordinal(today.toordinal() - 1)
    period = f"{today.strftime('%d/%m')} + {yesterday.strftime('%d/%m')}"

    return {
        "updated": datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M"),
        "period": period,
        "games": games,
    }


def _db_to_blob_perimeter(db_perim: str, db_format: str) -> str | None:
    """Map DB (perimeter, game_format) → blob key."""
    for blob_key, (p, f, _, _) in PERIMETER_CONFIG.items():
        if p == db_perim and f == db_format:
            return blob_key
    return None


# ---------------------------------------------------------------------------
# PERIMETERS
# ---------------------------------------------------------------------------

def _build_perimeters(db: Session, days: int) -> dict:
    """Build wr, matrix, otp_otd, trend, meta_share, top_players, elo_dist per perimeter."""
    result = {}
    for blob_key, (db_perim, db_fmt, label, min_elo) in PERIMETER_CONFIG.items():
        perim_data = _build_single_perimeter(db, db_perim, db_fmt, label, min_elo, days)
        if perim_data:
            result[blob_key] = perim_data

    # Community aggregate (all core perimeters combined)
    community = _build_community(db, days)
    if community:
        result["community"] = community

    return result


def _build_single_perimeter(db: Session, db_perim: str, db_fmt: str,
                             label: str, min_elo: int | None, days: int) -> dict | None:
    """Build stats for one perimeter."""
    params = {"perim": db_perim, "fmt": db_fmt, "days": days}
    elo_filter = ""
    if min_elo:
        elo_filter = "AND player_a_mmr >= :min_elo"
        params["min_elo"] = min_elo

    # WR per deck
    rows = db.execute(text(f"""
        SELECT deck_a AS deck, count(*) AS games,
               count(*) FILTER (WHERE winner = 'deck_a') AS w
        FROM matches
        WHERE perimeter = :perim AND game_format = :fmt
          AND played_at >= now() - make_interval(days => :days)
          {elo_filter}
        GROUP BY deck_a
        HAVING count(*) >= 5
        ORDER BY games DESC
    """), params).fetchall()

    if not rows:
        return None

    wr = {}
    total_games = sum(r.games for r in rows)
    for r in rows:
        wr[r.deck] = {"w": r.w, "l": r.games - r.w, "games": r.games,
                       "wr": round(r.w / r.games * 100, 2) if r.games else 0}

    # Matrix
    mx_rows = db.execute(text(f"""
        SELECT deck_a, deck_b, count(*) AS games,
               count(*) FILTER (WHERE winner = 'deck_a') AS wins
        FROM matches
        WHERE perimeter = :perim AND game_format = :fmt
          AND played_at >= now() - make_interval(days => :days)
          {elo_filter}
        GROUP BY deck_a, deck_b
    """), params).fetchall()

    matrix = {}
    for r in mx_rows:
        matrix.setdefault(r.deck_a, {})[r.deck_b] = {"w": r.wins, "t": r.games}

    # OTP/OTD
    otp_rows = db.execute(text(f"""
        SELECT deck_a, deck_b, count(*) AS games,
               count(*) FILTER (WHERE winner = 'deck_a') AS otp_w,
               count(*) FILTER (WHERE winner = 'deck_b') AS otd_w
        FROM matches
        WHERE perimeter = :perim AND game_format = :fmt
          AND played_at >= now() - make_interval(days => :days)
          {elo_filter}
        GROUP BY deck_a, deck_b
    """), params).fetchall()

    otp_otd = {}
    for r in otp_rows:
        otp_otd.setdefault(r.deck_a, {})[r.deck_b] = {
            "otp_w": r.otp_w, "otp_t": r.games, "otd_w": r.otd_w, "otd_t": r.games,
        }

    # Trend (per day)
    trend_rows = db.execute(text(f"""
        SELECT played_at::date AS day, deck_a AS deck,
               count(*) FILTER (WHERE winner = 'deck_a') AS w,
               count(*) FILTER (WHERE winner = 'deck_b') AS l
        FROM matches
        WHERE perimeter = :perim AND game_format = :fmt
          AND played_at >= now() - make_interval(days => :days)
          {elo_filter}
        GROUP BY day, deck_a
        ORDER BY day
    """), params).fetchall()

    trend = {}
    for r in trend_rows:
        day_str = r.day.strftime("%d/%m")
        trend.setdefault(day_str, {})[r.deck] = {"w": r.w, "l": r.l}

    # Meta share
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

    # Top players
    top_rows = db.execute(text(f"""
        SELECT player_a_name AS name, deck_a AS deck,
               max(player_a_mmr) AS mmr,
               count(*) AS games,
               count(*) FILTER (WHERE winner = 'deck_a') AS w,
               count(*) FILTER (WHERE winner = 'deck_b') AS l
        FROM matches
        WHERE perimeter = :perim AND game_format = :fmt
          AND played_at >= now() - make_interval(days => :days)
          AND player_a_name IS NOT NULL
          {elo_filter}
        GROUP BY player_a_name, deck_a
        HAVING count(*) >= 3
        ORDER BY count(*) FILTER (WHERE winner = 'deck_a')::float / count(*) DESC
        LIMIT 150
    """), params).fetchall()

    top_players = []
    for r in top_rows:
        wr_val = round(r.w / r.games * 100, 1) if r.games else 0
        top_players.append({
            "name": r.name, "w": r.w, "l": r.l, "wr": wr_val,
            "mmr": r.mmr, "deck": r.deck, "is_pro": False,
            "matchups": {}, "score": round(wr_val * (r.games / 10), 1),
            "bo3": r.games,
        })

    # ELO distribution
    elo_dist = _build_elo_dist(db, db_perim, db_fmt, days, elo_filter, params)

    return {
        "label": label,
        "wr": wr,
        "matrix": matrix,
        "otp_otd": otp_otd,
        "trend": trend,
        "meta_share": meta_share,
        "top_players": top_players,
        "elo_dist": elo_dist,
        "tech_choices": [],
    }


def _build_elo_dist(db: Session, db_perim: str, db_fmt: str,
                     days: int, elo_filter: str, params: dict) -> dict:
    """ELO distribution per deck."""
    bins = ["1300-1399", "1400-1499", "1500-1599", "1600-1699", "1700-1799", "1800+"]
    thresholds = [1300, 1400, 1500, 1600, 1700, 1800, 99999]

    rows = db.execute(text(f"""
        SELECT deck_a AS deck, player_a_mmr AS mmr
        FROM matches
        WHERE perimeter = :perim AND game_format = :fmt
          AND played_at >= now() - make_interval(days => :days)
          AND player_a_mmr IS NOT NULL AND player_a_mmr >= 1300
          {elo_filter}
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

    # WR and matrix for community (all core)
    wr_rows = db.execute(text("""
        SELECT deck_a AS deck, count(*) AS games,
               count(*) FILTER (WHERE winner = 'deck_a') AS w
        FROM matches
        WHERE game_format = 'core'
          AND played_at >= now() - make_interval(days => :days)
        GROUP BY deck_a HAVING count(*) >= 5
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
    """Leaderboards from duels.ink API (cached)."""
    try:
        lb = fetch_leaderboards()
        return lb.get("raw", {})
    except Exception as e:
        logger.warning("Leaderboard fetch failed: %s", e)
        return {}


# ---------------------------------------------------------------------------
# PRO PLAYERS
# ---------------------------------------------------------------------------

def _build_pro_players(db: Session, days: int) -> list:
    """Top players across all core perimeters."""
    rows = db.execute(text("""
        SELECT player_a_name AS name, deck_a AS deck,
               max(player_a_mmr) AS mmr,
               count(*) AS games,
               count(*) FILTER (WHERE winner = 'deck_a') AS w,
               count(*) FILTER (WHERE winner = 'deck_b') AS l
        FROM matches
        WHERE game_format = 'core'
          AND perimeter IN ('top', 'pro')
          AND played_at >= now() - make_interval(days => :days)
          AND player_a_name IS NOT NULL
        GROUP BY player_a_name, deck_a
        HAVING count(*) >= 3
        ORDER BY max(player_a_mmr) DESC
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

def _build_player_cards(db: Session, days: int) -> dict:
    """Per-player card usage. Uses tech_service logic but returns raw dict."""
    from backend.services.tech_service import get_player_cards
    try:
        return get_player_cards(db, "core", ["set11", "top", "pro"], days)
    except Exception as e:
        logger.warning("player_cards failed: %s", e)
        return {}


def _build_tech_tornado(db: Session, days: int) -> dict:
    """Tech tornado per perimeter group."""
    from backend.services.tech_service import get_tech_tornado
    result = {}
    for perim_key in ["set11", "top", "pro", "infinity", "infinity_top", "infinity_pro"]:
        cfg = PERIMETER_CONFIG.get(perim_key)
        if not cfg:
            continue
        db_perim, db_fmt = cfg[0], cfg[1]
        try:
            data = get_tech_tornado(db, db_perim, None, db_fmt, days)
            if data and "decks" in data:
                result[perim_key] = data["decks"]
        except Exception:
            pass
    return result


# ---------------------------------------------------------------------------
# MATCHUP TREND
# ---------------------------------------------------------------------------

def _build_matchup_trend(db: Session, days: int = 7) -> dict:
    """Daily WR trend per deck, grouped by perimeter group."""
    result = {}
    for group_key, perimeters, fmt in [
        ("set11", ["set11"], "core"),
        ("top", ["top"], "core"),
        ("pro", ["pro"], "core"),
        ("infinity", ["inf"], "infinity"),
    ]:
        rows = db.execute(text("""
            SELECT played_at::date AS day, deck_a AS deck,
                   count(*) FILTER (WHERE winner = 'deck_a') AS w,
                   count(*) FILTER (WHERE winner = 'deck_b') AS l
            FROM matches
            WHERE perimeter = ANY(:perims) AND game_format = :fmt
              AND played_at >= now() - make_interval(days => :days)
            GROUP BY day, deck_a
            ORDER BY day
        """), {"perims": perimeters, "fmt": fmt, "days": days}).fetchall()

        trend = {}
        for r in rows:
            day_str = r.day.strftime("%d/%m")
            trend.setdefault(day_str, {})[r.deck] = {"w": r.w, "l": r.l}
        if trend:
            result[group_key] = trend

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

    return analyzer


# ---------------------------------------------------------------------------
# META DECK (consensus-based optimal decklist)
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
    """Team overview stats from team roster matches."""
    # Check if team_replays or team roster exists
    try:
        rows = db.execute(text("""
            SELECT player_a_name AS name,
                   count(*) AS games,
                   count(*) FILTER (WHERE winner = 'deck_a') AS w
            FROM matches
            WHERE perimeter = 'mygame'
              AND played_at >= now() - make_interval(days => :days)
              AND player_a_name IS NOT NULL
            GROUP BY player_a_name
        """), {"days": days}).fetchall()

        if not rows:
            return {}

        players = []
        for r in rows:
            wr = round(r.w / r.games * 100, 1) if r.games else 0
            players.append({"name": r.name, "games": r.games, "w": r.w, "wr": wr})

        total_games = sum(p["games"] for p in players)
        total_wins = sum(p["w"] for p in players)
        avg_wr = round(total_wins / total_games * 100, 1) if total_games else 0

        best = max(players, key=lambda p: p["wr"]) if players else None
        worst = min(players, key=lambda p: p["wr"]) if players else None

        return {
            "overview": {
                "total_games": total_games,
                "avg_wr": avg_wr,
                "player_count": len(players),
                "best_player": {"name": best["name"], "wr": best["wr"]} if best else {},
                "worst_player": {"name": worst["name"], "wr": worst["wr"]} if worst else {},
                "weakness_overlap": {},
            },
            "players": players,
            "roster_count": len(players),
        }
    except Exception as e:
        logger.warning("team stats failed: %s", e)
        return {}
