# App_tool — Lorcana Monitor (metamonitor.app)

**Prodotto finale** per utente: dashboard analytics Disney Lorcana TCG. Questo repo contiene il backend FastAPI + frontend SPA + infra della app servita su `https://metamonitor.app`.

Scope: tutto ciò che tocca l'utente finale (feature dashboard, API, auth, billing, team, import). Per R&D e sperimentazione il repo companion è `../analisidef/`.

---

## Documenti chiave (leggi in ordine)

1. **[`docs/TODO.md`](docs/TODO.md)** — **Master TODO del prodotto**. Roadmap feature, gap competitivi, cleanup, infra, sprint plan. **Punto di partenza** per capire "cosa sta uscendo / cosa manca".
2. **[`ARCHITECTURE.md`](ARCHITECTURE.md)** — Target architetturale completo: 3 strati (schemas/pipelines/lib), API endpoints (§7.1), schema DB (§5.2), sicurezza 5 livelli (§8), feature pending frontend (§12).
3. **[`docs/MIGRATION_PLAN.md`](docs/MIGRATION_PLAN.md)** — Migrazione da `analisidef` → App_tool, con coupling runtime chiusi e coupling data-level D1/D2/D3 ancora aperti.
4. **[`ARCHITECTURE_EXPLANATION.md`](ARCHITECTURE_EXPLANATION.md)** — Spiegazione didattica (nginx, FastAPI, PostgreSQL, Redis, JWT, bcrypt) — per onboarding o review architetturale.

---

## Stack tecnico

```
Client (browser / PWA installabile)
  ↓ HTTPS (Let's Encrypt, nginx)
nginx (rate limit, fail2ban, UFW)
  ↓ proxy_pass :8100
uvicorn + FastAPI (backend/main.py)
  ↓ SQLAlchemy ORM + Redis cache
PostgreSQL (200K+ matches, 2822 cards, 1047 matchup reports)
```

- **Backend**: FastAPI + SQLAlchemy + PostgreSQL + Redis (rate limit + dashboard cache 2h stale-while-revalidate)
- **Frontend**: vanilla JS SPA monolitica in `frontend/dashboard.html` (~10.6K LOC), Chart.js, PWA (manifest + service worker). Il runtime live resta confinato a `frontend/`; il redesign in corso vive in `frontend_v3/` (workspace separato, non esposto in serving).
- **Deploy**: VPS 2 vCPU 4GB RAM, systemd unit `lorcana-api.service` (workers=2). Drop-in `lorcana-api.service.d/admin-token.conf` carica `/etc/apptool.env` (0600, contiene `APPTOOL_ADMIN_TOKEN`). Restart = `systemctl restart lorcana-api`.
- **Cron**: import matches ogni 2h, backup 03:00 daily, static importer domenica 04:45, KC batch/import martedì, import_matchup_reports 05:30 daily, import_kc_spy 04:05 daily, monitor_kc_freshness 07:00 daily, generate_playbooks martedì 01:00
- **Config runtime**: CORS da env (`CORS_ALLOW_ORIGINS`), leaderboard disabilitato se `DUELS_SESSION` manca, rate limit tier-aware via JWT nel middleware

---

## Layout frontend (7 tab)

Tutti i tab usano il pattern uniforme `monAccordion()` (titolo gold + "?" + chevron dx + toggle).

1. **Profile** — ink picker 6 colonne, Saved Decks, My Stats, Meta Radar, Best Plays (pending data)
2. **Monitor** — Deck Fitness strip + Matchup Matrix 14×14 (heatmap desktop, list mobile) + Deck Analysis + Best Format Players + Non-Standard Picks
3. **Coach V2** — Lore chart + Key Threats (pending Fase B LLM) + Opponent Playbook + How to Respond + Killer Curves + Opponent's Killer Cards + Trend by Turn + Replay Viewer
4. **Lab** — Mulligan Trainer + Card Impact (Correlation) + Card Impact (IWD) + Optimized Deck sidebar + Replay Viewer
5. **Team** — Roster, Board Lab (replay .gz upload + viewer animato)
6. **Community** — Stream, clips, schedule
7. **Events** — Mappa Leaflet, event cards

