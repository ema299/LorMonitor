# Deck Tab Refactor — Parity & Copy Rules

Contratto informativo del refactor del tab **Deck** (frontend V3, `metamonitor.app`).
Questo file regola i PR che riscrivono il tab Deck: `deck_summary.js`,
`deck_improve.js`, `deck_matchups.js`, `deck_list_view.js`,
`matchup_workspace.js`, `builder_workspace.js`,
`deck_recommendation_engine.js`, `honesty_badge.js` + eventuale
restringimento di `lab.js`.

Riferimenti di contesto:
- `docs/TODO.md` §1.3 (priority restyle Deck tab)
- Memory: `project_v3_restyle_plan.md`, `project_deck_tab_benchmark.md`

---

## Merge gate

**No Deck refactor PR can merge unless every legacy data point has:**
- source confirmed
- new location confirmed
- visibility confirmed (default / expand / workspace)
- copy reviewed for observed-not-personal

La **Parity table** a fondo file è la checklist concreta. Se un dato cambia
location o visibilità, questo file si aggiorna **prima** del codice.

---

## Rule 1 — Observed, not personal (vincolante)

Il tab Deck **non legge stats personali del player**. Ogni numero esposto
deriva dal campione osservato sull'archetipo o sulla lista. Il copy deve
essere coerente.

### Campi soggetti alla regola

Qualunque stringa che espone o discende da:

- `perimeters[p].wr[deck]`
- `perimeters[p].matrix[deck]`
- `perimeters[p].otp_otd[deck]`
- `perimeters[p].meta_share[deck]`
- `perimeters[p].fitness`
- `perimeters[p].trend[deck]`
- `matchup_analyzer[deck].vs_<opp>.*` (tutti i 12 `report_type`)
- `matchup_trend[deck][opp]`
- endpoint `/api/v1/lab/iwd/{our}/{opp}` e `/api/v1/lab/card-scores/{our}/{opp}`

### Vietato

- "Your deck..."
- "You should..."
- "You are weak vs..."
- "Your performance..."
- Prima persona, sempre
- "Personal Leak Detector"
- Badge senza "observed" (es. "55% on 40 games")

### Obbligatorio

- "This archetype..." / "This list..."
- "Observed sample shows..."
- "Data suggests..."
- "This list struggles vs X in the observed sample"
- "Archetype win rate"
- "Archetype Leak Detector"
- Badge honesty format: **`NN% on N observed games · Xd · {Low|Medium|High} confidence`**

### Eccezione nota

`player_lookup[format][player][deck]` è l'unico campo personale del blob
ed è consumato **solo** da Profile → "My Stats" (non dal Deck tab). Se un
giorno aggiungiamo personal stats al Deck tab, andranno in un blocco
separato ed esplicito "Your personal stats · N games played", mai mischiate
con i numeri archetipali.

### Soglie confidence (implementate in `honesty_badge.js`)

| Sample N | Label | Decimali ammessi |
|---|---|---|
| N < 30 | Low | 0 |
| 30 ≤ N < 100 | Medium | 0 |
| N ≥ 100 | High | 1 |

Badge tappabile → bottom-sheet con copy tipo: *"Based on N observed games
in the last X days. Small samples can move quickly."*

Flag heuristic (per Deck Lens class breakdown): badge separato
`Heuristic · ability text scan` con tooltip che avverte che classificazione
via regex su `rvCardsDB[c].ability` copre ~80% dei casi.

---

## Rule 2 — Response Coverage sopra il fold

Response Coverage **non vive solo** nel Matchup Workspace. Ha sempre un
mini-block in Area A Summary (`deck_summary.js`).

- Se opp selezionato → mini-block vs quell'opp
- Se nessun opp selezionato → auto-deriva worst observed matchup da
  `matrix[deck]` (min N=15 games)
- Formato copy:

```
vs Emerald/Steel (worst observed matchup · 42% on 80 observed games)
Covers 3/5 top threat lines · 🟡 Medium coverage
[View details →]
```

Fonte: `matchup_analyzer[deck].vs_<opp>.killer_curves[].response.cards[]`
matchato contro `myDeckCards` (o `consensus[deck]` se l'utente non ha
customizzato). Il renderer resta `deck_response_check.js`, riusato come
sub-componente compact.

---

## Rule 3 — Status dot recovery

Il per-card status dot (Winner / Drag / Neutral / Low-sample) sparisce dal
deck grid come first layer, ma **riappare** in Area B Improve come "Cards
trending in this archetype":

```
Cards trending in this archetype

Underperforming
  🔴 Card A (−3pp over 60 observed games)
  🔴 Card B (−2pp over 45 observed games)

Overperforming
  🟢 Card X (+4pp over 80 observed games)
  🟢 Card Y (+3pp over 55 observed games)
```

