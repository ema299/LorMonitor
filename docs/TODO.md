# App_tool — TODO Master

**Ultimo aggiornamento:** 26 Aprile 2026 — B.1 nickname bridge stats + privacy boundary V3 chiusi; B.7 Coach Workspace foundation in corso (B.7.0 + B.7.0.5 + B.7.1 + B.7.2 backend DONE; resta UI roster editor + B.7.3-7.9). Stripe webhook centralizzato in B.8 (post-fiscal SRL).
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

## HARDBLOCK — No-Removal Window su Deck / Team / Play (valido fino al 2026-04-29 notte)

L'utente è single-reviewer in finestra single-Claude fino a martedì 28/04 notte e **non può fare review esterna**. Per evitare regressioni silenziose:

- **Deck · Team · Play sono in modalità ADD-ONLY.** Non si rimuove e non si sposta nulla di visibile (accordion, sezione, button, badge, KPI tile, intro copy) senza:
  1. Nota esplicita nel commit message del tipo `breaking-ui(deck): removed X because <ragione>` oppure `breaking-ui(deck): moved X from <da> to <a>`.
  2. Aggiornamento contestuale del file baseline (`frontend_v3/point/V3_CURRENT_STATE.md`) nello stesso commit.
  3. Conferma utente prima del commit. **Se l'utente non è online, non rimuovere — sospendi il task e spostalo in PENDING.**
- "Refactor che sposta senza perdita" conta comunque come rimozione fino a quando il commit non documenta esplicitamente il nuovo punto di vita dell'oggetto.
- Cambi additivi (nuovi accordion, nuove sezioni, nuovi badge, nuove copy intro) restano **liberi** — è il working mode normale.
- Vale per Deck, Team, Play. Meta / Events / Community non si toccavano già (vincolo preesistente in §A.6). Home / Improve restano modificabili come prima.
- Baseline 26/04 sera = primo commit `dev` dopo questo blocco. La finestra termina **martedì 28/04 notte**: dopo, l'utente fa diff manuale contro lo snapshot.

**Cosa è già stato accettato come baseline (NON da ripristinare, decisione utente 26/04):**
- Deck Summary: rimossi `Response Coverage mini` + `Recommended actions opp-aware` (sostituito da versione cross-matchup in fondo a "Your list").
- Deck: rimosso ink-picker matchup selector — selezione opp ora via row-click in Matchups.

Tutto il resto in Deck / Team / Play come da `V3_CURRENT_STATE.md` snapshot 2026-04-24 è da preservare.

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

## A.7. Auth UI minima — sign-up / sign-in / account dropdown

**Goal:** chiudere il buco "utente arriva su V3 → vuole creare account / fare login → non c'è UI". Il backend `auth.py` espone già `/register`, `/login`, `/refresh`, `/logout`, `/forgot-password`, `/reset-password` — manca solo la superficie UI in V3.

**Scope ristretto pre-launch:**
- Sign-up form (email + password + display_name) → `POST /api/v1/auth/register`
- Sign-in form (email + password) → `POST /api/v1/auth/login` → JWT in `localStorage` (key `lorcana_jwt`)
- Account dropdown nell'header V3: avatar/initials, "Logout", link "Profile" (esistente in tab Improve)
- Forgot password flow base: form mail → `/forgot-password`, token via mail → `/reset-password` UI minima
- Stato anonimo resta default: tutto pubblico continua a funzionare senza login (no regression)

**Coerenza con guardrail A.5 (riga 88):** quel guardrail vietava di introdurre login *durante il task QA privacy boundary V3*, non in assoluto. A.7 è task separato, esplicito. Il vincolo di A.5 ("no OAuth, no account claiming, no nuove tabelle") resta valido anche per A.7: niente Google/Discord OAuth, niente "claim this nickname", niente nuove tabelle DB (tutti gli endpoint backend già esistono).

**Vincoli non-negoziabili:**
- ❌ NO OAuth (Google/Discord/etc) — solo email+password
- ❌ NO account claiming nickname duels.ink (resta separato, gestito via `/api/v1/user/nicknames`)
- ❌ NO nuovi endpoint backend (tutti già esistono)
- ❌ NO nuove tabelle DB
- ❌ NO billing UI (è B.8, post-fiscal)
- ✅ Solo presentation layer V3 + JWT storage + account dropdown header

**Guardrail Claude:** non introdurre OAuth, social login, "claim nickname", reset password tramite SMS, 2FA, magic link. Se serve qualcosa oltre register/login form base + JWT cookie/localStorage + dropdown header → fermarsi e chiedere.