### Replay viewer pubblico logs — stato 16 Apr 2026

Il viewer pubblico `rv*` in `frontend/dashboard.html` non legge piu' solo il payload legacy di `ReplayArchive.games`.

Pipeline attuale:

1. `matches.turns` resta la source of truth raw
2. `backend/services/match_log_features_service.py` estrae e persiste `viewer_public_log`
3. `viewer_public_log.viewer_timeline` e' il contratto canonico del viewer logs
4. `GET /api/replay/public-log?match_id=...` restituisce il log normalizzato (lazy-build se mancante / stale)
5. il frontend replay logs preferisce `public-log`; fallback al builder legacy solo se manca `match_id`

Cose fatte oggi:

- `replay_archive_service.py` espone `match_id` / `external_id` su `/api/replay/list` e `/api/replay/game`
- `match_log_features_service.py` ha `viewer_timeline` con `seq`, `turn`, `type`, `source`, `targets`, `effect_text`, `fx`, `board_before`, `board_after`, `resources`
- il viewer logs usa `viewer_timeline` e non deve piu' reinterpretare i raw log in frontend
- aggiunta virtualizzazione di alcuni macro-eventi:
  - `attack -> damage -> banish`
  - `quest -> lore`
  - `spell play -> spell effect`
  - `ability trigger -> resolve`
- strip turni semplificata: un bottone per mezzo turno (`T1 Us`, `T1 Opp`, ecc.); click = autoplay della sequenza dettagliata di quel mezzo turno
- board resa piu' simile a un tavolo:
  - meta zones laterali (`deck`, `discard`)
  - inkwell dedicato
  - zone separate `Exerted Characters`, `Ready Characters`, `Items / Locations`
  - highlight source/target sulle carte del board

Limiti noti residui:

- il viewer logs non e' ancora al livello del `.gz` viewer Team
- `deck` / `discard` lato board sono ancora derived nel frontend, non campi canonici del decoder backend
- il board usa ancora layout HTML/CSS custom, non un engine board-state dedicato
- alcuni edge case di duplicate effects possono ancora richiedere fix mirati nel decoder backend

---

## Pattern UI fissati

- **`monAccordion(id, labelHtml, summaryHtml, contentHtml, opts)`**: factory di accordion uniforme. Opzioni: `desktopOpen` (default true), `openOnMobile`, `info: {title, body}`, `onOpen`, `sub`.
- **Header structure**: `<div class="mon-acc__hdr" role="button" tabindex="0">` con `.mon-acc__title-row` (label + info-btn inline) + chevron a destra.
- **Info button "?"** apre `showInfoSheet(title, body)` — bottom-sheet slide-up su mobile, modal fade-scale su desktop.
- **`monAccOnExpandResize()`** per accordion con Chart.js: dispatcha `window.resize` post-animazione (340ms) per re-render canvas alla prima apertura.
- **Fail closed**: ogni sezione ha guardia `if (data.length > 0)` → se campo blob vuoto, accordion non appare, zero noise.

### 3 principi UX non-negoziabili

Vedi anche `../.claude/memory/feedback_ux_principles.md`.

1. **Semplicità**: no overload visivo. KPI principale sempre visibile, dettagli a scomparsa.
2. **Parità iPhone/web**: responsive mobile-first. Breakpoint ≤640px iPhone, 641-900px tablet, >900px desktop. Nessuna feature desktop-only.
3. **Preferenza a scomparsa elegante**: default collassato, apre on-demand. Pattern `mon-acc` + bottom-sheet + expandable rows. Animazioni ≤320ms cubic-bezier.

---

## Endpoint pubblici principali

Vedi `ARCHITECTURE.md` §7.1 per la lista completa.

- `GET /api/v1/dashboard-data` — blob completo cache 2h (no auth, alimentazione principale frontend)
- `GET /api/v1/monitor/deck-fitness` — fitness ranking per perimetro (aggiunto 14/04)
- `GET /api/v1/lab/iwd/{our}/{opp}` — Improvement When Drawn per card (aggiunto 14/04, pubblico)
- `GET /api/v1/lab/card-scores/{our}/{opp}` — card scores correlation (auth pro+)

---

## Flusso lavoro tipico

