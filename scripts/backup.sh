#!/bin/bash
# Daily backup: pg_dump lorcana DB, compress, keep 7 days
BACKUP_DIR="/mnt/HC_Volume_104764377/backups/lorcana"
DATE=$(date +%Y%m%d_%H%M)
BACKUP_FILE="$BACKUP_DIR/lorcana_$DATE.sql.gz"

# Dump and compress
su - postgres -c "pg_dump lorcana" | gzip > "$BACKUP_FILE"

# Verify
if [ -s "$BACKUP_FILE" ]; then
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "$(date): Backup OK — $BACKUP_FILE ($SIZE)"
else
    echo "$(date): BACKUP FAILED — empty file"
    exit 1
fi

# Cleanup: keep only last 7 days
find "$BACKUP_DIR" -name "lorcana_*.sql.gz" -mtime +7 -delete
echo "$(date): Cleanup done — $(ls $BACKUP_DIR/lorcana_*.sql.gz | wc -l) backups retained"
