"""
Import dashboard_data.json from analisidef → daily_snapshots table (perimeter='full').

This feeds /api/v1/dashboard-data which the frontend fetches on load.
Run after daily_routine.py generates the JSON.

Usage: python scripts/import_snapshot.py [--dry-run]
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from backend.config import ANALISIDEF_DAILY_DIR
from backend.models import SessionLocal

DASHBOARD_JSON = ANALISIDEF_DAILY_DIR / "dashboard_data.json"


def import_snapshot(dry_run: bool = False):
    if not DASHBOARD_JSON.exists():
        print(f"ERROR: {DASHBOARD_JSON} not found")
        sys.exit(1)

    with open(DASHBOARD_JSON) as f:
        data = json.load(f)

    today = date.today()
    size_kb = DASHBOARD_JSON.stat().st_size / 1024

    print(f"Snapshot: {DASHBOARD_JSON} ({size_kb:.0f} KB)")
    print(f"Date: {today}")
    print(f"Top-level keys: {len(data)}")

    if dry_run:
        print("Dry run — no changes made.")
        return

    db = SessionLocal()
    try:
        db.execute(text("""
            INSERT INTO daily_snapshots (snapshot_date, perimeter, data)
            VALUES (:date, 'full', :data)
            ON CONFLICT (snapshot_date, perimeter)
            DO UPDATE SET data = EXCLUDED.data
        """), {"date": today, "data": json.dumps(data)})
        db.commit()
        print(f"Imported snapshot for {today} (perimeter='full')")
    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    import_snapshot(dry_run=dry_run)
