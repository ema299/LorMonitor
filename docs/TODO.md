# App_tool — TODO Master

**Ultimo aggiornamento:** 24 Aprile 2026 (sera — A.1 + A.2 + A.3 partial chiusi)
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
| **How to Respond** inline in killer curve expansion (refactor A2, 24/04 sera) | **DONE** | gate per-curve: prime 3 curve free, 4ª+ con overlay paywall quando matchup >3/giorno |
| **Mulligan reveal gated** | **DEFERRED** | richiede toccare Deck/Improve, rinviato per isolamento Play-only |
| **Paywall 4° matchup/giorno** | **DONE** | nuovo `play_gate.js` (55 LOC), counter localStorage `play_matchups_viewed_YYYY-MM-DD`, overlay su "How to Respond" dal 4° matchup distinto |
| **Home headline insight teaser** | **DONE** | worst matchup (min 20 games) sopra hero-row, click → Play con deck+opp preselezionati |

## A.4. Board Lab — wiring minimo

**Obiettivo pre-launch:** upload owner-only funziona + access-control attivo. Flusso completo resta nel legacy `team_coaching.js` (NO refactor).

| Task | Dove | Effort | Priorità |
|------|------|--------|----------|
| Verifica `require_replay_access` / `require_replay_owner` wired su `/api/v1/team/replay/*` | `backend/api/team.py` dependency injection | 1 h | P0 |
| Verifica ownership `team_replays.user_id` attiva (migration M1 `9a1e47b3f0c2`) | PG check | 15 min | P0 |
| Stub `team.js:300` "coming soon" — lasciare così, decidere se nascondere o mostrare placeholder | `frontend_v3/assets/js/dashboard/team.js:300` | 15 min | P1 |

## A.5. Go-live ops

| Task | Dove | Effort | Priorità |
|------|------|--------|----------|
| **V3 swap one-liner** — `FRONTEND_DIR` in `_serve_dashboard()` da `frontend/` a `frontend_v3/`. Eseguire come ULTIMA azione settimana 1. | `backend/main.py` | 5 min + restart | P0 (ultima azione) |
| QA end-to-end: tab switch, paywall triggers, consent flow, upload owner-only, mobile + desktop | manuale | 1 dev day | P0 |
| Verifica service worker `frontend_v3/sw.js` self-destruct pulisce cache utenti legacy | client-side monitoring | auto | P1 |

## A.6. Ciò che NON si fa pre-launch (decisioni preservate)

Se qualcuno propone uno di questi, rispondere "post-launch" e non discutere. Vale anche per Claude.

- ❌ Ristrutturazione nav 5+2 / drawer "..." / creazione tab Community contenitore / Pro Tools
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
| Header "Your improvement path" con 3-4 step ordinati basati sul dato utente ("1. Your worst matchup → study. 2. Your mulligan WR → practice. 3. Your curve drop → fix") | 1 dev day | Alto (retention Pro) |
| Nickname bridge più utile: quando bridge attivo, mostrare "X match associati, Y% WR personale" in Home + Improve | 1 dev day | Alto (feature hook, sblocca country segmentation futura) |
| Confidence / sample size surface su Mulligan ("Based on N hands, confidence: low/med/high") | 0.5 dev day | Medio (honesty) |
| Blind Playbook personalizzato per-matchup (non solo per-deck) | 2 dev day | Medio |

## B.2. Board Lab — da stub a flusso coach

Oggi Board Lab vive nel legacy `team_coaching.js`. Per giustificare il Coach tier €39/m serve ownership completa + coach flow.

| Task | Effort | Impatto business |
|------|--------|------------------|
| Upload/delete owner-only verificati end-to-end (include `DELETE /api/v1/team/replay/:id` con `require_replay_owner`) | 0.5 dev day | Alto (Coach tier justification) |
| Session notes persistenti per replay | 2 dev day | Alto (Coach tier) |
| Coach flow più chiaro: landing Team → upload → viewer → notes → export | 2 dev day | Alto (Coach tier) |
| Export PDF sessione (base: snapshot + note) | 2 dev day | Medio |

## B.3. Privacy — hardening

