# UX Information Architecture Proposal

Data: 2026-04-16
Stato: draft operativo — review Claude 16/04/2026
Owner attuale: Codex + Claude
Note review: vedi §13 per appunti post-review

## 1. Problema

La dashboard attuale e' molto potente, ma espone nello stesso piano:

- contenuti decisionali semplici per casual / ladder player
- contenuti analitici intermedi per player competitivi
- strumenti profondi da analyst / team / grinder

Questo crea tre problemi UX:

1. overload cognitivo
   - un utente non pro puo' aprire `Coach` e trovarsi subito davanti a concetti come `killer curves`, `OTP/OTD`, `IWD`, `consensus vs player diff`

2. tassonomia orientata al sistema, non al compito
   - `Monitor`, `Coach`, `Lab`, `Profile`, `Team` riflettono come abbiamo costruito il prodotto, non la domanda reale dell'utente

3. mismatch tra maturita' utente e densita' dati
   - lo stesso layout serve casual player, competitive player e pro/team without adaptation

## 2. Obiettivo

Riorganizzare la SPA in una struttura piu' leggibile, orientata ai compiti, con progressive disclosure della complessita'.

Non vogliamo:

- duplicare tutto in due prodotti
- perdere i tool avanzati
- spezzare i contratti backend esistenti

Vogliamo invece:

- mostrare prima il livello corretto di informazione
- relegare il deep analysis a un livello esplicito
- rendere l'app utilizzabile anche da chi non conosce il gergo competitivo

## 3. Principio guida

La navigazione primaria deve rispondere a domande utente, non a categorie tecniche del codebase.

Ogni tab deve rispondere a una sola domanda dominante:

1. `Home` -> Cosa devo fare oggi?
2. `Play` -> Come gioco questo matchup?
3. `Meta` -> Cosa mi aspetto dal field?
4. `Deck` -> Come miglioro la mia lista?
5. `Improve` -> Dove sto sbagliando?
6. `Pro Tools` -> Quali analisi profonde mi servono?
7. `Community` -> Cosa succede nella community?
8. `Events` -> Dove gioco?

## 4. Mappa finale proposta

### 4.1 Home

Domanda:
- Cosa faccio oggi?

Target:
- tutti

Contenuti:
- deck attivo
- 3 matchup prioritari
- mulligan tip rapido
- 2 minacce da ricordare
- 1 replay consigliato
- 1 alert meta
- CTA chiare verso `Play`, `Meta`, `Deck`

Da evitare:
- chart dense
- matrix
- tool da analyst

Tono:
- zero jargon o quasi

### 4.2 Play

Domanda:
- Come gioco questo matchup?

Target:
- casual
- ladder player
- torneo locale
- competitive che vuole una vista operativa

Contenuti:
- matchup overview
- mulligan
- game plan per turni
- top threats
- do / don't
- best plays
- replay guidato

Advanced ma collassato:
- OTP/OTD dettagliato
- curve piu' tecniche
- linee molto granulari

Nota:
- questo e' il successore naturale di `Coach`, ma in versione piu' task-oriented

### 4.3 Meta

Domanda:
- Cosa mi aspetto dal field?

Target:
- tutti

Contenuti:
- meta share
- deck fitness semplificato
- top deck del momento
- emerging / rogue
- matchup matrix light

Advanced ma collassato:
- matrix completa
- leaderboard deep
- tech tornado completo

Nota:
- questo e' il successore naturale di `Monitor`

### 4.4 Deck

Domanda:
- Come miglioro la mia lista?

Target:
- tutti
- soprattutto competitive

Contenuti:
- consensus list
- my deck vs consensus
- tech cards
- curve
- optimized list
- card impact base

Nota:
- qui ha senso il linguaggio deckbuilding
- qui vanno concentrate le funzioni attuali sparse tra `Profile` e `Lab`

### 4.5 Improve

Domanda:
- Dove sto sbagliando?

Target:
- competitive player

Contenuti:
- my stats
- trend personale
- matchup studiati
- progress tracker
- misplay / error detection
- replay review personale

Nota:
- e' la vera area di coaching personale
- non serve mostrarla prominente al casual

### 4.6 Pro Tools

Domanda:
- Quali analisi profonde mi servono?

Target:
- pro
- tester
- grinder
- team

Contenuti:
- killer curves
- OTP/OTD deep
- IWD / card impact avanzato
- tech tornado full
- matrix completa
- board lab
- team analytics
- gz replay tooling

Nota:
- qui possiamo essere tecnici senza paura
- il problema attuale non e' l'esistenza di questi strumenti, ma il fatto che compaiano troppo presto

### 4.7 Community

Mantenerlo quasi invariato:

- live
- clip
- VOD

### 4.8 Events

