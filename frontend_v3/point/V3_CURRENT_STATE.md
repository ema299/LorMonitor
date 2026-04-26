# V3 — Current State (Live Code Inventory)

**Date:** 2026-04-24
**Scope:** `frontend_v3/` — what the code actually does right now, not what the architect-point target wants. Stubs, placeholders and debt included.

> Companion to `point/V3_ARCHITECT_POINT.md` (target state). This file is the **as-is** snapshot.

---

## Top-level layout

`frontend_v3/dashboard.html` (194 LOC). Structure:

- **Header** — gold-star logo + "Guide" tour button (→ `tourStart()`)
- **Tab bar (7):** Home · Play · Meta · Deck · Team · Improve · Events + inline Core/Infinity format toggle
- **Format bar** — mobile-only format toggle + format badge + inline ink picker (`#ink-picker-bar`)
- **Perimeter bar** — SET11 High ELO · TOP · PRO · Friends · Community
- **`#main-content`** — populated by JS via `render()` (monolith.js:639)
- **Info FAB** — "i" button opens fixed info popup (meta stats + abbreviations + privacy notice + disclaimer)
- **Cheatsheet overlay** (`#cheatsheet-overlay`) — pre-match bottom-sheet
- **Bottom nav (mobile)** — 7 chip buttons mirroring tab bar
- **Footer** — unofficial disclaimer + `/about.html` + `mailto:monitorteamfe@gmail.com`

**Important:** there is a `frontend_v3/assets/js/views/` folder (home.js, play.js, meta.js, deck.js, improve.js, events.js, community.js, pro.js — 148 LOC total) but it is **NOT loaded by dashboard.html** and **NOT wired**. These are scaffolding placeholders for a future split; current rendering is all in `assets/js/dashboard/*.js`.

---

## Tab rendering dispatch

`render()` in `monolith.js:639`:

| Tab | Render function | Main module |
|---|---|---|
| `home` | `renderProfileTab()` | `profile.js` |
| `play` | `renderCoachV2Tab()` | `coach_v2.js` |
| `meta` | `renderLadder()` | `monitor.js` |
| `deck` | `renderLabTab()` | `lab.js` |
| `team` | `renderTeamTab()` | `team.js` |
| `improve` | `renderImproveTab()` | `profile.js` |
| `events` | `renderEventsTab()` + `renderCommunityTab()` | `community_events.js` |

Tab switch via `switchToTab(tabId)` (monolith.js:112): updates `body[data-active-tab]`, syncs deck/opp state, calls `render()`.

---

## Tab-by-tab — what's actually there

### Home → `profile.js:181`

Blocks rendered, in order:
1. **Identity header** — avatar, nick, plan badge (Free/Pro), settings gear, demo-mode indicator
2. **Identity form** (drawer) — email, duels.ink nick, Lorcana nick, country (localStorage-backed)
3. **Set 12 Hub** (`set12_hub.js`, 406 LOC) — countdown to `RELEASE_DATE=2026-05-12`, email signup form, Discord CTA. **FORM_ACTION and DISCORD_INVITE are placeholders** (set12_hub.js:27-34) → form submit fails gracefully.
4. **My Deck Curve** — visual turn-by-turn cost distribution of the selected deck
5. **Meta Fitness top-3** — mini fitness list from current perimeter
6. **My Decklists** — saved decks via `saved_decks.js` (localStorage key `v3_saved_decks`)
7. **Blind Playbook** — lazy-loaded per (deck, format) on render, fetches `/api/v1/lab/iwd/{deck}/{format}`

### Play → `coach_v2.js:1539` (1981 LOC)

Blocks:
1. **Matchup selector** — our-deck ink picker × opponent ink picker → resolves `coachDeck` / `coachOpp`
2. **Killer Curves** — top 5 opponent sequences for the matchup, sorted by frequency, each with coverage signal (red/yellow/green from `deck_response_check.js`)
3. **Secondary tabs** (`cv2SecTab`): Killer Cards (default) · Curves · Threat Responses · Card Ratings (from `card_analysis.js`)
4. **Honesty badges** everywhere via `honesty_badge.js` (formatted WR + confidence tier + game count)

