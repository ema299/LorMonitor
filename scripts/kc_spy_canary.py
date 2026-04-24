#!/usr/bin/env python3
"""Native KC Spy canary for App_tool.

Runs the daily canary + validation cycle, writing the report directly to
the PG kc_spy_reports table. Replaces the analisidef bridge:
    analisidef/kc_spy.py (04:00 cron)  +  scripts/import_kc_spy.py (04:05 cron)

Phases:
1. Canary: pick one random matchup per format with an existing digest, run
   full KC generation via OpenAI (json_object mode + retry on JSONDecodeError)
2. Validate: scan all current killer_curves rows in PG via check_data
3. Autofix (only if validate found issues): drop off-color cards via
   check_data(drop_invalid=True), then re-validate
4. Report: upsert into kc_spy_reports so the dashboard KC Health badge reads it

Cost: ~$0.05/day (1 API call per format). Runs in ~30 seconds.
Exit code: 0 on OK/WARN, 1 on FAIL (alerts cron wrapper).

Usage:
    scripts/kc_spy_canary.py --format all
    scripts/kc_spy_canary.py --format core --dry-run   # no DB write
    scripts/kc_spy_canary.py --no-api                   # validation only
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import date, datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from openai import OpenAI  # noqa: E402
from sqlalchemy import text  # noqa: E402

from backend.models import SessionLocal  # noqa: E402
from pipelines.kc.build_prompt import build_prompt  # noqa: E402
from pipelines.kc.vendored.cards_api import refresh_cache  # noqa: E402
from pipelines.kc.vendored.postfix_response_colors import check_data  # noqa: E402
from pipelines.kc.vendored.stability import DECKS  # noqa: E402

DIGEST_DIR = _PROJECT_ROOT / "output" / "digests"
LOG_FILE = _PROJECT_ROOT / "output" / "kc_spy_canary.log"
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")


def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def _suffix(fmt: str) -> str:
    return "_inf" if fmt == "infinity" else ""


def pick_matchup(fmt: str) -> tuple[str, str] | None:
    """Random matchup whose digest exists on disk."""
    sfx = _suffix(fmt)
    cands = []
    for our in DECKS:
        for opp in DECKS:
            if our == opp:
                continue
            if (DIGEST_DIR / f"digest_{our}_vs_{opp}{sfx}.json").exists():
                cands.append((our, opp))
    return random.choice(cands) if cands else None


def run_canary(client: OpenAI, our: str, opp: str, fmt: str) -> dict:
    """Full pipeline canary for one matchup."""
    sfx = _suffix(fmt)
    result: dict = {"deck": our, "opp": opp, "format": fmt, "steps": {}}

    digest_path = DIGEST_DIR / f"digest_{our}_vs_{opp}{sfx}.json"
    result["steps"]["digest"] = digest_path.exists()
    if not digest_path.exists():
        result["status"] = "FAIL"
        result["error"] = "no digest"
        return result

    try:
        prompt = build_prompt(our, opp, game_format=fmt)
        result["steps"]["prompt"] = True
        result["prompt_kb"] = round(len(prompt) / 1024)
    except Exception as e:
        result["steps"]["prompt"] = False
        result["status"] = "FAIL"
        result["error"] = f"prompt: {e}"
        return result

    def _call_once():
        t0 = time.time()
        resp = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You generate only valid JSON. No markdown, no prose outside JSON, no code fences. Card names must be exact."},
                {"role": "user", "content": prompt},
            ],
        )
        return resp, round(time.time() - t0, 1)

    text_body = ""
    usage = None
    elapsed = 0.0
    api_ok = False
    api_error = None
    json_error = None
    data: dict | None = None
    attempts = 0
    for attempt in range(2):
        attempts = attempt + 1
        try:
            resp, elapsed = _call_once()
            text_body = resp.choices[0].message.content or ""
            usage = resp.usage
            api_ok = True
        except Exception as e:
            api_error = str(e)
            continue

        if text_body.strip().startswith("```"):
            lines = text_body.strip().split("\n")
            text_body = "\n".join(l for l in lines if not l.strip().startswith("```"))
        try:
            data = json.loads(text_body)
            json_error = None
            break
        except json.JSONDecodeError as e:
            json_error = f"{e}"
            data = None
            # Retry once — json_object mode usually prevents this; residual
            # flakes come from truncated completions.
            continue

    result["attempts"] = attempts
    if not api_ok:
        result["steps"]["api"] = False
        result["status"] = "FAIL"
        result["error"] = f"api: {api_error}"
        return result

    result["steps"]["api"] = True
    result["elapsed_sec"] = elapsed
    result["cost_usd"] = round(
        (usage.prompt_tokens / 1e6) * 0.75 + (usage.completion_tokens / 1e6) * 4.50, 4
    ) if usage else -1

    if data is None:
        result["steps"]["json"] = False
        result["status"] = "FAIL"
        result["error"] = f"json: {json_error}"
        return result

    n_curves = len(data.get("curves", []))
    result["steps"]["json"] = True
    result["curves"] = n_curves

    # Semantic validation via off-color check (no mutation).
    data.setdefault("metadata", {})["our_deck"] = our
    _, n_bad, _ = check_data(data, drop_invalid=False)
    result["steps"]["validate"] = n_bad == 0
    result["validation_fail"] = n_bad

    result["status"] = "OK" if all(result["steps"].values()) else "WARN"
    return result


def validate_all_pg(db) -> dict:
    """Validate all current killer_curves rows via check_data."""
    rows = db.execute(text("""
        SELECT game_format, our_deck, opp_deck, curves
        FROM killer_curves WHERE is_current = true
    """)).fetchall()

    files_ok = 0
    files_fail = 0
    total_fails = 0
    problems: list[dict] = []
    for r in rows:
        curves = r.curves if isinstance(r.curves, list) else json.loads(r.curves)
        data = {"metadata": {"our_deck": r.our_deck, "opp_deck": r.opp_deck}, "curves": curves}
        _, n_bad, details = check_data(data, drop_invalid=False)
        if n_bad > 0:
            files_fail += 1
            total_fails += n_bad
            problems.append({
                "file": f"{r.game_format}/{r.our_deck}_vs_{r.opp_deck}",
                "fails": n_bad,
                "details": [
                    f"curve #{d['curve']} ({d['curve_name']}): {d['card']} [{d['card_ink']}] off-color"
                    for d in details[:3]
                ],
            })
        else:
            files_ok += 1

    return {
        "files_ok": files_ok,
        "files_warn": 0,
        "files_fail": files_fail,
        "total_fails": total_fails,
        "problems": problems[:10],
    }


def autofix_pg(db) -> str:
    """Apply check_data drop_invalid to all current killer_curves rows."""
    rows = db.execute(text("""
        SELECT game_format, our_deck, opp_deck, curves, generated_at
        FROM killer_curves WHERE is_current = true
    """)).fetchall()
    fixed = 0
    for r in rows:
        curves = r.curves if isinstance(r.curves, list) else json.loads(r.curves)
        data = {"metadata": {"our_deck": r.our_deck, "opp_deck": r.opp_deck}, "curves": curves}
        _, n_bad, _ = check_data(data, drop_invalid=True)
        if n_bad > 0:
            fixed += 1
            db.execute(text("""
                UPDATE killer_curves
                SET curves = CAST(:curves AS jsonb)
                WHERE game_format = :fmt AND our_deck = :our AND opp_deck = :opp
                    AND generated_at = :gen
            """), {
                "curves": json.dumps(data["curves"]),
                "fmt": r.game_format, "our": r.our_deck, "opp": r.opp_deck,
                "gen": r.generated_at,
            })
    db.commit()
    return f"Totale: {fixed} fix on {len(rows)} rows"


def write_report(db, report: dict) -> None:
    try:
        report_date = date.fromisoformat(report["date"])
    except ValueError:
        report_date = date.today()
    try:
        generated_at = datetime.fromisoformat(report["timestamp"])
    except Exception:
        generated_at = datetime.now()
    db.execute(text("""
        INSERT INTO kc_spy_reports (report_date, generated_at, report, status)
        VALUES (:d, :g, CAST(:r AS jsonb), :s)
        ON CONFLICT (report_date) DO UPDATE
        SET generated_at = EXCLUDED.generated_at,
            report = EXCLUDED.report,
            status = EXCLUDED.status,
            imported_at = now()
    """), {
        "d": report_date,
        "g": generated_at,
        "r": json.dumps(report),
        "s": report.get("status"),
    })
    db.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description="KC Spy canary + validation for App_tool.")
    parser.add_argument("--format", choices=("core", "infinity", "all"), default="all")
    parser.add_argument("--dry-run", action="store_true", help="skip DB write")
    parser.add_argument("--no-api", action="store_true", help="skip canary OpenAI call (validation only)")
    args = parser.parse_args()

    if not args.no_api:
        if not os.getenv("OPENAI_API_KEY"):
            key_file = Path("/tmp/.openai_key")
            if key_file.exists():
                os.environ["OPENAI_API_KEY"] = key_file.read_text().strip()
            else:
                log("ERROR: OPENAI_API_KEY not set")
                return 1

    log(f"=== KC Spy (App_tool native) — {date.today().isoformat()} ===")

    try:
        refresh_cache(force=False)
    except Exception as e:
        log(f"refresh_cache warning: {e}")

    report: dict = {
        "date": date.today().isoformat(),
        "timestamp": datetime.now().isoformat(),
        "canary": {},
        "validation": {},
        "autofix": "",
        "status": "OK",
    }

    formats = ("core", "infinity") if args.format == "all" else (args.format,)

    if not args.no_api:
        client = OpenAI()
        for fmt in formats:
            matchup = pick_matchup(fmt)
            if not matchup:
                log(f"[{fmt}] no matchup — SKIP")
                report["canary"][fmt] = {"status": "SKIP", "reason": "no matchup"}
                continue
            our, opp = matchup
            log(f"[canary/{fmt}] {our} vs {opp}...")
            r = run_canary(client, our, opp, fmt)
            steps = " ".join(f"{k}:{'OK' if v else 'FAIL'}" for k, v in r.get("steps", {}).items())
            log(f"[canary/{fmt}] {r['status']} — {steps}")
            if r.get("error"):
                log(f"[canary/{fmt}] ERROR: {r['error']}")
            report["canary"][fmt] = r
            if r["status"] == "FAIL":
                report["status"] = "FAIL"

    db = SessionLocal()
    try:
        log("[validate] checking all current killer_curves rows...")
        val = validate_all_pg(db)
        log(f"[validate] {val['files_ok']} OK, {val['files_fail']} FAIL ({val['total_fails']} issues)")
        report["validation"] = val

        if val["files_fail"] > 0:
            if args.dry_run:
                log(f"[autofix] SKIPPED (dry-run); would fix {val['files_fail']} rows")
                report["autofix"] = f"dry-run — would fix {val['files_fail']} rows"
            else:
                log("[autofix] running check_data drop_invalid...")
                fix_msg = autofix_pg(db)
                log(f"[autofix] {fix_msg}")
                report["autofix"] = fix_msg

                val2 = validate_all_pg(db)
                log(f"[validate] after fix: {val2['files_ok']} OK, {val2['files_fail']} FAIL")
                report["validation_after_fix"] = val2
                if val2["files_fail"] > 0 and report["status"] == "OK":
                    report["status"] = "WARN"
        else:
            report["autofix"] = "not needed"

        if args.dry_run:
            log("[DRY-RUN] not writing report")
            print(json.dumps(report, indent=2))
        else:
            write_report(db, report)
            log(f"[saved] kc_spy_reports updated for {report['date']}")
    finally:
        db.close()

    log(f"=== Status: {report['status']} ===")
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
