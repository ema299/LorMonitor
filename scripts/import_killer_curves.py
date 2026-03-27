"""
Import killer_curves JSON files from analisidef/output/ into PostgreSQL.
Reads from analisidef data without modifying it.

Usage: python scripts/import_killer_curves.py [--dry-run]
"""
import json
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from backend.models import SessionLocal
from backend.config import ANALISIDEF_OUTPUT_DIR


def import_killer_curves(dry_run: bool = False):
    output_dir = ANALISIDEF_OUTPUT_DIR
    pattern = "killer_curves_*.json"
    files = sorted(output_dir.glob(pattern))
    print(f"Found {len(files)} killer_curves files in {output_dir}")

    if not files:
        print("No files found. Check ANALISIDEF_OUTPUT_DIR path.")
        return

    rows = []
    for f in files:
        try:
            with open(f) as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, IOError) as e:
            print(f"  SKIP {f.name}: {e}")
            continue

        meta = data.get('metadata', {})
        curves = data.get('curves', [])

        our_deck = meta.get('our_deck', '')
        opp_deck = meta.get('opp_deck', '')
        date_str = meta.get('date', '')
        match_count = meta.get('based_on_games', 0)
        loss_count = meta.get('based_on_losses', 0)

        if not our_deck or not opp_deck:
            print(f"  SKIP {f.name}: missing deck codes")
            continue

        try:
            generated_at = date.fromisoformat(date_str) if date_str else date.today()
        except ValueError:
            generated_at = date.today()

        rows.append({
            'generated_at': generated_at,
            'game_format': 'core',
            'our_deck': our_deck,
            'opp_deck': opp_deck,
            'curves': json.dumps(curves),
            'match_count': match_count,
            'loss_count': loss_count,
            'is_current': True,
        })

    print(f"Parsed {len(rows)} killer_curves entries")

    if dry_run:
        print("[DRY RUN] No data written.")
        return

    db = SessionLocal()
    inserted = 0
    try:
        for row in rows:
            db.execute(
                text("""
                    INSERT INTO killer_curves
                        (generated_at, game_format, our_deck, opp_deck, curves,
                         match_count, loss_count, is_current)
                    VALUES
                        (:generated_at, :game_format, :our_deck, :opp_deck, :curves,
                         :match_count, :loss_count, :is_current)
                    ON CONFLICT (game_format, our_deck, opp_deck, generated_at) DO UPDATE
                    SET curves = EXCLUDED.curves,
                        match_count = EXCLUDED.match_count,
                        loss_count = EXCLUDED.loss_count,
                        is_current = EXCLUDED.is_current
                """),
                row,
            )
            inserted += 1

        db.commit()
        print(f"Done: {inserted} killer_curves upserted")
    finally:
        db.close()


if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    t0 = time.time()
    import_killer_curves(dry_run=dry_run)
    print(f"Total time: {time.time() - t0:.1f}s")
