# Killer Curves — Note operative

## Quello che vogliamo fare

- Blindare `How to Respond` in modo che non sia generico.
- Se `response.cards` contiene carte, almeno una di quelle carte deve essere nominata testualmente nei campi leggibili della risposta.
- Per Core, permettere anche un piccolo `LEGAL FALLBACK POOL` di carte legalmente ammissibili ma non ancora osservate nel meta, limitato all’ultimo set Core legale.
- Tenere sempre il meta osservato come prima scelta; il fallback deve essere solo un secondo livello, non il comportamento standard.
- Evitare che il post-filter distrugga il fallback Core-legal.
- Distinguere chiaramente tra:
  - carte viste davvero nei match
  - carte Core-legal ma non ancora giocate
  - carte fuori meta da escludere

## Comportamento desiderato

- `How to Respond` deve spiegare come rispondere a quella curva specifica.
- La risposta deve citare una o piu' carte del nostro deck quando propone `response.cards`.
- Per Set 12/Core, le carte legalmente ammissibili del set nuovo devono poter entrare nel pool, anche se il meta non le ha ancora viste abbastanza.
- Il fallback deve restare controllato e tracciabile, senza inventare carte o forzare linee non supportate.

## Stato 2026-04-26 — validator wave applicato

`pipelines/kc/validator.py` v1.0 (~440 LOC) creato. Single source of truth per tutti i check P0/P1/P2 KC. Implementa direttamente i tre principi sopra:

- **Mention rule** (`response_missing_named_card` P0): se `response.cards != []` e nessun nome appare nei campi leggibili (`headline`, `core_rule`, `priority_actions`, `what_to_avoid`, `stock_build_note`, `off_meta_note`, `play_draw_note`, `failure_state`, `v3_payload.user_copy`), curva blocked.
- **3-tier card classification**: per ogni carta in `response.cards` il validator tagga `kept_meta` (≥20 plays in 30gg) | `kept_fallback` (Core-legal del latest set ma 0 plays) | `dropped_*` (off-color / core-illegal / non-meta-non-fallback / not-in-db). Conteggi granulari in `meta.quality_drop_metrics`.
- **Sequence guard simmetrico**: `sequence.plays[].card`, `key_cards`, `combo`, `recursion_sources` validati sui colori avversario. Sequence vuota dopo filtri = P0.
- **Required v2 fields**: `headline`, `core_rule`, `priority_actions` (≥2), `what_to_avoid` (≥1), `failure_state`. Mancanti = P0 `response_v2_incomplete`.
- **EN heuristic**, `v3_payload`/`self_check` completeness = P1/P2 warnings.

Wirato in `scripts/generate_killer_curves.py::generate_one` pre-upsert. CLI `--quality-gate {off|warn|strict}` (default `warn`). In strict mode, `quality_status='blocked'` aborta upsert. Persistito in `killer_curves.meta`: `validator_version`, `quality_status`, `quality_errors`, `quality_warnings`, `quality_drop_metrics`, `quality_completeness`, `quality_gate_mode`.

## Workflow batch martedì 01:30

```
[01:30] cron lancia: scripts/generate_killer_curves.py --format all --force
                     (default --quality-gate warn)
   ↓
[per matchup] LLM call → postprocess (3-tier filter) → repair LLM (1 shot if generic)
              → VALIDATOR (zero API) → upsert con meta.quality_status
   ↓
[post-batch] scripts/refresh_kc_matchup_reports.py --format all
   ↓
[verify]    scripts/kc_consistency_check.py     (zero API, exit 1 on drift)
   ↓
[refresh]   curl -X POST -H "X-Admin-Token: …" /api/v1/admin/refresh-dashboard
```

Audit script per ispezionare DB esistente: `scripts/audit_killer_curves.py [--format core|infinity|all]` → `/tmp/kc_audit.json`.

## Stato baseline 26/04

- DB: 265 righe `is_current=true` (134 Core / 131 Infinity)
- Audit pre-validator: 1 PASS / 14 WARN / 250 BLOCKED (94% del batch 04-21 pre-blindatura, atteso)
- Consistency check: 0 P0 drift, 0 P1 blocked_but_published, 5 ghost rows P2 (curves=[])
- Smoke test reali (gate strict): `EmSa vs AmyE` Core → PASS · `AmSa vs AmyE` Core → ERR_blocked (repair shot fallisce, comportamento corretto)
- Spesa OpenAI smoke: $0.111

