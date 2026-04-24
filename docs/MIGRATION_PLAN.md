# Piano migrazione: analisi completa dentro App_tool

**Obiettivo prodotto:** `App_tool` e' l'unica app pubblica che serve gli utenti.
`analisidef` e' un motore transitorio di calcolo/import, non il prodotto.

**Stato attuale (20 Apr 2026 — incident hardening static data + KC legality):**
API quasi 100% da PostgreSQL. Dashboard blob assemblato **live** da PG
(snapshot_assembler.py, cache 2h). Match importati ogni 2h con legality gate core
(Sprint-0). Blind Deck Playbook nativo generato in App_tool via OpenAI (Mossa B).

**Aggiornato oggi (20/04/2026):**
- fix importer statico: snapshot InkDecks parziale non puo' piu' disattivare globalmente `is_current` per tutti i deck
- recovery DB eseguito live: promozione del record piu' recente per ogni deck rimasto senza `is_current=true`
- `player_cards` separati per formato nel blob (`core` + `infinity`), cosi' il compare "Best Format Players" non resta core-only
- killer curves Core protette da doppio guard di legalita': prompt-time + post-filter prima dell'upsert

**Chiuso oggi (commit `ab03c6e` → `9ec0f45`):**
- P0 monitor freshness + baseline (commit `ab03c6e`)
- P1 digest nativo PG-first in shadow mode + `meta_epochs` migration (commit `ace88dc`)
- P1.5 vendorized freeze 1200 LOC analytics, `DIFFS=0` su 10 matchup (commit `7d08425`)
- P2.5a R1 replay endpoint legge da PG `replay_archives` (271 archive, 601MB JSONB)
- P2.5b R2 kc_spy runtime legge da PG `kc_spy_reports` (commit `8c2b84a`)
- P2.5c R3 `llm_worker.py` rimosso come dead code (commit `9ec0f45`)

**Aperto:** D1 (playbook → digest file analisidef, cutover 16/04), D2 (`import_killer_curves`, target P2), D3 (`import_matchup_reports`, target P3).

**Correzioni emerse da code review (16 Apr 2026):**
- Il serving runtime e' effettivamente su PG, ma il repo contiene ancora **drift documentale**: alcuni documenti dichiarano chiusi o irrilevanti componenti che sono ancora presenti come bridge o storico.
- Le materialized views `mv_meta_share` / `mv_matchup_matrix` **non servono il dashboard runtime corrente**, ma sono ancora refreshate da worker/script legacy; quindi non vanno descritte come "inesistenti" o "rimosse", solo come **non critiche per il serving**.
- `daily_snapshots` **non serve il blob live**, ma resta in uso per storico/benchmark e ha ancora script legacy attorno (`import_snapshot.py`, `assemble_snapshot.py`, `import_history.py`).
- Restano alcuni **rischi operativi non legati ad analisidef** da chiudere in parallelo: secret hardcoded `DUELS_SESSION`, fallback `/tmp/.openai_key`, rate limiting "per-tier" non effettivo, CORS troppo permissivo/incoerente in prod.

**Nuovi rischi operativi emersi dall'incidente del 20 Apr 2026:**
- lo scraper InkDecks upstream puo' restituire snapshot **sparsi** pur girando regolarmente ogni giorno; il problema quindi non e' la schedulazione ma la **completezza del dataset**
- senza freshness guard dedicato, uno snapshot con pochi archetipi puo' passare inosservato per giorni pur non rompendo piu' la dashboard
- le killer curves Core non devono fidarsi solo del filtro colori: la legalita' di rotazione va trattata come vincolo separato

Vedi [`SPRINT_1_MOSSA_B.md`](SPRINT_1_MOSSA_B.md), [`SPRINT_P1.5_VENDORED.md`](SPRINT_P1.5_VENDORED.md).

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
        │                              (12 tipi: overview, playbook, decklist, loss_analysis,
        │                               winning_hands, board_state, killer_responses,
        │                               ability_cards, killer_curves, threats_llm,
        │                               card_scores, pro_mulligans)
        │
        └──→ daily_routine.md (report umano, non usato da App_tool)

run_kc_production.sh (mar) ──→ killer_curves_*.json
                                     │
                                     └──→ import_killer_curves.py (cron mar 05:30) ──→ PG killer_curves

/api/v1/dashboard-data ──→ snapshot_assembler.assemble(db) ──→ blob live da PG
  └── assembla 21 sezioni da tabelle normalizzate (1.5s primo load, cache 5 min)
  └── include available_matchups derivato da chiavi vs_*
  └── nessun blob statico, nessuna dipendenza da daily_snapshots

