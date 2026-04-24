# Lorcana Monitor V3 — Architect Point

**Version:** 1.0 | **Date:** 24 April 2026
**Author role:** Senior product architect + UX strategist
**Scope:** Optimize an existing product. No redesign from scratch. Preserve every feature. Implementable in under 7 days.

---

## 1. Design problem

Two viewers live in this product and must not be conflated:

1. **Replay Viewer** — consumption surface. Reads real matches from `duels.ink` data. Step-by-step board playback, anonymized opponents. Passive, read-only, insight-serving.
2. **Board Lab** — creation / coaching surface. User uploads a `.replay.gz`. Coach annotates, walks through alternative lines, exports a session artifact. Active, write-enabled, coach-serving.

The current product risks placing both as "viewers" and confusing user intent. The architect's job is to separate them by surface, by user role, and by moment in the funnel.

Secondary problems addressed:

- First screen overload (too many blocks on Home).
- Insight buried under analytics (charts shown before meaning).
- Paywall placed reactively rather than at the natural value threshold.

---

## 2. Full V3 Architecture

**Nav primary (5):** Home · Play · Meta · Deck · Community
**Nav secondary, drawer (2):** Improve · Pro Tools (contains Team + Board Lab)

No tabs added, no tabs removed vs the current V3 target. The architect's intervention is inside the tabs: content, hierarchy, placement of the two viewers, and paywall triggers.

```
┌────────────────────────────────────────────────────────────────────┐
│  HOME          PLAY          META         DECK        COMMUNITY    │
│  entry      matchup core    field       builder      scene         │
│                                                                    │
│                                         ┌──────────────────────┐   │
│                                         │ "..." drawer          │   │
│                                         │   IMPROVE   PRO TOOLS │   │
│                                         │   personal  deep +    │   │
│                                         │             Team +    │   │
│                                         │             Board Lab │   │
│                                         └──────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
```

---

## 3. Tab-by-tab specification

### 3.1 Home

**Purpose.** Answer the question "what is the state of my deck and what should I look at today?" in under 30 seconds.

**Priority blocks (top to bottom):**

| Priority | Block | Content |
|---|---|---|
| P0 | Set 12 Hub (temporary, through end of May 2026) | Countdown + email capture + Discord CTA. Hero banner. |
| P0 | Deck selector | Ink picker 6 columns → deck auto-detect. Saved pins (max 3). My Deck custom toggle. |
| P1 | Headline insight teaser | "Your worst matchup is X (43% WR). Open Play →". One line. One CTA to Play. **This is the hook.** |
| P1 | Matchup chips strip | Best / Worst top 3 chips, click → Play. |
| P2 | Pre-match Cheatsheet CTA | Single button "Ready for a match?" → opens bottom-sheet cheatsheet. |
| P3 | My Stats mini (gated login) | 3 KPIs only: recent WR, games, current rank. Full stats live in Improve. |

**Removed from Home (vs prior layout):**

- Meta Radar (moved to Meta — duplicate, confused hierarchy).
- Consensus list (moved to Deck).
- Tech cards (moved to Deck).
- Best Plays top 3 sequences (moved to Play).
- Coach Corner (hidden unless coach is active — pure noise otherwise).

**Rule.** Home fits on one mobile screen without scroll for the deck selector + insight teaser. Everything else is below the fold or hidden.

### 3.2 Play (core)

**Purpose.** Answer "how do I win this matchup?" with prescriptive, turn-by-turn guidance. This is the revenue tab.

**Priority blocks (top to bottom):**

