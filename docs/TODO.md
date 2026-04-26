# App_tool — TODO Master

**Ultimo aggiornamento:** 26 Aprile 2026 — B.1 nickname bridge stats chiuso; aggiunti privacy boundary V3, KC quality sprint, ops digest e visual parity.
**Scope:** master TODO operativo di `metamonitor.app`. Tre sezioni ordinate per impatto business.

## Regola operativa per Claude

- **Sezione A — PRE-LAUNCH (max 7 giorni)**: tutto ciò che sblocca lancio/conversione. Non si aggiungono task qui se non davvero bloccanti. Se in dubbio → Sezione B.
- **Sezione B — POST-LAUNCH (entro 30 giorni)**: miglioramenti che contano ma non bloccano. Ordinati per impatto business, non per eleganza tecnica.
- **Sezione C — TECH DEBT (separato, non bloccante)**: refactor, split file, cleanup, migration. Nessuno di questi blocca il lancio.

**Non spezzare questa distinzione.** Ogni task deve stare in A o B o C. Se un task appare in A ma è refactor, viene spostato in C.

**Workflow progressivo (obbligatorio):**
- Ogni task completato → aggiornare qui **subito**. Status: `DONE` / `PENDING` / `BLOCKED`.
- Nota sintetica 1 riga max accanto al DONE (cosa/come confermato). Niente log verbose.
- Niente lavoro fuori dal TODO — se non è qui, non esiste.

**Vincoli preservati (non rinegoziabili pre-launch):**
- V3 resta a **7 tab primary** (Home · Play · Meta · Deck · Team · Improve · Events). NO 5+2. NO drawer. NO Pro Tools / Community contenitore.
- Meta, Deck, Events non si toccano salvo bug. Sono già maturi.
- Pagamento reale SOLO dopo struttura fiscale chiara. Fino ad allora: fake paywall + interest tracking (già live).
- Focus correzioni pre-launch: **Play** (conversion clarity) + **privacy minima** + **Board Lab wiring minimo**. Improve debole, migliorato post-launch.
- **Set 12 NON è blocker pre-launch.** URL reali Google Form + Discord invite = bassa priorità post-launch (B.5). Non lavorare su `set12_hub.js` salvo richiesta esplicita.

**Documenti sibling:** [`BP.md`](BP.md) · [`V3_ARCHITECT_POINT.md`](V3_ARCHITECT_POINT.md) · [`MIGRATION_PLAN.md`](MIGRATION_PLAN.md) · [`SET12_MIGRATION_PLAN.md`](SET12_MIGRATION_PLAN.md) · [`PRIVACY_LAYER_V3.md`](PRIVACY_LAYER_V3.md) · [`DECK_REFACTOR_PARITY.md`](DECK_REFACTOR_PARITY.md) · [`KC_REVIEW.md`](KC_REVIEW.md) · [`SPRINT_1_MOSSA_B.md`](SPRINT_1_MOSSA_B.md) · [`SPRINT_P1.5_VENDORED.md`](SPRINT_P1.5_VENDORED.md).

---

# Sezione A — PRE-LAUNCH (max 7 giorni)

Scope: sblocco lancio + conversione minima. **Non toccare Meta, Deck, Events, Community salvo bug.**

Ordine non è temporale 1→2→3→… ma per impatto business. Sequenza giorno-per-giorno in [`BP.md`](BP.md) §12.1.

## A.1. Privacy — bug fix reali + verifica regressione

| Task | Status | Nota |
|------|--------|------|
| Verifica `POST /api/v1/user/consent` funziona | **DONE** | curl POST → 200 + body valido (24/04 sera, dev) |
| Export GDPR include `consents` + `interest_to_pay` nel whitelist | **DONE** | export include entrambe le chiavi in `preferences` (24/04 sera) |
| Smoke test `scripts/privacy_smoke_test.py` | **DONE** | 6/7 PASS, 1 SKIP (T2 n/a, no replay test user) |
| Alias mail `legal@metamonitor.app` → `monitorteamfe@gmail.com` su Cloudflare | **PENDING** | ops DNS, non-code |

## A.2. Porting minimo V3

| Task | Status | Nota |
|------|--------|------|
| Consent modal V3 | **DONE** | già presente in `frontend_v3/assets/js/team_coaching.js` con path `/api/v1/user/consent` |
| 412 handling upload Board Lab | **DONE** | `tcUploadOne` added, retry 1× dopo re-consent (24/04 sera) |
| Verifica footer disclaimer + `/about.html` link | **DONE** | `dashboard.html:89-116` live, disclaimer + link ok |
| Verifica fake paywall → POST `/api/v1/user/interest` | **DONE** | T6 smoke + curl POST → 200, `interest_to_pay` persistito |

**NON fare pre-launch:** refactor `team_coaching.js` (resta copia legacy), rimozione `views/` scaffolding, ristrutturazione nav, drawer. Set 12 Hub URL reali → B.5 (bassa priorità post-launch).

## A.3. Play — conversion clarity (core commerciale)

Opzione B (isolated Play-only gate). Scope: 4/5 task → DONE. 1 task deferred per decisione utente (Mulligan reveal, impatto globale).

| Task | Status | Nota |
|------|--------|------|
| **Header conversion** sopra killer curves | **DONE** | `cv2-conv-hdr` dinamico da top killer curve + critical turn |
| **How to Respond** inline in killer curve expansion (refactor A2, 24/04 sera) | **DONE** | gate dentro `.cv2-threat`: prime 3 curve free, 4ª+ con overlay paywall quando matchup >3/giorno; rimossa sezione separata |
| **Mulligan reveal gated** | **DEFERRED** | richiede toccare Deck/Improve, rinviato per isolamento Play-only |
| **Paywall 4° matchup/giorno** | **DONE** | nuovo `play_gate.js` (55 LOC), counter localStorage `play_matchups_viewed_YYYY-MM-DD`, overlay su "How to Respond" dal 4° matchup distinto |
| **Home headline insight teaser** | **DONE** | worst matchup (min 20 games) sopra hero-row, click → Play con deck+opp preselezionati |

## A.4. Board Lab — wiring minimo

**Obiettivo pre-launch:** upload owner-only funziona + access-control attivo. Flusso completo resta nel legacy `team_coaching.js` (NO refactor).

