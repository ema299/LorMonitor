# Piano migrazione: analisi completa dentro App_tool

**Obiettivo prodotto:** `App_tool` e' l'unica app pubblica che serve gli utenti.
`analisidef` e' un motore transitorio di calcolo/import, non il prodotto.

**Stato attuale (15 Apr 2026 — Liberation Day):** API 100% da PostgreSQL.
Dashboard blob assemblato **live** da PG (snapshot_assembler.py, cache 2h).
Match importati ogni 2h **con legality gate per core** (Sprint-0 oggi).
Matchup reports e killer curves ancora importati da analisidef via cron (Fase F/G).
**Blind Deck Playbook** importato in PG con narrative completa (24/24 deck) — Sprint-1 Mossa A
oggi. **Mossa B** (porting nativo OpenAI in App_tool) pianificata, vedi
[`SPRINT_1_MOSSA_B.md`](SPRINT_1_MOSSA_B.md).

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

### Fase E: Dashboard live assembler
**COMPLETATA 09 Apr 2026 — aggiornata stessa data**

`snapshot_assembler.py` assembla il blob dashboard (21 sezioni, ~8 MB) direttamente da PG.
`/api/v1/dashboard-data` chiama `assemble(db)` live con cache in-memory 5 min.
Primo load ~1.5s, richieste successive ~0.3s (dalla cache). Parametro `?refresh=true` per forzare.

**Eliminato il pattern blob statico:** non serve più `import_snapshot.py` né `assemble_snapshot.py` via cron.
La tabella `daily_snapshots` non è più usata per il serving (resta per storico se necessario).

Frontend alleggerito: rimosso blob `_EMBEDDED_DATA` (8.8 MB → 418 KB), fetch da API.
Frontend resiliente: `getAnalyzerData()` deriva `available_matchups` dalle chiavi `vs_*` se manca.

**File creati/modificati:**
- `backend/services/snapshot_assembler.py` (~350 LOC) — assembla da PG
- `backend/api/dashboard.py` — serve live da assembler (non più da daily_snapshots)
- `scripts/import_matchup_reports.py` — ora importa tutti i 12 tipi di report

**Sezioni non implementate (opzionali):**
- `best_plays` — analisi replay complessa, frontend la gestisce come opzionale
- `team` — assembler cerca match `perimeter='mygame'`, dati da popolare

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

## Stato riepilogativo

| Fase | Stato | Dipende da analisidef? |
|------|-------|----------------------|
| 0-6 | **FATTO** | No (runtime) |
| A | **FATTO** | Solo `/matches/` (lorcana_monitor) |
| B-C | **FATTO** | No |
| D | **FATTO** | No |
| E | **FATTO** | No |
| **Sprint-0 (15/04)** | **FATTO** | No — legality gate nativo App_tool |
| **Sprint-1 Mossa A (15/04)** | **FATTO** | Sì — bridge importer per Blind Playbook |
| **Sprint-1 Mossa B (15/04)** | **FATTO** | No (generator nativo + prompt EN, batch in PG via OpenAI key App_tool) |
| F | DA FARE | Sì (analyzer 12K LOC → matchup reports) |
| G | FUTURO | Sì (OpenAI killer curves) |
| H | FUTURO | No (replay da PG + OpenAI) |

**Dopo Fase F:** `daily_routine.py` eliminabile. Solo `lorcana_monitor.py` resta.
**Dopo Fase G:** analisidef eliminabile completamente.
**Fase H:** indipendente da analisidef, richiede solo replay in PG + API OpenAI.

## Exit criteria

La migrazione e' davvero conclusa solo quando:

- `App_tool` serve tutti gli utenti senza leggere output applicativi da analisidef
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

Sostituisce e dettaglia Fase F-G. Dual-run e shadow mode obbligatori per ogni cutover (la app è a pagamento, zero discontinuità).

**Tabella riepilogo fasi (post-Codex)**:

| Sprint | Scope | Effort | Stato 15/04 sera |
|---|---|---|---|
| **P0** | Monitoring + baseline | — | ✅ FATTO (mail monitor 07:00, baseline tarball) |
| **P1** | Digest nativo PG + meta_epochs (shadow) | medio-alto | ✅ FATTO (branch `sprint-p1-digest`, non mergiato) |
| **P1.5** | Vendorized freeze 1200 LOC analytics + golden diff | medio | ⏳ IN CORSO — step 1/7 fatto da Codex (vendorize byte-perfect), step 2-7 domani |
| **P2** | KC pipeline nativa + kc_spy | medio | DA FARE |
| **P2.5a** | Replay endpoint → PG (user-facing) | medio-alto | DA FARE |
| **P2.5b** | KC spy reader → PG | basso-medio | DA FARE |
| **P2.5c** | llm_worker cleanup | basso | DA FARE (verdetto: dead code, cancellabile, no cron/import) |
| **P3** | Matchup reports / analyzer_v3 (12K LOC, vendored + adapter) | alto | DA FARE |
| **P4** | Decommission analisidef | basso | DA FARE |
| **P5** | lorcana_monitor failover (opzionale, robustezza) | alto | FUTURO |

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