App_tool API → serve tutto da PG (query live <150ms)
```

## Principi di migrazione

1. `App_tool` e' l'unico boundary pubblico: frontend, API, auth, billing, cache, DB.
2. `analisidef` puo' continuare a generare output solo come bridge temporaneo.
3. Nessuna logica critica utente deve dipendere da file copiati a mano o sync manuali.
4. Ogni import da analisidef deve essere idempotente, validato, osservabile e versionabile.
5. Il target finale non e' "spostare file", ma "spostare il controllo operativo" dentro App_tool.

**`daily_routine.py` non serve più per il serving.** Resta necessario solo come fonte dei matchup reports (analyzer 12K LOC).
**`import_snapshot.py` non serve più.** L'API assembla il blob live da PG.

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
**COMPLETATA per il serving 09 Apr 2026 — materialized views non necessarie al runtime**

Le query live su `matches` sono tutte <150ms con gli indici esistenti.
`stats_service.py` calcola WR, matrix, OTP/OTD, trend direttamente.
`players_service.py` calcola top players e leaderboard da PG.
`leaderboard_service.py` fetcha da duels.ink API con cache Redis 1h.

Le materialized views `mv_meta_share` e `mv_matchup_matrix` esistono ancora e vengono refreshate da worker/script legacy, ma **non sono nel critical path del serving runtime**. Le query live bastano per il prodotto utente.

---

### Fase D: Tech tornado + card usage da PG
**COMPLETATA — già funzionante**

`tech_service.py` calcola tech tornado da PG (CARD_PLAYED JSONB + consensus).

---

### Fase E: Dashboard live assembler
**COMPLETATA 09 Apr 2026 — aggiornata stessa data**

`snapshot_assembler.py` assembla il blob dashboard (21 sezioni, ~8 MB) direttamente da PG.
`/api/v1/dashboard-data` chiama `assemble(db)` live con cache in-memory 2h + stale-while-revalidate.
Primo load ~1.5s, richieste successive ~0.3s (dalla cache). Parametro `?refresh=true` per forzare.

**Eliminato il pattern blob statico dal serving:** `import_snapshot.py` e `assemble_snapshot.py` non sono piu' necessari per servire `/api/v1/dashboard-data`.
La tabella `daily_snapshots` non e' piu' usata per il serving, ma resta per storico/benchmark e i relativi script legacy non sono ancora stati rimossi dal repo.

Frontend alleggerito: rimosso blob `_EMBEDDED_DATA` (8.8 MB → 418 KB), fetch da API.
Frontend resiliente: `getAnalyzerData()` deriva `available_matchups` dalle chiavi `vs_*` se manca.

**Hardening 20/04/2026:**
- blob esteso con `player_cards_infinity` oltre a `player_cards` core
- il frontend monitor usa i `player_cards` del formato attivo per `Best Format Players`
- `buildDeckCompare()` puo' mostrare comunque la lista stimata del player anche se manca la consensus corrente del deck

**File creati/modificati:**
- `backend/services/snapshot_assembler.py` (~350 LOC) — assembla da PG
- `backend/api/dashboard.py` — serve live da assembler (non più da daily_snapshots)
- `scripts/import_matchup_reports.py` — ora importa tutti i 12 tipi di report

**Sezioni non implementate (opzionali):**
- `best_plays` — analisi replay complessa, frontend la gestisce come opzionale
- `team` — assembler cerca match `perimeter='mygame'`, dati da popolare

---

### P1.5 — Digest vendorized bridge freeze
**COMPLETATA 15 Apr 2026 sera (commit `7d08425`)**

Il generator digest nativo non importa piu' codice runtime dal tree esterno.
I moduli legacy (~1200 LOC) sono congelati byte-perfect in `pipelines/digest/vendored/`
(loader.py, gen_archive.py, investigate.py) con header freeze che cita SHA
analisidef `58288f36a6e41b1830efab0941223e7160b84450`. Harness di parita' dedicata
in `scripts/diff_digest_vendored.py`.

**Validazione eseguita:**
1. `rg -n "analisidef" pipelines/digest` → zero match
2. parity harness su 10 matchup core → `DIFFS=0`
3. smoke `generate_digests.py --format core --limit 3` → `ok=3 err=0`

Questo chiude il coupling **C1** (code-level) del digest generator. Resta aperto
solo il coupling **D1** (data-level): `pipelines/playbook/generator.py` legge ancora
file `analisidef/output/digest_*.json`. Cutover domani (vedi Piano 16/04).

---

### P2.5 — Runtime consumers (R1/R2/R3)
**COMPLETATA 15 Apr 2026 sera**

`Liberation Day` dei runtime coupling chiuso: nessun endpoint o assembler legge
piu' file live dal tree esterno.

#### P2.5a — Replay viewer → PostgreSQL (R1) ✅

Commit `8c2b84a`. Fatto:
1. nuova tabella `replay_archives` (our_deck, opp_deck, game_format, metadata, games JSONB)
2. importer `scripts/import_replay_archives.py` eseguito sul full set storico → **271 archive importati, ~601MB JSONB in PG**
3. `backend/services/replay_archive_service.py` nuovo; `/api/replay/list` e `/api/replay/game` riscritti su PG
4. smoke test verde su localhost e via metamonitor.app

Follow-up operativo: il dataset 28/03 è stale per design (archive analisidef fermo da allora). Refresh da PG → nativo coperto in P2.5a fase 2 (generator nativo archive) se/quando serve.

#### P2.5b — KC Spy runtime → PostgreSQL (R2) ✅

Commit `8c2b84a`. Fatto:
1. nuova tabella `kc_spy_reports` (generated_at, game_format, report JSONB)
2. `scripts/import_kc_spy.py` legge il JSON legacy e upserta in PG (cron 04:05 UTC daily, subito dopo canary legacy 04:00)
3. `backend/services/kc_spy_service.py` reader; `snapshot_assembler._load_kc_spy` letto da PG
4. migration applicata live, import report corrente validato

Follow-up: se in P2 vogliamo tagliare anche il producer `kc_spy.py`, si porta il generator in App_tool; non urgente.

#### P2.5c — llm_worker cleanup (R3) ✅

Commit `9ec0f45`. `backend/workers/llm_worker.py` è stato **rimosso**: non era schedulato nel crontab, duplicato funzionale di `scripts/import_killer_curves.py`, nessun consumer esterno trovato. Dead code eliminato.

---

### Fase F: Matchup report refresh — DA FARE
**Effort: medio-alto | Rischio: medio**

I matchup reports (playbook, decklist optimizer, overview, loss_analysis) vengono dagli analyzer in analisidef (~12K LOC). Oggi importati via `import_matchup_reports.py` da `dashboard_data.json`.

**Target corretto:** gli analyzer possono anche restare quasi invariati, ma devono essere eseguiti e schedulati da `App_tool`, con input da PostgreSQL e output scritto in PostgreSQL.

**Approccio consigliato — Wrapper controllato da App_tool:**
1. Copiare i moduli di analisi in `App_tool/analysis/`:
   - `analyzer_v3.py`, `v4_helpers.py`, `deck_baselines.py`, `combo_analyzer.py`, `shared_utils.py`
2. Worker/cron in `App_tool` che legge match da PG, chiama gli analyzer, scrive in `matchup_reports`
3. Adattare `loader.py` con query PG o adapter compatibile
4. Mantenere per un periodo il doppio run (`analisidef` vs `App_tool`) con confronto automatico output
5. Spegnere l'import da `dashboard_data.json` solo dopo convergenza stabile

**Non riscrivere in SQL** — gli analyzer sono battle-tested, ~12K LOC di logica non banale.

---

### Fase G: Killer curves autonome — FUTURO
**Effort: medio | Prerequisiti: API credit OpenAI**

Oggi `run_kc_production.sh` gira in analisidef (mar 00:00, OpenAI, ~$1-2/sett).
`import_killer_curves.py` importa i risultati in PG (cron mar 05:30).

Quando si vorrà eliminare analisidef completamente:
1. Spostare `run_kc_production.sh` + `kc_spy.py` in App_tool
2. Adattare input: leggere match da PG invece che da JSON
3. Spostare cron/job OpenAI sotto worker App_tool
4. Salvare stato job, costi, errori e freshness in App_tool
5. Import finale in `killer_curves` fatto localmente dal job stesso, senza bridge esterno

**Non urgente** — l'import bridge funziona, nessuna duplicazione di costi.

**Nota di qualita' aggiunta il 20/04/2026:** anche nel bridge attuale la legalita' Core va fatta rispettare dentro App_tool. Non basta che i digest core siano costruiti da match legali; anche l'output LLM deve essere validato e filtrato contro `meta_epochs.legal_sets` prima del write su `killer_curves`.

---

### Fase H: Player scouting reports (LLM) — FUTURO
**Effort: medio | Prerequisiti: Fase G (killer curves autonome), API credit OpenAI**

Per ogni top player di un deck, generare uno **scouting report** che spieghi *come* gioca.
Input: i replay reali del player (turns JSONB con CARD_PLAYED, QUEST, CHALLENGE, CARD_SHIFTED, CARD_SUNG, abilità attivate).

**Contenuto del report:**
1. **Curva di gioco** — cosa gioca ai turni chiave (T1-T3 setup, T4-T6 pivot, T7+ chiusura)
2. **Mulligan tendencies** — carte che tiene vs carte che butta (derivabile da INITIAL_HAND + prime giocate)
3. **Uso abilità** — come e quando attiva ETB, shift, canta canzoni, trigger specifici
4. **Stile di quest/challenge** — quando questa e quando sfida, se è aggressivo o paziente
5. **Signature plays** — combo o sequenze ricorrenti che usa (es. shift T4 + canzone T5)
6. **Adattamento per matchup** — se cambia approccio contro deck diversi

**Architettura:**
1. Worker `scouting_worker.py` legge i replay del player da PG (ultimi N match con quel deck)
2. Estrae una timeline strutturata turno-per-turno (carte giocate, azioni, abilità, lore delta)
3. Passa la timeline al LLM con prompt specifico per generare il report
4. Salva in nuova tabella `player_scouting_reports` (player, deck, format, report JSONB, generated_at)
5. Frontend mostra il report nel pannello "Best Player" del monitor tab

**Cron:** stesso schedule delle killer curves (settimanale), o on-demand per i top 3-5 player per deck.

---

## Stato riepilogativo (storico fasi A-H)

| Fase | Stato | Dipende da analisidef? |
|------|-------|----------------------|
| A (import matches) | **FATTO** | Solo `/matches/` (lorcana_monitor, infra non spostabile) |
| B-C (stats/leaderboard da PG) | **FATTO** | No |
| D (tech tornado da PG) | **FATTO** | No |
| E (dashboard live assembler) | **FATTO** | No |
| Sprint-0 legality gate (15/04) | **FATTO** | No |
| Sprint-1 Mossa A+B playbook (15/04) | **FATTO** | No (generator nativo OpenAI) |
| F (matchup reports/analyzer 12K LOC) | DA FARE | Sì — target **P3** |
| G (killer curves autonome) | FUTURO | Sì — target **P2** |
| H (scouting LLM) | FUTURO | No |

La tassonomia corrente è **P0-P5** (vedi sezione piano revisionato sotto) che rimpiazza le lettere F/G per gli sprint recenti.

## Exit criteria

La migrazione e' davvero conclusa solo quando:

- `App_tool` serve tutti gli utenti senza leggere output applicativi da analisidef
- replay viewer e KC Spy non leggono piu' file JSON live da analisidef
- i job schedulati vivono in `App_tool` e sono monitorati li'
- il frontend di produzione vive in `App_tool` senza sync manuali
- PostgreSQL e Redis sono l'unica base runtime dell'app
- analisidef puo' essere spento senza impattare utenti o aggiornamenti dati

---

## Cosa NON migrare

- **`lorcana_monitor.py`** — daemon che intercetta partite live da duels.ink. Infrastruttura di collection, resta dov'è.
- **`pipeline/`** — snapshot di analisidef, non in produzione. Ignorare.
- **Report .md umani** — lasciarli in analisidef. App_tool serve solo API JSON.

---

## 🔍 Discovery 15/04/2026 pomeriggio — revisione Fase F/G

Dopo aver completato Sprint-1 Mossa B (Blind Playbook nativo), indagine su come portare KC ha rivelato due problemi architetturali che **cambiano l'approccio alle Fasi F e G**.

### Finding #1 — Digest upstream trap

`pipelines/playbook/generator.py:63,150` (codice appena deployato ieri notte) **legge `analisidef/output/digest_*.json`**. Significa che il Blind Playbook nativo è ancora accoppiato ad analisidef a livello dati. Spegnere il cron analisidef = congelare silenziosamente le narrative del playbook (utente paga, vede contenuto stale, non riceve errori).

Porting "KC only" era un **time bomb**: l'ordine corretto è digest prima, KC dopo.

### Finding #2 — Archive pipeline rotta dal 28/03 (bug silenzioso)

`analisidef/output/archive_*.json` (265 file, 25MB ciascuno) **non sono più rigenerati dal 28/03**. Investigazione:
- Pre-28/03: cron `run_all_killer_curves.sh` (Mar+Gio) chiamava `generate_report.py` → rigenerava archive + digest
- 28/03: cron sostituito con `run_kc_production.sh` (Mar 00:00) che **rigenera solo digest**, mai archive
- Digest legge archive (stale) → narrative basate su dati di 18+ giorni fa
- PG `matches` / `matchup_reports` invece sono **fresche** (cron ogni 2h funziona)

**Impatto utente**: sezione "Killer Curves" e "Blind Playbook" in Coach V2 raccontano il meta del 28/03.

### Finding #3 — Architettura ripensata: digest da PG, non da archive

Il design corrente è:
```
matches (PG fresh) → archive_*.json (25MB, STALE 28/03) → digest_*.json (30KB) → LLM
                         ^^^^^^^^^^^^^^^^ intermediate inutile
