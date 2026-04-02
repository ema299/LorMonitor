# Piano migrazione: analisi completa dentro App_tool

**Stato attuale (02 Apr 2026):** API 100% da PostgreSQL (Fasi 0-6 completate).
Ma la **computazione** vive ancora fuori: `daily_routine.py` (3584 LOC) + analyzer root + analisidef/lib.

## Architettura attuale (cosa dipende da cosa)

```
lorcana_monitor.py ──→ /matches/DDMMYY/*.json     ← unica fonte dati
        │
        ↓
daily_routine.py (3584 LOC)                         ← il monolite
  ├── load_matches() → legge JSON da disco
  ├── fetch_leaderboards() → duels.ink API
  ├── deck_stats() + build_matrix() → calcola WR/meta
  ├── export_dashboard_json() (2619 LOC!) → blob JSON
  └── scrive dashboard_data.json + daily_routine.md
        │
        ↓
import scripts → PostgreSQL                          ← bridge manuale
        │
        ↓
App_tool API → serve da PG
```

**Cron attuale (UTC):**
- 06:30 → import_matches.py (JSON → PG)
- 07:00 → lorcana_monitor.py report
- 07:01 → daily_routine.py (genera dashboard_data.json)
- Martedì 00:00 → run_kc_production.py (killer curves via OpenAI)

## Architettura target

```
lorcana_monitor.py ──→ /matches/DDMMYY/*.json
        │
        ↓
import_matches.py ──→ PostgreSQL (già funziona, 136K match)
        │
        ↓
App_tool workers (nuovi)
  ├── worker_daily_snapshot.py   → aggrega da PG, scrive daily_snapshots
  ├── worker_matchup_reports.py  → rigenera matchup_reports da PG
  └── worker_refresh_views.py    → refresh materialized views
        │
        ↓
App_tool API → serve tutto da PG (già fatto)
```

**`daily_routine.py` viene eliminato.** Ogni sua funzione diventa una query PG o un worker.

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

### Fase B: Materialized views per meta stats
**Effort: medio | Rischio: basso | Prerequisiti: Fase A**

`daily_routine.py` calcola WR matrix, meta share, OTP/OTD, trend.
Tutto questo è derivabile con SQL da `matches`.

**Azione:**
1. Creare materialized views:
   - `mv_meta_share` — % deck per perimetro (già esiste, va popolata)
   - `mv_matchup_matrix` — WR deck vs deck per perimetro (già esiste)
   - `mv_otp_otd` — WR on-the-play vs on-the-draw
   - `mv_deck_trend` — delta giornaliero meta share
2. Creare `worker_refresh_views.py` che fa `REFRESH MATERIALIZED VIEW CONCURRENTLY`
3. Cron: ogni 2h dopo import match

**Funzioni di daily_routine.py sostituite:**
- `deck_stats()` (338 LOC) → `mv_meta_share`
- `build_matrix()` (322 LOC) → `mv_matchup_matrix`
- sezioni OTP/OTD → `mv_otp_otd`
- sezione Trend → `mv_deck_trend`

---

### Fase C: Leaderboard + top players da PG
**Effort: basso | Rischio: basso | Prerequisiti: nessuno**

`leaderboard_service.py` già fetcha da duels.ink API con cache Redis 1h.
Ma `daily_routine.py` fa anche scouting PRO (WR per giocatore, deck giocati, ecc.).

**Azione:**
1. Creare tabella `player_stats` (o usare daily_snapshots con perimeter='pro_players')
2. Worker che calcola stats per player dai match in PG:
   ```sql
   SELECT player_name, deck, COUNT(*), SUM(CASE WHEN winner THEN 1 END)
   FROM matches WHERE player_name IN (SELECT name FROM leaderboard_cache)
   GROUP BY player_name, deck
   ```
3. Esporre via `/api/v1/monitor/pro-players`

**Funzioni di daily_routine.py sostituite:**
- `fetch_leaderboards()` (882 LOC) → già in leaderboard_service.py
- sezione Top Players → query PG su matches
- sezione PRO Detail → query PG su matches

---

### Fase D: Tech tornado + card usage da PG
**Effort: già fatto | Rischio: zero**

`tech_service.py` già calcola tech tornado da PG (CARD_PLAYED JSONB + consensus).
Nessuna azione necessaria — questa fase è completata.

---

### Fase E: Dashboard snapshot assembler
**Effort: medio | Rischio: medio | Prerequisiti: Fasi B, C**

Oggi il blob `dashboard_data.json` viene generato da `export_dashboard_json()` (2619 LOC dentro daily_routine.py) e poi importato in `daily_snapshots(perimeter='full')`.