### P1.5 — Vendorized bridge freeze (nuovo, critico) — IN CORSO (step 1/7 fatto, 2-7 da fare)

**Scoperta nel review Codex 15/04/2026 sera**: P1 ha moved la dipendenza da livello-dati a livello-codice ma non l'ha eliminata. Il generator nativo importa `analisidef.lib.{loader, gen_archive._build_aggregates, investigate.{classify_losses, enrich_games}}` a runtime (~1200 LOC).

**Rischio se trattato come "pulizia dopo"**: silent divergence tra parsing legacy e PG-native, trascinamento dipendenza per mesi perché "tanto funziona".

**Approccio corretto — NON riscrivere, VENDORIZZARE**:
1. Copia esatta dei 3 moduli analisidef in `App_tool/pipelines/digest/vendored/`:
   - `loader.py`, `gen_archive.py` (solo `_build_aggregates` + suoi helper), `investigate.py`
2. **Congela il codice** — nessuna modifica creativa. Solo fix import path (da `analisidef.lib.X` a `pipelines.digest.vendored.X`).
3. Golden diff harness: test automatico che confronta output del vendored vs analisidef su dataset campione (10-20 matchup). Byte-per-byte per campi numerici, semantic diff per stringhe.
4. Solo dopo golden diff = 0 su 3 run consecutivi, cambia `generator.py` a importare da `vendored/` invece che da `analisidef/`.
5. `sys.path.insert(0, "/mnt/.../analisidef")` nel generator.py — RIMOSSO.

**Exit criterion**: `grep -rn "analisidef" App_tool/pipelines/digest/` ritorna zero match.

**Effort**: medio. Scope: copia 1200 LOC + harness test + validation 3 run.

**Rischio**: divergenza silenziosa se il golden diff non cattura tutti i campi. Mitigazione: test coverage obbligatoria su tutti i 15 campi digest + sub-dict `profiles.*`, `lore_speed.*`, `example_games[*].turns`.

#### Stato attuale 15/04/2026 sera

**Tentativo Codex**: lanciato `codex exec` in worktree `.claude/worktrees/codex-p15/` su branch `sprint-p1-5-vendored`. Sessione interrotta presumibilmente per limit turni.

**Step 1 completato** (byte-perfect vendorize):
- `pipelines/digest/vendored/loader.py` (1076 LOC: 1073 source + 3 freeze header)
- `pipelines/digest/vendored/gen_archive.py` (804 LOC: 801 + 3)
- `pipelines/digest/vendored/investigate.py` (807 LOC: 804 + 3)
- `pipelines/digest/vendored/__init__.py` (1 LOC)
- Tutti con header freeze che cita SHA analisidef `58288f36a6e41b1830efab0941223e7160b84450`
- **Untracked, non committati**. Branch `sprint-p1-5-vendored` ancora a `ace88dc` (HEAD di `sprint-p1-digest`).

**Step 2-7 da fare domani**:
2. Fix import paths **interni** ai vendored (es. `from lib.cards_dict import ...` → resolvere). I file attualmente non sono utilizzabili senza fix perché i loro import interni puntano a `lib.*` che non esiste in App_tool
3. Golden diff harness `scripts/diff_digest_vendored.py` — confronta output bridge vs vendored
4. Run harness 3 volte consecutive, diff=0 obbligatorio
5. Switch `generator.py` a importare da `pipelines.digest.vendored.*`
6. Smoke test `generate_digests.py --limit 3`
7. Sprint doc `docs/SPRINT_P1.5_VENDORED.md` + commit pulito

**Rischi post-sessione Codex**: zero impatto prod. Tutto isolato in worktree, nessun commit, nessuna migration.

---

### P2 — Port KC pipeline (dual-run su PG) — DOPO P1.5

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

### P2.5 — Port runtime consumers (replay + kc_spy + llm_worker) — NUOVO

**Scoperta Codex 15/04/2026 sera**: esistono 3 consumer RUNTIME che leggono da analisidef, **non batch**. Vanno portati prima di P4 (decommission) altrimenti spegnere analisidef rompe feature utente-facing.

