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
import re
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
from pipelines.kc.validator import validate as validate_kc, VALIDATOR_VERSION  # noqa: E402

DIGEST_DIR = _PROJECT_ROOT / "output" / "digests"
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
SCHEMA_VERSION = "killer_curves.v2"
QUALITY_GATE_MODE = "warn"  # off | warn | strict — set by CLI in main()

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


def _digest_path(our: str, opp: str, game_format: str) -> Path:
    return DIGEST_DIR / f"digest_{our}_vs_{opp}{_suffix(game_format)}.json"


def _load_digest(our: str, opp: str, game_format: str) -> dict | None:
    path = _digest_path(our, opp, game_format)
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def _stable_hash(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _digest_hash(our: str, opp: str, game_format: str) -> str | None:
    digest = _load_digest(our, opp, game_format)
    if digest is None:
        return None
    return _stable_hash(digest)


def _prompt_contract_hash() -> str:
    """Hash the prompt contract, excluding matchup data and today's date.

    `prompt_hash` is still persisted for forensics, but it changes with the
    full rendered prompt. This stable contract hash is the cache key component
    that tells us whether the instructions/schema changed.
    """
    h = hashlib.sha256()
    for path in [
        _PROJECT_ROOT / "pipelines" / "kc" / "build_prompt.py",
        _PROJECT_ROOT / "pipelines" / "kc" / "prompts" / "istruzioni_compact.md",
        _PROJECT_ROOT / "pipelines" / "kc" / "prompts" / "rules_compact.md",
    ]:
        h.update(path.name.encode("utf-8"))
        h.update(b"\0")
        try:
            h.update(path.read_bytes())
        except OSError:
            pass
        h.update(b"\0")
    h.update(SCHEMA_VERSION.encode("utf-8"))
    return h.hexdigest()[:16]


PROMPT_CONTRACT_HASH = _prompt_contract_hash()


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


def _card_ink_matches(card_name: str, deck_code: str | None) -> bool:
    if not deck_code:
        return False
    our_colors_str = DECK_COLORS.get(deck_code)
    if not our_colors_str:
        return False
    our_set = {c.strip().lower() for c in our_colors_str.split(",")}
    card = get_cards_db().get(card_name)
    if not isinstance(card, dict):
        return False
    ink = (card.get("ink", "") or "").lower()
    if not ink:
        return False
    if "/" in ink:
        return all(c.strip() in our_set for c in ink.split("/"))
    return ink in our_set or ink in ("dual ink", "inkless")


def _latest_core_legal_set() -> int | None:
    try:
        from backend.models import SessionLocal
        from backend.services.meta_epoch_service import get_current_epoch
        db = SessionLocal()
        try:
            epoch = get_current_epoch(db)
        finally:
            db.close()
        legal_sets = sorted(set(epoch.legal_sets or [])) if epoch else []
    except Exception:
        legal_sets = []
    if not legal_sets:
        return None
    return legal_sets[-1]


def _core_legal_fallback_cards(deck_code: str | None) -> set[str]:
    latest_set = _latest_core_legal_set()
    if latest_set is None:
        return set()
    db = get_cards_db()
    cards = {
        name
        for name, card in db.items()
        if _card_set(name) == latest_set and _card_ink_matches(name, deck_code)
    }
    return cards


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


def _strip_non_meta_cards(db, data: dict, game_format: str) -> int:
    """Strip cards from response.cards / sequence.plays that are not in the
    current meta. A card is "in meta" if CARD_PLAYED ≥20 times in the last
    30d of matches for this format. Guards against GPT suggesting legal-
    but-dead cards (e.g. set 1/2 pre-rotation staples) in Core KCs.
    """
    from pipelines.kc.meta_relevance import get_meta_relevant_cards
    meta = get_meta_relevant_cards(db, game_format=game_format, days=30, min_plays=20)
    if not meta:
        return 0

    fallback_cards: set[str] = set()
    our_deck = None
    if game_format == "core":
        meta_blob = data.get("metadata") or {}
        our_deck = meta_blob.get("our_deck")
        fallback_cards = _core_legal_fallback_cards(our_deck)

    removed = 0
    for curve in data.get("curves", []) or []:
        response = curve.get("response") or {}
        cards = response.get("cards")
        if isinstance(cards, list):
            kept = []
            for card_name in cards:
                if card_name and card_name not in meta:
                    if game_format == "core" and card_name in fallback_cards:
                        kept.append(card_name)
                        continue
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
                card_name = play.get("card")
                if card_name and card_name not in meta:
                    removed += 1
                    continue
                kept_plays.append(play)
            turn_data["plays"] = kept_plays
    return removed


def _load_existing_kc_from_pg(db, our, opp, game_format):
    """Load existing KC from PG for stability check and prompt context."""
    from sqlalchemy import text
    row = db.execute(text("""
        SELECT curves, match_count, loss_count, generated_at, meta
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
        "run_meta": row.meta or {},
        "curves": curves,
    }


def _cache_hit(existing: dict | None, our: str, opp: str, game_format: str) -> bool:
    if not existing:
        return False
    meta = existing.get("run_meta") or {}
    digest_hash = _digest_hash(our, opp, game_format)
    if not digest_hash:
        return False
    return (
        meta.get("digest_hash") == digest_hash
        and meta.get("prompt_contract_hash") == PROMPT_CONTRACT_HASH
        and meta.get("schema_version") == SCHEMA_VERSION
    )


def _existing_kc_for_prompt(existing: dict | None) -> dict | None:
    if not existing:
        return None
    return {
        "metadata": existing.get("metadata", {}),
        "curves": existing.get("curves", []),
    }


def _combined_response_text(response: dict) -> str:
    parts: list[str] = []
    for key, value in response.items():
        if key == "cards":
            continue
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(v for v in value if isinstance(v, str))
        elif isinstance(value, dict):
            parts.extend(v for v in value.values() if isinstance(v, str))
    return "\n".join(parts)


def _response_mentions_any_response_card(curve: dict) -> bool:
    response = curve.get("response") or {}
    if not isinstance(response, dict):
        return False
    cards = [c.strip() for c in (response.get("cards") or []) if isinstance(c, str) and c.strip()]
    if not cards:
        return False

    text = _combined_response_text(response).lower()
    for card in cards:
        pattern = rf"(?<!\w){re.escape(card.lower())}(?!\w)"
        if re.search(pattern, text):
            return True
    return False


def _generic_response_curves(curves: list) -> list[str]:
    blocked = []
    for curve in curves:
        if isinstance(curve, dict) and not _response_mentions_any_response_card(curve):
            blocked.append(f"{curve.get('id') or '?'}:{curve.get('name') or 'unnamed'}")
    return blocked


def _inject_metadata(data: dict, digest: dict | None, our: str, opp: str, game_format: str) -> None:
    if digest is None:
        return
    try:
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


def _postprocess_data(db, data: dict, game_format: str) -> int:
    _, n_bad, _ = check_data(data, drop_invalid=True)
    n_dropped = n_bad
    if game_format == "core":
        n_dropped += _strip_core_illegal_cards(db, data)
    n_dropped += _strip_non_meta_cards(db, data, game_format)
    return n_dropped


def _repair_response_named_cards(client, data: dict, blocked_curves: list[str]) -> tuple[dict | None, dict]:
    """One cheap repair pass for responses that list cards but never name them.

    The repair keeps sequences intact and only rewrites response/v3 copy so the
    published advice is actionable and references at least one listed answer.
    """
    repair_prompt = f"""Repair this Killer Curves JSON only.

Validation failed: these curves have response.cards but the readable response text does not name any listed response card:
{json.dumps(blocked_curves, ensure_ascii=False)}

Rules:
- Return the full corrected JSON object, no markdown.
- Do not change metadata, deck codes, sequence turns, or sequence plays.
- For each blocked curve, keep response.cards if they are valid answers, but rewrite response.headline, response.core_rule, response.priority_actions, response.what_to_avoid, response.stock_build_note, response.off_meta_note, response.play_draw_note, and response.failure_state so at least one exact card name from response.cards appears verbatim in readable text.
- Keep English only.
- Keep v3_payload consistent with the repaired response.

JSON to repair:
{json.dumps(data, ensure_ascii=False)}
"""
    t0 = time.time()
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You repair JSON only. No markdown, no prose outside JSON. "
                    "Do not alter game sequences; repair response copy."
                ),
            },
            {"role": "user", "content": repair_prompt},
        ],
    )
    elapsed = time.time() - t0
    raw_text = resp.choices[0].message.content
    if raw_text.strip().startswith("```"):
        lines = raw_text.strip().split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw_text = "\n".join(lines)

    usage = resp.usage
    input_tok = usage.prompt_tokens if usage else 0
    output_tok = usage.completion_tokens if usage else 0
    cost = estimate_cost(MODEL, input_tok, output_tok)
    metrics = {
        "repair_elapsed": round(elapsed, 1),
        "repair_cost": round(cost, 6),
        "repair_input_tok": input_tok,
        "repair_output_tok": output_tok,
    }
    try:
        return json.loads(raw_text), metrics
    except json.JSONDecodeError:
        metrics["repair_error"] = "json_parse"
        return None, metrics


def _curve_payload_metrics(curves: list) -> dict:
    response_fields = [
        "headline",
        "core_rule",
        "priority_actions",
        "what_to_avoid",
        "stock_build_note",
        "off_meta_note",
        "play_draw_note",
        "failure_state",
    ]
    v3_fields = ["one_line_hook", "mulligan_focus", "turn_checklist", "coach_badges", "user_copy"]
    response_v2_complete = 0
    response_named_card_complete = 0
    v3_payload_complete = 0
    self_check_complete = 0

    for curve in curves or []:
        if not isinstance(curve, dict):
            continue
        response = curve.get("response") or {}
        if isinstance(response, dict) and all(response.get(f) for f in response_fields) and _response_mentions_any_response_card(curve):
            response_v2_complete += 1
        if _response_mentions_any_response_card(curve):
            response_named_card_complete += 1

        v3_payload = curve.get("v3_payload") or {}
        if isinstance(v3_payload, dict) and all(v3_payload.get(f) for f in v3_fields):
            user_copy = v3_payload.get("user_copy") or {}
            if isinstance(user_copy, dict) and user_copy.get("short") and user_copy.get("expanded"):
                v3_payload_complete += 1

        self_check = curve.get("self_check") or {}
        if isinstance(self_check, dict) and all(
            key in self_check
            for key in ["curve_specific", "mentions_key_card", "response_by_turn", "not_generic", "uses_only_prompt_cards"]
        ):
            self_check_complete += 1

    total = len(curves or [])
    return {
        "response_v2_complete": response_v2_complete,
        "response_named_card_complete": response_named_card_complete,
        "v3_payload_complete": v3_payload_complete,
        "self_check_complete": self_check_complete,
        "response_v2_complete_pct": round(response_v2_complete / total * 100, 1) if total else 0,
        "response_named_card_complete_pct": round(response_named_card_complete / total * 100, 1) if total else 0,
        "v3_payload_complete_pct": round(v3_payload_complete / total * 100, 1) if total else 0,
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
                if _cache_hit(existing, our, opp, game_format):
                    continue
                r = evaluate_stability(
                    our,
                    opp,
                    game_format=game_format,
                    existing_kc=_existing_kc_for_prompt(existing),
                )
                if r['level'] == 'STABLE':
                    continue

            todo.append((our, opp))

    return todo


def generate_one(client, db, our, opp, game_format='core'):
    """Generate KC for one matchup via OpenAI, upsert to PG."""
    from sqlalchemy import text

    existing = _load_existing_kc_from_pg(db, our, opp, game_format)
    digest = _load_digest(our, opp, game_format)
    digest_hash = _stable_hash(digest) if digest is not None else None

    prompt = build_prompt(our, opp, game_format=game_format, existing_kc=_existing_kc_for_prompt(existing))
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]

    t0 = time.time()
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        response_format={"type": "json_object"},
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

    _inject_metadata(data, digest, our, opp, game_format)

    # Postfix: strip color tags + drop invalid response cards
    n_dropped = _postprocess_data(db, data, game_format)

    curves = data.get("curves", [])
    n_curves = len(curves)
    meta = data.get("metadata", {})
    repair_meta = {}

    generic_response_curves = _generic_response_curves(curves)
    if generic_response_curves:
        repaired, repair_meta = _repair_response_named_cards(client, data, generic_response_curves)
        cost += repair_meta.get("repair_cost", 0)
        input_tok += repair_meta.get("repair_input_tok", 0)
        output_tok += repair_meta.get("repair_output_tok", 0)
        if repaired is None:
            return {
                "status": "ERR:repair_json_parse",
                "elapsed": round(elapsed + repair_meta.get("repair_elapsed", 0), 1),
                "cost": round(cost, 6),
                "cards_dropped": n_dropped,
                "input_tok": input_tok,
                "output_tok": output_tok,
                "blocked_curves": len(generic_response_curves),
                "details": "; ".join(generic_response_curves[:8]),
            }

        data = repaired
        _inject_metadata(data, digest, our, opp, game_format)
        n_dropped += _postprocess_data(db, data, game_format)
        curves = data.get("curves", [])
        n_curves = len(curves)
        meta = data.get("metadata", {})
        generic_response_curves = _generic_response_curves(curves)
        if generic_response_curves:
            return {
                "status": "ERR:response_missing_named_card",
                "elapsed": round(elapsed + repair_meta.get("repair_elapsed", 0), 1),
                "cost": round(cost, 6),
                "cards_dropped": n_dropped,
                "input_tok": input_tok,
                "output_tok": output_tok,
                "blocked_curves": len(generic_response_curves),
                "details": "; ".join(generic_response_curves[:8]),
            }

    payload_metrics = _curve_payload_metrics(curves)

    # ── Hard validator gate (C.7.4) ─────────────────────────────────────────
    # Pre-upsert deterministic check. Outcome stored in meta regardless of
    # mode; in strict mode a `blocked` result also aborts the upsert.
    validation = validate_kc(data, our, opp, game_format, db)
    quality_status = validation.get("quality_status", "blocked")
    if QUALITY_GATE_MODE == "strict" and quality_status == "blocked":
        err_codes = sorted({e.get("code", "?") for e in (validation.get("errors") or [])})
        return {
            "status": "ERR:quality_blocked",
            "elapsed": round(elapsed, 1),
            "cost": round(cost, 6),
            "cards_dropped": n_dropped,
            "input_tok": input_tok,
            "output_tok": output_tok,
            "validator_version": VALIDATOR_VERSION,
            "quality_status": quality_status,
            "error_codes": err_codes,
            "details": "; ".join(err_codes[:6]),
        }

    run_meta = {
        "run_id": RUN_ID,
        "model": MODEL,
        "cost_usd": round(cost, 6),
        "input_tokens": input_tok,
        "output_tokens": output_tok,
        "duration_s": round(elapsed, 2),
        "prompt_hash": prompt_hash,
        "prompt_contract_hash": PROMPT_CONTRACT_HASH,
        "digest_hash": digest_hash,
        "schema_version": SCHEMA_VERSION,
        "cards_dropped": n_dropped,
        "n_curves": n_curves,
        "repair_attempted": bool(repair_meta),
        **repair_meta,
        **payload_metrics,
        "validator_version": VALIDATOR_VERSION,
        "quality_status": quality_status,
        "quality_gate_mode": QUALITY_GATE_MODE,
        "quality_errors": validation.get("errors") or [],
        "quality_warnings": validation.get("warnings") or [],
        "quality_drop_metrics": validation.get("drop_metrics") or {},
        "quality_completeness": validation.get("completeness") or {},
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
        "status": "OK" if quality_status == "pass" else f"OK:{quality_status}",
        "curves": n_curves,
        "elapsed": round(elapsed, 1),
        "cost": round(cost, 6),
        "cards_dropped": n_dropped,
        "input_tok": input_tok,
        "output_tok": output_tok,
        "quality_status": quality_status,
        "n_errors": len(validation.get("errors") or []),
        "n_warnings": len(validation.get("warnings") or []),
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
    global MODEL, QUALITY_GATE_MODE
    p = argparse.ArgumentParser(description="Generate killer curves (native App_tool)")
    p.add_argument("--format", choices=("core", "infinity", "all"), default="core")
    p.add_argument("--pair", nargs=2, metavar=("OUR", "OPP"),
                   help="Single matchup (e.g. --pair AmSa AbE)")
    p.add_argument("--force", action="store_true", help="Regenerate all (ignore stability)")
    p.add_argument("--dry-run", action="store_true", help="Show what would run, no OpenAI call")
    p.add_argument("--model", default=None, help=f"Override model (default: {MODEL})")
    p.add_argument("--quality-gate", choices=("off", "warn", "strict"), default="warn",
                   help="Validator behavior pre-upsert: off=no validation, warn=upsert+flag (default), strict=blocked rows are skipped (no upsert)")
    args = p.parse_args()

    if args.model:
        MODEL = args.model
    QUALITY_GATE_MODE = args.quality_gate

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
    log(f"Prompt contract: {PROMPT_CONTRACT_HASH} · Schema: {SCHEMA_VERSION}")
    log(f"Validator: {VALIDATOR_VERSION} · gate mode: {QUALITY_GATE_MODE}")

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
