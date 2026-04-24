"""
Stats service — win rates, matchup matrix, meta share, OTP/OTD.
All queries hit PostgreSQL instead of scanning JSON files.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session


def get_meta_share(db: Session, game_format: str = "core", days: int = 2):
    """Meta share: % of games per deck."""
    rows = db.execute(text("""
        SELECT deck_a AS deck, COUNT(*) AS games,
               COUNT(*) FILTER (WHERE winner = 'deck_a') AS wins
        FROM matches
        WHERE game_format = :fmt AND played_at >= now() - make_interval(days => :days)
        GROUP BY deck_a
        ORDER BY games DESC
    """), {"fmt": game_format, "days": days}).fetchall()

    total = sum(r.games for r in rows)
    return [
        {
            "deck": r.deck,
            "games": r.games,
            "wins": r.wins,
            "losses": r.games - r.wins,
            "wr": round(r.wins / r.games * 100, 1) if r.games else 0,
            "meta_share": round(r.games / total * 100, 1) if total else 0,
        }
        for r in rows
    ]


def get_deck_winrates(db: Session, game_format: str = "core", perimeter: str | None = None, days: int = 2):
    """Win rate per deck, optionally filtered by perimeter."""
    params = {"fmt": game_format, "days": days}
    where_perim = ""
    if perimeter:
        where_perim = "AND perimeter = :perim"
        params["perim"] = perimeter

    rows = db.execute(text(f"""
        SELECT deck_a AS deck,
               COUNT(*) AS games,
               COUNT(*) FILTER (WHERE winner = 'deck_a') AS wins
        FROM matches
        WHERE game_format = :fmt
          AND played_at >= now() - make_interval(days => :days)
          {where_perim}
        GROUP BY deck_a
        ORDER BY games DESC
    """), params).fetchall()

    return [
        {
            "deck": r.deck,
            "games": r.games,
            "wins": r.wins,
            "losses": r.games - r.wins,
            "wr": round(r.wins / r.games * 100, 1) if r.games else 0,
        }
        for r in rows
    ]


def get_matchup_matrix(db: Session, game_format: str = "core", perimeter: str | None = None, days: int = 7, queue_filter: str | None = None):
    """Full matchup matrix: WR for every deck_a vs deck_b pair.

    queue_filter: None=all, 'bo3'=only Bo3 matches (queue_name ending in -BO3).
    """
    params = {"fmt": game_format, "days": days}
    where_perim = ""
    if perimeter:
        where_perim = "AND perimeter = :perim"
        params["perim"] = perimeter
    where_queue = ""
    if queue_filter == "bo3":
        where_queue = "AND queue_name LIKE '%-BO3'"
    elif queue_filter == "bo1":
        where_queue = "AND queue_name LIKE '%-BO1'"

    rows = db.execute(text(f"""
        SELECT deck_a, deck_b,
               COUNT(*) AS games,
               COUNT(*) FILTER (WHERE winner = 'deck_a') AS wins_a,
               ROUND(AVG(total_turns), 1) AS avg_turns
        FROM matches
        WHERE game_format = :fmt
          AND played_at >= now() - make_interval(days => :days)
          {where_perim}
          {where_queue}
        GROUP BY deck_a, deck_b
        ORDER BY deck_a, deck_b
    """), params).fetchall()

    matrix = {}
    for r in rows:
        if r.deck_a not in matrix:
            matrix[r.deck_a] = {}
        matrix[r.deck_a][r.deck_b] = {
            "games": r.games,
            "wins": r.wins_a,
            "wr": round(r.wins_a / r.games * 100, 1) if r.games else 0,
            "avg_turns": float(r.avg_turns) if r.avg_turns else 0,
        }
    return matrix


def get_otp_otd(db: Session, game_format: str = "core", perimeter: str | None = None, days: int = 7, queue_filter: str | None = None):
    """OTP (on-the-play) vs OTD (on-the-draw) win rates per deck.

    In the match DB, deck_a is always player 1 (first to play = OTP).
    So deck_a wins as OTP = winner='deck_a', and deck_b wins as OTD = winner='deck_b'.

    queue_filter: None=all, 'bo3'=only Bo3 matches, 'bo1'=only Bo1.
    """
    params = {"fmt": game_format, "days": days}
    where_perim = ""
    if perimeter:
        where_perim = "AND perimeter = :perim"
        params["perim"] = perimeter
    where_queue = ""
    if queue_filter == "bo3":
        where_queue = "AND queue_name LIKE '%-BO3'"
    elif queue_filter == "bo1":
        where_queue = "AND queue_name LIKE '%-BO1'"

    rows = db.execute(text(f"""
        SELECT deck_a, deck_b,
               COUNT(*) AS games,
               COUNT(*) FILTER (WHERE winner = 'deck_a') AS otp_wins,
               COUNT(*) FILTER (WHERE winner = 'deck_b') AS otd_wins
        FROM matches
        WHERE game_format = :fmt
          AND played_at >= now() - make_interval(days => :days)
          {where_perim}
          {where_queue}
        GROUP BY deck_a, deck_b
    """), params).fetchall()

    result = {}
    for r in rows:
        if r.deck_a not in result:
            result[r.deck_a] = {}
        result[r.deck_a][r.deck_b] = {
            "games": r.games,
            "otp_wins": r.otp_wins,
            "otd_wins": r.otd_wins,
            "otp_wr": round(r.otp_wins / r.games * 100, 1) if r.games else 0,
            "otd_wr": round(r.otd_wins / r.games * 100, 1) if r.games else 0,
        }
    return result


def get_deck_fitness(
    db: Session,
    game_format: str = "core",
    perimeter: str | None = None,
    days: int = 7,
    min_games_per_matchup: int = 15,
):
    """Deck Fitness Score: meta-weighted winrate, normalized 0-100.

    For each deck D:
        fitness(D) = Σ (wr[D vs X] × share[X]) / Σ share[X]
        where X are opponents with at least `min_games_per_matchup` games.

    Since wr is already 0-100, fitness is naturally on a 0-100 scale.
    50 = meta break-even. Deck with no qualifying matchups has fitness=None.
    """
    meta = get_meta_share(db, game_format=game_format, days=days)
    matrix = get_matchup_matrix(db, game_format=game_format, perimeter=perimeter, days=days)

    share_by_deck = {row["deck"]: row["meta_share"] for row in meta}
    games_by_deck = {row["deck"]: row["games"] for row in meta}
    wr_by_deck = {row["deck"]: row["wr"] for row in meta}

    results = []
    for deck, share in share_by_deck.items():
        opp_map = matrix.get(deck, {})
        weighted_wr = 0.0
        total_weight = 0.0
        covered_matchups = 0

        for opp, cell in opp_map.items():
            if opp == deck:
                continue
            if cell["games"] < min_games_per_matchup:
                continue
            opp_share = share_by_deck.get(opp, 0)
            if opp_share <= 0:
                continue
            weighted_wr += cell["wr"] * opp_share
            total_weight += opp_share
            covered_matchups += 1

        if total_weight > 0:
            fitness = round(weighted_wr / total_weight, 1)
        else:
            fitness = None

        results.append({
            "deck": deck,
            "fitness": fitness,
            "wr_avg": wr_by_deck.get(deck, 0),
            "meta_share": share,
            "games_total": games_by_deck.get(deck, 0),
            "covered_matchups": covered_matchups,
            "coverage_pct": round(total_weight, 1),
        })

    # rank: None fitness at the end
    results.sort(
        key=lambda r: (r["fitness"] if r["fitness"] is not None else -1),
        reverse=True,
    )
    for i, r in enumerate(results):
        r["rank"] = i + 1 if r["fitness"] is not None else None

    return results


def get_trend(db: Session, game_format: str = "core", days: int = 5):
    """Daily win rate trend per deck over last N days."""
    rows = db.execute(text("""
        SELECT played_at::date AS day, deck_a AS deck,
               COUNT(*) AS games,
               COUNT(*) FILTER (WHERE winner = 'deck_a') AS wins
        FROM matches
        WHERE game_format = :fmt
          AND played_at >= now() - make_interval(days => :days)
        GROUP BY played_at::date, deck_a
        ORDER BY day, deck_a
    """), {"fmt": game_format, "days": days}).fetchall()

    trend = {}
    for r in rows:
        day_str = r.day.isoformat()
        if day_str not in trend:
            trend[day_str] = {}
        trend[day_str][r.deck] = {
            "games": r.games,
            "wins": r.wins,
            "wr": round(r.wins / r.games * 100, 1) if r.games else 0,
        }
    return trend