| Task | Effort | Priorità |
|------|--------|----------|
| Sign-up form modal V3 (`auth_signup.js` NEW MODULO V3, ~150 LOC) — email + password + display_name + consent checkbox ToS/Privacy → `POST /api/v1/auth/register` | **DONE 26/04** (bundle in `auth_signin.js`) | Modal con `display_name` + email + password (min 8 chars) + ToS checkbox required. `POST /api/v1/auth/register`, on success: `lmAuthWriteTokens()` + reload. Errore inline. Network error gestito. Bundled in `auth_signin.js` per ridurre LOC totali. |
| Sign-in form modal V3 (`auth_signin.js` NEW MODULO V3, ~100 LOC) → `POST /api/v1/auth/login` → JWT in `localStorage`, refresh token in cookie httpOnly se possibile | **DONE 26/04** | `frontend_v3/assets/js/dashboard/auth_signin.js` (~280 LOC totale incl sign-up). Modal email + password, `POST /api/v1/auth/login`, `lmAuthWriteTokens()` su access+refresh, reload page. Cross-link sign-up/sign-in nel footer modal. Esc + click overlay chiudono. Mobile full-screen via `auth.css` media query ≤640px. |
| Account dropdown header V3 (`auth_header.js` NEW MODULO V3, ~80 LOC) — avatar con iniziali, menu "Profile / Logout", state-aware (anonymous → "Sign in" button, logged → dropdown) | **DONE 26/04** (semplificato) | `lmRenderAuthSlot()` in `auth_signin.js` popola `#lm-auth-slot` nell'header. Anonymous → "Sign in" + "Sign up" CTA. Logged → "Hi, {display_name}" + tier badge gold + "Logout" button. Logout: `POST /api/v1/auth/logout` (best-effort revoke) + `lmAuthClearTokens()` + reload. Slot wirato in `dashboard.html` accanto a Guide button. Re-render auto post-loadProfile + setTimeout fallback. |
| Forgot/reset password flow minimal — modal "Reset password" → `POST /forgot-password` con messaggio "Check your email", landing `/reset-password?token=...` con form nuovo password → `POST /reset-password` | **DONE 26/04 (frontend)** — `lmShowForgotPassword()` + `lmShowResetPassword(token)` in `auth_signin.js`. Sign-in modal ha link "Forgot password?". Submit forgot → `POST /api/v1/auth/forgot-password` (anti-enumeration: backend ritorna sempre 200). Auto-apertura reset modal se URL contiene `?reset_token=…`. Confirm password con match check. On success, strip `?reset_token` da URL via `history.replaceState` + redirect a sign-in. **GAP backend**: `backend/api/auth.py:134` ha `# TODO: send email with reset link` — il token è generato ma NON inviato via mail. Fix backend richiesto prima del go-live: usare SMTP setup esistente (`/tmp/.smtp_pass`, sender `monitorteamfe@gmail.com`) per inviare link tipo `https://metamonitor.app/dashboard.html?reset_token=<token>`. |
| JWT lifecycle wiring globale: ogni `fetch()` autenticata aggiunge `Authorization: Bearer <token>`. Auto-refresh su 401 prima del retry. Logout su refresh fallito. | **DONE 26/04** | `auth_bootstrap.js` esteso: wrap `window.fetch` intercetta `/api/v1/*`, inietta `Authorization: Bearer <token>` da `localStorage.lm_access_token`. Auto-refresh su 401 via `POST /api/v1/auth/refresh` con coalescing concurrent (single inflight promise), retry 1×. Helpers `lmAuthWriteTokens(access, refresh)`, `lmAuthClearTokens()`, `lmAuthReadToken()`. Pulizia legacy keys `access_token`/`auth_access_token`. Endpoint esterni (cards.duels.ink, ecc.) skippano wrap. Anonymous resta default (no token = no header, endpoint pubblici continuano a funzionare). 215 LOC totali (sotto cap 800). |
| QA mobile: tutti i form full-screen su ≤640px (no modal scrollable cropped), keyboard handling iOS, autofocus. | 0.5 dev day | P0 |
| **Backend: send password reset email** | **DONE 26/04** — `backend/services/email_service.py` (NEW) con `send_password_reset_email(email, raw_token)`. Riusa pattern SMTP via `/tmp/.smtp_pass` + sender `monitorteamfe@gmail.com`. Configurabile via env: `LM_MAIL_FROM`, `LM_SMTP_PASS_FILE`, `LM_BASE_URL` (default `https://metamonitor.app`), `LM_SMTP_DISABLED=1` per dev/CI. Wirato in `auth.py::forgot_password`: best-effort, errori loggati ma mai propagati al client (anti-enumeration). Body include link `<LM_BASE_URL>/dashboard.html?reset_token=<token>` (auto-detected da `auth_signin.js`). Smoke test in disabled mode → False (atteso). **Pre-go-live**: restart `systemctl restart lorcana-api` per caricare il modulo + smoke con email reale. |