All content is wrapped in `wrapPremium(html, 'coach')` (monolith.js:872). Click on lock → `recordPaywallIntent('pro')` → POST `/api/v1/user/interest` with Bearer token from localStorage (`lm_access_token` | `access_token` | `auth_access_token`).

**Empty states:** "Select Matchup" (no opp) / "Data not available" (no matchup_analyzer entry).

**Not yet here (per restyle plan):** Replay Viewer inline, Mulligan Trainer (moved to Improve), Best Plays.

### Meta → `monitor.js:174` (2183 LOC)

Blocks, top to bottom:
1. **Meta Ticker** — scrolling editorial items, `/api/v1/news/ticker` (5 min client cache, monitor.js:79)
2. **Deck Fitness strip** — horizontal scroll of decks ranked by meta-weighted fitness score; click updates `selectedDeck` and rerenders below
3. **Emerging & Rogue** — decks with WR ≥52% and meta share <3%
4. **Matchup Matrix** (accordion, closed by default) — heatmap desktop / list mobile, WR per deck pair
5. **Deck Analysis** (accordion, open by default) — deck identity + Matchup WR chart + OTP/OTD gap chart (Chart.js instances cached per canvas in `charts`)
6. **Best Format Players** (accordion, closed) — top players in current scope, expandable into player cards
7. **Non-Standard Picks** (accordion, closed) — tornado chart of cards added/cut by top players (WR ≥52%, min 15 games)

Perimeter labels (from Info popup):
- SET11 = ~4-5K matches/day high-tier
- TOP = ~500 matches (top 100 ladder)
- PRO = ~70 matches (top 50)
- Community = ~60K+ matches/week
- Friends = custom

### Deck → `lab.js:998` (1276 LOC)

Rewritten recently. Section order:
1. **Deck selector** — ink picker (same ink states as Play/Meta)
2. **Summary panel** (`deck_summary.js`) — deck metadata: icon, name, archetype, WR, meta share, last-updated
3. **Recommendation Engine** (`deck_recommendation_engine.js`, 418 LOC) — meta-aware suggestions, PRO paywall
4. **Improve** (`deck_improve.js`, 339 LOC) — Mulligan Trainer + Card Impact, both PRO paywall
5. **Matchups** (accordion, closed, `deck_matchups.js`, 498 LOC) —
   - Cross-matchup OTP/OTD gap strip (10pp significance threshold)
   - Column header fixed 2026-04-24: `20px 1fr 56px 80px 86px 60px 100px` 7-track grid, horizontal labels (WR · Games · Conf. · Rating · Coverage)
   - Row tap expands into `Curves` / `Cards` sub-tabs (killer curves with coverage + card_scores trending with `in_deck_rate`)
6. **List view** (`deck_list_view.js`, 230 LOC) — consensus decklist grid + custom deck upload modal + pentagon radar comparison (my deck vs consensus)
7. **Lens panel** (`deck_lens.js`, 210 LOC) — bottom-right vertical panel:
   - **Δ vs consensus** — adds/cuts vs archetype list, WR impact badges when opp selected
   - **Type breakdown** — Characters · Actions · Songs · Items · Locations (added 2026-04-24, reads `rvCardsDB[name].subtypes` from `/api/replay/cards_db`)
   - **Class breakdown** — Removal · Bounce · Wipe · Evasive · Draw · Ramp (ability-text regex, flagged as ~80% heuristic)
8. **Compare to Pros / Deck Browser** (lab.js:616) —
   - First-open defaults applied 2026-04-24: ink filter pre-seeded with analysis deck's inks, rank=Top 16, date=Last month (sentinel `_dbDefaultsApplied`)
   - Filter groups: Ink · Rank · Date · Search + deck pills (filtered variants) + compare overlay (pentagon radar diff)
9. **Matchup workspace** (`matchup_workspace.js`, 561 LOC) — deep-dive overlay when opening a specific matchup from the matrix

**Incomplete:** "Matchup Prep" section has a "Coming Soon" marker (lab.js:1032).

### Team → `team.js:116` (485 LOC)