| Priority | Block | Content |
|---|---|---|
| P0 | Matchup selector | Our deck (locked from Home or selectable) × Opponent deck (ink picker). |
| P0 | KPI strip | WR · OTP WR · OTD WR · OTP-OTD gap. 4 numbers, always visible. |
| P0 | Key Threats (accordion, open by default) | Top threats, critical turn, Plan A / Plan B / Plan C. Written, not charted. |
| P1 | Killer Curves summary | 2–3 worst-case opponent sequences, condensed card rows with a "See it happen" link per curve → opens inline Replay Viewer at that match. |
| P1 | **Replay Viewer inline** | Anonymized example match showing the selected killer curve. "Opponent A" naming. Board playback. This is where insight becomes tangible. |
| P1 | How to Respond (OTP vs OTD split) | Two columns. Concrete cards to play, cards to avoid. |
| P2 | Mulligan Trainer | Carousel of real PRO hands in this matchup. Blind / OTP / OTD filter. Outcome reveal gated for Pro. |
| P2 | Best Plays | Top 3 winning sequences on OUR deck side (the opposite angle of killer curves). |
| P3 | Opponent Playbook | Turn-by-turn expected plays. Collapsed by default. |
| P3 | Pre-match Cheatsheet full | 5 bullet points + Copy to Discord. |

**Explicitly excluded from Play:**

- Editing UI. No drawing on boards, no moving pieces. Play is consumption only.
- Board Lab CTA banner cluttering the surface. The soft entry point is a small link at the bottom of the Replay Viewer block (see §4.2).
- Trend by Turn chart (moved to Pro Tools — too analytical for this tab).
- Lore chart (moved to Pro Tools).
- Opponent's Killer Cards list (redundant with Key Threats — collapsed or removed after validation).

### 3.3 Meta

**Purpose.** Answer "what does the field look like right now?" for pre-tournament or pre-session scouting.

**Priority blocks:**

| Priority | Block | Content |
|---|---|---|
| P0 | Deck Fitness strip | Horizontal scroll, 132×100px cards per deck, 0–100 meta-weighted score. |
| P0 | Matchup Matrix **light** | Desktop: condensed heatmap. Mobile: filtered list of 13 rows for selected deck. Click → deep-link to Play for that matchup. |
| P1 | Selected deck analysis | WR by matchup, OTP vs OTD split. |
| P2 | Meta Radar | Snapshot list of main matchups with share %. Promoted here (removed from Home). |
| P3 | Non-Standard Picks (meta-level) | Tech signals from winning player pool. Consolidated in Meta only (not duplicated in Deck). |

**Moved out of Meta to Pro Tools:**

- Full NxN matrix heatmap.
- Best Format Players / leaderboard deep.
- Advanced Tech Tornado (adoption history, tournament attribution).

### 3.4 Deck

**Purpose.** Answer "how do I improve my list?" with consensus data, optimization, and comparison tools.

**Priority blocks:**

| Priority | Block | Content |
|---|---|---|
| P0 | Consensus list | Standard decklist from inkDecks. Updated daily. |
| P0 | Deck curve | Mana curve + role breakdown. |
| P1 | Tech Picks (deck-specific) | Non-standard cards from winners of this deck. |
| P1 | Optimized Deck | Meta Deck Optimizer output. Add / cut reasoning card-by-card. |
| P2 | Deck Comparator | Diff two lists side-by-side. |
| P2 | Deck Browser | Tournament-sourced lists, filterable. |
| P3 | Card Impact (Correlation) base | Simple WR correlation per card. Advanced IWD lives in Pro Tools. |

### 3.5 Community

**Purpose.** Brand, goodwill, acquisition funnel. Not revenue. Three internal sub-sections, no further tabs.

| Sub-section | Content |
|---|---|
| Live & Content | YouTube / Twitch embed, schedule, clip grid, VOD archive. |
| Events & Tournaments | Leaflet map, calendar, event cards, store submission form, Meta Brief per event. |
| School of Lorcana (placeholder) | 5–10 curated YouTube embeds, glossary, archetype primer. Grows post-launch. |

**Rule.** Community is free, no paywall, no auth required. Its job is to bring people to Home, not to monetize.

### 3.6 Improve (secondary, drawer)

**Purpose.** Personal progress for logged-in users with nickname bridge active.

**Gating:** Hidden in the drawer for anonymous users. Placeholder "Log in with duels.ink nickname to unlock" for logged users without bridge.

**Blocks:**

- My Stats full (personal WR, trend, matchup coverage).
- Blind Playbook (per-deck personal guide).
- Error Detection / misplay review (post-launch feature, not day 1).
- Replay Review (personal replays, post-launch).

Improve exists to reward the logged-in user and create a retention hook. It is not the place for first-visit insight (that is Home + Play).

