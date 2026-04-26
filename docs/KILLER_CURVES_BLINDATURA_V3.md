# Killer Curves V3 — Lettura Critica e Blindatura

> Snapshot operativo: 2026-04-25. Questo documento legge il processo end-to-end delle Killer Curves: digest, prompt GPT, validazione, persistenza, sync verso `matchup_reports`, trasporto nel blob V3 e rendering "How to Respond".

## Executive Summary

Le Killer Curves sono gia' molto piu' blindate rispetto alla prima versione: esistono guardrail su colori, legalita' Core, meta-relevance, cost tracking, canary giornaliero, cleanup `is_current` e schema response v2. Il rischio residuo non e' "non c'e' controllo"; il rischio e' che alcuni controlli sono parziali, alcuni sono solo prompt-based, e il trasporto in V3 passa da piu' copie dello stesso dato.

La pipeline reale oggi e':

```text
matches + output/digests
  -> pipelines/kc/build_prompt.py
  -> scripts/generate_killer_curves.py
  -> PG killer_curves
  -> scripts/refresh_kc_matchup_reports.py oppure scripts/generate_matchup_reports.py
  -> PG matchup_reports(report_type='killer_curves')
  -> backend/services/snapshot_assembler.py
  -> /api/v1/dashboard-data cache
  -> frontend_v3/assets/js/dashboard/coach_v2.js
```

I punti piu' delicati sono:

1. `response.cards` e' validato bene sui colori, ma `sequence.plays` non ha ancora un validator simmetrico completo.
2. Core vs Infinity e' protetto da prompt guard + post-filter, ma il dato puo' restare divergente tra `killer_curves` e `matchup_reports`.
3. Lo schema JSON esiste, ma non sembra applicato come gate hard dentro `generate_killer_curves.py`.
4. `How to Respond` dipende dai campi v2: se mancano, la V3 degrada su `strategy`, che e' spesso troppo generica.
5. La cache `/api/v1/dashboard-data` puo' nascondere un fix appena fatto se non viene invalidata o refreshata.

Dato DB letto il 2026-04-25:

| Fonte | Core | Infinity |
|---|---:|---:|
| `killer_curves is_current=true` | 134 matchup / 488 curve | 131 matchup / 387 curve |
| `matchup_reports is_current=true, killer_curves` | 132 matchup / 483 curve | 126 matchup / 387 curve |

Questa differenza e' piccola ma importante: la V3 non consuma direttamente la tabella `killer_curves`, quindi il controllo di qualita' deve misurare anche il dato effettivamente servito.

## Processo Letto Criticamente

### 1. Costruzione del prompt

File principale: `pipelines/kc/build_prompt.py`.

Cose gia' buone:

- Distingue chiaramente colori nostri e colori avversario.
- Inserisce guardrail per `response.cards`: solo colori del nostro deck.
- Inserisce guardrail per `sequence.plays`: solo colori dell'avversario.
- Per Core aggiunge un blocco legalita' basato su `meta_epochs.legal_sets`.
- Aggiunge meta-relevance: evita carte legalmente possibili ma non giocate nel meta recente.
- Usa `our_playbook` per rendere "How to Respond" meno teorico.
- Chiede esplicitamente response v2: `headline`, `core_rule`, `priority_actions`, `what_to_avoid`, `stock_build_note`, `off_meta_note`, `play_draw_note`, `failure_state`.

Rischi:

- La guardia e' ancora testuale: GPT puo' obbedire quasi sempre, ma non e' un contratto.
- `_build_sequence_guard()` elenca solo alcune carte nostre come vietate nella sequence; non valida tutto il dominio carta per carta.
- `_build_core_legality_guard()` costruisce la lista di illegali da candidati nel digest, non da ogni possibile carta poi generata.
- `DECK_COLORS` e' duplicato in piu' file. Se un codice deck o colore cambia in un punto e non nell'altro, nasce drift.
- Il prompt dice "response text in ENGLISH only", ma la lingua non e' un gate hard in generazione.

Blindatura consigliata:

- Un validator unico post-GPT che controlla `response.cards`, `sequence.plays`, `key_cards`, `combo` e `recursion_sources`.
- Un singolo modulo condiviso per deck codes, colori e alias legacy.
- Fallire il run, o almeno marcare `quality_status='blocked'`, se i campi v2 sono assenti.

### 2. Chiamata GPT e post-processing

File principale: `scripts/generate_killer_curves.py`.