Blocks:
1. **Team roster** — add/remove players (localStorage-backed)
2. **Board Lab upload** — `.replay.gz` upload modal. **`team.js:300` marks "coming soon"** — full upload is not wired in V3 yet (legacy `team_coaching.js` carries the full implementation)
3. **Replay viewer** — embedded team-match viewer stub
4. **Coach notes** — annotations, handled by legacy `team_coaching.js` (1936 LOC copy-paste from legacy `frontend/`, loaded as last script in dashboard.html)

Analytics sections (player comparison, weakness heatmap, session agendas) wrapped in PRO paywall.

**Debt:** `team_coaching.js` is a verbatim copy from legacy — flagged in `feedback_v3_anti_monolith_rules.md` as the cautionary tale. Not refactored yet.

### Improve → `profile.js:884`

Blocks:
1. **Header** — same as Home (avatar, nick, plan, settings, demo-mode)
2. **My Stats** (collapsible, default expanded) — per-deck WR + games + worst matchup, total games, best MMR. Sourced from `DATA.player_lookup[format][nick.toLowerCase()]`.
3. **Study** section:
   - **Blind Playbook** — lazy-loaded from `/api/v1/lab/iwd/{deck}/{format}`, session-cached
   - **Card Analysis** (if `window.V3.CardAnalysis` wired) — card-level study signals
4. **Practice** section:
   - **Mulligan Trainer** (if `window.V3.ImprovePlayTools` wired) — interactive hand review
   - **Replay Viewer** (same namespace) — personal replay study

Nudges: "Link your duels.ink nickname" when identity blank; "Demo mode" banner when viewing another player.

### Events + Community → `community_events.js:272` + `:1` (483 LOC total)

Rendered into a single combined tab output (monolith.js:712-721 builds two temp divs side-by-side).

**Events:**
- **Event map** — structure present, no live location data wired yet
- **Calendar** — upcoming tournaments: shop, address, entry fee, registration form (community_events.js:439-475)

**Community** (driven by hardcoded `COMMUNITY_CONFIG` object, lines 7-22):
- **Live stream** — Twitch/YouTube embed
- **Schedule** — stream times, .ics export
- **Clips** — YouTube cards filtered by tag (Beginner/Intermediate/Advanced/Deck-specific). "Study in Play" CTA opens the clip in Play tab context.
- **Archive** — historical VODs, topic filter

No backend fetching for Community content — fully config-driven.

---

## Cross-cutting

### Global state (declared in monolith.js unless noted)

| Var | Type | Purpose |
|---|---|---|
| `currentFormat` | `'core'\|'infinity'` | Active format; persisted in localStorage `lorcana_format` |
| `currentPerim` | `set11\|top\|pro\|friends_core\|community` | Active perimeter; auto-syncs on format change |
| `currentTab` | tabId | Active tab |
| `selectedDeck` | string | Primary archetype (default EmSa or top-fitness) |
| `selectedInks` | `string[]` | Ink pair derived from `DECK_INKS[selectedDeck]` |
| `coachDeck` / `coachOpp` | strings | Play-tab selection |
| `labOpp` | string | Deck-tab selected opponent |
| `oppSelectedInks` | `string[]` | Intermediate opp ink state |
| `myDeckMode` | `'standard'\|'custom'` | Are we showing consensus or user-uploaded list? |
| `myDeckCards` | `{name: qty}` | User's custom list (when myDeckMode='custom') |
| `PRO_UNLOCKED` | bool | Client-side fake unlock (true after any paywall click) |
| `cv2SecTab` | string | Active sub-tab in Play |
| `DATA` | object | Everything from `/api/v1/dashboard-data` |
| `charts` | `{canvasId: Chart}` | Chart.js instances, destroyed on tab switch |
| `rvCardsDB` | `{name: {cost,type,ink,str,will,lore,ability,set,number,inkable,subtypes}}` | Lazy-loaded from `/api/replay/cards_db` |

### Backend endpoints consumed

| Path | Method | Purpose | Auth |
|---|---|---|---|
| `/api/v1/dashboard-data` | GET | Full blob (perimeters, consensus, matchup_analyzer, player_lookup, meta) | — |
| `/api/v1/news/ticker` | GET | Editorial ticker items | — |
| `/api/v1/lab/iwd/{deck}/{format}` | GET | Blind playbook | — |
| `/api/v1/user/interest` | POST | Paywall intent `{tier: 'pro'}` | optional Bearer |
| `/api/replay/cards_db` | GET | Slim card db (name → cost/type/ink/stats/ability/subtypes) | — |
| `/api/v1/team/replay/*` | — | Legacy module `team_coaching.js`; access-controlled (Privacy layer §24.5) | JWT |