## Consumer V3 — wiring `v3_payload` in UI (26/04)

### Tab Play — `coach_v2.js`

`frontend_v3/assets/js/dashboard/coach_v2.js` ora consuma `v3_payload` quando presente. Funzioni:

- `kcRenderV3Payload(p3, compact)` (NEW): renderizza badge orizzontali `coach_badges` (max 3, gold pill chips), `one_line_hook` come headline punchy gold-bold, `mulligan_focus` come "Mulligan Priority" bullet (max 2), `turn_checklist` come "Turn Checklist" rows T1/T2/T3 (max 3).
- `kcRenderResponse(resp, opts)` esteso: accetta `opts.v3Payload`. v3 elements vanno PRIMA delle sezioni v2 (badges + hook in cima). Se v2 è completamente assente, fallback su `v3_payload.user_copy.expanded`.
- `threatBriefs` (riga 1620+) ora propaga `v3_payload: curve.v3_payload` insieme a `response`. Caller principale (`kcRenderResponse(tb.response, {compact:true, v3Payload: tb.v3_payload})`).

### Tab Deck — `deck_matchups.js`

`_curvesBlockHtml(opp, deckCode)` esteso per esporre `v3_payload` in modo compatto (Deck è denso, mostra molti matchup):

- `coach_badges` (max 2) come pillole gold inline accanto al name della curva
- `one_line_hook` come row sotto la header, gold-bold
- `mulligan_focus` (max 2, joined `·`) come row "Mulligan: …" con border-left gold
- Curve senza `v3_payload` (legacy) renderizzano come prima — zero regression

CSS classi nuove in `frontend_v3/assets/css/dashboard/deck_summary.css`: `.mh-exp-coach-badge`, `.mh-exp-hook`, `.mh-exp-mulligan`, `.mh-exp-mul-lbl`.

### Filter sync `quality_status` (26/04)

`scripts/refresh_kc_matchup_reports.py` esteso con CLI `--quality-filter {none,blocked,non-pass}` default `blocked`:

- `none` → copia tutto (legacy)
- `blocked` (default) → skip righe con `meta.quality_status='blocked'`
- `non-pass` → solo `pass` viene copiato (più aggressivo)

Righe legacy senza `quality_status` (pre-26/04) sono sempre sincronizzate (no regression). Righe blocked dal validator non finiscono in `matchup_reports`, quindi non finiscono nel blob V3, quindi non sono mostrate in UI.

Smoke run 26/04 con `--quality-filter blocked --format all`: 265 sync, 0 skipped (tutte legacy con `quality_status=null`). Dal batch martedì 28/04 in poi, le BLOCKED nuove saranno filtrate.

Comportamento graceful complessivo: curve senza `v3_payload` (righe pre-25/04) renderizzano come prima. Curve nuove con payload completo mostrano coach badges + hook + mulligan + turn checklist sopra le sezioni v2 dettagliate. Tutte le stringhe HTML-escaped.

Cache invalidation: nessuna serve, service worker V3 è self-destruct (`frontend_v3/sw.js`), preview server serve con `Cache-Control: no-store`. Hard refresh browser è sufficiente.

Prossima azione: lasciare girare il batch automatico martedì 28/04 con gate `warn`. Dopo primo batch clean, le righe nuove avranno tutte `v3_payload` popolato e la UI Play+Deck mostrerà coach badges + hook + mulligan + turn checklist senza altri interventi. Le BLOCKED non passano al blob V3 grazie al filter sync. Valutare passaggio a `strict` post-batch.

## Riferimenti

- Validator: `pipelines/kc/validator.py`
- Prompt e guard: `pipelines/kc/build_prompt.py`
- Generatore batch: `scripts/generate_killer_curves.py` (CLI `--quality-gate`)
- Audit dry-run: `scripts/audit_killer_curves.py`
- Consistency check: `scripts/kc_consistency_check.py`
- Sync verso V3: `scripts/refresh_kc_matchup_reports.py`
- Prompt istruzioni: `pipelines/kc/prompts/istruzioni_compact.md`
- Blindatura generale: `docs/KILLER_CURVES_BLINDATURA_V3.md`
- TODO sprint: `docs/TODO.md` §C.7.4