Engine identico a `deck_grid.js._statusDot`:

- `MIN_SAMPLE = 30` (sotto = grigio "Low sample", non listato)
- `wrDelta ≥ +2pp` → 🟢
- `wrDelta ≤ -2pp` → 🔴
- Altrimenti escluso dalla short-list

---

## Rule 4 — Builder constraints

- **Max 4 copie per carta** (regola di gioco, hard)
- Deck size indicator `NN cards` — **no hard validation "min 60"**; si
  mostra un contatore tipo "60 cards · 15 unique" e se `NN != 60` un hint
  morbido ("Lorcana decks are 60 cards") ma zero blocchi all'editing
- Save / Reset to consensus sempre visibili nel workspace header
- 3 semafori sticky nel Builder Workspace:
  1. **Deck size** — contatore NN/60 (verde se esattamente 60, giallo altrimenti)
  2. **Curve health** — valutativa ("Balanced" / "Top-heavy" / "Low-curve"), non il grafico
  3. **Response coverage** — 🟢🟡🔴 vs worst observed matchup o opp selezionato
- Dettagli (Deck Lens full, class breakdown heuristic, consensus diff,
  optimized adds/cuts) aperti in drawer on-demand

---

## Rule 5 — Matchup Workspace

- **Sticky opponent switcher** (dropdown 14 opp ordinati per frequenza
  osservata nel matrix corrente) per evitare back-navigation
- **6 sezioni fisse** nell'ordine:
  1. Snapshot (`overview`, `matrix`, `otp_otd`, `matchup_trend`)
  2. How to win (`playbook`, `winning_hands`)
  3. Danger sequences (`killer_curves`, `threats_llm`, `board_state`)
  4. Your answers (`killer_responses`, `response.cards`, `deck_response_check`)
  5. Card optimization (`decklist`, `card_scores`, endpoint IWD, endpoint card-scores)
  6. Loss review (`loss_analysis`, `killer_curves[].failure_state`, `what_to_avoid`)
- CTA fisse in fondo al workspace:
  - **Open Mulligan Trainer in Play →** (consuma `pro_mulligans`, viver
    permanente in Play tab)
  - **Open Replay Viewer in Play →** (viewer consolidato in Play V3-5)

---

## Parity table

Legenda visibility:

- **D** — Default (sempre visibile aprendo Deck)
- **E** — Expand (visibile on-demand dentro Area visitata)
- **W** — Workspace (richiede entrare in Matchup/Builder workspace)
- **T** — Tap-only (detail sheet, modal, etc.)

Legenda status:

- ☐ — da verificare nel PR di riferimento
- ✅ — verificato su preview, dato presente e copy corretto
- ⚠️ — parità parziale (giustificazione richiesta nella PR description)
- ❌ — dato perso (merge bloccato)

