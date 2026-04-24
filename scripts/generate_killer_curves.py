#!/usr/bin/env python3
"""Native killer curves generator for App_tool (Sprint P2 — D2 cutover).

Reads digest from App_tool/output/digests/ (PG-first), calls OpenAI,
upserts directly into PG killer_curves table.

Replaces the analisidef bridge: run_kc_production.py → import_killer_curves.py.

Usage:
    # All unstable matchups, core format
    python3 scripts/generate_killer_curves.py --format core

    # Single matchup
    python3 scripts/generate_killer_curves.py --pair AmSa AbE --format core

    # Full batch (all formats, force regenerate all)
    python3 scripts/generate_killer_curves.py --format all --force

    # Dry run (build prompt, don't call OpenAI)
    python3 scripts/generate_killer_curves.py --format core --dry-run

Exit code: 0 on success, 1 if any matchup failed.

Typical cost: ~$0.02-0.05 per matchup with gpt-5.4-mini (~$1-3/week full batch).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from openai import OpenAI  # noqa: E402

from pipelines.kc.build_prompt import DECK_COLORS, build_prompt  # noqa: E402
from pipelines.kc.vendored.stability import (  # noqa: E402
    DECKS,
    MIN_LOSSES,
    MIN_LOSSES_INF,
    evaluate_stability,
    extract_digest_snapshot,
)
from pipelines.kc.vendored.postfix_response_colors import check_data  # noqa: E402
from pipelines.kc.vendored.cards_api import get_cards_db, refresh_cache  # noqa: E402

DIGEST_DIR = _PROJECT_ROOT / "output" / "digests"
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]

BATCH_PRICES = {
    "gpt-4o-mini":  {"input": 0.15, "output": 0.60},
    "gpt-5.4-mini": {"input": 0.75, "output": 4.50},
    "gpt-4o":       {"input": 2.50, "output": 10.00},
}


def log(msg):
    from datetime import datetime
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def estimate_cost(model, input_tokens, output_tokens):
    px = BATCH_PRICES.get(model)
    if not px:
        return -1.0
    return (input_tokens / 1_000_000) * px["input"] + (output_tokens / 1_000_000) * px["output"]


def _suffix(game_format):
    return '_inf' if game_format == 'infinity' else ''


def _current_core_legal_sets(db):
    try:
        from backend.services.meta_epoch_service import get_current_epoch
        epoch = get_current_epoch(db)
        return set(epoch.legal_sets or []) if epoch else set()
    except Exception:
        return set()


def _card_set(card_name: str) -> int | None:
    card = get_cards_db().get(card_name)
    if not isinstance(card, dict):
        return None
    raw = card.get("set")
    try:
        return int(raw) if raw is not None and raw != "" else None
    except (TypeError, ValueError):
        return None


def _strip_core_illegal_cards(db, data: dict) -> int:
    legal_sets = _current_core_legal_sets(db)
    if not legal_sets:
        return 0

    removed = 0
    for curve in data.get("curves", []) or []:
        response = curve.get("response") or {}
        cards = response.get("cards")
        if isinstance(cards, list):
            kept = []
            for card_name in cards:
                set_num = _card_set(card_name)
                if set_num is not None and set_num not in legal_sets:
                    removed += 1
                    continue
                kept.append(card_name)
            response["cards"] = kept

        sequence = curve.get("sequence") or {}
        for turn_data in sequence.values():
            plays = (turn_data or {}).get("plays")
            if not isinstance(plays, list):
                continue
            kept_plays = []
            for play in plays:
                if not isinstance(play, dict):
                    kept_plays.append(play)
                    continue
                set_num = _card_set(play.get("card"))
                if set_num is not None and set_num not in legal_sets:
                    removed += 1
                    continue
                kept_plays.append(play)
            turn_data["plays"] = kept_plays
    return removed


def _load_existing_kc_from_pg(db, our, opp, game_format):
    """Load existing KC from PG for stability check and prompt context."""
    from sqlalchemy import text
    row = db.execute(text("""
        SELECT curves, match_count, loss_count, generated_at
        FROM killer_curves
        WHERE our_deck = :our AND opp_deck = :opp AND game_format = :fmt
            AND is_current = true
        ORDER BY generated_at DESC LIMIT 1
    """), {"our": our, "opp": opp, "fmt": game_format}).fetchone()
    if not row:
        return None
    curves = row.curves if isinstance(row.curves, list) else json.loads(row.curves)
    return {
        "metadata": {
            "our_deck": our, "opp_deck": opp,
            "based_on_games": row.match_count or 0,
            "based_on_losses": row.loss_count or 0,
            "date": str(row.generated_at) if row.generated_at else "",
        },
        "curves": curves,
    }


def get_matchups_to_process(db, force=False, single=None, game_format='core'):
    """Determine which matchups need regeneration."""
    if single:
        return [single]

    sfx = _suffix(game_format)
    min_losses = MIN_LOSSES_INF if game_format == 'infinity' else MIN_LOSSES
    todo = []

    for our in DECKS:
        for opp in DECKS:
            if our == opp:
                continue

            digest_path = DIGEST_DIR / f"digest_{our}_vs_{opp}{sfx}.json"
            if not digest_path.exists():
                continue

            # Check minimum losses
            try:
                losses = json.load(open(digest_path)).get("losses", 0)
                if losses < min_losses:
                    continue
            except Exception:
                continue

            if not force:
                existing = _load_existing_kc_from_pg(db, our, opp, game_format)
                r = evaluate_stability(our, opp, game_format=game_format, existing_kc=existing)
                if r['level'] == 'STABLE':
                    continue

            todo.append((our, opp))

    return todo


def generate_one(client, db, our, opp, game_format='core'):
    """Generate KC for one matchup via OpenAI, upsert to PG."""
    from sqlalchemy import text

    sfx = _suffix(game_format)
    existing = _load_existing_kc_from_pg(db, our, opp, game_format)

    prompt = build_prompt(our, opp, game_format=game_format, existing_kc=existing)
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]

    t0 = time.time()
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "You generate only valid JSON. "
                    "No markdown, no prose outside JSON, no code fences. "
                    "Card names must be exact — no [COLOR] tags in output."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )
    elapsed = time.time() - t0
    raw_text = resp.choices[0].message.content

    # Strip markdown fences
    if raw_text.strip().startswith("```"):
        lines = raw_text.strip().split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw_text = "\n".join(lines)

    usage = resp.usage
    input_tok = usage.prompt_tokens if usage else 0
    output_tok = usage.completion_tokens if usage else 0
    cost = estimate_cost(MODEL, input_tok, output_tok)

    # Parse
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        return {"status": "ERR:json_parse", "elapsed": round(elapsed, 1), "cost": round(cost, 6)}

    # Inject metadata
    digest_path = DIGEST_DIR / f"digest_{our}_vs_{opp}{sfx}.json"
    if digest_path.exists():
        try:
            digest = json.load(open(digest_path))
            data.setdefault("metadata", {})
            meta = data["metadata"]
            meta["our_deck"] = our
            meta["opp_deck"] = opp
            meta["date"] = date.today().isoformat()
            meta["model"] = MODEL
            meta["game_format"] = game_format
            meta["based_on_games"] = digest.get("games", 0)
            meta["based_on_losses"] = digest.get("losses", 0)
            meta["digest_snapshot"] = extract_digest_snapshot(digest)
        except Exception:
            pass

    # Postfix: strip color tags + drop invalid response cards
    n_dropped = 0
    _, n_bad, _ = check_data(data, drop_invalid=True)
    n_dropped = n_bad
    if game_format == "core":
        n_dropped += _strip_core_illegal_cards(db, data)

    curves = data.get("curves", [])
    n_curves = len(curves)
    meta = data.get("metadata", {})

    run_meta = {
        "run_id": RUN_ID,
        "model": MODEL,
        "cost_usd": round(cost, 6),
        "input_tokens": input_tok,
        "output_tokens": output_tok,
        "duration_s": round(elapsed, 2),
        "prompt_hash": prompt_hash,
        "cards_dropped": n_dropped,
        "n_curves": n_curves,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    db.execute(text("""
        UPDATE killer_curves SET is_current = false
        WHERE game_format = :game_format
          AND our_deck = :our_deck AND opp_deck = :opp_deck
          AND generated_at < :generated_at AND is_current = true
    """), {
        "generated_at": date.today(),
        "game_format": game_format,
        "our_deck": our,
        "opp_deck": opp,
    })

    db.execute(text("""
        INSERT INTO killer_curves
            (generated_at, game_format, our_deck, opp_deck, curves,
             match_count, loss_count, is_current, meta)
        VALUES
            (:generated_at, :game_format, :our_deck, :opp_deck, :curves,
             :match_count, :loss_count, true, :meta)
        ON CONFLICT (game_format, our_deck, opp_deck, generated_at) DO UPDATE
        SET curves = EXCLUDED.curves,
            match_count = EXCLUDED.match_count,
            loss_count = EXCLUDED.loss_count,
            is_current = true,
            meta = EXCLUDED.meta
    """), {
        "generated_at": date.today(),
        "game_format": game_format,
        "our_deck": our,
        "opp_deck": opp,
        "curves": json.dumps(curves),
        "match_count": meta.get("based_on_games", 0),
        "loss_count": meta.get("based_on_losses", 0),
        "meta": json.dumps(run_meta),
    })
    db.commit()

    return {
        "status": "OK",
        "curves": n_curves,
        "elapsed": round(elapsed, 1),
        "cost": round(cost, 6),
        "cards_dropped": n_dropped,
        "input_tok": input_tok,
        "output_tok": output_tok,
    }


def run_format(db, game_format, force, dry_run, single, client):
    """Run KC generation for one format."""
    log(f"--- Format: {game_format} ---")

    todo = get_matchups_to_process(db, force=force, single=single, game_format=game_format)
    log(f"Matchups to process: {len(todo)} ({game_format})")

    if dry_run:
        for our, opp in todo:
            print(f"  {our} vs {opp}")
        log("Dry run — no generation.")
        return 0

    if not todo:
        log("Nothing to do. All up to date.")
        return 0

    total_cost = 0
    total_ok = 0
    total_fail = 0
    t_start = time.time()

    for i, (our, opp) in enumerate(todo):
        tag = f"[{i+1}/{len(todo)}] {our} vs {opp}"
        try:
            entry = generate_one(client, db, our, opp, game_format=game_format)
            total_cost += entry.get("cost", 0)

            status = entry["status"]
            if status == "OK":
                total_ok += 1
                info = f"{entry['curves']}c {entry['elapsed']}s ${entry['cost']:.3f}"
                if entry.get("cards_dropped", 0) > 0:
                    info += f" [dropped {entry['cards_dropped']}]"
                log(f"  {tag}: {info}")
            else:
                total_fail += 1
                log(f"  {tag}: {status}")
        except Exception as e:
            log(f"  {tag}: ERROR — {e}")
            total_fail += 1

    elapsed_total = time.time() - t_start
    log("=" * 60)
    log(f"[{game_format}] Completed: {total_ok} OK, {total_fail} FAIL")
    log(f"Time: {elapsed_total:.0f}s ({elapsed_total/60:.1f}min)")
    log(f"Cost: ${total_cost:.4f}")
    log("=" * 60)

    return total_fail


def main():
    global MODEL
    p = argparse.ArgumentParser(description="Generate killer curves (native App_tool)")
    p.add_argument("--format", choices=("core", "infinity", "all"), default="core")
    p.add_argument("--pair", nargs=2, metavar=("OUR", "OPP"),
                   help="Single matchup (e.g. --pair AmSa AbE)")
    p.add_argument("--force", action="store_true", help="Regenerate all (ignore stability)")
    p.add_argument("--dry-run", action="store_true", help="Show what would run, no OpenAI call")
    p.add_argument("--model", default=None, help=f"Override model (default: {MODEL})")
    args = p.parse_args()

    if args.model:
        MODEL = args.model

    # API key
    if not args.dry_run:
        if not os.getenv("OPENAI_API_KEY"):
            key_file = Path("/tmp/.openai_key")
            if key_file.exists():
                os.environ["OPENAI_API_KEY"] = key_file.read_text().strip()
            else:
                print("ERROR: OPENAI_API_KEY not set", file=sys.stderr)
                sys.exit(1)

    from backend.models import SessionLocal
    db = SessionLocal()

    log(f"=== KC Production (native) — {date.today().isoformat()} ===")
    log(f"Model: {MODEL}")
    log(f"Run ID: {RUN_ID}")

    # Refresh cards DB
    log("Phase 1: Refresh cards DB from duels.ink...")
    ok = refresh_cache(force=True)
    log(f"  Cards DB: {'OK' if ok else 'LOCAL FALLBACK'}")

    client = OpenAI() if not args.dry_run else None
    single = tuple(args.pair) if args.pair else None
    formats = ['core', 'infinity'] if args.format == 'all' else [args.format]

    total_fail = 0
    try:
        for fmt in formats:
            total_fail += run_format(db, fmt, args.force, args.dry_run, single, client)
    finally:
        db.close()

    sys.exit(0 if total_fail == 0 else 1)


if __name__ == "__main__":
    main()
