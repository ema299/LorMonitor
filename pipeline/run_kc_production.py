#!/usr/bin/env python3
"""
Batch produzione killer curves via OpenAI API.

Flusso:
  1. Refresh cards DB da duels.ink
  2. Rigenera digest per matchup con archivio recente
  3. Genera curve per tutti gli UNSTABLE via gpt-5.4-mini
  4. Postfix: strip color tags + drop carte colore sbagliato
  5. Validazione finale
  6. Report

Uso:
    python3 run_kc_production.py                    # tutti gli UNSTABLE
    python3 run_kc_production.py --force             # rigenera TUTTI (ignora stability)
    python3 run_kc_production.py --dry-run           # mostra cosa farebbe senza generare
    python3 run_kc_production.py AmyR AbS            # singolo matchup
    OPENAI_MODEL=gpt-4o-mini python3 run_kc_production.py  # modello diverso
"""

import os
import sys
import json
import time
import subprocess
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from openai import OpenAI
from test_kc.src.build_prompt import build_prompt
from test_kc.src.stability import evaluate_stability, DECKS, MIN_LOSSES
from test_kc.src.postfix_response_colors import check_file
from test_kc.src.cards_api import refresh_cache

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
OUT_DIR = ROOT / "output"
LOG_DIR = ROOT / "test_kc" / "logs"
LOG_FILE = ROOT / "output" / "kc_production.log"

BATCH_PRICES = {
    "gpt-4o-mini":  {"input": 0.15, "output": 0.60},
    "gpt-5.4-mini": {"input": 0.75, "output": 4.50},
    "gpt-4o":       {"input": 2.50, "output": 10.00},
}


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def estimate_cost(model, input_tokens, output_tokens):
    px = BATCH_PRICES.get(model)
    if not px:
        return -1.0
    return (input_tokens / 1_000_000) * px["input"] + (output_tokens / 1_000_000) * px["output"]


def get_matchups_to_process(force=False, single=None):
    """Determine which matchups need regeneration."""
    if single:
        return [single]

    today = date.today().isoformat()
    todo = []
    for our in DECKS:
        for opp in DECKS:
            if our == opp:
                continue

            if not force:
                r = evaluate_stability(our, opp)
                if r['level'] == 'STABLE':
                    continue
                # Check minimum losses
                digest_path = OUT_DIR / f"digest_{our}_vs_{opp}.json"
                if digest_path.exists():
                    try:
                        losses = json.load(open(digest_path)).get("losses", 0)
                        if losses < MIN_LOSSES:
                            continue
                    except Exception:
                        pass

            # Skip if already generated today
            kc_path = OUT_DIR / f"killer_curves_{our}_vs_{opp}.json"
            if kc_path.exists():
                try:
                    d = json.load(open(kc_path)).get("metadata", {}).get("date", "")
                    if d == today:
                        continue
                except Exception:
                    pass

            todo.append((our, opp))
    return todo