| # | Dato oggi | Fonte blob / endpoint | Nuova location | Vis | PR | Status |
|---|---|---|---|---|---|---|
| 1 | Deck name + inks | `DECK_INKS[deck]` | Summary header | D | PR2 | ☐ |
| 2 | Archetype WR | `perimeters[p].wr[deck].wr` | Summary main KPI | D | PR2 | ☐ |
| 3 | Games osservati | `perimeters[p].wr[deck].games` | Summary honesty badge | D | PR2 | ☐ |
| 4 | Meta share | `perimeters[p].meta_share[deck].share` | Summary secondary | D | PR2 | ☐ |
| 5 | Meta Tier S/A/B/C | derived `wr[deck].wr` percentile | Summary header | D | PR2 | ☐ |
| 6 | Fitness rank 🆕 | `perimeters[p].fitness[]` | Summary secondary | D | PR2 | ☐ |
| 7 | WR trend giornaliero 🆕 | `perimeters[p].trend[deck][day]` | Summary sparkline | D | PR2 | ☐ |
| 8 | Best/worst observed matchup 🆕 | `perimeters[p].matrix[deck]` | Summary secondary | D | PR2 | ☐ |
| 9 | Cost distribution 0-8+ | `rvCardsDB[c].cost` × qty | Summary compact ("Curve: top-heavy") / Builder drawer full | D+E | PR2/PR6 | ☐ |
| 10 | Ink split | `rvCardsDB[c].ink` | Summary compact / Builder drawer full | D+E | PR2/PR6 | ☐ |
| 11 | Type split (5 tipi) | `rvCardsDB[c].type` | Summary compact / Builder drawer full | D+E | PR2/PR6 | ☐ |
| 12 | Matchup picker (ink-based) | `matchup_analyzer[deck].available_matchups` | Matchups heatmap + Workspace sticky switcher | D | PR4/PR5 | ☐ |
| 13 | Deck grid flat + qty | `myDeckCards` / `consensus[deck]` / `decklist.full_list` | List view | E | PR4 | ☐ |
| 14 | Per-card status dot (Winner/Drag/Neutral) | `matchup_analyzer[deck].vs_<opp>.card_scores[card].delta` + `games` | **Improve "Cards up/down"** + List view on-expand | D+E | PR3 | ☐ |
| 15 | Card detail sheet (art + ability + impact) | `rvCardsDB` + `card_scores` | List view tap + Builder tap | T | PR4/PR6 | ☐ |
| 16 | Adds vs consensus | `consensus[deck]` vs `myDeckCards` | Improve + Builder drawer | D+E | PR3/PR6 | ☐ |
| 17 | Cuts vs consensus | `consensus[deck]` vs `myDeckCards` | Improve + Builder drawer | D+E | PR3/PR6 | ☐ |
| 18 | WR impact badge per card | `card_scores[card].delta` + `.games` | Improve inline | D | PR3 | ☐ |
| 19 | Class breakdown (Removal/Bounce/Wipe/Evasive/Draw/Ramp) | heuristic regex su `rvCardsDB[c].ability` | Builder drawer (flag `Heuristic`) | E | PR6 | ☐ |
| 20 | Response Coverage 🟢🟡🔴 | `killer_curves[].response.cards[]` + `myDeckCards` | **Summary mini-block** + Matchup Workspace full | D+W | PR2/PR5 | ☐ |
| 21 | Matchup-optimized list (non-standard picks) | `matchup_analyzer[deck].vs_<opp>.decklist` | Matchup Workspace → Card optimization | W | PR5 | ☐ |
| 22 | Optimized Deck full_list + score | `.decklist.full_list` | Matchup Workspace → Card optimization | W | PR5 | ☐ |
| 23 | Mana curve optimized | `.decklist.mana_curve` | Matchup Workspace → Card optimization | W | PR5 | ☐ |
| 24 | Adds/cuts badges matchup-specific | `.decklist.adds/cuts` | Matchup Workspace → Card optimization | W | PR5 | ☐ |
| 25 | Import text + Copy | `.decklist.import_text` | Matchup Workspace + List view "Copy" | W+E | PR4/PR5 | ☐ |
| 26 | Tournament Decks browser (4 lists) | `reference_decklists[deck]` | List view → "Compare to pros" | E | PR4 | ☐ |
| 27 | Tournament Comparator overlay | `reference_decklists[deck]` + `myDeckCards` | List view → Comparator modal | T | PR4 | ☐ |
| 28 | Builder search + filters Cost/Type | `rvCardsDB` | Builder Workspace | W | PR6 | ☐ |
| 29 | Pro-only pool toggle | derived da `consensus` + `reference_decklists` | Builder Workspace | W | PR6 | ☐ |
| 30 | Add/remove cards (cap 4/card) | `myDeckCards` | Builder Workspace | W | PR6 | ☐ |
| 31 | Save as new decklist | `SavedDecks.saveCurrent()` | Builder Workspace header | W | PR6 | ☐ |
| 32 | Reset to consensus | `consensus[deck]` | Builder Workspace header | W | PR6 | ☐ |
| 33 | Opening hand math (hypergeometric) | `V3.MathTool` | List view + Builder | T | PR4/PR6 | ☐ |
| 34 | Replay viewer CTA → Play | — | Matchup Workspace bottom | W | PR5 | ☐ |
| 35 | IWD per card | `/api/v1/lab/iwd/{our}/{opp}` | Matchup Workspace → Card optimization | W | PR5 | ☐ |
| 36 | Card scores pro (gate Pro+) | `/api/v1/lab/card-scores/{our}/{opp}` | Matchup Workspace → Card optimization | W | PR5 | ☐ |
| 37 | Killer curves (name + freq + critical_turn + sequence + response) | `matchup_analyzer[deck].vs_<opp>.killer_curves` | Matchup Workspace → Danger sequences | W | PR5 | ☐ |
| 38 | Threats LLM | `.threats_llm` | Matchup Workspace → Danger sequences | W | PR5 | ☐ |
| 39 | Board state typical | `.board_state` | Matchup Workspace → Danger sequences | W | PR5 | ☐ |
| 40 | Playbook | `.playbook` | Matchup Workspace → How to win | W | PR5 | ☐ |
| 41 | Winning hands | `.winning_hands` | Matchup Workspace → How to win | W | PR5 | ☐ |
| 42 | Pro mulligans (Mulligan Trainer) | `.pro_mulligans` | **Play tab** (V3-5) + CTA dal Workspace | W-link | PR5 | ☐ |
| 43 | Loss analysis | `.loss_analysis` | Matchup Workspace → Loss review | W | PR5 | ☐ |
| 44 | Killer responses | `.killer_responses` | Matchup Workspace → Your answers | W | PR5 | ☐ |
| 45 | Ability cards classification | `.ability_cards` | Builder drawer (Deck Lens) | E | PR6 | ☐ |
| 46 | OTP/OTD split | `otp_otd[deck][opp]` | Matchup Workspace Snapshot + Archetype Leak Detector | D+W | PR3/PR5 | ☐ |
| 47 | Matchup trend 7d | `matchup_trend[deck][opp]` | Matchup Workspace Snapshot | W | PR5 | ☐ |
| 48 | Overview summary | `.overview` | Matchup Workspace Snapshot | W | PR5 | ☐ |

