#!/bin/bash
# Sync dashboard.html from analisidef → App_tool
# Copies the HTML but replaces the data loading to use the API.
#
# What it does:
#   1. Takes the HTML from analisidef (template, no embedded data)
#   2. Replaces loadData() to fetch from /api/v1/dashboard-data
#   3. Strips any _EMBEDDED_DATA blob if present (daily_routine output)
#
# Usage: bash scripts/sync_dashboard.sh [--dry-run]

set -e

SRC="/mnt/HC_Volume_104764377/finanza/Lor/Analisi_deck/analisidef/daily/dashboard.html"
DST="/mnt/HC_Volume_104764377/finanza/Lor/Analisi_deck/App_tool/frontend/dashboard.html"
DRY_RUN=""

if [ "$1" = "--dry-run" ]; then
    DRY_RUN=1
    echo "[DRY RUN]"
fi

if [ ! -f "$SRC" ]; then
    echo "ERROR: Source not found: $SRC"
    exit 1
fi

echo "Source: $SRC ($(du -h "$SRC" | cut -f1))"

# Find the loadData function boundaries
LOAD_DATA_LINE=$(grep -n "^async function loadData" "$SRC" | head -1 | cut -d: -f1)
INIT_FORMAT_LINE=$(grep -n "^function initFormat" "$SRC" | head -1 | cut -d: -f1)

if [ -z "$LOAD_DATA_LINE" ] || [ -z "$INIT_FORMAT_LINE" ]; then
    echo "ERROR: Could not find loadData/initFormat boundaries"
    echo "  loadData line: ${LOAD_DATA_LINE:-NOT FOUND}"
    echo "  initFormat line: ${INIT_FORMAT_LINE:-NOT FOUND}"
    exit 1
fi

# Check if there's an _EMBEDDED_DATA blob line right before loadData
BLOB_LINE=$(grep -n "^const _EMBEDDED_DATA" "$SRC" | head -1 | cut -d: -f1)
if [ -n "$BLOB_LINE" ]; then
    START_CUT=$BLOB_LINE
    echo "Found embedded blob at line $BLOB_LINE — will strip"
else
    START_CUT=$LOAD_DATA_LINE
fi

echo "Replacing lines $START_CUT-$((INIT_FORMAT_LINE - 1)) with API-based loadData()"

# The replacement loadData
API_LOAD_DATA='// === LOAD DATA (from API, no embedded blob) ===
async function loadData() {
  try {
    const resp = await fetch('"'"'/api/v1/dashboard-data'"'"');
    if (!resp.ok) throw new Error(`API error: ${resp.status}`);
    DATA = await resp.json();
  } catch(e) {
    console.error('"'"'Failed to load dashboard data:'"'"', e);
    document.getElementById('"'"'main-content'"'"').innerHTML =
      '"'"'<div class="card" style="text-align:center;padding:40px"><h2>Loading error</h2><p>Could not fetch dashboard data from API. Please try again later.</p></div>'"'"';
    return;
  }
  initKPI();
  initFormat();
  render();
}
'

if [ -n "$DRY_RUN" ]; then
    TOTAL=$(wc -l < "$SRC")
    BEFORE=$((START_CUT - 1))
    AFTER=$((TOTAL - INIT_FORMAT_LINE + 1))
    REMOVED=$((INIT_FORMAT_LINE - START_CUT))
    echo "  Lines before: $BEFORE"
    echo "  Lines removed: $REMOVED (loadData + any blob)"
    echo "  Lines after: $AFTER"
    echo "  Result: ~$((BEFORE + 17 + AFTER)) lines"
else
    # Backup current
    cp "$DST" "${DST}.bak" 2>/dev/null || true

    # Build: before + API loadData + after
    {
        head -$((START_CUT - 1)) "$SRC"
        echo "$API_LOAD_DATA"
        tail -n +$INIT_FORMAT_LINE "$SRC"
    } > "$DST"

    echo "Done: $(du -h "$DST" | cut -f1) (backup: ${DST}.bak)"
fi
