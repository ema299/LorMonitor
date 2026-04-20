# Frontend V2 Architecture

Data: 2026-04-20
Stato: draft operativo
Owner: Codex

## 1. Obiettivo

Costruire un nuovo frontend in parallelo al prodotto live senza sporcare il frontend attuale, senza modificare `ARCHITECTURE.md`, e senza introdurre accoppiamenti confusi tra vecchia e nuova UI.

Il principio chiave e' semplice:

- `frontend/` resta il legacy live
- `frontend_v2/` diventa il nuovo frontend
- backend e API restano condivisi
- i due frontend non devono condividere file applicativi

## 2. Vincoli non negoziabili

- Non modificare `ARCHITECTURE.md`
- Non toccare `.py` in `lib/`
- Non rompere il frontend live
- Non fare refactor architetturali del backend per inseguire la nuova UI
- Non condividere JS/CSS applicativi tra legacy e v2

## 3. Target State

### 3.1 Legacy

`frontend/` deve diventare un blocco stabile e autosufficiente.

Deve contenere:

- la UI live attuale
- i suoi asset statici
- i suoi script
- i suoi riferimenti locali
- le sue dipendenze documentate

Non deve dipendere da file futuri di `frontend_v2/`.

### 3.2 V2

`frontend_v2/` deve essere un frontend autonomo.

Deve contenere:

- entry HTML propria
- asset CSS propri
- asset JS propri
- eventuale manifest proprio
- eventuale service worker proprio, solo se davvero serve

La v2 puo' chiamare le stesse API del backend live, ma non deve importare file dal legacy.

## 4. Boundary Rules

Queste regole servono a evitare confusione.

### 4.1 Cosa puo' essere condiviso

- endpoint backend
- contratti JSON API
- dati live
- autenticazione/cookie se gia' esistenti
- deck icons o asset statici solo se deliberatamente duplicati o resi shared in una fase successiva

### 4.2 Cosa non va condiviso

- `dashboard.html`
- `assets/js/*.js` applicativi
- `assets/css/*.css` applicativi
- inizializzazione UI
- tab routing
- logica di rendering
- file di supporto creati per il redesign

### 4.3 Regola sui path

Nel nuovo frontend non sono ammessi riferimenti che puntano implicitamente al legacy.

Esempi da evitare:

- path assoluti tipo `/assets/js/...` se servono file della v1
- import o script tag che caricano file da `frontend/`
- fallback che cambiano comportamento tra v1 e v2 in modo invisibile

## 5. Stato attuale del frontend live

Oggi il frontend live e' servito da `frontend/`.

Osservazioni concrete dal repo:

- `/` e `/dashboard.html` servono `frontend/dashboard.html`
- gli statici montati dal backend puntano a `frontend/`
- `frontend_v2/` esiste su disco ma non e' ancora esposta
- `frontend/dashboard.html` carica almeno uno script con path assoluto: `/assets/js/team_coaching.js`

Questo implica che una semplice copia cartella non garantisce isolamento reale se la v2 viene esposta sotto un path diverso ma continua a usare asset assoluti del legacy.

## 6. Strategia architetturale

La strategia corretta e' in due tempi.

### 6.1 Prima: seal del legacy

Prima di progettare la nuova UI, il frontend attuale va "chiuso".

Significa:

- mappare tutte le dipendenze del live
- eliminare riferimenti ambigui
- rendere espliciti asset e script usati dal legacy
- evitare che futuri cambi su JS/CSS impattino sia v1 sia v2

Output atteso:

- `frontend/` stabile
- blast radius ridotto
- base chiara per il cutover futuro

### 6.2 Poi: build della v2

La v2 nasce come frontend separato, non come patch della v1.

Linee guida:

- una entry HTML v2
- un set CSS v2
- un set JS v2
- un layer API v2 esplicito
- nessuna dipendenza file-to-file dal legacy

## 7. Struttura proposta

Struttura minima consigliata:

```text
frontend/
  dashboard.html
  assets/
    css/
    js/
  chart.min.js
  manifest.json
  sw.js

frontend_v2/
  index.html
  assets/
    css/
      app.css
    js/
      app.js
      api.js
      tabs/
      components/
      views/
  icons/
  manifest.json
  sw.js
```

Note:

- `frontend/` e `frontend_v2/` devono poter evolvere separatamente
- se un file del legacy serve anche alla v2, va copiato in v2 nella prima fase
- solo dopo stabilizzazione si puo' valutare una cartella shared, se davvero conviene

## 8. Dependency Policy

### 8.1 Legacy policy

Per il legacy valgono queste regole:

- niente nuovi accoppiamenti con `frontend_v2/`
- niente spostamento di file dal legacy alla v2
- niente "riuso rapido" di JS/CSS della v2
- bugfix solo mirati e conservativi

### 8.2 V2 policy

Per la v2 valgono queste regole:

- ogni script nuovo nasce in `frontend_v2/`
- ogni stile nuovo nasce in `frontend_v2/`
- ogni componente nuovo nasce in `frontend_v2/`
- ogni modifica visuale nuova va fatta solo li'

## 9. Sequenza di lavoro

### Step 1. Audit legacy

Mappare:

- script caricati da `dashboard.html`
- CSS usati dal live
- endpoint chiamati dal live
- key `localStorage`
- asset statici
- eventuali path assoluti da correggere

Deliverable:

- dependency map del frontend live

### Step 2. Seal legacy

Interventi possibili:

- rendere relativi o espliciti i path critici del live
- congelare le dipendenze applicative
- decidere cosa e' parte del contratto del frontend legacy

Deliverable:

- legacy autosufficiente

### Step 3. Scaffold v2

Creare base pulita per il nuovo frontend:

- entrypoint HTML
- shell CSS
- app bootstrap JS
- API layer v2
- convenzioni di cartelle

Deliverable:

- v2 pronta per sviluppo UI

### Step 4. Restyling e nuova IA

Solo qui si implementano:

- nuova navigazione
- nuove tab
- progressive disclosure
- nuova gerarchia informativa
- nuovo visual system

Deliverable:

- nuovo frontend senza impatto sul live

### Step 5. Cutover

Quando la v2 e' pronta:

- si decide come esporla
- si testa con utenti selezionati
- si pianifica il passaggio dal legacy alla v2

## 10. Cosa non fare

- non fare restyling dentro `frontend/`
- non usare `frontend_v2/` come copia che continua a pescare asset dalla v1
- non condividere `team_coaching.js` o altri file applicativi "temporaneamente"
- non fare il refactor completo del backend per cambiare nome ai tab
- non mischiare fix legacy e redesign nello stesso sprint

## 11. Decisione operativa

La decisione corretta e':

- `frontend/` = prodotto attuale da chiudere e stabilizzare
- `frontend_v2/` = prodotto nuovo da progettare e costruire

Il prossimo lavoro non e' ancora il redesign.

Il prossimo lavoro e':

- audit dipendenze del legacy
- definizione del perimetro autonomo del live
- scaffold pulito della v2

Solo dopo si passa al restyling.
