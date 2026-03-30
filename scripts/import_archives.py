"""
Import archive aggregates from analisidef/output/ into PostgreSQL.
Only imports metadata + aggregates (~15 KB per file), NOT the full game
logs (~3.6 GB total) which are already in the matches table.

Usage: python scripts/import_archives.py [--dry-run]
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


def import_archives(dry_run: bool = False):
    output_dir = ANALISIDEF_OUTPUT_DIR
    files = sorted(output_dir.glob("archive_*_vs_*.json"))
    print(f"Found {len(files)} archive files in {output_dir}")

    if not files:
        print("No files found. Check ANALISIDEF_OUTPUT_DIR path.")
        return

    rows = []
    skipped = 0
    for f in files:
        try:
            with open(f) as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, IOError) as e:
            print(f"  SKIP {f.name}: {e}")
            skipped += 1
            continue

        meta = data.get('metadata', {})
        aggregates = data.get('aggregates', {})

        our_deck = meta.get('our_deck', '')
        opp_deck = meta.get('opp_deck', '')
        game_format = meta.get('game_format', 'core')
        match_count = meta.get('total_games', 0)

        if not our_deck or not opp_deck:
            print(f"  SKIP {f.name}: missing deck codes")
            skipped += 1
            continue

        if not aggregates:
            print(f"  SKIP {f.name}: no aggregates")
            skipped += 1
            continue

        # Use last_updated from metadata, fallback to file mtime
        date_str = meta.get('last_updated', '')
        try:
            generated_at = date.fromisoformat(date_str) if date_str else date.today()
        except ValueError:
            generated_at = date.today()

        rows.append({
            'generated_at': generated_at,
            'game_format': game_format,
            'our_deck': our_deck,
            'opp_deck': opp_deck,
            'aggregates': json.dumps(aggregates),
            'match_count': match_count,
        })

    print(f"Parsed {len(rows)} archives, skipped {skipped}")

    if dry_run:
        print("[DRY RUN] No data written.")
        return

    db = SessionLocal()
    inserted = 0
    try:
        for row in rows:
            db.execute(
                text("""
                    INSERT INTO archives
                        (generated_at, game_format, our_deck, opp_deck, aggregates, match_count)
                    VALUES
                        (:generated_at, :game_format, :our_deck, :opp_deck, :aggregates, :match_count)
                    ON CONFLICT (game_format, our_deck, opp_deck, generated_at) DO UPDATE
                    SET aggregates = EXCLUDED.aggregates,
                        match_count = EXCLUDED.match_count
                """),
                row,
            )
            inserted += 1

        db.commit()
        print(f"Done: {inserted} archives upserted")
    finally:
        db.close()


if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    t0 = time.time()
    import_archives(dry_run=dry_run)
    print(f"Total time: {time.time() - t0:.1f}s")
