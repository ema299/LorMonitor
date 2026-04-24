# App_tool — TODO Prodotto

Master TODO del prodotto finale `metamonitor.app`. Questo file vive in App_tool (non in analisidef) perché qui abita il prodotto utente.

Linka a:
- [`ARCHITECTURE.md`](../ARCHITECTURE.md) — architettura target, endpoint, schema DB
- [`MIGRATION_PLAN.md`](MIGRATION_PLAN.md) — migrazione runtime da analisidef (Fase F-H futuro)
- [`SET12_MIGRATION_PLAN.md`](SET12_MIGRATION_PLAN.md) — readiness per release Set 12 (capture match transition window, meta_epochs, dual perimeter)
- [`KC_REVIEW.md`](KC_REVIEW.md) — review costo/qualità killer curves (schema v2, lingua EN, cost tracking)
- [`CLAUDE.md`](../CLAUDE.md) — entry point operativo (layout, pattern UI, flow lavoro)

**Separazione di scope**:
- `analisidef/` = ambiente R&D, dashboard porta 8060 per sperimentazione, generazione killer curves + replay viewer
- `App_tool/` = **prodotto finale** (`metamonitor.app`), questo TODO qui

---

## 1. Feature completate (14 Apr 2026)

| Feature | Dove | Doc |
|---------|------|-----|
| **Deck Fitness Score** (strip 0-100 meta-weighted) | Monitor tab | `ARCHITECTURE.md` "Monitor redesign" + §7.1 endpoint `/deck-fitness` |
| **Matchup Matrix 14×14** (heatmap desktop + list mobile, click → Coach V2) | Monitor tab | `ARCHITECTURE.md` "Monitor redesign" |
| **Card Impact (IWD)** causal drawn-by-T3 | Lab tab | `ARCHITECTURE.md` "Card Impact (IWD) — Lab tab" + §7.1 endpoint `/iwd` |
| **Uniformità accordion** gold-title + "?" + chevron dx | Monitor, Coach V2, Lab (10 accordion) | `ARCHITECTURE.md` "UI uniformity pass" |
| **Cross-tab navigation** click matrix cell → Coach V2 pre-selected | Monitor → Coach V2 | `CLAUDE.md` pattern cross-tab |

**Zero regressione**: tutti i cambi additivi. Pattern `monAccordion` retrocompatibile (default `desktopOpen: true`).

---

## 1b. Feature completate (16 Apr 2026)

| Feature | Dove | Doc |
|---------|------|-----|
| **Meta Ticker** scrolling (Bloomberg-style) | Monitor tab (sopra Deck Fitness) | NEWS/VIDEO/BUZZ/META/LIVE labels, pause on hover |
| YouTube RSS news feed (13 canali, auto 3h) | `scripts/fetch_news_feed.py` | Tier 1+2 EN + 2 affiliati IT (ToL, IkB), filtro keyword multi-TCG |
| Twitch Helix integration (Lorecast) | `scripts/fetch_news_feed.py` | LIVE pulse + VOD recenti (attende credenziali dev.twitch.tv) |
| News admin API | `backend/api/news.py` | GET `/api/v1/news/ticker` (pub), POST+DELETE (admin) |
| Tabella `news_feed` PG | `backend/models/news_feed.py` | UUID PK, label/source/title/url/channel, expires_at 24h, partial unique (source,url) |
| **Format toggle in tab bar** (desktop) | Monitor/Coach/Lab tabs | Core/Infinity a dx nella tab bar desktop, format-bar mobile |
| **Copy decklist pulito** (import-friendly) | Monitor Best Players + Lab Optimized | Rimossi `*` e `?` dal copy text, formato `qty CardName` |
| **Copy buttons mobile-friendly** | Monitor Best Players | Info + bottoni su righe separate, `flex:1`, min-height 34px |
| **Standard List senza scroll** | Profile tab | Rimosso max-height/overflow, blocco unico visibile |

---

## 2. Feature pending — Benchmark competitivo

Dal benchmark vs tool TCG (17Lands, HSReplay, Untapped.gg, Firestone, Limitless Labs, inkDecks, Duels.ink, Lorcanito, Metafy) del 14/04/2026.