No live calls found for `/api/decks`, `/api/v1/profile`, `/api/v1/user/consent`, `/api/v1/user/export` from V3 dashboard modules — but these exist in backend. V3 likely doesn't use them yet; legacy About/privacy surfaces do.

### Privacy & paywall

- Footer disclaimer (dashboard.html:90-95) — "unofficial fan-made analytics tool"
- Info FAB popup (dashboard.html:113-116) — Privacy section noting Replay Viewer anonymization + own-replay access control
- `/about.html` + `mailto:monitorteamfe@gmail.com` linked from footer
- **No consent modal in V3 yet** — consent flow exists in legacy `frontend/` (commit `1abbdd0`). Migration to V3 is in `docs/MIGRATION_PLAN.md` Appendice Z, not yet applied.
- `wrapPremium(html, ctx)` wraps PRO content. Contextual messaging per surface (Coach vs Lab vs Team). Click → `recordPaywallIntent(tier)` silent POST to `/api/v1/user/interest`.

### Service worker

`frontend_v3/sw.js` is a **self-destruct SW**: on `activate` it deletes all caches, unregisters itself, and forces a client navigate. No active caching strategy. Purpose: clean up cache-first SWs from earlier V3 builds that were trapping UI edits. Can be deleted once all affected browsers have picked it up at least once.

### Anti-monolith guardrails (from `feedback_v3_anti_monolith_rules.md`)

Current file LOC vs 800-LOC cap:

| File | LOC | Status |
|---|---|---|
| `monitor.js` | 2183 | **over** (Fase C split planned) |
| `coach_v2.js` | 1981 | **over** (Fase C split planned) |
| `profile.js` | 1444 | **over** (Fase C split planned) |
| `monolith.js` | 1357 | **over**, but **frozen** — do not append |
| `lab.js` | 1276 | **over** |
| `matchup_workspace.js` | 561 | ok |
| `deck_matchups.js` | 498 | ok |
| `team.js` | 485 | ok |
| `community_events.js` | 483 | ok |
| `deck_recommendation_engine.js` | 418 | ok |
| `shared_ui.js` | 407 | ok |
| `set12_hub.js` | 406 | ok |
| `saved_decks.js` | 372 | ok |
| `deck_improve.js` | 339 | ok |
| `deck_builder.js` | 283 | ok |
| `deck_list_view.js` | 230 | ok |
| `card_impact.js` | 217 | ok |
| `builder_status.js` | 215 | ok |
| `deck_lens.js` | 210 | ok |
| `deck_summary.js` | 199 | ok |
| `dashboard.html` | 194 | ok (250-LOC cap) |
| `deck_overview.js` | 175 | ok |
| `honesty_badge.js` | 171 | ok |
| `deck_grid.js` | 166 | ok |
| `math_tool.js` | 152 | ok |
| `deck_response_check.js` | 122 | ok |
| `card_analysis.js` | 73 | ok |
| `improve_play_tools.js` | 39 | ok |

**Additional legacy debt:** `team_coaching.js` (1936 LOC, copied wholesale from legacy `frontend/`). Not refactored; flagged as cautionary tale.

**Total V3 JS + HTML:** ~14,850 LOC vs legacy `frontend/dashboard.html` 10.6K inline — V3 is not yet leaner but is modular.

---

## Known stubs / coming-soon

| Location | What | Notes |
|---|---|---|
| `set12_hub.js:27-34` | Google Form + Discord invite | Placeholders, form fails gracefully |
| `lab.js:1032` | Matchup Prep section | "Coming Soon" badge |
| `team.js:300` | `.replay.gz` upload in Team tab | Coming soon |
| Events tab | Live event map | No geocoded data source |
| `assets/js/views/*.js` | Parallel view layer | 148 LOC total, not wired to dashboard.html |
| V3 consent modal | Privacy layer V3 port | Legacy `frontend/` has it, V3 doesn't — see MIGRATION_PLAN Appendice Z |

