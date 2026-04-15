#!/usr/bin/env python3
"""CLI orchestrator for the native blind playbook generator (Sprint-1 Mossa B).

Replaces `scripts/import_playbooks.py` (bridge reading JSON produced by
analisidef) with native generation via pipelines.playbook.generator. For every
(deck, format) selected, calls `generate_playbook` then persists the payload
via `playbook_service.upsert_playbook`.

Usage:
    # All decks, core format
    python3 scripts/generate_playbooks.py --format core

    # Single deck dry-run (aggregator only, no OpenAI call)
    python3 scripts/generate_playbooks.py --deck RS --format core --dry-run

    # Full batch (all decks, both formats)
    python3 scripts/generate_playbooks.py --format all

    # Dump prompt (dry-run implies no LLM; --print-prompt shows the built prompt)
    python3 scripts/generate_playbooks.py --deck RS --format core --dry-run --print-prompt

Exit code: 0 on success, 1 if any (deck, format) produced an error.

Typical cost: ~$0.02 per deck/format with gpt-5.4-mini (~$0.20/week for the
full 12x2 batch).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Add project root to path so backend.* + pipelines.* + lib.* are importable.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from pipelines.playbook.generator import (
    DECK_COLORS,
    build_narrative_prompt,
    generate_playbook,
    aggregate_playbook,
    load_deck_digests,
    load_pro_references,
)

DECKS = sorted(DECK_COLORS.keys())


def _run_one(deck, game_format, model, dry_run, print_prompt):
    """Run a single (deck, format). Returns (ok, summary_dict, err_str|None)."""
    t0 = time.time()
    try:
        if print_prompt:
            digests = load_deck_digests(deck, game_format)
            aggregated = aggregate_playbook(digests)
            pro_refs = load_pro_references(deck, game_format)
            prompt = build_narrative_prompt(deck, game_format, aggregated, pro_refs)
            print("--- PROMPT START ---")
            print(prompt)
            print("--- PROMPT END ---")

        result = generate_playbook(
            deck, game_format=game_format, use_llm=not dry_run, model=model,
        )
    except Exception as e:
        return False, None, str(e)

    elapsed = time.time() - t0
    meta = result.get("meta", {}) or {}
    pb = result.get("playbook") or {}
    status = "OK"
    if dry_run:
        status = "DRY"
    elif not pb:
        status = "ERR:empty"
    elif pb.get("error"):
        status = f"ERR:{pb.get('error')}"

    summary = {
        "deck": deck,
        "format": game_format,
        "status": status,
        "digests": meta.get("digest_count", 0),
        "games": meta.get("total_games", 0),
        "cost": meta.get("estimated_cost_usd", 0) or 0,
        "elapsed": round(elapsed, 1),
    }
    return True, {"summary": summary, "result": result}, None


def main():
    p = argparse.ArgumentParser(description="Generate blind deck playbooks (native)")
    p.add_argument("--deck", help="Single deck sigla (RS, ES, ...). Omit for all.")
    p.add_argument("--format", choices=("core", "infinity", "all"), default="all",
                   help="Game format. 'all' runs both core and infinity.")
    p.add_argument("--model", default="gpt-5.4-mini")
    p.add_argument("--dry-run", action="store_true",
                   help="Skip OpenAI call and DB write; run aggregator only.")
    p.add_argument("--print-prompt", action="store_true",
                   help="Print the narrative prompt built for each (deck, format). Useful for QA.")
    p.add_argument("--no-db", action="store_true",
                   help="Skip DB upsert even when LLM ran (stdout only).")
    args = p.parse_args()

    if args.deck and args.deck not in DECK_COLORS:
        print(f"ERR: unknown deck '{args.deck}'. Valid: {DECKS}", file=sys.stderr)
        sys.exit(2)

    formats = ["core", "infinity"] if args.format == "all" else [args.format]
    decks = [args.deck] if args.deck else DECKS

    # Lazy DB import so --dry-run works even without backend deps in the path.
    db = None
    upsert_playbook = None
    if not args.dry_run and not args.no_db:
        from backend.models import SessionLocal
        from backend.services.playbook_service import upsert_playbook as _upsert
        upsert_playbook = _upsert
        db = SessionLocal()

    print(f"Batch blind playbook — {len(decks)} deck(s) x {len(formats)} format(s)")
    print(f"Model: {args.model} | dry_run={args.dry_run} | no_db={args.no_db}")
    print("=" * 60)

    ok_count = 0
    err_count = 0
    total_cost = 0.0
    total_elapsed = 0.0
    results = []

    try:
        for fmt in formats:
            print(f"\n--- {fmt.upper()} ---")
            for deck in decks:
                ok, payload, err = _run_one(
                    deck, fmt, args.model, args.dry_run, args.print_prompt,
                )
                if not ok:
                    err_count += 1
                    print(f"  [ERR] {deck}: {err}")
                    continue

                summary = payload["summary"]
                result = payload["result"]
                total_cost += summary["cost"]
                total_elapsed += summary["elapsed"]

                if summary["status"].startswith("ERR"):
                    err_count += 1
                else:
                    ok_count += 1

                print(f"  [{summary['status']}] {deck}: digests={summary['digests']} "
                      f"games={summary['games']} | {summary['elapsed']}s ${summary['cost']}")

                # Upsert in DB if we ran the LLM path successfully.
                if (
                    db is not None
                    and not summary["status"].startswith("ERR")
                    and result.get("playbook")
                    and not result["playbook"].get("error")
                ):
                    try:
                        row_id = upsert_playbook(db, deck, fmt, result)
                        print(f"       -> upserted row id={row_id}")
                    except Exception as e:
                        err_count += 1
                        print(f"       -> DB upsert FAILED: {e}")
                        db.rollback()

                results.append(summary)
    finally:
        if db is not None:
            db.close()

    print("\n" + "=" * 60)
    print(f"Completed: {ok_count} OK, {err_count} error(s)")
    print(f"Total time: {total_elapsed:.0f}s")
    print(f"Estimated cost: ${total_cost:.2f}")

    sys.exit(0 if err_count == 0 else 1)


if __name__ == "__main__":
    main()
