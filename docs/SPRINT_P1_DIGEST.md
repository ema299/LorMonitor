# Sprint P1 — Native PG digest generator (shadow mode)

Liberation Day, step 1. We are cutting the dependency between downstream
LLM pipelines (killer-curves, blind playbook) and the stale
`analisidef/output/archive_*.json` intermediate files. The replacement reads
directly from PostgreSQL with a 30-day rolling window, epoch-aware bounds
and the same compact schema so downstream consumers can switch without code
changes at cutover time.

## What shipped

| Path | Purpose |
|------|---------|
| `db/migrations/versions/b7c2e9d41058_add_meta_epochs_table.py` | `meta_epochs` reference table + two seed rows |
| `backend/models/meta_epoch.py` | SQLAlchemy model (registered in `backend/models/__init__.py`) |
| `backend/services/meta_epoch_service.py` | `get_current_epoch(db)` + list/get helpers |
| `pipelines/digest/generator.py` | `generate_digest(db, our, opp, fmt, window_days, min_games)` |
| `scripts/generate_digests.py` | Batch runner, writes to `output/digests/` |
| `scripts/diff_digests.py` | Schema parity between legacy and native |
| `docs/SPRINT_P1_DIGEST.md` | This file |

## What is NOT shipped

1. **No cutover.** The playbook/KC generators still read
   `analisidef/output/digest_*.json`. No reader was modified.
2. **No cron change.** `run_kc_production.sh` and the matchup-report importer
   continue to run on the legacy tree.
3. **No deletion.** `analisidef/` is untouched.
4. **No LLM calls.** The digest is input to the LLM; this sprint only
   produces the input.
5. **No numeric parity expected.** Windows differ by design — legacy is
   whatever analisidef batched last, native is 30 days fresh.

## How to run (shadow smoke)

```bash
cd /mnt/HC_Volume_104764377/finanza/Lor/Analisi_deck/App_tool

# 1. apply migration
venv/bin/alembic upgrade head

# 2. full shadow batch (all 132 core + 132 infinity pairs)
venv/bin/python3 scripts/generate_digests.py --format all

# smoke subset — 3 core matchups
venv/bin/python3 scripts/generate_digests.py --format core --limit 3

# single-pair probe
venv/bin/python3 scripts/generate_digests.py --pair AmSa AbE --format core

# 3. compare schemas against legacy output
venv/bin/python3 scripts/diff_digests.py
```

Output directory: `App_tool/output/digests/digest_{OUR}_vs_{OPP}[_inf].json`.
The legacy analisidef output remains at
`analisidef/output/digest_{OUR}_vs_{OPP}[_inf].json`.

## Design notes

### Epoch gate

`meta_epochs` records rotation windows. The current epoch is the row with
`ended_at IS NULL`. The generator computes its window as::

    since = max(current_epoch.started_at, NOW() - window_days)

and excludes matches whose event log references any card outside
`current_epoch.legal_sets`. Seed rows:

| id | name | started_at | ended_at | legal_sets |
|----|------|------------|----------|-----------|
| 1 | Pre-Set12 | 2026-01-01 | 2026-03-27 | {1..11} |
| 2 | Set11 settled | 2026-03-28 | NULL | {1..11} |

When Set 12 rotates in, bump epoch 2's `ended_at` and insert a new row.

### Deck code handling

PG stores canonical codes (`AmSa`, `EmSa`); analisidef's `DECK_COLORS` uses
legacy codes (`AS`, `ES`). The generator accepts both at the public
interface; the PG query uses canonical and the archive metadata preserves
canonical.

### Reuse of analisidef enrichment pipeline

The compacting logic is a 1:1 port of
`analisidef/lib/gen_digest.py` lines 55-333, but the *aggregate builder*
(`_build_aggregates`, ~600 LOC of heavy analytics) and the per-game
enricher (`enrich_games`, ~200 LOC) are reused as libraries by importing
`analisidef.lib` directly. Porting those would have tripled the sprint
size for no additional output-schema benefit. They are scheduled for
removal in a later sprint (tracked: "Phase F — fully-native enrichment").

### Fail-closed behaviour

* Fewer than `min_games` losses → `generate_digest` returns `None`, batch
  runner emits `status=SKIP_LOW_GAMES`.
* PG row has null/empty `turns` JSONB → skipped as unparseable.
* `matches.winner` NULL → fallback scan of logs; still NULL → skip.
* Illegal card in logs (outside epoch's `legal_sets`) → match dropped.

### Known deviations from the spec

1. The generator preserves a documented **bug** from legacy gen_digest.py
   (cards contributed via `mechanics_cards` are looked up under the
   pre-rename key rather than `patterns_cards`, so they never reach
   `all_cards`). Bug-for-bug parity was chosen deliberately to keep the
   shadow diff meaningful.
2. Optional `our_playbook` field from `combo_intelligence` is NOT
   emitted. It isn't part of the 15 required fields. Will ship in a later
   sprint once `combo_intelligence` is ported.
3. An extra top-level key `_provenance` is emitted (source tag,
   window, epoch id, dropped-row counters, generation timestamp).
   The diff script ignores it explicitly. Downstream consumers should too.

## Cutover checklist (T+14 days)

Do these once the shadow diff is clean for two full weeks AND the user
confirms the native digests look sane on spot-checks.

1. `grep -rn "analisidef/output/digest_" App_tool/pipelines/playbook/generator.py` — flip
   the path to `App_tool/output/digests/digest_` (or delete the hard-coded
   `ANALISIDEF_BASE` and use `output/digests` unconditionally).
2. Same grep in `scripts/generate_playbooks.py` and any KC prompt builder
   that runs in App_tool.
3. Add cron entry for `scripts/generate_digests.py --format all` (2h
   cadence, staggered with `import_matches` — e.g. `15 */2 * * *`).
4. **Simultaneously** disable the analisidef digest generation cron in
   `run_kc_production.sh` / its wrapper (per project policy
   `feedback_no_duplicate_cron.md`). Do NOT leave both running.
5. Monitor `output/digests/*.json` mtimes and sizes for 48h.
6. After 30 days: drop the bridge imports in
   `pipelines/digest/generator.py` (analisidef loader/enricher) as part
   of Phase F.

## Rollback

If the native output turns out to be wrong post-cutover:

1. Add `DIGEST_SOURCE = "legacy"` to `backend/config.py` (constant, no env
   var needed).
2. In the cutover-point readers, branch on that constant: `"legacy"`
   restores the old `analisidef/output/digest_*.json` path.
3. Re-enable the analisidef cron. Re-disable the App_tool cron.
4. File an incident: note which field(s) diverged and why the shadow
   diff did not catch it.

The Alembic migration is independently revertible
(`alembic downgrade -1` drops `meta_epochs`). The shadow output
directory is just files — `rm -rf output/digests` has no side effects.
