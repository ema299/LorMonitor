#!/usr/bin/env bash
# P0 baseline snapshot — freezes current analisidef digest + KC output as golden reference
# before any migration work. Tarball lives under backups/golden/.
set -euo pipefail

APP_TOOL=/mnt/HC_Volume_104764377/finanza/Lor/Analisi_deck/App_tool
ANALISIDEF=/mnt/HC_Volume_104764377/finanza/Lor/Analisi_deck/analisidef
OUT_DIR="$APP_TOOL/backups/golden"
STAMP=$(date -u +%Y%m%d_%H%M%SZ)
TARBALL="$OUT_DIR/kc_baseline_${STAMP}.tar.gz"
SHA_FILE="$OUT_DIR/kc_baseline_${STAMP}.sha"

mkdir -p "$OUT_DIR"

{
  echo "# KC baseline $STAMP"
  echo "## App_tool git"
  cd "$APP_TOOL"
  echo "branch: $(git rev-parse --abbrev-ref HEAD)"
  echo "sha:    $(git rev-parse HEAD)"
  echo "status:"
  git status --porcelain || true
  echo
  echo "## analisidef git"
  cd "$ANALISIDEF"
  echo "branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'N/A')"
  echo "sha:    $(git rev-parse HEAD 2>/dev/null || echo 'N/A')"
  echo "status:"
  git status --porcelain 2>/dev/null || echo "(not a git repo)"
} > "$SHA_FILE"

cd "$ANALISIDEF"
tar -czf "$TARBALL" \
  output/digest_*.json \
  output/killer_curves_*.json \
  2>/dev/null

echo "baseline written:"
echo "  $TARBALL ($(du -h "$TARBALL" | awk '{print $1}'))"
echo "  $SHA_FILE"
echo
echo "contents:"
tar -tzf "$TARBALL" | wc -l | xargs echo "  files:"
