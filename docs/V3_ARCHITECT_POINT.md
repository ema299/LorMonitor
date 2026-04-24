# Lorcana Monitor V3 — Architettura + Product Overview

**Versione:** 1.1 reality-aligned | **Data:** 24 Aprile 2026 (sera)
**Scope:** documento architetturale + overview prodotto per il frontend V3 in `frontend_v3/`.

**Changelog 1.0 → 1.1 (reality-aligned dopo audit `V3_CURRENT_STATE.md`):**

La v1.0 descriveva un **target 5+2 drawer** derivato da `V3_ARCHITECT_POINT.md` originale (GPT 24/04 06:50). Il V3 reale è **7 tab primary flat** — decisione preservata per il lancio.

- **Riscritto §3** (Architettura): stato reale 7 tab, non target 5+2
- **Riscritto §4** (Tab-by-tab): stato reale + interventi pre-launch solo su Play; Meta/Deck/Events invariati
- **Riscritto §5** (Replay viewer placement): non si cambia pre-launch
- **Aggiunto §3.4** (Legacy vs V3): legacy è ancora production default, swap è una riga
- **Cancellato** §6-§8 v1.0 (User flow / Paywall / Cosa nascondere target-based)
- **Riscritto §11** (Evoluzione post-launch + tech debt reali)
- **Mantenuto integro** §12-§19 (Parte B: Product Overview, fonti dati, pipeline, cron, stack)

**Fonti consolidate:**
- `frontend_v3/point/V3_CURRENT_STATE.md` (stato reale 24/04) — **base per §3-§5 + §11**
- `frontend_v3/point/V3_ARCHITECT_POINT.md` originale (GPT 24/04 06:50) — riferimento target, usato solo dove compatibile
- `analisidef/business/V3_PRODUCT_OVERVIEW.md` (GPT 24/04 06:24) — **base per §12-§19**

Originali intatti nelle loro posizioni. Complementare a [`BP.md`](BP.md) (business) e [`TODO.md`](TODO.md) (operativo).

---

## 1. Cos'è Lorcana Monitor in una frase

Piattaforma analytics + community hub per **Disney Lorcana TCG**, costruita su 50K-300K match log turn-by-turn reali scrapati dai simulatori non ufficiali (`duels.ink`, `lorcanito`). Mostra al giocatore **come perde, con chi, in quale turno, e come rispondere** — con un livello di dettaglio che nessun altro tool Lorcana offre oggi.

Cuore tecnico: pipeline Python + LLM (OpenAI gpt-5.4-mini) che trasforma log grezzi in 268 killer curves validate, loss classification multi-livello, mulligan trainer su mani PRO reali, e replay viewer animato.

---

## 2. Problema di design (il cuore di V3)

Due viewer vivono in questo prodotto e non devono essere confusi:

1. **Replay Viewer** — superficie di consumo. Legge match reali da dati `duels.ink`. Playback board step-by-step, avversari anonimizzati. Passivo, read-only, insight-serving.
2. **Board Lab** — superficie di creazione / coaching. L'utente carica un `.replay.gz`. Il coach annota, cammina su linee alternative, esporta artefatto sessione. Attivo, write-enabled, coach-serving.

**Stato reale V3:** il Replay Viewer pubblico esiste nel legacy (`rv*` in `frontend/dashboard.html`); in V3 NON è esposto inline in Play oggi. Board Lab in V3 è stub (`team.js:300`), il flusso completo vive nel legacy `team_coaching.js` (1936 LOC copia). **Per il lancio si accetta questa realtà** — non si consolida il Replay Viewer in Play pre-launch, non si riscrive Board Lab pre-launch.

---

## 3. Architettura V3 — stato reale (24/04/2026)

Per l'evoluzione ipotizzata (5+2, drawer, Pro Tools) vedi §11 "Evoluzione post-launch". Quella è riflessione di lungo termine, non commitment.

### 3.1 Nav attuale (cosa c'è davvero)

**7 tab primary** (tab bar + bottom nav mobile, stesso elenco):

| # | Tab | Render module (file:linea) | Stato |
|---|-----|----------------------------|-------|
| 1 | Home | `profile.js:181` (`renderProfileTab`) | Maturo |
| 2 | Play | `coach_v2.js:1539` (`renderCoachV2Tab`) | **Debole — core commerciale da rafforzare** |
| 3 | Meta | `monitor.js:174` (`renderLadder`) | Maturo |
| 4 | Deck | `lab.js:998` (`renderLabTab`) | Maturo |
| 5 | Team | `team.js:116` (`renderTeamTab`) | Buono (Board Lab stub) |
| 6 | Improve | `profile.js:884` (`renderImproveTab`) | **Debole — raccolta strumenti, non percorso** |
| 7 | Events (+ Community) | `community_events.js` (render congiunto `renderEventsTab` + `renderCommunityTab`) | Maturo |

Dispatcher: `render()` in `monolith.js:639` (map tab → funzione).
Switch: `switchToTab(tabId)` in `monolith.js:112` aggiorna `body[data-active-tab]`, sync deck/opp state, call `render()`.

