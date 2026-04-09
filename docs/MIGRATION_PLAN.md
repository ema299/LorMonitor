# Piano migrazione: analisi completa dentro App_tool

**Stato attuale (09 Apr 2026):** API 100% da PostgreSQL. Dashboard blob assemblato da PG.
Match importati ogni 2h. Matchup reports e killer curves importati da analisidef via cron.

## Architettura attuale (09 Apr 2026)

```
lorcana_monitor.py ──→ /matches/DDMMYY/*.json     ← unica fonte dati (auto-cleanup 5gg)
        │
        ├──→ import_matches.py (ogni 2h, ~1s) ──→ PostgreSQL (200K+ match)
        │
        ↓
daily_routine.py ──→ dashboard_data.json
        │                    │
        │                    └──→ import_matchup_reports.py (cron 05:30) ──→ PG matchup_reports
        │
        └──→ daily_routine.md (report umano, non usato da App_tool)

run_kc_production.sh (mar) ──→ killer_curves_*.json
                                     │
                                     └──→ import_killer_curves.py (cron mar 05:30) ──→ PG killer_curves

assemble_snapshot.py (cron 05:35) ──→ PG daily_snapshots ──→ /api/v1/dashboard-data
  └── assembla blob da PG direttamente (0.8s, 5.3 MB, 21 sezioni)

App_tool API → serve tutto da PG (query live <150ms)
```

**`daily_routine.py` non serve più per il serving.** Resta necessario solo come fonte dei matchup reports (analyzer 12K LOC).

**Retention dati:** turns JSONB mantenuti 90 giorni (replay viewer), poi NULL. Stats aggregate per sempre.

---

## Piano di esecuzione (7 fasi)

### Fase A: Import automatico match (senza daily_routine)
**Effort: basso | Rischio: basso | Prerequisiti: nessuno**

Oggi `import_matches.py` gira via cron alle 06:30. Ma i match arrivano in tempo reale da lorcana_monitor.py.

**Azione:**
1. Aggiungere cron entry che importa match ogni 2h (non solo 1x/giorno)
2. Oppure: inotify/watchdog su `/matches/` che triggera import al volo
3. Risultato: PG ha sempre gli ultimi match entro 2h

**File da modificare:** crontab, `scripts/import_matches.py` (aggiungere flag `--incremental`)

---

### Fase B-C: Meta stats + leaderboard/player stats da PG
**COMPLETATA 09 Apr 2026 — non servono materialized views**

Le query live su `matches` sono tutte <150ms con gli indici esistenti.
`stats_service.py` calcola WR, matrix, OTP/OTD, trend direttamente.
`players_service.py` calcola top players e leaderboard da PG.
`leaderboard_service.py` fetcha da duels.ink API con cache Redis 1h.

Le materialized views `mv_meta_share` e `mv_matchup_matrix` esistono ma non sono usate — le query live bastano.

---

### Fase D: Tech tornado + card usage da PG
**COMPLETATA — già funzionante**

`tech_service.py` calcola tech tornado da PG (CARD_PLAYED JSONB + consensus).

---

### Fase E: Dashboard snapshot assembler
**COMPLETATA 09 Apr 2026**

`snapshot_assembler.py` assembla il blob dashboard (21 sezioni, 5.3 MB) direttamente da PG in 0.8s.
`assemble_snapshot.py` gira in cron alle 05:35, scrive in `daily_snapshots(perimeter='full')`.
`/api/v1/dashboard-data` serve il blob — zero dipendenza da `dashboard_data.json`.

Frontend alleggerito: rimosso blob `_EMBEDDED_DATA` (8.8 MB → 418 KB), fetch da API.

**File creati:**
- `backend/services/snapshot_assembler.py` (~350 LOC)
- `scripts/assemble_snapshot.py`

**Sezioni non implementate (opzionali):**
- `best_plays` — analisi replay complessa, frontend la gestisce come opzionale
- `team` — dipende da match con perimeter 'mygame'

---

### Fase F: Matchup report refresh — DA FARE
**Effort: medio-alto | Rischio: medio**

I matchup reports (playbook, decklist optimizer, overview, loss_analysis) vengono dagli analyzer in analisidef (~12K LOC). Oggi importati via `import_matchup_reports.py` da `dashboard_data.json`.

**Approccio consigliato — Wrapper:**
1. Copiare i moduli di analisi in `App_tool/analysis/`:
   - `analyzer_v3.py`, `v4_helpers.py`, `deck_baselines.py`, `combo_analyzer.py`, `shared_utils.py`
2. Worker che legge match da PG, chiama gli analyzer, scrive in `matchup_reports`
3. Adattare `loader.py` con query PG

**Non riscrivere in SQL** — gli analyzer sono battle-tested, ~12K LOC di logica non banale.

---

### Fase G: Killer curves autonome — FUTURO
**Effort: medio | Prerequisiti: API credit OpenAI**

Oggi `run_kc_production.sh` gira in analisidef (mar 00:00, OpenAI, ~$1-2/sett).
`import_killer_curves.py` importa i risultati in PG (cron mar 05:30).

Quando si vorrà eliminare analisidef completamente:
1. Spostare `run_kc_production.sh` + `kc_spy.py` in App_tool
2. Adattare input: leggere match da PG invece che da JSON
3. Spostare cron OpenAI

**Non urgente** — l'import bridge funziona, nessuna duplicazione di costi.

---

## Stato riepilogativo

| Fase | Stato | Dipende da analisidef? |
|------|-------|----------------------|
| 0-6 | **FATTO** | No (runtime) |
| A | **FATTO** | Solo `/matches/` (lorcana_monitor) |
| B-C | **FATTO** | No |
| D | **FATTO** | No |
| E | **FATTO** | No |
| F | DA FARE | Sì (analyzer 12K LOC → matchup reports) |
| G | FUTURO | Sì (OpenAI killer curves) |

**Dopo Fase F:** `daily_routine.py` eliminabile. Solo `lorcana_monitor.py` resta.
**Dopo Fase G:** analisidef eliminabile completamente.

---

## Cosa NON migrare

- **`lorcana_monitor.py`** — daemon che intercetta partite live da duels.ink. Infrastruttura di collection, resta dov'è.
- **`pipeline/`** — snapshot di analisidef, non in produzione. Ignorare.
- **Report .md umani** — lasciarli in analisidef. App_tool serve solo API JSON.
