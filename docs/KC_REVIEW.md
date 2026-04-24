# Killer Curves — Review costo / qualità

> Apertura: 2026-04-22. Doc vivo — da aggiornare ad ogni batch (martedì 01:00) e ad ogni cambio prompt/schema.

## 1. Scopo

Tracciare in un unico posto:
1. **Costo** batch KC (OpenAI) e trend nel tempo.
2. **Qualità output** (completezza schema, aderenza al prompt, lingua, coerenza coi digest).
3. **Decisioni** prese su prompt/modello/schema con razionale e data.

Motivo: user-facing complaint del 2026-04-21 "output insufficiente, bisogno di una review perché spendo troppo". Senza un file di riferimento, i cambi prompt/schema producono drift silenzioso (vedi §4).

---

## 2. Pipeline corrente (snapshot 2026-04-22)

```
meta_epochs.legal_sets ──┐
                         ▼
pipelines/digest/generator.py  (digest PG, window 30gg)
                         │
                         ▼
pipelines/kc/build_prompt.py   (istruzioni_compact + rules_compact + guards:
                         │      color / sequence / legality)
                         ▼
scripts/generate_killer_curves.py  (OpenAI API, modello env-configurabile)
                         │
                         ▼
pipelines/kc/vendored/postfix_response_colors.py  (postfilter colori + legality)
                         │
                         ▼
PG killer_curves  (is_current + version)
                         │
                         ▼
snapshot_assembler → dashboard-data blob → frontend Coach V2
```

**Config runtime**:
- Modello default: `gpt-5.4-mini` (env `OPENAI_MODEL`)
- Pricing tracciato: `gpt-4o-mini` $0.15/$0.60, `gpt-5.4-mini` $0.75/$4.50, `gpt-4o` $2.50/$10.00 per 1M tok
- Temperature: 0 (deterministic)
- Prompt language: ENGLISH (hardcoded in `build_prompt.py:7`)
- Schema target: **v2** (risposta strutturata con `headline`, `core_rule`, `priority_actions`, `what_to_avoid`, `stock_build_note`, `off_meta_note`, `play_draw_note`, `failure_state`)

**Cron**:
- `kc_spy_canary.py` — daily 04:05 UTC, 1 matchup canary, ~$0.05/day (cost guard)
- `generate_killer_curves.py` — full batch martedì 01:00 UTC
- `import_killer_curves.py` — legacy bridge, `is_current=false` al nuovo batch
- `monitor_kc_freshness.py` — daily 07:00, alert se stale

---

## 3. Stato DB al 2026-04-22 (baseline)

Query su `killer_curves WHERE is_current=true`:

| Metrica | Valore |
|---|---|
| Matchup totali (is_current) | 749 (core 554 + infinity 195) |
| Curve totali | 2'458 |
| Avg curve/matchup | core 3.38, infinity 3.01 |
| Matchup con 0 curve | 10 (5 core + 5 infinity) |
| Ultimo batch significativo | 2026-04-21 (166 matchup ri-gen) |
| Freschezza 7gg | 167/749 = **22%** |
| Freschezza 14gg | 220/749 = **29%** |
| Freschezza 30gg | 742/749 = **99%** |

**Interpretazione**: la maggioranza delle curve ha >14gg — consistente con schedulazione settimanale, ma significa che una modifica prompt/schema si propaga lentamente se non fai full rebuild.

---

## 4. Problemi identificati (prioritizzati)

### P0 — Schema v2 adottato solo al 25.1%

2'458 curve totali, di cui solo **617 hanno i campi v2** (headline / core_rule / priority_actions / what_to_avoid / failure_state / stock_build_note / off_meta_note / play_draw_note).

**Implicazione**: il 75% delle curve servite al frontend è ancora in schema v1 (solo `response.strategy` one-liner). Il frontend Coach V2 legge i campi strutturati con fallback — oggi sta mostrando un fallback per 3 curve su 4.