**Differenziatori nostri unici** (nessun competitor ha): threats LLM, killer curves multi-profilo, Board Lab replay animato, multi-language (IT/DE/ZH/JA), pre-match cheatsheet, Events + Community hub, Deck Fitness Score, Card Impact IWD, Matchup Matrix NxN cliccabile.

**Gap da colmare**:

| # | Feature | Competitor leader | Effort | Priorità | Sblocco |
|---|---------|------------------|--------|----------|---------|
| A | Replay v2 animato dashboard viewer (port Board Lab → Coach V2 + Lab) | Duels.ink (solo .gz raw) | 5-7 dev days | Alta | Nessuno |
| B | **Sideboard LLM cheatsheet + Copy Discord** | Metafy (human coach pagamento) | 4-5 dev days + ~$3-5/mese OpenAI | **CRITICAL PATH** | Fase B LLM batch (attiva anche Key Threats + How to Respond) |
| C | Public Player Profile `/player/<nick>` shareable | Untapped.gg (2024, driver virale) | 6-8 dev days | Media | Privacy review + opt-in flow + email duels.ink |
| D | Tournament path / conversion rate per round | Limitless Labs | 2-3 dev days | Bassa | Dati PRO/TOP già disponibili |
| E | In-game overlay live tracking | HSReplay, Firestone, Untapped | Strutturale | **No-go** | Duels.ink è browser chiuso |
| F | VOD annotation collaborative review | Insights.gg | Scope ampio | Post-MVP | — |

## 2.0. Priorità operative correnti

- **P0** = rischio produzione / qualità dato / verifica post-fix
- **P1** = backlog vicino al prodotto, utile nelle prossime iterazioni
- **P2** = medio termine, infra o feature più ampie

## 2.1. Replay viewer logs pubblico — update 16/04/2026

Stato reale dopo la sessione di oggi:

- il viewer logs pubblico ora e' **PG-first**
- `/api/replay/list` e `/api/replay/game` espongono `match_id`
- `/api/replay/public-log?match_id=...` serve `viewer_public_log` derivato da PG
- `viewer_public_log.viewer_timeline` e' il contratto canonico del viewer logs
- il frontend `rv*` in `frontend/dashboard.html` usa `viewer_timeline` e fallbacka al legacy solo se il `public-log` manca

Lavori fatti oggi:

| Task | Dove | Stato | Note |
|------|------|-------|------|
| `match_id` / `external_id` nel replay viewer pubblico | `backend/services/replay_archive_service.py` | Fatto | collega archive PG ai match reali |
| Endpoint `GET /api/replay/public-log` | `backend/main.py` | Fatto | lazy-build se row assente o vecchia |
| `viewer_timeline` canonico | `backend/services/match_log_features_service.py` | Fatto | `source/targets/fx/board_before/after/resources` |
| Viewer logs legge `viewer_timeline` | `frontend/dashboard.html` | Fatto | niente bypass raw nel path principale |
| Micro-step virtuali | `frontend/dashboard.html` | Fatto | `attack→damage→banish`, `quest→lore`, `spell/effect`, `ability/resolve` |
| Strip turni per mezzo turno | `frontend/dashboard.html` | Fatto | `T1 Us`, `T1 Opp`; click = autoplay di quel mezzo turno |
| Board pass stile tavolo | `frontend/dashboard.html` | Parziale | zone `exerted/ready/items`, inkwell, deck/discard |

TODO residui specifici viewer logs:

| Task | Dove | Effort | Note |
|------|------|--------|------|
| Canonicalizzare `deck` / `discard` nel decoder backend | `backend/services/match_log_features_service.py` | 0.5-1 dev day | oggi sono ancora derived nel viewer |
| Inkwell con identita' carta stabile + stato `spent` per carta | backend decoder + viewer | 1-2 dev days | serve per transizioni precise "gira l'ink usato" |
| Board renderer con slot stabili (meno `flex-wrap`) | `frontend/dashboard.html` | 2-3 dev days | e' il passo vero verso "come duels" |
| Frecce board-level vere (coordinate sorgente→target) | frontend viewer | 1-2 dev days | oggi highlight + pannello, non arrow geometry |
| Dedup effect edge cases nel decoder backend | `match_log_features_service.py` | 0.5-1 dev day | Bobby/T2 e simili oggi mitigati in frontend |

