# Piano migrazione: analisi completa dentro App_tool

**Obiettivo prodotto:** `App_tool` e' l'unica app pubblica che serve gli utenti.
`analisidef` e' un motore transitorio di calcolo/import, non il prodotto.

**Stato attuale (15 Apr 2026 — Liberation Day):** API quasi 100% da PostgreSQL.
Dashboard blob assemblato **live** da PG (snapshot_assembler.py, cache 2h).
Match importati ogni 2h **con legality gate per core** (Sprint-0 oggi).
Matchup reports e killer curves ancora importati da analisidef via cron (Fase F/G).
**Blind Deck Playbook** importato in PG con narrative completa (24/24 deck) — Sprint-1 Mossa A
oggi. **Mossa B** (porting nativo OpenAI in App_tool) completata. Digest pipeline
P1.5 vendorized e sganciata dal codice runtime esterno. Replay viewer P2.5a
fase 1 e' in corso: endpoint letti da PG via `replay_archives`, import one-shot
degli archive pronto, generatore nativo archive ancora da fare. Vedi
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

### P1.5: Digest vendorized bridge freeze
**COMPLETATA 15 Apr 2026 sera**

Il generator digest nativo non importa piu' codice runtime dal tree esterno.
I moduli legacy sono congelati in `pipelines/digest/vendored/` con harness di
parita' dedicata (`scripts/diff_digest_vendored.py`).

**Validazione eseguita:**
1. `rg -n "analisidef" pipelines/digest` -> zero match
2. parity harness su 10 matchup core -> `DIFFS=0`
3. smoke `generate_digests.py --format core --limit 3` -> `ok=3 err=0`

Questo chiude il coupling **code-level** del digest generator. Restano aperti i
coupling **runtime** user-facing descritti sotto.

---

### P2.5: Runtime consumers ancora agganciati a analisidef
**Effort: basso-medio | Rischio: medio | Priorita': alta**

`Liberation Day` non si chiude finche' esistono endpoint o assembler runtime che
leggono file live dal tree esterno.

#### P2.5a: Replay viewer -> PostgreSQL
**IN CORSO (fase 1 implementata e validata localmente 15 Apr 2026 notte)**

Fase 1 fatta:
1. nuova tabella `replay_archives` con `metadata` + `games` JSONB
2. importer one-shot `scripts/import_replay_archives.py`
3. `/api/replay/list` e `/api/replay/game` riscritti per leggere da PG
4. migration applicata in locale + sample import validato (`limit 5`)

Da fare per chiuderla davvero:
1. eseguire il full import storico dei 271 archive replay (job operativo piu' lungo)
2. validare endpoint replay su dataset importato completo
3. sostituire l'archive stale del 28/03 con generatore nativo da PG oppure on-demand cache

#### P2.5b: KC Spy runtime consumer
**FATTO 15 Apr 2026 notte**

Fatto:
1. nuova tabella `kc_spy_reports`
2. importer `scripts/import_kc_spy.py` dal file legacy
3. `snapshot_assembler.py` ora legge l'ultimo report da PG
4. migration applicata in locale + import report corrente validato
5. cron macchina aggiornato: `04:05 UTC` importa `KC Spy` in App_tool subito dopo il canary legacy delle `04:00`

Da fare:
1. in un secondo tempo, se serve, portare anche il producer `kc_spy.py` in App_tool

#### P2.5c: llm_worker cleanup
**DISCOVERY FATTA 15 Apr 2026 notte — non schedulato nel crontab macchina**

`backend/workers/llm_worker.py` punta ancora a `ANALISIDEF_OUTPUT_DIR`, ma il
crontab reale usa `scripts/import_killer_curves.py` e non mostra invocazioni a
`llm_worker.py`. I guardrail OpenAI delle killer curves stanno nel batch
`run_kc_production.py`, non in `llm_worker.py`.

Prossimo step corretto:
1. verificare se esiste qualche invocazione manuale/esterna fuori repo
2. se no, rimuovere `llm_worker.py` come legacy morto o sostituirlo con alias chiaro

#### Prima del commit (ripartenza domani)

Stato adesso:
1. `P1.5` chiuso e validato (`DIFFS=0` su 10 matchup)
2. `P2.5b` chiuso anche lato operativo (cron aggiunto)
3. `P2.5a` pronto nel codice, ma validato solo con sample import replay (`replay_archives=5`)
4. `P2.5c` in discovery: `llm_worker.py` non e' nel crontab macchina

Cose da fare domani prima del commit:
1. decidere se eseguire il full import storico di `replay_archives` (271 file) oppure lasciare il sample import come rollout operativo separato
2. se si fa il full import: validare di nuovo replay list/game su dataset completo
3. decidere se `llm_worker.py` resta fuori da questo commit o viene rimosso come legacy non schedulato
4. fare review finale del diff e spezzare i commit in blocchi logici (`P1.5`, `P2.5a`, `P2.5b/docs`)

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
| **P1.5 (15/04 sera)** | **FATTO** | No — digest vendorized, no code import runtime esterno |
| **P2.5a (15/04 notte)** | **IN CORSO** | Ancora parzialmente sì finche' non si decide/full-import replay storico |
| **P2.5b (15/04 notte)** | **FATTO** | No — runtime KC Spy legge PG, cron import aggiunto |
| **P2.5c** | DISCOVERY | `llm_worker` non risulta schedulato; legacy da verificare/rimuovere |
| F | DA FARE | Sì (analyzer 12K LOC → matchup reports) |
| G | FUTURO | Sì (OpenAI killer curves) |
| H | FUTURO | No (replay da PG + OpenAI) |

**Dopo Fase F:** `daily_routine.py` eliminabile. Solo `lorcana_monitor.py` resta.
**Dopo Fase G:** analisidef eliminabile completamente.
**Fase H:** indipendente da analisidef, richiede solo replay in PG + API OpenAI.

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