**Causa probabile**: schema v2 introdotto di recente (`schemas/killer_curves.schema.json` modificato in `git status` M), batch completo non ancora fatto sotto il nuovo prompt.

**Azione**: `OPENAI_MODEL=gpt-5.4-mini venv/bin/python scripts/generate_killer_curves.py --force-all` per ricostruire. Stima costo full: vedi §5.

### P0 — 42.5% delle strategie in italiano invece che in inglese

Controllo su 2'393 strategie non vuote:
- marker italiani (`Priorità`, `perché`, `contro`, `non lasciare`, `nostro`, …): **1'017 match (42.5%)**.

Esempi recenti (generated_at ≥ 14gg):
- `AmSa vs AbE` (16/04): "Priorità assoluta: non lasciare che Grandmother Willow…"
- `AmSa vs AbSt` (14/04): "Priorità: togliere il primo singer…"
- `RS vs AmyR` (14/04): "Priorità assoluta: non concedere il primo spike…"

**Contraddizione**: `pipelines/kc/prompts/istruzioni_compact.md:81,85,86,130` dicono esplicitamente "in English". `build_prompt.py:7` idem. Il modello sta comunque producendo IT — probabilmente perché il digest input è in inglese ma esempi in-prompt (few-shot interni) o il prior del modello drifta sui nomi carte italiane / vecchie run.

**Azione**: aggiungere **post-check lingua** in `generate_killer_curves.py` (regex marker IT → reject + retry, o warn + flag). Considerare anche un system prompt esplicito "Output MUST be 100% English. Any Italian word in response.strategy will cause validation failure".

### P1 — Zero cost tracking in DB

Tabella `killer_curves` non ha colonna `meta` / `cost_usd` / `tokens`. Il costo esiste solo come stdout del batch script.

**Implicazione**: impossibile rispondere oggi a "quanto ho speso in KC questa settimana / questo mese" da una query. Il concern "spendo troppo" non è misurabile in modo riproducibile.

**Azione**: aggiungere colonna `meta JSONB` (o `kc_runs` table separata con `cost_usd`, `input_tokens`, `output_tokens`, `model`, `duration_s`, `run_id`). Migration additiva. Il `kc_spy_canary.py` già produce cost per run — serve solo persistere.

### P1 — 10 matchup con 0 curve

5 core + 5 infinity. Non sappiamo se è:
- sample < soglia minima (digest vuoto → LLM genera vuoto correttamente), o
- LLM ha fallito schema validation e output è stato rigettato (gap in logging).

**Azione**: log dedicato `output/kc_empty_matchups.json` con matchup + motivo (digest rows, last attempt timestamp, error).

### P2 — Postfilter colori / legality su 1047 matchup — efficacia non tracciata

`pipelines/kc/vendored/postfix_response_colors.py` rimuove carte off-color / illegal dalla risposta. Non sappiamo quante carte/curve rimuove per batch — quindi se il prompt peggiora e il postfilter pulisce molto, noi vediamo "output ok" senza capire che stiamo sprecando token.

**Azione**: aggiungere telemetria post-filter (cards_rejected per run, % curve scartate per schema fail) al JSON di meta-run.

### P2 — Schema drift non documentato

`schemas/killer_curves.schema.json` è modificato (M in git status) ma nessun CHANGELOG. Se il prompt evolve e lo schema evolve, ma non c'è versioning esplicito, è impossibile correlare "curve vecchie" con "prompt vecchio".

**Azione**: aggiungere `schema_version` nel JSON curve (oltre a `version` che è già nel record PG ma indica solo numerazione batch). Nel record PG aggiungere `prompt_hash` (SHA256 del prompt generato) per diff forensic.

---

## 5. Costo — analisi e stima

### Dati osservati

Dal docstring in `generate_killer_curves.py:24`:
> Typical cost: ~$0.02-0.05 per matchup with gpt-5.4-mini (~$1-3/week full batch).

Canary `kc_spy_canary.py` = $0.05/die ≈ $1.50/mese (cost floor).