---

## 3. Frontend accordion in attesa di dati backend

Sezioni **già implementate** in `frontend/dashboard.html` con pattern `monAccordion` uniforme, guardia `if (data.length > 0)` → **"fail closed"** (non appaiono finché il campo blob è vuoto).

Documento di riferimento: `ARCHITECTURE.md` §12.

| Sezione | Tab | Campo blob atteso | Sblocco |
|---------|-----|-------------------|---------|
| **Key Threats** | Coach V2 | `matchup_analyzer.<deck>.vs_<opp>.threats_llm.threats[]` | Fase B LLM batch |
| **How to Respond — OTP vs OTD** | Coach V2 | `matchup_analyzer.<deck>.vs_<opp>.killer_responses[]` | Fase B LLM pass 3 + importer update |
| **Best Plays** | Profile | `best_plays`, `best_plays_infinity` | Query Python su killer curves avversarie (1 dev day) |

**Principio**: nessuna sezione rimossa anche se il dato manca. Il rebuild blob (cache 2h) popola automaticamente al prossimo batch senza richiedere modifiche frontend.

---

## 4. P1 — Cleanup immediato (low-effort, high-value)

| Task | Dove | Effort | Rischio |
|------|------|--------|---------|
| Best Plays query Python (su killer curves avversarie) | nuovo service `best_plays_service.py` + snapshot_assembler | 1 dev day | Zero (additivo) |
| Uniformità 4 `section-title` in Community+Events tab | `frontend/dashboard.html` | 30 min | Zero |
| Uniformità pattern Team tab (`player-card` → `monAccordion`) | `frontend/dashboard.html` | 1-2 dev days | Medio |

**Audit 20/04/2026: gia' chiusi e rimossi dall'open backlog**
- `tech_choices` duplicato nel blob per-perimetro: rimosso da `backend/services/snapshot_assembler.py`
- campo top-level `analysis`: verificato dead e rimosso dal blob runtime

## 4.0-bis. P0 — Set 12 readiness (Fase S0, 22/04/2026)

Piano consolidato in [`SET12_MIGRATION_PLAN.md`](SET12_MIGRATION_PLAN.md) v3. Tutto il codice S0 è in repo.

| Task | Stato | Dove |
|------|-------|------|
| Regex folder/queue future-proof (SETNN, S12-BO*) | FATTO | `backend/workers/match_importer.py`, `scripts/import_matches.py` |
| Digest generator `_is_core_perimeter()` (SQL regex) | FATTO | `pipelines/digest/generator.py` |
| Canary filesystem-level FS vs DB | FATTO | `scripts/monitor_unmapped_matches.py` |
| `SET_MAP` estensibile via env | FATTO | `backend/workers/static_importer.py` |
| Admin endpoint `reset-legality-cache` + `refresh-dashboard` | FATTO | `backend/api/admin.py`, `backend/deps.py` |
| Wrapper `refresh_static_and_reset.sh` | FATTO | `scripts/refresh_static_and_reset.sh` |
| `default_core_perimeter` nel blob + helper frontend | FATTO | `backend/services/snapshot_assembler.py`, `frontend/dashboard.html` |
| Migration S0.5 `set12_launch` in cassetto (guard env) | FATTO | `db/migrations/versions/7894044b7dd3_*.py` |
| Migration S0.6 partial index future-proof | FATTO (codice + DB) | `db/migrations/versions/7dec24a98839_*.py` + `backend/models/match.py:44`. `alembic current = 7dec24a98839`. |
| E2E dry-run SETXX → `perimeter=setXX`/`format=core` | VERIFICATO | — |
| Token admin + systemd drop-in | FATTO | `/etc/apptool.env` (0600) + `lorcana-api.service.d/admin-token.conf`. Smoke test endpoint: 200 con token, 401 senza. |
| Crontab Dom 04:45 → wrapper | FATTO | backup `/tmp/crontab_backup_1776843879.bak`. |
| Cron canary 07:05 UTC | FATTO | `scripts/monitor_unmapped_matches.py` installato. |