**Test backend pre-existing (no nuovo endpoint):** smoke `scripts/auth_smoke_test.py` (NEW) → register → login → me → logout → reset-password roundtrip. Run con account temp.

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
| `user_feedback` table + `POST /api/v1/feedback` rate-limited + sticky feedback button/modal V3 (kind, text, page_url, ua, auto-context) | **DONE 26/04** | Migration `a3f8e2c91b4d` (`user_feedback` PG: id UUID, user_id FK nullable, kind, message, page_url, user_agent, ip_hash SHA256, status, triage_notes, created_at, triaged_at). `backend/models/feedback.py` (UserFeedback + OpsIncident). `backend/api/feedback.py` POST /api/v1/feedback con `get_optional_current_user` (anon-tolerant), rate limit 5/die user + 3/die anon-IP, ip_hash mai raw IP. Frontend sticky `feedback_button.js` (gold pill bottom-right, NON in tab Deck/Team/Play — rispetta hardblock), modal con kind dropdown (general/bug/request/coach_issue) + textarea 4-4000 chars + auto-capture page_url+UA. Riusa `auth.css` shell (zero nuovi CSS file). Smoke 201 + cleanup OK. |
| `ops_incidents` table + `backend/services/incident_reporter.py::report_incident()` | **DONE 26/04** | Migration `a3f8e2c91b4d` (stessa, `ops_incidents` PG: id UUID, source, severity ENUM[info|warn|error|critical], payload JSONB, status, created_at, digested_at + 3 indici). `backend/services/incident_reporter.py`: `report_incident(source, severity, payload)` apre proprio session, swallowed exceptions (mai propaga). `capture(source, severity)` context manager per try/except style su cron. |
| Wiring cron/worker critici: import matches, KC batch, matchup reports, snapshot assembler, monitor unmapped, KC freshness, backup | PENDING | `catch + report_incident()` su failure; digest mostra solo `severity >= warn`, DB conserva tutto. Pattern: aggiungere `with capture(source="<cron_name>", severity="error"): main()` all'entry point di ogni cron. Stima: 30min per ~6 cron. |
| `daily_health_digest.py` 07:30 UTC → mail unica a `monitorteamfe@gmail.com` | **DONE 26/04** (script ready, cron schedule manual) | `scripts/daily_health_digest.py` (NEW): legge ultime 24h `user_feedback status=new` + `ops_incidents status=new severity>=warn`, formatta digest text con header window/counts + sezioni FEEDBACK by kind + INCIDENTS by severity. SMTP via Gmail (riusa pattern `cron_health_report.py`), `LM_SMTP_DISABLED=1` per dry-run. Su send success marca rows come `digested`. Smoke dry-run OK. **Ops**: aggiungere a crontab `30 7 * * *` per VPS dopo go-live. |
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

### B.7 Progress snapshot (aggiornato 26/04)

| Sub | Stato | Cosa manca |
|-----|-------|------------|
| B.7.0 prereq | **DONE 3/4** | Stripe webhook (in B.8, post-fiscal) |
| B.7.0.5 V3 auth bootstrap | **DONE** | — |
| B.7.1 Layered rendering tab Team | **DONE 3/3** | — |
| B.7.2 Roster gestionale | **DONE 2/3** (backend) | UI `team_roster_editor.js` |
| B.7.3 Nickname binding | PENDING | gz_internal_nick parser + `replay_nick_bindings` table + UI student-picker + cron validation |
| B.7.4 Replay queue + review states | PENDING | migration `team_replays` + 3 endpoint + UI queue panel `team_queue.js` |
| B.7.5 Session notes visibility | PENDING | migration `replay_session_notes.visibility` + endpoint extension + UI toggle |
| B.7.6 Coach feedback hook | PENDING | extension B.6 `user_feedback.kind=coach_issue` |
| B.7.7 GDPR cascade + audit log | PENDING | revoke flow + cascade + `replay_access_log` table |
| B.7.8 Notifications & realtime | PENDING | polling + mail "Coach reviewed" + extension B.6 daily digest |
| B.7.9 Discord integration | PENDING (Fase 2 opzionale) | bot OAuth + sync membri |