### Stima full rebuild con schema v2

749 matchup × $0.035 avg = **~$26 per full rebuild**.

Se lo facciamo oggi + 1 rebuild/settimana = ~$104/mese peggior caso. Se incrementale (solo matchup con digest cambiato >3gg), target ~$5-8/settimana.

### Quanto ha già inciso schema v2

617 curve v2 ÷ ~3.3 curve/matchup = ~187 matchup ri-generati dopo intro schema v2. Assumendo $0.035 avg: **~$6.5 speso fin qui per la transizione schema**.

### Leve di riduzione

| Leva | Effetto stimato | Rischio |
|---|---|---|
| Switch `gpt-5.4-mini` → `gpt-4o-mini` | −80% ($0.75+$4.50 vs $0.15+$0.60 per 1M tok) | Qualità: 4o-mini è nettamente meno bravo su JSON strutturato / few-shot. **Sconsigliato senza A/B** |
| Compressione prompt (taglio sezioni digest meno usate) | −20-30% input tok | Basso se guidato da audit (ci sono sezioni che il modello non cita mai in output) |
| Rebuild solo se digest_hash cambia | −60% numero matchup ri-gen | Zero (additivo, ma serve colonna digest_hash) |
| Cache output su `(digest_hash, prompt_hash)` | Pareggia qualità, taglia costo se rebuild forzati per errore | Zero |

**Raccomandazione**: prima *misurare* (P1 cost tracking), poi *ottimizzare* (digest_hash). Non cambiare modello senza A/B controllato.

---

## 6. KPI da monitorare

Dashboard interna (aggiungere a `monitor_kc_freshness.py` o a nuovo script settimanale):

| KPI | Soglia verde | Soglia gialla | Soglia rossa |
|---|---|---|---|
| % curve con schema v2 | ≥95% | 70-95% | <70% |
| % strategy in inglese | ≥99% | 90-99% | <90% |
| Freshness 7gg | ≥60% | 30-60% | <30% |
| Cost settimanale | <$5 | $5-10 | >$10 |
| Matchup vuoti (is_current, 0 curve) | ≤5 | 6-15 | >15 |
| Cards rejected dal postfilter per run | <5% | 5-15% | >15% |

Oggi (22/04): **rosso** su schema v2 (25%), **rosso** su lingua inglese (57.5%), **giallo** su freshness 7gg (22% — ma atteso post-schema intro).

---

## 7. Backlog azioni

| # | Task | Effort | Priorità | File |
|---|---|---|---|---|
| 1 | Forzare full rebuild con schema v2 | 30 min + batch cost ~$26 | P0 | `scripts/generate_killer_curves.py --force-all` |
| 2 | Post-check lingua inglese con retry | 1-2h | P0 | `scripts/generate_killer_curves.py` |
| 3 | ~~Cost tracking persistente (migration + hook)~~ ✅ **FATTO 2026-04-22** | 3-4h | P1 | migration `8890033ea91a` + `generate_killer_curves.py` + `scripts/kc_cost_report.py` — vedi §9 |
| 4 | Log empty matchup con reason | 1h | P1 | `scripts/generate_killer_curves.py` |
| 5 | Telemetria postfilter (n carte tagliate) | 1-2h | P2 | `pipelines/kc/vendored/postfix_response_colors.py` |
| 6 | `prompt_hash` + `digest_hash` + `schema_version` in record | 2h | P2 | migration + `build_prompt.py` + `generate_killer_curves.py` |
| 7 | Incremental rebuild (solo se digest_hash cambia) | 3-4h | P2 | `generate_killer_curves.py` — richiede task 6 |
| 8 | A/B `gpt-4o-mini` vs `gpt-5.4-mini` su 20 matchup | 1h + ~$2 | P3 | ad-hoc test |

---

## 8. Decisioni storiche (log)