**S0 chiuso end-to-end 22/04/2026 07:45 UTC.** Azioni VPS tutte applicate — vedi `SET12_MIGRATION_PLAN.md` §9 per la quick-verify checklist.

## 4.0. P0 — Follow-up incidente 20/04/2026

Issue emersi in produzione su metamonitor.app dopo snapshot InkDecks parziali e alcune KC Core contaminate da carte Infinity.

| Task | Dove | Effort | Note |
|------|------|--------|------|
| Alert "snapshot InkDecks sparse" | `scripts/monitor_kc_freshness.py` | Fatto | aggiunto guard su streak di snapshot con archetipi sotto soglia |
| Audit `decks_db_builder.py` fuori repo | `/mnt/HC_Volume_104764377/finanza/Lor/decks_db_builder.py` | Fatto | trovati timeout browser; aggiunti retry + sparse snapshot guard |
| Rebuild/verify blob dopo fix static data | runtime/cache | Fatto | blob assemblato live contro PG: `consensus_decks=15`, `reference_decks=15` |
| Verifica batch KC core post-fix | `scripts/generate_killer_curves.py` + PG `killer_curves` | 10-20 min | controllare matchups RS/rosso-blu senza carte fuori rotazione |

**Nota operativa 20/04/2026**
- `snapshot_20260420.json` e' stato recuperato dal contenuto dell'ultimo snapshot sano (`snapshot_20260416.json`) per non lasciare come latest un file sparse a 5 archetipi

## 4.1. Audit chiuso — Rogue / scouting

- `rogue_scout` risulta gia' fatto lato prodotto; rimosso dall'open backlog su richiesta utente il `20/04/2026`
- endpoint/admin preview presente: `GET /api/v1/monitor/rogue-scout-preview`
- backlog rogue UI/backfill non piu' trattato come open in questo file

## 4.2. P2 — Lab tab — Deck Comparator (piramide)

Endpoint backend pronto: `GET /api/v1/lab/tournament-lists/{deck}` (15 liste da inkdecks snapshot).

**Layout**:
- **Desktop**: piramide — My List centrata in alto (griglia carte max 3-4 colonne, immagini zoomabili), sotto max 4 liste torneo affiancate con diff evidenziata (verde = add, rosso = cut)
- **Mobile**: My List in alto + 4 badge cliccabili sotto; click badge → overlay fullscreen con lista + diff
- Stesso formato carte del Profile (gallery thumbnails zoomabili)
- My List da saved deck Profile (o consensus/standard se nessun saved deck)
- Filtro liste torneo da dropdown (player + evento + data)

| Task | Dove | Effort | Note |
|------|------|--------|------|
| Frontend comparatore desktop (piramide + diff) | `frontend/dashboard.html` Lab tab | FATTO 20/04/2026 | CSS griglia + JS fetch + diff calc |
| Frontend comparatore mobile (badge → fullscreen) | `frontend/dashboard.html` | OPEN | Oggi responsive stack/chips, manca bottom-sheet fullscreen dedicato |
| Integrare in Lab tab come prima sezione | `frontend/dashboard.html` | FATTO 20/04/2026 | Prima di Mulligan Trainer |

---

## 5. P2 — Infrastruttura pre go-pubblico serio

| Task | Status | Rischio se non fatto |
|------|--------|----------------------|
| **systemd service** `lorcana-api` per uvicorn | Da verificare | docs in drift: `CLAUDE.md` lo dà pending, `ARCHITECTURE.md` lo dà fatto |
| **CORS stringere** (oggi permissivo) | Non fatto | Bassa priorità finché no API pubbliche cross-origin; da stringere pre go-pubblico |
| **OAuth Discord bridge** (per opt-in Public Profile) | Non pianificato | Blocca feature #C |
| **Email duels.ink** per allineamento legale | Scritta in `../analisidef/business/email_duels_ink_v4.md`, non ancora spedita | Blocca feature #C pubblico |
| **Rate limit per endpoint pubblici nuovi** (`/iwd`, `/deck-fitness`) | Ereditato dal middleware Redis globale | OK |