#### P2.5a — Replay archive endpoint (PRIORITÀ ALTA, user-facing)

`backend/main.py:111-150` → endpoint `/api/replay/list` e `/api/replay/game` leggono hardcoded da `/mnt/.../analisidef/output/archive_*.json`. Serve la feature **Lab tab → Replay Viewer** e **Coach V2 → Replay Viewer**.

**Port path**:
1. Importare gli archive `archive_*.json` esistenti (stale 28/03) in una nuova tabella PG `replay_archives(our_deck, opp_deck, game_format, games JSONB, imported_at)` — **una tantum** preserva i dati storici
2. Endpoint riscritti a leggere da PG invece che da filesystem
3. Archive nuovi: siccome gli archive non vengono più rigenerati dal 28/03 (vedi Discovery sopra), serve generatore nativo in App_tool che produce archive da PG matches. Scope ~800 LOC lift-and-shift di `analisidef/lib/gen_archive.py` (parte di `_build_aggregates` è già in vendored da P1.5) + cron settimanale
4. Alternativa più pulita: rigenerare archive dinamicamente ON-DEMAND al primo hit dell'endpoint, con cache (stesso pattern del dashboard blob)

**Effort**: medio-alto. Blocca P4.

#### P2.5b — kc_spy runtime consumer

`backend/services/snapshot_assembler.py:77-95` legge `kc_spy_report.json` hardcoded da `analisidef/output`. Alimenta la sezione "KC Spy" del dashboard.

**Port path**:
1. Portare `analisidef/kc_spy.py` in `App_tool/scripts/kc_spy.py` (fatto in P2 o separato qui)
2. Output: scrivere in PG `kc_spy_reports` table invece che JSON file
3. Assembler legge da PG, non filesystem

**Effort**: basso-medio (dopo P2).

#### P2.5c — llm_worker.py

`backend/workers/llm_worker.py:8` importa `ANALISIDEF_OUTPUT_DIR` per glob `killer_curves_*.json`. Duplicato di `scripts/import_killer_curves.py`.

**Port path**: verificare se worker è attivo in produzione. Se sì, migrare a leggere da PG nativo (post-P2). Se no (legacy code), rimuovere in P4.

**Effort**: basso.

### P3 — Port matchup reports / daily_routine — DOPO P2

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

## Stato coupling App_tool → analisidef (15/04/2026 sera, post Codex review)

### Livello RUNTIME (servono richieste utente) — BLOCCANTI per qualsiasi decommission

| # | File App_tool | Dipendenza | Sbloccato da |
|---|---|---|---|
| R1 | `backend/main.py:111-150` | `/api/replay/list` + `/api/replay/game` leggono `analisidef/output/archive_*.json` live | **P2.5a** |
| R2 | `backend/services/snapshot_assembler.py:77` | legge `kc_spy_report.json` da analisidef | **P2.5b** |
| R3 | `backend/workers/llm_worker.py:8` | importa `ANALISIDEF_OUTPUT_DIR` per glob KC JSON | **P2.5c** |

### Livello CODICE (import Python runtime — introdotto da P1)

| # | File App_tool | Dipendenza | Sbloccato da |
|---|---|---|---|
| C1 | `pipelines/digest/generator.py` | importa `analisidef.lib.{loader, gen_archive, investigate}` (~1200 LOC) | **P1.5** |

### Livello DATA (file reads batch — importer cron)

| # | File App_tool | Dipendenza | Sbloccato da |
|---|---|---|---|
| D1 | `pipelines/playbook/generator.py` | legge `analisidef/output/digest_*.json` | **P1 cutover** |
| D2 | `scripts/import_killer_curves.py` | legge `analisidef/output/killer_curves_*.json` | **P2** |
| D3 | `scripts/import_matchup_reports.py` | legge `Daily_routine/output/dashboard_data.json` | **P3** |

### Legacy script da rimuovere in P4 (non attivi runtime, ma coupling residuo)

- `scripts/import_archives.py`
- `scripts/import_snapshot.py`
- `scripts/import_playbooks.py` (post Mossa B il generator nativo rende questo bridge obsoleto)
- `scripts/sync_dashboard.sh`

## Rischi noti non-indipendenza

- `lorcana_monitor.py` single-node: se cade, tutto a monte si ferma. Non coperto da P1–P4.
- Stale archive 28/03 esiste ma **non impatta il design digest nuovo** (archive eliminato a monte del digest in P1). Impatta però il **replay endpoint** (R1) che serve archive stale a utente. P2.5a deve rigenerare archive da PG o importarli una tantum.
- Fallback credenziali `/tmp/.openai_key` in `pipelines/playbook/generator.py:1205` = coupling operativo fragile (non analisidef, ma reboot VPS = perdita chiave).