| Task | Status | Nota |
|------|--------|------|
| Verifica `require_replay_access` / `require_replay_owner` wired su `/api/v1/team/replay/*` | **DONE (verifica)** | Helpers esistono in `backend/deps.py:149,179` ma **non wirati** su `team.py` (25/04). Wiring richiede JWT-mandatory: rompe transitional nginx-only mode (`TEAM_API_REQUIRE_JWT=false`). Decisione: wiring effettivo gated su flip flag → fa parte di A.5 swap. Oggi `/replay/list` + `/replay/{game_id}` reimplementano filter ownership inline (`team.py:132-138, 174-179`); upload usa `get_current_user` mandatory (consent + ownership scritti). Nginx basic auth resta gate primario fino allo swap. |
| Verifica ownership `team_replays.user_id` attiva (migration M1 `9a1e47b3f0c2`) | **DONE** | Migration applicata 24/04 (CLAUDE.md §Privacy Layer V3). Upload assigna `user_id`, `is_private=true`, `consent_version`, `uploaded_via='board_lab'` (`team.py:85-99`). |
| Board Lab visibile in Team anche senza roster | **DONE** | `team.js:107` helper `buildBoardLabSection()`, early-return ora renderizza Board Lab + chiama `tcInit('tc-container')` (25/04). BP §2.2: Team primary perché ospita Board Lab. |
| Stub `team.js:308` "coming soon" — lasciare così, decidere se nascondere o mostrare placeholder | **DONE 25/04** | Sostituito con hint "Upload .replay.gz in Board Lab below" coerente col fix Board Lab no-roster |

## A.5. Go-live ops

| Task | Dove | Effort | Priorità |
|------|------|--------|----------|
| **V3 swap one-liner** — `FRONTEND_DIR` in `_serve_dashboard()` da `frontend/` a `frontend_v3/`. Eseguire come ULTIMA azione settimana 1. | `backend/main.py` | 5 min + restart | P0 (ultima azione) |
| QA end-to-end: tab switch, paywall triggers, consent flow, upload owner-only, mobile + desktop | manuale | 1 dev day | P0 |
| **QA privacy boundary V3** — nickname manuale non deve sembrare "claimed": copy `Public player lookup`/demo finché non c'è verifica; `.replay.gz` owner-only; public replay viewer solo anonymized/reconstructed, niente nickname reali o hidden-hand/full private state derivato da upload altrui. | **DONE 26/04** — Audit (Fase 1): backend endpoint replay verificati clean (anonymizer wirato su `/api/replay/list|game|public-log`, `/api/v1/team/replay/*` owner/shared filter). Copy fix (Fase 2) in `profile.js` + `shared_ui.js`: `My Stats`→`Player lookup` (×7), `Your account · deck · performance`→`Setup · pinned deck · player lookup`, `Personal Profile`→`Profile`, `Your improvement path`→`Improvement path` (×3), `Personal performance signals…`→`Performance signals based on the linked nickname's public match logs.`, `personal stats`→`lookup stats` (4 empty-state CTAs), hero CTA `your real matches`→`public match logs for the linked nickname`, bullet `Personal WR per deck — what actually wins for you`→`WR per deck · what wins on that nickname's logs`, `My Decks (up to 3)`→`Pinned Decks (up to 3)`, demo nudge Improve allineato a Home con `Stats below are not yours.` Diff: profile.js +24/-24, shared_ui.js +3/-3. | 0.5 day | P0 |
| Verifica service worker `frontend_v3/sw.js` self-destruct pulisce cache utenti legacy | client-side monitoring | auto | P1 |

**Guardrail Claude per QA privacy boundary:** questo task è audit/copy/smoke, non una nuova feature. Non introdurre login, OAuth, account claiming, nuove tabelle o nuovo replay engine. Correzioni ammesse prima del lancio: rinominare copy ambigua (`My Stats` → `Public player lookup` quando nickname non verificato), nascondere/limitare dati se sembrano privati, verificare che Board Lab usi solo replay owner-uploaded e che il public viewer resti anonymized. Se serve backend nuovo, fermarsi e chiedere.

## A.6. Ciò che NON si fa pre-launch (decisioni preservate)

Se qualcuno propone uno di questi, rispondere "post-launch" e non discutere. Vale anche per Claude.

### V3 nav sacred — vincolo non-negoziabile (pre- e post-launch)

Nav resta fissa a **7 tab primary**: Home · Play · Meta · Deck · Team · Improve · Events.

- ❌ NO rename / reorder / new tab / drawer "..." / Pro Tools tab / Community tab / Coach tab / fusione Team-Improve-Events
- ❌ NO spostamento Board Lab fuori da Team
- ❌ NO spostamento Play content fuori da Play
- ❌ NO modifiche Meta / Deck / Events salvo bug esplicitamente richiesto
- ✅ Feature post-launch (B/C) **innestate dentro tab esistenti**:
  - Best Plays → in Play
  - Blind Playbook personalized → in Improve (o punto già previsto)
  - Session notes / Coach flow / Export PDF → in Team / Board Lab
  - Coach tier = superficie dentro Team, non un tab nuovo

Qualsiasi proposta che richiede cambio nav → tech debt deferred, NON implementare.

### Altre cose pre-launch escluse

- ❌ School of Lorcana placeholder
- ❌ Replay Viewer inline in Play ("See it happen")
- ❌ Sideboard LLM batch (Feature B) — richiede $3-5/m OpenAI + 1 settimana dev
- ❌ Nickname bridge completo / country segmentation
- ❌ Coach page pubblica `/coach/<slug>` + affiliate tracking
- ❌ Split file `monolith.js` / `coach_v2.js` / `monitor.js` / `profile.js`
- ❌ Refactor `team_coaching.js` copia legacy
- ❌ Rimozione `views/` scaffolding
- ❌ Label enrichment Board Lab (chi ha cantato, chi ha banished, ecc.)
- ❌ Error Detection / replay review personale
- ❌ Pagamento reale Paddle (solo fake paywall + interest tracking)
- ❌ Meta / Deck / Events / Community: non toccare salvo bug
- ❌ Improve ristrutturazione a percorso (resta raccolta strumenti pre-launch, dichiarato limite)

---

# Sezione B — POST-LAUNCH (entro 30 giorni)

Scope: migliorie che contano, non bloccanti. Ordinate per impatto business.

## B.1. Improve — da raccolta a percorso di miglioramento

Oggi Improve è un menu (My Stats + Blind Playbook + Card Analysis + Mulligan + Replay). L'utente entra e non sa da dove cominciare. Dichiarato come limite in [`BP.md`](BP.md) §2.4.