**No drawer "...", no Pro Tools tab, no Community tab separato.** Events e Community sono nello stesso tab (`monolith.js:712-721` concatena due div).

### 3.2 Cosa NON si tocca pre-launch

Decisioni preservate:

- **Non cambiamo la nav.** 7 tab restano 7 tab.
- **Non creiamo drawer "..."**.
- **Non fondiamo tab** (Community non diventa primary, Team non diventa sub).
- **Non facciamo rename.** Monitor/Coach V2/Lab sono già diventati Meta/Play/Deck.
- **Non tocchiamo Meta, Deck, Events** salvo bug. Sono già soddisfacenti.

### 3.3 Scaffolding layer non wired

`frontend_v3/assets/js/views/` contiene 8 file (home.js, play.js, meta.js, deck.js, improve.js, events.js, community.js, pro.js — 148 LOC totali) **non caricati da `dashboard.html` e non wired**. Sono placeholder per uno split futuro; oggi il rendering è tutto in `assets/js/dashboard/*.js`.

Questo layer NON va rimosso (è scaffolding futuro) ma non va neanche wired pre-launch (sarebbe refactor strutturale non giustificato).

### 3.4 Legacy vs V3 — non coincidono al 100%

- **Legacy `frontend/dashboard.html`** è ancora production default, servito da `backend/main.py:_serve_dashboard()` su `metamonitor.app/`.
- **V3 `frontend_v3/dashboard.html`** è staging, testabile via flag o path dedicato.
- **Lo swap al lancio è una riga**: cambio `FRONTEND_DIR` in `_serve_dashboard()` da `frontend/` a `frontend_v3/`.
- **Condividono gli stessi endpoint e blob** (`/api/v1/dashboard-data`, `/api/replay/public-log`, `/api/v1/user/interest`, ecc.).
- **Modifiche backend devono restare compatibili con entrambi** durante la finestra di transizione.

**Regola:** nessun big-bang refactor che spezzi uno dei due.

---

## 4. Tab-by-tab — stato reale + interventi pre-launch

Per ogni tab: (a) cosa c'è oggi, (b) cosa cambia pre-launch, (c) cosa NON si tocca. Focus correzioni pre-launch: **solo Play, Home insight teaser, Team wiring privacy.** Meta/Deck/Events non si toccano.

### 4.1 Home (`profile.js:181`) — Maturo

**Oggi:**
1. Identity header (avatar, nick, plan badge Free/Pro, settings, demo-mode indicator)
2. Identity form drawer (email, duels nick, lorcanito nick, country — localStorage)
3. Set 12 Hub (`set12_hub.js`, 406 LOC) — countdown `RELEASE_DATE=2026-05-12`, email signup, Discord CTA. **`FORM_ACTION` + `DISCORD_INVITE` sono placeholder** (`set12_hub.js:27-34`).
4. My Deck Curve
5. Meta Fitness top-3
6. My Decklists (`saved_decks.js`, localStorage `v3_saved_decks`)
7. Blind Playbook (lazy da `/api/v1/lab/iwd/{deck}/{format}`)

**Pre-launch:**
- (a) Sostituire placeholder `FORM_ACTION` + `DISCORD_INVITE` in `set12_hub.js:27-34` con URL reali — 15 min
- (b) Aggiungere **headline insight teaser** ("Your worst matchup is X · Open Play →") sopra matchup chip — dati già nel blob, solo render — 2 h

**Non toccare:** struttura, My Decklists flow, Blind Playbook lazy loading.

### 4.2 Play (`coach_v2.js:1539`, 1981 LOC) — DEBOLE, core commerciale

**Oggi:**
- Matchup selector (ink picker × ink picker)
- **Killer Curves** — top 5 opponent sequences, sortate per frequenza, ognuna con coverage signal (red/yellow/green da `deck_response_check.js`)
- **Secondary tabs** (`cv2SecTab`): Killer Cards (default) · Curves · Threat Responses · Card Ratings (da `card_analysis.js`)
- **Honesty badges** (formatted WR + confidence tier + game count via `honesty_badge.js`)
- Tutto wrap `wrapPremium(html, 'coach')` → paywall intent → POST `/api/v1/user/interest` (fake local unlock dopo click)
- Empty states: "Select Matchup" / "Data not available"

**Gap commerciale:**
- **Manca la narrativa "insight → killer curve → risposta"** che guida l'utente al paywall. Oggi la Play apre sulle curves senza header che inquadri l'intent.
- **How to Respond** esiste come sub-tab "Threat Responses" ma è generico archetype-based (vedi [`BP.md`](BP.md) §2.4 limitazioni). Va esposto come blocco dedicato, non nascosto in un tab.
- **Mulligan Trainer NON è in Play** (vive in Deck via `deck_improve.js` e in Improve via `improve_play_tools.js`). Per conversion clarity va almeno linkato da Play.