### 3.7 Pro Tools (secondary, drawer)

**Purpose.** Power-user depth and coaching workspace. Contains **Team** and **Board Lab** as sub-sections.

**Gating:** Visible to all, but most blocks are paywalled beyond preview state for non-Pro / non-Coach.

**Sub-sections:**

| Sub-section | Content | Tier |
|---|---|---|
| Deep Analytics | Killer Curves deep, Matchup Matrix full, Best Format Players, Tech Tornado advanced, Trend by Turn chart, Lore chart, IWD, Card Impact advanced | Pro |
| **Team** | KPI strip, player cards, meta coverage, suggested lineup, coaching inbox, weakness heatmap | Coach |
| **Board Lab** | Upload `.replay.gz`, animated viewer with full hand, annotation overlay, session notes, PDF export, public coach page link | Coach |

**Architectural note.** Pro Tools is not a new nav layer — it's the paywall surface. It collects the blocks that justify paying. This is the right place for them because they are power-user features and they share a "I already understand the basics, show me depth" mental model.

---

## 4. Placement of the two viewers

This is the central design decision.

### 4.1 Replay Viewer placement

**Location:** inline inside **Play**, attached to the Killer Curves summary.

**Why:**

- Replay Viewer is a consumption tool. Its role is to make insight *tangible*. "Here is the killer curve described above, now watch it happen in a real match."
- Placing it in Play means users see it **only after understanding the insight** it illustrates. Insight-first, illustration-second.
- This placement is also the correct paywall moment: free users see the first two replays per matchup, Pro sees unlimited.

**What it shows:**

- Real match from data logs.
- **Anonymized opponent names** ("Opponent A", "Opponent B") — raw `duels.ink` identity is never exposed.
- Our-side player shown as "Player" or the user's own nickname if logged in and their match is selected.
- Board step-by-step playback. No edit controls.

**What it does NOT do:**

- No edit UI. No card dragging. No annotation. That is Board Lab's job.
- No standalone tab. It is always contextual to a matchup or killer curve.

**Three historical instances consolidated into one:** the previous layout had a Replay Viewer in Coach V2, in Lab, and embedded in Team. All three are replaced by this single inline-in-Play instance, plus the embedded viewer inside Board Lab (which is separate — see next section).

### 4.2 Board Lab placement

**Location:** inside **Pro Tools → Team** sub-section.

**Why:**

- Board Lab is a coaching workspace, not a consumer feature.
- It requires the user to upload their own `.replay.gz` — legally safe, user-owned data.
- Its value accrues to a coach with students, not to a free hobbyist browsing the meta.
- Placing it behind Pro Tools → Team makes the paywall story clean: "Board Lab is for coaches and teams."

**What it contains:**

- Upload `.replay.gz` drag & drop.
- Animated viewer with full hand reveal (unlike Replay Viewer, which shows only what the match logs contain).
- Annotation layer: coach notes per turn, alternative-line highlights, "what if" markers.
- Session export: PDF with board snapshots + notes.
- Public coach page link: the coach page URL that serves as their lead-gen asset.

**Soft entry point from Play:**

At the bottom of the Killer Curves / Replay Viewer block inside Play, a single link:

> "Want to review your own match? Coaches use Board Lab →"

One line. No banner. No modal. It leads to Pro Tools → Team → Board Lab, which gates behind Coach tier for users not yet on Coach.

This is the upgrade trigger from consumer to coach. Placed precisely at the moment the user has just experienced an insight and is thinking "I wish I could do this with my own match."

### 4.3 What must never happen

- Replay Viewer and Board Lab must not share a tab.
- Replay Viewer must not have editing controls.
- Board Lab must not appear in Home, Meta, Deck, or Community.
- Play must not contain upload UI.

---

## 5. User flow

### 5.1 First visit (anonymous)

```
Home (Set 12 Hub + deck selector + insight teaser)
  → Insight teaser: "Your worst matchup is X"
  → Play (that matchup already loaded)
    → Key Threats read
    → Killer Curves summary read
    → Replay Viewer: "See it happen" click → watch one example match
```