Mantenerlo quasi invariato:

- tornei
- mappa
- submit evento

## 5. Vista per persona

La stessa IA puo' essere adattata con un `persona mode` semplice.

### 5.1 Casual

Mostrare:
- Home
- Play
- Meta
- Deck
- Community
- Events

Nascondere o tenere secondario:
- Improve
- Pro Tools

### 5.2 Competitive

Mostrare:
- Home
- Play
- Meta
- Deck
- Improve
- Community
- Events

Secondario:
- Pro Tools

### 5.3 Pro / Team

Mostrare tutto:
- Home
- Play
- Meta
- Deck
- Improve
- Pro Tools
- Community
- Events

## 6. Mapping dai tab attuali

### 6.1 Profile

Oggi contiene troppa roba mista:

- deck selection
- radar/meta
- standard list
- tech picks
- best plays
- coaching angle
- stats personali

Nuova destinazione:

- `Home`
  - deck attivo
  - alert e priorita'
- `Deck`
  - consensus list
  - tech
  - curve
- `Improve`
  - stats personali
  - progress

### 6.2 Monitor

Nuova destinazione:

- `Meta`
  - meta share
  - deck fitness
  - matrix light
  - rogue / emerging

- `Pro Tools`
  - matrix full
  - leaderboard deep
  - tech tornado avanzato

### 6.3 Coach_v2

Nuova destinazione:

- `Play`
  - matchup overview
  - mulligan
  - game plan
  - threats
  - guided replay

- `Pro Tools`
  - killer curves
  - OTP/OTD deep

### 6.4 Lab

Nuova destinazione:

- `Deck`
  - optimizer
  - deck comparison
  - card impact base

- `Pro Tools`
  - IWD
  - deep impact analysis
  - board lab tecnico

### 6.5 Team

Nuova destinazione:

- `Pro Tools`
  - team coverage
  - lineup
  - training dashboard

Alternativa:
- tenerlo separato solo in persona mode `Pro / Team`

### 6.6 Community

Resta:
- `Community`

### 6.7 Events

Resta:
- `Events`

## 7. UX rules non-negoziabili

### 7.1 Progressive disclosure

Le metriche avanzate non devono stare nel primo viewport dei tab generalisti.

Prima:
- summary
- recommendation
- action

Poi:
- analysis
- advanced analysis

### 7.2 Glossario inline

Termini come:

- killer curve
- OTP
- OTD
- IWD
- consensus
- tech tornado

devono avere:

- info icon
- tooltip breve
- microcopy leggibile

### 7.3 Complexity gating

I contenuti devono cambiare per:

- ordine
- apertura default
- density

non necessariamente per disponibilita' backend.

### 7.4 No silent jargon in primary views

In `Home`, `Play`, `Meta` evitare che la UI primaria usi parole comprensibili solo a tester/grinder.

### 7.5 Decision-first

Ogni vista primaria deve dire prima:

- cosa fare

e solo dopo:

- perche'
- quali metriche lo supportano

## 8. Proposta di nav finale

### 8.1 Nav Casual

Ordine:

1. Home
2. Play
3. Meta
4. Deck
5. Community
6. Events

### 8.2 Nav Competitive

Ordine:

1. Home
2. Play
3. Meta
4. Deck
5. Improve
6. Community
7. Events

### 8.3 Nav Pro / Team

Ordine:

1. Home
2. Play
3. Meta
4. Deck
5. Improve
6. Pro Tools
7. Community
8. Events

## 9. Strategia di implementazione consigliata

Non riscrivere tutto in una volta.

### Fase 1 — soft IA

Obiettivo:
- cambiare etichette e raggruppamenti senza cambiare i contratti backend

Azioni:
- rinominare i tab
- spostare blocchi esistenti sotto nuovi contenitori
- collassare le sezioni avanzate
- introdurre microcopy orientata al compito

Rischio:
- basso

### Fase 2 — persona mode

Obiettivo:
- cambiare ordine e visibilita' dei tab in base al profilo utente

Azioni:
- toggle `Casual / Competitive / Pro`
- default per tier o preference utente
- show/hide di `Improve` e `Pro Tools`

Rischio:
- medio-basso

### Fase 3 — home reale

Obiettivo:
- creare una vera dashboard `Home` orientata all'azione

Azioni:
- aggregare moduli da Profile / Coach / Monitor
- costruire CTA chiare
- introdurre una daily brief

Rischio:
- medio

### Fase 4 — estrazione tecnica

Obiettivo:
- smettere di far vivere tutto dentro `frontend/dashboard.html`

Azioni:
- estrarre modulo per tab
- separare nav model, persona model e section registry

Rischio:
- medio-alto

## 10. Raccomandazioni pratiche per Claude