```

Il design target in App_tool:
```
matches (PG fresh, window ultimi N giorni) → digest ON-DEMAND da query PG → LLM
```

Gli archive JSON sono un **intermediate legacy** che sostituisce una query PG. In App_tool non vanno portati: la nuova `gen_digest()` legge direttamente da PG (coerente con principio "PG = source of truth").

**Benefici:**
- Impossibile per costruzione produrre digest stale (sempre riflette gli ultimi N giorni)
- Zero file system da mantenere (−6.6GB di archive)
- Pipeline 2 step invece di 3
- Narrative adattive al meta corrente

---

## 🆕 Piano revisionato (P0–P5) — 15/04/2026, rivisto post-Codex review

Sostituisce e dettaglia Fase F-G. Dual-run e shadow mode obbligatori per ogni cutover (app a pagamento, zero discontinuità).

**Tabella riepilogo fasi (stato fine giornata 15/04/2026):**

| Sprint | Scope | Effort | Stato |
|---|---|---|---|
| **P0** | Monitoring + baseline | basso | ✅ FATTO (commit `ab03c6e`, mail monitor 07:00, baseline tarball) |
| **P1** | Digest nativo PG + meta_epochs (shadow) | medio-alto | ✅ FATTO (commit `ace88dc`, shadow attivo) |
| **P1.5** | Vendorized freeze 1200 LOC analytics + golden diff | medio | ✅ FATTO (commit `7d08425`, DIFFS=0 su 10 matchup) |
| **P2.5a** | Replay endpoint → PG (user-facing) | medio-alto | ✅ FATTO (commit `8c2b84a`, 271 archive in PG) |
| **P2.5b** | KC spy reader → PG | basso-medio | ✅ FATTO (commit `8c2b84a`, cron 04:05 attivo) |
| **P2.5c** | llm_worker cleanup | basso | ✅ FATTO (commit `9ec0f45`, file rimosso) |
| **P2** | KC pipeline nativa (D2) | medio | ✅ FATTO (16/04 — vendorized + runner nativo, E2E verde) |
| **P3** | Matchup reports nativi (D3) | alto | ✅ FATTO (16/04 — generator nativo da digest + turns PG, 7 report types) |
| **P4** | Decommission analisidef | basso | DA FARE (dopo P2+P3 stabili ≥4 settimane) |
| **P5** | lorcana_monitor failover (opzionale, robustezza) | alto | FUTURO |

**Cutover intermedio 16/04/2026:** D1 (playbook → digest nativo). Vedi sezione "Piano domani" sotto. Non è un nuovo sprint, è il completamento operativo di P1.

### P0 — Monitoring + baseline ✅ FATTO 15/04/2026

- Baseline golden: `backups/golden/kc_baseline_20260415_125044Z.tar.gz` (533 file: 264 digest + 269 KC)
- Monitor: `scripts/monitor_kc_freshness.py` (dual signal: `fresh_7d>=100` AND `newest>=today-10`)
- Cron 07:00 giornaliero → mail `monitorteamfe@gmail.com` solo su STALE/ERROR (no news = good news)
- SMTP via Python smtplib + `/tmp/.smtp_pass` (Gmail app password)

### P1 — Port digest pipeline (nativo PG-first) — PROSSIMO

**Obiettivo**: `scripts/generate_digests.py` produce digest JSON dagli **ultimi N giorni di `PG matches`** invece che da archive files. Sostituisce `analisidef/lib/gen_digest.py` + elimina `gen_archive.py` del tutto.

#### Parametri scelti (15/04/2026)

- **Window**: 30 giorni (meta adattivo)
- **Min games per matchup**: 20 (skippa se sotto)
- **Pre-window games**: ignorati del tutto (zero ambiguità)
- **90-day constraint**: `turns` JSONB retention. Campi che richiedono turns (example_games, avg_trend, lore_t4, patterns, keywords/abilities) per costruzione limitati a ≤90gg. Con window=30gg, sempre coperti.

#### Meta-stability (design obbligatorio per P1)

Il meta Lorcana cambia a ondate: nuovo set ogni ~3 mesi, rotazioni periodiche. Una window fissa 30gg è sbagliata in questi momenti. P1 deve includere:

**A — Set-legality filter (obbligatorio)**: il generator query-filtra escludendo match con carte da set non-legali per il formato target. Riuso di `LEGAL_SETS` dal legality gate Sprint-0.

**B — Meta epoch config (obbligatorio)**: nuova tabella `meta_epochs`:
```sql
CREATE TABLE meta_epochs (
  id            SERIAL PRIMARY KEY,
  name          TEXT NOT NULL,           -- "Pre-Set12", "Set12 launch", ...
  started_at    DATE NOT NULL,
  ended_at      DATE,                    -- NULL = current epoch
  legal_sets    INTEGER[] NOT NULL,
  notes         TEXT,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);