| Task | Effort | Impatto business |
|------|--------|------------------|
| Header "Your improvement path" con 3-4 step ordinati basati sul dato utente | **DONE 25/04** — `profile.js:912 pfImprovementPath()` 3 step (Worst matchup→Play / Best matchup→Play / Underperforming deck→Deck), gating: < 20 game = teaser cresci, 0 step = "balanced". Ogni step actionable con click → tab+preselect. | Alto (retention Pro) |
| Nickname bridge più utile: quando bridge attivo, mostrare "X match associati, Y% WR personale" in Home + Improve | **DONE 26/04** — `profile.js` helper `pfPlayerBridgeStats()` aggrega da `DATA.player_lookup[fmt][nick]` (no backend) + `pfBridgeStatsCard(saved, scope, variant)` rendering Home/Improve variants. Stati gestiti: nickname assente (card hidden), linked-with-data ("X matches, Y% WR over N decks" + best deck line + "Open Improve"/"Review decks" CTA), linked-but-empty ("nickname linked, no matches in {fmt}"), demo (title swap "Demo bridge active"). Smoke unit 5/5 PASS. | Alto (feature hook, sblocca country segmentation futura) |
| Confidence / sample size surface su Mulligan ("Based on N hands, confidence: low/med/high") | **DONE 25/04** — `lab.js:116 _mullSetConfidence()` badge inline accanto al counter, aggiornato per filtro attivo (Blind/OTP/OTD). Threshold: <10=Low rosso, 10-29=Medium giallo, 30+=High verde, 0=No data. Tooltip esplicativo per ogni soglia. | Medio (honesty) |
| Blind Playbook personalizzato per-matchup (non solo per-deck) | 2 dev day | Medio |

## B.2. Board Lab — da stub a flusso coach

Oggi Board Lab vive nel legacy `team_coaching.js`. Per giustificare il Coach tier €39/m serve ownership completa + coach flow.

| Task | Effort | Impatto business |
|------|--------|------------------|
| Upload/delete owner-only verificati end-to-end (include `DELETE /api/v1/team/replay/:id` con `require_replay_owner`) | **DONE 25/04** — endpoint + UI + smoke test `scripts/replay_ownership_smoke.py` (7 check: T1 endpoint, T2 is_owner+has_note shape, T3 anon→401, T4 cross-user→403, T5 owner→204+gone, T6 rate limit, T7 notes round-trip). Run con `USER_A_TOKEN`/`USER_B_TOKEN`/`USER_A_GAME_ID` env. | Alto (Coach tier justification) |
| Session notes persistenti per replay | **DONE 25/04 (MVP A owner-only)** — migration `b8e72d4a9c3f` (`replay_session_notes` table, CASCADE FK), endpoint `GET/PUT/DELETE /api/v1/team/replay/{game_id}/notes` (`require_replay_owner`, 50k chars cap), `has_note` privacy-aware in `/replay/list` (owner/admin only), GDPR export esteso (`replay_session_notes` key), UI inline in legacy `team_coaching.js` (textarea autosave 1.5s + min 5 chars threshold + manual Save + Clear con confirm + relative timestamp + has_note dot badge nelle list rows). MVP A = no sharing; estensione futura B aggiunge `visibility` enum senza breaking. | Alto (Coach tier) |
| Export PDF sessione (base: snapshot + note) | 2 dev day | Medio |

> **Nota scope**: il "coach flow gestionale" (landing → roster → queue → review → export → share) è ora gestito interamente in **B.7 Coach Workspace** (nuova sezione). B.2 resta scoped alle *feature* di Board Lab (export PDF, viewer evolution, viewer comparativo).

## B.3. Privacy — hardening

| Task | Effort | Impatto business |
|------|--------|------------------|
| Tabella `user_consents` dedicata (se serve versioning append-only) invece di JSONB `preferences.consents` | **DONE 26/04** — migration `c4f9e1d8a2b6` (`user_consents` table append-only, CASCADE FK su `users`, idx composto `(user_id, kind, accepted_at)`); model `UserConsent`; service helpers `record_consent` + `get_latest_consents`; endpoint `POST /api/v1/user/consent` ora dual-write (table + JSONB cache mantenuto per backward-compat) con `ip` + `user_agent` catturati da `request`; nuovo `GET /api/v1/user/consents` legge latest-per-kind da table; GDPR export esteso con `user_consents` key (full history); smoke `privacy_smoke_test.py` T8 (POST→JSONB sync + table append + GET latest match). | Basso (compliance seria) |
| Rate limit upload replay (DoS prevention + abuse) | **DONE 25/04** (`backend/middleware/rate_limit.py:25-33` bucket dedicato per-tier: free 5/min, pro 30, team 60, admin 300) | Medio |
| `DELETE /api/v1/team/replay/:id` endpoint + UI trigger | **DONE 25/04** — endpoint `team.py:184` con `require_replay_owner`; `is_owner` esposto in `/replay/list`; UI button (`team_coaching.js:228+225`) owner-only con confirm | Alto (GDPR right to delete) |

## B.4. Play — evoluzione post-lancio

| Task | Effort | Impatto business |
|------|--------|------------------|
| Replay Viewer inline "See it happen" sulla killer curve (se dati engagement post-launch lo giustificano) | 2-3 dev day | Medio |
| How to Respond **personalized** (non più archetype-based) — Feature B LLM batch | 1 settimana + $3-5/m OpenAI | Alto (sblocca anche Key Threats + Sideboard in un solo cantiere) |

## B.5. Home + acquisition

| Task | Status | Nota |
|------|--------|------|
| Set 12 Hub `FORM_ACTION` + `FORM_EMAIL_FIELD` + `DISCORD_INVITE` → URL reali | **BLOCKED** | attesa Google Form + Discord server. Marcatore `BLOCKED_URL_PENDING` in `set12_hub.js`. Non bloccante lancio. |
| Improve onboarding più aggressivo sul nickname bridge | **DONE 25/04** | Hero CTA card sopra Improve quando `!duelsNick` (3 unlock bullets + Link/Demo dual CTA + counter player tracked) — `profile.js:913-940 pfImproveNickHero()`. Demo mode = strip slim. Linked = nascosto. |

## B.6. Ops — Feedback & Ops Digest

**Goal:** canale unico per bug/request utenti e anomalie pipeline notturne, con mail digest giornaliero. Non blocca V3 launch; serve a ridurre il tempo di triage post-lancio.

**Guardrail Claude:** non implementare questa sezione durante pre-launch salvo richiesta esplicita. Se richiesto, partire da Fase 1 in commit piccoli: schema DB + endpoint feedback, poi incident reporter, poi digest mail. Non aggiungere LLM remediation nella stessa PR. Non leggere o inviare secrets nei digest. Non permettere azioni automatiche: il sistema deve solo raccogliere, raggruppare e suggerire.