## Exit criteria riformulati (post-Codex)

**Liberation Day** non è "P4 completato", è la capacità di rispondere **SÌ** alla domanda:

> *"Posso spegnere analisidef adesso senza perdere replay, KC spy, playbook, digest, matchup reports, o nessuna feature utente-facing?"*

Checklist oggi (15/04/2026 sera): ❌ NO.
- R1 Replay endpoint: ancora legge analisidef live → Lab tab si rompe
- R2 KC spy: snapshot_assembler ancora legge analisidef → sezione KC Spy vuota
- R3 llm_worker: ancora punta ad ANALISIDEF_OUTPUT_DIR
- C1 Digest generator: ancora importa analisidef code
- D1/D2/D3: data-level couplings esistenti

**Traguardo Liberation Day = risposta SÌ**, quando ogni voce sopra è verde.

---

## 📋 Bilancio giornata 15/04/2026

### Fatto oggi

1. **Sprint-0** ✅ Legality gate nativo App_tool (mattina)
2. **Sprint-1 Mossa A** ✅ Import bridge Blind Playbook (mattina)
3. **Sprint-1 Mossa B** ✅ Generator nativo Blind Playbook + cron settimanale Tue 01:00 (notte)
4. **Discovery** digest dependency trap + archive stale 28/03 (pomeriggio)
5. **P0** ✅ Monitor freshness + baseline + mail alert a `monitorteamfe@gmail.com` + cron 07:00
6. **P1** ✅ Digest nativo PG-first + meta_epochs migration (applicata live) + 3 smoke digest prodotti, schema diff=0 (branch `sprint-p1-digest`, non mergiato)
7. **MIGRATION_PLAN** riscritto con piano P0-P5 + Codex review integrata
8. **P1.5** ⏳ Codex ha fatto step 1/7 (vendorize byte-perfect), uscito senza committare — file untracked nel worktree

### Stato repository fine giornata

- Branch `dev` pulito sul HEAD di stamattina `a838e8c` + untracked files di lavoro (baseline, monitor, migration plan doc update, 3 scripts)
- Branch `sprint-p1-digest` (commit `ace88dc`) con P1 completo shadow, non mergiato
- Branch `sprint-p1-5-vendored` creato, a `ace88dc`, nessun commit nuovo (lavoro di Codex untracked nel worktree)
- Branch `worktree-agent-a46465f8` (Mossa B) — già mergiato
- Migration `meta_epochs` applicata live (2 seed row), non reader prod → zero impatto
- Cron attivi: playbook Tue 01:00, freshness monitor daily 07:00, import_matches ogni 2h (invariato), import_killer_curves Tue 05:30 (invariato), analisidef KC Tue 00:00 (invariato), kc_spy daily 04:00 (invariato)

### Da riprendere domani 16/04/2026

**Prima scelta — merge di P1 o prosecuzione P1.5?**

- Raccomandazione: **completare P1.5 step 2-7 prima del merge P1**. Altrimenti mergi codice con bridge runtime ad analisidef e rischi "tanto funziona" (Codex warning).
- Alternative: merge P1 subito e P1.5 come PR separata. Più granulare ma bridge vive 1-2 giorni in più.

**Completamento P1.5 (step 2-7)**:

2. Fix import paths interni ai vendored (es. `loader.py` importa `lib.cards_dict` → redirect a `pipelines.digest.vendored.cards_dict` o usa App_tool/lib/cards_dict.py già esistente)
3. `scripts/diff_digest_vendored.py` — golden diff harness
4. Run harness 3 volte → diff=0 atteso
5. Switch `pipelines/digest/generator.py` import a `vendored.*`, rimuovere `sys.path.insert(_ANALISIDEF_ROOT)`
6. `grep -rn "analisidef" pipelines/digest/` deve tornare vuoto
7. Smoke test `generate_digests.py --limit 3` + sprint doc + commit

**Altro pending minore (domani o dopo)**:
- P2.5c llm_worker cleanup: dead code confermato, cancellabile. 5 minuti.
- Commit degli untracked su `dev` (baseline script, monitor script, migration plan doc). Oggi sono stati usati live ma non committati.

**Prossimo ciclo verifica automatica**:
- Martedì 21/04 00:00: batch analisidef legacy gira (come sempre)
- Martedì 21/04 01:00: playbook nativo App_tool gira (come settimana scorsa)
- Mercoledì 22/04 07:00: primo vero test del monitor freshness su ciclo completo
- Se monitor manda STALE → investigare prima di P1.5 cutover
