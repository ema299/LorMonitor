# Lorcana Monitor — Architettura Produzione

**Versione:** 5.1 | **Data:** 20 Aprile 2026

---

## 1. Principi

1. **3 strati con contratti fissi**: schemas (contratti) -> pipelines (orchestratori) -> lib (moduli puri). L'HTML non calcola. L'LLM non tocca il codice. I validatori sono guardiani.
2. **Fail-safe by default**: ogni componente ha backup, recovery automatico, e log strutturato. Se un pezzo si rompe, il sistema degrada senza perdere dati.
3. **Performance first**: match in PostgreSQL con indici mirati, query <100ms. Zero file scan a runtime.
4. **Privacy by design**: GDPR-compliant, dati utente criptati, password hashate, cancellazione garantita.
5. **Mobile-native**: PWA responsive, poi wrapper nativo iOS con Capacitor per App Store.
6. **Zero-downtime deploy**: reload graceful, rollback immediato, nessuna interruzione per gli utenti.

---

## 2. Stato Attuale (da migrare)

```
analisidef/                         # Sistema monolitico funzionante
  lib/              6.7K LOC        # 16 moduli Python (loader, investigate, gen_*)
  daily/            9.9K LOC        # daily_routine.py 3456 LOC (monolite), dashboard.html 5259 LOC
  generate_report.py                # Pipeline 5 fasi -> report .md
  output/           3.6 GB          # 139 archive, 132 digest, 134 killer_curves, 140 scores
  reports/          141 .md         # Report matchup (14 deck)
  daily/output/     48 MB           # dashboard_data.json + history.db

Dati sorgente:
  matches/          64K+ file JSON, 3 GB    # Match log turno per turno
  cards_db.json     1511 carte              # DB carte normalizzato
  decks_db/                                  # Decklist tornei
```

**Stato migrazione (aggiornato 16 Apr 2026):**
- 200K+ match in PostgreSQL, import automatico ogni 2h (~1s/run con skip cache)
- 2822 carte in tabella `cards` con image_path completi (thumbnail via cards.duels.ink). 163 carte dual ink con entrambi i colori (es. `"amethyst/sapphire"`), aggiornate settimanalmente via `static_importer.py` (merge duels.ink cache)
- 192 consensus cards, 14 reference decklists, 1047 matchup reports
- Auth JWT completa, HTTPS via nginx + Let's Encrypt su metamonitor.app
- Rate limiting Redis + nginx, fail2ban, UFW attivo (tier-aware via JWT nel middleware; fail-open se Redis non disponibile)
- Backup pg_dump giornaliero, maintenance settimanale (turns retention 90gg)
- Dashboard HTML alleggerito (418 KB, no blob embedded), fetch da API
- Dashboard blob assemblato **live** da PG (snapshot_assembler.py, cache 2h + stale-while-revalidate + warm-up allo startup, no blob statico)
- Matchup reports: tutti i 12 tipi importati (incl. killer_curves, threats_llm, card_scores, pro_mulligans)

**Migrazione serving/runtime da analisidef — COMPLETATA 09 Apr 2026:**
- [x] Fase 0: Tabelle dati statici (cards, consensus_lists, reference_decklists, matchup_reports) + servizi
- [x] Fase 1: Tech tornado da PostgreSQL (query JSONB CARD_PLAYED + consensus)
- [x] Fase 2: Mulligans da PostgreSQL (query JSONB INITIAL_HAND + MULLIGAN)
- [x] Fase 3: Playbook + Optimizer da PostgreSQL (961 report importati da dashboard_data.json → matchup_reports)
- [x] Fase 4: Leaderboard da duels.ink API diretta (leaderboard_service.py, cache Redis 1h, queue IDs: core-bo1, core-bo3, infinity-bo1-beta, infinity-bo3-beta)
- [x] Fase 5: /api/v1/dashboard-data assembla blob live da PG (snapshot_assembler, cache 2h stale-while-revalidate)
- [x] Fase 6: dashboard_bridge.py rimosso, nessun fallback a file JSON, API 100% da PostgreSQL
- [x] Fase A: Import match automatico ogni 2h (skip cache, ON CONFLICT DO NOTHING)
- [x] Fase B-C: Meta stats e player stats live da PG (query <150ms, no materialized views necessarie)
- [x] Fase D: Tech tornado da PG (già completata)
- [x] Fase E: Dashboard blob assemblato live da PG (snapshot_assembler.py, 21 sezioni, ~8 MB, cache 2h stale-while-revalidate)