| Task | Fase | Nota |
|------|------|------|
| `user_feedback` table + `POST /api/v1/feedback` rate-limited + sticky feedback button/modal V3 (kind, text, page_url, ua, auto-context) | Fase 1 | Separare feedback utente da incidenti ops; limite 5/die user, 3/die anon-IP |
| `ops_incidents` table + `backend/services/incident_reporter.py::report_incident()` | Fase 1 | Campi minimi: source, severity `info|warn|error|critical`, payload JSONB, status; helper riusabile dai cron |
| Wiring cron/worker critici: import matches, KC batch, matchup reports, snapshot assembler, monitor unmapped, KC freshness, backup | Fase 1 | `catch + report_incident()` su failure; digest mostra solo `severity >= warn`, DB conserva tutto |
| `daily_health_digest.py` 07:30 UTC → mail unica a `monitorteamfe@gmail.com` | Fase 1 | Raggruppa nuovi feedback per kind + incidents per source/severity + lista azioni suggerita |
| `digest_remediation_plan.py` 08:00 UTC con LLM plan in `docs/incidents/YYYY-MM-DD.md` | Fase 2 | Solo suggerimenti, mai esecuzione; prompt con log pertinenti, no secrets, no destructive, compatibile con `ARCHITECTURE.md` |

## B.7. Coach Workspace — tab Team end-to-end

**Goal:** trasformare il tab Team da read-only KPI dashboard a workspace gestionale per Coach tier €39/m. Stessa nav, stesso tab, layered rendering basato su `User.tier` esistente. Player view (free/pro/coach-in-casual-mode) e Coach view convivono nella stessa pagina con render condizionale.

**Architettura (vincoli non-negoziabili):**
- **NESSUN nuovo tab** (V3 nav sacred, 7 tab fissi).
- **NESSUNA seconda autenticazione** dentro il tab. JWT `tier='coach'` (già esistente in `auth_service.create_access_token`) basta. Il toggle Player/Coach view è UI-state in `User.preferences.team_view_mode`, non auth.
- **NESSUNA nuova capability surface**: `users.tier` (`free|pro|coach|team`) + `promo_service.granted_tier` esistenti coprono entrambi gating Stripe e beta access.
- **NESSUNA nuova tabella di membership**: si estende `team_roster` con `coach_id` + `student_user_id` (entrambi FK `users.id`, nullable). Il binding replay→studente passa per `team_replays.student_id` + nuovo campo `gz_internal_nick` (estratto al parse del `.gz`), **indipendente da `duels_nick`** — questo è il fix dello stress-test "CSV con 0 match in duels".
- **Nuovo codice in moduli V3-native** (`frontend_v3/assets/js/dashboard/team_*.js`) wired via scaffolding `views/`. **Niente nuovo codice in `frontend/assets/js/team_coaching.js`** (legacy 2005 LOC, flagged C.2). Sblocca anche C.3 (`views/` scaffolding).
- **Anonymizer** (`backend/services/replay_anonymizer.py`, già consent-aware da privacy V3) esteso: mostra `display_name` reale solo se ruolo richiedente = `coach_reviewer` AND `student.consent_version >= REQUIRED`. Default resta `Player/Opponent`.
- **Migration alembic** sempre additive, non rompono head `9a1e47b3f0c2` (privacy V3) né `b8e72d4a9c3f` (session notes).
- **Discord** mai prerequisito: workspace coach funziona end-to-end senza Discord (B.7.9 è Fase 2 opzionale).

**Guardrail Claude:**
- NON implementare in pre-launch. Anche post-launch, **B.7.0 (gating) è prerequisito infra** prima di qualsiasi altra sub-sezione.
- Ogni sub-sezione = **PR separata**, mai bundle. Se una sub-sezione richiede migration + endpoint + UI, splittare in 3 PR consecutive.
- **Mai introdurre WebSocket**, secondo login, account separati per coach/player, o un nuovo tab.
- **Mai estendere `team_coaching.js`**: ogni nuovo componente in file V3-native nuovi.
- **Audit privacy**: prima di ogni endpoint nuovo, verificare che `replay_anonymizer` sia stato considerato e che le 3 dependency `require_replay_owner` / `require_replay_reviewer` (NEW) / `require_replay_access` siano applicate correttamente.

### B.7.0 Tier gating + beta access (prerequisito)

| Task | Effort | Impatto |
|------|--------|---------|
| Stripe webhook → `users.tier='coach'` post-checkout (riusa `subscription_service.create_checkout_session`, già scaffold). Test con account dev Stripe + dry-run. | 2 dev day | Alto |
| Beta redemption code: riuso `promo_service.granted_tier='coach'` + endpoint `POST /api/v1/promo/redeem-beta`, distribuibile a 5-10 power-coach prima di Stripe live. Codici scadono dopo N giorni o never (param). Audit log redemption. | 1 dev day | Alto (dogfooding) |
| `User.preferences.team_view_mode` (`player`/`coach`, default `coach` se `tier=coach`, sennò non applicabile). Endpoint `PUT /api/v1/user/preferences` già accetta whitelist (`user_service.py::ALLOWED_PREFS`) — aggiungere `team_view_mode` lì. | 0.5 dev day | Medio |
| **Tier `team` legacy compatibility**: `users.tier` ENUM oggi accetta `free|pro|coach|team` (`team` è valore storico pre-`coach`). Default policy B.7: `tier='team'` mappato a Coach Workspace capability (alias temporaneo) per non rompere user paganti esistenti. Decisione finale di prodotto sul tier `team` (deprecate / alias permanente / tier intermedio €19) tracciata in B.7.Y. Nessun nuovo signup deve poter scegliere `team` — restringere `interest_to_pay` pattern a `(pro\|coach)` in `backend/api/user.py`. | 0.5 dev day | Alto (no silent default-deny per pagante) |

### B.7.1 Layered rendering tab Team (player / coach view)

| Task | Effort | Impatto |
|------|--------|---------|
| `renderTeamTab()` in `team.js` switch su `(tier, team_view_mode)`: free+team→KPI+roster cards read-only (oggi), pro→+analytics avanzate (read-only), coach+coach-mode→full workspace, coach+player-mode→stessa vista pro. | 1 dev day | Alto |
| Toggle Player/Coach view nell'header del tab Team (visibile solo se `tier=coach`). Persistenza in `preferences.team_view_mode`. | 0.5 dev day | Medio |
| Empty states differenziati: (no team / free with team / coach without students / coach onboarding). Soft-gating upsell card per pro→coach: "Upgrade to manage students". | 1 dev day | Medio (conversion) |

### B.7.2 Roster gestionale + CSV import

