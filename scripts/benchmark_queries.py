"""
Benchmark critical queries against PostgreSQL.
Verifies performance targets from ARCHITECTURE.md §5.4.

Usage: python scripts/benchmark_queries.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from backend.models import SessionLocal


def benchmark(db, name: str, query: str, target_ms: float):
    """Run a query, measure time, compare to target."""
    t0 = time.perf_counter()
    result = db.execute(text(query))
    rows = result.fetchall()
    elapsed_ms = (time.perf_counter() - t0) * 1000

    status = "PASS" if elapsed_ms < target_ms else "SLOW"
    print(f"  [{status}] {name}")
    print(f"         Time: {elapsed_ms:.1f}ms (target: <{target_ms}ms)")
    print(f"         Rows: {len(rows)}")
    return elapsed_ms, target_ms, status


def main():
    db = SessionLocal()
    print("=" * 60)
    print("BENCHMARK — Query Performance")
    print("=" * 60)

    results = []

    # 1. Matchup query: WR for specific matchup, last 2 days
    results.append(benchmark(db,
        "Matchup query (2 days, 1 matchup)",
        """
        SELECT deck_a, deck_b, COUNT(*) as games,
               COUNT(*) FILTER (WHERE winner = 'deck_a') as wins
        FROM matches
        WHERE game_format = 'core'
          AND deck_a = 'AmSa' AND deck_b = 'EmSa'
          AND played_at >= now() - INTERVAL '7 days'
        GROUP BY deck_a, deck_b
        """,
        target_ms=50,
    ))

    # 2. Full matchup matrix 12x12
    results.append(benchmark(db,
        "Matchup matrix (all decks, 7 days)",
        """
        SELECT deck_a, deck_b, COUNT(*) as games,
               COUNT(*) FILTER (WHERE winner = 'deck_a') as wins_a,
               AVG(total_turns) as avg_turns
        FROM matches
        WHERE game_format = 'core'
          AND played_at >= now() - INTERVAL '7 days'
        GROUP BY deck_a, deck_b
        """,
        target_ms=500,
    ))

    # 3. Killer curves lookup (current)
    results.append(benchmark(db,
        "Killer curves lookup (current)",
        """
        SELECT our_deck, opp_deck, curves, match_count
        FROM killer_curves
        WHERE game_format = 'core'
          AND our_deck = 'AmSa'
          AND opp_deck = 'EmSa'
          AND is_current = true
        """,
        target_ms=10,
    ))

    # 4. Meta share (top decks)
    results.append(benchmark(db,
        "Meta share (all decks, last 7 days)",
        """
        SELECT deck_a as deck, COUNT(*) as games,
               COUNT(*) FILTER (WHERE winner = 'deck_a') as wins
        FROM matches
        WHERE game_format = 'core'
          AND played_at >= now() - INTERVAL '7 days'
        GROUP BY deck_a
        ORDER BY games DESC
        """,
        target_ms=200,
    ))

    # 5. Top players by win rate
    results.append(benchmark(db,
        "Top players (win rate, last 7 days)",
        """
        SELECT player_a_name as player, deck_a as deck,
               COUNT(*) as games,
               COUNT(*) FILTER (WHERE winner = 'deck_a') as wins
        FROM matches
        WHERE game_format = 'core'
          AND played_at >= now() - INTERVAL '7 days'
          AND player_a_mmr >= 1500
        GROUP BY player_a_name, deck_a
        HAVING COUNT(*) >= 3
        ORDER BY COUNT(*) FILTER (WHERE winner = 'deck_a')::float / COUNT(*) DESC
        LIMIT 70
        """,
        target_ms=200,
    ))

    # 6. Daily snapshots lookup
    results.append(benchmark(db,
        "Snapshot lookup (last 30 days)",
        """
        SELECT snapshot_date, perimeter, data
        FROM daily_snapshots
        WHERE snapshot_date >= now() - INTERVAL '30 days'
        ORDER BY snapshot_date DESC
        """,
        target_ms=100,
    ))

    # Summary
    print("\n" + "=" * 60)
    passed = sum(1 for _, _, s in results if s == "PASS")
    total = len(results)
    print(f"RESULTS: {passed}/{total} passed")

    if passed == total:
        print("All queries within target! Database is ready.")
    else:
        print("Some queries are slow. Consider adding data or tuning indexes.")

    # Refresh materialized views
    print("\nRefreshing materialized views...")
    t0 = time.perf_counter()
    db.execute(text("REFRESH MATERIALIZED VIEW mv_meta_share"))
    db.execute(text("REFRESH MATERIALIZED VIEW mv_matchup_matrix"))
    db.commit()
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"  Materialized views refreshed in {elapsed:.1f}ms")

    db.close()


if __name__ == '__main__':
    main()