def regenerate_digest(our, opp):
    """Regenerate digest from existing archive (fast path, ~0.6s)."""
    archive = OUT_DIR / f"archive_{our}_vs_{opp}.json"
    if not archive.exists():
        return False
    try:
        result = subprocess.run(
            ["python3", "-m", "lib.gen_digest", str(archive)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=30
        )
        return result.returncode == 0
    except Exception:
        return False


def generate_one(client, our, opp):
    """Generate killer curves for one matchup via OpenAI API."""
    # Build prompt (production mode: reads from output/, not test_kc/output/)
    prompt = build_prompt(our, opp, test_mode=False)
    out_path = OUT_DIR / f"killer_curves_{our}_vs_{opp}.json"

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
    text = resp.choices[0].message.content

    # Strip markdown fences
    if text.strip().startswith("```"):
        lines = text.strip().split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    usage = resp.usage
    input_tok = usage.prompt_tokens if usage else 0
    output_tok = usage.completion_tokens if usage else 0
    cost = estimate_cost(MODEL, input_tok, output_tok)

    # Parse and save
    try:
        data = json.loads(text)
        with open(out_path, "w") as f:
            json.dump(data, f, indent=2)
        n_curves = len(data.get("curves", []))
        valid = True
    except json.JSONDecodeError:
        raw_path = OUT_DIR / f"raw_{our}_vs_{opp}.txt"
        raw_path.write_text(text, encoding="utf-8")
        n_curves = 0
        valid = False

    # Postfix: strip color tags + drop invalid response cards
    n_dropped = 0
    if valid:
        _, n_dropped, _ = check_file(str(out_path), drop_invalid=True)

    # Validate
    v_fail = 0
    if valid:
        result = subprocess.run(
            ["python3", "-m", "lib.validate_killer_curves", str(out_path)],
            capture_output=True, text=True, cwd=str(ROOT)
        )
        v_fail = sum(1 for l in result.stdout.split("\n") if "FAIL" in l and "curve #" in l)

    # Save log
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_entry = {
        "deck": our, "opp": opp, "model": MODEL,
        "date": date.today().isoformat(),
        "valid_json": valid, "curves": n_curves,
        "prompt_tokens": input_tok, "completion_tokens": output_tok,
        "elapsed_sec": round(elapsed, 1),
        "cost_usd": round(cost, 6),
        "cards_dropped": n_dropped,
        "validation_fail": v_fail,
    }
    log_path = LOG_DIR / f"log_{our}_vs_{opp}.{MODEL}.json"
    log_path.write_text(json.dumps(log_entry, indent=2), encoding="utf-8")

    return log_entry


def main():
    args = sys.argv[1:]
    force = "--force" in args
    dry_run = "--dry-run" in args
    args = [a for a in args if not a.startswith("--")]

    single = None
    if len(args) == 2:
        single = (args[0], args[1])

    # API key
    if not os.getenv("OPENAI_API_KEY"):
        key_file = Path("/tmp/.openai_key")
        if key_file.exists():
            os.environ["OPENAI_API_KEY"] = key_file.read_text().strip()
        else:
            print("ERRORE: OPENAI_API_KEY non impostata")
            sys.exit(1)

    # Start
    log(f"=== KC Production — {date.today().isoformat()} ===")
    log(f"Model: {MODEL}")

    # Phase 1: Refresh cards DB
    log("Fase 1: Refresh cards DB da duels.ink...")
    ok = refresh_cache(force=True)
    log(f"  Cards DB: {'OK' if ok else 'FALLBACK locale'}")

    # Phase 2: Determine matchups
    todo = get_matchups_to_process(force=force, single=single)
    log(f"Fase 2: {len(todo)} matchup da processare")

    if dry_run:
        for our, opp in todo:
            print(f"  {our} vs {opp}")
        log("Dry run — nessuna generazione.")
        return

    if not todo:
        log("Niente da fare. Tutti aggiornati.")
        return

    # Phase 3: Regenerate digests (fast, ~0.6s each)
    log("Fase 3: Rigenerazione digest...")
    for our, opp in todo:
        regenerate_digest(our, opp)

    # Phase 4: Generate curves
    log(f"Fase 4: Generazione curve ({MODEL})...")
    client = OpenAI()
    total_cost = 0
    total_ok = 0
    total_fail = 0
    total_dropped = 0
    t_start = time.time()

    for i, (our, opp) in enumerate(todo):
        tag = f"[{i+1}/{len(todo)}] {our} vs {opp}"
        try:
            entry = generate_one(client, our, opp)
            total_cost += entry["cost_usd"]
            total_dropped += entry["cards_dropped"]

            status = f"{entry['curves']}c {entry['elapsed_sec']}s ${entry['cost_usd']:.3f}"
            if entry["cards_dropped"] > 0:
                status += f" [dropped {entry['cards_dropped']}]"
            if entry["validation_fail"] > 0:
                status += f" ({entry['validation_fail']} FAIL)"
                total_fail += 1
            else:
                total_ok += 1
            log(f"  {tag}: {status}")
        except Exception as e:
            log(f"  {tag}: ERROR — {e}")
            total_fail += 1

    elapsed_total = time.time() - t_start

    # Phase 5: Summary
    log("=" * 60)
    log(f"Completati: {total_ok} OK, {total_fail} FAIL")
    log(f"Carte droppate: {total_dropped}")
    log(f"Tempo: {elapsed_total:.0f}s ({elapsed_total/60:.1f}min)")
    log(f"Costo: ${total_cost:.4f}")
    log("=" * 60)


if __name__ == "__main__":
    main()