| Task | Effort | Impatto |
|------|--------|---------|
| Migration additiva `team_roster`: `+ coach_id FK users, student_user_id FK users NULL, display_name, status_admin ENUM[invited|active|paused|archived], duels_nick, duels_nick_status ENUM[missing|unverified|linked|conflict], discord_username, discord_id, notes, revoked_at`. Backfill rows esistenti come `coach_id=NULL` (roster legacy team-wide resta accessibile a admin). | 1 dev day | Alto (foundation) |
| Endpoint `POST /api/v1/team/students` (single CRUD) + `POST /api/v1/team/students/bulk` (CSV: display_name, duels_nick?, discord?). Parser server-side, validazione nick contro `matches` table (max 10k row check). Quote: max 50 studenti per coach. | 2 dev day | Alto |
| UI `team_roster_editor.js` (NEW MODULO V3): tabella editabile, add/remove/edit inline, import CSV button, badge `Linked · 47 matches` / `Missing — ask student to play`. | 2 dev day | Alto |

### B.7.3 Nickname binding (gz_internal_nick + duels_nick separati)

| Task | Effort | Impatto |
|------|--------|---------|
| Parser `.gz` (estende `replay_archive_service.py` + `match_log_features_service.py`) salva `team_replays.gz_internal_nick` al parse. Migration additiva. | 1 dev day | Alto (stress-test fix) |
| Tabella `replay_nick_bindings (coach_id, gz_internal_nick, student_id, created_at)` UNIQUE`(coach_id, gz_internal_nick)`. Endpoint `POST /api/v1/team/bindings` per assegnazione manuale. Auto-suggest se nick coincide con `team_roster.duels_nick` di studente già linked. | 1 dev day | Alto |
| UI student-picker modal post-upload `.gz` (`team_student_picker.js` NEW): "Who is this replay from?" → dropdown studenti + auto-suggest. Successivi upload con stesso `gz_internal_nick` saltano il modal. | 1 dev day | Alto (UX critico) |
| Validazione `duels_nick` in `team_roster`: cron giornaliero (riusa slot `monitor_kc_freshness` 07:00 UTC) verifica match in `matches` table, aggiorna `duels_nick_status`. | 0.5 dev day | Medio |

### B.7.4 Replay queue + review states

| Task | Effort | Impatto |
|------|--------|---------|
| Migration additiva `team_replays`: `+ student_id FK team_roster NULL, review_status ENUM[new|in_review|reviewed|shared|archived] DEFAULT 'new', reviewed_at, reviewed_by FK users`. Indice composto `(coach_id, review_status, created_at DESC)` per queue performance (essenziale a 1500+ replay/coach). | 1 dev day | Alto |
| Endpoint `PATCH /api/v1/team/replay/{id}/status` con dependency `require_replay_reviewer` (NEW: coach del team del cui studente è il replay, con consent OK). | 0.5 dev day | Alto |
| Endpoint `GET /api/v1/team/workspace` (no-cache, separato da `/team/overview` blob 2h): queue replay + counters per stato + roster live + activity recent. Paginazione (default 50, max 200) + filtri (`student_id`, `status`, `date_from`, `date_to`). | 2 dev day | Alto |
| UI queue panel `team_queue.js` (NEW MODULO V3): landing del Coach view in tab Team. Filtri queue, counter chip ("3 new", "5 to deliver"), click row → Board Lab viewer con replay caricato. | 2-3 dev day | Alto |

### B.7.5 Session notes visibility model (extension MVP A)

| Task | Effort | Impatto |
|------|--------|---------|
| Migration additiva `replay_session_notes`: `+ visibility ENUM[owner_only|coach_private|shared_with_student] DEFAULT 'owner_only'`. No breaking — MVP A esistenti restano `owner_only`. | 0.5 dev day | Medio |
| Endpoint `PUT /notes` accetta `visibility`. Read logic: studente vede solo `shared_with_student`, coach vede `coach_private` + `shared_with_student` dei propri student, owner vede sempre proprie note. | 1 dev day | Alto (loop coaching) |
| UI toggle "Share with student" inline su nota in Board Lab. Studente in tab Team vede badge "Coach notes (X)" sui suoi replay condivisi, click → vista note shared. | 1 dev day | Alto |

### B.7.6 Coach feedback hook (extension B.6)

| Task | Effort | Impatto |
|------|--------|---------|
| `user_feedback.kind` aggiunge valore `coach_issue`. Auto-context modal: roster size, replay pending count, last review date. Triage prioritario nel digest B.6 (sezione coach-only). | 0.5 dev day (extension B.6) | Medio |

### B.7.7 Side studente — revoke + GDPR cascade + audit log

| Task | Effort | Impatto |
|------|--------|---------|
| Studente vede "Your coaches" in Profile: lista coach + button "Revoke coach access". `team_roster.revoked_at` + cascade soft (replay restano con `student_id → null`, note `coach_private` orfanate restano coach-asset, `shared_with_student` decadono). | 1.5 dev day | Alto (GDPR + trust) |
| Account delete cascade: `team_roster.student_user_id → null`, `team_replays.student_id → null` ma `gz_internal_nick` resta (asset coach), note pseudonimizzate (`display_name → "Former student"`). Test in `scripts/privacy_smoke_test.py` (estensione T8/T9). | 1 dev day | Alto (compliance) |
| Tabella `replay_access_log (replay_id, viewer_id, action ENUM[view|review|share|note_create|note_share], at)`. Append-only. Studente può richiedere "audit del proprio replay" via GDPR export esteso. | 1 dev day | Medio (privacy posture) |

### B.7.8 Notifications & realtime (no WebSocket)

| Task | Effort | Impatto |
|------|--------|---------|
| Polling `/team/workspace` ogni 30s in tab Team attivo (gated by `document.visibilityState`). Counter unread su tab Team navbar quando `new` queue cambia. Pause polling se tab nascosto. | 1 dev day | Medio |
| Mail immediata "Coach reviewed your replay" allo studente quando coach setta `shared_with_student`. Riusa SMTP esistente (`/tmp/.smtp_pass`, sender `monitorteamfe@gmail.com`). | 0.5 dev day | Alto (loop coaching) |
| Mail digest "X new replays from your students today" al coach (extension B.6 daily digest, sezione coach-only). | 0.5 dev day (extension B.6) | Medio |

### B.7.9 Discord integration (Fase 2 — NON blocker)

Discord come acceleratore. Workspace funziona end-to-end senza Discord. **Vincolo invariante:** ogni studente importato da Discord deve comunque passare per `duels_nick` linking — Discord ≠ analytics access.

| Task | Effort | Impatto |
|------|--------|---------|
| Discord bot OAuth + scelta server/ruolo (es. `Students`, `DKP Students`) + import membri come `team_roster` con `discord_id`/`discord_username`. Sync periodico: nuovo membro→`invited`, ruolo rimosso→`paused`, leave→`archived` (con confirm). | 3-5 dev day | Medio-Alto |
| Discord notifications (replay received / review completed / N pending). Opt-in per coach. | 2 dev day | Medio |