Target time-to-insight: **under 60 seconds**.
Target time-to-email-capture: **under 3 minutes** (Set 12 PDF lead magnet visible throughout).

### 5.2 Insight discovery (returning anonymous)

```
Home → deck saved from previous visit
  → matchup chip (best or worst) → Play
    → read Key Threats for another matchup
    → hit paywall at 4th matchup viewed today
      → upgrade prompt: "Unlock all matchups + mulligan reveal → Pro €9/m"
```

This is the conversion moment for Pro. Paywall at the 4th matchup is a natural threshold — the user has had three free matchups of value, the pattern is clear, the upgrade is contextual.

### 5.3 Replay usage

```
Play → Killer Curves summary
  → click "See it happen" on a curve
    → Replay Viewer opens inline, step-by-step, anonymized
    → at end of replay, small link: "Want to review your own match?"
      → click → drawer opens to Pro Tools → Team → Board Lab
        → Board Lab landing page gates behind Coach tier for non-Coach users
          → upgrade prompt: "Review your own replays + coach students → Coach €39/m"
```

This is the upgrade moment to Coach. Not pitched cold. Pitched after the user has seen a killer curve visualized and thought "I want this for my match."

### 5.4 Coach onboarding (post-upgrade)

```
Pro Tools → Team → Board Lab
  → upload .replay.gz
  → viewer animates
  → annotate turns
  → export PDF for student
  → public coach page populated
    → coach shares page link on Discord / Metafy / personal network
      → student lands on coach page → sees coach's stats → follows CTA to book session
```

The public coach page is the coach's lead-gen tool. It is also our SEO surface. Both sides benefit.

---

## 6. Paywall placement strategy

Three paywall triggers. No more.

| Trigger | What the user did | What they see | Conversion target |
|---|---|---|---|
| 1 | Opened 4th matchup in Play in one day | "Free covers 3 matchups/day. Unlock all matchups + full killer curves + mulligan reveal → Pro €9/m" | Convert to Pro |
| 2 | Clicked mulligan outcome reveal | "Outcome reveals are for Pro. Upgrade →" | Convert to Pro |
| 3 | Clicked Board Lab entry (from Play or drawer) | "Board Lab is for coaches. Review your own replays + coach students + public page → Coach €39/m" | Convert to Coach |

**Paywall rules:**

- Never paywall Home, Meta basic, Deck consensus, Community, or the first Replay Viewer playback per matchup.
- Never show a paywall modal before the user has experienced the value behind it.
- Always show the price and the specific feature unlocked, never vague "Upgrade to Premium".
- Paywall is a prompt, not a wall: the user can back out without friction.

---

## 7. What to hide or deprioritize

| Block | Action | Reason |
|---|---|---|
| Meta Radar in Home | Removed | Duplicates Meta tab. Split mental model. |
| Coach Corner in Home | Hidden unless coach active | Pure noise for 99% of users. |
| Trend by Turn chart in Play | Moved to Pro Tools | Too analytical for Play. Disrupts reading flow. |
| Lore chart in Play | Moved to Pro Tools | Same reason. |
| Opponent's Killer Cards in Play | Collapsed by default, reviewed post-launch | Overlaps with Key Threats. Decide after seeing usage. |
| Replay Viewer in Lab | Removed | Duplicate instance. Consolidated to Play. |
| Replay Viewer in Team (standalone) | Removed | Only embedded viewer inside Board Lab remains. |
| Tech Tornado duplicated in Deck and Meta | Consolidated in Meta (meta-driven) or Deck (deck-specific), not both | Overlapping mental model. |
| Board Lab CTA banner in Play | Replaced with single inline link | Banner would pollute Play's consumption flow. |
| Full NxN matrix heatmap in Meta | Moved to Pro Tools | Too dense for primary nav. |
| Error Detection / replay review for end users | Post-launch, not in V3 scope | Too much engineering scope; validate basic funnel first. |
| Country segmentation | Post-launch | Nice-to-have, not a revenue driver. |

---

## 8. What to keep visible

