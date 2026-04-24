#!/usr/bin/env bash
# Deck-refactor copy-rule linter.
# Enforces docs/DECK_REFACTOR_PARITY.md Rule 1 — observed, not personal.
# Fails the merge gate if any tracked file contains forbidden first-person
# copy addressed to the user (the Deck tab reads only archetype-level
# observed data — no personal stats).
#
# Usage:  scripts/check_deck_copy.sh
# Exit 0 clean, exit 1 on any violation.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

TARGETS=(
  "frontend_v3/assets/js/dashboard/honesty_badge.js"
  "frontend_v3/assets/js/dashboard/deck_recommendation_engine.js"
  "frontend_v3/assets/js/dashboard/deck_summary.js"
  "frontend_v3/assets/js/dashboard/deck_improve.js"
  "frontend_v3/assets/js/dashboard/deck_matchups.js"
  "frontend_v3/assets/js/dashboard/deck_list_view.js"
  "frontend_v3/assets/js/dashboard/matchup_workspace.js"
  "frontend_v3/assets/js/dashboard/builder_workspace.js"
  "frontend_v3/assets/js/dashboard/builder_status.js"
  "frontend_v3/assets/js/views/deck.js"
)

FORBIDDEN=(
  'Your deck'
  'You should'
  'You are weak'
  'Your performance'
  'Your win'
  'Personal Leak'
)

fails=0
checked=0

for file in "${TARGETS[@]}"; do
  path="$ROOT/$file"
  [ -f "$path" ] || continue
  checked=$((checked + 1))
  for pat in "${FORBIDDEN[@]}"; do
    # Skip lines that are comments (// ...) — commentary is allowed to
    # cite forbidden forms when explaining the rule.
    hits=$(grep -n -E "$pat" "$path" | grep -v -E '^[^:]+:[0-9]+:[[:space:]]*//' || true)
    if [ -n "$hits" ]; then
      echo "FAIL: forbidden copy '$pat' in $file"
      echo "$hits"
      echo ""
      fails=$((fails + 1))
    fi
  done
done

if [ "$fails" -gt 0 ]; then
  echo "$fails copy rule violation(s) across $checked tracked file(s)."
  echo "See docs/DECK_REFACTOR_PARITY.md Rule 1."
  exit 1
fi

echo "OK — copy rule clean across $checked tracked file(s)."