**Effort residuo onesto:** ~18-20 dev day in scope (B.7.2 UI + B.7.3-B.7.8). B.7.9 Discord +5-7 day se attivata. Sequencing: B.7.2 UI → B.7.3 → B.7.4 (cuore Coach view) → B.7.5 → B.7.7 → B.7.8 → B.7.6.

### B.7.0 Tier gating + beta access (prerequisito)

| Task | Effort | Impatto |
|------|--------|---------|
| Stripe webhook → `users.tier='coach'` post-checkout (riusa `subscription_service.create_checkout_session`, già scaffold). Test con account dev Stripe + dry-run. | **PENDING** (richiede struttura fiscale SRL chiusa, BP §6.3; coordinato con B.8 Stripe & Billing) | Alto |
| Beta redemption code: riuso `promo_service.granted_tier='coach'` + endpoint `POST /api/v1/promo/redeem-beta`, distribuibile a 5-10 power-coach prima di Stripe live. Codici scadono dopo N giorni o never (param). Audit log redemption. | **DONE 26/04** — endpoint `backend/api/promo.py:91 redeem_beta_code` con doppia validazione (`type='tier_upgrade'` + `granted_tier='coach'`), opaque error per non leakare codici non-beta, audit log via logger (`code, user, tier, expires, ip, ua`). Riusa `promo_service.redeem_promo` esistente. Codici creati via `POST /api/v1/promo/create` con `granted_tier=coach` + `expires_at` opzionale. | Alto (dogfooding) |
| `User.preferences.team_view_mode` (`player`/`coach`, default `coach` se `tier=coach`, sennò non applicabile). Endpoint `PUT /api/v1/user/preferences` già accetta whitelist (`user_service.py::ALLOWED_PREFS`) — aggiungere `team_view_mode` lì. | **DONE 26/04** — `team_view_mode` aggiunto a `ALLOWED_PREFS` in `user_service.py`. Endpoint PUT esistente lo accetta. Default UI fallback gestito in frontend (B.7.1). | Medio |
| **Tier `team` legacy compatibility**: `users.tier` ENUM oggi accetta `free|pro|coach|team` (`team` è valore storico pre-`coach`). Default policy B.7: `tier='team'` mappato a Coach Workspace capability (alias temporaneo) per non rompere user paganti esistenti. Decisione finale di prodotto sul tier `team` (deprecate / alias permanente / tier intermedio €19) tracciata in B.7.Y. Nessun nuovo signup deve poter scegliere `team` — restringere `interest_to_pay` pattern a `(pro\|coach)` in `backend/api/user.py`. | **DONE 26/04** — `users.tier` è VARCHAR(20), no ENUM Postgres. `TIER_LEVEL` (`backend/deps.py:20`) e `TIER_LIMITS` + `UPLOAD_REPLAY_LIMITS` (`backend/middleware/rate_limit.py`) estesi con `coach=2` allo stesso livello di `team=2`. `InterestRequest` pattern (`backend/api/user.py:53`) ristretto da `(pro\|coach\|team)` a `(pro\|coach)`. Nessun nuovo signup può scegliere `team`; legacy paganti `team` mantengono Coach capability via alias. Frontend non posta `tier='team'`, breaking change safe. | Alto (no silent default-deny per pagante) |
| **B.7.0.5 V3 auth bootstrap** (prereq trovato durante implementazione B.7.1 — non era listato originariamente nello spec) | **DONE 26/04** — nuovo `frontend_v3/assets/js/dashboard/auth_bootstrap.js` (~95 LOC) carica `/api/v1/user/profile` da JWT su localStorage, espone `window.LM_USER = {id, email, tier, is_admin, team_view_mode, ...}` + `lmTierLevel()` + `lmEffectiveTeamView()`. Wired in `frontend_v3/dashboard.html` prima di `monolith.js`. Re-render automatico quando profilo carica (non blocca initial render). | Alto (prerequisito infra) |

### B.7.1 Layered rendering tab Team (player / coach view)