| Task | Effort | Impatto business |
|------|--------|------------------|
| Tabella `user_consents` dedicata (se serve versioning append-only) invece di JSONB `preferences.consents` | 1 dev day | Basso (compliance seria) |
| Rate limit upload replay (DoS prevention + abuse) | 0.5 dev day | Medio |
| `DELETE /api/v1/team/replay/:id` endpoint + UI trigger | 0.5 dev day | Alto (GDPR right to delete) |

## B.4. Play — evoluzione post-lancio

| Task | Effort | Impatto business |
|------|--------|------------------|
| Replay Viewer inline "See it happen" sulla killer curve (se dati engagement post-launch lo giustificano) | 2-3 dev day | Medio |
| How to Respond **personalized** (non più archetype-based) — Feature B LLM batch | 1 settimana + $3-5/m OpenAI | Alto (sblocca anche Key Threats + Sideboard in un solo cantiere) |
| Best Plays top-3 sequenze NOSTRO deck vs opp | 1 dev day | Basso-medio |

## B.5. Home + acquisition

| Task | Status | Nota |
|------|--------|------|
| Set 12 Hub `FORM_ACTION` + `FORM_EMAIL_FIELD` + `DISCORD_INVITE` → URL reali | **BLOCKED** | attesa Google Form + Discord server. Marcatore `BLOCKED_URL_PENDING` in `set12_hub.js`. Non bloccante lancio. |
| Set 12 Hub → decommissionare post drop Maggio, rimpiazzare con evergreen hero | PENDING | 0.5 dev day, impatto medio |
| Improve onboarding più aggressivo sul nickname bridge | PENDING | 0.5 dev day, alto (sblocca Improve + country segmentation) |

## B.6. NON in B — resta fuori scope 30 gg

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

## C.3. V3 — `views/` scaffolding non wired

`assets/js/views/` (148 LOC totali, 8 file) sono placeholder per split futuro.

- Decidere: wire o rimuovere
- Raccomandazione: wire gradualmente quando si fa C.1 (profile.js split → home.js + improve.js useranno lo scaffolding)

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

### C.7.4. Invarianti KC da memoria

- KC full batch solo **martedì 01:30** — non lanciare run manuali (`project_kc_pipeline_cost`)
- KC Spy = canary $0.05/die
- OpenAI gpt-5.4-mini, mai crediti Anthropic API (`feedback_claude_subscription_not_api`, `project_api_constraint`)

### C.7.5. Canary + monitoring ops

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
| `replay_anonymizer.py` + wiring API | Live |
| `POST /api/v1/user/interest` + `POST /api/v1/user/consent` | Live |
| GDPR export esteso con `team_replays` | Live |
| Consent modal legacy + footer disclaimer + `/about.html` | Live legacy (porting V3 in §A.2) |
| Copy sanitization (no duels, no MMR/ELO, fair-use card images) | Live legacy |
| Email swap `legal@` → `monitorteamfe@gmail.com` | Live legacy. V3 da allineare dopo alias Cloudflare up |
| SW `CACHE_NAME=lorcana-privacy-v4` + network-first HTML | Live legacy (V3 ha self-destruct, vedi §C.4) |

**Head alembic:** 2 head parallele (`7894044b7dd3` Set12 cassetto dormant, `9a1e47b3f0c2` privacy — current). Alembic upgrade richiede revision esplicita (NON `upgrade head`).

---

*TODO consolidato il 24 Aprile 2026 (sera) reality-aligned. Sostituisce struttura precedente (§A App_tool legacy / §B V3 target-based / §C Migration). Nuova tassonomia: A = pre-launch, B = post-launch 30gg, C = tech debt. Sibling: [`BP.md`](BP.md) v4.1, [`V3_ARCHITECT_POINT.md`](V3_ARCHITECT_POINT.md) v1.1.*

*Update 24/04 sera: A.1 + A.2 + A.3 partial chiusi. A.3 Opzione B (Play-only soft gate via `play_gate.js`) implementato; Mulligan reveal deferred. Set 12 Hub URLs spostati in B.5 come BLOCKED non-blocker. Focus ora: A.4 Board Lab wiring minimo.*
