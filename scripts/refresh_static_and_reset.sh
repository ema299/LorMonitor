#!/bin/bash
# Refresh static cards DB + invalidate in-process caches (cross-process wrapper).
#
# static_importer runs as a separate python process, so calling reset_checkers()
# from inside it would only clear its own process cache — not uvicorn's. This
# wrapper curls the admin endpoint right after so the serving uvicorn picks up
# the new cards/legality state without a restart.
#
# Prerequisites:
#   - venv/bin/python present in the app tree
#   - APPTOOL_ADMIN_TOKEN env var (or /etc/apptool.env sourced with it) so the
#     admin endpoint accepts the server-to-self call
#   - uvicorn reachable on 127.0.0.1:8100
#
# Cron schedule (replaces the bare static_importer line on Sun 04:45):
#   45 4 * * 0 cd /mnt/.../App_tool && scripts/refresh_static_and_reset.sh >> /var/log/lorcana-import.log 2>&1
#
# Exit codes:
#   0 = both steps succeeded
#   1 = static_importer failed (curl skipped)
#   2 = static_importer OK but cache-reset curl failed
set -e

APP_ROOT="${APP_ROOT:-/mnt/HC_Volume_104764377/finanza/Lor/Analisi_deck/App_tool}"
ADMIN_URL="${ADMIN_URL:-http://127.0.0.1:8100/api/v1/admin}"

cd "$APP_ROOT"

# Optionally source an env file that sets APPTOOL_ADMIN_TOKEN + other secrets.
if [ -f "/etc/apptool.env" ]; then
    set -a
    # shellcheck disable=SC1091
    . /etc/apptool.env
    set +a
fi

echo "[$(date -u +%FT%TZ)] refresh_static_and_reset: running static_importer..."
if ! venv/bin/python -m backend.workers.static_importer; then
    echo "[$(date -u +%FT%TZ)] refresh_static_and_reset: static_importer FAILED — skipping cache reset" >&2
    exit 1
fi

if [ -z "${APPTOOL_ADMIN_TOKEN:-}" ]; then
    echo "[$(date -u +%FT%TZ)] refresh_static_and_reset: APPTOOL_ADMIN_TOKEN not set — skipping cache reset (uvicorn may serve stale legality until restart)" >&2
    exit 0
fi

echo "[$(date -u +%FT%TZ)] refresh_static_and_reset: resetting in-process caches..."
HTTP_CODE=$(curl -s -o /tmp/apptool_reset_resp.json -w "%{http_code}" \
    -X POST \
    -H "X-Admin-Token: $APPTOOL_ADMIN_TOKEN" \
    "$ADMIN_URL/reset-legality-cache")

if [ "$HTTP_CODE" != "200" ]; then
    echo "[$(date -u +%FT%TZ)] refresh_static_and_reset: reset-legality-cache FAILED http=$HTTP_CODE body=$(cat /tmp/apptool_reset_resp.json)" >&2
    exit 2
fi

echo "[$(date -u +%FT%TZ)] refresh_static_and_reset: OK $(cat /tmp/apptool_reset_resp.json)"
exit 0
