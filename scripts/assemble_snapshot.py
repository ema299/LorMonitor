"""
Assemble dashboard snapshot from PostgreSQL and store in daily_snapshots.

This replaces import_snapshot.py (which reads from analisidef's dashboard_data.json).
All data is computed directly from PG — no dependency on daily_routine.py.

Usage: python scripts/assemble_snapshot.py [--dry-run] [--days N]
"""
import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from backend.models import SessionLocal
from backend.services.snapshot_assembler import assemble


def main():
    parser = argparse.ArgumentParser(description="Assemble dashboard snapshot from PG")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--days", type=int, default=2, help="Analysis window in days")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        t0 = time.time()
        blob = assemble(db, days=args.days)
        elapsed = time.time() - t0

        size_kb = len(json.dumps(blob)) / 1024
        print(f"Assembled in {elapsed:.1f}s — {size_kb:.0f} KB, {len(blob)} sections")

        for key, val in blob.items():
            if isinstance(val, dict):
                print(f"  {key}: {len(val)} keys")
            elif isinstance(val, list):
                print(f"  {key}: {len(val)} items")
            else:
                print(f"  {key}: {type(val).__name__}")

        if args.dry_run:
            print("\nDry run — not saved.")
            return

        today = date.today()
        db.execute(text("""
            INSERT INTO daily_snapshots (snapshot_date, perimeter, data)
            VALUES (:date, 'full', :data)
            ON CONFLICT (snapshot_date, perimeter)
            DO UPDATE SET data = EXCLUDED.data
        """), {"date": today, "data": json.dumps(blob)})
        db.commit()
        print(f"\nSaved to daily_snapshots (date={today}, perimeter='full')")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