| Data | Decisione | Razionale |
|---|---|---|
| ~2026-03 | D2 cutover: pipeline KC nativa in App_tool | Chiudere dipendenza da `analisidef/run_kc_production.py` |
| 2026-04-20 | Doppio guard legality Core (prompt-time + post-filter) | Incidente: curve Core contaminate da carte Infinity |
| 2026-04-~20 | Schema v2 con campi strutturati `headline/core_rule/priority_actions/...` | `response.strategy` one-liner insufficiente per UI |
| 2026-04-21 | Prompt language locked EN in `build_prompt.py:7` | User feedback: app è 100% EN |
| 2026-04-22 | Aperto questo doc | Concern user "spendo troppo, output insufficiente" |
| 2026-04-22 | **Cost tracking persistente implementato** (task #3 backlog) | Vedi §9 delivery log |
| 2026-04-22 | **Cleanup `is_current` duplicati** (A + B) | 484 righe stale demotate, pipeline fixed upstream |

---

## 9. Delivery log

### 2026-04-22 — Task #3 cost tracking persistente ✅

**Cosa è entrato**:

- `db/migrations/versions/8890033ea91a_add_meta_to_killer_curves.py` — migration additiva, colonna `meta JSONB NOT NULL DEFAULT '{}'` su `killer_curves`. Parallel branch off `7dec24a98839` (convive con set12 in cassetto).
- `backend/models/analysis.py` — campo `meta: Mapped[dict]` sul modello `KillerCurve`.
- `scripts/generate_killer_curves.py` — ogni upsert ora popola:
  - `run_id` — UUID per batch (`YYYYMMDDThhmmssZ-{hex6}`)
  - `model` — modello effettivo usato
  - `cost_usd`, `input_tokens`, `output_tokens`, `duration_s` — già calcolati, ora persistiti
  - `prompt_hash` — SHA256 prefix 16 del prompt completo (diff forensic)
  - `cards_dropped` — quante carte il postfilter ha tolto
  - `n_curves` — numero curve generate
  - `generated_utc` — timestamp ISO
- `scripts/kc_cost_report.py` — report read-only aggregato (total, by model, recent runs, top-N expensive, drill su `--run-id`). JSON o testo.

**Stato migration**: applicata su PG produzione (`alembic upgrade 8890033ea91a`), 777 record esistenti hanno `meta = '{}'` (backfill impossibile, dati storici persi).

**Validazione**:
- Sintassi Python: OK
- Dry-run script: OK (132 matchup core pronti, run_id generato)
- SQL roundtrip meta: OK (insert → select → parse)
- E2E con OpenAI: **BLOCCATO da quota 429 insufficient_quota** sulla key in `/tmp/.openai_key`

**Finding critico quota**:

Il tentativo E2E di 1 matchup ha restituito:

```
Error code: 429 - insufficient_quota — You exceeded your current quota,
please check your plan and billing details.
```

La chiave OpenAI in `/tmp/.openai_key` è saturata. **Il batch martedì 01:00 della settimana prossima fallirà** se non si topuppa o non si cambia key. Questo spiega anche una parte del concern "spendo troppo": probabilmente la spesa accumulata negli ultimi batch ha consumato il budget.

**Azioni di follow-up immediate**:
1. Verificare billing OpenAI: quanto è stato speso nell'ultimo mese? → risponde al concern reale.
2. Se confermato "troppo", valutare:
   - Switch a `gpt-4o-mini` per A/B (task #8 backlog)
   - Rebuild incrementale via `digest_hash` (task #7 — ora sbloccato, abbiamo `prompt_hash`)
3. Sbloccata colonna `meta` → nei prossimi batch la spesa sarà **per-record tracciabile**; prima query utile:

```sql
SELECT DATE_TRUNC('week', generated_at) AS wk,
       SUM((meta->>'cost_usd')::float) AS cost,
       COUNT(*) FILTER (WHERE meta ? 'cost_usd') AS tracked
FROM killer_curves
WHERE meta ? 'cost_usd'
GROUP BY wk ORDER BY wk DESC;
```

o via script: `venv/bin/python scripts/kc_cost_report.py --days 30`.

---

*Ultimo update: 2026-04-22 — task #3 chiuso, task #2 (lingua EN) e #1 (full rebuild v2) restano aperti in backlog.*

---

### 2026-04-22 — Cleanup `is_current` duplicati (A + B) ✅

**Cosa è entrato**:

- **Demote SQL one-shot** su PG: 484 righe `is_current=true` "stale" (che non erano la versione più recente della propria coppia `(format, our, opp)`) sono state demotate a `is_current=false`.
- **Safety check pre-cleanup** eseguito: analizzati i 9 matchup dove la newest ha meno curve della penultima. Risultato: 4 casi = duplicati/overlap, 3 casi = meta-vecchia, 2 casi = info teoricamente unica ma in italiano + schema v1. **Nessuna info strategica rilevante persa.**
- **Backup** degli ID demoted scritto in `output/kc_is_current_demote_backup_YYYYMMDDTHHMMSSZ.json` (serve per rollback rapido: `UPDATE SET is_current=true WHERE id IN (...)`).
- **Fix upstream**: `scripts/generate_killer_curves.py` e `scripts/import_killer_curves.py` ora eseguono `UPDATE is_current=false` sulle righe precedenti della stessa coppia PRIMA dell'UPSERT. Nessun duplicato futuro.

**Stato DB post-cleanup**:

| Metrica | Pre | Post |
|---|---|---|
| Righe `is_current=true` | 749 | 265 |
| Matchup unici | 265 | 265 |
| Matchup con >1 `is_current` | 186 | 0 |
| Determinismo read | No (ambiguo) | Sì |

**Conseguenza**: il frontend / snapshot_assembler ora restituisce esattamente UNA curve-family per matchup, sempre la più recente. Eliminato il rumore del 65%.

**Rollback**: `UPDATE killer_curves SET is_current=true WHERE id IN (<id_list>)` dove la lista è in `output/kc_is_current_demote_backup_*.json`.

---

### 2026-04-22 — Verification + deploy ✅

**Costo totale test**: $0.086

**Test eseguiti**:
- `scripts/kc_spy_canary.py` ($0.05): canary core + infinity OK, validazione 265 righe `is_current` OK, 0 FAIL/issues
- `scripts/generate_killer_curves.py --pair EmSa AmAm --force` ($0.036): E2E validato
  - Fix B: riga 21/04 demoted auto a `is_current=false`, riga 22/04 entra `is_current=true`
  - Meta: tutti 10 campi popolati (cost_usd, tokens, prompt_hash, duration, run_id...)
  - Lingua: 4/4 curve in inglese (il prompt sta generando EN correttamente)
  - Schema v2: 4/4 curve con 8/8 campi v2

**Deploy**:
- uvicorn restart: pid 3661913, preserva `--workers 2`
- Cache dashboard-data bustata: blob rigenerato (11.3 MB, 17s cold), 132 matchup core con KC, 483 curve totali
- Endpoint validato: `/api/v1/dashboard-data` → HTTP 200, EmSa vs AmAm mostra 4 curve con headline EN e 4/4 v2 fields

**Insight emerso — task #2 downgradato**:

Il 42.5% italiano nel DB è **overhang storico**, non problema attivo. Il prompt con lock EN in `build_prompt.py:7` sta generando correttamente in EN (validato sul run live). Quindi:
- Task #2 (post-check lingua + retry) → P3 (safety net opzionale)
- Task #1 (full rebuild schema v2) → diventa la leva combinata: risolve simultaneamente schema v2 + overhang italiano in un solo batch

**Nuova stima full rebuild**: 265 matchup × $0.036 (osservato) = **~$9.5** invece di $26 stimati pre-cleanup. Risparmio ~$16 da A+B.

---

*Ultimo update: 2026-04-22 — task #3 (cost tracking), A+B (is_current cleanup) chiusi, deploy verificato. Rimangono: task #1 (full rebuild ~$9.5) e task C (incremental rebuild 3-4h coding).*