Cose gia' buone:

- Temperature `0`.
- System prompt: solo JSON, niente markdown, niente tag colore nei nomi.
- Produzione in JSON mode con `response_format={"type": "json_object"}`.
- Parse JSON con rimozione di code fence.
- Persistenza di costo, token, durata, `prompt_hash`, `prompt_contract_hash`, `digest_hash`, `schema_version`, `cards_dropped`, `run_id`.
- Post-filter:
  - `check_data(drop_invalid=True)` rimuove carte off-color da `response.cards`.
  - `_strip_core_illegal_cards()` rimuove carte Core-illegal da response e sequence.
  - `_strip_non_meta_cards()` rimuove carte non meta da response e sequence.

Rischi:

- Se il JSON e' valido ma semanticamente povero, viene salvato.
- Se il post-filter rimuove carte fondamentali, la curva puo' restare formalmente valida ma strategicamente vuota.
- Non c'e' retry automatico dopo schema fail o semantic fail.
- Non viene chiamato `schemas.validate.validate(..., "killer_curves")` nel flusso di generazione.
- `cards_dropped` e' un numero aggregato; non dice se e' stata rimossa una carta da `response` o dalla `sequence`, ne' quale.

Blindatura consigliata:

- Validare schema prima dell'upsert.
- Separare `response_cards_dropped`, `sequence_cards_dropped`, `core_illegal_dropped`, `non_meta_dropped`.
- Se una curva dopo i filtri ha `response.cards=[]`, `sequence` vuota, o campi v2 mancanti, non pubblicarla come OK.
- Aggiungere retry guidato: "Your previous JSON failed these checks: ... return corrected JSON only".

### 3. Validazione colore / legalita' / formato

File principali:

- `pipelines/kc/vendored/postfix_response_colors.py`
- `pipelines/kc/meta_relevance.py`
- `scripts/kc_spy_canary.py`
- `schemas/killer_curves.schema.json`

Cose gia' buone:

- `check_data()` rimuove tag `[AMBER]`, `[STEEL]`, ecc.
- `check_data()` blocca carte fuori colore in `response.cards`.
- `kc_spy_canary.py` valida tutte le righe correnti e fa autofix su off-color.
- `meta_relevance.py` usa dati reali `CARD_PLAYED` degli ultimi 30 giorni.
- Lo schema v2 e' documentato.

Rischi:

- `check_data()` non controlla `sequence.plays[].card`.
- `check_data()` non controlla Core vs Infinity.
- Il canary valida off-color response, ma non verifica completezza v2, lingua, legalita', meta-relevance, sequenza avversaria o trasporto V3.
- Lo schema JSON e' permissivo: molte proprieta' non hanno `required`, quindi un oggetto povero puo' passare.
- Lo schema root richiede `our_deck` / `opp_deck`, ma la generazione usa spesso `metadata.our_deck` / `metadata.opp_deck`; questo va normalizzato prima della validazione o corretto nello schema.

Blindatura consigliata:

- Creare `pipelines/kc/validator.py` con severita':
  - `P0 fail`: JSON non valido, deck mismatch, formato mismatch, Core-illegal, carta fuori colore, card name non esistente, campi v2 mancanti, sequence lato sbagliato.
  - `P1 warn`: lingua non EN, response generica, `cards_dropped > 0`, poche curve, frequenza sospetta.
  - `P2 info`: costo, token, prompt hash, freshness.
- Aggiornare `kc_spy_canary.py` per usare lo stesso validator.
- Rendere lo schema piu' stretto per `response.format_version = v2` e campi v2 required.

### 4. Persistenza in `killer_curves`

File principale: `scripts/generate_killer_curves.py`.

Cose gia' buone:

- Upsert per `(game_format, our_deck, opp_deck, generated_at)`.
- Demote delle righe vecchie per la stessa coppia.
- `meta` JSONB con costo e hash.
- Cleanup storico dei duplicati `is_current` gia' fatto.

Rischi:

- La demotion usa `generated_at < :generated_at`; se due run nello stesso giorno producono una versione peggiore, l'upsert sovrascrive lo stesso record. Non c'e' storico intra-day.
- Non c'e' `quality_status` esplicito. Una riga "ripulita" ma impoverita sembra uguale a una riga perfetta.
- `digest_hash` e `schema_version` sono ora persistiti in `meta`, ma le righe storiche non li hanno: il risparmio pieno parte dai prossimi batch.

Blindatura consigliata:

- Aggiungere in `meta`: `validator_version`, `quality_status`, `quality_errors`, `quality_warnings`.
- Se possibile, aggiungere una tabella `kc_runs` o una versione intra-day con timestamp, non solo `date`.
- Pubblicare in V3 solo righe `quality_status='pass'`.

### 5. Trasporto verso `matchup_reports`

File principali:

- `scripts/refresh_kc_matchup_reports.py`
- `scripts/generate_matchup_reports.py`
- `pipelines/matchup_reports/generator.py`

Cose gia' buone:

- `load_killer_curves_from_db()` copia le KC correnti dentro i report.
- `refresh_kc_matchup_reports.py` permette sync rapido senza rigenerare tutti i report.
- `generate_matchup_reports.py` demote tutto il formato a inizio batch per evitare shadowing vecchio.

Rischi:

- La V3 legge `matchup_reports`, non `killer_curves`. Se il sync non gira, la tabella sorgente e la V3 divergono.
- Oggi c'e' divergenza: `killer_curves` ha piu' matchup correnti di `matchup_reports`.
- `refresh_kc_matchup_reports.py` demote per formato/report/date, ma non confronta conteggi finali con sorgente.
- Non c'e' un checksum del payload trasportato.

Blindatura consigliata:

- Dopo ogni generazione KC, eseguire sempre sync `killer_curves -> matchup_reports`.
- Aggiungere check automatico:

```sql
SELECT k.game_format,
       count(*) FILTER (WHERE m.our_deck IS NULL) AS missing_in_matchup_reports
FROM killer_curves k
LEFT JOIN matchup_reports m
  ON m.game_format = k.game_format
 AND m.our_deck = k.our_deck
 AND m.opp_deck = k.opp_deck
 AND m.report_type = 'killer_curves'
 AND m.is_current = true
WHERE k.is_current = true
GROUP BY k.game_format;
```

- Salvare in `matchup_reports.data` o `meta` un `source_kc_generated_at` / `source_prompt_hash`.
- Fallire deploy/cache refresh se ci sono missing non spiegati.

### 6. Trasporto nel blob V3

File principali:

- `backend/services/snapshot_assembler.py`
- `backend/api/dashboard.py`
- `frontend_v3/assets/js/adapters/live.js`

Cose gia' buone:

- `_build_matchup_analyzer()` prende `matchup_reports is_current=true`.
- Il frontend distingue Core e Infinity con `matchup_analyzer` e `matchup_analyzer_infinity`.

Rischi:

- Cache server `/api/v1/dashboard-data` ha TTL: una correzione KC puo' non vedersi subito.
- `_build_matchup_analyzer()` non controlla che il report abbia il formato giusto rispetto al blob in cui finisce; si fida di `game_format`.
- Non espone una health summary KC nel blob: la V3 mostra contenuto ma non sa se e' stale, filtrato o con warning.

Blindatura consigliata:

- Dopo batch KC: refresh esplicito `/api/v1/dashboard-data?refresh=true`.
- Inserire nel blob `kc_quality`:
  - counts per formato
  - ultimo `generated_at`
  - missing `matchup_reports`
  - stale > N giorni
  - pct response v2
  - pct con `cards_dropped > 0`
- In V3, nascondere o etichettare KC con `quality_status != pass`.

### 7. Rendering V3 e "How to Respond"

File principale: `frontend_v3/assets/js/dashboard/coach_v2.js`.

Cose gia' buone:

- `kcResponseSections()` usa i campi v2 in modo ordinato.
- Se i campi v2 mancano, `kcRenderResponse()` fa fallback su `strategy`.
- La threat view unifica `killer_curves` e `threats_llm`.
- `How to Respond` mostra `headline`, `core_rule`, azioni, errori da evitare, note stock/off-meta, play/draw, failure state.

Rischi:

- Il fallback su `strategy` evita crash, ma nasconde output povero.
- Non c'e' escape HTML su molte stringhe KC renderizzate. I dati sono interni, ma arrivano da LLM: meglio non fidarsi.
- Se `killer_responses` manca, il blocco dedicato "Play this, avoid that" non si vede; resta la response interna alla curva.
- Le curve sono ordinate per `frequency.pct`; se GPT produce frequenze incoerenti, la UI enfatizza la curva sbagliata.

Blindatura consigliata:

- Escapare tutte le stringhe provenienti da KC prima di inserirle in HTML.
- Mostrare solo response v2 complete nella UI principale; mettere fallback v1 in stato "legacy".
- Aggiungere un piccolo badge interno/non pubblico durante QA: `KC pass`, `legacy`, `filtered`, `stale`.
- Validare lato frontend che `currentFormat` scelga sempre il blob giusto.

## Failure Modes da Bloccare

### P0 — Core contaminato da Infinity

Sintomi:

- Carte fuori set legali Core in `sequence` o `response`.
- Carte tipiche Infinity visibili in matchup Core.

Controlli esistenti:

- Prompt legality guard.
- `_strip_core_illegal_cards()`.
- `meta_epochs.legal_sets`.

Blindatura mancante:

- Validator hard che fallisce se trova Core-illegal, non solo strip.
- Test sul blob V3, non solo su tabella `killer_curves`.

### P0 — Lato sbagliato: carte nostre nella sequenza avversaria

Sintomi:

- `sequence.plays` contiene carte del nostro deck.
- "Opponent's Plan" mostra la nostra risposta come se fosse la curva killer.

Controlli esistenti:

- Prompt sequence guard.
- Meta/core strip parziale.

Blindatura mancante:

- Post-validator simmetrico per `sequence.plays[].card` nei colori avversario.
- Check su `key_cards` e `combo`.

### P0 — "How to Respond" generico o non adeguato

Sintomi:

- Risposta valida grammaticalmente ma non azionabile.
- Non menziona turno critico, priorita', carta setup o errore da evitare.
- Campi v2 assenti e fallback su `strategy`.

Controlli esistenti:

- Prompt richiede v2.
- UI renderizza v2 se presente.

Blindatura mancante:

- Required hard: `format_version='v2'`, `headline`, `core_rule`, almeno 2 `priority_actions`, almeno 1 `what_to_avoid`, `failure_state`.
- Quality heuristic: response deve citare almeno una carta della curva o una carta risposta legale.
- Harder rule applicata dopo il 25/04/2026: se `response.cards` non e' vuoto, almeno una di quelle carte deve comparire testualmente nelle stringhe leggibili di `How to Respond` (`headline`, `core_rule`, `priority_actions`, `what_to_avoid`, `stock_build_note`, `off_meta_note`, `play_draw_note`, `failure_state`).
- Il prompt ora include anche un `LEGAL FALLBACK POOL`: carte Core-legal dell'ultimo set legale, non ancora osservate nel meta, che il modello puo' usare solo se la curva non ha una risposta osservata abbastanza precisa.

### P1 — Dato generato ma non arrivato in V3

Sintomi:

- In DB `killer_curves` e' corretto, ma la dashboard mostra vecchio/nessun dato.

Cause:

- Sync `matchup_reports` non eseguito.
- Cache dashboard non refreshata.
- Mismatch Core/Infinity nel frontend.

Blindatura:

- Check conteggi `killer_curves` vs `matchup_reports`.
- Refresh cache obbligatorio post-batch.
- Smoke API su `/api/v1/dashboard-data` per 3 matchup campione Core e 3 Infinity.

### P1 — Post-filter impoverisce ma pubblica

Sintomi:

- `cards_dropped > 0`, response senza carte, sequence con turni vuoti.

Blindatura:

- Se una curva perde una carta critica, mandarla in retry invece che pubblicarla.
- Mettere `quality_status='warn'` o `blocked`.

## Checklist Release KC per V3

Questa e' la checklist minima prima di dire "le Killer Curves sono vendibili".

### Prima del batch

```bash
venv/bin/python scripts/generate_digests.py --format all
venv/bin/python scripts/generate_killer_curves.py --format all --dry-run
```

Controlli:

- Nessun digest mancante per matchup che vuoi vendere.
- `meta_epochs.legal_sets` corretto per Core.
- `OPENAI_MODEL` intenzionale.
- Budget OpenAI disponibile.

Nota: il comando documentato in vecchie note come `--force-all` non esiste nello script attuale. Il comando reale e' `--format all --force`.

### Batch

```bash
OPENAI_MODEL=gpt-5.4-mini venv/bin/python scripts/generate_killer_curves.py --format all --force
```

Controlli:

- Exit code `0`.
- `cards_dropped` basso e spiegabile.
- Nessun `ERR:json_parse`.
- Costo in linea con stima.

### Validazione DB sorgente

```bash
venv/bin/python scripts/kc_spy_canary.py --no-api
venv/bin/python scripts/kc_cost_report.py --days 7
```