1. **Modifica backend**: edit `backend/services/*.py` o `backend/api/*.py` → `systemctl restart lorcana-api` (unit systemd; journalctl per i log).
2. **Modifica frontend**: edit `frontend/dashboard.html` inline → FastAPI serve il file con `Cache-Control: no-cache`, hard refresh browser per bustare cache.
3. **Nuove feature**: seguire il pattern `monAccordion` per uniformità. Aggiungere endpoint pubblici se popolabili solo on-demand. Campi blob se pre-computabili via `snapshot_assembler`.
4. **Test backend**: smoke test via `venv/bin/python3 -c "from backend.services import X; ..."` o curl diretto su localhost:8100.
5. **Deploy**: push su produzione (oggi = edit in-place sul VPS, systemd pending).

### Nota operativa replay viewer

- Se tocchi il viewer logs, il file da guardare e' `frontend/dashboard.html`
- Se tocchi il contratto del viewer logs, i file da guardare sono:
  - `backend/services/match_log_features_service.py`
  - `backend/main.py` (`/api/replay/public-log`)
  - `backend/services/replay_archive_service.py`
- Il viewer `.gz` Team e il viewer logs pubblico sono separati; non confonderli

---

## Separazione con analisidef

| Scope | Repo |
|-------|------|
| Prodotto utente (dashboard, API, auth, billing) | **App_tool** (questo) |
| R&D dashboard sperimentale (porta 8060) | analisidef/daily/ |
| Pipeline killer curves batch (OpenAI) | App_tool `scripts/generate_killer_curves.py` → PG `killer_curves`; legacy `import_killer_curves.py` solo bridge da output analisidef |
| Replay viewer v1/v2 + Board Lab development | analisidef/build_replay*.py + App_tool/backend/services/replay_service.py |
| Business strategy, email duels.ink | analisidef/business/ + `BUSINESS_PLAN.md` root |

**Regola**: nuove feature utente-facing vanno in App_tool. `analisidef` resta R&D / batch bridge temporaneo; quando una feature ha valore prodotto stabile, va portata o riscritta in App_tool.

### Note operative aggiuntive

- `How to Respond` nelle killer curves deve restare **curve-specifico**: spiega come rispondere a quella linea avversaria, non al matchup in generale.
- Il testo user-facing del blocco `response` va scritto in **inglese**.
- `response.strategy` resta una one-line summary; il formato target supporta anche campi strutturati come `headline`, `core_rule`, `priority_actions`, `what_to_avoid`, `stock_build_note`, `off_meta_note`, `play_draw_note`, `failure_state`.
- `frontend/assets/js/team_coaching.js` non dipende piu' dal replay viewer pubblico per cache carte / image helper / short-name: usa helper locali e chiama solo le API App_tool (`/api/replay/cards_db`, `/api/v1/team/replay/*`, `/api/decks`) piu' `localStorage` browser per auth/deck context.

### Set 12 readiness (S0 applicato, 2026-04-22)

La Fase S0 di `docs/SET12_MIGRATION_PLAN.md` è entrata in repo. Cosa cambia a livello operativo oggi:

- **Folder `SETNN` futuro = automatico**: `backend/workers/match_importer.py` e `scripts/import_matches.py` usano regex `^SET(\d+)$` → `perimeter=setNN`, `format=core`. Zero code change al reveal.
- **Digest generator env-driven (hard cutover)**: `pipelines/digest/generator.py` filtra perimeter con `_ACTIVE_CORE_PERIMETERS = {APPTOOL_DEFAULT_CORE_PERIMETER, top, pro, friends}`. Post-flip env a `set12`, il digest vede **solo** `set12+top+pro+friends`: i match `set11` restano in DB come storico ma sono invisibili a digest/KC/matchup reports. Policy decisa 22/04: hard cutover, niente overlap 30gg (KC deve operare strettamente sul set attivo).
- **Default core perimeter env-driven**: `APPTOOL_DEFAULT_CORE_PERIMETER` (default `set11`). Cambiarlo a release-day senza toccare codice. Blob espone `default_core_perimeter`; frontend legge via `getCoreDefaultPerimeter()` con fallback `'set11'`.
- **SET_MAP estensibile**: `EXTRA_SET_CODE=<3-letter> EXTRA_SET_NUM=12` oppure `EXTRA_SET_MAP='{"XYZ":"12","ABC":"13"}'` JSON.
- **Admin endpoint cache invalidation**: `POST /api/v1/admin/reset-legality-cache` + `POST /api/v1/admin/refresh-dashboard` con doppio gate (JWT admin **o** `X-Admin-Token` shared via `APPTOOL_ADMIN_TOKEN` env). Consumati dal wrapper `scripts/refresh_static_and_reset.sh` (sostituto del cron `static_importer` diretto la domenica 04:45).
- **Canary `scripts/monitor_unmapped_matches.py`**: diff FS vs DB vs skip_cache → alert mail se appare un nuovo folder, drop_rate > 10%, o `perimeter='other'` > 50/die. Cron target 07:05 UTC.
- **Migration `7dec24a98839` (partial index future-proof)**: scritta ma **non ancora applicata** sul DB produzione. Va eseguita con `alembic upgrade 7dec24a98839` (NON `upgrade head` — la head successiva `7894044b7dd3` è la cassetto S0.5 che aborta senza env var di release).
- **Migration `7894044b7dd3` (Set12 launch)**: in cassetto, deve rimanere non applicata fino all'annuncio Ravensburger.

Azioni VPS eseguite 2026-04-22 07:45 UTC:
1. `alembic upgrade 7dec24a98839` — indice `idx_matches_lookup` ora con `WHERE perimeter <> 'other'` (9.8 MB, copre 303399/303402 righe).
2. `/etc/apptool.env` (0600) con `APPTOOL_ADMIN_TOKEN` (64 hex chars). Drop-in systemd `lorcana-api.service.d/admin-token.conf` carica l'env.
3. `systemctl restart lorcana-api` + smoke test endpoint admin: token valido → 200, assente/sbagliato → 401.
4. Crontab aggiornato: Dom 04:45 ora esegue `scripts/refresh_static_and_reset.sh` (backup precedente in `/tmp/crontab_backup_1776843879.bak`).
5. Nuova cron 07:05 UTC: `scripts/monitor_unmapped_matches.py`.

La migration cassetto `7894044b7dd3_set12_launch_meta_epoch.py` NON è stata applicata (resta dormant, guard env). Head alembic = `7dec24a98839`.

**Prossima finestra rotation attesa — Settembre 2026** (Set 12 release Ravensburger, non ancora annunciato ufficialmente). Al D-day: `SET12_RELEASE_DATE=2026-09-DD SET12_LEGAL_SETS=3,4,5,6,7,8,9,10,11,12 alembic upgrade 7894044b7dd3` + `systemctl restart lorcana-api` + `curl -X POST -H "X-Admin-Token: ..." /api/v1/admin/reset-legality-cache`. Default env già allineato con `[3..12]` (sets 1-2 fuori).

### KC meta-relevance guard (applicato 2026-04-24 pm)

Rotation preemptiva applicata sul DB produzione: `meta_epochs.Set11 settled.legal_sets` ristretto da `[1..11]` a `[3..11]` (sets 1-2 effettivamente fuori meta oggi, il cassetto Set 12 li esclude già di default, quindi forward-compatible a Settembre).

Doppio guard ora attivo in `pipelines/kc/`:
- **Prompt-time** (`build_prompt._build_meta_relevance_guard`): elenca a GPT le carte out-of-meta presenti nel digest (0 plays in 30gg / < soglia 20 plays). Passata al prompt insieme a `_build_core_legality_guard` (rotation). Risultato: GPT non suggerisce carte pre-rotation o fuori dal meta corrente.
- **Post-filter** (`scripts/generate_killer_curves._strip_non_meta_cards`): stripping safety-net su `response.cards` + `sequence.plays` prima dell'upsert in PG.

Helper: `pipelines/kc/meta_relevance.get_meta_relevant_cards(db, format, days=30, min_plays=20)` — cached per-format, conta CARD_PLAYED events dalla `matches` table. Core ha 876 carte in meta oggi.

Admin endpoint `/api/v1/admin/reset-legality-cache` invalida ora anche `kc_meta_relevant` + `meta_relevance_cache`.