### B.7.X Vincoli inline (applicati a tutte le sub-sezioni)

- **Quote per tier**: free→nessun roster gestionale (oggi), pro→roster read-only, coach→max 50 studenti + max 500 replay storage (configurabile env). Enforcement lato endpoint.
- **Tier gating UI**: render condizionale, mai hard-hide componenti — sempre mostrare upsell CTA dove applicabile (drives conversion).
- **Migration policy**: tutte additive, mai breaking. Ogni migration deve coesistere con head `7894044b7dd3` cassetto Set12 dormant.
- **English-only copy** (CLAUDE.md): UI tab Team, mail notification, error messages tutti in inglese.
- **No new cron**: riusare slot esistenti (`monitor_kc_freshness` 07:00, `daily_health_digest` 07:30 di B.6) per validation/digest task. Cron nuovo solo se Fase 2 Discord sync.

### B.7.Y Decisioni esplicitamente DEFERRED

- **Multi-coach per team** (assistant coach, head coach + sub-coach) — Fase 3 post B.7 stable.
- **Note collaborative** (studente risponde alla nota del coach, thread) — MVP unidirezionale.
- **Studente ospite via magic link** senza account metamonitor — riduce barriera adoption ma è feature grossa, DEFERRED.
- **Coach contattabilità senza account studente** (coach uploada `.gz` ricevuti via DM) — funziona già con `gz_internal_nick` binding lato coach senza che lo studente sia user. Resta supportato come fallback, non come flusso primario.
- **Decisione finale tier `team`**: in B.7.0 è alias temporaneo a Coach capability per non rompere user paganti esistenti. 3 strade aperte da decidere come **decisione di prodotto** (non tecnica): (a) deprecate definitivo + migrazione user esistenti a `coach`/`pro`; (b) alias permanente di `coach` riservato per multi-coach team (sblocca multi-coach Fase 3); (c) tier intermedio €19/m tra Pro e Coach (Pro+roster read-only, no queue/review). Decisione attesa entro 30 gg dal B.7 launch. Fino ad allora: alias = `coach`, signup nuovo `team` bloccato.

---

## B.8. NON in B — resta fuori scope 30 gg

- Country segmentation / meta locale (richiede ≥500 utenti con country; post-60 gg minimo)
- Coach page pubblica `/coach/<slug>` + affiliate (post-validazione Coach tier, non prima)
- School of Lorcana full build (placeholder solo se emerge segnale)
- Multi-TCG expansion (mai in scope 30 gg)

---

# Sezione C — TECH DEBT (separato, non bloccante)

Scope: debiti che il codebase ha accumulato. **Nessuno blocca il lancio.** Affrontati con sprint dedicati post-launch, in ordine di manutenibilità.

## C.1. V3 — split file over 800 LOC cap

Da `feedback_v3_anti_monolith_rules.md`:

| File | LOC | Strategia |
|------|-----|-----------|
| `monitor.js` | 2183 | Split per sezione (Ticker, Fitness, Rogue, Matrix, Analysis, BestPlayers, NonStandard) in `monitor_*.js` |
| `coach_v2.js` | 1981 | Split per blocco (selector, curves, cards, ratings, responses) in `coach_v2_*.js` |
| `profile.js` | 1444 | Separare Home (`home.js`) da Improve (`improve.js`) usando lo scaffolding `views/` |
| `lab.js` | 1276 | Split per sezione Deck |
| `monolith.js` | 1357 (**frozen**) | Non toccare. Nuove feature in file separati. |

## C.2. V3 — `team_coaching.js` legacy copy

1936 LOC copia-incollato dal legacy `frontend/`. Flagged come cautionary tale in `feedback_v3_anti_monolith_rules.md`.

- Refactor: modularizza in `team_coaching_*.js` (upload, viewer, notes)
- Dedup: sostituisci con chiamate a moduli V3-native dove possibile
- Effort stimato: 1 settimana

**Sequenziamento con B.7:** se B.7 (Coach Workspace) chiude prima di C.2, gran parte di `team_coaching.js` (notes UI, share toggle, queue hooks) è già stata riscritta in moduli V3-native (`team_roster_editor.js`, `team_queue.js`, `team_student_picker.js`). In quel caso C.2 collassa a *deprecation/delete dopo parity check* — effort scende da 1 settimana a 1-2 giorni. Se invece C.2 viene fatto prima, B.7 deve riusare i nuovi `team_coaching_*.js` modularizzati invece di crearne di nuovi paralleli.

## C.3. V3 — `views/` scaffolding non wired

`assets/js/views/` (148 LOC totali, 8 file) sono placeholder per split futuro.

- Decidere: wire o rimuovere
- Raccomandazione: wire gradualmente quando si fa C.1 (profile.js split → home.js + improve.js useranno lo scaffolding) **o quando si fa B.7** (i nuovi `team_roster_editor.js` / `team_queue.js` / `team_student_picker.js` di Coach Workspace sono i candidati naturali per popolare lo scaffolding)

## C.4. Service Worker cleanup

`sw.js` oggi è **self-destruct** (elimina cache + unregister) per risolvere cache-first trap storica.

- Quando tutti i client legacy sono stati toccati ≥1 volta → rimuovere `sw.js`
- Sostituire con SW network-first per HTML (pattern già in legacy, memoria `feedback_v3_service_worker_cache`)

## C.5. Performance

Non blocker ora. Post-launch, se i dati mostrano regressioni:

- Chart.js instances cachate (`charts`), verificare `destroy()` su tab switch
- Lazy-load `rvCardsDB` già attivo
- `DATA` blob da `/api/v1/dashboard-data` — cache 2h server + ETag client

## C.6. Doc cleanup

- `ARCHITECTURE.md` root (182KB, enterprise) — archiviare o ridurre a §ridotta + link ai 3 canonici ([`BP.md`](BP.md), [`TODO.md`](TODO.md), [`V3_ARCHITECT_POINT.md`](V3_ARCHITECT_POINT.md))
- `frontend_v3/point/V3_ARCHITECT_POINT.md` originale EN — mantenere come archivio GPT 24/04, linkato dal canonico
- `frontend_v3/point/V3_CURRENT_STATE.md` — mantenere aggiornato come snapshot as-is di V3
- `analisidef/BUSINESS_PLAN.md` v3.1 + `BP_STRATEGIST_POINT.md` — già archivi, no action
- [`MIGRATION_PLAN.md`](MIGRATION_PLAN.md) + [`SET12_MIGRATION_PLAN.md`](SET12_MIGRATION_PLAN.md) — mantenere, fonte dettaglio per §C.7

## C.7. Migration pipeline (analisidef → App_tool + Set 12)

