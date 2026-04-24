"""Backfill derived public-log features from matches.turns."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from backend.models import SessionLocal
from backend.models.match import Match
from backend.services.match_log_features_service import upsert_match_log_features

BATCH_SIZE = 100


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true", help="Recompute even when a feature row already exists")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    where = [
        "turns IS NOT NULL",
        "jsonb_typeof(turns) = 'array'",
        "jsonb_array_length(turns) > 0",
    ]
    if not args.force:
        where.append("id NOT IN (SELECT match_id FROM match_log_features)")
    params = {}
    if args.days is not None:
        where.append("played_at >= now() - make_interval(days => :days)")
        params["days"] = args.days
    limit_sql = ""
    if args.limit is not None:
        limit_sql = " LIMIT :lim"
        params["lim"] = args.limit

    ids = [
        row[0]
        for row in db.execute(
            text(
                f"""
                SELECT id
                FROM matches
                WHERE {' AND '.join(where)}
                ORDER BY played_at DESC
                {limit_sql}
                """
            ),
            params,
        ).fetchall()
    ]

    scanned = 0
    upserted = 0
    for start in range(0, len(ids), BATCH_SIZE):
        batch_ids = ids[start:start + BATCH_SIZE]
        matches = db.query(Match).filter(Match.id.in_(batch_ids)).all()
        for match in matches:
            scanned += 1
            upsert_match_log_features(db, match)
            upserted += 1
        if not args.dry_run:
            db.commit()
        else:
            db.rollback()

    db.close()
    print(
        {
            "scanned": scanned,
            "upserted": upserted,
            "dry_run": args.dry_run,
            "force": args.force,
        }
    )


if __name__ == "__main__":
    main()