| Task | Effort | Impatto |
|------|--------|---------|
| `renderTeamTab()` in `team.js` switch su `(tier, team_view_mode)`: free+team→KPI+roster cards read-only (oggi), pro→+analytics avanzate (read-only), coach+coach-mode→full workspace, coach+player-mode→stessa vista pro. | **DONE 26/04** — `team.js` helpers `ttResolveView()` + `lmEffectiveTeamView()` (in `auth_bootstrap.js`) + `lmTierLevel()` mappano `(tier, team_view_mode)` → `'free'|'pro'|'coach'|'coach_player'`. `renderTeamTab` early-return + final `main.innerHTML` usano lo stato. Legacy roster path resta intatto, wrapping additive. | Alto |
| Toggle Player/Coach view nell'header del tab Team (visibile solo se `tier=coach`). Persistenza in `preferences.team_view_mode`. | **DONE 26/04** — `buildLayeredTeamStrip()` rende la strip toggle, visibile solo per `isCoachTier=true` (include alias `team`). `lmSetTeamViewMode(mode)` aggiorna `window.LM_USER` + `localStorage` + chiama `PUT /api/v1/user/preferences` (best-effort) + re-render. | Medio |
| Empty states differenziati: (no team / free with team / coach without students / coach onboarding). Soft-gating upsell card per pro→coach: "Upgrade to manage students". | **DONE 26/04** — 3 helper builder: `buildFreeEmptyTeam`, `buildProEmptyTeam`, `buildCoachOnboardingEmpty`. Pro→Coach upsell card via `buildProUpsellToCoachCard()` injected sopra il roster path quando `tier='pro'`. | Medio (conversion) |

### B.7.2 Roster gestionale + CSV import

| Task | Effort | Impatto |
|------|--------|---------|
| Migration additiva `team_roster`: `+ coach_id FK users, student_user_id FK users NULL, display_name, status_admin ENUM[invited|active|paused|archived], duels_nick, duels_nick_status ENUM[missing|unverified|linked|conflict], discord_username, discord_id, notes, revoked_at`. Backfill rows esistenti come `coach_id=NULL` (roster legacy team-wide resta accessibile a admin). | **DONE 26/04** — migration `d5a8f3e1c2b9` applicata. ENUM-as-VARCHAR (matches `users.tier` pattern). Drop legacy `UNIQUE (name)` (impossibile a multi-coach scale). Partial unique idx `(coach_id, display_name)` WHERE NOT NULL. Partial idx `(coach_id)` + `(student_user_id)` per query ottimali. Backfill `display_name = name` per legacy rows. CASCADE su `users(coach_id)`, SET NULL su `users(student_user_id)`. | Alto (foundation) |
| Endpoint `POST /api/v1/team/students` (single CRUD) + `POST /api/v1/team/students/bulk` (CSV: display_name, duels_nick?, discord?). Parser server-side, validazione nick contro `matches` table (max 10k row check). Quote: max 50 studenti per coach. | **DONE 26/04 (backend only)** — 4 endpoint con `require_tier("coach")` (alias `team` accettato): `GET /api/v1/team/students`, `POST /api/v1/team/students` (single, quota 50, dedup via unique idx), `POST /api/v1/team/students/bulk` (max 200 rows/req, per-row error reporting, quota enforcement), `DELETE /api/v1/team/students/{id}` (soft archive, no hard delete per audit). `duels_nick` validation deferita a B.7.3 cron — al create/import status='unverified'. | Alto |
| UI `team_roster_editor.js` (NEW MODULO V3): tabella editabile, add/remove/edit inline, import CSV button, badge `Linked · 47 matches` / `Missing — ask student to play`. | **PENDING** (sessione successiva — B.7.2 UI dipende da backend done) | Alto |

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

## B.8. Billing & Stripe checkout — wiring reale (post-fiscal)

**Goal:** sostituire fake paywall + interest tracking con Stripe checkout reale, una volta che la struttura fiscale (P.IVA, regime, fatturazione UE) è chiara. Backend ha già `subscription_service.create_checkout_session()` scaffold; manca wiring UI + webhook + customer portal.

**Vincolo blocker (memoria `project_apptool_status` + A.6):** non implementare prima di struttura fiscale chiara. `interest_to_pay` resta meccanismo di tracking finché non c'è P.IVA + fatturazione automatica configurate.

**Vincoli non-negoziabili:**
- ❌ NO billing prima di fiscal setup (P.IVA, IVA OSS UE, regime fatturazione)
- ❌ NO crediti API Anthropic per processi billing (memoria `feedback_claude_subscription_not_api`)
- ❌ NO altri provider fuori da Stripe (no Paddle, no LemonSqueezy — riusare scaffold esistente)
- ✅ Riusare `subscription_service.create_checkout_session()` esistente
- ✅ Webhook secret in `/etc/apptool.env` (0600) come `APPTOOL_ADMIN_TOKEN` pattern

**Guardrail Claude:** non avviare nessuna delle entry sotto finché il blocker fiscale non è chiuso. Se richiesto, partire da webhook backend + smoke test in dev (Stripe test mode), poi UI checkout, poi customer portal. Mai bypassare webhook signature validation. Mai esporre `STRIPE_SECRET_KEY` in frontend.