**Azione:**
1. Creare `worker_daily_snapshot.py` che assembla il blob direttamente da PG:
   ```python
   blob = {
       "meta": compute_meta(db),           # da mv_meta_share
       "perimeters": compute_perimeters(db), # da mv_matchup_matrix + mv_meta_share
       "leaderboards": fetch_leaderboards(), # da leaderboard_service
       "pro_players": compute_pro_stats(db), # da matches
       "consensus": get_consensus(db),       # da consensus_lists
       "reference_decklists": get_refs(db),  # da reference_decklists
       "tech_tornado": compute_tech(db),     # da tech_service
       "matchup_analyzer": build_analyzer(db), # da matchup_reports
       "card_images": get_card_images(db),   # da cards
       "card_types": get_card_types(db),     # da cards
       "card_inks": get_card_inks(db),       # da cards
   }
   # Upsert in daily_snapshots(perimeter='full')
   ```
2. Cron: alle 07:30 (dopo import match)
3. `/api/v1/dashboard-data` già serve da daily_snapshots — zero modifiche API

**Funzione di daily_routine.py sostituita:**
- `export_dashboard_json()` (2619 LOC) → worker_daily_snapshot.py (~200 LOC)

---

### Fase F: Matchup report refresh
**Effort: medio-alto | Rischio: medio | Prerequisiti: Fase A**

I report matchup (playbook, decklist optimizer, overview, loss_analysis) oggi vengono da `dashboard_data.json` che li prende dal pipeline di analisi (analyzer_v3.py + v4_helpers.py + gen_decklist.py).

Questi sono i file più complessi: **~12K LOC** di analisi statistica e ottimizzazione.

**Due approcci possibili:**

**Approccio 1 — Wrapper (pragmatico, consigliato):**
1. Copiare i moduli di analisi in `App_tool/analysis/`:
   - `analyzer_v3.py` → analisi worst case, sinergie
   - `v4_helpers.py` → ottimizzazione deck
   - `deck_baselines.py` → consensus baseline
   - `combo_analyzer.py` → combo detection
   - `shared_utils.py` → costanti
2. Worker `worker_matchup_reports.py` che:
   - Legge match da PG (non da JSON su disco)
   - Chiama gli analyzer esistenti
   - Scrive risultati in `matchup_reports`
3. Adattatore: sostituire `loader.py` con query PG

**Approccio 2 — Riscrittura SQL (ambizioso):**
Reimplementare la logica degli analyzer come query PG pure.
Possibile per overview/playbook, impossibile per worst case analysis e policy simulation.
Non consigliato: troppo rischio e troppo effort per poco guadagno.

**Consiglio: Approccio 1.** Gli analyzer sono battle-tested, ~12K LOC di logica non banale.
Copiarli e adattare l'input da JSON a PG è 10x più sicuro che riscrivere.

---

### Fase G: Killer curves autonome
**Effort: medio | Rischio: basso | Prerequisiti: Fase F, API credit**

`run_kc_production.py` genera killer curves via OpenAI API (gpt-5.4-mini).
Oggi gira settimanale il martedì.

**Azione:**
1. Creare `worker_killer_curves.py` che:
   - Legge match recenti da PG
   - Genera digest per matchup instabili
   - Chiama OpenAI API (quando disponibile)
   - Scrive in `killer_curves` table
2. Adattare `run_kc_production.py` per leggere da PG invece che da JSON
3. Integrare in cron settimanale

**Nota:** Richiede API credit OpenAI. Finché non disponibile, le killer curves
restano quelle già importate — sono pre-generate e funzionanti.

---

## Dipendenze tra fasi

```
A (import auto) ──→ B (materialized views) ──→ E (snapshot assembler)
                                                    ↑
                 ──→ C (leaderboard/pro) ───────────┘
                                                    
                 ──→ F (matchup reports) ──→ G (killer curves)

D (tech tornado) ──→ già completata
```

## Priorità consigliata

| Ordine | Fase | Effort | Impatto |
|--------|------|--------|---------|
| 1 | A | basso | Match sempre freschi in PG |
| 2 | B | medio | Meta stats calcolate da PG, no daily_routine |
| 3 | C | basso | PRO stats da PG |
| 4 | E | medio | Dashboard blob da PG, daily_routine.py eliminabile per serving |
| 5 | F | alto | Analisi matchup autonoma (copare analyzer ~12K LOC) |
| 6 | G | medio | Killer curves autonome (serve API credit) |

**Dopo Fase E:** `daily_routine.py` non serve più per il serving.
Resta utile solo per generare i report .md umani e i report matchup (Fase F).

**Dopo Fase F:** `daily_routine.py` eliminabile completamente.
Solo `lorcana_monitor.py` resta necessario (data collection).

---

## Cosa NON migrare

- **`lorcana_monitor.py`** — resta dov'è. È un daemon che pollla duels.ink
  e scrive JSON. Non ha senso portarlo in App_tool, è infrastruttura di collection.
- **`pipeline/`** (vecchio) — analisi ad-hoc, non in produzione. Ignorare.
- **Report .md umani** — se servono ancora, lasciarli in analisidef.
  App_tool serve solo API JSON, non genera documenti.

## Stima totale

| Metrica | Valore |
|---------|--------|
| LOC da eliminare (daily_routine.py) | ~3584 |
| LOC da copiare+adattare (analyzer) | ~12K |
| LOC nuovi (workers + views) | ~500-800 |
| File nuovi in App_tool | ~5-7 |
| Tempo stimato (tutte le fasi) | — |