| Block | Where | Why |
|---|---|---|
| Deck selector | Home (primary), Play (locked from Home) | Entry point for everything. |
| Killer Curves summary | Play (primary) | Core value surface. |
| Key Threats | Play (open accordion) | The one insight the user must read. |
| Matchup chips (best/worst) | Home | Hook to Play. |
| Deck Fitness strip | Meta (primary) | Quick pre-tournament scan. |
| Mulligan Trainer | Play | High-engagement asset. |
| Consensus list | Deck | Expected deckbuilding surface. |
| Replay Viewer inline | Play (inside killer curves block) | Illustrates insight. |
| Board Lab | Pro Tools → Team | Coaching workstation. |
| Pre-match Cheatsheet | Play full + Home CTA | Pre-game action. |
| Set 12 Hub | Home (hero, temporary) | Launch-window acquisition. |

---

## 9. Legal / positioning notes

- **Replay Viewer anonymization is non-negotiable.** All opponent names shown as "Opponent A / B / C" by default. Player's own username only appears in their own logged-in session. This is both a legal posture (no third-party PII exposed) and a UX clarity move (user focuses on the gameplay, not who played whom).
- **Every Replay Viewer instance is labeled "Example match".** Not "real match", not "live game". This frames the content correctly for both the user and any future legal inquiry.
- **Board Lab uses user-uploaded data only.** Safe by definition.
- **No card images, no logos, no Lorcana branding in the domain or UI.** Names as text are fine. Screenshots of cards from duels.ink or lorcanito are not displayed. Card rendering, if needed, uses text + inline SVG ink pips.
- Unofficial disclaimer in footer + About page: *"Lorcana Monitor is an unofficial fan-made analytics tool. Not affiliated with, endorsed by, or sponsored by Disney or Ravensburger. Disney Lorcana TCG is a trademark of Disney and Ravensburger."*

---

## 10. Implementation roadmap (7 days)

| Day | Work | Owner effort |
|---|---|---|
| 1 | Rename tabs (Monitor→Meta, Coach V2→Play, Lab→Deck). Bottom-bar 5 chips mobile. Drawer for Improve + Pro Tools. | 6h |
| 2 | Home rebuild: Set 12 Hub + deck selector + insight teaser + matchup chips. Remove Meta Radar, Consensus, Tech Cards, Best Plays, Coach Corner. | 6h |
| 3 | Play rebuild: Key Threats accordion open, Killer Curves summary with "See it happen" links, Replay Viewer inline, Mulligan Trainer, Best Plays, How to Respond. Move Trend by Turn / Lore chart to Pro Tools. | 8h |
| 4 | Community tab: fuse Events subsection + School placeholder (5 YouTube embeds + glossary). | 4h |
| 5 | Pro Tools drawer: Deep Analytics sub + Team sub + Board Lab sub. Paywall triggers wired. Public coach page route stubbed. | 6h |
| 6 | Public hosting + HTTPS + anonymization pass on Replay Viewer. Disclaimer footer. Legal@ alias. | 4h |
| 7 | QA mobile + desktop. Fix blocking regressions only. Paywall copy polish. | 5h |

**Total: ~39 hours over 7 days.** Fits within a solo founder's part-time capacity.

---

## Final Verification

- [x] Architecture implementable in under 7 days
- [x] No feature lost (every current block has a home)
- [x] Flow simpler: 5 primary tabs instead of 7
- [x] Conversion improved: paywall placed at natural value thresholds (4th matchup, mulligan reveal, Board Lab entry)
- [x] Replay Viewer placed inside Play, linked to killer curves insight
- [x] Board Lab placed inside Pro Tools → Team, with soft entry from Play
- [x] Editing UI not mixed into Play
- [x] Anonymization pass explicit in roadmap
- [x] No generic UX advice — every recommendation is Lorcana Monitor-specific
- [x] Aligned with the Business Plan Strategist Point (SKU definitions, coaching as revenue engine)

Architecture finalized.

---

*Drafted 24 April 2026 as Architect Point for Frontend V3. Complement to `frontend_v3/docs/ARCHITECTURE.md`, `TAB_RENAME_MIGRATION.md`, `OBJECT_MIGRATION_MATRIX.md`. Aligned with `analisidef/business/BP_STRATEGIST_POINT.md`.*
