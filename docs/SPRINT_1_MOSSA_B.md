# Sprint-1 Mossa B — Blind Playbook native generation in App_tool

**Status:** ✅ COMPLETATA 15/04/2026 (commit `df8e486` + merge `f4a0d2d`).
Generator nativo + CLI + helpers in App_tool. Prompt EN, OpenAI key proprio.
Test end-to-end OK su RS core (~$0.01, 14s, narrative 1651 chars EN).
Batch completo (24 deck × ~$0.008 = ~$0.20) in esecuzione.

**Pendente post-batch:** aggiornare crontab per cron settimanale nativo
(martedi 01:00) e disattivare il bridge importer.

## Goal

Sostituire l'importer bridge (`scripts/import_playbooks.py` che legge da
`analisidef/output/deck_playbook_*.json`) con la generazione nativa OpenAI
dentro App_tool. Spegnere il batch settimanale di analisidef.

## Stato attuale (Mossa A)

- Tabella `deck_playbooks` in PG con 24 row (12 deck × 2 formati).
- Endpoint pubblico `GET /api/v1/profile/blind-playbook/{deck}?game_format=core|infinity`.
- Frontend accordion "How to Pilot — Blind Guide" nel Profile tab.
- Render: strategic frame (chips archetype/tier/skill + one-liner + principles)
  + narrative + pro references footer.
- Importer `scripts/import_playbooks.py` legge JSON da analisidef e mappa
  alias `ES → EmSa`, `AS → AmSa`.

## Cosa fare in Mossa B

1. **Port `gen_deck_playbook.py`** (~1573 LOC) da `analisidef/lib/` a
   `App_tool/pipelines/playbook/generator.py`. Adattare path costanti:
   - `BASE = analisidef path` → leggere da PG (`matchup_reports` per digest)
   - `DASHBOARD_DATA = analisidef/daily/output/dashboard_data.json` → snapshot_assembler
   - `CARDS_DB_PATH = cards_db.json` → modulo App_tool `static_data_service`
   - `SNAPSHOT_DIR = decks_db/history` (file system condiviso, OK lasciare)

2. **Port helper `lib/cards_dict.py`** (366 LOC) - servono solo 4 funzioni:
   `_classify_removal`, `_is_draw`, `_is_ramp`, `_parse_shift_cost`. Versione
   minimale gia' usabile in `App_tool/lib/cards_dict.py` (vuoto ora).

3. **CRITICAL — caveat lingua: il prompt deve produrre output in INGLESE.**
   In `lib/gen_deck_playbook.py` cercare `build_narrative_prompt` (linea 1059)
   e tutto il prompt content. Stringhe da TRADURRE/CAMBIARE:
   - `'"narrative": "2-3 paragrafi di prosa, 220-280 parole, italiano fluido"'`
     → `'"narrative": "2-3 paragraphs of prose, 220-280 words, fluent English"'`
   - Tutte le istruzioni in italiano nel prompt → inglese
   - Validator `validate_narrative` (linea 1234) ha check `min_words/max_words` —
     verifica che funzioni anche su testi inglesi (probabilmente OK)
   - `strategic_frame.one_liner`, `key_principles[]`: anche questi devono uscire
     in inglese, controllare il prompt che li genera

   **REGOLA:** App_tool e' inglese-only (vedi `feedback_app_language_english.md`
   in memoria). Nessun output utente-visibile in italiano.

4. **Cron nativo App_tool**: martedi' 01:00 (dopo KC che gira alle 00:00).
   Worker `App_tool/backend/workers/playbook_worker.py` invoca generation per
   tutti i 24 (deck, format) e fa upsert via `playbook_service.upsert_playbook`.

5. **Schema output PG**: gia' disegnato per accogliere tutto:
   - `playbook` JSONB (con campo `narrative`)
   - `strategic_frame` JSONB (chips, one_liner, principles)
   - `weekly_tech` JSONB (new_tech, dropped_tech)
   - `pro_references` JSONB
   - meta: model, input_tokens, output_tokens, cost_usd, elapsed_sec

6. **OpenAI key**: leggere da `/tmp/.openai_key` (gia' usato da KC batch).
   Aggiungere fallback `OPENAI_API_KEY` env var.

7. **Spegnimento bridge**:
   - Disabilitare `scripts/import_playbooks.py` (oppure tenere come fallback)
   - Aggiornare crontab: rimuovere ruolo bridge, aggiungere worker nativo
   - Aggiornare `docs/MIGRATION_PLAN.md` Fase F/G/H

## Caveat aggiuntivi

- **Costo**: ~$0.20/settimana (24 × ~$0.008). Stima validata 15/04/2026 batch reale.
- **Tempo batch**: ~5 min totali (24 deck, ~12s ciascuno mediamente).
- **Validazione**: il prompt v2 ha 2 attempts max + retry su validation failure.
  Mantenere questa logica: hallucination/cards-out-of-deck succedono.
- **Idempotenza**: `upsert_playbook` gia' atomico su (deck, fmt, generated_at).
  Re-run sicuro.

## Riferimenti

- Mossa A commits: 5d5d79f, 8a33b58, dc87e76, a92596e, c6a8f93
- analisidef source: `lib/gen_deck_playbook.py`, `run_deck_playbook_batch.py`
- Memoria persistente: `feedback_app_language_english.md`