| Task | Effort | Priorità |
|------|--------|----------|
| Wiring Stripe webhook backend `/api/v1/webhooks/stripe` (route già scaffold in `backend/main.py`) → su `checkout.session.completed` setta `users.tier='pro|coach'` + audit log | 1 dev day | P0 |
| UI Upgrade modal V3 (`billing_upgrade.js` NEW MODULO V3) — pricing card con Pro €10/m + Coach €39/m + button "Subscribe" → `POST /api/v1/billing/checkout` → redirect Stripe Checkout. Sostituisce fake paywall + interest tracking. | 1.5 dev day | P0 |
| Customer portal Stripe — button "Manage subscription" in account dropdown → `POST /api/v1/billing/portal` → redirect Stripe portal (cancel, update payment method, invoices history) | 0.5 dev day | P0 |
| Migration `interest_to_pay → real conversion`: per user con `preferences.interest_to_pay` esistente, mostra banner "We're live! Activate your subscription" che li porta direttamente al checkout | 0.5 dev day | Alto (recover early interest) |
| Webhook Stripe per `customer.subscription.deleted` → downgrade `tier='free'` con grace period 7gg. Mail al user con link reactivate. | 1 dev day | P0 |
| Endpoint admin `GET /api/v1/admin/subscriptions` (gated `X-Admin-Token`) per audit MRR + active subscriptions count | 0.5 dev day | Medio |

**Test smoke (Stripe test mode):** `scripts/billing_smoke_test.py` (NEW) — register → login → checkout (test card 4242) → webhook fires → `tier='pro'` → portal → cancel → grace period.

**Coordinamento con B.7.0:** Stripe webhook in B.7.0 ("Stripe webhook → users.tier='coach' post-checkout") è subset di questo B.8. Se B.7 viene avviato prima di B.8, allora B.7.0 implementa il webhook minimo solo per Coach tier; B.8 lo estende a Pro + customer portal + grace period.

---

## B.9. NON in B — resta fuori scope 30 gg

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

**Stato 26/04:** key OpenAI ruotata e verificata; test reale `EmSa vs AmyE` Core OK dopo repair automatico `response_missing_named_card`; DB sorgente ha `digest_hash`, `prompt_contract_hash`, `schema_version`, `response_v2_complete=6/6`, `v3_payload_complete=6/6`, `self_check_complete=6/6`. Sync Core verso `matchup_reports` eseguito.

**Stato 26/04 (validator wave):** `pipelines/kc/validator.py` v1.0 + `scripts/audit_killer_curves.py` + `scripts/kc_consistency_check.py` + wiring `generate_killer_curves.py::generate_one` con CLI `--quality-gate {off|warn|strict}` (default `warn`). Audit DB (265 rows current) → 1 PASS / 14 WARN / 250 BLOCKED — coerente con batch 04-21 pre-blindatura. Consistency `kc → mr` clean (0 P0 drift, 5 ghost rows P2). Smoke test reali con strict gate: $0.111 OpenAI, 1/2 PASS end-to-end (`EmSa vs AmyE` Core), 1/2 correctly blocked (`AmSa vs AmyE` Core). UI consumer V3 di `v3_payload` wirato in 2 tab: Play (`coach_v2.js::kcRenderV3Payload`) + Deck (`deck_matchups.js::_curvesBlockHtml` con coach_badges/one_line_hook/mulligan_focus inline). Filter `--quality-filter blocked` (default) in `refresh_kc_matchup_reports.py` impedisce alle BLOCKED di propagarsi al blob V3. Pipeline end-to-end pronta per batch martedì 28/04 con gate `warn` + filter sync `blocked`. Strict gate KC da attivare dopo primo batch clean.

**Guardrail Claude:** non lanciare `--format all`, non usare `--force`, non cambiare modello e non toccare la key OpenAI. Prima implementare validator deterministico e testarlo su righe esistenti. Ogni chiamata OpenAI reale deve essere single-pair, motivata e confermata dall'utente. Non pubblicare dati KC se il validator trova P0. Il repair LLM deve correggere solo il JSON già prodotto, non cambiare deck/format/sequence arbitrariamente.