Query utili:

```sql
SELECT game_format, count(*) AS matchups, sum(jsonb_array_length(curves)) AS curves
FROM killer_curves
WHERE is_current = true
GROUP BY game_format;
```

```sql
SELECT game_format, count(*) AS bad
FROM killer_curves
WHERE is_current = true
  AND (meta->>'cards_dropped')::int > 0
GROUP BY game_format;
```

### Sync verso V3

```bash
venv/bin/python scripts/refresh_kc_matchup_reports.py --format all
```

Poi controllare:

```sql
SELECT game_format, count(*) AS rows, sum(jsonb_array_length(data)) AS curves
FROM matchup_reports
WHERE is_current = true AND report_type = 'killer_curves'
GROUP BY game_format;
```

### Cache/API

Fare refresh del blob:

```text
GET /api/v1/dashboard-data?refresh=true
```

Smoke test:

- Un matchup Core con KC note.
- Un matchup Infinity con KC note.
- Un matchup dove `cards_dropped > 0`, se esiste.
- Un matchup appena rigenerato.

Verificare nella risposta:

- `matchup_analyzer[OUR].vs_OPP.killer_curves` per Core.
- `matchup_analyzer_infinity[OUR].vs_OPP.killer_curves` per Infinity.
- Campi v2 presenti in `response`.

## Ottimizzazione LLM: Spendere Meno e Sfruttare Meglio Ogni Call

La chiamata LLM e' costosa, quindi la domanda corretta non e' solo "posso ridurre token?". La domanda corretta e': "ogni call produce abbastanza valore V3 da giustificare il costo?". La risposta e' si', ma solo se la call genera payload strutturato direttamente riusabile dalla V3, non testo generico.

### Principio

Le parti numeriche devono restare Python/SQL. Il LLM deve fare solo cio' che vale il costo:

- interpretare una curva reale;
- trasformarla in coaching leggibile;
- rendere la risposta specifica per matchup/turno/carta;
- produrre micro-copy e campi UI pronti;
- aiutare il QA spiegando cosa pensa di aver soddisfatto.

Non chiedere al LLM:

- card scores;
- meta share;
- win rate;
- deck optimizer;
- legalita' carte;
- conteggi o frequenze calcolabili.

Quelli sono dati deterministici e devono restare fuori dalla spesa LLM.

### Schema extra da chiedere nella stessa call

Oggi la KC contiene gia' `response` v2. Ha senso aggiungere un blocco `v3_payload` leggero, pensato per riuso diretto in Play/Coach/Profile senza seconda call:

```json
{
  "v3_payload": {
    "one_line_hook": "short, sharp V3 headline for this exact curve",
    "mulligan_focus": [
      "keep/remove priority tied to this curve",
      "second priority if relevant"
    ],
    "turn_checklist": {
      "T1": "what we must check or avoid",
      "T2": "what we must prepare",
      "T3": "what we must answer"
    },
    "coach_badges": [
      "answer by T4",
      "kill setup",
      "do not overcommit"
    ],
    "user_copy": {
      "short": "1 sentence for collapsed card",
      "expanded": "2-3 sentences for opened coaching panel"
    }
  }
}
```

Valore V3:

- `one_line_hook`: headline nella card curva o nel top threat header.
- `mulligan_focus`: riusabile in Play/Profile senza generare un altro playbook.
- `turn_checklist`: diventa micro-playbook operativo.
- `coach_badges`: rende la UI scansionabile e filtrabile.
- `user_copy.short` / `expanded`: evita riscritture lato frontend o chiamate LLM successive.

Questo blocco deve restare corto. Se diventa un secondo report dentro la KC, aumenta token e peggiora qualita'. Il limite pratico: massimo 3 badge, massimo 3 turni checklist, massimo 2 mulligan focus.

### Self-check LLM: utile, ma non fidato

Si puo' chiedere anche un blocco `self_check`:

```json
{
  "self_check": {
    "curve_specific": true,
    "mentions_key_card": true,
    "response_by_turn": 4,
    "not_generic": true,
    "uses_only_prompt_cards": true
  }
}
```

Questo non sostituisce il validator. Serve per debug, retry e osservabilita'. Se il modello dichiara `not_generic=true` ma il validator trova una response senza carta/turno, il validator vince.

### Come risparmiare davvero

Il risparmio grosso non arriva chiedendo meno campi alla stessa call. Arriva evitando call inutili.

#### 1. `digest_hash`