Stato generale:
- Runtime coupling R1/R2/R3/C1 chiusi 15/04
- D1-D3 data-level coupling ancora aperti (bridge JSON via cron)
- Dettaglio completo: [`MIGRATION_PLAN.md`](MIGRATION_PLAN.md)

### C.7.1. P0 Set 12 readiness (FATTO 22/04)

Piano: [`SET12_MIGRATION_PLAN.md`](SET12_MIGRATION_PLAN.md) v3.

| Task | Stato | Dove |
|------|-------|------|
| Regex folder/queue future-proof (SETNN) | FATTO | `backend/workers/match_importer.py`, `scripts/import_matches.py` |
| Digest generator `_is_core_perimeter()` | FATTO | `pipelines/digest/generator.py` |
| Canary FS vs DB | FATTO | `scripts/monitor_unmapped_matches.py` (cron 07:05) |
| `SET_MAP` estensibile via env | FATTO | `backend/workers/static_importer.py` |
| Admin endpoint `reset-legality-cache` + `refresh-dashboard` | FATTO | `backend/api/admin.py`, `backend/deps.py` |
| Wrapper `refresh_static_and_reset.sh` | FATTO | `scripts/refresh_static_and_reset.sh` (cron dom 04:45) |
| `default_core_perimeter` nel blob + helper frontend | FATTO | `snapshot_assembler.py`, `dashboard.html`, V3 |
| Migration S0.5 `set12_launch` in cassetto (guard env) | FATTO (dormant) | `db/migrations/versions/7894044b7dd3_*.py` |
| Migration S0.6 partial index `idx_matches_lookup` | FATTO (applicata) | `7dec24a98839_*.py`, alembic current |
| Token admin + systemd drop-in | FATTO | `/etc/apptool.env` (0600) + `lorcana-api.service.d/admin-token.conf` |

**Prossima finestra rotation attesa:** Settembre 2026 (Set 12 release Ravensburger, non ancora annunciato). Al D-day:

```bash
SET12_RELEASE_DATE=2026-09-DD SET12_LEGAL_SETS=3,4,5,6,7,8,9,10,11,12 \
  alembic upgrade 7894044b7dd3
systemctl restart lorcana-api
curl -X POST -H "X-Admin-Token: ..." /api/v1/admin/reset-legality-cache
```

### C.7.2. P2 Migrazione Fase F-H (da analisidef)

| Fase | Scope | Stato | Note |
|------|-------|-------|------|
| **Sprint-1 Mossa A** | Blind Playbook in PG + endpoint + accordion Profile | FATTO 15/04 | Importer bridge da analisidef |
| **Sprint-1 Mossa B** | Porting nativo `gen_deck_playbook.py` in App_tool + cron settimanale + chiave OpenAI propria | DA FARE | [`SPRINT_1_MOSSA_B.md`](SPRINT_1_MOSSA_B.md). ⚠️ prompt da EN-only (memoria `feedback_app_language_english`) |
| **Fase F** | Matchup report refresh autonomo | DA FARE | Oggi dipende da `analisidef/dashboard_data.json` importato da cron |
| **Fase G** | Killer curves batch autonomo | FUTURO | Oggi parte da `analisidef/output/killer_curves_*.json`. Prompt EN |
| **Fase H** | Player scouting reports LLM nativo | FUTURO | Prompt EN |

### C.7.3. P1 KC meta-relevance (applicato 24/04 pm)

Doppio guard attivo in `pipelines/kc/`: prompt-time (`build_prompt._build_meta_relevance_guard`) + post-filter (`scripts/generate_killer_curves._strip_non_meta_cards`). Helper `pipelines/kc/meta_relevance.get_meta_relevant_cards(db, format, days=30, min_plays=20)` — cached per-format.

Admin endpoint `/api/v1/admin/reset-legality-cache` invalida anche `kc_meta_relevant` + `meta_relevance_cache`. One-shot `scripts/reclean_kc_meta.py` già eseguito (209 card ref strippate). Sync rapido `scripts/refresh_kc_matchup_reports.py`: `killer_curves` → `matchup_reports` senza full regen (12 min → 5 sec).

### C.7.4. P1 KC quality sprint — validator, repair, batch safety

**Stato 26/04:** key OpenAI ruotata e verificata; test reale `EmSa vs AmyE` Core OK dopo repair automatico `response_missing_named_card`; DB sorgente ha `digest_hash`, `prompt_contract_hash`, `schema_version`, `response_v2_complete=6/6`, `v3_payload_complete=6/6`, `self_check_complete=6/6`. Sync Core verso `matchup_reports` eseguito. Non lanciare batch completo finché i punti sotto non sono chiusi.

**Guardrail Claude:** non lanciare `--format all`, non usare `--force`, non cambiare modello e non toccare la key OpenAI. Prima implementare validator deterministico e testarlo su righe esistenti. Ogni chiamata OpenAI reale deve essere single-pair, motivata e confermata dall'utente. Non pubblicare dati KC se il validator trova P0. Il repair LLM deve correggere solo il JSON già prodotto, non cambiare deck/format/sequence arbitrariamente.

| Task | Stato | Nota |
|------|-------|------|
| Repair automatico singolo per `response_missing_named_card` | PARTIAL | Implementato in `scripts/generate_killer_curves.py`; serve test su 3-5 matchup Core/Infinity, incluso caso che falliva (`AbSt` vs `SSt` Infinity) |
| Validator hard condiviso `pipelines/kc/validator.py` | PENDING | P0 fail: JSON/deck/format mismatch, Core-illegal, off-color, card non esistente, campi v2 mancanti, sequence lato sbagliato |
| Schema validation prima dell'upsert + `quality_status/errors/warnings` in `meta` | PENDING | Pubblicare in V3 solo `quality_status=pass` o warning esplicitamente accettati |
| Drop metrics granulari | PENDING | Separare response vs sequence, core-illegal vs non-meta; oggi `cards_dropped` è aggregato |
| Consistency check `killer_curves` → `matchup_reports` → dashboard blob | PENDING | Fallire refresh/cache se mancano matchup non spiegati o se il formato finisce nel blob sbagliato |
| Batch completo KC | PENDING | Solo dopo validator + smoke; poi `refresh_kc_matchup_reports.py --format all` + `/api/v1/dashboard-data?refresh=true` |

### C.7.5. Invarianti KC da memoria

- KC full batch solo **martedì 01:30** — non lanciare run manuali (`project_kc_pipeline_cost`)
- KC Spy = canary $0.05/die
- OpenAI gpt-5.4-mini, mai crediti Anthropic API (`feedback_claude_subscription_not_api`, `project_api_constraint`)

### C.7.6. Canary + monitoring ops

