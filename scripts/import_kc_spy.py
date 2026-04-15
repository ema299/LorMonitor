"""Import kc_spy_report.json into PostgreSQL for dashboard runtime."""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from backend.models import SessionLocal

KC_SPY_PATH = Path(
    "/mnt/HC_Volume_104764377/finanza/Lor/Analisi_deck/analisidef/output/kc_spy_report.json"
)


def import_kc_spy(dry_run: bool = False) -> int:
    if not KC_SPY_PATH.is_file():
        print(f"Missing file: {KC_SPY_PATH}")
        return 1

    with open(KC_SPY_PATH) as fh:
        report = json.load(fh)

    try:
        report_date = date.fromisoformat(report.get("date", ""))
    except ValueError:
        report_date = date.today()

    ts_raw = report.get("timestamp")
    generated_at = None
    if ts_raw:
        try:
            generated_at = datetime.fromisoformat(ts_raw)
        except ValueError:
            generated_at = None

    row = {
        "report_date": report_date,
        "generated_at": generated_at,
        "report": json.dumps(report),
        "status": report.get("status"),
    }

    print(f"Parsed KC Spy report for {report_date.isoformat()} status={row['status']}")
    if dry_run:
        print("[DRY RUN] No data written.")
        return 0

    db = SessionLocal()
    try:
        db.execute(
            text(
                """
                INSERT INTO kc_spy_reports
                    (report_date, generated_at, report, status)
                VALUES
                    (:report_date, :generated_at, CAST(:report AS jsonb), :status)
                ON CONFLICT (report_date) DO UPDATE
                SET generated_at = EXCLUDED.generated_at,
                    report = EXCLUDED.report,
                    status = EXCLUDED.status,
                    imported_at = now()
                """
            ),
            row,
        )
        db.commit()
        print("Done: 1 kc_spy report upserted")
        return 0
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    t0 = time.time()
    rc = import_kc_spy(dry_run=args.dry_run)
    print(f"Total time: {time.time() - t0:.1f}s")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