```

Generator filtra `played_at >= current_epoch.started_at`. **Window efficace** = `min(30, days_since_epoch_start)` — si auto-riduce a 7-14gg nelle prime settimane post-launch, cresce fino a 30gg dopo 30gg di stabilità. Zero intervento manuale al giorno X+N.

**Fonte date ufficiali**: Ravensburger (publisher Disney Lorcana). Set release + rotation date sono pubblicati sul sito ufficiale. L'operatore inserisce nuova riga `meta_epochs` al release; non serve scraping automatico se il ritmo è ~3 mesi.

**C — Meta-stability hint nel digest output (nice-to-have, aggiungere in P1.2)**: campo `meta_stability: "STABLE" | "TRANSITIONING" | "NEW_EPOCH"` calcolato:
- `NEW_EPOCH` se `days_since_epoch_start < 14`
- `TRANSITIONING` se winrate variance ultime 7gg diverge >15pp dalla window
- `STABLE` altrimenti

L'LLM lo vede nel prompt e può mitigare: "*the meta is in transition — these patterns may shift*".

**D — Monitoring epoch change (nice-to-have)**: quando viene inserita nuova riga `meta_epochs`, trigger alert via mail "new epoch started, expect narrative warmup period". Evita confusione "perché il monitor dice fresh_7d basso questa settimana?" → risposta: "perché hai appena creato un epoch, la window effettiva è 7gg, non 30".

#### Sub-step P1

1. Mappare schema digest (`digest_*.json` campo per campo) → query PG equivalenti (aggregati, example games, card DB). **FATTO 15/04/2026** — spec completa in memoria interna.
2. Migration `meta_epochs` + seed `Pre-Set12` + `Set11 settled` (current) in dev
3. Scrivere `App_tool/pipelines/digest/generator.py` (legge PG + cards_db, produce stesso JSON schema, applica set-legality + epoch filter)
4. Scrivere `App_tool/scripts/generate_digests.py` (batch, per tutti i matchup rilevanti)
5. **Shadow run 2 settimane**: entrambe le pipeline scrivono digest in path separati
   - Legacy: `analisidef/output/digest_*.json`
   - Nativa: `App_tool/output/digests/digest_*.json`
6. Diff script struttura + numeric (ignora differences attese: window, epoch filter)
7. **Cutover**: flip `pipelines/playbook/generator.py:150` a leggere da `App_tool/output/digests/`

**Rollback**: flag config `DIGEST_SOURCE = "legacy" | "native"` in `backend/config.py`, toggle atomico.

**Effort**: medio-alto. Scope ~1.5–2K LOC nuovo + 1 migration Alembic + 1 tabella.

### P1.5 — Vendorized bridge freeze ✅ FATTO (commit `7d08425`)

Dettagli operativi nella sezione "P1.5 — Digest vendorized bridge freeze" sopra. Razionale storico: P1 ha moved la dipendenza da livello-dati a livello-codice; il generator nativo importava `analisidef.lib.{loader, gen_archive._build_aggregates, investigate.{classify_losses, enrich_games}}` a runtime (~1200 LOC).

Esecuzione completata in un unico commit `7d08425`: vendorize byte-perfect dei 3 moduli in `pipelines/digest/vendored/`, fix import paths interni, harness `scripts/diff_digest_vendored.py`, switch di `generator.py` alle import `vendored.*`, rimozione di `sys.path.insert(_ANALISIDEF_ROOT)`. Exit criterion `grep -rn analisidef pipelines/digest/` → zero match: rispettato. Validazione: `DIFFS=0` su 10 matchup, smoke `generate_digests.py --limit 3` verde.

---

### P2 — Port KC pipeline (dual-run su PG) — DA FARE

**Obiettivo**: `scripts/generate_killer_curves.py` legge digest nativi + chiama OpenAI + upserta direttamente in PG `killer_curves` (saltando il passaggio file JSON).

**Sub-step:**
1. Port `run_kc_production.py` + `test_kc/src/build_prompt.py` → `App_tool/pipelines/kc/`
2. Runner scrive PG con `version=2, is_current=false` (non impatta utenti)
3. Legacy cron continua con `version=1, is_current=true`
4. **Dual-run 2-3 settimane**: diff qualità narrative + schema, revisione manuale 3-5 matchup/settimana
5. **Cutover atomico**: flip `is_current` → `version=2`, disabilita cron legacy + `import_killer_curves.py` nello stesso commit
6. Lascia commented-out 1 mese per rollback rapido

**Effort**: medio. Scope ~2–2.5K LOC.

---

### P2.5 — Runtime consumers ✅ FATTO (commit `8c2b84a`, `9ec0f45`)

Dettagli operativi nella sezione "P2.5 — Runtime consumers" sopra (R1/R2/R3 tutti chiusi, 271 replay_archives in PG, `kc_spy_reports` + cron 04:05 attivo, `llm_worker.py` rimosso).

---

### P3 — Port matchup reports / daily_routine — DA FARE

Corrisponde alla vecchia **Fase F**. Dual-run dell'analyzer v3 (12K LOC) su PG invece che su JSON estratti.

**Refinement post-review Codex**: **non wrappare `daily_routine.py` come monolite**. Wrappare gli analyzer come **libreria con adapter PG**:
- Copia `analyzer_v3.py`, `v4_helpers.py`, `combo_analyzer.py`, `deck_baselines.py`, `shared_utils.py` in `App_tool/pipelines/matchup_reports/vendored/` (pattern P1.5)
- Adapter nuovo in `App_tool/pipelines/matchup_reports/adapter.py` che fornisce l'interfaccia esistente degli analyzer ma legge da PG, scrive a PG
- Il monolite `daily_routine.py` **non viene portato** — solo i suoi analyzer
- Side effects, path hardcoded, assunzioni file-based = lasciati morire con analisidef

**Nota**: questa è la più grossa (12K LOC battle-tested). Non riscrivere in SQL, porting con adapter.

### P4 — Decommission analisidef — DOPO P3

- 4 settimane di native-only stabile (P1+P2+P3)
- Archivio analisidef in read-only tag git
- Rimuovi `ANALISIDEF_OUTPUT_DIR` + `ANALISIDEF_DAILY_DIR` da `backend/config.py`
- Elimina cron legacy
- Elimina `App_tool/scripts/import_killer_curves.py`, `import_matchup_reports.py`

### P5 — `lorcana_monitor.py` failover — FUTURO (opzionale)

Single-node senza failover. Non blocca indipendenza, è un miglioramento di robustezza a parte.

---

## Stato coupling App_tool → analisidef (15/04/2026 sera — Liberation Day runtime)

### Livello RUNTIME (servono richieste utente) — CHIUSI

| # | File App_tool | Stato | Come chiuso |
|---|---|---|---|
| R1 | `backend/main.py` + `backend/services/replay_archive_service.py` | ✅ CHIUSO | `/api/replay/*` leggono da PG `replay_archives` (271 archive, 601MB JSONB) |
| R2 | `backend/services/snapshot_assembler.py` + `kc_spy_service.py` | ✅ CHIUSO | KC Spy letto da PG `kc_spy_reports`, cron 04:05 |
| R3 | `backend/workers/llm_worker.py` | ✅ RIMOSSO | Dead code, file cancellato (commit `9ec0f45`) |

### Livello CODICE (import Python runtime) — CHIUSO

| # | File App_tool | Stato | Come chiuso |
|---|---|---|---|
| C1 | `pipelines/digest/generator.py` | ✅ CHIUSO | Vendorized in `pipelines/digest/vendored/` (~1200 LOC), DIFFS=0 su 10 matchup |

### Livello DATA (file reads batch — importer cron)

| # | File App_tool | Dipendenza | Stato |
|---|---|---|---|
| D1 | `pipelines/playbook/generator.py` | ~~legge `analisidef/output/digest_*.json`~~ | ✅ CHIUSO 16/04 — `DIGEST_SOURCE=native` default, legge `App_tool/output/digests/` |
| D2 | `scripts/generate_killer_curves.py` | ~~legge `analisidef/output/killer_curves_*.json`~~ | ✅ CHIUSO 16/04 — pipeline nativa: digest PG → OpenAI → PG `killer_curves` |
| D3 | `scripts/generate_matchup_reports.py` | ~~legge `dashboard_data.json`~~ | ✅ CHIUSO 16/04 — 7 report types nativi da digest PG + turns JSONB |

### Legacy script da rimuovere in P4 (non attivi runtime, ma coupling residuo)

- `scripts/import_archives.py`
- `scripts/import_snapshot.py`
- `scripts/import_playbooks.py` (post Mossa B il generator nativo rende questo bridge obsoleto)
- `scripts/sync_dashboard.sh`

## Rischi noti non-indipendenza

- `lorcana_monitor.py` single-node: se cade, tutto a monte si ferma. Non coperto da P1–P4.
- Stale archive 28/03 esiste, impatta il **replay endpoint** che ora serve archive stale da PG (dati importati 15/04 ma contenuto 28/03). Refresh da PG → nativo in follow-up di P2.5a.
- Fallback credenziali `/tmp/.openai_key` in `pipelines/playbook/generator.py:1205` = coupling operativo fragile (non analisidef, ma reboot VPS = perdita chiave).

## Rischi operativi emersi da review (16/04/2026)

Questi punti **non bloccano D1**, ma sono debito operativo reale e vanno schedulati in parallelo.

- `backend/services/leaderboard_service.py` contiene un default reale per `DUELS_SESSION`: **secret hardcoded nel repo**. Va spostato in env-only con failure esplicita o degrado controllato.
- `backend/middleware/rate_limit.py` legge `request.state.user_tier`, ma oggi nessun middleware/dependency lo valorizza: il rate limit "per-tier" e' di fatto **sempre free-tier**.
- `backend/main.py` ha CORS permissivo (`allow_origins=["*"]`) insieme a `allow_credentials=True`: configurazione troppo larga e non pulita per produzione.
- Documentazione e repo hanno ancora **drift** su `assemble_snapshot.py`, materialized views e `daily_snapshots`: prima del decommission finale bisogna riallineare i documenti allo stato reale.
- Il repo contiene ancora doppie superfici (`pipeline/` snapshot legacy vs `pipelines/` runtime nuovo, bridge storici, script non piu' usati) che aumentano il costo cognitivo e il rischio di confusione operativa.

## Exit criteria riformulati

**Liberation Day** non è "P4 completato", è la capacità di rispondere **SÌ** alla domanda:

> *"Posso spegnere analisidef adesso senza perdere replay, KC spy, playbook, digest, matchup reports, o nessuna feature utente-facing?"*

Checklist fine giornata 15/04/2026:
- [x] R1 Replay endpoint da PG
- [x] R2 KC spy da PG
- [x] R3 llm_worker rimosso
- [x] C1 Digest generator senza import da analisidef
- [x] D1 Playbook generator senza `analisidef/output/digest_*.json` → **CHIUSO 16/04** (`DIGEST_SOURCE=native`)
- [x] D2 KC pipeline nativa → **CHIUSO 16/04** (E2E: digest PG → OpenAI → PG, $0.034/matchup)
- [x] D3 Matchup reports nativi → **CHIUSO 16/04** (132 matchup, 924 reports, 0 errors)

**Risposta alla domanda Liberation Day 16/04: AVANZATA**.
- Runtime (richieste utente): ✅ SÌ — nessun endpoint o assembler rompe se analisidef è down
- Playbook batch: ✅ SÌ — digest nativi da PG, zero dipendenza analisidef
- KC batch: ✅ SÌ — `generate_killer_curves.py` nativo (digest PG → OpenAI → PG)
- Matchup reports batch: ✅ SÌ — `generate_matchup_reports.py` nativo (digest PG + turns JSONB)

**Traguardo Liberation Day completo = tutte le caselle verdi**, sbloccato dopo D1/D2/D3.

---

## 📋 Bilancio giornata 15/04/2026

### Fatto oggi (commit `ab03c6e` → `9ec0f45`)

1. **Sprint-0** ✅ Legality gate nativo App_tool (mattina)
2. **Sprint-1 Mossa A** ✅ Import bridge Blind Playbook (mattina)
3. **Sprint-1 Mossa B** ✅ Generator nativo Blind Playbook + cron settimanale Tue 01:00 (notte)
4. **Discovery** digest dependency trap + archive stale 28/03 (pomeriggio)
5. **P0** ✅ Monitor freshness + baseline + mail alert `monitorteamfe@gmail.com` + cron 07:00 (commit `ab03c6e`)
6. **P1** ✅ Digest nativo PG-first + `meta_epochs` migration (2 seed row) + shadow mode (commit `ace88dc`)
7. **P1.5** ✅ Vendorize byte-perfect 1200 LOC (loader/gen_archive/investigate) + harness + switch import + `DIFFS=0` su 10 matchup + smoke ok (commit `7d08425`, merge `64397d2`)
8. **P2.5a** ✅ R1 replay: tabella `replay_archives` + importer full 271 archive (~601MB JSONB) + endpoint `/api/replay/*` letti da PG via `replay_archive_service.py` (commit `8c2b84a`)
9. **P2.5b** ✅ R2 kc_spy: tabella `kc_spy_reports` + `import_kc_spy.py` + cron 04:05 daily + `kc_spy_service.py` in snapshot_assembler (commit `8c2b84a`)
10. **P2.5c** ✅ R3 llm_worker: file `backend/workers/llm_worker.py` rimosso come dead code non schedulato (commit `9ec0f45`)
11. **Docs** ✅ MIGRATION_PLAN + ARCHITECTURE aggiornati (commit `1ea4ccf`)

### Stato repository fine giornata

- Branch `dev` a HEAD `9ec0f45` con tutti i commit P0-P2.5c + docs mergiati
- Branch `sprint-p1-digest`, `sprint-p1-5-vendored`, `worktree-agent-a46465f8` storici (mergiati)
- Tabelle PG create e popolate: `meta_epochs` (2 righe), `replay_archives` (271 righe, 601MB JSONB), `kc_spy_reports` (1 riga)
- Cron App_tool: import_matches */2h, healthcheck 5min, backup 03:00, maintenance Dom 02:00, **import_kc_spy daily 04:05 (nuovo)**, static_importer Dom 04:45, import_matchup_reports daily 05:30, import_killer_curves Mar 05:30, assemble_snapshot daily 05:35, monitor_kc_freshness daily 07:00, generate_playbooks Mar 01:00
- Cron analisidef ancora attivi (fino a cutover P2/P3): lorcana_monitor 05:00, daily_routine 05:01, run_kc_production Mar 00:00, kc_spy 04:00, decks_db_builder 04:30
- Produzione live: uvicorn `127.0.0.1:8100`, smoke test verde su replay + dashboard (localhost + metamonitor.app)