Quando raffini questo documento:

1. non trasformarlo in una teoria astratta
   - mantieni mapping concreto dai tab attuali

2. distingui chiaramente:
   - naming UX
   - IA
   - rollout tecnico

3. non proporre split troppo ambiziosi nel primo step
   - la prima iterazione deve essere fattibile sopra il frontend attuale

4. conserva i tool avanzati
   - il problema non e' rimuoverli, ma posizionarli meglio

5. privilegia:
   - reorder
   - collapse
   - relabel
   - summary cards
   rispetto a refactor massivi immediati

## 11. Deliverable atteso da Claude

Claude dovrebbe produrre una versione raffinata di questo piano con:

1. mappa finale confermata
2. elenco sezioni esistenti da spostare per tab
3. proposta di nav desktop e mobile
4. suggerimento di rollout in 2-3 milestone
5. note sui rischi di regressione UX

## 12. Decisione consigliata

Raccomandazione finale:

- adottare la mappa `Home / Play / Meta / Deck / Improve / Pro Tools / Community / Events`
- introdurre persona mode in seconda battuta
- considerare `Play`, `Meta`, `Deck` come nucleo stabile del prodotto
- relegare `killer curves`, `IWD`, `team coverage`, `board lab` in `Pro Tools`

Questa soluzione massimizza:

- leggibilita' per casual
- continuita' per competitive
- potenza per pro/team

senza buttare via il lavoro backend gia' fatto.

## 13. Appunti review Claude (16/04/2026)

### Condivisi

L'analisi e' solida. Il problema e' reale, i principi sono corretti, il mapping §6 e' concreto. Progressive disclosure + relabel + collapse e' il primo step giusto a rischio zero.

### Calibrazioni

**8 tab sono troppi per mobile.** Su iPhone ci stanno 5 icone nella tab bar. Proposta ridotta:

| Tab | Contenuto | Note |
|-----|-----------|------|
| **Home** | Daily brief, deck attivo, CTA | Fase 3 (non Fase 1) |
| **Play** | Matchup coaching operativo | Ex Coach V2 |
| **Meta** | Meta share, fitness, emerging, matrix | Ex Monitor |
| **Deck** | Lista, optimizer, comparatore, card impact | Ex Lab + pezzi Profile |
| **Pro** | KC, IWD deep, board lab, team, tech tornado full | Power tools |
| **More** | Community + Events + Profile settings | Hamburger o tab secondario |

Questo da' 5 tab primari + 1 overflow. Home puo' essere landing di default oppure il tab Meta se Home non e' pronta.

**Persona mode: rischio moltiplicatore.** Un toggle che nasconde tab e' semplice (CSS `display:none`). Ma se il persona mode cambia anche il contenuto _dentro_ i tab (ordine sezioni, default apertura accordion, densita' KPI) diventa un moltiplicatore di complessita' 3x. Consiglio: Fase 1 senza persona mode. Fase 2 solo show/hide tab. Fase 3 se serve davvero, adattamento contenuto.

**Home e' Fase 3, non Fase 1.** Richiede aggregazione dati da piu' fonti (deck attivo + matchup prioritari + alert meta + replay). Non blocca il restyling. Prima si rinomina e riordina, poi si costruisce Home quando il layout e' stabile.

**Fase 4 (estrazione moduli da dashboard.html) e' corretta ma non urgente.** 10.6K LOC in un file funzionano finche' il prodotto e' in beta con utente singolo. Il split in moduli ha senso solo quando: (a) piu' sviluppatori toccano il frontend in parallelo, oppure (b) serve un framework/build step. Per ora vanilla JS monolite va bene.

### Fase 1 concreta (fattibile in 1 sessione, ~2h)

1. **Rinominare tab**: Monitor -> Meta, Coach -> Play, Lab -> Deck
2. **Spostare** consensus list + tech picks + deck comparatore da Profile/Lab dentro Deck
3. **Collassare** killer curves, IWD, tech tornado avanzato sotto accordion "Advanced" nei rispettivi tab
4. **Aggiungere** microcopy + tooltip (`?` button pattern gia' esistente) sui termini: killer curve, OTP, OTD, IWD, consensus, tech tornado
5. **Profile** diventa: deck selector + my stats + saved decks (piu' leggero)
6. **Non toccare** backend, endpoint, blob structure

### Rischi di regressione UX

- Cross-tab navigation (click matrix cell -> Coach) deve aggiornare i nomi tab nel codice JS
- Deep link / bookmark utente se qualcuno ha salvato `#coach` -> va in 404 concettuale
- Il pattern `monAccordion` e' retrocompatibile, nessun rischio li'
- Service worker cache puo' servire vecchio HTML -> bump versione SW ad ogni rename