Salvare in `killer_curves.meta.digest_hash` l'hash del digest normalizzato. Se digest, formato e matchup non cambiano, la KC precedente resta valida.

Regola:

```text
same digest_hash + same prompt_contract_hash + same schema_version = reuse, no LLM call
```

Stato 2026-04-25: implementato `digest_hash`, `prompt_contract_hash` e `schema_version` in `scripts/generate_killer_curves.py`. Nei run non-forzati futuri, se questi tre valori coincidono, la matchup viene saltata prima della call LLM. `--force` continua a rigenerare.

#### 2. `prompt_hash`

Esiste gia' `prompt_hash` in meta. Per la cache e' stato aggiunto anche `prompt_contract_hash`, piu' stabile: non dipende dal digest o dalla data del giorno, ma dal contratto prompt/schema. Se il contratto cambia, rigeneri; se non cambia, puoi riusare.

#### 3. Repair invece di rebuild

Se il problema e' schema v2 mancante, lingua vecchia o campi UI assenti, non rimandare tutto il digest completo. Mandare solo:

- JSON precedente;
- errori validator;
- schema atteso;
- poche istruzioni di correzione.

Questo costa molto meno di una rigenerazione full.

Flusso:

```text
full KC call -> validator fail
  -> repair call con JSON + errori
  -> validator
  -> publish oppure block
```

#### 4. Due livelli di LLM

Non tutti i matchup meritano la stessa spesa.

- Python/SQL decide se il matchup e' stabile o instabile.
- Modello principale solo per matchup instabili o ad alto traffico.
- Modello piu' economico solo per repair leggero o copy non critica, dopo A/B.

Non cambiare modello principale senza A/B: il costo scende, ma se aumenta output povero o retry, il risparmio reale puo' sparire.

#### 5. Priorita' per valore commerciale

Rigenerare prima:

- matchup piu' giocati;
- matchup con piu' loss recenti;
- matchup visibili nella V3 free/pro funnel;
- matchup con KC legacy o response v1;
- matchup dove il validator trova rischio P0/P1.

I matchup stabili e poco visti possono restare cacheati.

### Output LLM ideale per una call KC

Una singola call premium dovrebbe produrre:

- `curves`: sequenze killer;
- `response`: campi v2 completi;
- `v3_payload`: headline, mulligan focus, checklist, badge, copy;
- `self_check`: diagnostica non fidata;
- `metadata`: schema/prompt/digest/model info aggiunti dal sistema, non dal modello.

Il modello non deve produrre dati numerici che il sistema puo' calcolare. Il sistema deve calcolare e validare; il modello deve spiegare e rendere azionabile.

Stato 2026-04-25: `v3_payload` e `self_check` sono stati aggiunti al prompt e allo schema. La generazione salva anche metriche in `killer_curves.meta`: `response_v2_complete`, `v3_payload_complete`, `self_check_complete` e relative percentuali.

## LLM nel Tab Deck: Dove Serve e Dove No

Il tab Deck e' gia' molto deterministico. Oggi legge soprattutto:

- Summary KPI da `deck_summary.js`: WR, giochi, meta share, fitness rank, worst matchup, confidence.
- Matchups da `deck_matchups.js`: righe per opponent, WR, sample, coverage vs killer curves, cards trending.
- Improve helpers da `deck_improve.js`: leak detector, card trend over/under, OTP/OTD structural gap.
- Recommendation engine da `deck_recommendation_engine.js`: add/cut deterministici da response coverage, consensus diff, card_scores e meta_deck.
- Deck Lens da `deck_lens.js`: diff vs consensus, type breakdown, class breakdown via regex.
- Your List da `deck_list_view.js`: lista, edit, compare to pros, suggested add/cut.
- Response coverage da `deck_response_check.js`: quante copie di answer cards sono gia' nella lista.

Quasi tutto questo non va dato al LLM. Il modello non deve decidere WR, ranking, sample, card delta, response coverage o legality. Quelli sono calcoli interni e devono restare tracciabili.

### Dove il LLM puo' aggiungere valore

Il valore vero e' una lettura sintetica di deckbuilding: trasformare i segnali gia' calcolati in una diagnosi breve, chiara e vendibile. Nome operativo: `deck_doctor`.

Output consigliato, generabile a basso volume:

```json
{
  "deck_doctor": {
    "archetype_read": "1-2 sentences on what this deck is trying to do in the current meta",
    "main_leak": {
      "title": "short leak title",
      "evidence": ["observed signal 1", "observed signal 2"],
      "why_it_matters": "plain explanation"
    },
    "top_adjustments": [
      {
        "action": "add|cut|hold",
        "card": "Exact Card Name",
        "qty": 1,
        "reason": "why this adjustment matters",
        "linked_signal": "response_gap|card_score|consensus_diff|otp_otd_gap|killer_curve"
      }
    ],
    "matchup_focus": [
      {
        "opp": "DeckCode",
        "plan": "what this deck should prepare for",
        "watchout": "specific killer curve or failure mode"
      }
    ],
    "pilot_note": "what the player should practice, not what card to buy",
    "confidence_note": "short caveat tied to sample size"
  }
}
```

Questo e' utile in V3 per:

- Summary panel: una riga "Deck Doctor" sopra o sotto i KPI.
- Your List: spiegare perche' gli add/cut suggeriti hanno senso.
- Matchups: dare priorita' a 2-3 matchup da studiare.
- Improve/Profile: trasformare leak e response coverage in un piano di lavoro.

### Input da dare al LLM

Non mandare l'intero blob. Mandare solo un digest compatto creato da Python:

```json
{
  "deck": "AmSa",
  "format": "core",
  "scope": "set11",
  "summary": {
    "wr": 51.2,
    "games": 420,
    "meta_share": 8.4,
    "fitness_rank": 3,
    "worst_matchup": {"opp": "AbE", "wr": 39, "games": 52}
  },
  "coverage_gaps": [
    {
      "opp": "AbE",
      "curve": "Willow draw engine",
      "critical_turn": 4,
      "missing_answers": ["Card A", "Card B"]
    }
  ],
  "card_signals": {
    "overperforming": [{"card": "Card A", "delta_pp": 3.4, "sample": 88}],
    "underperforming": [{"card": "Card B", "delta_pp": -2.8, "sample": 74}]
  },
  "consensus_diff": {
    "adds": [{"card": "Card A", "delta_qty": 2}],
    "cuts": [{"card": "Card B", "delta_qty": 2}]
  },
  "structural_gaps": [
    {"type": "otp_otd", "weaker_side": "OTD", "gap_pp": 12.5}
  ]
}
```

Il LLM riceve evidenze gia' filtrate e ordinate. Non deve cercare pattern nel dataset grezzo.

### Frequenza consigliata

Non generare `deck_doctor` a ogni cambio tab o a ogni edit.

Regole pragmatiche:

- Per consensus deck: rigenera solo se cambia `deck_digest_hash`.
- Per custom deck: genera solo quando l'utente salva la lista o chiede esplicitamente "Analyze my deck".
- Per edit live: restare deterministici con `BuilderStatus`, `ResponseCheck`, `RecommendationEngine`.
- Cache key: `deck_code + format + scope + decklist_hash + digest_hash + prompt_contract_hash + schema_version`.

### Cosa NON deve fare il LLM nel Deck

Non deve:

- inventare add/cut fuori colori;
- inventare carte non in cards DB;
- sostituire `RecommendationEngine.compute()`;
- ricalcolare card_scores;
- decidere sample confidence;
- classificare type/class se regex/cards DB gia' lo fanno;
- fare "ottimizzatore meta" non validato.

La regola e': Python decide, LLM spiega e prioritizza.

### Come collegarlo alle Killer Curves

Il tab Deck usa gia' `killer_curves[].response.cards[]` per response coverage. Se aggiungiamo `v3_payload` alle KC, il Deck puo' riusare:

- `coach_badges` per spiegare coverage gaps;
- `turn_checklist` per matchup focus;
- `mulligan_focus` per pilot note;
- `user_copy.short` per righe compatte nel matchup table.

Questo riduce bisogno di una call Deck separata. La call Deck Doctor deve servire solo per sintesi deck-level cross-matchup.

### Decisione consigliata

Implementare in due livelli:

1. Zero nuova LLM call: arricchire KC con `v3_payload` e farlo consumare dal Deck.
2. Una call settimanale/per-salvataggio: `deck_doctor` compatto per archetype/custom list.

Non fare una call LLM per ogni matchup del Deck tab: sarebbe costoso e ridondante, perche' Play/KC copre gia' il dettaglio matchup.

## Backlog Prioritario di Blindatura

### P0 — Validator unico KC

Creare `pipelines/kc/validator.py` e usarlo in:

- `scripts/generate_killer_curves.py`
- `scripts/kc_spy_canary.py`
- uno script QA manuale tipo `scripts/audit_killer_curves.py`

Checks minimi:

- Deck e formato coerenti.
- Tutte le carte esistono in cards DB.
- `response.cards` nei colori nostri.
- `sequence.plays[].card`, `key_cards`, `combo` nei colori avversario.
- Core legalita' su tutti i riferimenti carta.
- Meta-relevance su tutti i riferimenti carta.
- Campi response v2 required.
- Lingua response EN.
- Nessuna sequence vuota dopo filtri.

### P0 — Gate di pubblicazione

Non basta salvare la riga. Serve distinguere:

- generated
- validated
- synced
- served

Proposta:

- `killer_curves.meta.quality_status = pass|warn|blocked`
- `matchup_reports` copia solo `pass`, oppure copia anche `warn` ma la V3 lo sa.

### P0 — Test sul dato servito

Creare uno smoke test che legge `/api/v1/dashboard-data` e valida il payload effettivo, non solo PG.

Deve fallire se:

- Core contiene carte Infinity.
- Infinity finisce nel blob Core.
- Mancano campi v2.
- `killer_curves` sorgente e `matchup_reports` divergono oltre soglia.

### P1 — Retry automatico GPT su semantic fail

Flusso consigliato:

1. GPT genera JSON.
2. Validator produce lista errori.
3. Se errori P0, retry una volta con solo errori e JSON precedente.
4. Se fallisce ancora, non pubblicare quella matchup.

### P1 — Cache LLM con `digest_hash`

Usare `digest_hash + prompt_contract_hash + schema_version` come chiave di riuso. Se la chiave non cambia, non chiamare LLM.

Campi da aggiungere in `killer_curves.meta`:

- `validator_version`
- `reused_from_run_id`, quando si riusa una KC precedente

Stato:

- `digest_hash`: fatto 2026-04-25
- `prompt_contract_hash`: fatto 2026-04-25
- `schema_version`: fatto 2026-04-25
- skip cache nei run non-forzati: fatto 2026-04-25
- `reused_from_run_id`: aperto

### P1 — Payload V3 nella stessa call

Estendere lo schema KC con `v3_payload`, mantenendolo corto e validabile:

- `one_line_hook`
- `mulligan_focus`
- `turn_checklist`
- `coach_badges`
- `user_copy.short`
- `user_copy.expanded`

Questo aumenta leggermente i token di output, ma puo' eliminare chiamate LLM successive per micro-copy, pre-match coaching e pannelli V3.

Stato:

- prompt KC esteso: fatto 2026-04-25
- schema KC esteso: fatto 2026-04-25
- metriche completezza in `killer_curves.meta`: fatto 2026-04-25
- consumo UI diretto del payload: aperto

### P1 — Deck Doctor cacheato

Creare un digest compatto deck-level e una call LLM opzionale/cacheata:

- input: summary KPI, worst matchups, response gaps, card_signals, consensus_diff, structural_gaps;
- output: `deck_doctor`;
- trigger: batch settimanale per consensus, oppure "Analyze my deck" dopo save custom;
- cache key: `deck_code + format + scope + decklist_hash + digest_hash + prompt_contract_hash + schema_version`.

Non deve sostituire `RecommendationEngine`: deve spiegare e prioritizzare i risultati deterministici.

### P1 — Osservabilita' costi e qualita'

Estendere `kc_cost_report.py` o creare `kc_quality_report.py`:

- costo per run
- costo per formato
- curve per matchup
- v2 coverage
- cards dropped
- stale
- mismatch source/report/blob

### P2 — Ridurre duplicazioni

Unificare:

- deck colors
- alias legacy
- legality helper
- card lookup
- schema version

Oggi questi concetti appaiono in piu' file e questo e' un rischio silenzioso.

## Decisione Pragmatica

Per vendere V3 senza giocarsi fiducia, il minimo non e' "GPT produce belle risposte". Il minimo e':

1. Ogni KC pubblicata deve passare un validator hard.
2. Ogni KC pubblicata deve essere presente nel blob V3 corretto.
3. Ogni "How to Respond" deve essere v2 completo o non va mostrato come contenuto premium principale.
4. Core e Infinity devono essere controllati nel dato servito, non solo nel dato generato.

La pipeline e' vicina, ma oggi la blindatura critica sta soprattutto nel trasformare i controlli da "prompt + cleanup" a "contratto + gate di pubblicazione".