### Liberation Day status fine giornata

- Runtime coupling (R1/R2/R3) + code-level coupling (C1): **TUTTI CHIUSI** ✅
- Data-level coupling (D1/D2/D3): 3 su 3 ancora aperti, target 16/04 (D1), P2 (D2), P3 (D3)
- Prossimo gate: D1 cutover playbook → digest nativo (vedi piano sotto)

---

## 📅 Piano domani 16/04/2026 — D1 cutover (playbook → digest nativo)

**Target singolo della giornata**: chiudere coupling data-level **D1**. `pipelines/playbook/generator.py` deve smettere di leggere `analisidef/output/digest_*.json` e passare a `App_tool/output/digests/*.json` (prodotti da P1 nativo, shadow attivo dal 15/04).

### Step

1. **Shadow run mattina** — eseguire in parallelo il generator playbook con:
   - `DIGEST_SOURCE=legacy` → legge `analisidef/output/digest_*.json`
   - `DIGEST_SOURCE=native` → legge `App_tool/output/digests/*.json`
   Confronto output narrative per **5-10 matchup core** (Amber/Steel vs top meta).
2. **Review manuale**: se le narrative sono semanticamente equivalenti e non si osservano regressioni evidenti (hallucination, dati stale, formattazione rotta), aggiungere flag `DIGEST_SOURCE` in `backend/config.py` con default `"legacy"`.
3. **Flip a native** in un commit separato dopo review manuale. Default `"native"` in config, `"legacy"` sbloccato via env var come fallback.
4. **Osservazione 3-7 giorni**: monitor freshness daily + check manuale playbook output su spot matchup. Se stabile, pianificare lo spegnimento del cron analisidef relativo (oppure lasciarlo come fallback silenzioso).