| Task | Stato | Nota |
|------|-------|------|
| Repair automatico singolo per `response_missing_named_card` | PARTIAL | Implementato in `scripts/generate_killer_curves.py`; serve test su 3-5 matchup Core/Infinity, incluso caso che falliva (`AbSt` vs `SSt` Infinity) |
| Validator hard condiviso `pipelines/kc/validator.py` | **DONE 26/04** | `pipelines/kc/validator.py` v1.0 (~440 LOC). Check P0: deck/format mismatch, JSON struct, curve required (id/name/sequence/response), response v2 fields presenti, response.cards exist+core-legal+on-color, 3-tier META/FALLBACK_CORE_LEGAL/DROP, response_missing_named_card (regola killer.md), sequence.plays exist+core-legal+on-opp-colors+non-empty. P1 warn: v3_payload missing/incomplete, EN heuristic, priority_actions/what_to_avoid length, key_cards/combo/recursion off-color. P2 info: self_check missing/incomplete. Output: quality_status (pass/warn/blocked), errors/warnings/info, drop_metrics granulari, completeness pct. |
| Audit script `scripts/audit_killer_curves.py` read-only su DB | **DONE 26/04** | Run su 265 righe `is_current=true` → 1 PASS, 14 WARN, **250 BLOCKED**. Top P0: `response_missing_named_card` (514), `sequence_card_core_illegal` (386), `response_v2_incomplete` (258), `card_core_illegal` (219), `card_not_in_db` (3 = LLM hallucination). Le 250 blocked sono quasi tutte del batch 04-21 pre-blindatura 25/04 — atteso che martedì 28/04 batch full le rigeneri con nuove regole. Report in `/tmp/kc_audit.json`. |
| Schema validation prima dell'upsert + `quality_status/errors/warnings` in `meta` | **DONE 26/04** | Wirato in `scripts/generate_killer_curves.py::generate_one`: post-repair, pre-upsert chiama `validate_kc()`. CLI flag `--quality-gate {off|warn|strict}` (default `warn`). In strict, `blocked` aborta upsert con status `ERR:quality_blocked`. In warn, upsert procede ma `meta` riceve `quality_status`, `quality_errors`, `quality_warnings`, `quality_drop_metrics`, `quality_completeness`, `validator_version`, `quality_gate_mode`. Smoke: import + `--help` OK. |
| Drop metrics granulari | **DONE 26/04** | `validator.py::drop_metrics` separa `response_cards_off_color`, `response_cards_core_illegal`, `response_cards_not_in_db`, `response_cards_non_meta`, `response_cards_kept_meta`, `response_cards_kept_fallback`, `sequence_plays_*` simmetrici. Salvati in `meta.quality_drop_metrics`. |
| Smoke test single-pair end-to-end con validator wirato | **DONE 26/04** | 2 run reali con `--quality-gate strict --force`: (a) `--pair AmSa AmyE` Core → `ERR:response_missing_named_card` (gate preesistente blocca, repair shot fallisce; in strict mode upsert abortito = comportamento corretto); (b) `--pair EmSa AmyE` Core → OK pass, validator wirato e meta arricchito (`validator_version=1.0, quality_status=pass, quality_gate_mode=strict, n_errors=0, n_warnings=0, completeness 6/6, drop_metrics: 12 kept_meta, cost_usd=0.0517`). Costo totale 2 test: **$0.111**. Confermato wiring end-to-end + persistenza meta. |
| Consistency check `killer_curves` → `matchup_reports` → dashboard blob | **DONE 26/04** | `scripts/kc_consistency_check.py` (NEW). Detecta P0 drift (`missing_in_mr` con curve > 0, `orphan_in_mr`, `curve_count_mismatch`), P1 (`blocked_but_published`), P2 info (`ghost_in_kc` con `curves=[]`). Exit 1 se drift P0. Run baseline 26/04: clean — 0 P0, 0 P1 blocked, 5 ghost legacy P2. Da lanciare post-batch martedì + post-`refresh_kc_matchup_reports.py` per verificare sync. |
| Consumer UI di `v3_payload` in V3 (`coach_v2.js`) | **DONE 26/04** | Era "aperto" in `KILLER_CURVES_BLINDATURA_V3.md` §6.4. Wirato in `frontend_v3/assets/js/dashboard/coach_v2.js`: nuova `kcRenderV3Payload(p3, compact)` espone `coach_badges` (gold pill chips), `one_line_hook` (headline gold-bold), `mulligan_focus` (bullet list "Mulligan Priority"), `turn_checklist` (rows T1/T2/T3). `kcRenderResponse` esteso accetta `opts.v3Payload`; v3 elements precedono v2 sections. Fallback `user_copy.expanded` se v2 assent. `threatBriefs` propaga `v3_payload: curve.v3_payload`. Tutte le stringhe HTML-escaped. Graceful per righe legacy senza payload (rendering invariato). Syntax check Node OK. Sblocca consumo dei coach badges già nelle righe del 26/04 (`EmSa vs AmyE` Core ha `v3_payload_complete=6/6`). |
| Consumer UI di `v3_payload` in tab Deck (`deck_matchups.js`) | **DONE 26/04** | `_curvesBlockHtml` esteso: `coach_badges` (max 2) come pillole gold inline accanto al curve name, `one_line_hook` come row gold-bold sotto header, `mulligan_focus` (max 2, joined `·`) come row "Mulligan: …" con border-left gold. CSS nuove classi `.mh-exp-coach-badge`, `.mh-exp-hook`, `.mh-exp-mulligan`, `.mh-exp-mul-lbl` in `deck_summary.css`. Compatto perché Deck è denso (più matchup contemporanei). Graceful: curve legacy senza `v3_payload` invariate. Syntax check Node OK. |
| Filter `quality_status` nel sync `killer_curves → matchup_reports` | **DONE 26/04** | `scripts/refresh_kc_matchup_reports.py` esteso con CLI `--quality-filter {none,blocked,non-pass}` default `blocked`. Righe `meta.quality_status='blocked'` non vengono copiate in `matchup_reports` (quindi non passano al blob V3). Righe legacy senza `quality_status` sempre sincronizzate (no regression). Conteggi `synced`/`skipped` + breakdown per status. Smoke 26/04 con `--quality-filter blocked --format all`: 265 sync, 0 skipped (atteso, tutte legacy). Dal batch martedì 28/04 in poi le BLOCKED nuove saranno filtrate. |
| Batch completo KC martedì 28/04 con `--quality-gate warn` | PENDING | Cron esistente martedì 01:30 — già configurato. Per primo batch post-validator: usare `warn` (default) per popolare DB completo + flagare in meta. Strict alza la barra dopo che il DB è clean. Post-batch: `refresh_kc_matchup_reports.py --format all` + `/api/v1/dashboard-data?refresh=true`. |

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

