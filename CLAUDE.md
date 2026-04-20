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
- **Frontend**: vanilla JS SPA monolitica in `frontend/dashboard.html` (~10.6K LOC), Chart.js, PWA (manifest + service worker). Il runtime live resta confinato a `frontend/`; `frontend_v2/` e' solo per lavoro parallelo e non fa parte del serving corrente.
- **Deploy**: VPS 2 vCPU 4GB RAM, manual uvicorn (systemd pending, vedi `TODO.md` §5)
- **Cron**: import matches ogni 2h, backup 03:00 daily, static importer domenica 04:45, import KC martedì 05:30, import_matchup_reports 05:30 daily, import_kc_spy 04:05 daily, monitor_kc_freshness 07:00 daily, generate_playbooks martedì 01:00
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

1. **Modifica backend**: edit `backend/services/*.py` o `backend/api/*.py` → restart uvicorn (`fuser -k 8100/tcp; nohup venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8100 --workers 1 &`)
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
| Pipeline killer curves batch (OpenAI) | analisidef/run_kc_production.py → import in App_tool PG martedì 05:30 |
| Replay viewer v1/v2 + Board Lab development | analisidef/build_replay*.py + App_tool/backend/services/replay_service.py |
| Business strategy, email duels.ink | analisidef/business/ + `BUSINESS_PLAN.md` root |

**Regola**: nuove feature utente-facing vanno in App_tool. `analisidef` resta R&D / batch bridge temporaneo; quando una feature ha valore prodotto stabile, va portata o riscritta in App_tool.

### Note operative aggiuntive

- `How to Respond` nelle killer curves deve restare **curve-specifico**: spiega come rispondere a quella linea avversaria, non al matchup in generale.
- Il testo user-facing del blocco `response` va scritto in **inglese**.
- `response.strategy` resta una one-line summary; il formato target supporta anche campi strutturati come `headline`, `core_rule`, `priority_actions`, `what_to_avoid`, `stock_build_note`, `off_meta_note`, `play_draw_note`, `failure_state`.
- `frontend/assets/js/team_coaching.js` non dipende piu' dal replay viewer pubblico per cache carte / image helper / short-name: usa helper locali e chiama solo le API App_tool (`/api/replay/cards_db`, `/api/v1/team/replay/*`, `/api/decks`) piu' `localStorage` browser per auth/deck context.

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

*Ultimo aggiornamento: 20 Apr 2026 — legacy frontend sealed, team coaching replay core decoupled, killer-curves response schema v2*