---

## 6. P2 — Migrazione da analisidef (Fase F-H)

Dettaglio in [`MIGRATION_PLAN.md`](MIGRATION_PLAN.md).

- **Sprint-1 Mossa A FATTO 15/04/2026**: Blind Playbook in PG + endpoint + accordion Profile (importer bridge da analisidef)
- **Sprint-1 Mossa B (DA FARE)**: porting nativo `gen_deck_playbook.py` in App_tool + cron settimanale + chiave OpenAI propria. Vedi [`SPRINT_1_MOSSA_B.md`](SPRINT_1_MOSSA_B.md).
  - **⚠️ CAVEAT LINGUA**: il prompt analisidef forza output `italiano fluido`. App e' inglese-only. Quando porteremo il generator in App_tool, modificare il prompt in `fluent English` e tutte le istruzioni (vedi `SPRINT_1_MOSSA_B.md` §3 e memoria `feedback_app_language_english.md`). Le 24 narrative attualmente in PG sono in italiano e resteranno tali fino a Mossa B.
- **Fase F (DA FARE)**: matchup report refresh autonomo (oggi dipende ancora da `analisidef/dashboard_data.json` importato da cron)
- **Fase G (FUTURO)**: killer curves batch autonomo (oggi parte da `analisidef/output/killer_curves_*.json` via `import_killer_curves.py`). **Anche qui prompt deve produrre EN**.
- **Fase H (FUTURO)**: player scouting reports LLM nativo App_tool. **Anche qui prompt EN**.

---

## 7. Roadmap estesa Q2-Q3 2026

1. **Sprint 1 (2-3 giorni) — Cleanup immediato**
   - Best Plays query Python (§4)
   - 4 section-title Community+Events uniformi (§4)
   - Cleanup `tech_choices` + `analysis` (§4)

2. **Sprint 2 (1 settimana) — Feature B Sideboard LLM** ⭐ critical path
   - Pipeline `run_all_reviews.sh` batch settimanale OpenAI (~$3-5/mese)
   - Prompt B esteso con blocchi strutturati `<!-- THREATS_LLM -->`, `<!-- KILLER_RESPONSES -->`, `<!-- SB_PLAN -->`
   - Parser in `import_matchup_reports.py` per popolare campi blob
   - Render SB_PLAN nel Coach V2 con bottone "Copy to Discord"
   - **Sblocca 3 sezioni Coach V2 con un cantiere solo** (Key Threats + How to Respond + Sideboard)

3. **Sprint 3 (1-2 settimane) — Feature A Replay v2 animato**
   - Port animazioni da Board Lab (`team_coaching.js`) in modulo condiviso `replay_anim_core.js`
   - Integrazione nel Replay Viewer dashboard (Coach V2 + Lab)
   - Feature flag `localStorage.rv_anim_v2` per rollback rapido

4. **Sprint 4 (mezza giornata) — Infra pre-pubblico**
   - systemd service `lorcana-api` (§5)
   - CORS stringere (§5)

5. **Sprint 5 (Q3, 2-3 settimane) — Feature C Public Profile**
   - Prerequisito: email duels.ink spedita + OK ricevuto
   - Opt-in registry `public_profiles.json`
   - 4 endpoint pubblici + pagina `/player/<nick>` SSR-like
   - OG meta tags per Discord/Twitter embed
   - Rate limit aggressivo

---

## 8. Principi architetturali invariabili

- **App_tool = prodotto, analisidef = R&D** (`../.memory/feedback_analisidef_scope.md`)
- **UX: semplicità + parità iPhone/web + componenti "a scomparsa"** (`../.memory/feedback_ux_principles.md`)
- **Fail closed sul frontend**: guardia `if (data.length > 0)` → nessuna sezione rotta quando i dati mancano
- **Additivo, mai breaking**: nuovi endpoint + nuovi blob fields + `monAccordion` opzioni retrocompatibili
- **Cache blob 2h + stale-while-revalidate**: feature nuove si propagano automaticamente al prossimo rebuild senza downtime

---

*Ultimo aggiornamento: 20 Apr 2026 — dopo sessione "incident hardening static data + KC legality + priority pass"*