**UI uniformity pass (14 Apr 2026):**
- **Pattern `monAccordion` esteso** a tutto Lab (Mulligan Trainer, Card Impact Correlation, Card Impact IWD, Optimized Deck title) e Coach V2 (Opponent Playbook, How to Respond, Killer Curves, Key Threats, Opponent\'s Killer Cards, Trend by Turn)
- **Uniformità header**: titolo gold 1.1em weight 600, bottone "?" subito dopo (apre bottom-sheet su mobile, modal su desktop), chevron a destra, click header o chevron apre/chiude
- **Open-by-default desktop solo per KPI principali**: Deck Analysis (Monitor), Mulligan Trainer (Lab), Key Threats (Coach V2). Tutto il resto chiuso di default.
- **Rimossi**: tutti i `section-title` custom nel Coach V2 + Lab con chevron inline sinistro e onclick toggle non uniforme.
- **Chart.js dentro accordion chiusi**: risolto via `onOpen: monAccOnExpandResize` che dispatcha `window.resize` post-animazione (340ms). Applicato a: `acc-deck` (Monitor Deck Analysis), `acc-trend` (Coach Trend by Turn).

**Card Impact (IWD) — Lab tab (14 Apr 2026):**
- **IWD = Improvement When Drawn** (stile 17Lands, adattato a Lorcana). Per ogni carta del nostro deck, misura come cambia la nostra WR quando la carta è vista in mano entro T3.
- **Definizione "drawn by T3"**: carta appare in `INITIAL_HAND`, `CARD_DRAWN`, `CARD_PLAYED` o `CARD_INKED` per `player=1` con `turnNumber <= 3`. Inferenza da CARD_PLAYED/CARD_INKED necessaria perché TURN_DRAW (draw automatico) ha `cardRefs` vuoto nei log pubblici duels.ink.
- **Pool candidati**: top 30 carte più viste nei match del matchup (data-driven, no dipendenza da consensus list). Soglia min 20 drawn + 20 not-drawn games per carta.
- **Soglia matchup**: `MIN_TOTAL_MATCHES=80` sotto cui tutto il matchup è low-sample (output `cards=[]`).
- **Backend**: `backend/services/lab_iwd_service.get_iwd(db, our, opp, format, days)` + endpoint pubblico `GET /api/v1/lab/iwd/{our}/{opp}`. Query JSONB ~1.3-2s per matchup con 1000+ games. Non cachato server-side (fetch on-demand), ma frontend cachea per session.
- **Frontend**: nuovo accordion `Card Impact (IWD)` nel Lab, lazy load via `onOpen` callback, sort `|Δ|/+Δ/−Δ/N` + "Show top 5 / Show all". Info "?" spiega differenza con Card Impact correlation esistente (causal vs correlation).
- **File toccati**: `backend/services/lab_iwd_service.py` (nuovo, 158 LOC), `backend/api/lab.py` (+1 endpoint), `frontend/dashboard.html` (+150 LOC CSS, +130 LOC JS, additive). Endpoint pubblico (no `require_tier`) coerente con dashboard-data.
- **Zero regressione**: Card Impact esistente (correlation) invariato, nuova sezione additiva.

**Monitor tab redesign (14 Apr 2026):**
- **Deck Fitness Score**: nuova strip sempre visibile in cima al tab. Card 132×100 per deck, scroll orizzontale, score 0-100 meta-weighted (`Σ (WR vs X · meta_share[X]) / Σ meta_share[X]`, 50 = break-even, min 15 games per matchup). Deck #1 bordo gold + glow. Desktop: wheel→horizontal scroll + frecce navigazione; mobile: touch swipe
- **Matchup Matrix** (nuovo): accordion chiuso di default ovunque. Desktop = heatmap NxN con sticky row headers + colori rosso/giallo/verde. Mobile = lista filtrata per deck selezionato. Click cella → `switchToTab('coach_v2', {deck, opp})` con sync ink picker nostro+avversario + `localStorage.lorcana_deck_code`
- **Uniformità accordion**: tutte le sezioni Monitor (Matchup Matrix, Deck Analysis, Best Format Players, Non-Standard Picks) usano pattern `monAccordion()` con titolo gold, bottone "?" subito dopo (bottom-sheet su mobile, modal su desktop), chevron a destra. `desktopOpen: true` solo per Deck Analysis (contiene charts Chart.js)
- **Rimossa Meta Overview** (tabella piatta): ridondante rispetto alla Fitness strip
- **Backend**: `snapshot_assembler._compute_fitness()` aggiunge campo `fitness` a ogni perimetro del blob `dashboard-data` (~150 bytes extra per perimetro, cache 2h invariata). Nuovo endpoint dedicato `GET /api/v1/monitor/deck-fitness` per debug/batch
- **File toccati**: `backend/services/snapshot_assembler.py` (+50 LOC), `backend/services/stats_service.py` (+50 LOC), `backend/api/monitor.py` (+1 endpoint), `frontend/dashboard.html` (~450 LOC tra CSS e JS, additive)
- **Zero regressione**: tutti i cambi additivi, `monAccordion` retrocompatibile (default `desktopOpen: true` invariato), endpoint esistenti intatti

**Parametri chiave (aggiornati 10 Apr 2026):**
- **DAYS = 3** — finestra analisi Monitor/Profile/Tech (era 2)
- **TOP_N = 100, PRO_N = 50** — leaderboard thresholds (era 70/30)
- **PRO = solo leaderboard top 50** — rimossa lista hardcoded, solo duels.ink API live
- **Queue IDs duels.ink**: `core-bo1`, `core-bo3` (aggiornati da `core-set11-*-beta`), `infinity-bo1-beta`, `infinity-bo3-beta`
- **Cache dashboard: TTL 2h** + stale-while-revalidate (serve vecchio, ricostruisce in background) + warm-up allo startup
- **Matchup trend**: 7gg finestra, formato `{perim: {deck: {opp: {current_wr, delta, recent_games}}}}`, ultimi 3gg vs 3gg precedenti
- **Monitor "Best Format Players"**: sezione top_players filtrata solo a nomi presenti nella leaderboard duels.ink
- **player_lookup**: `{core: {player: {deck: {w,l,mmr}}}, infinity: {...}}` — stats personali per "My Stats" in Profile, split per formato, nessun filtro leaderboard, stessa finestra DAYS=3

**Fix runtime e resilienza dati statici (20 Apr 2026):**
- **Importer consensus fail-safe**: `backend/workers/static_importer.py` non fa piu' il demote globale di `is_current=true` su `consensus_lists` e `reference_decklists`. Ora demota solo i deck effettivamente presenti nello snapshot nuovo. Questo impedisce che uno snapshot InkDecks parziale azzeri 10+ deck dal monitor/profile.
- **Origine incidente**: gli snapshot InkDecks dal `17/04/2026` al `19/04/2026` sono risultati parziali (5, 4, 5 archetipi vs 15 il `16/04/2026`). Il fetch giornaliero quindi c'e', ma il dato upstream non e' completo.
- **Frontend Best Format Players**: il compare decklist non dipende piu' solo dalla presenza simultanea di `consensus` + `player_cards` core. `buildDeckCompare()` degrada correttamente se la consensus non e' disponibile e il blob ora include anche `player_cards_infinity`, quindi il compare puo' apparire anche in formato Infinity.
- **KC Health badge**: il dashboard usa i contatori `validation_after_fix` se presenti, cosi' il badge non resta ancorato ai vecchi bucket `files_warn`.
- **Killer Curves Core legality**: il batch nativo `scripts/generate_killer_curves.py` e il prompt `pipelines/kc/build_prompt.py` applicano ora anche un guard di legalita' Core basato su `meta_epochs.legal_sets`, non solo un vincolo di colori. Questo evita curve Core con carte Infinity-only come `Be Prepared`.
- **Post-filter difensivo**: anche se l'LLM propone una carta fuori rotazione, il generator rimuove da `sequence.plays` e `response.cards` ogni carta non legale per il Core corrente prima dell'upsert in `killer_curves`.

**Profile tab (aggiornato 10 Apr 2026):**
- **Select Your Deck** (box gold): ink picker 6 colonne con label, toggle Standard/My Deck, sezione "Saved Decks" con card per deck pinnato, sezione "My Stats" collapsibile con tutti i deck giocati (icona, WR bar, peggior matchup), click per selezionare
- **Meta Radar** (box rosso): deck identity banner, KPI strip (WR, Share, Games, Players del meta), Best/Worst matchups in box separati, sezione "Threats to watch"
- My Stats usa `DATA.player_lookup[formato][nick]` — coerente col formato Core/Infinity selezionato

**Dipendenze residue da analisidef (bridge temporaneo, stato 15 Apr 2026 sera — Liberation Day):**
- `lorcana_monitor.py` → `/matches/*.json` (collection dati live) — **non spostabile** (collection infra)
- `daily_routine.py` → `dashboard_data.json` → `import_matchup_reports.py` (12 tipi, analyzer 12K LOC) — **D3, target P3**
- `run_kc_production.sh` → killer curves via OpenAI → `import_killer_curves.py` — **D2, target P2**
- `pipelines/playbook/generator.py` → `analisidef/output/digest_*.json` — **D1, target 16/04 (cutover a digest nativo)**
- `kc_spy.py` → `kc_spy_report.json` → `import_kc_spy.py` (cron 04:05 daily) — **producer legacy, consumer runtime gia' su PG**

**Dipendenze runtime gia' rimosse da analisidef (15 Apr 2026 — Liberation Day):**
- R1 replay viewer pubblico — `/api/replay/list` + `/api/replay/game` leggono da PostgreSQL (`replay_archives`, 271 archive importati, 601MB JSONB) via `backend/services/replay_archive_service.py`
- R2 dashboard `kc_spy` — `snapshot_assembler._load_kc_spy` legge da PostgreSQL (`kc_spy_reports`) via `backend/services/kc_spy_service.py`
- R3 `backend/workers/llm_worker.py` — **rimosso** (dead code, non schedulato, commit `9ec0f45`)
- C1 digest generator code-level — `pipelines/digest/vendored/` (1200 LOC congelati da `58288f36`), golden diff `DIFFS=0` su 10 matchup, smoke generate_digests ok

**Eliminato dal serving path:** `import_snapshot.py` e `assemble_snapshot.py` non sono necessari per servire il blob live. Possono restare come superficie legacy/storica finche' non verranno rimossi dal repo.

**Frontend:** il file di produzione vive in `App_tool/frontend/dashboard.html`. Rimane ancora monolitico, ma non e' piu' un symlink e non deve dipendere da sync manuali da analisidef.

**Cron App_tool (UTC, verificato 15 Apr 2026 via `crontab -l`):**
```
*/2h        import_matches.py           → match JSON → PG (~1s)
*/5min      healthcheck.sh              → monitoring, auto-restart
03:00       backup.sh                   → pg_dump giornaliero
Dom 02:00   maintenance.sh              → drop turns >90gg, VACUUM
Dom 04:45   static_importer.py          → cards DB refresh (duels.ink cache merge)
04:05       import_kc_spy.py            → KC Spy JSON legacy → PG `kc_spy_reports` (aggiunto 15/04)
05:30       import_matchup_reports.py   → 12 tipi report da dashboard_data.json → PG
Mar 00:00   (analisidef) run_kc_production.sh   → OpenAI batch KC
Mar 01:00   generate_playbooks.py       → playbook nativo App_tool
Mar 05:30   import_killer_curves.py     → KC da analisidef/output → PG
07:00       monitor_kc_freshness.py     → canary freshness, mail STALE/ERROR
```
**Nota:** l'API assembla il blob on-demand con cache 2h + stale-while-revalidate + warm-up allo startup. `assemble_snapshot.py` non e' parte del serving runtime corrente.

**Nota operativa 20/04/2026:** il cron `decks_db_builder.py` continua a girare giornalmente, ma non garantisce snapshot completi se InkDecks risponde in modo parziale. La frequenza del cron non e' il problema; il rischio corrente e' la sparse coverage upstream. Finche' non viene corretto lo scraper esterno, i deck assenti continuano a mostrare consensus/reference piu' vecchie ma preservate dal nuovo importer fail-safe.

---

## 3. Architettura Target

```
                    ┌──────────────────────────────────────────────────┐
                    │                   INTERNET                       │
                    └──────────────────────┬───────────────────────────┘
                                          │
                                   ┌──────┴──────┐
                                   │    nginx     │
                                   │  + SSL/TLS   │
                                   │  + rate limit│
                                   │  + gzip      │
                                   └──┬───────┬───┘
                                      │       │
                          ┌───────────┘       └───────────┐
                          │                               │
                   ┌──────┴──────┐                 ┌──────┴──────┐
                   │  Frontend   │                 │  Backend    │
                   │  Static     │                 │  FastAPI    │
                   │  (nginx)    │                 │  (uvicorn)  │
                   └─────────────┘                 └──────┬──────┘
                                                          │
                          ┌───────────────┬───────────────┼───────────────┐
                          │               │               │               │
                   ┌──────┴──────┐ ┌──────┴──────┐ ┌─────┴──────┐ ┌─────┴──────┐
                   │ PostgreSQL  │ │    Redis     │ │ LLM Worker │ │  Pipeline  │
                   │ (dati+auth) │ │ (cache+sess) │ │  (async)   │ │  (cron)    │
                   └─────────────┘ └─────────────┘ └────────────┘ └────────────┘
```

---

## 4. Alberatura App_tool

```
App_tool/
│
├── ARCHITECTURE.md
├── ARCHITECTURE_EXPLANATION.md     # Spiegazione per non-tecnici
│
├── backend/                          # FastAPI application
│   ├── main.py                       # Entrypoint uvicorn
│   ├── config.py                     # Settings (env vars, path, costanti)
│   ├── deps.py                       # Dependency injection (db session, current_user)
│   │
│   ├── api/                          # Route handlers
│   │   ├── auth.py                   # POST /login, /register, /logout, /refresh
│   │   ├── monitor.py                # GET /meta, /deck, /players, /tech
│   │   ├── coach.py                  # GET /matchup, /killer-curves, /threats
│   │   ├── lab.py                    # GET /optimizer, /mulligans, /card-scores
│   │   ├── user.py                   # GET/POST/DELETE /decks, /profile, /preferences
│   │   ├── admin.py                  # POST /refresh-daily, /refresh-curves, /health
│   │   └── webhooks.py               # Stripe webhook, monitor alerts
│   │
│   ├── models/                       # SQLAlchemy ORM models
│   │   ├── user.py                   # User, UserPreferences
│   │   ├── subscription.py           # Subscription, PaymentHistory
│   │   ├── match.py                  # Match (JSONB turns)
│   │   ├── analysis.py               # KillerCurve, Archive, ThreatLLM, DailySnapshot
│   │   └── user_deck.py              # UserDeck
│   │
│   ├── services/                     # Business logic (moduli puri)
│   │   ├── auth_service.py           # Hash, verify, JWT, refresh token, password reset     ✅
│   │   ├── stats_service.py          # WR, matrice, trend, meta share, OTP/OTD              ✅
│   │   ├── players_service.py        # Top players, pro detail, scouting                    ✅
│   │   ├── tech_service.py           # Tech tornado da PG (CARD_PLAYED JSONB + consensus)   ✅
│   │   ├── matchup_service.py        # Killer curves, threats, playbook, optimizer da PG    ✅
│   │   ├── deck_service.py           # Card scores, mulligan da PG (INITIAL_HAND JSONB)     ✅
│   │   ├── static_data_service.py    # Cards, consensus, reference decklists da PG          ✅
│   │   ├── leaderboard_service.py    # Fetch duels.ink API diretta, cache Redis 1h          ✅
│   │   ├── history_service.py        # Storico snapshot, trend da PG                        ✅
│   │   ├── subscription_service.py   # Stripe checkout, webhook, cancel                     ✅
│   │   ├── team_service.py           # Team stats, overview, weaknesses da PG               ✅
│   │   ├── cache.py                  # Redis cache layer con fallback dict                  ✅
│   │   └── alerting.py               # Telegram bot notifiche (serve TG_BOT_TOKEN)          ✅
│   │
│   ├── middleware/                    # Cross-cutting concerns
│   │   ├── rate_limit.py             # Per-endpoint, per-tier rate limiting
│   │   ├── logging_mw.py             # Request/response structured logging
│   │   ├── cors.py                   # CORS policy
│   │   └── error_handler.py          # Global exception handler, error codes
│   │
│   └── workers/                      # Background jobs
│       ├── daily_pipeline.py         # Cron 07:00 — aggiorna monitor_data
│       ├── weekly_pipeline.py        # Cron lunedi — aggiorna coach_data + lab_data
│       ├── match_importer.py         # Cron 06:00 — importa nuovi match JSON -> PostgreSQL
│       └── backup_worker.py          # Cron 03:00 — pg_dump + upload offsite
│
├── schemas/                          # JSON Schema (contratti API)
│   ├── monitor.schema.json
│   ├── coach.schema.json
│   ├── lab.schema.json
│   ├── killer_curves.schema.json
│   ├── user.schema.json
│   └── validate.py                   # Validatore generico
│
├── lib/                              # Moduli puri riciclati da analisidef/lib
│   ├── loader.py                     # Interfaccia unica: load_matches(perimeter, ...)
│   ├── investigate.py                # Board state, ink budget, classify_losses
│   ├── stats.py                      # Calcoli statistici puri
│   ├── cards_dict.py                 # 1511 carte normalizzate
│   ├── formatting.py                 # Display helpers
│   ├── gen_archive.py                # Genera archivio JSON
│   ├── gen_digest.py                 # Genera digest compatto per LLM
│   └── validate_killer_curves.py     # Validazione meccanica
│
├── pipeline/                         # ⚠️ SNAPSHOT da analisidef — solo storage/git, NON usato da App_tool
│   │                                 # Copiato il 01/04/2026 per avere backup versionato
│   │                                 # La produzione gira ancora da analisidef/
│   ├── daily/
│   │   ├── daily_routine.py          # Orchestratore principale (cron giornaliero, 3456 LOC)
│   │   ├── history_db.py             # Storico snapshot SQLite
│   │   ├── serve_dashboard.py        # Server HTTP vecchio (:8060)
│   │   ├── serve.py                  # Server minimale
│   │   ├── team_training.py          # Team stats generator
│   │   └── backfill_history.py       # Riempimento storico retroattivo
│   ├── lib/
│   │   ├── loader.py                 # Caricamento match JSON (42K LOC)
│   │   ├── investigate.py            # Board state, ink budget, classify_losses
│   │   ├── gen_archive.py            # Genera archive_*.json (dettagli partite)
│   │   ├── gen_digest.py             # Genera digest compatto per LLM
│   │   ├── gen_killer_curves.py      # Genera playbook + threat curves
│   │   ├── gen_decklist.py           # Card scores per matchup
│   │   ├── gen_review.py             # Review tattica
│   │   ├── gen_risposte.py           # Analisi risposte
│   │   ├── gen_mani.py               # Analisi mani iniziali
│   │   ├── gen_panoramica.py         # Panoramica matchup
│   │   ├── gen_curve_t1t7.py         # Curve mana turni 1-7
│   │   ├── gen_deck_actually.py      # "Deck actually played" analysis
│   │   ├── gen_all_turns.py          # Dump tutti i turni
│   │   ├── gen_validate.py           # Validazione output generati
│   │   ├── gen_killer_curves_draft.py # KC versione draft
│   │   ├── stats.py                  # Calcoli statistici puri
│   │   ├── cards_dict.py             # 1511 carte normalizzate
│   │   ├── formatting.py             # Display helpers
│   │   ├── i18n.py                   # Internazionalizzazione
│   │   ├── assembler.py              # Assembla sezioni report
│   │   ├── build_replay_steps.py     # Ricostruzione passi replay
│   │   ├── validate.py               # Validazione generica
│   │   ├── validate_killer_curves.py # Validazione meccanica KC
│   │   ├── validate_semantics.py     # Validazione semantica
│   │   └── __init__.py
│   ├── generate_report.py            # Pipeline 5 fasi → report .md
│   ├── run_kc_production.py          # Killer curves batch production
│   ├── build_replay.py               # Replay builder v1
│   ├── build_replay_v2.py            # Replay builder v2
│   └── audit_replay.py               # Audit qualita' replay
│
├── llm/                              # Output LLM (generati da Claude API)
│   ├── killer_curves/                # JSON validati contro schema
│   ├── threats/                      # Analisi minacce
│   ├── reviews/                      # Review tattica 6 pass
│   └── instructions/                 # Prompt per Claude
│       ├── ISTRUZIONI_KILLER_CURVES.md
│       ├── ISTRUZIONI_REVIEW.md
│       └── LORCANA_RULES_REFERENCE.md
│
├── frontend/                         # SPA statica (servita da nginx)
│   ├── index.html                    # Shell SPA
│   ├── assets/
│   │   ├── css/
│   │   │   └── app.css
│   │   ├── js/
│   │   │   ├── app.js                # Router + state management
│   │   │   ├── api.js                # Fetch wrapper con auth token
│   │   │   ├── monitor.js            # Tab Monitor
│   │   │   ├── coach.js              # Tab Coach V2
│   │   │   ├── lab.js                # Tab Lab
│   │   │   ├── team.js               # Tab Team Training
│   │   │   └── auth.js               # Login/register/logout
│   │   ├── icons/                    # PWA icons (192, 512)
│   │   └── vendor/
│   │       └── chart.min.js
│   ├── manifest.json                 # PWA manifest
│   └── sw.js                         # Service Worker (offline, cache)
│
├── mobile/                           # iOS wrapper (Capacitor)
│   ├── capacitor.config.ts
│   ├── ios/                          # Xcode project (generato)
│   └── README.md                     # Build & deploy instructions
│
├── db/                               # Database
│   ├── migrations/                   # Alembic migrations
│   │   ├── env.py
│   │   └── versions/
│   │       ├── 001_initial.py        # Users, subscriptions, matches
│   │       ├── 002_analysis.py       # Killer curves, archives, threats
│   │       └── 003_snapshots.py      # Daily snapshots, history
│   ├── seed.py                       # Import iniziale: 64K JSON -> PostgreSQL
│   └── backup.sh                     # Script pg_dump + compress + rotate
│
├── infra/                            # Configurazione infrastruttura
│   ├── nginx/
│   │   ├── lorcana.conf              # Virtual host (SSL, proxy, rate limit, headers)
│   │   └── security.conf             # CSP, HSTS, X-Frame, X-Content-Type
│   ├── systemd/
│   │   ├── lorcana-api.service       # FastAPI (uvicorn)
│   │   ├── lorcana-worker.service    # Background workers
│   │   └── lorcana-backup.timer      # Backup timer
│   ├── certbot/
│   │   └── renew.sh                  # Let's Encrypt auto-renewal
│   ├── logrotate/
│   │   └── lorcana                   # Rotazione log (7gg retain, compress)
│   ├── monitoring/
│   │   ├── healthcheck.py            # /health endpoint check + alert
│   │   └── uptime.sh                 # Cron 5min: check API, DB, disk, memory
│   └── docker-compose.yml            # Dev environment (opzionale)
│
├── scripts/                          # Utility operative
│   ├── import_matches.py             # Bulk import 64K JSON -> PostgreSQL
│   ├── migrate_killer_curves.py      # Migra output/ JSON -> PostgreSQL
│   ├── migrate_history.py            # Migra history.db SQLite -> PostgreSQL
│   ├── create_admin.py               # Crea utente admin
│   ├── benchmark_queries.py          # Misura performance query critiche
│   └── deploy.sh                     # Deploy zero-downtime (git pull + reload)
│
├── tests/                            # Test suite
│   ├── test_services/
│   ├── test_api/
│   ├── test_lib/
│   └── conftest.py                   # Fixture DB test (PostgreSQL test DB)
│
├── .env.example                      # Template variabili ambiente
├── .env.dev                          # Variabili dev (non versionato)
├── requirements.txt                  # Dipendenze Python
└── .gitignore
```

---

## 5. Database — PostgreSQL

### 5.1 Perche' PostgreSQL (non MongoDB, non SQLite)

| Criterio | PostgreSQL | MongoDB | SQLite |
|----------|-----------|---------|--------|
| Relazionale (users, subs) | Nativo | Forzato | Nativo |
| Documentale (match turns) | JSONB eccellente | Nativo | JSON1 limitato |
| Query aggregate SQL | Si | Aggregation pipeline | Si |
| Indici su JSONB | GIN, btree su path | Si | No |
| Backup/replica | pg_dump, streaming | mongodump | File copy |
| Concorrenza multi-utente | MVCC maturo | Si | Write lock globale |
| Tooling | pgAdmin, pg_stat | Compass | Limitato |
| Un solo servizio | Si | Serve mongod separato | Si (ma non scala) |
| Managed su Hetzner | Si (futuro) | No | N/A |

**Scelta: PostgreSQL.** Un DB per relazionale + documentale. SQLite non regge concorrenza. MongoDB aggiunge un servizio senza vantaggi reali per questo caso (dati misti relazionali + documenti).

### 5.2 Schema

```sql
-- ============================================================
-- UTENTI E ABBONAMENTI
-- ============================================================

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,         -- bcrypt (cost 12)
    display_name    VARCHAR(100),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    last_login      TIMESTAMPTZ,
    is_active       BOOLEAN DEFAULT true,
    is_admin        BOOLEAN DEFAULT false,
    tier            VARCHAR(20) DEFAULT 'free',     -- free, pro, team
    stripe_customer_id VARCHAR(255),
    preferences     JSONB DEFAULT '{}',             -- lingua, deck preferito, notifiche
    deletion_requested_at TIMESTAMPTZ              -- GDPR: soft delete schedulato
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_tier ON users(tier);

CREATE TABLE subscriptions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    tier            VARCHAR(20) NOT NULL,           -- pro, team
    status          VARCHAR(20) NOT NULL,           -- active, cancelled, past_due, trialing
    stripe_sub_id   VARCHAR(255) UNIQUE,
    current_period_start TIMESTAMPTZ,
    current_period_end   TIMESTAMPTZ,
    cancel_at       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_subs_user ON subscriptions(user_id);
CREATE INDEX idx_subs_status ON subscriptions(status);

CREATE TABLE password_reset_tokens (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    token_hash      VARCHAR(255) NOT NULL,          -- SHA-256 del token
    expires_at      TIMESTAMPTZ NOT NULL,
    used_at         TIMESTAMPTZ
);

CREATE TABLE user_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    refresh_token_hash VARCHAR(255) NOT NULL,
    device_info     VARCHAR(500),
    ip_address      INET,
    created_at      TIMESTAMPTZ DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL,
    revoked_at      TIMESTAMPTZ
);

CREATE INDEX idx_sessions_user ON user_sessions(user_id);

-- ============================================================
-- DECK UTENTE ("Mio Deck")
-- ============================================================

CREATE TABLE user_decks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    name            VARCHAR(100) NOT NULL,
    deck_code       VARCHAR(10) NOT NULL,           -- AmAm, ES, etc.
    cards           JSONB NOT NULL,                  -- [{card_name, count}, ...]
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_user_decks_user ON user_decks(user_id);

-- ============================================================
-- MATCH (sorgente dati principale)
-- ============================================================

CREATE TABLE matches (
    id              BIGSERIAL PRIMARY KEY,
    external_id     VARCHAR(100) UNIQUE,            -- ID originale duels.ink
    played_at       TIMESTAMPTZ NOT NULL,
    game_format     VARCHAR(20) NOT NULL,            -- core, infinity
    queue_name      VARCHAR(50),                     -- S11-BO1, INF-BO3, etc.
    perimeter       VARCHAR(20) NOT NULL,            -- set11, top, pro, friends, infinity
    deck_a          VARCHAR(10) NOT NULL,
    deck_b          VARCHAR(10) NOT NULL,
    winner          VARCHAR(10),                     -- deck_a, deck_b, draw
    player_a_name   VARCHAR(100),
    player_b_name   VARCHAR(100),
    player_a_mmr    INTEGER,
    player_b_mmr    INTEGER,
    total_turns     INTEGER,
    lore_a_final    INTEGER,
    lore_b_final    INTEGER,
    turns           JSONB NOT NULL,                  -- [{plays, abilities, challenges, ...}, ...]
    cards_a         JSONB,                           -- lista carte giocate da A
    cards_b         JSONB,                           -- lista carte giocate da B
    imported_at     TIMESTAMPTZ DEFAULT now()
);

-- Indici critici per performance (<100ms per matchup query)
CREATE INDEX idx_matches_format ON matches(game_format);
CREATE INDEX idx_matches_perimeter ON matches(perimeter);
CREATE INDEX idx_matches_decks ON matches(deck_a, deck_b);
CREATE INDEX idx_matches_date ON matches(played_at DESC);
CREATE INDEX idx_matches_mmr_a ON matches(player_a_mmr);
CREATE INDEX idx_matches_mmr_b ON matches(player_b_mmr);

-- Indice composto per la query piu' frequente:
-- "tutti i match core AmAm vs ES degli ultimi 2 giorni"
CREATE INDEX idx_matches_lookup ON matches(game_format, deck_a, deck_b, played_at DESC)
    WHERE perimeter IN ('set11', 'top', 'pro', 'friends');

-- ============================================================
-- ANALISI (output pipeline + LLM)
-- ============================================================

CREATE TABLE killer_curves (
    id              BIGSERIAL PRIMARY KEY,
    generated_at    DATE NOT NULL,
    game_format     VARCHAR(20) NOT NULL,
    our_deck        VARCHAR(10) NOT NULL,
    opp_deck        VARCHAR(10) NOT NULL,
    curves          JSONB NOT NULL,
    match_count     INTEGER,
    loss_count      INTEGER,
    version         INTEGER DEFAULT 1,
    is_current      BOOLEAN DEFAULT true,
    UNIQUE(game_format, our_deck, opp_deck, generated_at)
);

CREATE INDEX idx_kc_lookup ON killer_curves(game_format, our_deck, opp_deck, is_current)
    WHERE is_current = true;

-- NOTA ARCHITETTURALE: la tabella archives contiene SOLO gli aggregati
-- statistici (~15 KB/matchup), NON i log turno-per-turno delle partite.
-- I file archive_*.json originali (3.6 GB) includevano anche games[].turns,
-- ma quei dati sono gia' nella tabella matches.turns (JSONB).
-- Scelta fatta il 2026-03-30 per evitare ~3.6 GB di duplicazione.
CREATE TABLE archives (
    id              BIGSERIAL PRIMARY KEY,
    generated_at    DATE NOT NULL,
    game_format     VARCHAR(20) NOT NULL,
    our_deck        VARCHAR(10) NOT NULL,
    opp_deck        VARCHAR(10) NOT NULL,
    aggregates      JSONB NOT NULL,          -- solo aggregati: cause_frequency,
                                             -- critical_turn_distribution, loss_profiles, etc.
    match_count     INTEGER,
    UNIQUE(game_format, our_deck, opp_deck, generated_at)
);

CREATE TABLE threats_llm (
    id              BIGSERIAL PRIMARY KEY,
    generated_at    DATE NOT NULL,
    game_format     VARCHAR(20) NOT NULL,
    our_deck        VARCHAR(10) NOT NULL,
    opp_deck        VARCHAR(10) NOT NULL,
    threats         JSONB NOT NULL,
    is_current      BOOLEAN DEFAULT true,
    UNIQUE(game_format, our_deck, opp_deck, generated_at)
);

CREATE TABLE daily_snapshots (
    id              BIGSERIAL PRIMARY KEY,
    snapshot_date   DATE NOT NULL,
    perimeter       VARCHAR(20) NOT NULL,
    data            JSONB NOT NULL,
    UNIQUE(snapshot_date, perimeter)
);

CREATE INDEX idx_snapshots_date ON daily_snapshots(snapshot_date DESC);

-- ============================================================
-- RUNTIME DECOUPLING (aggiunte 15 Apr 2026 — Liberation Day)
-- ============================================================

-- replay_archives (R1): sostituisce la lettura live di analisidef/output/archive_*.json
-- Popolata da scripts/import_replay_archives.py (271 archive, ~601MB JSONB).
-- Letta da backend/services/replay_archive_service.py per /api/replay/list + /api/replay/game.
CREATE TABLE replay_archives (
    id              BIGSERIAL PRIMARY KEY,
    our_deck        VARCHAR(16) NOT NULL,
    opp_deck        VARCHAR(16) NOT NULL,
    game_format     VARCHAR(16) NOT NULL,
    metadata        JSONB NOT NULL,
    games           JSONB NOT NULL,
    imported_at     TIMESTAMPTZ DEFAULT now(),
    UNIQUE(our_deck, opp_deck, game_format)
);

-- kc_spy_reports (R2): sostituisce la lettura live di analisidef/output/kc_spy_report.json
-- Popolata da scripts/import_kc_spy.py (cron 04:05 UTC daily).
-- Letta da backend/services/kc_spy_service.py + snapshot_assembler.
CREATE TABLE kc_spy_reports (
    id              BIGSERIAL PRIMARY KEY,
    generated_at    TIMESTAMPTZ NOT NULL,
    game_format     VARCHAR(16) NOT NULL,
    report          JSONB NOT NULL,
    imported_at     TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_kc_spy_generated ON kc_spy_reports(generated_at DESC);

-- meta_epochs (P1 digest): governa set-legality + window effettiva del digest generator.
-- Popolata manualmente al release di ogni nuovo set Ravensburger.
CREATE TABLE meta_epochs (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    started_at      DATE NOT NULL,
    ended_at        DATE,
    legal_sets      INTEGER[] NOT NULL,
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- AUDIT LOG
-- ============================================================

CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    event_type      VARCHAR(50) NOT NULL,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    ip_address      INET,
    details         JSONB,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_audit_user ON audit_log(user_id, created_at DESC);

-- ============================================================
-- COMMUNITY (aggiunto 02 Apr 2026)
-- ============================================================

CREATE TABLE videos (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           VARCHAR(200) NOT NULL,
    url             VARCHAR(500) NOT NULL,
    platform        VARCHAR(20),
    topic           VARCHAR(50),
    tags            JSONB DEFAULT '[]',
    is_live         BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE tournaments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(200) NOT NULL,
    date            DATE NOT NULL,
    location        VARCHAR(200),
    format          VARCHAR(20),
    region          VARCHAR(50),
    url             VARCHAR(500),
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- PROMO CODES (aggiunto 30 Mar 2026)
-- ============================================================

CREATE TABLE promo_codes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code            VARCHAR(50) UNIQUE NOT NULL,
    type            VARCHAR(20) NOT NULL,       -- tier_upgrade, discount
    granted_tier    VARCHAR(20),
    duration_days   INTEGER,
    discount_percent INTEGER,
    discount_months INTEGER,
    max_uses        INTEGER,
    times_used      INTEGER DEFAULT 0,
    is_active       BOOLEAN DEFAULT true,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE promo_redemptions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    promo_code_id   UUID REFERENCES promo_codes(id),
    user_id         UUID REFERENCES users(id),
    redeemed_at     TIMESTAMPTZ DEFAULT now(),
    original_tier   VARCHAR(20),
    granted_tier    VARCHAR(20),
    expires_at      TIMESTAMPTZ
);
```

### 5.3 Materialized Views (precalcolo)

```sql
CREATE MATERIALIZED VIEW mv_meta_share AS
SELECT game_format, perimeter, deck_a as deck,
       COUNT(*) as games,
       COUNT(*) FILTER (WHERE winner = 'deck_a') as wins
FROM matches
WHERE played_at >= now() - INTERVAL '2 days'
GROUP BY game_format, perimeter, deck_a;

CREATE MATERIALIZED VIEW mv_matchup_matrix AS
SELECT game_format, perimeter, deck_a, deck_b,
       COUNT(*) as games,
       COUNT(*) FILTER (WHERE winner = 'deck_a') as wins_a,
       AVG(total_turns) as avg_turns
FROM matches
WHERE played_at >= now() - INTERVAL '7 days'
GROUP BY game_format, perimeter, deck_a, deck_b;
```

### 5.4 Performance Target

| Query | Target | Strategia |
|-------|--------|-----------|
| WR matchup (2gg, 1 perimetro) | <50ms | Indice composto `idx_matches_lookup` |
| Matrice 12x12 (tutti matchup) | <500ms | 1 query aggregata con GROUP BY |
| Killer curves correnti | <10ms | Indice parziale `WHERE is_current = true` |
| Top players (70) con WR | <200ms | Materialized view, refresh daily |
| Storico 30gg per deck | <100ms | `daily_snapshots` + indice data |
| Login utente | <50ms | Indice email, bcrypt in-memory |
| Import 1 match | <5ms | Prepared statement, batch commit |

### 5.5 Import Iniziale

```bash
# Fase 1: import bulk 64K match JSON -> PostgreSQL
python scripts/import_matches.py --source /mnt/HC_Volume_104764377/finanza/Lor/matches/
# Stima: ~10 min per 64K file (batch insert 1000/commit)

# Fase 2: migra killer curves
python scripts/migrate_killer_curves.py --source analisidef/output/

# Fase 3: migra history
python scripts/migrate_history.py --source analisidef/daily/output/history.db

# Fase 4: verifica
python scripts/benchmark_queries.py
```

---

## 6. Scalabilita'

### 6.1 Capacity del VPS attuale (2 vCPU, 4GB RAM)

| Metrica | Valore | Collo di bottiglia |
|---------|--------|-------------------|
| Richieste API concorrenti | ~100-150 | CPU (4 uvicorn worker) |
| Utenti registrati | Migliaia | Solo spazio disco |
| Utenti attivi simultanei | ~50-80 | RAM (PostgreSQL + Redis + uvicorn) |
| Query PostgreSQL/sec | ~500-1000 | Con indici e cache |
| Tempo risposta medio | <100ms | Cache hit ~5ms, DB ~50ms |

50-80 simultanei = ~200-500 utenti attivi giornalieri = ~1000-2000 registrati.
Per un prodotto Lorcana di nicchia, sufficiente per mesi.

### 6.2 Upgrade Path

```
Fase 1: Stesso VPS, upgrade RAM (sufficiente fino a ~200 utenti simultanei)
┌────────────────────────────────────────┐
│  CX31: 2 vCPU, 8GB RAM — 9 EUR/mese  │
│  Tutto sullo stesso server             │
└────────────────────────────────────────┘

Fase 2: Separa il DB (fino a ~500 utenti simultanei)
┌──────────────┐    ┌──────────────────────┐
│  VPS App     │───→│  PostgreSQL managed   │
│  CX21, 5€/m │    │  Hetzner, 15 EUR/m    │
└──────────────┘    └──────────────────────┘

Fase 3: Scala orizzontale (500+ simultanei, improbabile per Lorcana)
┌──────────┐
│  nginx   │──→ VPS App 1 (uvicorn)
│  load    │──→ VPS App 2 (uvicorn)  ──→ PostgreSQL managed
│ balancer │──→ VPS App 3 (uvicorn)      + Redis managed
└──────────┘
```

**Principio**: l'architettura non blocca la scala. Ogni pezzo e' separato — se il DB e' il collo, lo sposti. Se l'API non regge, aggiungi worker o nodi. nginx fa gia' load balancing nativo.

### 6.3 Bottleneck reale: pipeline, non API

Le richieste utente sono letture — veloci, cachate. Il pezzo pesante e' la pipeline notturna:

```
06:00  Import match (I/O disco + INSERT bulk)
07:00  Pipeline daily (query aggregate + materialized view refresh)
08:00  LLM worker (CPU + rete verso Claude API)
```

Gira di notte quando nessuno usa l'app. Se servisse, si sposta su un worker separato.

---

## 6.4 Pipeline dati — Bridge temporaneo da analisidef

La cartella `pipeline/` contiene una **copia statica** di tutti i moduli Python che generano i dati per la dashboard. Questi file vengono da `analisidef/` e sono sotto git solo come backup versionato.

**⚠️ STATO:** la produzione utenti gira in `App_tool`. `analisidef` resta solo come producer transitorio di alcuni output batch (matchup reports, killer curves). La copia in `pipeline/` non e' usata da App_tool a runtime.

### Flusso dati attuale (aggiornato 10 Apr 2026)

```
Match JSON (duels.ink)
  ↓
analisidef/daily/daily_routine.py       ← cron 07:01, orchestratore
  ├── lib/loader.py                     ← carica match da /matches/{DATE}/
  ├── lib/gen_archive.py                → archive_*.json (dettagli partite)
  ├── lib/gen_digest.py                 → digest_*.json (per LLM)
  ├── lib/gen_killer_curves.py          → playbook, threat curves
  ├── lib/gen_decklist.py               → card scores
  ├── lib/investigate.py                ← board state, loss classification
  └── assembla tutto in:
       ↓
  analisidef/daily/output/dashboard_data.json   (9 MB, dati completi)
       ↓
  scripts/import_matchup_reports.py             → PG matchup_reports

run_kc_production.sh (analisidef, batch LLM)
  ↓
  killer_curves_*.json
  ↓
  scripts/import_killer_curves.py               → PG killer_curves

/matches/*.json
  ↓
  scripts/import_matches.py                     → PG matches

PostgreSQL
  ↓
  App_tool/backend/api/dashboard.py             → GET /api/v1/dashboard-data
  App_tool/backend/services/snapshot_assembler.py → blob live da PG
  App_tool/backend/services/cache.py            → cache 2h + stale-while-revalidate
  ↓
  App_tool/frontend/dashboard.html              → fetch da API, NO dati embedded
```

### Mappa file pipeline/ (31 file, ~15K LOC)

| Cartella | File | LOC | Ruolo |
|----------|------|-----|-------|
| `daily/` | `daily_routine.py` | 3456 | Orchestratore: carica match, calcola tutto, produce dashboard_data.json |
| `daily/` | `history_db.py` | 615 | Storico: salva snapshot giornalieri in SQLite |
| `daily/` | `serve_dashboard.py` | 453 | Server HTTP vecchio (porta 8060) |
| `daily/` | `team_training.py` | 261 | Genera stats per team coaching |
| `daily/` | `backfill_history.py` | 127 | Riempimento retroattivo storico |
| `daily/` | `serve.py` | 14 | Server minimale |
| `lib/` | `loader.py` | 1096 | Caricamento e parsing match JSON |
| `lib/` | `investigate.py` | 779 | Board state, ink budget, classify_losses |
| `lib/` | `gen_archive.py` | 671 | Genera archive JSON con dettagli partite |
| `lib/` | `gen_killer_curves.py` | 613 | Playbook e threat curves |
| `lib/` | `gen_decklist.py` | 334 | Card scores per matchup |
| `lib/` | `build_replay_steps.py` | 813 | Ricostruzione passi replay |
| `lib/` | `i18n.py` | 418 | Internazionalizzazione stringhe |
| `lib/` | `validate_killer_curves.py` | 313 | Validazione meccanica KC |
| `lib/` | `validate_semantics.py` | 334 | Validazione semantica output |
| `lib/` | `gen_digest.py` | 211 | Digest compatto per input LLM |
| `lib/` | `gen_deck_actually.py` | 274 | Analisi "deck actually played" |
| `lib/` | `gen_review.py` | 197 | Review tattica |
| `lib/` | `gen_risposte.py` | 164 | Analisi risposte |
| `lib/` | `stats.py` | 169 | Calcoli statistici puri |
| `lib/` | `cards_dict.py` | 233 | DB 1511 carte normalizzate |
| `lib/` | `gen_curve_t1t7.py` | 218 | Curve mana turni 1-7 |
| `lib/` | `gen_validate.py` | 157 | Validazione output |
| `lib/` | `gen_mani.py` | 67 | Analisi mani iniziali |
| `lib/` | `gen_panoramica.py` | 57 | Panoramica matchup |
| `lib/` | `gen_all_turns.py` | 82 | Dump tutti i turni |
| `lib/` | `gen_killer_curves_draft.py` | 152 | KC versione draft |
| `lib/` | `validate.py` | 130 | Validazione generica |
| `lib/` | `formatting.py` | 51 | Display helpers |
| `lib/` | `assembler.py` | 47 | Assembla sezioni report |
| root | `generate_report.py` | 238 | Pipeline 5 fasi → report .md |
| root | `run_kc_production.py` | 235 | Killer curves batch |
| root | `build_replay.py` | 978 | Replay builder v1 |
| root | `build_replay_v2.py` | 137 | Replay builder v2 |
| root | `audit_replay.py` | 694 | Audit qualita' replay |

### Piano futuro

Quando App_tool sara' completamente indipendente da analisidef:
1. Gli analyzer necessari verranno portati in codice attivo dentro App_tool
2. I job saranno schedulati da worker/cron di App_tool, non da analisidef
3. L'output andra' direttamente in PostgreSQL, non piu' in `dashboard_data.json`
4. La cartella `pipeline/` restera' archivio/versioned snapshot oppure verra' rimossa
5. `analisidef` potra' restare solo come reference read-only, non come dipendenza operativa

---

## 7. Backend — FastAPI

### 7.1 API Endpoints

```
/api/v1/
│
├── auth/                            # ✅ IMPLEMENTATO 30/03/2026
│   ├── POST /register              # Email + password -> JWT + refresh    ✅
│   ├── POST /login                  # Email + password -> access + refresh ✅
│   ├── POST /logout                 # Revoca refresh_token                ✅
│   ├── POST /refresh                # refresh_token -> nuovi token        ✅
│   ├── GET  /me                     # Profilo utente corrente             ✅
│   ├── DELETE /me                   # GDPR: cancellazione account         ✅
│   ├── POST /forgot-password        # Invia email reset                   ⏳
│   └── POST /reset-password         # Token + nuova password              ⏳
│
├── promo/                           # ✅ IMPLEMENTATO 30/03/2026
│   ├── POST /create                 # [admin] Crea codice promo           ✅
│   ├── GET  /list                   # [admin] Lista codici attivi         ✅
│   ├── POST /deactivate/{code}      # [admin] Disattiva codice            ✅
│   └── POST /redeem                 # [auth] Utente riscatta codice       ✅
│
├── monitor/                         # ✅ IMPLEMENTATO — [auth: qualsiasi tier]
│   ├── GET /meta?game_format=core&days=2                                  ✅
│   ├── GET /deck/{code}?game_format=core&days=7                           ✅
│   ├── GET /matchup-matrix?game_format=core&days=7                        ✅
│   ├── GET /deck-fitness?game_format=core&days=7&min_games=15             ✅ (14/04)
│   ├── GET /winrates?game_format=core&days=2                              ✅
│   ├── GET /otp-otd?game_format=core&days=7                               ✅
│   ├── GET /trend?game_format=core&days=5                                 ✅
│   ├── GET /leaderboard?game_format=core&days=7&limit=100                 ✅
│   ├── GET /players/{deck}?game_format=core&days=7                        ✅
│   └── GET /tech-tornado?perimeter=set11&deck=AmAm                        ✅
│
├── coach/                           # ✅ IMPLEMENTATO — [auth: tier pro+]
│   ├── GET /matchup/{our}/{opp}?format=core&days=7                        ✅
│   ├── GET /killer-curves/{our}/{opp}?format=core                         ✅
│   ├── GET /threats/{our}/{opp}?format=core                               ✅
│   ├── GET /history/{our}/{opp}?format=core&days=30                       ✅
│   └── GET /playbook/{our}/{opp}?format=core                              ✅
│
├── lab/                             # ✅ IMPLEMENTATO — [auth: tier pro+, tranne iwd public]
│   ├── GET /card-scores/{our}/{opp}?format=core&days=7                    ✅
│   ├── GET /iwd/{our}/{opp}?format=core&days=14                           ✅ (14/04, public)
│   ├── GET /history?perimeter=full&days=30                                ✅
│   ├── GET /optimizer/{our}/{opp}?format=core                             ✅
│   └── GET /mulligans/{our}/{opp}?format=core                             ✅
│
├── user/                            # ✅ IMPLEMENTATO 01/04/2026 — [auth: qualsiasi tier]
│   ├── GET    /profile              # Profilo completo (nick, link esterni)  ✅
│   ├── PUT    /profile              # Aggiorna profilo                       ✅
│   ├── GET    /nicknames            # Leggi nickname linkati                 ✅
│   ├── PUT    /nicknames            # Associa nickname duels.ink / lorcanito ✅
│   ├── GET    /decks                                                         ✅
│   ├── POST   /decks               # Salva deck nel profilo                 ✅
│   ├── PUT    /decks/{id}           # Aggiorna deck                          ✅
│   ├── DELETE /decks/{id}                                                    ✅
│   ├── GET    /preferences                                                   ✅
│   ├── PUT    /preferences          # Lingua, notifiche, deck preferito     ✅
│   ├── GET    /my-stats?game_format=core&days=30  # Stats personali da nick ✅
│   └── GET    /export               # GDPR: esporta tutti i dati utente     ✅
│
├── community/                       # [auth] — Contenuti community       ⏳
│   ├── GET /videos                  # Lista video streamer + School of Lorcana
│   ├── POST /videos                 # [admin] Aggiungi video
│   ├── DELETE /videos/{id}          # [admin] Rimuovi video
│   ├── GET /tournaments             # Lista tornei (link a tcg.ravensburgerplay.com)
│   ├── POST /tournaments            # [admin] Aggiungi torneo
│   └── DELETE /tournaments/{id}     # [admin] Rimuovi torneo
│
├── team/                            # [TEAM tier only]                    ⏳
│   ├── GET /roster
│   ├── GET /player/{name}/stats
│   ├── GET /overview
│   └── GET /weaknesses
│
├── admin/                           # ✅ IMPLEMENTATO — [admin only, health pubblico]
│   ├── GET  /health                 # Pubblico (uptime monitors)          ✅
│   ├── GET  /metrics                # [admin]                             ✅
│   ├── POST /refresh-views          # [admin]                             ✅
│   └── GET  /logs?level=error&limit=100                                   ✅
│
├── subscription/                    # ✅ IMPLEMENTATO 02/04/2026
│   ├── POST /subscribe              # Crea Stripe Checkout Session         ✅
│   ├── GET  /subscription/status    # Stato abbonamento corrente           ✅
│   └── POST /subscription/cancel    # Cancella a fine periodo              ✅
│
├── community/                       # ✅ IMPLEMENTATO 02/04/2026
│   ├── GET  /videos                 # Lista video (pubblico)               ✅
│   ├── POST /videos                 # [admin] Aggiungi video               ✅
│   ├── DELETE /videos/{id}          # [admin] Rimuovi video                ✅
│   ├── GET  /tournaments            # Lista tornei (pubblico)              ✅
│   ├── POST /tournaments            # [admin] Aggiungi torneo              ✅
│   └── DELETE /tournaments/{id}     # [admin] Rimuovi torneo               ✅
│
└── webhooks/                        # ✅ IMPLEMENTATO 02/04/2026
    └── POST /stripe                 # Webhook Stripe (signature verificata) ✅
```

### 7.2 Stato Implementazione (aggiornato 02 Apr 2026)

```
IMPLEMENTATO:
  backend/services/auth_service.py    — bcrypt (cost 12), JWT HS256, refresh token rotation,
                                         password reset (create_token + reset_password)
  backend/api/auth.py                 — register, login, logout, refresh, me, delete me,
                                         forgot-password, reset-password
  backend/deps.py                     — get_current_user, require_tier(), require_admin
  scripts/create_admin.py             — seed account admin + test
  backend/api/user.py                 — profile, nicknames, decks CRUD, preferences, my-stats, GDPR export
  backend/services/user_service.py    — business logic: deck validation, prefs whitelist, my-stats SQL, export
  backend/services/dashboard_bridge.py — bridge layer: reads dashboard_data.json for playbook,
                                         mulligans, optimizer, tech tornado (transitional → PostgreSQL)
  backend/services/cache.py           — Redis cache con fallback dict (TTL configurabile)
  backend/services/subscription_service.py — Stripe checkout, webhook handler, cancel, status
  backend/services/team_service.py    — player stats, team overview, weaknesses SQL
  backend/services/alerting.py        — Telegram bot notifiche (placeholder, serve TG_BOT_TOKEN)
  backend/middleware/rate_limit.py    — per-IP, per-tier rate limiting via Redis
  backend/api/community.py           — videos + tournaments CRUD (tabelle PostgreSQL)
  backend/api/subscription.py        — subscribe, status, cancel, webhook
  backend/api/coach.py +playbook     — GET /playbook/{our}/{opp} via dashboard_bridge
  backend/api/lab.py +optimizer,mulligans — GET /optimizer, /mulligans via dashboard_bridge
  backend/api/monitor.py +tech-tornado — GET /tech-tornado via dashboard_bridge
  backend/api/admin.py +logs          — GET /logs from audit_log table
  backend/api/team.py                 — replay upload/list/get, roster, player stats, overview, weaknesses
  backend/main.py                     — replay list/game pubblici letti da PG (`replay_archives`)
  backend/services/replay_archive_service.py — reader PG per replay viewer
  backend/services/kc_spy_service.py  — reader PG per dashboard KC Spy
  frontend/dashboard.html             — auth UI (login/register/logout), profile tab con save nicknames,
                                         country via API, pfRefreshAuthUser() per sync profilo.
                                         Dati via fetch('/api/v1/dashboard-data'), no embedded data.

  backend/workers/match_importer.py   — import nuovi match JSON → PostgreSQL, refresh views
  backend/workers/daily_pipeline.py   — orchestratore: import + refresh views
  backend/workers/backup_worker.py    — pg_dump + GPG encryption + cleanup

  schemas/                            — JSON Schema contratti API (monitor, coach, lab, user, killer_curves)
  schemas/validate.py                 — validatore generico contro schema

  frontend/sw.js                      — Service Worker PWA (cache-first static, network-first API)

  Testato: login → JWT → /me → profilo OK, nicknames save → API OK, my-stats → OK
  Tutti i nuovi endpoint verificati su /api/docs (Swagger)
  Token: access 15min, refresh 30gg con rotazione (old revocato, new emesso)
  Sessioni: hash SHA-256 in DB, revocabili, legate a IP/device

ACCOUNT TEST (tutti tier=team, accesso completo):
  admin@metamonitor.app  (admin=true)   password: admin123!
  free@metamonitor.app                  password: test1234
  pro@metamonitor.app                   password: test1234
  team@metamonitor.app                  password: test1234
  nuovo@metamonitor.app                 password: testtest1234

  NOTA: in fase di test tutti gli account sono team per vedere tutto.
  I tier verranno differenziati quando il paywall sara' attivo.

SERVIZI ESTERNI DA CONFIGURARE (.env):
  - STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_*  → per pagamenti
  - TG_BOT_TOKEN, TG_CHAT_ID                                  → per alerting Telegram
  - Storage Box SFTP credentials                               → per backup offsite

DA IMPLEMENTARE (frontend):
  - Collegare dashboard HTML ai nuovi endpoint API (community, subscription, team stats)
  - Registrare Service Worker in dashboard.html
  - Password blacklist (top 10K comuni)
```

### 7.3 Paywall (Tier Enforcement)

```python
# backend/deps.py
TIER_LEVEL = {"free": 0, "pro": 1, "team": 2, "admin": 3}

def require_tier(min_tier: str):
    def checker(user: User = Depends(get_current_user)):
        if TIER_LEVEL.get(user.tier, 0) < TIER_LEVEL[min_tier]:
            raise HTTPException(403, {"error": "upgrade_required", "required_tier": min_tier})
        return user
    return checker

# Uso:
@router.get("/killer-curves/{our}/{opp}")
def get_killer_curves(our: str, opp: str, user = Depends(require_tier("pro"))):
    ...
```

### 7.4 Promo Codes (implementato 30 Mar 2026)

```
Due tipi di codice promozionale:

1. TIER UPGRADE — accesso completo per X giorni
   Esempio: BETATEST2026 → tier team per 30 giorni, max 10 usi
   Dopo scadenza: l'utente torna al tier originale (via cron expire_upgrades)

2. DISCOUNT — sconto % sul pagamento Stripe
   Esempio: AMICO20 → 20% sconto per 3 mesi, max 50 usi
   Si applica al checkout Stripe (da implementare con coupon Stripe)

Tabelle: promo_codes, promo_redemptions
Endpoint:
  POST /api/v1/promo/create     [admin]  — crea codice
  GET  /api/v1/promo/list        [admin]  — lista codici attivi
  POST /api/v1/promo/deactivate/{code} [admin] — disattiva codice
  POST /api/v1/promo/redeem      [auth]   — utente riscatta codice

Protezioni:
  - Solo admin puo' creare/gestire codici
  - Ogni utente puo' riscattare un codice solo una volta
  - Max usi configurabile per codice
  - Scadenza codice configurabile
  - Scadenza upgrade con revert automatico al tier originale
```

### 7.5 Profile — Dati Utente e Stats Personali (implementato 01 Apr 2026)

Il tab Profile permette all'utente di associare il proprio nickname duels.ink, salvare deck personalizzati e visualizzare le proprie statistiche reali calcolate dai match in database.

**Principio architetturale:** zero nuove tabelle. Tutto usa `users.preferences` (JSONB), `user_decks` (tabella esistente) e query su `matches`.

#### 7.5.1 Preferences JSONB — Schema campi

`users.preferences` e' un campo JSONB gia' presente in tabella. Il Profile lo usa per persistere le impostazioni personali senza migrazioni.

```json
{
  "duels_nick": "CLOUD",
  "lorcanito_nick": "cloud_lor",
  "country": "IT",
  "deck_pins": ["ESt", "AmySt", "AbSt"],
  "active_deck": "ESt",
  "notifications": {
    "meta_shift": true,
    "daily_report": false
  }
}
```

| Campo | Tipo | Validazione | Usato da |
|-------|------|-------------|----------|
| `duels_nick` | string, max 50 | Sanitizzato, lowercase per lookup | My Stats, Coach sync |
| `lorcanito_nick` | string, max 50 | Opzionale | Link esterno |
| `country` | string, 2 char ISO | Enum paesi supportati | Visualizzazione profilo |
| `deck_pins` | array string, max 3 | Ogni elemento in `VALID_DECK_CODES` | Quick select, Coach/Lab sync |
| `active_deck` | string | In `VALID_DECK_CODES` | Contesto attivo per Coach/Monitor |
| `notifications` | object | Chiavi predefinite | Futuro: email digest |

**Endpoint:**
```
PATCH /api/v1/user/preferences
  Body: { "duels_nick": "CLOUD", "country": "IT" }
  Merge: server fa JSON merge (non sovrascrive tutto), valida ogni campo
  Auth: JWT required, qualsiasi tier
  Response: 200 { preferences: {...} }
```

#### 7.5.2 My Stats — Query per nickname

Quando l'utente imposta `duels_nick`, il backend cerca le sue partite nella tabella `matches`. Il lookup e' server-side (non client-side come in analisidef) per sicurezza e performance.

**Query principale — WR per deck giocato:**
```sql
SELECT
  CASE WHEN lower(player_a_name) = :nick THEN deck_a ELSE deck_b END AS my_deck,
  COUNT(*) AS games,
  SUM(CASE
    WHEN lower(player_a_name) = :nick AND winner = 'deck_a' THEN 1
    WHEN lower(player_b_name) = :nick AND winner = 'deck_b' THEN 1
    ELSE 0
  END) AS wins
FROM matches
WHERE (lower(player_a_name) = :nick OR lower(player_b_name) = :nick)
  AND played_at >= now() - INTERVAL :days || ' days'
  AND game_format = :format
GROUP BY my_deck
ORDER BY games DESC;
```

**Query matchup breakdown (per deck selezionato):**
```sql
SELECT
  CASE WHEN lower(player_a_name) = :nick THEN deck_b ELSE deck_a END AS vs_deck,
  COUNT(*) AS games,
  SUM(CASE
    WHEN lower(player_a_name) = :nick AND winner = 'deck_a' THEN 1
    WHEN lower(player_b_name) = :nick AND winner = 'deck_b' THEN 1
    ELSE 0
  END) AS wins,
  -- OTP/OTD split (il primo turno e' deducibile da turns JSONB)
  COUNT(*) FILTER (WHERE total_turns IS NOT NULL) AS with_turns
FROM matches
WHERE (lower(player_a_name) = :nick OR lower(player_b_name) = :nick)
  AND CASE WHEN lower(player_a_name) = :nick THEN deck_a ELSE deck_b END = :my_deck
  AND played_at >= now() - INTERVAL :days || ' days'
  AND game_format = :format
GROUP BY vs_deck
ORDER BY games DESC;
```

**Query trend WR giornaliero (chart 30gg):**
```sql
SELECT
  played_at::date AS day,
  COUNT(*) AS games,
  SUM(CASE
    WHEN lower(player_a_name) = :nick AND winner = 'deck_a' THEN 1
    WHEN lower(player_b_name) = :nick AND winner = 'deck_b' THEN 1
    ELSE 0
  END) AS wins
FROM matches
WHERE (lower(player_a_name) = :nick OR lower(player_b_name) = :nick)
  AND played_at >= now() - INTERVAL '30 days'
  AND game_format = :format
GROUP BY day
ORDER BY day;
```

**Performance:** con gli indici esistenti su `player_a_name`, `player_b_name`, `played_at` e `game_format`, queste query girano in <100ms anche su 64K+ match.

**Indici consigliati (futuri, se serve):**
```sql
-- Solo se le query my-stats diventano lente (improbabile sotto 200K match)
CREATE INDEX idx_matches_player_a_lower ON matches(lower(player_a_name));
CREATE INDEX idx_matches_player_b_lower ON matches(lower(player_b_name));
```

**Endpoint:**
```
GET /api/v1/user/my-stats?format=core&days=30
  Auth: JWT required, tier free (KPI base) / pro (matchup breakdown + trend)
  Il nick viene da users.preferences.duels_nick (server-side, non dal client)
  Response: {
    nick: "CLOUD",
    data_range: { from: "2026-03-01", to: "2026-03-30" },
    decks: [
      { deck: "ESt", games: 47, wins: 28, wr: 59.6, mmr_avg: 1380,
        best_mu: { vs: "AmAm", wr: 72.0 },
        worst_mu: { vs: "AbSt", wr: 38.0 } }
    ],
    matchups: { ... },     // solo tier pro+
    daily_trend: [ ... ]   // solo tier pro+
  }
```

**⚠️ NOTA CRITICA — Identita' player duels.ink (01/04/2026):**

duels.ink non fornisce un player ID univoco nei log — solo `name` + `mmr`.
Problemi noti:
1. **Nickname duplicabili**: due player diversi possono avere lo stesso nick
2. **Nickname mutabili**: un player puo' cambiare nick in qualsiasi momento
3. **Nessun ID stabile** nei match JSON (`game_info.player1` ha solo name/mmr)

Impatto sul Profile tab:
- My Stats cerca per `lower(player_a_name)` — se il nick e' duplicato, le stats mescolano due player
- Se l'utente cambia nick su duels.ink, deve aggiornarlo manualmente nel profilo
- Il filtro omonimi (±200 MMR via leaderboard) e' un workaround, non una soluzione

Impatto sull'auth:
- Il login usa username scelto dall'utente (NON il nick duels.ink)
- Il nick duels.ink e' solo un campo profilo per agganciare le stats
- Email opzionale (solo per reset password), criptata se presente

**TODO futuri (non bloccanti per MVP):**
- Se duels.ink esporra' un player ID stabile, usarlo come chiave di lookup
- Considerare verifica ownership nick (es. "gioca una partita con deck X per conferma")
- Aggiungere campo `mmr_range_hint` nel profilo per disambiguare omonimi manualmente

#### 7.5.3 Deck Salvati — CRUD su user_decks

La tabella `user_decks` e' gia' creata (migrazione 274c18df8c4a). Mancano solo le API route.

**Schema tabella (esistente):**
```sql
user_decks (
  id          UUID PRIMARY KEY,
  user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
  name        VARCHAR(100) NOT NULL,
  deck_code   VARCHAR(10) NOT NULL,     -- 'ESt', 'AmAm', etc.
  cards       JSONB NOT NULL,           -- {"Card Name": qty, ...}
  is_active   BOOLEAN DEFAULT true,
  created_at  TIMESTAMPTZ,
  updated_at  TIMESTAMPTZ
)
```

**Endpoint:**
```
GET    /api/v1/user/decks                    # Lista deck utente
POST   /api/v1/user/decks                    # Crea deck (name, deck_code, cards)
PUT    /api/v1/user/decks/{id}               # Aggiorna deck
DELETE /api/v1/user/decks/{id}               # Elimina deck
Auth: JWT required, qualsiasi tier
Limite: max 10 deck per utente (free), 30 (pro), 50 (team)
```

**Validazione server-side:**
- `deck_code` deve essere in `VALID_DECK_CODES`
- `cards` JSONB: ogni chiave deve esistere in cards_db, somma qty = 60, max 4 copie per carta
- I colori delle carte devono corrispondere al `deck_code` dichiarato
- `deck_code` viene sempre verificato server-side (non fidarsi del client che potrebbe mandare un codice sbagliato per carte custom)

**Differenza da analisidef:** in analisidef i deck erano salvati in un file JSON flat per "user" (basato sul nick, senza auth). In App_tool sono in PostgreSQL con FK a users.id, protetti da JWT. Il `deck_code` e' salvato nel record (non ricalcolato dai colori delle carte) per evitare errori di auto-detect con deck non standard.

#### 7.5.4 Flusso Profile → Coach/Monitor/Lab

Quando l'utente seleziona un deck nel Profile (dai pin o da "My Deck"), il frontend sincronizza lo stato con gli altri tab:

```
Profile                          Coach / Monitor / Lab
───────                          ─────────────────────
  pfSelectDeck("ESt")
    │
    ├─→ selectedDeck = "ESt"     coachOur = "ESt" (Coach matchup selector)
    ├─→ selectedInks = [E, St]   inkPicker aggiornato
    └─→ render()                 Se tab Coach attivo, ri-renderizza con nuovo deck
```

**Server-side:** il deck attivo e' salvato in `preferences.active_deck`. Quando l'utente riapre l'app, il frontend legge `GET /auth/me` → `preferences.active_deck` e ripristina lo stato.

**My Deck → Coach:** se l'utente ha un deck custom (60 carte salvate in `user_decks`), il Coach puo' mostrare il confronto "tua lista vs consensus meta" usando i dati dal record `user_decks.cards` incrociati con i dati di `archives.aggregates`.

#### 7.5.5 Implementazione — File modificati

```
IMPLEMENTATO (01 Apr 2026):
  backend/api/user.py              # Route handler: profile, nicknames, decks, preferences, my-stats, export
  backend/services/user_service.py # Business logic: CRUD deck, query my-stats (3 SQL), prefs whitelist+country
  frontend/dashboard.html          # Auth UI inline (login/register/logout), profile save via API,
                                     pfSaveNicknames(), pfSaveCountry(), pfRefreshAuthUser()
  frontend/assets/js/team_coaching.js # Team coaching replay/roster
  backend/main.py                  # Router user registrato
```

---

## 8. Sicurezza — 5 Livelli

### 8.1 Livello 1: Rete

```
- nginx: unico punto esposto a internet
- Firewall UFW: solo porte 80, 443, 22
- SSH: solo key authentication, no password, no root login
- PostgreSQL: listen su localhost only (127.0.0.1:5432)
- Redis: listen su localhost only (127.0.0.1:6379)
- Nessun servizio interno esposto all'esterno
```

### 8.2 Livello 2: Trasporto

```
- TLS 1.2+ obbligatorio (Let's Encrypt, auto-renewal certbot)
- HSTS header: forza HTTPS, il browser non prova mai HTTP
- HTTP :80 → redirect 301 a HTTPS :443
```

### 8.3 Livello 3: Autenticazione e Autorizzazione

```
AUTENTICAZIONE (chi sei):

  Password:
  - bcrypt cost 12 (~250ms per hash — resiste a brute force)
  - Minimo 8 caratteri
  - Controllata contro lista password comuni (top 10K)
  - Mai loggata, mai trasmessa in chiaro, mai salvata in plain text

  Token:
  - Access token JWT: 15 minuti durata, HS256, secret da env var (256 bit random)
  - Refresh token: 30 giorni durata, hashato in DB (user_sessions), revocabile
  - Il client manda: Authorization: Bearer <access_token>

  Flusso:
  1. POST /login → email + password → verifica bcrypt
  2. OK → ritorna access_token (15min) + refresh_token (30gg)
  3. Ogni richiesta: middleware verifica JWT → estrae user_id, tier, is_admin
  4. Token scaduto: POST /refresh con refresh_token → nuovo access_token
  5. Logout: revoca refresh_token in DB (revoked_at = now)

AUTORIZZAZIONE (cosa puoi fare):

  Tier enforcement:
  - free: monitor community, killer curves parziali, mulligan limitato
  - pro: tutti i perimetri, coach, lab, storico
  - team: tutto + team training + 5 account
  - admin: trigger pipeline, health, metrics, logs

  Data isolation:
  - user_id preso dal JWT server-side, MAI dal client
  - Ogni utente vede/modifica solo i SUOI dati
  - Admin: accesso a tutto
```

### 8.4 Livello 4: Rate Limiting

```
  Login:          5 tentativi / 15 minuti per IP
  API free tier:  100 richieste / minuto
  API pro tier:   500 richieste / minuto
  API team tier:  1000 richieste / minuto
  Webhook Stripe: nessun limit (IP whitelist)
```

### 8.5 Livello 5: Headers HTTP e Protezione Web

```
  Content-Security-Policy: default-src 'self'; script-src 'self'; img-src 'self' cards.duels.ink
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=()
  CORS: solo dominio proprio (lorcanamonitor.com)
  Cookie (se usati): Secure, HttpOnly, SameSite=Strict
  CSRF: non necessario con JWT Bearer (no cookie auth)
```

### 8.6 Attacchi Comuni — Difese

| Attacco | Difesa |
|---------|--------|
| Brute force login | Rate limit 5/15min per IP + bcrypt lento (250ms) |
| SQL injection | SQLAlchemy ORM (zero SQL raw) + Pydantic validation |
| XSS | CSP header + no innerHTML con dati utente |
| CSRF | JWT Bearer (non cookie-based) → CSRF non applicabile |
| Token theft | Access token 15min (vita breve) + refresh revocabile |
| Session hijacking | Refresh token hashato in DB, legato a IP/device |
| Privilege escalation | user_id dal JWT server-side, mai dal client |
| DDoS | nginx rate limit + Cloudflare free tier (futuro) |
| Stripe webhook spoofing | Verifica HMAC-SHA256 signature + IP whitelist |

### 8.6.1 Security findings da review (16 Apr 2026)

| # | Finding | Stato | File |
|---|---------|-------|------|
| S1 | SQL in health check usava f-string (non injection reale: whitelist interna) | ✅ FIXATO — query pre-compilate | `backend/api/admin.py` |
| S2 | Password reset token loggato in chiaro | ✅ FIXATO — log rimosso | `backend/api/auth.py` |
| S3 | CORS permissivo in produzione | ✅ GIA' FIXATO — `CORS_ALLOW_ORIGINS` da env | `backend/config.py` |
| S4 | Team API senza JWT (solo nginx basic auth) | NOTO — target post-login frontend | `backend/api/team.py` |
| S5 | Rate limiting fail-open se Redis down | ACCETTATO — documentato | `backend/middleware/rate_limit.py` |
| S6 | File upload validazione tipo insufficiente | LOW — solo `.gz/.replay` + nginx basic auth | `backend/api/team.py` |
| S7 | Error handler espone exception type name | LOW — non espone stack trace | `backend/middleware/error_handler.py` |

### 8.7 Sicurezza Operativa (Server Hardening)

I livelli 1-6 proteggono l'applicazione. Questa sezione protegge il **server stesso** e i **processi operativi**.

#### 8.7.1 Stato attuale vs target

| Area | OGGI (30 Mar 2026) | TARGET |
|------|-------------------|--------|
| Utente sistema | **root** per tutto | Utente dedicato `lorcana` (no root) |
| Firewall UFW | **inattivo** | Attivo: solo 80, 443, 22 |
| fail2ban | **non installato** | Attivo: ban IP dopo 5 tentativi SSH/login falliti |
| Aggiornamenti OS | unattended-upgrades attivo | OK — gia' a posto |
| Processi | uvicorn gira come root | systemd con `User=lorcana`, `NoNewPrivileges=true` |
| SSH | key auth (da verificare) | Disabilitare password auth + root login |

#### 8.7.2 Secrets Management

```
OGGI:
  .env su disco con password in chiaro (DATABASE_URL con password)
  .env correttamente in .gitignore (mai committato)
  Nessuna rotazione password

TARGET:
  Fase 1 (immediata):
  - Verificare che .env non sia MAI finito in un commit (git log --all -- .env)
  - Password PostgreSQL: cambiare da "lorcana_dev_2026" a random 32 char
  - JWT secret: generare con `openssl rand -hex 32`
  - Permessi file: chmod 600 .env (leggibile solo da owner)

  Fase 2 (quando servono secrets in piu'):
  - Stripe keys, webhook secrets
  - Separare .env.prod da .env.dev
  - Rotazione password ogni 6 mesi

  Regola: MAI password in codice, commit, log, o output. Solo in .env e in variabili ambiente.
```

#### 8.7.3 Monitoring & Alerting

```
OGGI:
  Nessun sistema di alerting
  Log sparsi in /var/log/lorcana-*.log
  Nessuno viene avvisato se il server va giu'

TARGET:
  Livello 1 — Health check (costo zero):
  - healthcheck.sh gia' in cron ogni 5min
  - Aggiungere: se fallisce → notifica (Telegram bot o email)
  - Monitorare: API up, PostgreSQL up, disco < 90%, RAM < 90%

  Livello 2 — Log strutturato:
  - Tutti i log in formato JSON (gia' previsto in logging_mw.py)
  - Log centralizzato in /var/log/lorcana/
  - Rotazione con logrotate (7gg retain, compressione)

  Livello 3 — Alerting sicurezza:
  - Login falliti > 10/ora → alert
  - Accesso SSH non riconosciuto → alert
  - File .env modificato → alert
  - Nuovi processi in ascolto su porte → alert

  Strumenti consigliati (gratis):
  - UptimeRobot free tier (5min check, alert email/Telegram)
  - Telegram bot per notifiche custom (webhook semplice)
```

#### 8.7.4 Incident Response

```
SE SOSPETTI UNA COMPROMISSIONE:

  1. CONTIENI
     - Blocca accesso SSH da IP sospetti: ufw deny from <IP>
     - Se grave: spegni nginx (systemctl stop nginx) → sito offline ma dati salvi

  2. ANALIZZA
     - auth.log: chi si e' collegato? → journalctl -u ssh --since "24h ago"
     - audit_log in DB: azioni sospette? → SELECT * FROM audit_log ORDER BY created_at DESC
     - Processi attivi: ps aux | grep -v root
     - File modificati di recente: find /var/www -mtime -1

  3. RECUPERA
     - Ruota TUTTE le password: PostgreSQL, JWT secret, Stripe keys
     - Revoca tutte le sessioni utente: UPDATE user_sessions SET revoked_at = now()
     - Ripristina da backup se necessario (vedi sezione 12)
     - Riattiva servizi uno alla volta, verifica log

  4. PREVIENI
     - Documenta cosa e' successo e come
     - Chiudi la falla trovata
     - Aggiungi monitoring per quel vettore
```

#### 8.7.5 Backup Encryption

```
OGGI:
  pg_dump in chiaro su disco locale
  Nessun backup offsite (Storage Box non ancora attivo)

TARGET:
  - pg_dump | gzip | gpg --symmetric → backup criptato
  - Password GPG separata, conservata offline (non su .env del server)
  - Upload su Hetzner Storage Box via SFTP
  - Verifica restore mensile (backup non testato = backup inesistente)
```

#### 8.7.6 Dependency Security

```
  Controllo vulnerabilita':
  - pip audit                         # Vulnerabilita' note nelle dipendenze Python
  - Eseguire prima di ogni deploy e settimanalmente (cron)

  Regole:
  - requirements.txt con versioni pinned (gia' fatto)
  - Aggiornare dipendenze mensilmente
  - Mai installare pacchetti da fonti non verificate
  - Preferire librerie con manutenzione attiva e auditing
```

#### 8.7.7 Git & Code Security

```
OGGI:
  .env in .gitignore → OK, non committato
  Repo GitHub privati (LorMonitor, LorAnalisi) → OK

  Verifiche da fare:
  - git log --all --diff-filter=A -- '*.env' '*.key' '*.pem'  → assicurarsi che
    nessun secret sia MAI stato committato (anche se poi rimosso, resta nella storia)
  - GitHub: abilitare Dependabot alerts (gratis, avvisa su vulnerabilita')
  - GitHub: abilitare branch protection su main (richiede PR per merge)

  Regole:
  - MAI committare: .env, chiavi private, certificati, token
  - Se un secret finisce in un commit per errore:
    1. Ruota il secret IMMEDIATAMENTE (il vecchio e' compromesso)
    2. Pulisci la storia git con git filter-repo
    3. Force push (unica volta in cui e' giustificato)
```

#### 8.7.8 Cloudflare (stato attuale)

```
OGGI:
  Cloudflare gestisce DNS per metamonitor.app
  Proxy: da verificare se attivo o solo DNS

TARGET:
  - Proxy attivo (arancione in dashboard): nasconde IP reale del server
  - SSL mode: Full (strict) — Cloudflare verifica il certificato Let's Encrypt
  - Bot Fight Mode: attivo (gratis, blocca bot malevoli)
  - Under Attack Mode: disponibile in caso di DDoS
  - WAF rules base: gratis, blocca pattern noti (SQLi, XSS nelle URL)
  - Rate limiting Cloudflare: 1 regola gratis, usarla per /api/v1/auth/login
```

#### 8.7.9 Checklist priorita'

```
URGENTE (fare subito, prima del lancio):
  [x] Attivare UFW (ufw enable, allow 80,443,22) — FATTO, porta 8889 Jupyter rimossa
  [x] Installare fail2ban — FATTO, SSH + nginx jails attivi, 15+ IP bannati
  [x] Cambiare password PostgreSQL da default — FATTO, 32-char hex
  [x] chmod 600 .env — FATTO
  [x] Rimuovere fallback insicuri da config.py — FATTO, fail-fast se .env mancante
  [ ] Verificare proxy Cloudflare attivo

IMPORTANTE (fare prima di utenti paganti):
  [x] Generare JWT secret sicuro — FATTO, 64-char hex
  [x] Rate limiting nginx + backend — FATTO, login 5/15min, API 100/min, Redis-backed
  [x] Rate limiting middleware FastAPI — FATTO, per-tier (free/pro/team)
  [ ] Creare utente lorcana, non girare come root
  [ ] Attivare backup criptato offsite (serve Storage Box Hetzner)
  [ ] Impostare alerting Telegram (serve TG_BOT_TOKEN)
  [ ] pip audit su dipendenze
  [ ] Branch protection su main (GitHub)

NICE TO HAVE (fare quando il prodotto funziona):
  [ ] Dependabot su GitHub
  [ ] Log strutturato JSON
  [ ] Audit security trimestrale
  [ ] Documentare incident response con contatti
```

---

## 9. Pagamenti — Stripe + Apple Pay + Google Pay

### 9.1 Metodi di pagamento (tutti via Stripe)

```
┌─────────────────────────────────────────────────┐
│           STRIPE CHECKOUT (hosted)               │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │  Carte   │  │  Apple   │  │  Google  │      │
│  │ Visa/MC/ │  │   Pay    │  │   Pay    │      │
│  │ Amex     │  │          │  │          │      │
│  └──────────┘  └──────────┘  └──────────┘      │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │  SEPA    │  │  iDEAL   │  │  Bancon- │      │
│  │  (EU DD) │  │   (NL)   │  │  tact    │      │
│  └──────────┘  └──────────┘  └──────────┘      │
│                                                  │
│  Apple Pay e Google Pay: abilitati con toggle   │
│  nel dashboard Stripe. Zero codice extra.       │
│  Su iPhone vedono Apple Pay, su Android Google.  │
└─────────────────────────────────────────────────┘
```

**PayPal**: integrazione separata (non via Stripe per subscription). NON prioritario alla Fase 1 — aggiungere solo se utenti lo richiedono. Complessita' doppia per ~10-15% del mercato.

### 9.2 Flusso Pagamento

```
1. Utente clicca "Upgrade to Pro"
   → Frontend: POST /api/v1/subscribe {tier: "pro"}

2. Backend:
   - Verifica utente loggato (JWT)
   - Crea Stripe Checkout Session:
     · price: STRIPE_PRICE_PRO_MONTHLY (12 EUR)
     · mode: "subscription"
     · payment_method_types: [card] (Apple/Google Pay inclusi)
     · success_url: /dashboard?upgraded=true
     · cancel_url: /pricing
     · customer_email: utente.email
   - Ritorna {checkout_url: "https://checkout.stripe.com/..."}

3. Frontend: redirect a Stripe Checkout (pagina hosted da Stripe)
   I dati della carta NON toccano MAI il nostro server (PCI compliant)

4. Utente paga (carta, Apple Pay, Google Pay, SEPA)

5. Stripe manda webhook: POST /webhooks/stripe
   - Backend verifica firma HMAC-SHA256 (STRIPE_WEBHOOK_SECRET)
   - Event checkout.session.completed:
     → Crea record subscription (status: active)
     → user.tier = 'pro'
     → Audit log: "subscription_created"

6. Redirect a success_url → utente vede dashboard Pro
```

### 9.3 Rinnovi e Cancellazioni

```
Rinnovo mensile automatico:
  - Stripe tenta il pagamento
  - Webhook invoice.paid → rinnova current_period_end
  - Webhook invoice.payment_failed → subscription.status = 'past_due'
  - Dopo 3 tentativi falliti → status = 'cancelled', user.tier = 'free'

Cancellazione volontaria:
  - Utente cancella dal profilo
  - Backend: subscription.cancel_at = fine periodo corrente
  - Accesso pro fino a scadenza, poi downgrade automatico

Webhook gestiti:
  - checkout.session.completed → attiva subscription
  - invoice.paid → rinnova
  - invoice.payment_failed → past_due
  - customer.subscription.deleted → tier = free
  - charge.refunded → log
```

### 9.4 Sicurezza Pagamenti

| Aspetto | Gestione |
|---------|---------|
| Dati carte | Mai sul nostro server. Stripe Checkout e' hosted. PCI DSS compliance automatica |
| Webhook auth | Signature HMAC-SHA256 verificata + IP whitelist nginx |
| Doppia verifica | Webhook + polling stripe.Subscription.retrieve() |
| Frode | Stripe Radar incluso (ML anti-frode, gratis) |
| SCA (EU PSD2) | Stripe gestisce 3D Secure automaticamente per carte EU |
| Refund | Via Stripe Dashboard o API. Webhook charge.refunded |

### 9.5 Fee Stripe

```
Carta EU:       1.5% + 0.25 EUR
Carta non-EU:   2.5% + 0.25 EUR
Apple/Google Pay: stessa fee (passa via Stripe)
SEPA Direct Debit: 0.35 EUR flat

Su 12 EUR/mese Pro:
  Carta EU: 0.43 EUR fee → incassi 11.57 EUR
  SEPA:     0.35 EUR fee → incassi 11.65 EUR
```

### 9.6 iOS App Store — In-App Purchase

Se l'app e' su App Store con contenuti digitali, Apple richiede IAP (30% fee, o 15% small business).

```
Strategia consigliata:

Fase 1: Solo PWA (no App Store)
  - PWA su iOS funziona (Add to Home Screen)
  - Zero fee Apple, zero review process
  - Pagamento via web (Stripe, 1.5%)

Fase 2: App Store con pagamento web-only
  - App iOS e' solo un viewer, login con credenziali web
  - Pagamento avviene su lorcanamonitor.com (non nell'app)
  - Apple non puo' forzare IAP se il pagamento e' esterno
  - MA: non puoi linkare al sito di pagamento dall'app

Fase 3: Dual pricing (se necessario)
  - Web: 12 EUR/mese (Stripe)
  - iOS: 15 EUR/mese (IAP, Apple prende 30%)
```

---

## 10. Privacy e GDPR

### 10.1 Dati Personali Raccolti

| Dato | Necessario | Conservazione | Base legale |
|------|-----------|---------------|-------------|
| Email | Si (login) | Fino a cancellazione account | Contratto |
| Password hash | Si (auth) | Fino a cancellazione account | Contratto |
| IP address (log) | Si (sicurezza) | 90 giorni, poi anonimizzato | Interesse legittimo |
| Stripe customer ID | Si (pagamento) | Fino a cancellazione + 10 anni fiscali | Obbligo legale |
| Preferenze utente | No (opzionale) | Fino a cancellazione account | Consenso |
| Deck salvati | No (opzionale) | Fino a cancellazione account | Contratto |

### 10.2 Diritti Utente (GDPR Art. 15-22)

| Diritto | Implementazione |
|---------|----------------|
| **Accesso** | `GET /api/v1/user/export` — dump JSON completo |
| **Rettifica** | `PUT /api/v1/user/preferences` + `PUT /decks/{id}` |
| **Cancellazione** | `DELETE /api/v1/auth/me` — soft delete, hard delete dopo 30gg |
| **Portabilita'** | Export JSON machine-readable (stesso endpoint accesso) |
| **Opposizione** | Unsubscribe email nel profilo |

### 10.3 Flusso Cancellazione Account

```
1. DELETE /api/v1/auth/me
   → user.deletion_requested_at = now()
   → user.is_active = false
   → revoca tutte le sessioni
   → email conferma: "Account schedulato per cancellazione in 30 giorni"

2. Dopo 30 giorni (worker):
   → DELETE CASCADE: user_decks, subscriptions, user_sessions, password_reset_tokens
   → Anonimizza audit_log: user_id = NULL
   → DELETE users WHERE id = ...
   → Log: "account_permanently_deleted"

3. Stripe:
   → Cancella subscription se attiva
   → Dati fiscali conservati 10 anni (obbligo legale)
```

### 10.4 Cosa NON loggare MAI

- Password (neanche hashate)
- JWT token completi
- Numeri carte (gestiti da Stripe, non toccano il server)
- Refresh token in chiaro
- Dati personali nel log applicativo (solo user_id UUID)

---

## 11. Dominio e Routing

### 11.1 DNS (Cloudflare free tier)

```
A     lorcanamonitor.com      → 157.180.46.188
A     www.lorcanamonitor.com  → 157.180.46.188
MX    lorcanamonitor.com      → mail provider (Resend/Postmark)
TXT   _dmarc                  → "v=DMARC1; p=quarantine"
TXT   @                       → "v=spf1 include:resend.com -all"
```

Cloudflare: gestione DNS + proxy opzionale (DDoS protection, CDN) + analytics gratis.

### 11.2 Routing nginx

```
https://lorcanamonitor.com/                → frontend static (index.html SPA)
https://lorcanamonitor.com/assets/*        → CSS, JS, immagini (cache 7gg)
https://lorcanamonitor.com/api/v1/*        → FastAPI reverse proxy
https://lorcanamonitor.com/health          → nginx diretto (200 OK, uptime check)
http://*                                   → redirect 301 → https://*
```

### 11.3 nginx Config

```nginx
upstream api {
    server 127.0.0.1:8000;
}

# Rate limit zones
limit_req_zone $binary_remote_addr zone=api:10m rate=100r/m;
limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;

server {
    listen 443 ssl http2;
    server_name lorcanamonitor.com www.lorcanamonitor.com;

    ssl_certificate /etc/letsencrypt/live/lorcanamonitor.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/lorcanamonitor.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "strict-origin" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;

    # Frontend statico
    location / {
        root /var/www/lorcana/frontend;
        try_files $uri $uri/ /index.html;

        location ~* \.(js|css|png|jpg|svg|woff2)$ {
            expires 7d;
            add_header Cache-Control "public, immutable";
        }
    }

    # API
    location /api/ {
        proxy_pass http://api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        limit_req zone=api burst=20 nodelay;
    }

    # Login: rate limit piu' aggressivo
    location /api/v1/auth/login {
        proxy_pass http://api;
        limit_req zone=login burst=3 nodelay;
    }

    # Webhook Stripe: IP whitelist, no rate limit
    location /api/v1/webhooks/stripe {
        proxy_pass http://api;
        allow 3.18.12.63;
        allow 3.130.192.163;
        deny all;
    }

    # Health check (no auth, no rate limit)
    location /health {
        proxy_pass http://api/api/v1/admin/health;
    }
}

# Redirect HTTP -> HTTPS
server {
    listen 80;
    server_name lorcanamonitor.com www.lorcanamonitor.com;
    return 301 https://lorcanamonitor.com$request_uri;
}
```

---

## 12. Backup, Recovery, Disaster Plan

### 12.1 Strategia Backup (3-2-1)

```
3 copie dei dati:
  1. PostgreSQL live (VPS Hetzner)
  2. Backup locale compresso (stesso VPS, volume separato)
  3. Backup remoto criptato (Hetzner Storage Box, ~3 EUR/mese)

2 supporti diversi:
  - SSD VPS (produzione)
  - HDD Storage Box (backup offsite)

1 copia offsite:
  - Storage Box in datacenter diverso dal VPS
```

### 12.2 Schedule

| Cosa | Frequenza | Retention | Dove |
|------|-----------|-----------|------|
| PostgreSQL full dump | Giornaliero 03:00 | 7 giorni rolling | Locale + offsite |
| PostgreSQL WAL archiving | Continuo | 48 ore | Locale |
| Match JSON originali | Immutabili | Permanente | Volume Hetzner |
| Codice + config | Ad ogni push | Completo | Git (GitHub/GitLab) |
| .env (secrets) | Ad ogni modifica | Volume + Storage Box | MAI su Git |
| Killer curves (storico) | In PostgreSQL | Tutte le versioni | (nel dump) |

### 12.3 Script Backup

```bash
#!/bin/bash
# db/backup.sh — systemd timer ogni giorno 03:00

set -euo pipefail

BACKUP_DIR="/mnt/HC_Volume_104764377/backups/lorcana"
REMOTE="u123456@u123456.your-storagebox.de"
DATE=$(date +%Y%m%d_%H%M)
RETAIN_DAYS=7

# 1. Dump PostgreSQL (formato custom, compresso)
pg_dump -Fc -Z6 lorcana > "${BACKUP_DIR}/pg_${DATE}.dump"

# 2. Cripta con GPG (AES-256)
gpg --batch --symmetric --cipher-algo AES256 \
    --passphrase-file /root/.backup_passphrase \
    "${BACKUP_DIR}/pg_${DATE}.dump"
rm "${BACKUP_DIR}/pg_${DATE}.dump"

# 3. Upload offsite
scp "${BACKUP_DIR}/pg_${DATE}.dump.gpg" "${REMOTE}:lorcana/"

# 4. Cleanup locale
find "${BACKUP_DIR}" -name "pg_*.dump.gpg" -mtime +${RETAIN_DAYS} -delete

# 5. Cleanup remoto
ssh "${REMOTE}" "find lorcana/ -name 'pg_*.dump.gpg' -mtime +${RETAIN_DAYS} -delete"

# 6. Log + alert se errore
echo "[$(date)] Backup OK: pg_${DATE}.dump.gpg" >> /var/log/lorcana/backup.log
```

### 12.4 Disaster Recovery — 5 Scenari

**Scenario 1: Processo crasha (FastAPI, worker, nginx)**
```
Difesa:    systemd Restart=always, RestartSec=5
Recovery:  Automatico in 5 secondi
Downtime:  5 secondi
Dati persi: Zero
```

**Scenario 2: PostgreSQL crasha**
```
Difesa:    WAL (Write-Ahead Log) garantisce consistency
Recovery:  systemd riavvia PostgreSQL, WAL replay automatico
Downtime:  10-30 secondi
Dati persi: Zero (WAL e' il journal)
```

**Scenario 3: Disco corrotto (dati PostgreSQL persi)**
```
Difesa:    Backup giornaliero (pg_dump) locale + offsite
Recovery:
  1. Stop servizi
  2. pg_restore dall'ultimo dump locale
     Se corrotto: scarica da Storage Box offsite
  3. Replay WAL se disponibili (point-in-time recovery)
  4. Restart servizi
Downtime:  15-30 minuti
Dati persi: Max 24 ore (tra un backup e l'altro)
Mitigazione: WAL archiving continuo riduce a ~minuti
```

**Scenario 4: VPS completamente morto**
```
Difesa:
  - Volume Hetzner indipendente dal VPS (sopravvive)
  - Backup offsite su Storage Box
  - Codice su Git
Recovery:
  1. Crea nuovo VPS Hetzner (stessa region per montare il volume)
  2. Monta il volume (match JSON e backup locali gia' li')
  3. apt install postgresql nginx redis python3
  4. git clone → /opt/lorcana
  5. Restore .env da backup sicuro
  6. pg_restore dal dump su Storage Box
  7. certbot certonly (nuovo certificato SSL)
  8. systemctl start lorcana-api lorcana-worker
  9. Aggiorna DNS (nuovo IP, propaga in <5 min con Cloudflare TTL basso)
Downtime:  30-60 minuti
Dati persi: Max 24 ore
```

**Scenario 5: Datacenter Hetzner down (catastrofico)**
```
Difesa:
  - Storage Box in datacenter diverso
  - Git repo esterno (GitHub/GitLab)
Recovery:
  1. Provisiona VPS in altro datacenter Hetzner (o altro cloud)
  2. Restore tutto da Storage Box + Git
  3. Rigenera SSL, aggiorna DNS
Downtime:  1-2 ore
Probabilita': Bassissima (Hetzner SLA 99.9%)
```

### 12.5 Test Backup Mensile

```bash
# Cron primo lunedi del mese: test restore su DB temporaneo
createdb lorcana_test_restore
pg_restore -d lorcana_test_restore /mnt/HC_Volume_104764377/backups/lorcana/pg_LATEST.dump
# Se fallisce: alert Telegram
dropdb lorcana_test_restore
```

---

## 13. Logging e Monitoring

### 13.1 3 Tipi di Log

**Request log** (ogni richiesta API → `/var/log/lorcana/api.log`):
```json
{
    "ts": "2026-03-27T07:01:23Z",
    "level": "INFO",
    "method": "GET",
    "path": "/api/v1/coach/killer-curves/AmAm/ES",
    "status": 200,
    "duration_ms": 45,
    "user_id": "uuid-...",
    "tier": "pro",
    "ip": "1.2.3.4"
}
```

**Audit log** (eventi sensibili → tabella `audit_log` in DB):
- login, login_failed, logout
- password_change, password_reset
- subscription_created, subscription_cancelled
- account_delete_requested, account_permanently_deleted
- admin_action (refresh pipeline, etc.)
- Conservato 1 anno

**Security log** (anomalie → alert Telegram immediato):
- Rate limit superato
- JWT invalid/expired/tampered
- Tier violation (free prova ad accedere a pro)
- Stripe webhook signature invalida
- Login falliti ripetuti (>5 dallo stesso IP)

### 13.2 Livelli

| Livello | Cosa | Esempio |
|---------|------|---------|
| ERROR | Blocca la richiesta | DB connection failed, Stripe webhook invalido |
| WARN | Anomalia non bloccante | Rate limit vicino, LLM timeout, disk 80% |
| INFO | Operazione normale | Request completata, pipeline OK, backup OK |
| DEBUG | Troubleshooting (solo dev) | Query SQL, token decoded, cache hit/miss |

### 13.3 Log Rotation

```
/var/log/lorcana/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

### 13.4 Health Check

```python
# GET /api/v1/admin/health
{
    "status": "healthy",        # healthy, degraded, down
    "checks": {
        "database":    {"status": "ok", "latency_ms": 2},
        "redis":       {"status": "ok", "latency_ms": 1},
        "disk_free_gb": 59,
        "memory_used_pct": 43,
        "last_daily_pipeline": "2026-03-27T07:01:00Z",
        "last_backup": "2026-03-27T03:00:00Z",
        "match_count": 64347,
        "active_users": 42,
        "uptime_seconds": 86400
    }
}
```

### 13.5 Alerting (Telegram)

```bash
# infra/monitoring/uptime.sh — cron ogni 5 minuti

HEALTH=$(curl -sf http://localhost:8000/api/v1/admin/health)
STATUS=$(echo "$HEALTH" | jq -r '.status')

if [ "$STATUS" != "healthy" ]; then
    curl -X POST "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
        -d "chat_id=${TG_CHAT}" \
        -d "text=Lorcana Monitor: status=${STATUS}"
fi

# Alert disco <5GB
DISK_FREE=$(df --output=avail /mnt/HC_Volume_104764377 | tail -1)
if [ "$DISK_FREE" -lt 5242880 ]; then
    curl -X POST "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
        -d "chat_id=${TG_CHAT}" -d "text=Disco quasi pieno: ${DISK_FREE}KB"
fi
```

---

## 14. Performance Optimization

### 14.1 Da 22s a <100ms per Matchup

| Oggi | Domani | Speedup |
|------|--------|---------|
| Scan 64K file JSON da disco | Query PostgreSQL con indice composto | **200x** |
| Parse JSON in Python per ogni file | Dati strutturati in colonne + JSONB | **50x** |
| Ricalcola WR ad ogni request | Materialized view, refresh 1x/giorno | **Istantaneo** |
| Dashboard_data.json 4MB embedded | API per tab, dati on-demand | **10x meno banda** |

### 14.2 Caching (Redis)

```
Redis (in-memory, ~50MB):

  cache:monitor:{perimeter}:{format}       TTL: 1 ora
  cache:coach:{our}:{opp}:{format}         TTL: 6 ore
  cache:lab:{our}:{opp}:{format}           TTL: 6 ore
  cache:leaderboard:{queue}                TTL: 30 minuti

Invalidazione:
  Dopo pipeline daily: delete pattern cache:monitor:*
  Dopo LLM worker: delete cache:coach:{matchup aggiornato}
  Dopo admin refresh: delete specifico

Fallback: se Redis down, query diretta PostgreSQL (piu' lento, funziona)
```

### 14.3 Compressione e CDN

- **nginx gzip**: HTML, JSON, JS, CSS
- **Brotli** (opzionale): 15-25% meglio di gzip su JSON
- **CDN (futuro)**: Cloudflare free tier per static assets + DDoS protection
- **Immagini carte**: proxy cache da cards.duels.ink, nginx 30gg cache

---

## 15. Frontend — PWA + Mobile

### 15.1 PWA (Fase 1)

Il dashboard attuale diventa Progressive Web App:
- `manifest.json` per "Add to Home Screen" su iOS/Android
- `sw.js` Service Worker per cache offline
- Tutte le richieste via `fetch('/api/v1/...')` con Bearer token
- Responsive gia' fatto (viewport, safe area, touch target 44px)

**Cache strategy (Service Worker):**
```
Assets statici (CSS, JS, chart.min.js): Cache First, 7gg
API data (monitor, coach, lab): Network First, fallback su cache
Immagini carte (cards.duels.ink): Cache First, 30gg
Auth endpoints: Network Only (mai cachati)
```

### 15.2 iOS Nativo (Fase 2 — Capacitor)

Stesso codice web wrappato con Capacitor per App Store:
- Push notification native (nuove killer curves, meta shift)
- Touch ID / Face ID per login
- Badge icona con alert non letti
- Stesso backend, stessa API

```bash
# Build
npm install @capacitor/core @capacitor/ios
npx cap add ios
npx cap sync ios
# → Apri Xcode, build, submit
```

**Perche' Capacitor e non React Native:**
- Zero rewrite (il frontend e' gia' HTML/JS)
- 1 codebase per web + iOS + Android
- Plugin nativi (push, biometrics) senza riscrivere

### 15.3 Replay Viewers — Due viewer distinti

Il frontend ha **due** viewer replay, con fonti dati e livelli di dettaglio diversi.
Facile confonderli: vivono entrambi nell'area "coach/lab".

| Aspetto            | `rv*` (Lab-tab inline)                              | `tc*` (Team Coaching)                              |
|--------------------|-----------------------------------------------------|----------------------------------------------------|
| File               | `frontend/dashboard.html` (~L6159+)                 | `frontend/assets/js/team_coaching.js`              |
| Data source        | `td.event_log` dai match scrapati (duels.ink)       | Upload `.gz` → `backend/services/replay_service.py`|
| Parser             | `rvBuildSteps` in JS (port di `build_game_steps.py`)| Patch `.gz` estratti con `singer`/`target`/`damage`|
| Hand cards         | count only (o 'partial'/'full' se `.gz` abbinato)   | piena: `snap.hand` da patch                        |
| Carte DB           | `rvCardsDB` via `/api/replay/cards_db`              | cache locale `tcCardsDB` via `/api/replay/cards_db`|
| Match coperti      | tutti i ~21K match importati                        | solo quelli caricati dal team via `.gz`            |
| Coverage eventi    | play/ink/quest/challenge/damage/destroyed/bounce    | + spell overlay, combat arrows, damage transfer   |
| Animation model    | diff-based highlight (pop-in + stagger, no DOM persist) | DOM-persistent, death anim, hand-out→swap→draw-in |

**Perche' due viewer.** L'`rv*` lavora su qualunque match dei 21K (no `.gz` disponibile),
quindi resta inevitabilmente limitato alla granularita' del log parsato.
Il `tc*` sfrutta le patch complete del file `.gz` uploadato: puo' mostrare spell overlay,
damage transfer, hand piena turn-by-turn. Convergerli significherebbe imporre
l'upload `.gz` su tutti i 21K match → non fattibile per storage.

**Animazioni (stato 13 Apr 2026).**
- `tc*`: pipeline sequenziata (`tcApplySnap`) — commit `41428bf` label da patch, `b98dbbb`
  sequenziamento hand-out → board swap → draw-in stagger.
- `rv*`: refactor "Option A light" — diff-based `rv-mc-new` (pop-in), `rv-hc-new` stagger
  su hand card, counter flash su cambio, pause variabile in `rvTick`
  (ink/draw quieti 0.55x, play/challenge pieni). Niente DOM persist: rerender innerHTML
  con classi di animazione selettive.

Per un eventuale "Option B" (parita' piena con `tc*`) serve: diff DOM persistente,
death animation, spell overlay — ~250+ righe JS, da valutare solo se il feel Option A
non regge sui match lunghi.

**Coupling aggiornato (aprile 2026).** `team_coaching.js` non usa piu' helper/globali del replay viewer pubblico (`rvCardsDB`, `rvCardImg`, `RV_IC`, `rvSn`, `currentUser`) per la parte core replay. Restano deliberate solo:
- API App_tool (`/api/replay/cards_db`, `/api/v1/team/replay/*`, `/api/decks`)
- `localStorage` browser per auth/deck context

---

## 16. Pipeline e Workers

### 16.1 Schedule

| Ora | Worker | Cosa fa |
|-----|--------|---------|
| 03:00 | `backup_worker.py` | pg_dump + GPG + upload offsite |
| 06:00 | `match_importer.py` | Importa nuovi JSON match → PostgreSQL |
| 06:30 | `match_importer.py` | Refresh materialized views |
| 07:00 | `daily_pipeline.py` | Genera dati Monitor |
| 07:01 | `daily_pipeline.py` | Raccoglie killer curves, parsa threats |
| Lunedi 08:00 | `weekly_pipeline.py` | Genera dati Coach + Lab |

### 16.2 LLM Worker (Claude API)

```
Oggi (analisidef):
  claude -p "..." --model sonnet < digest.json > killer_curves.json
  Seriale, 1 alla volta, ~3 ore per 50 matchup

Domani (App_tool):
  Claude API Batch (50% sconto, asincrono)
  + Prompt Caching (cards_db + system prompt cachati, 90% risparmio input)
  = ~6 EUR/mese per 50 matchup/notte
```

### 16.3 Resilienza

| Failure | Recovery |
|---------|----------|
| Import match interrotto | `external_id UNIQUE` → ON CONFLICT DO NOTHING → riparte |
| Pipeline daily fallisce | systemd Restart=always. Dati vecchi restano serviti |
| LLM timeout | Retry con backoff. Killer curves vecchie restano current |
| Backup fallisce | Alert Telegram. Volume Hetzner persistente |
| PostgreSQL down | systemd riavvia. WAL recovery automatico |
| Redis down | Fallback a PostgreSQL diretto |
| Disco pieno | Alert a 5GB. Match JSON vecchi archivabili |

---

## 17. Workflow Dev/Prod e Deploy

### 17.1 Git

```
Repository: github.com/user/lorcana-monitor (privato)

Branches:
  main          → produzione (deployed sul VPS)
  develop       → sviluppo
  feature/*     → feature branch (da develop)
  hotfix/*      → fix urgenti (da main, merge in main + develop)
```

### 17.2 Ambienti

```
DEV (stesso VPS o locale):
  - uvicorn --reload --port 8001
  - PostgreSQL database "lorcana_dev"
  - Redis database 1
  - .env.dev: APP_ENV=development, LOG_LEVEL=DEBUG
  - Stripe test mode (sk_test_..., carte fake 4242...)

PROD (VPS Hetzner):
  - uvicorn via systemd, 4 worker, porta 8000
  - PostgreSQL database "lorcana"
  - Redis database 0
  - .env: APP_ENV=production, LOG_LEVEL=INFO
  - Stripe live mode (sk_live_...)
  - nginx :443 davanti
```

### 17.3 Deploy Zero-Downtime

```bash
#!/bin/bash
# scripts/deploy.sh

set -euo pipefail
LOG="/var/log/lorcana/deploy.log"
echo "[$(date)] Deploy started" >> "$LOG"

cd /opt/lorcana

# 1. Pull codice
git fetch origin main
git reset --hard origin/main

# 2. Dipendenze (solo se cambiate)
if git diff HEAD~1 --name-only | grep -q "requirements.txt"; then
    venv/bin/pip install -r requirements.txt >> "$LOG" 2>&1
fi

# 3. Migra database
venv/bin/alembic upgrade head >> "$LOG" 2>&1

# 4. Validazione schema
venv/bin/python -m schemas.validate >> "$LOG" 2>&1

# 5. Reload graceful (zero downtime)
#    SIGHUP → uvicorn ricarica i worker uno alla volta
#    Worker attivi finiscono le richieste, poi si riavviano col codice nuovo
systemctl reload lorcana-api

# 6. Verifica health
sleep 2
STATUS=$(curl -sf http://localhost:8000/api/v1/admin/health | jq -r '.status')
if [ "$STATUS" = "healthy" ]; then
    echo "[$(date)] Deploy OK" >> "$LOG"
else
    echo "[$(date)] Deploy WARN: health=$STATUS" >> "$LOG"
    # Alert Telegram
    curl -sf -X POST "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
        -d "chat_id=${TG_CHAT}" -d "text=Deploy: health=$STATUS"
fi
```

**Perche' e' zero-downtime:** `systemctl reload` (non restart) invia SIGHUP a uvicorn. I worker attivi finiscono le richieste in corso, poi ripartono col codice nuovo. In ogni momento almeno 1-2 worker sono attivi.

### 17.4 Rollback

```bash
# Rollback codice (immediato, <10 secondi)
ssh vps 'cd /opt/lorcana && git reset --hard HEAD~1 && systemctl reload lorcana-api'

# Rollback database migration
ssh vps 'cd /opt/lorcana && venv/bin/alembic downgrade -1'

# Rollback nucleare (restore da backup)
ssh vps 'pg_restore -d lorcana --clean /mnt/HC_Volume/backups/pg_LATEST.dump'
```

### 17.5 CI/CD (Fase 2, opzionale)

```
GitHub Actions (gratis, 2000 min/mese):
  push su main →
    1. pytest (PostgreSQL test in Docker)
    2. Se OK: SSH al VPS, esegue deploy.sh
    3. Se FAIL: notifica, non deploya

Per Fase 1: deploy manuale con deploy.sh e' sufficiente.
```

---

## 18. Infrastruttura Hetzner

### 18.1 Server Attuale

| Risorsa | Valore |
|---------|--------|
| OS | Ubuntu 24.04 LTS |
| CPU | 2 vCPU |
| RAM | 3.7 GB |
| Volume montato | 89 GB (30% usato, 59 GB liberi) |
| IP | 157.180.46.188 |

### 18.2 Layout Produzione

```
┌─────────────────────────────────────────────────────┐
│  Hetzner VPS                                         │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │  nginx   │  │ FastAPI  │  │ PostgreSQL│          │
│  │  :443    │→ │ :8000    │→ │ :5432     │          │
│  │  SSL/TLS │  │ 4 worker │  │           │          │
│  └──────────┘  └──────────┘  └──────────┘          │
│  ┌──────────┐  ┌──────────┐                         │
│  │  Redis   │  │ Workers  │                         │
│  │  :6379   │  │ cron +   │                         │
│  │          │  │ LLM      │                         │
│  └──────────┘  └──────────┘                         │
│                                                      │
│  Volume: /mnt/HC_Volume (89GB)                      │
│    - Match JSON originali (3GB, read-only)          │
│    - PostgreSQL data                                 │
│    - Backup locali                                   │
│                                                      │
│  Hetzner Storage Box (100GB, offsite, ~3 EUR/mese)  │
└─────────────────────────────────────────────────────┘
```

### 18.3 systemd Services

```ini
# lorcana-api.service
[Unit]
Description=Lorcana Monitor API
After=network.target postgresql.service redis.service

[Service]
Type=exec
User=lorcana
WorkingDirectory=/opt/lorcana/backend
EnvironmentFile=/opt/lorcana/.env
ExecStart=/opt/lorcana/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 4
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=5
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/var/log/lorcana /opt/lorcana/output

[Install]
WantedBy=multi-user.target
```

```ini
# lorcana-worker.service
[Unit]
Description=Lorcana Monitor Workers
After=network.target postgresql.service

[Service]
Type=exec
User=lorcana
WorkingDirectory=/opt/lorcana/backend
EnvironmentFile=/opt/lorcana/.env
ExecStart=/opt/lorcana/venv/bin/python -m workers.scheduler
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## 19. Variabili Ambiente (.env)

```bash
# Database
DATABASE_URL=postgresql://lorcana:STRONG_PASSWORD@localhost:5432/lorcana
DATABASE_URL_DEV=postgresql://lorcana:devpass@localhost:5432/lorcana_dev
REDIS_URL=redis://localhost:6379/0

# Auth
JWT_SECRET=<256-bit-random-hex>
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30

# Stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_PRO_MONTHLY=price_...
STRIPE_PRICE_TEAM_MONTHLY=price_...

# Claude API
ANTHROPIC_API_KEY=sk-ant-...

# Paths
MATCH_JSON_DIR=/mnt/HC_Volume_104764377/finanza/Lor/matches
CARDS_DB_PATH=/mnt/HC_Volume_104764377/finanza/Lor/cards_db.json
DECKS_DB_DIR=/mnt/HC_Volume_104764377/finanza/Lor/decks_db

# Backup
BACKUP_LOCAL_DIR=/mnt/HC_Volume_104764377/backups/lorcana
BACKUP_REMOTE=u123456@u123456.your-storagebox.de
BACKUP_GPG_PASSPHRASE_FILE=/root/.backup_passphrase

# Monitoring
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...

# App
APP_ENV=production
LOG_LEVEL=INFO
CORS_ORIGINS=https://lorcanamonitor.com
```

---

## 20. Dipendenze

```
# requirements.txt
fastapi>=0.115
uvicorn[standard]>=0.30
sqlalchemy>=2.0
alembic>=1.13
asyncpg>=0.30              # PostgreSQL async driver
psycopg2-binary>=2.9       # PostgreSQL sync (scripts)
redis>=5.0
pydantic>=2.0
python-jose[cryptography]  # JWT
passlib[bcrypt]             # Password hashing
stripe>=10.0
httpx>=0.27                 # Async HTTP (duels.ink, Claude API)
anthropic>=0.40             # Claude API SDK
python-multipart>=0.0.9    # Form data
structlog>=24.0             # Structured logging
apscheduler>=3.10           # Scheduler workers
```

---

## 21. Costi Produzione

| Voce | Mese 1-3 | Mese 6 | Mese 12 |
|------|----------|--------|---------|
| VPS Hetzner CX21 | 5 EUR | 5 EUR | 9 EUR (upgrade CX31) |
| Volume 100GB | 4 EUR | 4 EUR | 4 EUR |
| Storage Box 100GB (backup) | 3 EUR | 3 EUR | 3 EUR |
| Dominio (.com) | 1 EUR | 1 EUR | 1 EUR |
| SSL (Let's Encrypt) | 0 | 0 | 0 |
| Claude API (Batch + Cache) | 0* | 0* | 8 EUR |
| Stripe fees (1.5% + 0.25) | 5 EUR | 40 EUR | 130 EUR |
| Apple Developer (iOS) | 0** | 8 EUR | 8 EUR |
| Email (Resend) | 0 | 0 | 10 EUR |
| **Totale** | **~18 EUR** | **~61 EUR** | **~173 EUR** |

*Coperto da Anthropic Startup Program ($25K crediti)
**iOS solo da Fase 2

---

## 22. Rilascio — Piano Operativo

> **Nota**: App_tool e' un progetto nuovo costruito in parallelo. `analisidef/` resta invariata.
> Gli script di import leggono i dati da analisidef in sola lettura (copia, non migrazione).
>
> **Vincolo API**: al 27/03/2026 non c'e' un piano Anthropic API con credito attivo.
> Tutto cio' che richiede chiamate Claude API (generazione killer curves, threat analysis,
> review tattiche) e' rimandato. Il backend serve i dati LLM gia' generati da analisidef
> e importati nel DB. Quando sara' disponibile credito API si aggiungera' il worker LLM.

### Fase 0 — Preparazione ✅ completata 27/03/2026
- [x] PostgreSQL 16 installato e attivo su VPS
- [x] Redis 7 installato e attivo
- [x] DB `lorcana` creato con utente `lorcana_app`
- [x] Python 3.12 virtualenv con dipendenze (SQLAlchemy, Alembic, asyncpg, psycopg2, pydantic)
- [x] File progetto: `requirements.txt`, `.env.example`, `.env`, `.gitignore`
- [x] `backend/config.py` — settings centralizzati da `.env`
- [ ] Creare utente sistema `lorcana` (non root) — rimandato a deploy produzione
- [ ] Setup firewall UFW (80, 443, 22) — rimandato a deploy produzione

### Fase 1 — Database + Import ✅ completata 27/03/2026
- [x] 11 tabelle PostgreSQL via Alembic migration autogenerata dai modelli ORM:
  - Auth: `users`, `user_sessions`, `password_reset_tokens`
  - Subscriptions: `subscriptions`
  - User data: `user_decks`
  - Match data: `matches` (BIGSERIAL, JSONB turns, 7 indici incl. composto `idx_matches_lookup`)
  - Analisi: `killer_curves`, `archives`, `threats_llm`, `daily_snapshots`
  - Audit: `audit_log`
- [x] 2 materialized views: `mv_meta_share`, `mv_matchup_matrix`
- [x] 7 modelli SQLAlchemy ORM in `backend/models/`
- [x] 2 Alembic migrations (001_initial + 002_widen_perimeter)
- [x] `scripts/import_matches.py`: 2,317 match importati da `/mnt/.../matches/` (JSON → PostgreSQL, batch 1000, winner fix v2)
- [x] `scripts/import_killer_curves.py`: 128 killer_curves importate da `analisidef/output/`
- [x] `scripts/import_history.py`: 102 snapshot storici importati da `analisidef/daily/output/history.db` (SQLite → PostgreSQL)
- [x] `scripts/benchmark_queries.py` — 5/6 query sotto target:
  - Matchup singolo: 49ms (target <50ms) ✅
  - Matrice 12x12: 6ms (target <500ms) ✅
  - Killer curves: 2ms (target <10ms) ✅
  - Meta share: 4ms (target <200ms) ✅
  - Top players: 4ms (target <200ms) ✅
  - Snapshot (tutti): 1.5s (target <100ms) — OK con query filtrate per perimeter
- [ ] Backup automatico + test restore — da configurare

### Fase 2 — Backend API ✅ completata 27/03/2026
- [x] FastAPI scaffold + `backend/main.py` (entrypoint con CORS, error handler, router mount)
- [x] `backend/deps.py` — dependency injection (db session)
- [x] 4 service modules in `backend/services/`:
  - `stats_service.py` — WR, matrice matchup, meta share, OTP/OTD, trend giornaliero
  - `players_service.py` — top players, leaderboard MMR, player detail
  - `matchup_service.py` — dettaglio matchup, killer curves, threats, storico
  - `deck_service.py` — card scores, deck breakdown, history snapshots
- [x] 4 route modules in `backend/api/`:
  - `monitor.py` — 7 endpoint (meta, deck, matchup-matrix, otp-otd, trend, leaderboard, winrates)
  - `coach.py` — 4 endpoint (matchup detail, killer-curves, threats, history)
  - `lab.py` — 2 endpoint (card-scores, history snapshots)
  - `admin.py` — 3 endpoint (health, refresh-views, metrics)
- [x] `backend/middleware/error_handler.py` — global exception handler
- [x] CORS middleware configurato (permissive in dev)
- [x] Swagger UI attivo su `/api/docs`
- [x] Bug fix: corretto `determine_winner()` in import_matches.py (winner in `data.winner`, non `entry.winner`)
- [x] Re-import match: 2,317 match con winner corretto (1,154 deck_a / 1,076 deck_b / 87 draw)
- [x] Tutti 16 endpoint testati con curl — risposte corrette
- [ ] Test suite automatizzata — da aggiungere
- [ ] Deploy uvicorn + systemd — rimandato a infra produzione
- [ ] Rate limiting per-endpoint — rimandato a Fase 3 (con tier enforcement)

### Fase 3 — Frontend Ponte (dashboard identica via analisidef)

> **Strategia**: App_tool serve la stessa dashboard di analisidef, leggendo il
> `dashboard_data.json` gia' prodotto dalla daily routine. Zero riscrittura del motore.
> analisidef continua a girare e a calcolare tutto. App_tool si occupa solo di servire.

- [x] Endpoint `GET /api/v1/dashboard-data` — `backend/api/dashboard.py`, legge `analisidef/daily/output/dashboard_data.json`
- [x] Template `dashboard.html` copiato in `App_tool/frontend/`, `loadData()` modificato per fetch da `/api/v1/dashboard-data`
- [x] File statici copiati: `manifest.json`, `icon-192.svg`, `icon-512.svg`
- [x] Verificato: dashboard su App_tool identica a quella su porta 8060
- [x] systemd service `lorcana-api.service` — uvicorn 2 workers, auto-restart, boot-enabled
- [x] nginx reverse proxy (porta 80 → uvicorn 8100) con security headers, gzip, timeouts
- [x] Dominio `metamonitor.app` registrato su Cloudflare, DNS A record → 157.180.46.188
- [x] SSL Let's Encrypt configurato (certbot + auto-renewal), scadenza 25/06/2026
- [x] HTTP → HTTPS redirect automatico (301)
- [x] Password protection HTTP Basic (nginx) — rimuovere quando si apre al pubblico

### Stabilizzazione infrastruttura ✅ completata 27/03/2026
- [x] Git repo `ema299/LorMonitor` su GitHub (privato), primo commit 49 file
- [x] Symlink `frontend/dashboard.html` → analisidef (dashboard sempre aggiornata con le modifiche in analisidef)
- [x] Backup automatico DB: cron 03:00, `scripts/backup.sh` (pg_dump + gzip, retention 7gg, dir `/backups/lorcana/`)
- [x] Import match automatico: cron 06:30, `scripts/import_matches.py` (ON CONFLICT DO NOTHING, solo nuovi)
- [x] Import killer curves: cron mar 05:30, `scripts/import_killer_curves.py` (dopo batch generation analisidef)
- [x] Replay runtime decoupling: `replay_archives` + API replay da PG (sample import validato localmente)
- [x] KC Spy runtime decoupling: `kc_spy_reports` + assembler da PG (import corrente validato localmente)
- [x] `robots.txt` — blocca tutti i crawler (Disallow: /)
- [x] Health check: cron ogni 5 min, `scripts/healthcheck.sh` (auto-restart se API non risponde)
- [ ] Alerting Telegram — da aggiungere
- [ ] Load testing — da fare prima del lancio pubblico

**Cron schedule completo (App_tool, verificato 15 Apr 2026):**
```
*/5 * * * *   healthcheck.sh           → auto-restart se down
0   3 * * *   backup.sh                → pg_dump + gzip + cleanup 7gg
0 */2 * * *   import_matches.py        → importa nuovi match da /matches/
0   2 * * 0   maintenance.sh           → drop turns >90gg, VACUUM
45  4 * * 0   static_importer.py       → cards DB refresh (duels.ink)
5   4 * * *   import_kc_spy.py         → KC Spy JSON → PG kc_spy_reports
30  5 * * 2   import_killer_curves.py  → importa nuove curve dopo batch KC OpenAI
30  5 * * *   import_matchup_reports.py → importa matchup reports daily_routine → PG
35  5 * * *   assemble_snapshot.py     → warm-up cache blob
0   7 * * *   monitor_kc_freshness.py  → canary freshness, mail STALE/ERROR
0   1 * * 2   generate_playbooks.py    → playbook nativo App_tool
```

**Cron schedule analisidef (ancora attivo fino a P2/P3 cutover):**
```
0   0 * * 2   run_kc_production.sh     → genera killer curves (OpenAI batch)
0   4 * * *   kc_spy.py --format all   → daily canary KC + validation
30  4 * * *   decks_db_builder.py      → refresh decks DB
0   5 * * *   lorcana_monitor.py report
1   5 * * *   daily_routine.py         → genera dashboard_data.json
```

### Piano di transizione verso autonomia (futuro)

```
OGGI — Fase A (ponte):
  lorcana_monitor.py cattura match → /matches/
  analisidef daily_routine → dashboard_data.json (calcoli, 6.7K LOC in lib/)
  App_tool serve dashboard_data.json via API → frontend identico
  App_tool ha il suo DB PostgreSQL (88K match, 162 killer curves)
  Le due cose coesistono senza interferire.

DOMANI — Fase B (motore copiato):
  Copiare analisidef/lib/ (16 moduli) in App_tool/lib/
  Adattare per leggere da PostgreSQL invece che da file JSON
  Testare: stessi input → stessi output (confronto con analisidef)
  Non sostituisce analisidef, gira in parallelo per validazione.

DOPO — Fase C (autonomia):
  Attivare worker cron in App_tool (daily_pipeline, match_importer)
  Verificare output identico per N giorni
  Spegnere daily routine di analisidef
  App_tool diventa autonoma. lorcana_monitor.py resta attivo.

Rischi e mitigazioni:
  Fase A: nessun rischio — analisidef non cambia
  Fase B: calcoli divergenti → confronto automatico output
  Fase C: worker fallisce → fallback a ultimo JSON di analisidef
```

### Fase 4 — Auth + Pagamento (3-4 giorni)
- [ ] Auth endpoints (register, login, logout, refresh, reset)
- [ ] JWT middleware (python-jose, 15min access + 30d refresh)
- [ ] Stripe (checkout, webhook, cancellation)
- [ ] Paywall enforcement per tier (free/pro/team)
- [ ] GDPR (export, delete)
- [ ] Audit log integration

### Fase 5 — Frontend PWA (4-5 giorni)
- [ ] manifest.json + Service Worker (offline cache)
- [ ] Login/register UI
- [ ] Test iOS Safari PWA
- [ ] Bottom nav mobile

### Fase 6 — Mobile iOS (3-4 giorni)
- [ ] Capacitor setup
- [ ] Push notifications
- [ ] Face ID login
- [ ] Build + submit App Store

### Fase 7 — Stabilizzazione continua
- [x] Backup automatico (cron 03:00, pg_dump, 7gg retention)
- [x] Health check (cron 5min, auto-restart)
- [x] robots.txt (no indexing)
- [x] Git repo GitHub (privato)
- [ ] Alerting Telegram (notifica se health check fallisce)
- [ ] Load testing (100 concurrent)
- [ ] Test restore backup mensile
- [ ] Aggiornamento dipendenze

---

## 23. Migrazione analisidef → App_tool — Piano Completo

> **Data**: 30 Marzo 2026
> **Obiettivo**: rendere App_tool autonomo — tutto il motore Python, i cron, i batch LLM
> devono girare dentro App_tool senza dipendere da analisidef.
> analisidef resta viva in sola lettura come reference e fallback.

### 23.1 Inventario Sorgente (analisidef)

```
analisidef/                         13,100 LOC Python totali
├── lib/                            7,565 LOC — 25 moduli
│   ├── loader.py           1,036   Parse match JSON, cards_db, deck pool, FORMAT_FOLDERS
│   ├── investigate.py        804   Board state, ink budget, classify_losses (9 dim + alert)
│   ├── gen_archive.py        631   Archivio JSON completo (~15-55 MB/matchup)
│   ├── gen_killer_curves.py  560   Sezione playbook T1-T7 per report
│   ├── i18n.py               457   Traduzioni killer curves (en/it/de/zh/ja)
│   ├── validate_semantics.py 400   Validazione LLM: claim vs ability reali
│   ├── gen_decklist.py       334   Sezione decklist ottimizzata
│   ├── validate_killer_curves.py 315 Validazione meccanica killer curves JSON
│   ├── gen_deck_actually.py  290   Sezione deck actually (PRO player tech)
│   ├── cards_dict.py         275   1511 carte normalizzate con keyword/flag
│   ├── stats.py              208   Calcoli statistici puri
│   ├── gen_review.py         200   Sezione review (cause sconfitta, play vincenti)
│   ├── gen_risposte.py       184   Sezione toolkit (removal, rush, ward, ramp)
│   ├── gen_curve_t1t7.py     164   Curve storiche T1-T7
│   ├── gen_validate.py       161   Validazione meccanica report
│   ├── gen_killer_curves_draft.py 154 Bozza threat identification
│   ├── build_replay_steps.py 701   Step pre-calcolati per replay v2
│   ├── gen_digest.py         ~100  Digest compatto per LLM (~20KB)
│   ├── gen_all_turns.py       89   Dump turni (legacy)
│   ├── gen_mani.py            78   Sezione mani vincenti
│   ├── formatting.py          78   Display helpers
│   ├── gen_panoramica.py      60   Sezione panoramica
│   ├── assembler.py           55   Assemblaggio finale report
│   ├── validate.py           122   Validazione report
│   └── __init__.py
│
├── daily/                          4,826 LOC
│   ├── daily_routine.py    3,456   Monolite: meta WR, leaderboard, tech, player_cards
│   ├── history_db.py         677   SQLite storico (5 tabelle)
│   ├── team_training.py      317   Stats per-player (modulo isolato)
│   ├── serve_dashboard.py    199   HTTP server + /api/decks (file JSON)
│   ├── backfill_history.py   162   Backfill storico per date passate
│   ├── serve.py               15   Server minimal (legacy)
│   ├── dashboard.html      7,554   Template dashboard monolitico
│   ├── team_training_js.js 1,288   JS team training
│   ├── team_roster.json            Config team (5 player)
│   └── refresh_dashboard.sh        Rebuild template → output (~2s)
│
├── generate_report.py        249   Pipeline 5 fasi orchestratore
├── build_replay.py           754   Replay HTML v1
├── build_replay_v2.py        153   Replay HTML v2
├── audit_replay.py           602   Validazione integrita' replay
├── run_all_killer_curves.sh        Batch notturno (digest + LLM + validazione + git)
│
├── output/                   3.6 GB
│   ├── archive_*.json        132   Archivi matchup (15-55 MB ciascuno)
│   ├── digest_*.json         132   Digest LLM (~200-500 KB)
│   ├── killer_curves_*.json  134   Killer curves LLM (~100-300 KB)
│   └── replay_*.html         140   Replay interattivi (~1-2 MB)
│
└── reports/                  141   Report matchup .md
```

**Dipendenze esterne:**
- `/mnt/.../matches/` — 64K+ file JSON (scritti da lorcana_monitor.py)
- `/mnt/.../cards_db.json` — 1511 carte
- `/mnt/.../decks_db/` — Decklist tornei
- `https://duels.ink/api/leaderboard` — 4 queue (TOP/PRO player)
- `https://duels.ink/api/stats/meta` — Community meta stats
- Claude CLI (`claude -p --model sonnet`) — killer curves batch (subscription OAuth)

### 23.2 Inventario Destinazione (App_tool) — Stato 30/03

```
App_tool/
├── backend/                        IMPLEMENTATO 60%
│   ├── api/        7 file, 518 LOC   28 endpoint funzionanti ✅
│   ├── services/   6 file, 777 LOC   6/11 servizi (5 mancanti) ⚠️
│   ├── models/     7 file, 328 LOC   12 classi ORM ✅
│   ├── middleware/  1 file,  13 LOC   Solo error_handler ⚠️
│   ├── workers/    NON ESISTE         0 worker ✗
│   ├── main.py     72 LOC            FastAPI entrypoint ✅
│   ├── config.py   23 LOC            Settings ✅
│   └── deps.py     62 LOC            Auth + tier ✅
│
├── db/migrations/  2 file             Schema completo ✅
├── scripts/        7 file, 962 LOC    Import funzionanti ✅
├── frontend/       2 JS + symlink     Skeleton + dashboard.html ⚠️
├── lib/            Solo __init__.py   Vuoto ✗
├── schemas/        Solo __init__.py   Vuoto ✗
├── pipelines/      Solo __init__.py   Vuoto ✗
├── infra/          NON ESISTE         0 config ✗
└── tests/          NON ESISTE         0 test ✗
```

**Gia' operativo:**
- PostgreSQL con 88K+ match, 128 killer curves, 102 snapshot storici
- Auth JWT + tier enforcement + promo codes
- 28 API endpoint (monitor, coach, lab, admin, promo, dashboard)
- Cron: backup 03:00, import match 06:30, import curves Mar+Gio 05:30, healthcheck 5min
- nginx + SSL + dominio metamonitor.app

### 23.3 Strategia Git — dev / main

```
main ────────────────────────────────────────────────────────────►
  │                                                    ▲
  │ (oggi: 339c6d2)                                    │ merge quando stabile
  │                                                    │
  └── dev ──┬── M1 ──┬── M2 ──┬── M3 ──┬── M4 ──┬── M5 ──►
            │        │        │        │        │
         lib/     workers/  profile  frontend  cutover
         migrate  + cron    API+UI   SPA       spegni
         da       batch              completa  analisidef
         analisidef

Regole:
  - main = produzione stabile (metamonitor.app serve da main)
  - dev = integrazione continua, si rompe, si aggiusta
  - Ogni milestone (M1-M5) = merge dev → main quando:
    1. Tutti i test passano
    2. Output confrontato con analisidef (stessi numeri)
    3. Cron testato per almeno 2 giorni
  - Mai push diretto su main
  - analisidef non cambia (sola lettura + cron invariati fino a cutover)
```

### 23.4 Le 5 Milestone

---

#### M1 — Lib Migration (lib/ da analisidef → App_tool)

**Obiettivo:** copiare i 25 moduli Python in App_tool/lib/ e adattarli per leggere da PostgreSQL dove possibile, mantenendo compatibilita' con file JSON come fallback.

**File da copiare (as-is, poi adattare):**

| Modulo | LOC | Adattamento |
|--------|-----|-------------|
| `loader.py` | 1,036 | **Chiave**: aggiungere `load_matches_from_db()` come alternativa a `load_matches()`. Stessa interfaccia (ritorna lista game dict), ma legge da PostgreSQL `matches` table + JSONB turns. Il vecchio path JSON resta come fallback. |
| `investigate.py` | 804 | Nessun adattamento — lavora su game dict in memoria |
| `gen_archive.py` | 631 | Nessun adattamento — scrive JSON in output/ |
| `gen_digest.py` | ~100 | Nessun adattamento |
| `stats.py` | 208 | Nessun adattamento — calcoli puri su liste |
| `cards_dict.py` | 275 | Path `cards_db.json` da config (non hardcoded) |
| `formatting.py` | 78 | Nessun adattamento |
| `validate.py` | 122 | Nessun adattamento |
| `validate_killer_curves.py` | 315 | Nessun adattamento |
| `validate_semantics.py` | 400 | Nessun adattamento |
| `i18n.py` | 457 | Nessun adattamento |
| `assembler.py` | 55 | Nessun adattamento |
| `build_replay_steps.py` | 701 | Nessun adattamento |
| `gen_panoramica.py` | 60 | Nessun adattamento |
| `gen_killer_curves.py` | 560 | Nessun adattamento |
| `gen_mani.py` | 78 | Nessun adattamento |
| `gen_risposte.py` | 184 | Nessun adattamento |
| `gen_review.py` | 200 | Nessun adattamento |
| `gen_decklist.py` | 334 | Nessun adattamento |
| `gen_deck_actually.py` | 290 | Path matches da config |
| `gen_validate.py` | 161 | Nessun adattamento |
| `gen_curve_t1t7.py` | 164 | Nessun adattamento |
| `gen_killer_curves_draft.py` | 154 | Nessun adattamento |
| `gen_all_turns.py` | 89 | Nessun adattamento |

**L'adattamento critico e' UNO SOLO: `loader.py`.**

```python
# App_tool/lib/loader.py — nuova funzione
def load_matches_from_db(our_deck, opp_deck, game_format='core', db_url=None):
    """
    Stessa interfaccia di load_matches() ma legge da PostgreSQL.
    Ritorna: (games, cards_db, deck_pool) — stesso formato.
    """
    # SELECT * FROM matches WHERE deck_a/deck_b match, game_format match
    # Deserializza JSONB turns → stessa struttura game dict
    # cards_db: caricato da file (non cambia)
    # deck_pool: caricato da file (non cambia)
    ...
```

**Validazione M1:**
```bash
# Confronto output: analisidef vs App_tool con stessi input
python3 generate_report.py ES AbE           # in analisidef → report A
python3 generate_report.py ES AbE --from-db # in App_tool   → report B
diff <(grep "WR:" report_A.md) <(grep "WR:" report_B.md)
# Devono essere identici (stessi match, stessi calcoli)
```

**File da creare/modificare in App_tool:**
```
NUOVO:      lib/*.py (25 file copiati)
MODIFICARE: lib/loader.py (aggiungere load_matches_from_db)
MODIFICARE: lib/cards_dict.py (path da config)
NUOVO:      lib/config.py (path centralizzati: matches_dir, cards_db, decks_db)
```

**Durata stimata:** 1-2 giorni (copia + adattamento loader + test confronto)

---

#### M2 — Workers + Cron Batch

**Obiettivo:** App_tool esegue autonomamente le pipeline che oggi girano in analisidef.

**Worker 1: `daily_pipeline.py`** (sostituisce `daily_routine.py` di analisidef)

Questo e' il pezzo piu' complesso. `daily_routine.py` e' un monolite da 3,456 LOC che:
1. Scansiona match dalle cartelle (SET11, TOP, PRO, FRIENDS, INF)
2. Aggrega WR per 8 perimetri
3. Fetcha leaderboard duels.ink (4 queue)
4. Fetcha community stats duels.ink
5. Calcola tech choices, player_cards, meta share, trend
6. Chiama team_training.py
7. Scrive history.db (SQLite)
8. Genera dashboard_data.json + report .md/.pdf

**Strategia di migrazione daily_routine:**

```
NON riscrivere. Adattare.

Fase 1 (M2): copiare daily_routine.py in App_tool/backend/workers/
  - Sostituire load da file con load da PostgreSQL (usa loader.py adattato)
  - Sostituire history.db SQLite con INSERT in daily_snapshots PostgreSQL
  - fetch duels.ink API: invariato (stesso codice HTTP)
  - team_training.py: copiare in App_tool/backend/workers/
  - Output: scrive dashboard_data.json in App_tool/data/output/

Fase 2 (M5): decomposizione in servizi
  - stats_service.py gia' fa parte dei calcoli (WR, matrice)
  - Estrarre funzioni da daily_routine in servizi dedicati
  - Ma questo e' ottimizzazione, non blocco
```

**Worker 2: `match_importer.py`** (evoluzione di `scripts/import_matches.py`)

Gia' funzionante come script cron. Da promuovere a worker:
- Aggiungere log strutturato
- Aggiungere metriche (match importati, tempo, errori)
- Notifica Telegram se fallisce

**Worker 3: `killer_curves_batch.py`** (sostituisce `run_all_killer_curves.sh`)

Il batch shell fa:
1. Per ogni matchup qualificato: genera archivio + digest (Python)
2. Chiama Claude CLI per killer curves (4 paralleli, 120s pausa)
3. Valida output
4. Git commit + push

```
Strategia:
  Fase 1: tradurre la parte Python dello shell script in Python puro
  Fase 2: mantenere la chiamata Claude CLI come subprocess
  Fase 3 (futuro con API credit): sostituire CLI con Claude API via SDK

  Il batch resta un processo separato (non un endpoint API).
  Gira come cron: 0 0 * * 2,4 (mar+gio mezzanotte).
```

**Worker 4: `refresh_dashboard.py`** (sostituisce `refresh_dashboard.sh`)

Lo shell script:
1. Copia template dashboard.html
2. Inietta dati da dashboard_data.json
3. Ridimensiona icone deck (PIL)
4. Restart systemd service

In App_tool questo diventa piu' semplice: il frontend legge via API, non serve embed nel template. Il worker si riduce a:
1. Chiama daily_pipeline → genera dashboard_data.json
2. REFRESH MATERIALIZED VIEW (gia' implementato in admin.py)

**Cron schedule App_tool (post M2):**

```
# App_tool autonomo
*/5 * * * *    healthcheck.sh              → auto-restart
0   3 * * *    backup.sh                   → pg_dump + gzip
30  6 * * *    match_importer.py           → importa nuovi match JSON → PostgreSQL
1   7 * * *    daily_pipeline.py           → meta WR, leaderboard, dashboard_data.json
0   0 * * 2,4  killer_curves_batch.py      → digest + LLM + validazione

# analisidef (parallelo per validazione, poi spento)
0   7 * * *    lorcana_monitor.py report   → resta attivo (scrive match JSON)
1   7 * * *    daily_routine.py            → SPENTO dopo validazione M2
0   0 * * 2,4  run_all_killer_curves.sh    → SPENTO dopo validazione M2
```

**File da creare:**
```
NUOVO: backend/workers/daily_pipeline.py    (~500 LOC, wrappa daily_routine adattato)
NUOVO: backend/workers/match_importer.py    (evoluzione script esistente)
NUOVO: backend/workers/killer_curves_batch.py (~200 LOC, traduce shell script)
COPIARE: daily/team_training.py → backend/workers/team_training.py
COPIARE: daily/history_db.py → backend/workers/ (adattare per PostgreSQL)
COPIARE: daily/team_roster.json → data/team_roster.json
```

**Validazione M2:**
```bash
# Confronto output daily
diff <(python3 -c "import json; d=json.load(open('analisidef/daily/output/dashboard_data.json')); print(sorted(d.keys()))") \
     <(python3 -c "import json; d=json.load(open('App_tool/data/output/dashboard_data.json')); print(sorted(d.keys()))")

# Confronto WR per deck (devono coincidere)
# Confronto top_players (stessi nomi, stessi WR)
# Confronto killer_curves count (stesso numero di curve valide)
```

**Durata stimata:** 3-5 giorni (daily_routine adattamento + test + cron setup)

---

#### M3 — Profile API + Frontend

**Obiettivo:** implementare il tab Profile come descritto in sezione 7.5.

**Backend (sezione 7.5 gia' specifica tutto):**
```
NUOVO: backend/api/user.py              # CRUD preferences, decks, my-stats
NUOVO: backend/services/user_service.py  # Query my-stats, preferences merge, deck validation
MODIFICARE: backend/main.py             # Mount user router
```

**Frontend:**
```
NUOVO: frontend/assets/js/profile.js    # Render Profile tab
MODIFICARE: frontend/assets/js/app.js   # Aggiungere tab routing
MODIFICARE: frontend/index.html         # Bottone tab Profile
```

**Dati:**
- `users.preferences` JSONB → nick, country, pins (zero migrazioni)
- `user_decks` tabella → CRUD deck (zero migrazioni)
- `matches` tabella → query my-stats (zero migrazioni)

**Durata stimata:** 2-3 giorni

---

#### M4 — Frontend SPA Completa

**Obiettivo:** rompere la dipendenza dal `dashboard.html` monolitico.
Ogni tab diventa un modulo JS separato che chiama le API di App_tool.

**Oggi:** `frontend/dashboard.html` vive gia' in App_tool, ma resta un file monolitico
che contiene gran parte di Monitor, Coach, Lab, Team, Profile.

**Target:** 7 moduli JS indipendenti, ciascuno chiama le API backend.

```
frontend/assets/js/
├── app.js          Router, state, tab switching (esiste, da estendere)
├── api.js          Fetch wrapper con JWT (esiste)
├── monitor.js      Tab Monitor (estrarre da dashboard.html)
├── coach.js        Tab Coach V2 (estrarre da dashboard.html)
├── lab.js          Tab Lab (estrarre da dashboard.html)
├── team.js         Tab Team Training (estrarre da dashboard.html + team_training_js.js)
├── profile.js      Tab Profile (creato in M3)
├── community.js    Tab Community (nuovo)
├── events.js       Tab Events (nuovo)
└── auth.js         Login/register UI (nuovo)
```

**Strategia estrazione dal monolite:**

```
dashboard.html (7,554 LOC) contiene:
  - CSS (~1,700 LOC) → frontend/assets/css/app.css
  - HTML template per ogni tab (~2,000 LOC) → inline nei render() di ogni .js
  - JS globale + funzioni per tab (~3,800 LOC) → split per modulo

Approccio:
  1. Estrarre CSS in file separato
  2. Per ogni tab, identificare le funzioni JS che usa
  3. Creare modulo .js con quelle funzioni
  4. Sostituire DATA.perimeters[*] con fetch('/api/v1/monitor/...')
  5. Testare tab per tab

Ordine estrazione (dal piu' indipendente al piu' intrecciato):
  1. Profile (gia' fatto in M3)
  2. Monitor (usa solo API monitor, nessuna dipendenza da altri tab)
  3. Lab (usa API lab + coach, dipende da selezione deck)
  4. Coach (usa API coach, dipende da selezione deck + formato)
  5. Team Training (usa API team, dipende da roster)
  6. Community + Events (nuovi, nessuna estrazione)
```

**Differenza chiave: DATA → API**

In dashboard.html monolitico:
```javascript
// Tutto caricato in un blob JSON gigante
const DATA = await fetch('/output/dashboard_data.json').then(r => r.json());
const wr = DATA.perimeters.set11.decks.AmAm.wr;
```

In App_tool SPA:
```javascript
// Ogni tab chiama la sua API
const meta = await API.get('/monitor/meta?game_format=core&days=2');
const wr = meta.decks.find(d => d.code === 'AmAm').wr;
```

**Durata stimata:** 5-8 giorni (estrazione + test per ogni tab)

---

#### M5 — Cutover (spegnimento analisidef)

**Obiettivo:** App_tool e' completamente autonomo. analisidef non e' piu' necessaria per aggiornare dati applicativi.

**Prerequisiti:**
- [M1] lib/ funzionante con output identico
- [M2] Worker cron testato per almeno 7 giorni in parallelo
- [M3] Profile API operativo
- [M4] Frontend che non dipende da monolite legacy o da sync esterni

**Checklist cutover:**

```
PRE-CUTOVER (giorno -7):
  □ Worker daily_pipeline.py gira da 7+ giorni senza errori
  □ Output confrontato giornalmente con analisidef (WR, players, curves identici)
  □ Frontend SPA testato su tutti i tab
  □ Backup verificato e restore testato

CUTOVER DAY:
  1. Disabilitare cron analisidef:
     # crontab -e → commentare:
     # 1   7 * * *   daily_routine.py
     # 0   0 * * 2,4 run_all_killer_curves.sh
     # 5   7 * * *   generate_and_send.py

  2. Verificare che App_tool cron funziona da solo:
     - worker analyzer genera matchup_reports in PG ✓
     - worker killer curves genera/importa curve ✓
     - match_importer.py importa match ✓

  3. Verificare che frontend produzione usa solo asset/code in App_tool

  4. Aggiornare nginx se necessario per servire solo frontend/ statico

  5. Monitorare per 48h

POST-CUTOVER:
  □ analisidef resta su disco come reference (read-only)
  □ lorcana_monitor.py RESTA ATTIVO (scrive match JSON, App_tool li importa)
  □ Rimuovere import paths da analisidef in config.py
  □ Merge dev → main
```

**Cosa resta attivo di analisidef:**
- `lorcana_monitor.py` — cattura match da duels.ink → `/matches/`. **Non si tocca.**
  App_tool lo importa via `match_importer.py` cron 06:30.
- Eventuali file JSON storici restano solo come archivio/reference, non come input richiesto dal prodotto.

**Cosa viene spento:**
- `daily_routine.py` cron → sostituito da job App_tool
- `run_all_killer_curves.sh` cron → sostituito da `killer_curves_batch.py`
- `serve_dashboard.py` (porta 8060) → non piu' necessario
- `generate_and_send.py` → da migrare o riscrivere

### 23.5 Mappa Dipendenze Esterne

```
lorcana_monitor.py (NON in analisidef, NON in App_tool — standalone)
  │
  │ scrive ogni 15s
  ▼
/mnt/.../matches/{DDMMYY}/{PERIMETER}/*.json
  │
  ├──── analisidef/lib/loader.py legge (OGGI)
  │
  └──── App_tool/scripts/import_matches.py importa (OGGI, cron 06:30)
        App_tool/lib/loader.py leggera' da PostgreSQL (DOPO M1)

/mnt/.../cards_db.json (1511 carte, aggiornato manualmente)
  │
  ├──── analisidef/lib/cards_dict.py legge
  └──── App_tool/lib/cards_dict.py leggera' (path da config)

duels.ink API (leaderboard + community stats)
  │
  ├──── analisidef/daily/daily_routine.py fetcha (OGGI)
  └──── App_tool/backend/workers/daily_pipeline.py fetchera' (DOPO M2)

Claude CLI (subscription OAuth, no API key)
  │
  ├──── analisidef/run_all_killer_curves.sh chiama (OGGI)
  └──── App_tool/backend/workers/killer_curves_batch.py chiamera' (DOPO M2)
```

### 23.6 Rischi e Mitigazioni

| Rischio | Impatto | Mitigazione |
|---------|---------|-------------|
| daily_routine.py (3456 LOC) diverge durante migrazione | Output diversi tra analisidef e App_tool | Confronto automatico giornaliero per 7+ giorni prima di cutover |
| JSONB turns in PostgreSQL ha struttura diversa da JSON file | Query sbagliate, dati persi | Test su 100 match campione: deserializza JSONB → stessa struttura dict |
| Claude CLI non disponibile (subscription scaduta) | Killer curves non generate | Fallback: usa killer curves esistenti in DB (generate_at recente) |
| lorcana_monitor.py cambia formato output | Import fallisce | Healthcheck su import: se 0 nuovi match per 24h → alert |
| Frontend SPA rotta durante estrazione | Utenti vedono errori | M4 su dev, merge solo quando tutti i tab passano test visivo |
| cards_db.json aggiornato manualmente (nuove carte) | Mismatch tra file e DB | Singola fonte: il file resta master, caricato all'avvio da entrambi |

### 23.7 Ordine Cronologico Consigliato

```
Settimana 1: M1 (lib migration)
  Lun-Mar: copia lib/, adatta loader.py, test confronto
  Mer-Gio: fix divergenze, test generate_report.py da DB
  Ven: merge dev, tag v0.4.0-m1

Settimana 2: M2 (workers)
  Lun-Mar: daily_pipeline.py (adatta daily_routine)
  Mer: killer_curves_batch.py (traduce shell script)
  Gio-Ven: cron setup, test parallelo con analisidef
  Ven: merge dev, tag v0.4.0-m2

Settimana 3: M3 (Profile) + inizio M4
  Lun: backend/api/user.py + user_service.py
  Mar: frontend/profile.js
  Mer-Ven: inizio estrazione Monitor + Coach da monolite
  Ven: merge dev, tag v0.5.0-m3

Settimana 4: M4 (Frontend SPA)
  Lun-Mer: Lab + Team Training estrazione
  Gio-Ven: Community + Events (nuovi)
  Ven: merge dev, tag v0.6.0-m4

Settimana 5: M5 (Cutover)
  Lun: confronto finale output (7 giorni di parallelo)
  Mar: cutover day (spegni cron analisidef)
  Mer-Ven: monitoraggio, fix, merge dev → main
  Ven: tag v1.0.0, merge main
```

---

## 12. TODO — Feature Frontend non ancora alimentate (14 Apr 2026)

Queste sezioni sono **già implementate nel frontend** (`dashboard.html`), rispettano il pattern `monAccordion` uniforme e compaiono automaticamente **solo quando i dati arrivano**. Finché il backend non popola il campo, l'accordion è silenziosamente nascosto via guardia `if (data.length > 0)` — zero rumore visivo, zero rischio architetturale.

### 12.1 Coach V2 — Sezioni in attesa di Fase B LLM

| Sezione | Campo blob | Status | Sblocco |
|---------|-----------|--------|---------|
| **Key Threats** (`acc-kt`) | `matchup_analyzer.<deck>.vs_<opp>.threats_llm.threats[]` | Campo esiste, array vuoto per tutti i matchup | Fase B LLM batch (feature #2 benchmark) |
| **How to Respond** (`acc-howrespond`) | `matchup_analyzer.<deck>.vs_<opp>.killer_responses[]` e `killer_curves[].response` | Presente ma eterogeneo tra legacy e schema nuovo | Target: testo inglese, curve-specifico, fallback legacy |

**Attivazione stimata**: pipeline `run_all_reviews.sh` batch settimanale via OpenAI (~$3-5/mese). Prompt B esteso per emettere blocchi `<!-- THREATS_LLM -->` e `<!-- KILLER_RESPONSES -->` strutturati. Parser in `import_matchup_reports.py` per popolare i campi blob. Stima 4-5 dev days.

### 12.2 Profile tab

| Sezione | Campo blob | Status | Sblocco |
|---------|-----------|--------|---------|
| **Best Plays** | `best_plays`, `best_plays_infinity` | dict vuoto top-level | Query Python: estrae le 3 sequenze più devastanti per deck dalle killer curves avversarie esistenti, ranking per complessità. ~1 dev day backend + 0.5 dev day frontend |

### 12.1.1 Killer Curves — `response` schema v2

Problema emerso nel frontend:
- `How to Respond` risultava spesso troppo compresso o analyst-oriented
- `OTP / OTD` come sola sigla era poco leggibile
- il testo assumeva troppo spesso la stock list

Decisione:
- la killer curve resta una **curve** avversaria
- `How to Respond` deve spiegare come rispondere a **quella curva**
- il testo user-facing va scritto in **inglese**
- `response.strategy` resta una summary breve
- il blocco leggibile va in campi strutturati opzionali con fallback al formato legacy

Campi target in `killer_curves[].response`:
- `format_version`
- `strategy`
- `cards`
- `ink_required`
- `turn_needed`
- `headline`
- `core_rule`
- `priority_actions`
- `what_to_avoid`
- `stock_build_note`
- `off_meta_note`
- `play_draw_note`
- `failure_state`

### 12.3 Monitor tab

| Sezione | Campo blob | Status | Sblocco |
|---------|-----------|--------|---------|
| **Non-Standard Picks** per perimetro | `perimeters.<peri>.tech_choices[]` | Array vuoto | Consumato comunque da `tech_tornado` top-level (dict(6)) che alimenta la sezione. `tech_choices` è duplicato non usato — candidato rimozione lato backend. |

### 12.4 Top-level

| Campo | Status | Azione |
|-------|--------|--------|
| `analysis` | `str(0)` vuoto | Probabilmente deprecated. Verificare se qualche tab lo legge, altrimenti rimuovere. |

### 12.5 Principio UX garantito

Ogni nuova feature aggiunta al frontend deve rispettare la regola **"fail closed"**:
- Se il campo blob manca o è vuoto → accordion **non appare** (niente placeholder "coming soon")
- Se il campo blob ha dati → accordion appare con stato default (aperto/chiuso) documentato
- Nessuna regressione quando una feature pipeline si attiva successivamente: l'accordion si popola automaticamente al prossimo rebuild del blob (cache 2h)
```

---

## 24. Sensitive Data & Privacy Architecture — V3 Launch Layer

**Aggiunta il 24 Aprile 2026.** Delta additivo su architettura esistente. Nessun refactor auth, nessun refactor DB, nessuna modifica al modello V3. Mirato a chiudere il gap di ownership/privacy sui replay upload e sul Replay Viewer pubblico prima che V3 vada live.

### 24.1 Verdetto GO incrementale

Il layer privacy si implementa come **delta additivo** sullo schema e sugli endpoint già in produzione. Nessun componente esistente viene sostituito.

Base già in produzione (da NON toccare):
- `users` (id UUID, `tier`, `preferences` JSONB, `deletion_requested_at`, `stripe_customer_id`)
- `user_sessions`, `password_reset_tokens`
- `user_decks`, `promo_codes`, `promo_redemptions`
- `team_replays`, `team_roster`
- `user_service.export_user_data()` + `GET /api/user/export` (GDPR export attivo)
- Soft-delete flow via `deletion_requested_at`

Cosa aggiungiamo: **1 migration additiva** (`team_replays` ownership) + **access-control su 4 endpoint** + **consenso UI** + **anonymization response** del Replay Viewer pubblico. Tutto il resto (tabelle dedicate per consensi, identity links, privacy events) può restare in `users.preferences` JSONB fino a 30 giorni post-lancio.

Unico blocker reale: l'ownership dei replay. Senza `user_id` su `team_replays`, Board Lab non ha un concetto di proprietà → rischio GDPR concreto. M1 risolve questo in una migration zero-downtime.

### 24.2 Data Classification

| Categoria | Tipo | Storage | Personale | Anonymization | Retention | Access |
|---|---|---|---|---|---|---|
| Public aggregated data (meta, WR, matchup stats) | Derivato | `dashboard_data` blob (Redis) + `daily_snapshots` (PG) | No | N/A | Rolling 90gg | Public |
| Scraped match logs (duels.ink) | Grezzo | `matches` (PG) + FS `/matches/<DDMMYY>/` | No (non-PII; contiene solo nickname pubblici duels.ink) | Mascheramento nickname solo in output pubblico | Indefinito (storico statistico) | Internal |
| Player nicknames (duels/lorcanito) come stringhe in log | Sensibile low | In `matches.turns[].player` (esistente) | Sì (identificabile) | Sì nel Replay Viewer pubblico (→ "Player/Opponent A") | Come match logs | Internal, mai in risposte API pubbliche |
| User profile data (email, password_hash, tier) | PII | `users` | Sì | No (serve per auth) | Fino a deletion request +30gg | Owner + admin |
| User nicknames duels/lorcanito + country | PII low | `users.preferences.nicknames` JSONB | Sì | No internamente; mai esposti pubblicamente | Con account | Owner + admin |
| Saved decks | Config | `user_decks` | No (non PII di per sé) | No | Con account | Owner |
| Replay uploads Team/Board Lab (.gz parsed) | **PII + contenuto utente** | `team_replays` (esistente) + ownership M1 | Sì | No per owner/coach assegnato | Con account (+30gg post-delete) | **Owner only + assigned coach** |
| Coaching session notes (futuro) | PII + contenuto | `coaching_session_notes` (tabella entro 30gg se serve) | Sì | No | Con account | Owner + student + assigned coach |
| Student/team data (roster) | Low PII (solo nickname scelto) | `team_roster` (esistente) | Low | No | Con account team coach | Team coach only |
| Email / waitlist | PII low | `users.preferences.waitlist_joined_at` + (opzionale) `email_subscribers` | Sì | No | Fino a unsubscribe | Internal |
| Promo / trial state | Derivato | `promo_codes`, `promo_redemptions` (esistenti) | No | N/A | Audit permanente | Internal |
| Future payment data | PII + PCI | NON in DB nostro. Solo token PSP (Paddle/Stripe customer_id già in `users.stripe_customer_id`) | Sì | No | Secondo PSP | Internal + PSP |

**Regola operativa:** ogni categoria sopra "low PII" viene loggata nel `GET /api/user/export` (GDPR) e cancellata su `deletion_requested_at`.

### 24.3 Storage Rules e Ownership

**Principi:**

1. **Ownership esplicita obbligatoria** per ogni dato user-generated: `user_id` NOT NULL (o con backfill plan).
2. **Privacy default = private.** Upload, replay, notes non sono pubblici salvo flag esplicito + consenso.
3. **Scraped data != user data.** I match logs scrapati da duels.ink sono statistiche aggregate: non trattati come dati personali dell'utente-finale della dashboard.
4. **JSONB `preferences` come escape hatch** per campi non-critici che non meritano ancora tabella dedicata (consensi, nicknames, waitlist).
5. **Niente duplicazione.** Se `preferences` basta, non crei tabella dedicata. Si promuove a tabella quando serve versioning, audit append-only, o query relazionali.

**Cosa resta in `users.preferences` (no migration):**

```jsonc
// users.preferences JSONB — struttura consolidata V3
{
  // Nickname bridge
  "nicknames": {
    "duels": "player_nick_here",
    "lorcanito": "player_nick_here",
    "country": "IT"
  },

  // Consensi (append-only, versionati)
  "consents": {
    "tos":             { "version": "1.0", "accepted_at": "2026-05-01T10:00:00Z" },
    "privacy":         { "version": "1.0", "accepted_at": "2026-05-01T10:00:00Z" },
    "replay_upload":   { "version": "1.0", "accepted_at": "2026-05-03T15:22:00Z" },
    "marketing":       { "version": "1.0", "accepted_at": null }  // opt-in esplicito
  },

  // Fake paywall / waitlist (pre-monetizzazione)
  "waitlist_joined_at": "2026-05-01T10:00:00Z",
  "interest_to_pay":    { "tier": "pro", "at": "2026-05-10T12:00:00Z" },

  // UI preferences (già esistenti)
  "theme": "dark",
  "pinned_decks": ["ES", "AmAm", "RS"]
}
```

**Regola di lettura:** ogni chiave sopra ha default sicuro (vuoto/null) quando assente. Nessun crash se un utente legacy non ha `preferences.consents`.

**Cosa va in tabella dedicata (M1 pre-lancio):** solo `team_replays` viene esteso. Nessun'altra tabella nuova pre-lancio.

### 24.4 Migration M1 — `team_replays` ownership

**Obbligatoria pre-lancio. Additive. Zero-downtime.**

```sql
-- Alembic migration: <revision>_team_replays_ownership.py
-- Up:

ALTER TABLE team_replays
  ADD COLUMN user_id UUID NULL REFERENCES users(id) ON DELETE CASCADE,
  ADD COLUMN is_private BOOLEAN NOT NULL DEFAULT true,
  ADD COLUMN consent_version VARCHAR(10) NULL,
  ADD COLUMN uploaded_via VARCHAR(20) NULL,   -- 'team_lab' | 'board_lab' | 'api'
  ADD COLUMN shared_with JSONB NOT NULL DEFAULT '[]'::jsonb;
  -- shared_with = array di user_id UUID string a cui l'owner ha esplicitamente
  -- dato accesso (coach assegnato). Vuoto = solo owner.

CREATE INDEX IF NOT EXISTS idx_team_replays_user ON team_replays(user_id)
  WHERE user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_team_replays_private
  ON team_replays(is_private, user_id);

-- Down:
DROP INDEX IF EXISTS idx_team_replays_private;
DROP INDEX IF EXISTS idx_team_replays_user;
ALTER TABLE team_replays
  DROP COLUMN IF EXISTS shared_with,
  DROP COLUMN IF EXISTS uploaded_via,
  DROP COLUMN IF EXISTS consent_version,
  DROP COLUMN IF EXISTS is_private,
  DROP COLUMN IF EXISTS user_id;
```

**Backfill strategy:**

- **Nessun backfill automatico.** I record pre-M1 restano `user_id = NULL`.
- L'access-control (§24.5) nega accesso a qualunque record con `user_id IS NULL` tranne che a utenti `is_admin=true`.
- Dopo 30 giorni di operatività M1: decidi manualmente se hard-delete degli orphan oppure backfill da `player_name` + matching nickname → `users.preferences.nicknames.duels`.
- `NOT NULL` su `user_id` rimandato a M2 (post-backfill).

**SQLAlchemy model update:**

```python
# backend/models/team.py — additive
class TeamReplay(Base):
    __tablename__ = "team_replays"
    # ... campi esistenti ...
    user_id = mapped_column(UUID(as_uuid=True),
                            ForeignKey("users.id", ondelete="CASCADE"),
                            nullable=True, index=True)
    is_private = mapped_column(Boolean, nullable=False, server_default="true")
    consent_version = mapped_column(String(10), nullable=True)
    uploaded_via = mapped_column(String(20), nullable=True)
    shared_with = mapped_column(JSONB, nullable=False, server_default="[]")
```

### 24.5 Access-Control Policy — `/api/v1/team/replay/*`

**Policy matrix:**

| Endpoint | Metodo | Autorizzazione | Filtro query |
|---|---|---|---|
| `/api/v1/team/replay/upload` | POST | `user authenticated` + `user.consent.replay_upload not null` | Assegna `user_id = current_user.id`, `is_private = true`, `consent_version = current` |
| `/api/v1/team/replay/list` | GET | `user authenticated` | `WHERE user_id = current_user.id OR current_user.id IN shared_with OR current_user.is_admin` |
| `/api/v1/team/replay/{game_id}` | GET | `user authenticated` | Stessa WHERE + check per-record |
| `/api/v1/team/replay/{game_id}` | DELETE | `user authenticated` + `replay.user_id == current_user.id OR current_user.is_admin` | — |
| `/api/v1/team/replay/{game_id}/share` | POST | `user authenticated` + `replay.user_id == current_user.id` | Aggiunge user_id target a `shared_with` |

**Deps helper (FastAPI):**

```python
# backend/deps.py — additive
def require_replay_access(
    game_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TeamReplay:
    replay = db.query(TeamReplay).filter(TeamReplay.game_id == game_id).first()
    if replay is None:
        raise HTTPException(404, "replay not found")
    if user.is_admin:
        return replay
    if replay.user_id is None:
        # orphan legacy record, nessuno può accedere tranne admin
        raise HTTPException(403, "replay access denied")
    if replay.user_id == user.id:
        return replay
    if str(user.id) in (replay.shared_with or []):
        return replay
    raise HTTPException(403, "replay access denied")


def require_replay_owner(
    game_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TeamReplay:
    replay = db.query(TeamReplay).filter(TeamReplay.game_id == game_id).first()
    if replay is None:
        raise HTTPException(404, "replay not found")
    if user.is_admin:
        return replay
    if replay.user_id != user.id:
        raise HTTPException(403, "replay access denied — not owner")
    return replay
```

**Consent check upload:**

```python
# backend/api/team.py — upload endpoint
@router.post("/replay/upload")
def upload_replay(payload: ReplayUploadIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    consent = (user.preferences or {}).get("consents", {}).get("replay_upload")
    if not consent or not consent.get("accepted_at"):
        raise HTTPException(412, "replay_upload consent required")

    replay = TeamReplay(
        game_id=payload.game_id,
        user_id=user.id,
        is_private=True,
        consent_version=consent.get("version", "1.0"),
        uploaded_via="board_lab",
        replay_data=payload.replay_data,
        # ... altri campi esistenti
    )
    db.add(replay); db.commit()
    return {"id": str(replay.id)}
```

### 24.6 Board Lab — Regole Operative

1. **Upload sempre privato di default** (`is_private = true`). Nessun toggle pubblico nella UI V3 al lancio.
2. **Ownership fissa all'upload:** `user_id = current_user.id` non modificabile.
3. **Consenso obbligatorio prima del primo upload:** checkbox UI → scrive `users.preferences.consents.replay_upload = {version, accepted_at}`.
4. **Sharing opt-in esplicito:** l'owner può aggiungere `user_id` del coach assegnato tramite `POST /api/v1/team/replay/{id}/share`. Nessuno "shared by default".
5. **Delete owner-only:** `DELETE /api/v1/team/replay/{id}` ammesso solo al proprietario o admin. Hard delete (non soft — non ha senso conservare un replay richiesto di eliminazione).
6. **Tier check Coach:** accesso a Board Lab UI gated da `user.tier in ('coach','admin')`. Non Coach → paywall soft (§24.8).
7. **Nessun public sharing URL** al lancio. Se in futuro serve "public replay link", richiede flag `is_private = false` + consenso dedicato `public_share`.
8. **Export sessione PDF:** consentito solo a owner o coach con accesso `shared_with`. Non anonimizzato (è un artefatto per il proprietario).
9. **Retention:** replay restano finché l'account esiste. On `deletion_requested_at +30gg` → hard delete.
10. **Rate limit upload:** max 20 replay/giorno per utente free, 200/giorno per Pro/Coach. Enforce a livello middleware (§24.10 post-launch).

### 24.7 Public Replay Viewer — Regole

Il Replay Viewer dentro Play mostra match reali da `matches` (scraped duels.ink). Queste **non sono uploads utente** e hanno regole separate.

1. **Sempre anonymized in response API.** Il backend sostituisce nickname reali con placeholder prima di serializzare.
2. **Mapping anonymization:**
   - Nostro player (perspective) → `"Player"`
   - Avversario → `"Opponent A"` (se match singolo)
   - In lista di match multipli dello stesso matchup → `"Opponent A"`, `"Opponent B"`, `"Opponent C"`... allocati deterministicamente per seed + match_id
3. **Mai raw nickname duels.ink nella response pubblica** di `GET /api/replay/public-log`, `GET /api/replay/game`, `GET /api/replay/list`.
4. **Nessun link a profili esterni** (duels.ink, lorcanito) dal Replay Viewer pubblico.
5. **Label UI fissa:** ogni istanza del viewer pubblico ha badge "Example match" in alto a destra.
6. **No audit per-open al lancio.** Tracciare chi apre quale replay è overhead inutile pre-monetizzazione. Entro 30gg, se servisse per abuse prevention, si aggiunge a `audit`.
7. **Differenza con Board Lab:** Board Lab mostra il proprio nickname (o vuoto) perché è l'upload del proprietario. Il Replay Viewer pubblico **non mostra mai nicknames reali**, neanche quello dell'utente loggato.

**Implementazione anonymization:**

```python
# backend/services/replay_anonymizer.py — nuovo file
def anonymize_replay_payload(payload: dict, perspective: int | None = None) -> dict:
    """Sostituisce nicknames con placeholder. Idempotente.
       Chiamato da replay_archive_service e match_log_features_service prima
       del return delle API pubbliche."""
    # Mantieni struttura, sostituisci solo i campi identificativi
    # player_name, opponent_name, ownerPlayerId, ...
    ...
```

Chiamato in:
- `replay_archive_service.list_replays()`
- `replay_archive_service.get_game()`
- `match_log_features_service.build_viewer_public_log()`

**Nessun cambiamento** in `backend/services/replay_service.py` (Board Lab parser) — quello è owner-visible, non passa dall'anonymizer.

### 24.8 Fake Paywall / Waitlist (Pre-Monetizzazione)

Al lancio non fatturiamo ancora. Il paywall serve comunque per misurare intent e stratificare UI.

**Cosa salviamo, cosa NON salviamo:**

| Dato | Dove | Quando | Note |
|---|---|---|---|
| Email iscritta alla waitlist | `users.email` + `users.preferences.waitlist_joined_at` | Su click "notify me" | Crea user con `tier='free'` se non esiste |
| Intent to pay (quale tier l'utente ha cliccato) | `users.preferences.interest_to_pay = { tier, at }` | Su click paywall "Unlock Pro" / "Unlock Coach" | Overwrite sull'ultimo click |
| Promo code riscattato pre-lancio | `promo_redemptions` (esistente) | Su redeem | Funziona identico a oggi |
| Carta di credito | **MAI. Zero.** | — | Nessuna integrazione Stripe/Paddle attiva al lancio |
| Subscription status | `users.tier` (esistente) | Upgrade via promo code | Stripe integration rimandata |

**Flusso paywall soft:**

```
User clicca "Unlock Pro — €9/m"
  ↓
  writeInterest('pro')                 // POST /api/user/interest
  ↓
  UI overlay: "Sei in waitlist. Ti scriveremo quando apriamo i pagamenti.
              Intanto, codice promo? [ input ]"
  ↓
  Se promo valido → redeem → tier='pro' per N giorni (logica esistente)
  Altrimenti → nessun cambio tier, solo intent registrato
```

**Endpoint nuovo (implementazione reale, commit `f032129`):**

```python
# backend/api/user.py — additive
# Mounted under router prefix /api/user → full path POST /api/user/interest
class InterestRequest(BaseModel):
    tier: str = Field(..., pattern="^(pro|coach|team)$")

@router.post("/interest")
def register_interest(
    payload: InterestRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prefs = dict(user.preferences or {})
    prefs["interest_to_pay"] = {
        "tier": payload.tier,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    user.preferences = prefs
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(user, "preferences")
    db.commit()
    return {"ok": True, "tier": payload.tier}
```

**Nota path:** la prima bozza di questa sezione riportava `/api/v1/user/interest`.
Il prefix effettivo del router user è `/api/user`, quindi il path reale è
`/api/user/interest`. Allineato post-implementazione.

**Endpoint collegato (commit `1abbdd0`): `POST /api/user/consent`** — usato dal
consent modal Board Lab prima dell'upload. Vedi §24.3.2 per lo schema di
`preferences.consents.<kind>` scritto da questo endpoint:

```python
class ConsentRequest(BaseModel):
    kind: str = Field(..., pattern="^(tos|privacy|replay_upload|marketing)$")
    version: str = Field(..., min_length=1, max_length=10)

@router.post("/consent")
def register_consent(payload: ConsentRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prefs = dict(user.preferences or {})
    consents = dict(prefs.get("consents", {}))
    consents[payload.kind] = {
        "version": payload.version,
        "accepted_at": datetime.now(timezone.utc).isoformat(),
    }
    prefs["consents"] = consents
    user.preferences = prefs
    flag_modified(user, "preferences")
    db.commit()
    return {"ok": True, "kind": payload.kind, "version": payload.version}
```

**Cosa evitare:**

- **Nessuna tabella `subscriptions` al lancio.** Arriva con Stripe/Paddle.
- **Nessun campo `trial_expires_at` dedicato.** Se serve un trial, si concede via promo code `TRIAL14D` → `promo_codes.duration_days=14`.
- **Nessun lock hard.** Se l'unlock è solo UI-side (come oggi con `PRO_UNLOCKED`), **non è sicuro lato server**: sostituisci con check `user.tier` enforced da `require_pro` / `require_coach` deps.

### 24.9 GDPR Export / Delete — Impact

`GET /api/user/export` esiste già (`user_service.export_user_data`). Va **esteso** per includere i dati V3.

**Estensione export:**

```python
# backend/services/user_service.py — additive
def export_user_data(db: Session, user: User) -> dict:
    return {
        "exported_at": datetime.utcnow().isoformat(),
        "user": {...},  # esistente
        "decks": [...],  # esistente
        "preferences": user.preferences or {},  # include consensi, nicknames, waitlist
        "team_replays": [
            {
                "game_id": r.game_id,
                "uploaded_at": r.created_at.isoformat(),
                "is_private": r.is_private,
                "consent_version": r.consent_version,
                "uploaded_via": r.uploaded_via,
                "shared_with": r.shared_with,
                "turn_count": r.turn_count,
                "replay_data": r.replay_data,  # incluso completo
            }
            for r in db.query(TeamReplay).filter(TeamReplay.user_id == user.id).all()
        ],
        "promo_redemptions": [...],  # se esistente, o da aggiungere
    }
```

**Soft-delete flow (delete request):**

```
User clicca "Delete account" nella UI V3
  ↓
  POST /api/user/delete-request
  ↓
  user.deletion_requested_at = now()                   (già supportato)
  user.is_active = false                               (blocca login)
  ↓
  (grazie di 30 giorni — recovery via email admin se utente cambia idea)
  ↓
  Cron job nightly:
    SELECT id FROM users WHERE deletion_requested_at < now() - interval '30 days'
    → per ogni user:
        DELETE FROM team_replays WHERE user_id = :uid  (hard)
        DELETE FROM user_decks WHERE user_id = :uid    (hard)
        DELETE FROM promo_redemptions WHERE user_id = :uid  (hard)
        DELETE FROM user_sessions WHERE user_id = :uid      (hard)
        UPDATE users SET email='deleted_<uid>@local', password_hash='', preferences='{}',
                         display_name=NULL, stripe_customer_id=NULL
          WHERE id = :uid
        -- user row resta per integrità referenziale audit; PII cancellata
```

Cron job `db/purge_deleted_users.py` da creare entro 30gg post-lancio. **Non blocker al lancio** se nessun utente chiede delete nei primi 30 giorni — basta monitorare la coda.

**Cosa l'export NON include:**

- `matches` scrapati che contengono il nickname duels dell'utente → **non** sono "user data" del prodotto, sono dati aggregati. Se l'utente vuole la rimozione dai nostri log statistici, richiede processo manuale (contatto `legal@`) e comporta ricalcolo aggregati (evento raro, post-lancio).
- Log analytics aggregati dove l'utente appare in forma statistica → non estraibili come riga singola.

Questa distinzione va scritta chiaramente nella Privacy Policy ma non impatta l'implementazione al lancio.

### 24.10 Checklist Operativa

**A. Pre-lancio (OBBLIGATORI, ≤7 giorni)**

| # | Task | Owner | Effort |
|---|---|---|---|
| A1 | Alembic migration M1 (`team_replays` ownership) scritta + applicata su staging + applicata su prod | BE | 1h |
| A2 | Update `TeamReplay` SQLAlchemy model con nuovi campi | BE | 30min |
| A3 | Deps helper `require_replay_access` / `require_replay_owner` in `backend/deps.py` | BE | 1h |
| A4 | Wiring access-control su 5 endpoint `/api/v1/team/replay/*` | BE | 1h |
| A5 | Endpoint `POST /api/user/interest` (waitlist soft paywall) | BE | 30min |
| A6 | `replay_anonymizer.py` + wiring in `replay_archive_service` + `match_log_features_service` | BE | 2h |
| A7 | Consent checkbox UI Board Lab prima del primo upload → `preferences.consents.replay_upload` | FE | 1h |
| A8 | Disclaimer footer "Unofficial fan-made" + `/about` page minimale + `legal@` alias | Ops | 30min |
| A9 | Extend `export_user_data()` con `team_replays` + `preferences` | BE | 30min |
| A10 | Smoke test access-control: utente A non vede replay utente B (curl + assertion) | QA | 1h |

**Totale: ~9h.** Budget cuscinetto: 2 giorni di calendar time part-time.

**B. Entro 30 giorni post-lancio**

| # | Task | Trigger |
|---|---|---|
| B1 | Tabella dedicata `user_consents` con versioning append-only | Quando servono audit per consent change |
| B2 | Tabella dedicata `user_identity_links` | Quando > 2 provider (oggi duels + lorcanito) |
| B3 | Endpoint `DELETE /api/v1/team/replay/{id}` owner-only | Il prima possibile post-lancio, bassa priorità se no feedback |
| B4 | Endpoint `POST /api/v1/team/replay/{id}/share` (coach assignment) | Quando un coach reale paga |
| B5 | Rate-limit upload replay (20/giorno free, 200 pro) | Se abuse osservato |
| B6 | Cron `db/purge_deleted_users.py` | Obbligatorio appena il primo utente chiede delete |
| B7 | Privacy events log (usa `audit` esistente) per export, delete, consent revoke | Nice-to-have |
| B8 | Backfill decision per `team_replays` orphan (user_id IS NULL) | Dopo 30gg |
| B9 | Alembic `NOT NULL` su `team_replays.user_id` (M1.5) | Dopo backfill |

**C. Post-monetizzazione**

| # | Task |
|---|---|
| C1 | Webhook Paddle/Stripe → `subscriptions` table |
| C2 | `invoices` table + endpoint download |
| C3 | Admin UI: search utente, export/delete manuale, revoke consent |
| C4 | Automated retention policy cron (replay > 365gg di utenti cancellati, audit > 7 anni, etc.) |
| C5 | Cookie banner se serve (solo se attivi analytics non-essenziali tipo GA) |
| C6 | DPIA completa (Data Protection Impact Assessment) |
| C7 | Data Processing Agreement con subprocessor (Hetzner, Paddle, Resend, OpenAI, Anthropic) |