*Update 25-26/04: Sezione A pre-launch chiusa code-side. B.2 Session notes MVP A (`replay_session_notes`, owner-only, dual-write JSONB+table). B.3 Privacy hardening completo (rate limit upload, DELETE replay round-trip, `user_consents` append-only). B.5 Improve nickname onboarding hero. B.1 nickname bridge stats card. A.5 privacy boundary copy fixes.*

*Update 26/04 sera: B.7 Coach Workspace foundation in corso. **DONE oggi**: B.7.0 (3 di 4: tier `coach`+alias+InterestRequest pattern restricted, `team_view_mode` pref whitelisted, beta redemption code endpoint con audit log) + B.7.0.5 V3 auth bootstrap (prereq trovato) + B.7.1 Layered rendering tab Team (3 di 3) + B.7.2 backend (migration `d5a8f3e1c2b9` `team_roster` Coach Workspace columns + 4 endpoint students). **Stripe webhook centralizzato in B.8** (post-fiscal SRL, blocker decisione struttura). **Migrations live:** alembic head `d5a8f3e1c2b9`. **Resta in B.7:** UI roster editor (B.7.2), B.7.3 nick binding gz_internal, B.7.4 replay queue, B.7.5 visibility, B.7.6 feedback hook, B.7.7 GDPR cascade, B.7.8 notifications, B.7.9 Discord (opzionale Fase 2).*

*Update 26/04 notte (validator wave + auth UI + git backup + smoke):* C.7.4 KC quality sprint chiuso (validator deterministico + audit + consistency + sync filter `--quality-filter blocked` + UI consumers Play/Deck + KC prompt v3_payload + LEGAL_FALLBACK_POOL). A.7 Auth UI minima chiusa lato frontend (sign-in/sign-up/forgot/reset password + account header slot + JWT lifecycle wiring globale + auto-refresh) + backend `email_service.py` per password reset (env-configurabile, `LM_SMTP_DISABLED=1` per CI). **Git push completato**: 9 commit oggi su `origin/dev` (HEAD = `540e3f4`), working tree clean, `scripts/.unmapped_monitor_state.json` ora in `.gitignore`. **Backend `lorcana-api` restartato 17:07 UTC**, smoke endpoint critici tutti verde: `/api/v1/auth/register|login|me|refresh|forgot-password` 200/201, `/api/v1/dashboard-data` blob 9MB. **Pre-go-live restano**: QA mobile auth flow (browser umano), V3 swap one-liner, batch KC martedì 28/04 01:30, refresh blob post-batch.*
