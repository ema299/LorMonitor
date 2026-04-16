# App_tool — TODO Prodotto

Master TODO del prodotto finale `metamonitor.app`. Questo file vive in App_tool (non in analisidef) perché qui abita il prodotto utente.

Linka a:
- [`ARCHITECTURE.md`](../ARCHITECTURE.md) — architettura target, endpoint, schema DB
- [`MIGRATION_PLAN.md`](MIGRATION_PLAN.md) — migrazione runtime da analisidef (Fase F-H futuro)
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

## 4. Cleanup immediato (low-effort, high-value)

| Task | Dove | Effort | Rischio |
|------|------|--------|---------|
| Best Plays query Python (su killer curves avversarie) | nuovo service `best_plays_service.py` + snapshot_assembler | 1 dev day | Zero (additivo) |
| Uniformità 4 `section-title` in Community+Events tab | `frontend/dashboard.html` | 30 min | Zero |
| Rimuovere `tech_choices` duplicato dal blob per-perimetro | `backend/services/snapshot_assembler.py` | 30 min | Zero (non usato) |
| Verifica/rimuovi campo `analysis` top-level vuoto | grep usages → se dead, cleanup | 30 min | Verifica prima |
| Uniformità pattern Team tab (`player-card` → `monAccordion`) | `frontend/dashboard.html` | 1-2 dev days | Medio |

## 4.1. Scouting meta / rogue decks

Discovery 16/04/2026 da `analisidef`:

- `lib/rogue_scout.py` ha valore prodotto reale: migliora molto il vecchio "emerging decks" con Wilson LB, baseline player/deck, filtri anti-noise e bucket distinti (`emerging_archetypes`, `solo_brews`, `tier0_killers`, `off_meta_validated`).
- In App_tool il port PG-first esiste gia' in `backend/services/rogue_scout_service.py` ed e' esposto come endpoint admin/debug `GET /api/v1/monitor/rogue-scout-preview`; la UI ancora non lo usa.
- Blocker dati emerso dallo smoke test reale: `cards_a/cards_b` non venivano valorizzati dal nuovo importer anche se i raw logs contengono `cardRefs`.
- Fix avviato il 16/04/2026:
  - `backend/workers/match_importer.py` ora ricostruisce `cards_a/cards_b` dai log (`INITIAL_HAND`, `MULLIGAN`, `CARD_DRAWN`, `CARD_PLAYED`, `CARD_INKED`)
  - `scripts/import_matches.py` riallineato alla stessa logica
  - nuovo `scripts/backfill_match_cards_from_turns.py` per ripopolare il DB storico dai `turns` gia' salvati
  - backfill eseguito su primi chunk recenti: l'endpoint rogue scout e' tornato a produrre bucket `solo_brews` e `off_meta_validated`

Prossimi step consigliati:

| Task | Dove | Effort | Note |
|------|------|--------|------|
| Continuare one-off backfill `cards_a/cards_b` sui match recenti/storici | importer / DB | 0.5-1 dev day | Importer live e script sono pronti; resta da far girare il backfill piu' ampio |
| Port completo `rogue_scout` PG-first | `backend/services/rogue_scout_service.py` | 2-4 dev days | Il core c'e', ma va rifinito dopo il fix decklist coverage |
| Endpoint debug `GET /api/v1/monitor/rogue-scout-preview` | `backend/api/monitor.py` | Fatto | Admin/debug only, smoke test reale passato |
| UI Monitor "Emerging / Rogue / Tier-0 Killers" | `frontend/dashboard.html` | 1-2 dev days | accordion chiuso di default |
| Decide porting `gen_meta_deck.py` | discovery | 1 dev day | farlo solo dopo valutazione stabilita di `rogue_scout` |

---

## 5. Infrastruttura — pre go-pubblico serio

| Task | Status | Rischio se non fatto |
|------|--------|----------------------|
| **systemd service** `lorcana-api` per uvicorn (ora nohup manuale) | Non fatto | Crash → dashboard down fino restart manuale |
| **CORS stringere** (oggi permissivo) | Non fatto | Bassa priorità finché no API pubbliche cross-origin; da stringere pre go-pubblico |
| **OAuth Discord bridge** (per opt-in Public Profile) | Non pianificato | Blocca feature #C |
| **Email duels.ink** per allineamento legale | Scritta in `../analisidef/business/email_duels_ink_v4.md`, non ancora spedita | Blocca feature #C pubblico |
| **Rate limit per endpoint pubblici nuovi** (`/iwd`, `/deck-fitness`) | Ereditato dal middleware Redis globale | OK |

---

## 6. Migrazione da analisidef (Fase F-H)

Dettaglio in [`MIGRATION_PLAN.md`](MIGRATION_PLAN.md).

- **Sprint-1 Mossa A FATTO 15/04/2026**: Blind Playbook in PG + endpoint + accordion Profile (importer bridge da analisidef)
- **Sprint-1 Mossa B (DA FARE)**: porting nativo `gen_deck_playbook.py` in App_tool + cron settimanale + chiave OpenAI propria. Vedi [`SPRINT_1_MOSSA_B.md`](SPRINT_1_MOSSA_B.md).
  - **⚠️ CAVEAT LINGUA**: il prompt analisidef forza output `italiano fluido`. App e' inglese-only. Quando porteremo il generator in App_tool, modificare il prompt in `fluent English` e tutte le istruzioni (vedi `SPRINT_1_MOSSA_B.md` §3 e memoria `feedback_app_language_english.md`). Le 24 narrative attualmente in PG sono in italiano e resteranno tali fino a Mossa B.
- **Fase F (DA FARE)**: matchup report refresh autonomo (oggi dipende ancora da `analisidef/dashboard_data.json` importato da cron)
- **Fase G (FUTURO)**: killer curves batch autonomo (oggi parte da `analisidef/output/killer_curves_*.json` via `import_killer_curves.py`). **Anche qui prompt deve produrre EN**.
- **Fase H (FUTURO)**: player scouting reports LLM nativo App_tool. **Anche qui prompt EN**.

---

## 7. Priorità consigliata Q2-Q3 2026

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

*Ultimo aggiornamento: 16 Apr 2026 — dopo sessione "Meta Ticker + UI polish + Liberation Day D1-D3"*