| Cron | Ora | Cosa alerta |
|------|-----|-------------|
| `monitor_unmapped_matches.py` | 07:05 UTC | Nuovo folder FS, drop_rate > 10%, `perimeter='other'` > 50/die |
| `monitor_kc_freshness` | 07:00 UTC | KC stale, snapshot InkDecks sparse (post-incidente 20/04) |
| `import_kc_spy` | 04:05 UTC | Validazione 268 file KC, auto-fix |

## C.8. Legacy — eventuale deprecation

Post-launch, dopo conferma che V3 non ha regressioni vs legacy per ≥2 settimane:
- Archivia `frontend/dashboard.html` (10.6K LOC inline) come `frontend/dashboard_legacy_20260501.html`
- Mantieni endpoint, model, services legacy — servono al V3 (zero divergenza API)
- Prima del lancio: **non toccare legacy.**

Backlog legacy-specifico (viewer rv*, accordion pending backend data, benchmark competitivo) spostato qui da §A vecchio. **Se il lancio V3 fallisce e si torna a legacy, questi task tornano attivi.**

## C.9. Privacy Layer V3 (applicato 24/04)

Dettaglio: [`PRIVACY_LAYER_V3.md`](PRIVACY_LAYER_V3.md). Componenti già live:

| Componente | Stato |
|------------|-------|
| Alembic head `9a1e47b3f0c2` (team_replays ownership) | Applicato |
| Deps `require_replay_access` / `require_replay_owner` | Live |
| Dep `require_replay_reviewer` (coach del team del cui studente è il replay, consent-aware) | PENDING — sarà introdotto da B.7.4 (Replay queue + review states) |
| `replay_anonymizer.py` + wiring API | Live |
| `POST /api/v1/user/interest` + `POST /api/v1/user/consent` | Live |
| GDPR export esteso con `team_replays` | Live |
| Consent modal legacy + footer disclaimer + `/about.html` | Live legacy (porting V3 in §A.2) |
| Copy sanitization (no duels, no MMR/ELO, fair-use card images) | Live legacy |
| Email swap `legal@` → `monitorteamfe@gmail.com` | Live legacy. V3 da allineare dopo alias Cloudflare up |
| SW `CACHE_NAME=lorcana-privacy-v4` + network-first HTML | Live legacy (V3 ha self-destruct, vedi §C.4) |

**Head alembic:** 2 head parallele (`7894044b7dd3` Set12 cassetto dormant, `9a1e47b3f0c2` privacy — current). Alembic upgrade richiede revision esplicita (NON `upgrade head`).

## C.10. V3 — naming cleanup post-launch

| Task | Stato | Nota |
|------|-------|------|
| Rinominare `frontend_v3/assets/js/dashboard/coach_v2.js` in `play.js` | PENDING | Solo dopo freeze pre-launch/Claude: oggi il file serve il tab Play ma contiene anche codice storico `rv*`; rename o split rischia conflitti mentre il TODO V3 è in corso. |

## C.11. Best Plays — backend pipeline dedicato (DEFERRED da B.4)

**Stato (verificato 25/04):** frontend renderer `buildBestPlaysCard()` (`profile.js:101`) **già pronto** e atteso al fondo del Play tab (`coach_v2.js:1897`). Backend data source **vuoto**: `snapshot_assembler.py:81-82` espone `best_plays = {}` placeholder; DB ha **0 reports** in `matchup_reports` con `best_plays` non-vuoto.

**Perché DEFERRED da B.4:** implementazione reale richiede mining da `matches.turns`, scoring euristico, categorizzazione, snapshot wiring e smoke test. Non è blocker pre-launch e non va fatto prima dello swap V3.

**Scope minimo futuro (sprint dedicato):**

- `backend/services/best_plays_service.py` — nuovo modulo
- No LLM (vincolo `project_api_constraint`)
- Heuristic scoring da winning matches: punteggio = `kills*3 + bounced*2 + lore + cards_played`
- Top-3 per deck/opponent (struttura già supportata dal renderer via campo `vs`)
- Categorize via regole semplici: `wipe` se kills≥2, `lore` se lore≥3, `combo` se abilities≥2, `early` se turn≤3, `tempo` altrimenti
- Headline auto-generato template `T${turn} ${cards.join('+')} → N kills, +X lore`
- Wiring in `snapshot_assembler.py` (popola `blob["best_plays"]` e `blob["best_plays_infinity"]`)
- Smoke test: count reports populated, sample shape match con frontend renderer schema

## C.12. V3 visual parity — Deck tab as design baseline

**Goal:** rendere Home, Play, Meta, Team, Improve, Events coerenti con la maturità visuale del tab Deck senza cambiare nav o contenuti. Non blocca go-live; sprint di polish post-launch.

**Guardrail Claude:** visual parity non significa redesign. Non cambiare nav, ordine tab, copy strategica, dati mostrati, gating/paywall o layout funzionale. Prima fare audit e lista differenze; poi patch CSS/classi condivise piccole. Evitare refactor monolitici e non toccare più di 1-2 tab per commit. Ogni patch deve passare smoke mobile/desktop e controllare overflow/overlap.

**Sequenziamento con B.7:** il tab Team passa per ultimo nel C.12 sweep. Non lavorare su visual parity tab Team finché B.7.4 (queue + roster componenti V3-native) non è chiuso e stabile — altrimenti CSS thrash tra ridisegno e wiring nuovi componenti.

| Task | Nota |
|------|------|
| Audit stile per tab | Confrontare typography, spacing, section headers, divider comments, card radius, color usage, CTA density contro Deck tab |
| Shared CSS tokens/components | Estrarre o riallineare classi comuni invece di inline style duplicati; mantenere mobile-first |
| Section comment/structure consistency | Uniformare commenti divisori e naming interno per ridurre drift tra tab |
| Smoke visual desktop/mobile | Verificare text overflow, overlap, contrast, tab switch e componenti con contenuto lungo |

---

*TODO consolidato il 24 Aprile 2026 (sera) reality-aligned. Sostituisce struttura precedente (§A App_tool legacy / §B V3 target-based / §C Migration). Nuova tassonomia: A = pre-launch, B = post-launch 30gg, C = tech debt. Sibling: [`BP.md`](BP.md) v4.1, [`V3_ARCHITECT_POINT.md`](V3_ARCHITECT_POINT.md) v1.1.*

*Update 24/04 sera: A.1 + A.2 + A.3 partial chiusi. A.3 Opzione B (Play-only soft gate via `play_gate.js`) implementato; Mulligan reveal deferred. Set 12 Hub URLs spostati in B.5 come BLOCKED non-blocker. Focus ora: A.4 Board Lab wiring minimo.*