**Pre-launch (core business):**
- (a) **Header conversion** sopra killer curves: 1-2 righe di insight matchup-specific ("Questo matchup ti chiude a T5 con queste carte. Ecco come rispondi.") — 0.5 dev day
- (b) **How to Respond** come sezione dedicata (archetype-based ok per lancio), gated `wrapPremium('coach')` — 1 dev day
- (c) **Mulligan reveal gated** — verificare che il fake unlock avvenga solo dopo `recordPaywallIntent('pro')`, non di default — 2 h verify
- (d) **Paywall 4° matchup/giorno** — counter localStorage `matchups_viewed_today`, reset 00:00 UTC, overlay Pro on trigger — 0.5 dev day

**Non toccare pre-launch:** Killer Cards sub-tab, Card Ratings, honesty badge rendering.

### 4.3 Meta (`monitor.js:174`, 2183 LOC) — Maturo

**Oggi:** Meta Ticker (`/api/v1/news/ticker`, 5 min cache), Deck Fitness strip, Emerging & Rogue (WR ≥52% AND meta share <3%), Matchup Matrix (accordion closed, heatmap desktop / list mobile), Deck Analysis (accordion open, charts), Best Format Players (accordion closed), Non-Standard Picks (accordion closed, tornado WR ≥52% min 15 games).

Perimetri: SET11 (~4-5K match/giorno high-tier), TOP (~500 match top 100), PRO (~70 match top 50), Community (~60K+ match/settimana), Friends (custom).

**Pre-launch:** nessun intervento salvo bug.

**Non toccare:** tutto.

### 4.4 Deck (`lab.js:998`, 1276 LOC) — Maturo

**Oggi:**
1. Deck selector (ink picker)
2. Summary panel (`deck_summary.js`)
3. Recommendation Engine (`deck_recommendation_engine.js`, 418 LOC — PRO paywall)
4. Improve (`deck_improve.js`, 339 LOC — Mulligan + Card Impact, PRO paywall)
5. Matchups accordion (`deck_matchups.js`, 498 LOC) — OTP/OTD gap strip, row expand → Curves/Cards sub-tabs
6. List view (`deck_list_view.js`, 230 LOC) — consensus grid + custom deck upload + pentagon radar
7. Lens panel (`deck_lens.js`, 210 LOC) — Δ consensus + Type breakdown + Class breakdown
8. Compare to Pros / Deck Browser — filter groups + compare overlay
9. Matchup workspace (`matchup_workspace.js`, 561 LOC) — deep-dive overlay

**Pre-launch:** nessun intervento salvo bug. Se Matchup Prep "Coming Soon" (`lab.js:1032`) resta tale al giorno 7 → **nascondere la sezione** invece di mostrarlo.

**Non toccare:** tutto il rendering.

### 4.5 Team (`team.js:116`, 485 LOC) — Buono (Board Lab stub)

**Oggi:**
1. Team roster (localStorage)
2. Board Lab upload **stub** ("coming soon" a `team.js:300`) — flusso completo vive nel legacy `team_coaching.js` (1936 LOC copia-incollato, caricato come ultimo script in V3 `dashboard.html`)
3. Replay viewer stub embedded
4. Coach notes (via legacy `team_coaching.js`)

Analytics sections (player comparison, weakness heatmap, session agendas) wrapped in PRO paywall.

**Pre-launch (Board Lab minimo):**
- (a) Verificare access-control `require_replay_access` / `require_replay_owner` su `/api/v1/team/replay/*`
- (b) Verificare ownership `team_replays.user_id` (migration M1 `9a1e47b3f0c2` applicata 24/04)
- (c) 412 handling su upload senza consent
- Lasciare il flusso completo nel legacy bundle. **NO refactor pre-launch.**

**Non toccare:** `team_coaching.js`, roster localStorage, Coach notes legacy. Refactor in tech debt (§11.2).

### 4.6 Improve (`profile.js:884`) — DEBOLE, raccolta strumenti

**Oggi:**
1. Header (avatar, nick, plan, settings, demo-mode — stesso di Home)
2. **My Stats** (collapsible, default expanded) — per-deck WR + games + worst matchup da `DATA.player_lookup[format][nick.toLowerCase()]`
3. **Study** — Blind Playbook + Card Analysis (opzionale, se `window.V3.CardAnalysis` wired)
4. **Practice** — Mulligan Trainer + Replay Viewer (opzionali, se `window.V3.ImprovePlayTools` wired)
5. Nudges: "Link your duels.ink nickname" quando identity blank; "Demo mode" banner quando vedi un altro player

**Gap:** non è un **percorso**, è un menu. L'utente entra e non sa da dove cominciare.

**Pre-launch:** nessuna azione strutturale. Si ship così.

**Ristrutturazione Improve → post-launch 30 gg** (vedi [`TODO.md`](TODO.md) §B.1).

### 4.7 Events + Community (`community_events.js`, 483 LOC) — Maturo

**Oggi:** due div concatenati nello stesso tab (`monolith.js:712-721`).
- Events: map stub (no live data) + calendar (shop, address, entry fee, registration form)
- Community (da `COMMUNITY_CONFIG` hardcoded lines 7-22): Live stream (Twitch/YouTube embed), Schedule (.ics export), Clips (YouTube filtered by tag + "Study in Play" CTA), Archive (VOD topic filter)

