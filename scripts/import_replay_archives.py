"""Import full replay archives into PostgreSQL for the replay viewer.

Unlike `scripts/import_archives.py`, this stores the full `games` payload so
`/api/replay/list` and `/api/replay/game` no longer depend on filesystem JSON.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from backend.config import ANALISIDEF_OUTPUT_DIR
from backend.models import SessionLocal
from backend.services.replay_archive_service import normalize_deck_code


def _iter_files(limit: int | None) -> list[Path]:
    files = sorted(ANALISIDEF_OUTPUT_DIR.glob("archive_*_vs_*.json"))
    if limit is not None:
        files = files[:limit]
    return files


def import_replay_archives(
    dry_run: bool = False,
    limit: int | None = None,
    batch_size: int = 10,
) -> int:
    files = _iter_files(limit)
    print(f"Found {len(files)} replay archives in {ANALISIDEF_OUTPUT_DIR}")

    rows = []
    skipped = 0
    for path in files:
        try:
            with open(path) as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"  SKIP {path.name}: {exc}")
            skipped += 1
            continue

        meta = data.get("metadata") or {}
        games = data.get("games") or []
        our_deck = normalize_deck_code(meta.get("our_deck", ""))
        opp_deck = normalize_deck_code(meta.get("opp_deck", ""))
        game_format = meta.get("game_format", "core")

        if not our_deck or not opp_deck:
            print(f"  SKIP {path.name}: missing deck codes")
            skipped += 1
            continue
        if not isinstance(games, list):
            print(f"  SKIP {path.name}: games is not a list")
            skipped += 1
            continue

        try:
            generated_at = date.fromisoformat(meta.get("last_updated", ""))
        except ValueError:
            generated_at = date.today()

        rows.append(
            {
                "generated_at": generated_at,
                "game_format": game_format,
                "our_deck": our_deck,
                "opp_deck": opp_deck,
                "metadata": json.dumps(meta),
                "games": json.dumps(games),
                "match_count": meta.get("total_games", len(games)),
            }
        )

    print(f"Parsed {len(rows)} replay archives, skipped {skipped}")
    if dry_run:
        print("[DRY RUN] No data written.")
        return len(rows)

    db = SessionLocal()
    inserted = 0
    try:
        for i, row in enumerate(rows, start=1):
            db.execute(
                text(
                    """
                    INSERT INTO replay_archives
                        (generated_at, game_format, our_deck, opp_deck, metadata, games, match_count)
                    VALUES
                        (:generated_at, :game_format, :our_deck, :opp_deck, CAST(:metadata AS jsonb), CAST(:games AS jsonb), :match_count)
                    ON CONFLICT (game_format, our_deck, opp_deck, generated_at) DO UPDATE
                    SET metadata = EXCLUDED.metadata,
                        games = EXCLUDED.games,
                        match_count = EXCLUDED.match_count,
                        imported_at = now()
                    """
                ),
                row,
            )
            inserted += 1
            if inserted % batch_size == 0:
                db.commit()
                print(f"  committed {inserted}/{len(rows)}", flush=True)
        db.commit()
        print(f"Done: {inserted} replay archives upserted")
        return inserted
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=10)
    args = parser.parse_args()

    t0 = time.time()
    count = import_replay_archives(
        dry_run=args.dry_run,
        limit=args.limit,
        batch_size=args.batch_size,
    )
    print(f"Total time: {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