---

## A/B validation protocol

Durante lo sviluppo teniamo **due tab browser aperti**:

- **Tab 1** — frontend V3 attuale (produzione)
- **Tab 2** — preview_server.py V3 con la nuova IA

Stesso deck, stesso perimetro, stesso opp selezionato. Per ogni PR:

1. **Parity sweep** — la tabella sopra viene aggiornata ☐ → ✅ riga per riga
2. **30-second value test** — aprire il Deck tab e cronometrare: in 30 secondi
   l'utente deve aver identificato almeno:
   - WR osservato + confidence
   - Miglior/peggior matchup
   - 1 azione consigliata con "Data suggests..."
3. **5-second find test** — scegliere 3 dati a caso dalla Parity table e
   verificare che siano raggiungibili in ≤5 secondi. Se no → bug IA, non UI
4. **Copy audit** — grep della PR per `Your deck`, `You should`, `You are`,
   `Your performance` → tutti gli hit vanno corretti prima del merge

---

## Rollout sequence

```
PR0 — questo file (merge prima di toccare codice UI)
PR1 — honesty_badge.js + deck_recommendation_engine.js + copy rule linter grep
PR2 — deck_summary.js (Area A) con Response Coverage inline + trend sparkline
PR3 — deck_improve.js (Area B) con Cards up/down + Archetype Leak Detector
PR4 — deck_matchups.js + deck_list_view.js (Area C + D)
PR5 — matchup_workspace.js con sticky opponent switcher
PR6 — builder_workspace.js (deprecation deck_builder.buildPanel)
PR7 — cleanup lab.js + rimozione dead code + SW cache bump
```

Ogni PR chiude le righe della Parity table che ha in scope (colonna `PR`).

---

## Open questions / decisioni da confermare

- [ ] **Archetype Leak Detector** (riga ≈46) — basato su `otp_otd` + `loss_analysis`
  + `killer_curves[].failure_state`. Ordine di ranking leak:
  otp/otd gap > worst matchup > failure_state più frequente? Confermare in PR3.
- [ ] **Confidence threshold** globale per il Deck tab — oggi Monitor usa
  `min_games=15` per fitness, deck_grid usa `MIN_SAMPLE=30`. Uniformare a 30
  o mantenere due soglie diverse? Decidere in PR1.
- [ ] **Fitness rank** — mostriamo rank assoluto ("#4 of 14") o banda
  qualitativa ("Top tier") in Summary? Confermare in PR2.
- [ ] **Recommendation engine** — ordine di priorità delle azioni suggerite.
  Bozza: (1) missing response cards, (2) pro consensus diff high, (3) cuts/adds
  da `meta_deck`. Confermare in PR1.

---

## PR status

| PR | Status | Notes |
|---|---|---|
| PR0 | ✅ merged-in-dev | this file |
| PR1 | ✅ | `honesty_badge.js` + `deck_recommendation_engine.js` + linter |
| PR2 | ✅ | `deck_summary.js` (Area A) + CSS + wire in `lab.js`. Summary + Response Coverage mini + Recommended actions live. |
| PR3 | ✅ | `deck_improve.js` (Area B) — Cards trending + Archetype Leak Detector |
| PR4 | ✅ | `deck_matchups.js` heatmap + `deck_list_view.js` collapsed Your list |
| PR5 | ✅ | `matchup_workspace.js` — 6 sections, sticky opp switcher, IWD async |
| PR6 | ✅ | `builder_status.js` — 3 live semafori sticky + mobile reorder (lens accordion). Kept builder inline instead of full-screen overlay (user preference). |
| PR7 | ✅ | Legacy removed from `lab.js`: Response Coverage inline, Matchup-optimized accordion, Optimized Deck panel, Replay CTA. All absorbed by workspace. |

## Rows closed by PR7

Rows 20 (Response Coverage), 21 (Matchup-optimized list), 22-25 (Optimized Deck + mana curve + adds/cuts + Copy), 34 (Replay CTA) — all removed from the always-on render path. Surfaces live only in Summary (mini) and Matchup Workspace.

---

*Last updated: 2026-04-24 · Owner: Deck refactor track · Related: `docs/TODO.md` §1.3*