No backend fetching per Community content — fully config-driven.

**Pre-launch:** nessun intervento. Se mancano dati live-event (map), nascondere la sezione.

**Non toccare:** `COMMUNITY_CONFIG` hardcoded, calendar flow.

---

## 5. Replay viewer — dove sono e dove NON vanno

### 5.1 Stato attuale

- **Replay Viewer pubblico (`rv*`)** — vive nel legacy `frontend/dashboard.html`, backed by `/api/replay/public-log?match_id=...`. Usato in Coach V2 legacy. **In V3 NON è esposto inline in Play oggi.**
- **Board Lab viewer (`.gz` upload)** — vive nel legacy `team_coaching.js`, caricato come ultimo script da V3 `dashboard.html`. Renderizza viewer animato con mano completa.
- **Team replay stub** — `team.js:300` placeholder "coming soon".

### 5.2 Pre-launch — non cambiare placement

Il Replay Viewer inline in Play (il "See it happen" target) è un miglioramento, non un blocker. Costa 2-3 dev day + richiede matching killer curve → match representative (fallback UX se non c'è).

**Non è nel path critico di lancio.** Rinviato a post-launch 30-60 gg se i numeri di engagement lo giustificano.

### 5.3 Anonimizzazione (già live backend)

`backend/services/replay_anonymizer.py` è wired in `replay_archive_service` + `match_log_features_service`: response JSON di `/api/replay/list|game|public-log` restituiscono `"Player"` / `"Opponent"` invece dei nick raw. **Legale safe, già attivo in produzione.**

---

## 6. Note legali / positioning

- **Anonimizzazione Replay Viewer non negoziabile** — già attiva backend.
- **Ogni istanza Replay Viewer etichettata "Example match"**. Non "real match", non "live game".
- **Board Lab usa solo dati user-uploaded.** Safe by definition.
- **No immagini carte, no loghi, no branding Lorcana** nel dominio o UI. Nomi come testo ok.
- Disclaimer unofficial in footer + About page (già live su legacy via Privacy Layer V3, porting V3 in §4.5).

---

## 7. Paywall strategy (3 trigger, fake paywall)

Il V3 ha già `wrapPremium(html, ctx)` + `recordPaywallIntent(tier)` → POST `/api/v1/user/interest`. Pre-launch serve **solo estendere i trigger**, non ricostruire.

| Trigger | Cosa ha fatto l'utente | Cosa vede | Stato implementazione |
|---------|------------------------|-----------|-----------------------|
| 1 | 4° matchup in Play in un giorno | "Free copre 3 matchup/giorno. Unlock all + killer curves + mulligan reveal → Pro €9/m" | **Pre-launch** (counter localStorage, §4.2) |
| 2 | Click mulligan outcome reveal | "Outcome reveals are for Pro. Upgrade →" | **Pre-launch** (verify fake unlock solo dopo click, §4.2) |
| 3 | Entry Board Lab | "Board Lab is for coaches. Review replay + coach students + public page → Coach €39/m" | Post-launch (Board Lab flusso completo) |

Regole paywall:
- Mai paywall Home, Meta basic, Deck consensus, Events, o il primo replay per matchup.
- Mai modal prima che l'utente abbia esperito il valore dietro.
- Sempre mostrare prezzo e feature specifica, mai vago.
- Paywall è prompt, non wall: uscita senza frizione.

---

## 8. Note legali / positioning

(Invariata dalla v1.0, vedi §6.)

---

## 9. Note legali / positioning

(Spostata in §6.)

---

## 10. (Riservato)

---

## 11. Evoluzione post-launch (non commitment)

### 11.1 Quando avrebbe senso riaprire la discussione nav

**Solo se** dati post-launch dicono:
- 2+ dei 7 tab sono sotto-utilizzati (<5% session time)
- Onboarding rileva friction sulla nav (heatmap / user testing)
- Nuove feature (School full, Replay Viewer inline, Country Meta) richiedono casa e non c'è spazio naturale

Prima di questo: **7 tab vivono così.**

### 11.2 Debiti tecnici V3 — da split post-launch

Da `feedback_v3_anti_monolith_rules.md` (cap 800 LOC per file):

| File | LOC | Stato | Azione |
|------|-----|-------|--------|
| `monitor.js` | 2183 | over | Split Fase C post-launch |
| `coach_v2.js` | 1981 | over | Split Fase C post-launch |
| `team_coaching.js` | 1936 | **legacy copy** | Refactor + dedup post-launch |
| `profile.js` | 1444 | over | Split Fase C post-launch |
| `monolith.js` | 1357 | over, **frozen** | Non toccare. Nuove feature in file separati. |
| `lab.js` | 1276 | over | Split Fase C post-launch |

Altri debiti:
- `assets/js/views/*.js` scaffolding (148 LOC, 8 file) **non wired** — lasciarli, wire gradualmente se si fa il split `profile.js` (home.js + improve.js naturali candidati)
- `sw.js` self-destruct — mantenere finché tutti i client vecchi toccati ≥1 volta, poi rimuovere e sostituire con network-first HTML

### 11.3 Ripresa 9 gap "target ideale"

Per i 9 gap identificati il 24/04 mattina (headline teaser, nav 5+2, paywall 3 trigger, Replay inline, School, Feature B LLM, nickname bridge, Coach page), **solo 3 sono pre-launch**:

1. Headline insight teaser in Home (§4.1)
2. Play conversion clarity (header insight + How to Respond gated + Mulligan reveal gated) (§4.2)
3. Paywall 4° matchup/giorno (§4.2, §7)

Gli altri 6 sono **post-launch**, ordinati per impatto business in [`TODO.md`](TODO.md) §B.

---

# Parte B — Product Overview (dati, pipeline, infrastruttura)

Da qui in avanti: overview prodotto completo, fonti dati, pipeline, cron. Ereditato integralmente da `V3_PRODUCT_OVERVIEW.md` (GPT 24/04 06:24). **Invariato nella v1.1** — la parte B è accurata e non va toccata.

---

## 12. Feature chiave in produzione oggi

| Feature | Cosa fa | Status |
|---------|---------|--------|
| **268 Killer Curves** | Sequenze avversario peggio-caso (fast/typical/slow) generate via OpenAI gpt-5.4-mini, validate automaticamente (9 check) | Batch martedì, ~45min, ~$4/run |
| **Loss Detection 3 livelli** | Keywords (Shift, Ward, Rush, Evasive, ...) × Abilities (etb_banish, passive_draw, ...) × Patterns (WIPE, RECURSION, RAMP_CHAIN, SYNERGY_BURST, HAND_STRIP, LORE_FLOOD, SING_TOGETHER) | 100% data-driven dal cards_db, zero hardcode |
| **Loss Profiles FAST/TYPICAL/SLOW** | 3 bucket per velocità perdita, con top_cards, mechanics, lore_t4 percentili, 12 example_game_ids diversificati | Base per killer curves |
| **Mulligan Trainer** | Mani iniziali reali da PRO, filtri Blind/OTP/OTD, carousel reveal outcome | Live |
| **Meta Deck Optimizer** | Scoring 4D (stat delta, KC coverage, combo synergy, tech discovery) + LLM reasoning → deck ottimizzato per META intero | Prototipo su ES |
| **Board Lab (Team)** | Upload replay `.replay.gz` duels.ink + viewer animato con mano completa, spell overlay, frecce combat, death animations | Live (label generici, TODO arricchimento) |
| **Replay Viewer v1** | Board statico per-step, log eventi, speed 0.5x-4x, filtri Win/Loss/OTP/OTD | Live |
| **Dashboard multi-perimetro** | SET11 High ELO (≥1300), TOP-70, PRO-30, Community (duels.ink meta), Infinity (core + top + pro + friends) | Live |
| **KC Spy canary** | Test giornaliero 04:00 (1 matchup random per formato) + validazione 268 file + auto-fix | Cron attivo |
| **Country Segmentation** | Meta locale per paese (da nickname + paese in registrazione) | Roadmap |

---

## 13. Fonti dati — COSA prendiamo e DA DOVE

### 13.1 duels.ink (fonte primaria)

**Cosa è:** simulatore Lorcana non ufficiale community-built, 2.600+ carte implementate, ranked matchmaking BO1/BO3 su 4 queue (core set11 BO1/BO3 + infinity BO1/BO3). Basato in Francia, finanziato da donazioni Ko-fi.

**Cosa prendiamo:**

| Endpoint / meccanismo | Contenuto | Frequenza |
|------------------------|-----------|-----------|
| `/api/matches/*` (undocumented) | Match log grezzi turn-by-turn: plays, abilities, challenges, quests, dead, bounced, drawn, inkwell, lore. Ogni carta con `ink_paid`, `is_shift`, `shift_cost`, `is_sung`, `singer` | Monitor continuo (`lorcana_monitor.py`), ~40K+ match/mese scaricati |
| `/api/leaderboard?queue=<queueId>` | Ranking top 100 per queue: nickname, MMR, position | Refresh 30 min (monitor) + a ogni run dashboard |
| `/api/cards` (e fallback mirror) | 2.646 carte con legality, translations (de/it/ja/zh), set, cost, type, keywords | Refresh settimanale (domenica 04:45) |
| `/api/replay/{replayId}` (con cookie) | Replay completo `.replay.gz` con `baseSnapshot.myPlayer.hand` + `frames[]` JSON patches per ogni azione | On-demand (Board Lab upload utente) |

**Come accediamo:**
- Senza auth per match/cards/leaderboard
- Replay individuali richiedono cookie di sessione del player → ottenibili solo via upload manuale `.replay.gz` nel Board Lab
- No ToS pubblico → scraping in good-standing, stessa posizione di op.gg/Mobalytics/Dotabuff

**Storage:**
- File JSON in `/mnt/HC_Volume_104764377/finanza/Lor/matches/<DDMMYY>/`
- Monitor routing per `queueShortName`: `S11-*` → `SET11/`, `INF-*` → `INF/`, `JA-*` → `JA/`, `ZH-*` → `ZH/`, altro → `OTHER/`, `TOP-*`/`PRO-*`/`FRIENDS-*` → cartelle dedicate
- ~50K+ match accumulati nel FS, 200K-300K+ importati in PostgreSQL App_tool

**Rischio:** può bloccarci l'accesso in qualsiasi momento (2 email outreach ignorate). Mitigato da Piano A (lorcanito) + Piano C (simulazione AI). Dettaglio in [`BP.md`](BP.md) §15.

### 13.2 lorcanito.com (fonte secondaria, parziale)

**Cosa è:** secondo simulatore Lorcana, engine open source (MIT, `TheCardGoat/lorcana-engine`).

**Stato:** ~200-400 match/giorno, ~2.000 ranked. Log **superiori** a duels.ink (payedCost+originalCost esatti, ability text completo, boost, scry, optional ability).

**Cosa prenderemmo:** match history per nickname dato.

**Problema:** dati solo client-side (IndexedDB/Nakama), no API batch pubblica. Outreach partnership prevista (pitch community, stessa leva di duels.ink).

### 13.3 inkdecks.com (fonte tornei)

**Cosa è:** database risultati tornei ufficiali pubblicati.

**Cosa prendiamo:**
- 45.947 deck totali, 3.734 risultati tornei
- **Consensus decklist** per deck (usata da Tab Deck)
- **Snapshot storico** (`snapshot_YYYYMMDD.json`)

**Come:** `decks_db_builder.py` cron 04:30 scraping inkdecks.com → `/mnt/HC_Volume_104764377/finanza/Lor/decks_db/`

**Uso in V3:** Consensus List + Deck Browser + comparazione con tech cards dei winning player.

### 13.4 Cards Database

**Path:** `/mnt/HC_Volume_104764377/finanza/Lor/cards_db.json` (1500+ carte)

**Contenuto:**
- name, fullName, cost, type (character/action/item/location)
- strength, willpower, lore
- keywords (Shift, Ward, Rush, Evasive, Bodyguard, Support, Resist, Challenger, Reckless, Singer, Vanish)
- ability text completo
- ink (colore, incluso dual-ink: 163 carte bicolore)
- shift_cost, singer_cost, sing_together_cost
- is_song, is_floodborn
- **ability_profile**: trigger + effects + scope auto-parsed (`cards_dict.py → _parse_ability_profile()`)
  - Trigger: etb, quest, challenge, banished, activated, passive
  - Effect: draw, ramp, damage, banish, bounce, tuck, buff, heal, discard_opp, play_from_disc, search, protect, lore_gain, exert_opp, ready

**Fonte:** `/api/cards` duels.ink → normalizzato + arricchito localmente.

### 13.5 Pro Player (leaderboard live + fallback)

**Live:** `duels.ink/api/leaderboard?queue=<queueId>` su 4 queue.

**Fallback:** `/mnt/HC_Volume_104764377/finanza/Lor/guides/pro_momento.json` (lista hardcoded).

**Definizioni:**
- **TOP** = primi 70 in leaderboard (union BO1+BO3, ranked by best position)
- **PRO** = primi 30 (sottoinsieme di TOP) + hardcoded fallback
- **Friends** = lista hardcodata (`FRIENDS` set + prefissi `tol_`)

**Filtro omonimi:** `mmr_ref` tolleranza ±200 MMR per evitare nickname collision.

### 13.6 Leaderboards raw

Esportate in `dashboard_data.json → leaderboards` per frontend → sezione "Best Format Players" (Pro Tools).

### 13.7 duels.ink community meta

`duels.ink` pubblica meta stats aggregate su tutta la ladder (non solo TOP/PRO). Scraped e mostrato come perimetro **Community** nella dashboard. Include tier lorcanito community dove disponibile.

---

## 14. Pipeline dati — dal match log al frontend V3

```
┌───────────────────────────────────────────────────────────────────┐
│                       ACQUISIZIONE DATI                            │
├───────────────────────────────────────────────────────────────────┤
│ • lorcana_monitor.py  → scarica match duels.ink ogni minuto       │
│ • decks_db_builder.py → scraping inkdecks tornei    (cron 04:30)  │
│ • duels.ink /api/cards → cards_db refresh            (dom 04:45)  │
│ • User upload .replay.gz (Board Lab)                 (on-demand)  │
└────────────────────────────┬──────────────────────────────────────┘
                             ↓
┌───────────────────────────────────────────────────────────────────┐
│                STORAGE GREZZO                                      │
├───────────────────────────────────────────────────────────────────┤
│ • /matches/<DDMMYY>/ (~50K+ file JSON)                            │
│ • /decks_db/<DECK>/ + snapshot storici                            │
│ • /cards_db.json (1500 carte arricchite)                          │
│ • App_tool PostgreSQL (200K+ matches importati)                   │
└────────────────────────────┬──────────────────────────────────────┘
                             ↓
┌───────────────────────────────────────────────────────────────────┐
│                  PIPELINE PYTHON (analisidef)                      │
├───────────────────────────────────────────────────────────────────┤
│ FASE 1 LOAD       → lib/loader.py (filtro formato+queue)          │
│ FASE 2 INVESTIGATE → board state per turno, ink budget,           │
│                      classify_losses 9 dim + alert                │
│ FASE 2b ARCHIVE    → archive_<DECK>_vs_<OPP>.json (2-14MB)        │
│ FASE 2c DIGEST     → digest_<DECK>_vs_<OPP>.json (~35KB per LLM)  │
│ FASE 3 GENERATE    → 8 sezioni report                             │
│ FASE 4 VALIDATE    → ink, shift, song, 60 carte, max 4 copie      │
│ FASE 5 ASSEMBLE    → reports/<Deck>/vs_<Opp>.md                   │
└────────────────────────────┬──────────────────────────────────────┘
                             ↓
┌───────────────────────────────────────────────────────────────────┐
│                      LLM PIPELINE                                  │
├───────────────────────────────────────────────────────────────────┤
│ • Killer Curves: OpenAI gpt-5.4-mini (batch mar 00:00, ~$4)       │
│ • Review tattica: Claude subscription (6 pass interattivi)        │
│ • Validazione semantica: Claude Haiku                             │
│ • Traduzioni: Claude Haiku (en→it/de/zh/ja)                       │
│ • Meta Deck Optimizer: Claude (settimanale, ~$0.02/deck)          │
└────────────────────────────┬──────────────────────────────────────┘
                             ↓
┌───────────────────────────────────────────────────────────────────┐
│                  BACKEND APP_TOOL (FastAPI + PG)                   │
├───────────────────────────────────────────────────────────────────┤
│ • POST import_matches.py ogni 2h → PostgreSQL                     │
│ • POST import_killer_curves.py mar 05:30 → DB                     │
│ • POST import_matchup_reports.py 05:30 daily                      │
│ • Redis cache dashboard blob (2h SWR)                             │
│ • JWT auth + rate limit tier-aware                                │
└────────────────────────────┬──────────────────────────────────────┘
                             ↓
┌───────────────────────────────────────────────────────────────────┐
│              API PUBBLICHE (alimentano V3)                         │
├───────────────────────────────────────────────────────────────────┤
│ • GET /api/v1/dashboard-data           (blob completo, cache 2h) │
│ • GET /api/v1/monitor/deck-fitness     (fitness score ranking)   │
│ • GET /api/v1/lab/iwd/{our}/{opp}      (Improvement When Drawn)  │
│ • GET /api/v1/lab/card-scores/{our}/{opp} (correlation, auth)    │
│ • GET /api/replay/public-log?match_id= (viewer logs timeline)    │
│ • POST /api/v1/team/replay/upload      (Board Lab .gz)           │
│ • POST /api/v1/user/interest           (fake paywall, waitlist)  │
│ • POST /api/v1/user/consent            (consent flow)            │
│ • GET /api/v1/user/export              (GDPR export)             │
│ • GET /api/decks                       (nickname bridge)         │
└────────────────────────────┬──────────────────────────────────────┘
                             ↓
┌───────────────────────────────────────────────────────────────────┐
│                   FRONTEND V3 (7 tab primary)                      │
├───────────────────────────────────────────────────────────────────┤
│   Home | Play | Meta | Deck | Team | Improve | Events             │
└───────────────────────────────────────────────────────────────────┘
```

---

## 15. Stack tecnico (sintesi)

| Strato | Tecnologia |
|--------|-----------|
| **Data acquisition** | Python monitor, polling duels.ink API + scraping inkdecks |
| **Pipeline analytics** | Python (loader + investigate + archive + digest) |
| **LLM batch** | OpenAI gpt-5.4-mini (killer curves), Claude Haiku (validate + i18n), Claude Max subscription (sviluppo) |
| **Backend app** | FastAPI + SQLAlchemy + PostgreSQL + Redis (cache 2h SWR) |
| **Frontend V3** | Vanilla JS SPA modulare (`frontend_v3/assets/js/dashboard/*.js`) + Chart.js + Leaflet (Events). PWA installabile. |
| **Deploy** | VPS 2 vCPU 4GB, nginx + Let's Encrypt, systemd `lorcana-api.service`, fail2ban + UFW |
| **Auth** | JWT, bcrypt, rate limit tier-aware |
| **Dashboard R&D** | Porta 8060 separata (`analisidef/daily/serve_dashboard.py`) — sperimentale |

---

## 16. Automazione notturna (cron attivi)

| Ora | Job | Cosa fa |
|-----|-----|---------|
| **00:00 mar** | `run_kc_production.sh` | Killer curves batch core + infinity, ~$4, ~45min |
| **01:00 mar** | `generate_playbooks` | Meta deck playbook per-deck |
| **02:00** | `experimental_engine/` | Simulazione match agente autonomo (30 min, Claude Sonnet) |
| **03:00** | Backup daily | Dump PG |
| **04:00** | `kc_spy.py` | Canary KC: 1 test + validazione 268 file + auto-fix |
| **04:05** | `import_kc_spy` | Import spy report in PG |
| **04:30** | `decks_db_builder.py` | Scraping inkdecks |
| **04:45 dom** | `refresh_static_and_reset.sh` | Refresh cards DB settimanale + reset cache |
| **05:00** | `lorcana_monitor.py` report | Report partite daily |
| **05:01** | `daily_routine.py` | Dashboard 8060 meta + KC + spy badge |
| **05:30 mar** | `import_killer_curves.py` | Import KC in App_tool DB |
| **05:30** | `import_matchup_reports.py` | Daily |
| **06:30** | `import_matches.py` | Sync match App_tool DB |
| **07:00** | `monitor_kc_freshness` | Check freshness KC |
| **07:05** | `monitor_unmapped_matches.py` | Alert se nuovo folder/drop rate >10% |

---

## 17. Set 12 readiness (lancio Maggio 2026)

Il sistema è **pronto per Set 12** senza code change:
- `lorcana_monitor.get_format_folder()` regex-driven: `^S(\d+)` → `SET<NN>` (accetta S11, S12, S13...)
- `FORMAT_FOLDERS`/`FORMAT_QUEUE_PREFIXES` accettano `SET11` + `SET12`
- `APPTOOL_DEFAULT_CORE_PERIMETER` env (default `set11` → flip a `set12` al drop)
- Migration cassetto `7894044b7dd3_set12_launch_meta_epoch.py` pronta (non ancora applicata, guard env)
- Canary alert se un nuovo folder appare

**Policy cutover:** hard (niente overlap 30gg), KC opera strettamente sul set attivo, Set 11 resta in DB come storico ma invisibile a digest/KC/matchup reports.

---

## 18. Rischi data-layer

| Rischio | Impatto | Mitigazione |
|---------|---------|-------------|
| duels.ink blocca API | **Critico** | Piano A (lorcanito) + Piano C (simulazione AI con engine open source `TheCardGoat/lorcana-engine` + agent heuristic/LLM) |
| Ravensburger chiude duels.ink (scenario Pixelborn) | **Critico** | Dati storici restano (50K+ match), switch a lorcanito + accelerare Piano C |
| Ravensburger lancia client ufficiale | **Alto** | Diventare analytics partner naturale (unici con pipeline 12+ mesi) |
| Nuova espansione rompe parsing | **Basso** | Pipeline 100% data-driven, zero carte hardcodate — auto-detect nuove ability via ability_profile |
| Cards_db disallineato post-espansione | **Basso** | Refresh settimanale dom 04:45 + monitor canary |

Dettaglio completo: [`BP.md`](BP.md) §15 (Piani contingenza A + B + C).

---

## 19. Numeri chiave oggi

- **~50K-300K match** scaricati (FS grezzo + PG App_tool)
- **2.646 carte** in cards_db
- **268 killer curves** in produzione (134 core + 134 infinity) validate 0 FAIL
- **45.947 deck** tornei scraped da inkdecks
- **2.000-2.500** ranked player duels.ink attivi stimati
- **~200-400 match/giorno** catturati oggi
- **8 cron notturni** coordinati
- **0 utenti paganti** (pre-lancio — waitlist economy via fake paywall)

---

## Verifica finale (reality-aligned)

- [x] Stato reale 7 tab documentato (non target 5+2)
- [x] Meta, Deck, Events riconosciuti come maturi — non toccare
- [x] Play + Home identificati come focus pre-launch
- [x] Improve dichiarato debole (raccolta strumenti), ristrutturato post-launch
- [x] Board Lab stato stub V3 + legacy `team_coaching.js` chiarito
- [x] Replay viewer placement = non cambiare pre-launch
- [x] Fake paywall già live riconosciuto (no ricostruzione pre-launch)
- [x] Legacy vs V3 distinzione esplicita (swap = una riga)
- [x] Scaffolding `views/` non wired — lasciare
- [x] Tech debt (file >800 LOC + `team_coaching.js` copia legacy + `sw.js` self-destruct) separato post-launch
- [x] Allineato con [`BP.md`](BP.md) v4.1 (SKU diagnosi/prescrizione/applicazione, conversion loop)
- [x] Fonti dati, pipeline, cron documentate (§12-§19 invariate)

---

*Documento consolidato il 24 Aprile 2026 (sera) reality-aligned. Fonti:*
- *`frontend_v3/point/V3_CURRENT_STATE.md` (stato reale) — base §3-§5 + §11*
- *`frontend_v3/point/V3_ARCHITECT_POINT.md` originale (GPT 06:50) — riferimento target, usato dove compatibile*
- *`analisidef/business/V3_PRODUCT_OVERVIEW.md` (GPT 06:24) — §12-§19 integrali*
- *Complementari: [`BP.md`](BP.md) (business), [`TODO.md`](TODO.md) (operativo).*
