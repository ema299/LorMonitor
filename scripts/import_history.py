"""
Import history.db (SQLite) from analisidef/daily/output/ into PostgreSQL daily_snapshots.
Reads from analisidef data without modifying it.

Usage: python scripts/import_history.py [--dry-run]
"""
import json
import sqlite3
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from backend.models import SessionLocal
from backend.config import ANALISIDEF_DAILY_DIR


def import_history(dry_run: bool = False):
    history_db = ANALISIDEF_DAILY_DIR / "history.db"
    print(f"Reading {history_db} ...")

    if not history_db.exists():
        print(f"ERROR: {history_db} not found")
        return

    conn = sqlite3.connect(str(history_db))
    conn.row_factory = sqlite3.Row

    # Check available tables
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print(f"SQLite tables: {tables}")

    # Strategy: import daily_snapshot table as-is (has full JSON snapshots),
    # and also aggregate other tables into per-date/perimeter snapshots.

    rows = []

    # 1. Import daily_snapshot table (pre-computed full snapshots)
    if 'daily_snapshot' in tables:
        cursor = conn.execute("SELECT date, json_data FROM daily_snapshot ORDER BY date")
        for row in cursor:
            snapshot_date = row['date']
            try:
                data = json.loads(row['json_data']) if isinstance(row['json_data'], str) else row['json_data']
            except (json.JSONDecodeError, TypeError):
                continue

            rows.append({
                'snapshot_date': snapshot_date,
                'perimeter': 'full',
                'data': json.dumps(data),
            })

    # 2. Import daily_meta as per-date snapshots
    if 'daily_meta' in tables:
        cursor = conn.execute("""
            SELECT date, perimeter,
                   json_group_array(json_object(
                       'deck', deck, 'wins', wins, 'losses', losses,
                       'games', games, 'wr', wr, 'meta_share', meta_share
                   )) as entries
            FROM daily_meta
            GROUP BY date, perimeter
            ORDER BY date
        """)
        for row in cursor:
            rows.append({
                'snapshot_date': row['date'],
                'perimeter': f"meta_{row['perimeter']}",
                'data': row['entries'],
            })

    # 3. Import daily_matchups
    if 'daily_matchups' in tables:
        cursor = conn.execute("""
            SELECT date, perimeter,
                   json_group_array(json_object(
                       'deck', deck, 'vs_deck', vs_deck, 'wins', wins,
                       'total', total, 'wr', wr
                   )) as entries
            FROM daily_matchups
            GROUP BY date, perimeter
            ORDER BY date
        """)
        for row in cursor:
            rows.append({
                'snapshot_date': row['date'],
                'perimeter': f"matchups_{row['perimeter']}",
                'data': row['entries'],
            })

    # 4. Import daily_pro
    if 'daily_pro' in tables:
        cursor = conn.execute("""
            SELECT date,
                   json_group_array(json_object(
                       'player', player, 'deck', deck, 'wins', wins,
                       'losses', losses, 'wr', wr
                   )) as entries
            FROM daily_pro
            GROUP BY date
            ORDER BY date
        """)
        for row in cursor:
            rows.append({
                'snapshot_date': row['date'],
                'perimeter': 'pro_players',
                'data': row['entries'],
            })

    conn.close()
    print(f"Parsed {len(rows)} snapshot entries")

    if dry_run:
        print("[DRY RUN] No data written.")
        return

    db = SessionLocal()
    inserted = 0
    try:
        for row in rows:
            db.execute(
                text("""
                    INSERT INTO daily_snapshots (snapshot_date, perimeter, data)
                    VALUES (:snapshot_date, :perimeter, :data)
                    ON CONFLICT (snapshot_date, perimeter) DO UPDATE
                    SET data = EXCLUDED.data
                """),
                row,
            )
            inserted += 1

        db.commit()
        print(f"Done: {inserted} snapshots upserted")
    finally:
        db.close()


if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    t0 = time.time()
    import_history(dry_run=dry_run)
    print(f"Total time: {time.time() - t0:.1f}s")