### Exit criteria D1

- `grep -rn "analisidef/output/digest" pipelines/playbook/` → zero match
- Flag `DIGEST_SOURCE` in config default `"native"`, valore `"legacy"` ancora supportato come rollback
- Nessuna regressione visibile sul Blind Playbook utente-facing per 72h

### Effort

1-2h di lavoro effettivo (shadow run + diff + flag + flip), il resto è osservazione.

### Pending minori da smaltire in coda

- Commit degli untracked residui (`backups/`, `scripts/kc_baseline.sh`, `scripts/monitor_kc_freshness.py`) su `dev`
- Aggiornare `docs/MIGRATION_PLAN.md` con esito D1 a fine giornata

### Lavori paralleli che non bloccano D1

Questi item possono essere presi da un secondo agente o in parallelo senza toccare il path critico playbook→digest:

1. **P0.5 docs truth pass**
   - Allineare `MIGRATION_PLAN.md`, `ARCHITECTURE.md`, `CLAUDE.md` allo stato reale del repo
   - Correggere: cache dashboard 2h, ruolo residuale di `daily_snapshots`, materialized views legacy, `assemble_snapshot.py` non piu' serving-critical

2. **P0.6 security/config cleanup**
   - Rimuovere default hardcoded `DUELS_SESSION` da `leaderboard_service.py`
   - Rendere esplicito il bootstrap segreti (`OPENAI_API_KEY`, leaderboard session) via env
   - Stringere CORS in prod tramite config