---

## PRO paywall surface

Client-side gate; server-side enforcement TBD. Paywall intent (`/api/v1/user/interest`) is already persisted. Unlocked surfaces on click (fake local unlock) — meant as pre-billing waitlist signal.

- Coach V2 (all) — `wrapPremium(..., 'coach')`
- Deck Recommendation Engine
- Card Impact
- Mulligan Trainer
- Team analytics (player comparison, weakness heatmap, session agendas)

Free surfaces (no paywall):
- Meta tab (Fitness, Matrix, Deck Analysis, Emerging, Best Players, Non-Standard Picks)
- Deck tab Summary + List view + Lens panel + Matchups accordion
- Home (Set12 Hub + My Stats + Saved Decks)
- Community/Events
- Blind Playbook (public endpoint)

---

## Swap readiness vs production

- API parity with legacy: 100% (audit 2026-04-23)
- V3 is still **not** the production default (legacy `frontend/dashboard.html` is served at `/` via FastAPI)
- To flip: one line change in `backend/main.py` `_serve_dashboard()` to point FRONTEND_DIR at `frontend_v3/`
- Blockers to flip per `project_v3_restyle_plan.md`: finish restyle tabs (Home / Play / Deck), close Fase A parity (Team Replay upload, JWT smoke, nginx CSP), port privacy layer V3 consent modal.

---

## Recent changes (this session, 2026-04-24)

1. **Deck Lens — Type breakdown added** (`deck_lens.js:75-123`): Characters / Actions / Songs / Items / Locations tile row, reads `subtypes` from the enriched cards_db endpoint
2. **Backend cards_db enrichment** (`backend/main.py:91-153`): renamed `_INKABLE_MAP` → `_DUELS_ENRICHMENT`, now propagates `subtypes` alongside `inkable` into the `/api/replay/cards_db` response (requires backend restart to take effect)
3. **Matchups header alignment** (`deck_summary.css:288-325` + `deck_matchups.js:468-477`): fixed off-by-one caused by absolute-positioned `.mh-stripe` not consuming a grid track. Row & header now both 7-track `20px 1fr 56px 80px 86px 60px 100px`. Rotation removed, horizontal compact labels.
4. **Compare to Pros defaults** (`lab.js:241, 623-635`): sentinel-guarded first-open seed of ink filter (from analysis deck) + rank=Top 16 + date=Last month.

---

## Baseline 2026-04-26 — accepted removals/moves on Deck tab (no rollback)

User-confirmed during single-Claude window (TODO §HARDBLOCK). These are the **new Deck baseline**:

- **Removed** — `deck_summary.js` `_responseCoverageMini()` (90 LOC). Was a 🟢/🟡/🔴 coverage indicator vs worst matchup. No replacement; coverage info now only available curve-by-curve inside Matchups → row → Curves expansion.
- **Removed** — Deck-tab matchup selector (`buildMatchupSelector('lab')` invocation in `lab.js`). Opp selection now via row-click on Matchups table only. Helper still used by Play tab.
- **Moved + redesigned** — Recommended actions block: was opp-aware inside Summary card (`deck_summary.js::_recommendedActions`). Now lives at the bottom of "Your list" card (`deck_list_view.js`), runs without opp hint = **cross-matchup aggregate** ranking. The opp-specific variant is gone; nearest-equivalent is now the matchup workspace.
- **Added** — Type breakdown tile row in Lens (`deck_lens.js::buildTypeBreakdown`).
- **Added** — Confidence badge on Mulligan Trainer (`lab.js::_mullSetConfidence`).
- **Added** — Deck Browser first-open defaults (analysis deck inks + Top 16 + Last month).
- **Added** — "Loaded: <name>" indicator + "Load…" button in `deck_list_view.js`.
- **Added** — Intro copy paragraphs above Summary and above Your list.
- **Replaced** — `builder_status.js` strip semantics: `[Size · Curve · Response coverage]` → `[Size · Inkable · Colors]`. Response coverage status no longer surfaced in the builder strip.
- **Tightened** — `deck_builder.js::_legalCardNames` now scoped per-archetype + 30-day window (was global pool across all consensus + reference decks). Reduces splash-ink contamination in suggestions.