One-shot `scripts/reclean_kc_meta.py` già girato sui dati esistenti: 209 card refs strippate su 36 matchup Core (134 righe), 66 curve ora con `response.cards=[]` (GPT aveva scelto solo carte non-meta in quei casi — attendo prossima run Martedì 01:30 che col prompt guard produrrà output pulito in origine).

Sync `scripts/refresh_kc_matchup_reports.py` — copia rapida `killer_curves` → `matchup_reports` senza full regen matchup_reports (12 min → 5 sec).

### KC LLM request optimization (applicato 2026-04-25)

Pipeline operativa: `scripts/generate_killer_curves.py` legge digest nativi da `output/digests`, costruisce prompt con `pipelines/kc/build_prompt.py`, chiama OpenAI, post-filtra e upserta in PG `killer_curves`.

Cambi a basso impatto entrati:

- **JSON mode in produzione**: la call OpenAI usa `response_format={"type": "json_object"}`.
- **Cache key LLM**: nuove righe KC salvano in `meta` `digest_hash`, `prompt_contract_hash`, `schema_version`, `prompt_hash`, costo/tokens e `run_id`.
- **Skip non-forzato**: nei run senza `--force`, se `digest_hash + prompt_contract_hash + schema_version` coincidono con la current row, la matchup viene saltata prima della call LLM. `--force` rigenera sempre.
- **Payload V3 nella stessa call**: prompt e schema supportano `killer_curves[].v3_payload` e `killer_curves[].self_check`.
- **Metriche di completezza**: `meta` include `response_v2_complete`, `v3_payload_complete`, `self_check_complete` e percentuali.
- **No token leak**: `run_meta` viene usato per cache/stability ma non viene passato nel prompt come contesto storico.

Operativo post-batch:

1. `scripts/generate_killer_curves.py --format all` o `--force` se si vuole rebuild completo.
2. `scripts/refresh_kc_matchup_reports.py --format all` per portare KC in `matchup_reports`.
3. Refresh `/api/v1/dashboard-data?refresh=true` per V3.

Doc critico: `docs/KILLER_CURVES_BLINDATURA_V3.md`.

### Privacy Layer V3 (live in produzione dal 2026-04-24)

Delta additivo per chiudere ownership/privacy gap prima che V3 vada live. Documentato in `ARCHITECTURE.md §24 "Sensitive Data & Privacy Architecture — V3 Launch Layer"` con subsection `§24.11 Applied State`. Piano di porting Legacy → V3 in `docs/MIGRATION_PLAN.md` (Appendice Z).

**Backend** — live sul service `lorcana-api`:

- Alembic head: `9a1e47b3f0c2` — team_replays: +`user_id`, +`is_private`, +`consent_version`, +`uploaded_via`, +`shared_with` + 2 indici (commit `5f4b72d`)
- Model update (`7aafab1`), deps `require_replay_access` / `require_replay_owner` (`1e7f6b2`), wiring access-control `/api/v1/team/replay/*` (`5999d66`)
- `backend/services/replay_anonymizer.py` + wiring in `replay_archive_service` + `match_log_features_service` (`6f40d8d`) — response JSON di `/api/replay/list|game|public-log` restituiscono `"Player"` / `"Opponent"` invece dei nick raw
- `POST /api/v1/user/interest` (`f032129`), `POST /api/v1/user/consent` (`1abbdd0`), GDPR export esteso con `team_replays` (`6043444`)

**Frontend legacy** — live dopo SW invalidation:

- Consent modal pre-upload in `frontend/assets/js/team_coaching.js` (`1abbdd0`)
- Footer disclaimer + `frontend/about.html` (`5d986e5`)
- Copy sanitization: no menzioni `duels.ink` in privacy surfaces + fair-use card images + no MMR/ELO numeric thresholds nella info popup (`1c2d5b9`, `d13fdc9`)
- Email swap `legal@metamonitor.app` → `monitorteamfe@gmail.com` (`1c2d5b9`)
- Service worker `CACHE_NAME=lorcana-privacy-v4` + strategia **network-first per HTML** (`e076524`) — da ora edit a dashboard.html/about.html arrivano on reload senza bump

**Apply sul VPS (2026-04-24)**:

1. Ownership fix (prerequisito): `team_replays` + `team_roster` erano owned by `postgres`, trasferite a `lorcana_app` via `ALTER TABLE ... OWNER TO lorcana_app` eseguito come postgres. Le altre 26 tabelle `public.*` erano già owned by `lorcana_app`. Fix raccomandato anche per future migration sulle team tables.
2. `alembic upgrade 9a1e47b3f0c2` (13:30 UTC). Backup pre-M1 della singola riga esistente: `/tmp/team_replays_pre_M1_20260424_132428.json` (player `Seton`, rimasto orphan).
3. Cleanup: killato `uvicorn` orphan PID `3661913` (avviato manualmente 2 giorni prima, detached da systemd) che teneva la porta 8100 occupata → systemd in crash-loop. `daemon-reload` (era pendente per il drop-in `admin-token.conf` del 22 Apr) + `systemctl restart lorcana-api` (13:28 UTC). Service live PID `810410` + workers.
4. Smoke test A10 — `scripts/privacy_smoke_test.py`: T1 (schema) + T4 (anonymization API) PASS automatizzati. T2/T3/T5/T6/T7 coperti da manual browser check (checklist consegnata 24/04) — richiederebbero 2 user test + 1 admin con JWT.

**Ancora da fare (azioni ops, non-code)**:

- Alias mail `legal@metamonitor.app` → `monitorteamfe@gmail.com` su Cloudflare Email Routing (10 min DNS). Quando è up, swappare indietro le 3 occorrenze nel footer/about.
- Porting V3 di consent modal + disclaimer + copy sanitization — vedere `docs/MIGRATION_PLAN.md` Appendice Z per checklist completa.

**Path reali**:
- Tutti gli endpoint user sono sotto prefix `/api/v1/user/*` — `/profile`, `/preferences`, `/nicknames`, `/decks`, `/export`, `/interest`, `/consent`. Il primo draft di §24 usava `/api/user/*` per una diagnosi errata del prefix: in verifica post-deploy del 24/04 il consent modal legacy restituiva 405, e `ALLOWED_PREFS` whitelist droppava `consents` + `interest_to_pay` dall'export GDPR. Risolto in commit `05845e3` (fix path in `team_coaching.js` + whitelist `user_service.py` + smoke test script). Doc allineati dopo: ARCHITECTURE §24.8+§24.11, CLAUDE §Privacy Layer V3, MIGRATION_PLAN Appendice Z.
- `POST /api/v1/user/consent` — endpoint aggiuntivo non previsto dal §24 first draft, aggiunto durante implementazione come dipendenza del consent modal Board Lab (legacy + V3). Schema: `{ kind: "tos"|"privacy"|"replay_upload"|"marketing", version: str }` → scrive `preferences.consents.<kind> = { version, accepted_at }`.

**Head alembic dopo M1**: 2 head parallele (`7894044b7dd3` Set12 cassetto dormant, `9a1e47b3f0c2` privacy — current). Alembic upgrade richiederà revision esplicita (NON `upgrade head`) finché il cassetto Set12 resta dormant.

---

## Memoria persistente rilevante (`~/.claude/projects/*/memory/`)

- `feedback_analisidef_scope.md` — App_tool è il prodotto principale
- `feedback_ux_principles.md` — 3 principi UX (semplicità / parità iPhone-web / a scomparsa)
- `feedback_claude_subscription_not_api.md` — subscription OAuth Max per batch, mai crediti API
- `feedback_openai_for_kc.md` — killer curves via OpenAI gpt-5.4-mini
- `project_apptool_status.md` — stato 136K+ → 200K+ match in PG
- `project_independence_plan.md` — Fase A-H migrazione
- `project_coaching_tool.md` — Board Lab replay upload

---

*Ultimo aggiornamento: 25 Apr 2026 — KC LLM request optimization applicata: JSON mode in produzione, cache key `digest_hash + prompt_contract_hash + schema_version`, payload `v3_payload/self_check`, metriche completezza in `killer_curves.meta`. Privacy Layer V3 live dal 24 Apr 2026; resta alias mail `legal@` + porting V3 (vedere `docs/MIGRATION_PLAN.md` Appendice Z).*