3. **P0.7 rate-limit correctness**
   - Introdurre un middleware leggero che popola `request.state.user_tier` da JWT quando presente
   - Oppure rinominare il comportamento corrente come per-IP only finche' il tier-aware non e' implementato davvero

4. **P0.8 legacy surface audit**
   - Catalogare cosa in `pipeline/`, `scripts/import_snapshot.py`, `scripts/assemble_snapshot.py`, `scripts/import_playbooks.py` e' davvero morto
   - Marcare esplicitamente i file come legacy/unused o prepararne la rimozione in P4

### Prossimo ciclo verifica automatica

- Martedì 21/04 00:00: batch analisidef legacy KC (come sempre, finché P2 non è chiuso)
- Martedì 21/04 01:00: playbook nativo App_tool (dopo flip D1, legge digest nativo)
- Mercoledì 22/04 07:00: monitor freshness — se manda STALE, investigare prima di procedere a P2

---

## 📋 Bilancio giornata 16/04/2026

### Fatto oggi (sessione 1: Liberation Day)

1. **D1 cutover CHIUSO** ✅ — `pipelines/playbook/generator.py` ora legge da `App_tool/output/digests/` (digest nativi PG-first). Flag `DIGEST_SOURCE` in `backend/config.py` (default `"native"`, rollback via `DIGEST_SOURCE=legacy` env var).
2. **Full batch digest nativi** — generati tutti i digest core+infinity da PG (200K+ match, window 30gg). Dati 5x più freschi dei legacy stale dal 28/03.
3. **Code review completa** — 3 agenti paralleli (backend, pipelines/scripts, frontend). Findings consolidati:
   - CRITICAL: SQL injection fix in admin.py (applicato), password reset token log rimosso (applicato)
   - HIGH: CORS già fixato con env var, team API senza JWT (noto, target post-login), `pipeline/` legacy da archiviare
   - MEDIUM: shell scripts senza `set -e`, logging `print()` → `logging` module, worktree cleanup, frontend dead API wrappers, `team_coaching.js` 1444 LOC monolitico
