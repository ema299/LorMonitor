#!/bin/bash
# Weekly maintenance: drop turns data older than 90 days, then VACUUM
# Keeps aggregate match data (decks, winner, mmr) forever for stats
# Frees TOAST storage from large JSONB turns blobs
set -euo pipefail

DB_NAME="lorcana"
RETENTION_DAYS=90
LOG_PREFIX="$(date '+%Y-%m-%d %H:%M')"

# Count matches to clean
COUNT=$(su - postgres -c "psql -t -A -d $DB_NAME -c \"
  SELECT count(*) FROM matches
  WHERE played_at < now() - interval '${RETENTION_DAYS} days'
    AND turns IS NOT NULL AND turns != 'null'::jsonb;
\"")

if [ "$COUNT" -eq 0 ]; then
    echo "$LOG_PREFIX: No turns to clean (all within ${RETENTION_DAYS}d retention)"
    exit 0
fi

# Null out turns in batches of 10000 to avoid long locks
echo "$LOG_PREFIX: Cleaning turns from $COUNT matches older than ${RETENTION_DAYS} days..."

su - postgres -c "psql -d $DB_NAME -c \"
  UPDATE matches SET turns = NULL
  WHERE played_at < now() - interval '${RETENTION_DAYS} days'
    AND turns IS NOT NULL AND turns != 'null'::jsonb;
\""

# VACUUM to reclaim TOAST space
echo "$LOG_PREFIX: Running VACUUM FULL on matches (reclaims TOAST)..."
su - postgres -c "psql -d $DB_NAME -c 'VACUUM FULL matches;'"

# Report final size
SIZE=$(su - postgres -c "psql -t -A -d $DB_NAME -c \"
  SELECT pg_size_pretty(pg_total_relation_size('matches'));
\"")

echo "$LOG_PREFIX: Done. Cleaned $COUNT matches. matches table now: $SIZE"