4. **D2 cutover CHIUSO** ✅ — KC pipeline nativa: `pipelines/kc/` (build_prompt, stability, postfix, cards_api vendorized) + `scripts/generate_killer_curves.py`. E2E test: AmSa vs AbE → 5 curves, $0.034, upserted in PG. Prompt in English. Zero analisidef dependency.
5. **Security fixes applicati**: admin.py SQL hardened, auth.py token log rimosso

### D1 exit criteria verification

- `_get_digest_source()` default → `"native"` ✅
- `load_deck_digests('AmAm', 'core')` con native → 11 digest, 20111 games ✅
- `generate_playbook('AmAm', use_llm=False)` E2E → output completo con tutte le chiavi ✅
- Rollback `DIGEST_SOURCE=legacy` testato e funzionante ✅
- `DASHBOARD_DATA` (analisidef) ancora usato da `load_pro_references` → coupling D3, non D1 ✅

### Liberation Day status 16/04/2026

| Coupling | Stato |
|----------|-------|
| R1 Replay endpoint | ✅ CHIUSO |
| R2 KC Spy runtime | ✅ CHIUSO |
| R3 llm_worker | ✅ RIMOSSO |
| C1 Digest generator code | ✅ CHIUSO |
| **D1 Playbook → digest** | ✅ **CHIUSO** (oggi) |
| **D2 KC pipeline** | ✅ **CHIUSO** (oggi) |
| **D3 Matchup reports** | ✅ **CHIUSO** (oggi) |

**Score: 7/7 coupling chiusi. LIBERATION DAY COMPLETO.** Restano D2 (KC import bridge) e D3 (matchup reports bridge).

### Fatto oggi (sessione 2: Meta Ticker + UI polish)

1. **Meta Ticker** ✅ — news feed scrolling Bloomberg-style in Monitor tab (tabella PG `news_feed`, YouTube RSS 13 canali + Twitch ready, cron 3h, frontend CSS+JS)
2. **Format toggle in tab bar** ✅ — Core/Infinity spostato a dx nella tab bar desktop, format-bar solo mobile
3. **Copy decklist pulito** ✅ — rimossi `*` e `?` dal copy (Monitor Best Players), rimosso CSS `::after *` (Lab Optimized Deck)
4. **Copy buttons mobile** ✅ — layout responsive con bottoni full-width su mobile
5. **Standard List senza scroll** ✅ — rimosso max-height/overflow, blocco unico
6. **Rimosso toggle Core/Infinity duplicato** da Profile header

### Debito tecnico emerso da review (backlog)

| Item | Effort | Sprint suggerito |
|------|--------|-----------------|
| Archiviare `pipeline/` (36 file legacy) | 30 min | P0.8 |
| `set -e` + trap in shell scripts | 1h | P0.6 |
| Python `logging` module in scripts | 2h | P0.6 |
| Cleanup worktree artifacts | 10 min | Immediato |
| Frontend: rimuovere 5 API wrapper dead | 15 min | Prossimo frontend sprint |
| Frontend: sanitize innerHTML in team_coaching.js | 1h | Prossimo frontend sprint |

---

## Nuove feature infra aggiunte 16/04/2026

### Meta Ticker (news feed scrolling)

Componente Bloomberg-style in cima al Monitor tab. Due stream:
- **META** (gold) — auto-generato client-side dal blob dashboard (fitness, meta share, WR swings)
- **Editorial** (VIDEO/NEWS/BUZZ/LIVE) — da tabella PG `news_feed`, alimentata da cron ogni 3h

**Stack:**
- Tabella `news_feed` (migration `f1a2b3c4d5e6`)
- Service `backend/services/news_feed_service.py` — CRUD + upsert dedup + cleanup expired
- API `backend/api/news.py` — GET `/ticker` (pub, cache 5min), POST (admin), DELETE (admin)
- Cron `scripts/fetch_news_feed.py` — YouTube RSS (13 canali, filtro keyword multi-TCG) + Twitch Helix (pronto, attende credenziali) + Reddit (bloccato da IP datacenter)
- Frontend: CSS ticker + JS `buildMetaTickerItems()` + `fetchEditorialItems()` + `renderMetaTicker()`

**Canali YouTube tracciati:** Lorcana Academy, Lorcana Goons, The Forbidden Mountain, The Illumiteers, DMArmada, Team Covenant, Ready Set Draw TCG, The Inkwell, phonetiic, Mushu Report, Inkborn Heroes, Tales of Lorcana (it), Inked Broom (it)

**Twitch:** Lorecast (disneylorcana) — LIVE pulse + VOD. Setup: `echo 'CLIENT_ID:SECRET' > /tmp/.twitch_creds`

**Crontab:** `0 */3 * * * cd .../App_tool && venv/bin/python scripts/fetch_news_feed.py`
