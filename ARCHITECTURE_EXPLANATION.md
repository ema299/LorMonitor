# Lorcana Monitor — Architettura Spiegata

**Per chi:** chi conosce Python ma non infrastruttura web, database, sicurezza o deployment.
**Obiettivo:** capire COSA fa ogni pezzo, PERCHE' serve, e COME si collega al resto.

---

## Il Quadro Generale

Oggi hai uno script Python che legge file JSON e genera una pagina HTML. Funziona per te. Ma non puo' servire 100 utenti che pagano.

La nuova architettura prende lo stesso contenuto (killer curves, matchup analysis, dashboard) e lo serve come un servizio web professionale: con login, pagamento, sicurezza, e la garanzia che se qualcosa si rompe non perdi i dati.

```
OGGI:
  File JSON → Script Python → Un file HTML enorme → Lo apri nel browser

DOMANI:
  Database → Server Python → API → Pagina web leggera → Login → Pagamento
```

---

## I Pezzi dell'Architettura

Immagina un ristorante:

```
RISTORANTE = LA TUA APP

  Porta d'ingresso (nginx)     = Il cameriere che accoglie
  Sala (Frontend)              = I tavoli dove si siedono i clienti
  Cucina (Backend FastAPI)     = Dove si preparano i piatti
  Frigorifero (PostgreSQL)     = Dove sono conservati gli ingredienti
  Dispensa veloce (Redis)      = Il bancone con le cose pronte
  Fornitore notturno (Pipeline)= Chi rifornisce il frigo di notte
  Chef speciale (LLM Worker)   = Lo chef che prepara i piatti elaborati
  Cassaforte (Backup)          = La copia di tutto in un posto sicuro
  Registratore di cassa (Stripe)= Chi gestisce i pagamenti
```

Ora vediamo ogni pezzo nel dettaglio.

---

## nginx — La Porta d'Ingresso

### Cos'e'
nginx (si pronuncia "engine-x") e' un programma che riceve TUTTE le richieste da internet e decide cosa farne. E' l'unica cosa visibile dall'esterno.

### Perche' serve
Il tuo script Python (FastAPI) non dovrebbe parlare direttamente con internet. E' come far rispondere il cuoco al telefono — funziona, ma non e' il suo lavoro. nginx fa il lavoro sporco:

**1. HTTPS (il lucchetto nel browser)**
Quando visiti un sito e vedi il lucchetto, significa che la connessione e' criptata. Nessuno puo' leggere cosa stai facendo (password, dati carte, etc.). nginx gestisce questa criptazione usando un certificato SSL gratuito di Let's Encrypt.

Senza HTTPS:
```
Tu ---"password123"--→ Internet (tutti possono leggere) --→ Server
```

Con HTTPS:
```
Tu ---"x7$kQ2m..."---→ Internet (incomprensibile) --→ Server (decripta)
```

**2. Rate limiting (protezione da abuso)**
Se qualcuno manda 10.000 richieste al secondo per far crashare il server, nginx lo blocca. "Massimo 100 richieste al minuto per IP" — oltre quel limite, risponde "429 Too Many Requests" senza disturbare il backend.

**3. Routing (smistamento)**
```
Richiesta per /dashboard.html → nginx serve il file direttamente (velocissimo)
Richiesta per /api/v1/...     → nginx la inoltra a FastAPI (che calcola la risposta)
```

**4. Compressione (gzip)**
I dati JSON possono essere grossi. nginx li comprime prima di inviarli — il browser li decomprime automaticamente. Risultato: meno banda, pagina piu' veloce.

### In pratica
nginx e' un programma che gira sempre sul server. Lo configuri una volta con un file di testo, e lui fa il suo lavoro 24/7. Gestisce migliaia di connessioni simultanee con pochissima RAM.

---

## FastAPI — La Cucina

### Cos'e'
FastAPI e' un framework Python (come Flask, ma piu' moderno) per creare API web. Un'API e' un "menu": il frontend chiede "dammi le killer curves di AmAm vs ES" e il backend risponde con i dati in formato JSON.

### Perche' FastAPI e non Flask
- Piu' veloce (asincrono, gestisce piu' richieste contemporaneamente)
- Validazione automatica dei dati (se mandi un numero dove serve una stringa, ti dice l'errore)
- Documentazione automatica (genera una pagina di test per tutte le API)
- Type hints Python nativi (scrivi codice piu' pulito)

### Come funziona

```python
# Esempio semplificato di un endpoint

from fastapi import FastAPI, Depends

app = FastAPI()

@app.get("/api/v1/coach/killer-curves/{our}/{opp}")
async def get_killer_curves(our: str, opp: str, user = Depends(get_current_user)):
    # 1. Verifica che l'utente sia loggato (Depends fa il check automatico)
    # 2. Verifica che sia Pro (altrimenti errore 403)
    # 3. Cerca in cache Redis
    # 4. Se non c'e', query PostgreSQL
    # 5. Ritorna JSON
    curves = await db.fetch_killer_curves(our, opp)
    return {"curves": curves}
```

Il decoratore `@app.get(...)` dice: "quando qualcuno chiede GET su questo URL, esegui questa funzione". `Depends(get_current_user)` e' un meccanismo di FastAPI che automaticamente controlla il token di login prima di eseguire la funzione.

### uvicorn
FastAPI ha bisogno di un "server" che lo faccia girare. uvicorn e' quel server. In produzione lo lanci con 4 "worker" — cioe' 4 copie del tuo programma Python che lavorano in parallelo. Se un utente sta aspettando una risposta lenta, gli altri 3 worker servono gli altri utenti.

```bash
uvicorn main:app --workers 4 --port 8000
```

---

## PostgreSQL — Il Frigorifero

### Cos'e'
PostgreSQL e' un database. Prende i tuoi dati (match, utenti, killer curves) e li salva in modo strutturato, con indici che permettono ricerche velocissime.

### Perche' serve (non bastano i file JSON?)
Oggi hai 64.000 file JSON in una cartella. Per trovare "tutti i match AmAm vs ES degli ultimi 2 giorni" devi:
1. Aprire tutti i 64.000 file
2. Leggere il contenuto di ognuno
3. Filtrare quelli che corrispondono

Tempo: **~22 secondi**.

Con PostgreSQL i dati sono in una tabella con indici (come l'indice di un libro). La stessa ricerca:

```sql
SELECT * FROM matches
WHERE deck_a = 'AmAm' AND deck_b = 'ES'
AND played_at >= now() - INTERVAL '2 days';
```

Tempo: **<50 millisecondi**. Cioe' 400 volte piu' veloce.

### Come funziona (spiegazione semplice)
Pensa a un foglio Excel enorme:

```
| id  | data       | deck_a | deck_b | winner | turni (JSON) |
|-----|------------|--------|--------|--------|--------------|
| 1   | 2026-03-27 | AmAm   | ES     | deck_a | [{T1: ...}]  |
| 2   | 2026-03-27 | AbSt   | AS     | deck_b | [{T1: ...}]  |
| ... | ...        | ...    | ...    | ...    | ...          |
```

L'"indice" e' come un segnalibro: PostgreSQL sa che tutti i match "AmAm vs ES" sono in queste posizioni, e ci va direttamente senza scorrere tutto.

La colonna "turni" contiene JSON dentro il database (si chiama JSONB). Quindi puoi avere sia dati strutturati (deck_a, deck_b, data) sia dati flessibili (i turni con tutti i dettagli). Il meglio dei due mondi.

### Perche' non MongoDB
MongoDB e' un database specializzato per documenti JSON. Sembra perfetto per i tuoi match JSON, ma:

1. **Hai anche dati relazionali**: utenti, abbonamenti, pagamenti. Questi dati hanno relazioni ("l'utente X ha l'abbonamento Y"). PostgreSQL gestisce relazioni nativamente. MongoDB no — dovresti fare workaround nel codice.

2. **Le query piu' importanti sono SQL**: "win rate per deck", "matrice matchup", "trend 7 giorni". Queste sono somme e conteggi — SQL le fa in una riga. MongoDB richiede "aggregation pipeline" — funziona ma e' piu' complesso.

3. **Un servizio in meno**: PostgreSQL e' gia' installabile con `apt install`. MongoDB richiede un repository esterno, un processo separato, altra configurazione. Meno cose girano, meno cose si rompono.

4. **PostgreSQL ha JSONB**: puoi salvare JSON dentro PostgreSQL e fare query sui campi annidati. Non e' veloce quanto MongoDB per query JSON complesse, ma per il tuo caso e' piu' che sufficiente.

---

## Redis — La Dispensa Veloce

### Cos'e'
Redis e' un database che vive interamente in RAM (la memoria veloce del computer). E' velocissimo ma non persistente — se si spegne, perde tutto. Per questo si usa come cache, non come storage primario.

### Perche' serve
Immagina che 50 utenti chiedano la stessa cosa: "matrice matchup core, ultimo 2 giorni". Senza cache, il server fa 50 query identiche a PostgreSQL. Con Redis:

```
Utente 1 chiede la matrice
  → Redis: "ce l'ho?" → NO
  → PostgreSQL: calcola (50ms)
  → Salva in Redis (TTL 1 ora)
  → Ritorna all'utente

Utente 2-50 chiedono la matrice
  → Redis: "ce l'ho?" → SI (5ms)
  → Ritorna subito, senza toccare PostgreSQL
```

### E se Redis muore?
Il sistema funziona lo stesso. FastAPI nota che Redis non risponde e va direttamente a PostgreSQL. Piu' lento, ma funziona. Redis e' un'ottimizzazione, non un requisito.

---

## Autenticazione — Chi Sei

### Il Problema
Quando un utente apre il browser e va su lorcanamonitor.com, il server non sa chi e'. Potrebbe essere un utente pro, un utente free, o un estraneo. Serve un sistema per identificarlo.

### Come Funziona (JWT)

JWT (JSON Web Token) e' come un badge di ingresso:

```
1. REGISTRAZIONE (una sola volta)
   Utente manda: email + password
   Server:
     - Controlla che l'email non esista gia'
     - Prende la password e la "hasha" (la trasforma in modo irreversibile)
       "password123" → "$2b$12$xKqV8..." (non puoi tornare indietro)
     - Salva email + hash nel database
     - Ritorna: "OK, sei registrato"

2. LOGIN
   Utente manda: email + password
   Server:
     - Trova l'utente per email
     - Hasha la password ricevuta e la confronta con quella salvata
     - Se corrispondono: genera un TOKEN (una stringa lunga)
       Il token contiene: {user_id: "abc", tier: "pro", scade: "tra 15 min"}
       Firmato con una chiave segreta (solo il server la conosce)
     - Ritorna il token all'utente

3. OGNI RICHIESTA SUCCESSIVA
   Il browser manda il token nell'header:
     Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR...

   Il server:
     - Verifica la firma (e' stato generato da me? non e' scaduto?)
     - Estrae user_id e tier
     - Sa chi e' l'utente e cosa puo' fare
     - Non deve MAI consultare il database per questo check (velocissimo)
```

### Perche' il token dura solo 15 minuti?
Se qualcuno ruba il token (malware, Wi-Fi pubblico), puo' usarlo per impersonarti. Ma solo per 15 minuti. Dopo, scade e serve il "refresh token" — un secondo token con durata lunga (30 giorni) che serve SOLO per ottenere un nuovo access token. Il refresh token e' salvato nel database e puo' essere revocato (logout = revoca il refresh token).

### Perche' bcrypt e non salvare la password direttamente?
Se qualcuno ruba il database (succede — data breach), trova solo hash:
```
email: mario@example.com
password_hash: $2b$12$xKqV8nP3r2Z5... (inutilizzabile)
```

Non puo' risalire alla password originale. bcrypt e' progettato per essere LENTO (~250ms per tentativo). Un attaccante che prova 1 miliardo di password impiegherebbe migliaia di anni.

---

## Autorizzazione — Cosa Puoi Fare

### Tier (livelli)
```
free  → Vede solo il meta community, killer curves limitate
pro   → Vede tutto: tutti i perimetri, coach, lab, storico
team  → Come pro + team training + 5 account
admin → Puo' triggerare pipeline, vedere log, gestire tutto
```

### Come funziona nel codice
Ogni endpoint dichiara il livello minimo:

```python
# Questo endpoint richiede almeno "pro"
@router.get("/killer-curves/{our}/{opp}")
async def get_killer_curves(our: str, opp: str, user = Depends(require_tier("pro"))):
    # Se l'utente e' free, FastAPI ritorna automaticamente:
    # 403 Forbidden: {"error": "upgrade_required", "required_tier": "pro"}
    # Se e' pro o team, prosegue normalmente
    ...
```

### Data isolation
L'utente puo' vedere e modificare solo i SUOI dati. Il `user_id` viene estratto dal token JWT server-side — l'utente non puo' falsificarlo. Se Mario chiede i deck di Luigi, il server risponde "non autorizzato".

---

## Stripe — I Pagamenti

### Cos'e'
Stripe e' un servizio che gestisce i pagamenti online. Tu non tocchi MAI i numeri delle carte di credito — Stripe li gestisce per te. Questo ti rende conforme a PCI DSS (lo standard di sicurezza per i pagamenti) senza dover fare nulla.

### Come funziona il pagamento

```
1. L'utente clicca "Upgrade to Pro" nella tua app

2. Il tuo server crea una "Checkout Session" su Stripe:
   "Questo utente vuole pagare 12 EUR/mese per il piano Pro"

3. Stripe ti da un URL (es. https://checkout.stripe.com/abc123)

4. L'utente viene mandato su quella pagina di Stripe
   - Vede il form di pagamento (carta, Apple Pay, Google Pay)
   - I dati della carta vanno DIRETTAMENTE a Stripe
   - Il tuo server non vede MAI il numero della carta

5. L'utente paga

6. Stripe manda un "webhook" al tuo server:
   - Un webhook e' una richiesta HTTP che Stripe fa al TUO server
   - Dice: "L'utente X ha pagato per il piano Pro"
   - Il tuo server aggiorna il database: user.tier = 'pro'
```

### Apple Pay e Google Pay
Sono gia' inclusi in Stripe. Non devi scrivere codice extra. Quando l'utente apre la pagina Stripe su iPhone, vede il bottone Apple Pay automaticamente. Su Android vede Google Pay. Li abiliti con un click nel dashboard Stripe.

### Rinnovo automatico
Ogni mese Stripe prova ad addebitare la carta. Se il pagamento va a buon fine, manda un webhook "invoice.paid" e tu rinnovi. Se fallisce 3 volte, manda "customer.subscription.deleted" e tu riporti l'utente al tier free.

### Sicurezza
- **I numeri carta non passano mai dal tuo server** (pagina Stripe hosted)
- **I webhook hanno una firma crittografica** — il tuo server verifica che il messaggio arrivi davvero da Stripe e non da un impostare
- **Stripe Radar** (incluso gratis) usa machine learning per bloccare carte rubate

---

## Backup — La Cassaforte

### Il Problema
I dati sono la cosa piu' preziosa. Se il disco si rompe, se il server prende fuoco, se fai un errore e cancelli una tabella — devi poter tornare indietro.

### La Regola 3-2-1
```
3 copie dei dati:
  1. Il database live (sul server)
  2. Una copia locale compressa (sullo stesso server, disco diverso)
  3. Una copia remota criptata (in un altro datacenter)

2 supporti diversi:
  - SSD del server (veloce, piccolo)
  - HDD del backup remoto (lento, grande, economico)

1 copia fuori sede:
  - Se il datacenter del server brucia, la copia remota e' salva
```

### Come funziona in pratica
Ogni notte alle 3:00, uno script automatico:

```
1. Prende tutto il database PostgreSQL e lo "dumpa" in un file
   (come fare un export di un foglio Excel)

2. Cripta il file con una password (GPG, AES-256)
   Anche se qualcuno ruba il file, non puo' leggerlo

3. Lo copia su un server di backup remoto (Hetzner Storage Box, 3 EUR/mese)

4. Cancella i backup vecchi (tiene solo gli ultimi 7 giorni)
```

### Scenari di Recovery

**"Il processo si e' bloccato"**
→ systemd (il gestore servizi di Linux) lo riavvia in 5 secondi. Automatico.

**"Il database si e' corrotto"**
→ Ricarichi l'ultimo backup: `pg_restore -d lorcana backup.dump`. 15 minuti.

**"Il server e' morto"**
→ Crei un nuovo server Hetzner, monti il disco (che sopravvive), scarichi il backup, installi tutto da Git. 30-60 minuti.

**"Le killer curves sono sbagliate"**
→ In PostgreSQL tieni tutte le versioni precedenti. Torni a quella di ieri con una query.

---

## Logging — Il Diario

### Cos'e'
Ogni volta che succede qualcosa nel server, viene scritto in un file di log. E' come le telecamere di sicurezza di un negozio — non le guardi sempre, ma quando succede qualcosa le rivedi.

### 3 Tipi di Log

**1. Request log (ogni richiesta)**
```
Chi ha chiesto cosa, quando, quanto ci ha messo il server a rispondere.
Utile per: capire la performance, trovare endpoint lenti, vedere il traffico.
```

**2. Audit log (eventi importanti)**
```
Login, logout, cambio password, pagamento, cancellazione account.
Utile per: sicurezza, GDPR, capire cosa e' successo se un utente segnala un problema.
```

**3. Security log (anomalie)**
```
Troppi login falliti, tentativi di accesso non autorizzato, webhook sospetti.
Utile per: bloccare attacchi, proteggere gli utenti.
```

### Log Rotation
I file di log crescono ogni giorno. "Log rotation" significa: ogni giorno il file viene compresso e archiviato, e ne parte uno nuovo. Dopo 7 giorni, i vecchi vengono cancellati. Cosi' il disco non si riempie.

---

## Monitoring — Le Sentinelle

### Health Check
Ogni 5 minuti, uno script chiede al server: "stai bene?". Il server risponde con lo stato di ogni componente:

```
Database: OK (risponde in 2ms)
Redis: OK (risponde in 1ms)
Disco: 59 GB liberi
RAM: 43% usata
Ultimo backup: stamattina alle 3:00
```

Se qualcosa non va, parte un messaggio Telegram al tuo telefono: "Il database non risponde!". Cosi' puoi intervenire prima che gli utenti se ne accorgano.

---

## GDPR — La Privacy degli Utenti

### Cos'e'
Il GDPR e' la legge europea sulla privacy. Se un utente europeo usa il tuo servizio, devi rispettare queste regole:

**1. Diritto di sapere**: l'utente puo' chiedere "quali dati hai su di me?" e tu devi darglieli (endpoint `/export`).

**2. Diritto di cancellazione**: l'utente puo' dire "cancella tutto" e tu devi farlo. Il sistema aspetta 30 giorni (nel caso cambi idea), poi elimina tutto.

**3. Minimizzazione**: raccogli solo i dati necessari. Email e password per il login, Stripe ID per il pagamento. Niente di piu'.

**4. Sicurezza**: devi proteggere i dati. Password hashate, connessioni criptate, accesso limitato.

---

## Frontend — Cosa Vede l'Utente

### Oggi (aggiornato 30 Mar 2026)
La dashboard e' un file HTML (288K) generato da analisidef con tutti i dati incorporati.
Viene servita da App_tool via symlink. Funziona, la conosci, ci stai lavorando sopra.

Tab in sviluppo attivo su analisidef:
- **Profile**: login, collegamento a duels.ink e lorcanito per i nickname
- **Community Video**: video degli streamer che collaborano, School of Lorcana
- **Community Tornei**: link ai tornei (tcg.ravensburgerplay.com)

### Strategia di transizione (NON costruire la SPA adesso)

Finche' sviluppi attivamente dashboard.html in analisidef, costruire una SPA
in parallelo significherebbe fare doppio lavoro. La strategia e':

```
FASE ATTUALE — Dashboard cresce in analisidef, backend cresce in App_tool
  analisidef: sviluppo tab Profile, Community, tornei
  App_tool:   API, auth, DB, sicurezza, import dati

QUANDO la dashboard e' STABILE (non ci lavori ogni giorno):
  1. Copia dashboard.html in App_tool (snapshot statico, gia' pianificato)
  2. Adatta il JS per chiamare le API invece di dashboard_data.json
  3. Aggiungi schermata login davanti
  4. Le API per profile/community/tornei saranno gia' pronte nel backend

DOPO (se serve):
  Ricostruisci come SPA vera (pagine separate, caricamento on-demand)
  Oppure tieni la dashboard adattata — se funziona, funziona
```

### Perche' NON fare la SPA ora
- Ogni feature la faresti due volte (in dashboard.html e nella SPA)
- La SPA non sarebbe mai allineata con la dashboard che evolve
- La dashboard attuale e' gia' ricca e funzionante

### PWA (quando la dashboard sara' in App_tool)
Lo stesso HTML, ma:
- I dati non sono piu' incorporati — il JavaScript chiede al server via API solo quello che serve
- C'e' un "Service Worker" — un programmino che salva i dati in cache nel browser, cosi' la prossima volta e' istantaneo
- C'e' un "manifest.json" — un file che dice al telefono "puoi installare questa pagina come un'app". Su iPhone: Safari → Condividi → "Aggiungi a Home". Appare un'icona come un'app nativa.

### App iPhone (Capacitor)
Capacitor e' uno strumento che prende il tuo sito web e lo "wrappa" in un'app nativa iOS. Stesso codice, ma:
- Appare nell'App Store
- Puo' mandare notifiche push ("Nuove killer curves per AmAm!")
- Puo' usare Face ID per il login
- Ha un'icona con badge (il numerino rosso delle notifiche)

Non devi riscrivere nulla in Swift/Objective-C. Il tuo HTML/JS funziona dentro un browser nascosto nell'app.

---

## Deploy — Come Aggiorni il Codice

### Il Problema
Quando modifichi il codice e vuoi metterlo online, non puoi spegnere il server perche' gli utenti stanno navigando. Serve un "deploy zero-downtime".

### Come Funziona

```
1. Spingi il codice su Git: git push origin main

2. Sul server, lanci lo script deploy.sh che fa:
   a. Scarica il codice nuovo: git pull
   b. Aggiorna il database se serve: alembic upgrade
   c. Dice a uvicorn: "ricarica" (segnale SIGHUP)

3. uvicorn ha 4 worker. Quando riceve SIGHUP:
   - Worker 1: sta servendo una richiesta → FINISCE → si riavvia col codice nuovo
   - Worker 2: e' libero → si riavvia SUBITO col codice nuovo
   - Worker 3: sta servendo → FINISCE → si riavvia
   - Worker 4: e' libero → si riavvia SUBITO

   In ogni momento, almeno 1-2 worker sono attivi.
   L'utente non nota nulla. Zero downtime.
```

### Rollback (tornare indietro)
Se il deploy rompe qualcosa:
```bash
# Torna al codice precedente (10 secondi)
git reset --hard HEAD~1
systemctl reload lorcana-api

# Se anche il database e' rotto:
alembic downgrade -1  # annulla l'ultima modifica allo schema
```

---

## Dev vs Prod — Due Ambienti Separati

### Perche'
Non vuoi testare il codice nuovo direttamente sul server che usano gli utenti. Rischi di rompere tutto. Servono due ambienti identici ma separati:

```
DEV (sviluppo):                      PROD (produzione):
  Database: lorcana_dev               Database: lorcana
  Stripe: modalita' test              Stripe: modalita' live
  (carte finte: 4242 4242 4242 4242)  (carte vere)
  Log: DEBUG (tutto)                  Log: INFO (solo cose importanti)
  Porta: 8001                         Porta: 8000 (dietro nginx)
```

Lavori su dev, testi, funziona? Fai merge su Git, deploy su prod. Se in dev funziona e in prod no, il problema e' nell'ambiente — non nel codice.

---

## La Pipeline — Cosa Gira di Notte

Mentre gli utenti dormono, il server lavora:

```
03:00  BACKUP
       Copia di sicurezza del database → disco locale → server remoto

06:00  IMPORT MATCH
       I nuovi match JSON scaricati dal monitor → dentro PostgreSQL

06:30  AGGIORNA VISTE
       Ricalcola win rate, matrice matchup, meta share (materialized views)

07:00  PIPELINE DAILY
       Genera i dati per il tab Monitor della dashboard

07:01  RACCOLTA
       Prende le killer curves fresche e le threats dell'LLM

Lunedi 08:00  PIPELINE WEEKLY
       Genera i dati per Coach e Lab (piu' pesante, 1 volta a settimana)

Quando serve  LLM WORKER
       Chiede a Claude di generare nuove killer curves
       Usa la Batch API (50% di sconto, non e' urgente)
```

Tutto gira automaticamente. Se qualcosa fallisce, il sistema manda un messaggio Telegram e continua a servire i dati vecchi fino alla prossima run.

---

## Le Difese (Sicurezza in Sintesi)

```
LIVELLO 1 — RETE
  Solo le porte 80 (HTTP), 443 (HTTPS) e 22 (SSH) sono aperte.
  Il database, Redis, i worker: parlano solo tra loro, invisibili dall'esterno.

LIVELLO 2 — TRASPORTO
  Tutto criptato con HTTPS. Il browser mostra il lucchetto.
  Impossibile intercettare password o dati in transito.

LIVELLO 3 — AUTENTICAZIONE
  Password hashate con bcrypt (irreversibili).
  Token JWT con scadenza 15 minuti.
  Rate limit: max 5 tentativi di login in 15 minuti.

LIVELLO 4 — AUTORIZZAZIONE
  Ogni endpoint controlla il tier dell'utente.
  Free non puo' accedere ai dati Pro.
  Un utente non puo' vedere i dati di un altro.

LIVELLO 5 — HEADERS
  Il browser viene istruito a bloccare attacchi comuni:
  - Non puo' includere la pagina in un iframe (clickjacking)
  - Non puo' eseguire script non autorizzati (XSS)
  - Non manda il referer a siti esterni
```

---

## I Costi (Quanto Costa Tenere in Piedi Tutto)

```
Server Hetzner (2 CPU, 4GB RAM):      5 EUR/mese
Disco aggiuntivo (89GB):              4 EUR/mese
Backup remoto (100GB):                3 EUR/mese
Dominio (lorcanamonitor.com):         1 EUR/mese
HTTPS (Let's Encrypt):                GRATIS
Claude API per killer curves:          ~6 EUR/mese (o gratis con Startup Program)
Commissioni Stripe:                    ~1.5% per ogni pagamento

TOTALE FISSO: ~13-19 EUR/mese

Per coprire i costi fissi bastano 2 utenti Pro (2 × 12 EUR = 24 EUR).
```

---

## Glossario

| Termine | Significato |
|---------|-------------|
| **API** | Un "menu" di comandi che il frontend puo' chiedere al backend. Es: "GET /api/v1/killer-curves/AmAm/ES" |
| **Backend** | La parte del programma che gira sul server. Calcola, legge dal database, risponde alle richieste. |
| **bcrypt** | Un algoritmo per trasformare una password in una stringa illeggibile. Irreversibile. |
| **Cache** | Una copia veloce di dati che servono spesso, per non ricalcolarli ogni volta. |
| **CDN** | Content Delivery Network — server sparsi nel mondo che servono i tuoi file statici piu' velocemente. |
| **CORS** | Una regola che dice al browser: "accetta dati solo dal mio dominio, non da altri". |
| **Cron** | Un programma Linux che esegue comandi a orari prestabiliti (es: "ogni giorno alle 3:00"). |
| **Deploy** | Mettere online il codice nuovo. |
| **DNS** | Il "rubrica telefonica" di internet. Traduce "lorcanamonitor.com" nell'indirizzo IP del server. |
| **Endpoint** | Un singolo "piatto" del menu API. Es: `/api/v1/monitor/meta` |
| **fail2ban** | Programma che blocca automaticamente gli IP che tentano troppi accessi sbagliati. |
| **FastAPI** | Framework Python per creare API web. Come Flask ma piu' veloce e moderno. |
| **Frontend** | La parte del programma che gira nel browser dell'utente. HTML, CSS, JavaScript. |
| **GDPR** | Legge europea sulla privacy. Regola come tratti i dati degli utenti. |
| **gzip** | Un algoritmo di compressione. Riduce la dimensione dei dati trasferiti. |
| **Hash** | Trasformazione irreversibile. Da "password123" a "$2b$12$xKq..." — non puoi tornare indietro. |
| **HTTPS** | HTTP criptato. Il lucchetto nel browser. Nessuno puo' leggere i dati in transito. |
| **Indice (DB)** | Come l'indice di un libro — permette al database di trovare i dati senza leggere tutto. |
| **JSONB** | JSON salvato in formato binario dentro PostgreSQL. Puoi fare query sui campi interni. |
| **JWT** | JSON Web Token — un "badge digitale" che identifica l'utente. Firmato crittograficamente. |
| **Let's Encrypt** | Servizio gratuito che fornisce certificati HTTPS. Si rinnova automaticamente. |
| **Materialized View** | Una query precalcolata. Il database salva il risultato e lo serve subito, senza ricalcolare. |
| **Middleware** | Codice che si esegue "prima" di ogni richiesta API. Es: controlla il token, logga, rate limit. |
| **Migration** | Uno script che modifica la struttura del database (aggiunge tabella, colonna, indice). |
| **nginx** | Server web ad alte prestazioni. Gestisce HTTPS, routing, rate limiting, compressione. |
| **ORM** | Object-Relational Mapping. Scrivi Python invece di SQL. SQLAlchemy e' un ORM. |
| **PCI DSS** | Standard di sicurezza per chi gestisce pagamenti. Con Stripe Checkout sei conforme automaticamente. |
| **pg_dump** | Comando PostgreSQL che esporta tutto il database in un file. Per il backup. |
| **Pipeline** | Una sequenza di operazioni automatiche. Es: importa match → calcola WR → aggiorna dashboard. |
| **Promo Code** | Codice che regala accesso o sconto. L'admin li crea, gli utenti li riscattano. |
| **PWA** | Progressive Web App. Un sito web che si comporta come un'app (offline, installabile, notifiche). |
| **Rate limit** | Limite al numero di richieste per utente. Protegge da abusi e attacchi. |
| **Redis** | Database in-memory. Velocissimo, usato come cache. Se si spegne, perde i dati (non grave). |
| **Refresh token** | Token a lunga durata (30gg) usato solo per ottenere nuovi access token. Revocabile. |
| **Reverse proxy** | nginx riceve le richieste e le inoltra al backend. Il backend non e' esposto direttamente. |
| **Rollback** | Tornare alla versione precedente del codice o del database. |
| **Service Worker** | Un programmino JavaScript che gira nel browser e gestisce la cache offline. |
| **SQL** | Linguaggio per interrogare database. `SELECT * FROM matches WHERE deck_a = 'AmAm'`. |
| **SQLAlchemy** | Libreria Python per lavorare con database SQL senza scrivere SQL a mano. |
| **SSL/TLS** | Il protocollo di criptazione dietro HTTPS. TLS e' la versione moderna di SSL. |
| **Stripe** | Servizio di pagamento online. Gestisce carte, Apple Pay, Google Pay, abbonamenti. |
| **systemd** | Il gestore servizi di Linux. Avvia i programmi, li riavvia se crashano, li ferma ordinatamente. |
| **Tier** | Livello di abbonamento. Free, Pro, Team. Determina cosa puoi vedere nell'app. |
| **UFW** | Uncomplicated Firewall. Blocca tutte le porte del server tranne quelle che servono. |
| **TTL** | Time To Live. Quanto tempo un dato resta in cache prima di essere ricalcolato. |
| **uvicorn** | Il server che fa girare FastAPI. Gestisce le connessioni HTTP e distribuisce le richieste. |
| **UUID** | Identificativo unico universale. Es: "550e8400-e29b-41d4-a716-446655440000". Impossibile da indovinare. |
| **WAL** | Write-Ahead Log. PostgreSQL scrive le modifiche in un log PRIMA di applicarle. Se crasha, riparte dal log. |
| **Webhook** | Una richiesta HTTP che un servizio esterno fa al tuo server per notificarti di un evento. |
| **Worker** | Un processo che esegue lavoro in background (import match, generazione killer curves, backup). |
| **Zero-downtime** | Aggiornare il codice senza che gli utenti notino interruzioni. |

---

## Codici Promozionali

### Cosa sono
Puoi creare dei codici (tipo "BETATEST2026" o "AMICO20") da dare a persone specifiche.
Due tipi:

**1. Accesso gratuito** — Regala l'accesso completo per un periodo limitato.
Esempio: dai BETATEST2026 a un amico → lui vede tutto per 30 giorni → poi torna free.
Utile per: beta tester, influencer Lorcana, amici, collaboratori.

**2. Sconto** — Riduce il prezzo dell'abbonamento.
Esempio: AMICO20 = 20% di sconto per 3 mesi.
Utile per: promozioni, lancio, fidelizzazione.

### Come funziona
Solo l'admin puo' creare codici (dall'API o da un pannello futuro).
L'utente inserisce il codice nel suo profilo.
Il sistema controlla: codice valido? non scaduto? non esaurito? non gia' usato?
Se tutto OK, applica l'effetto (upgrade tier o sconto).

Ogni codice ha:
- Un numero massimo di usi (es. 10 persone)
- Una data di scadenza (opzionale)
- Un tipo (accesso o sconto)
- Un contatore di quante volte e' stato usato

Quando scade un accesso regalato, l'utente torna automaticamente al suo tier originale.

---

## Sicurezza Operativa (aggiornato 30 Mar 2026)

### Cos'e'
Oltre a proteggere l'app (password, token, HTTPS), bisogna proteggere il server stesso.
E' come blindare la porta di casa (HTTPS) ma anche mettere l'antifurto (fail2ban)
e non lasciare le chiavi sotto lo zerbino (password nel .env, non nel codice).

### Cosa abbiamo fatto il 30 Marzo

**Firewall (UFW)**: attivato. Solo 3 porte aperte al mondo: 22 (SSH), 80 (HTTP), 443 (HTTPS).
Tutto il resto (database, Redis, porte interne) e' invisibile dall'esterno.

**fail2ban**: installato. Se qualcuno sbaglia la password SSH 5 volte, il suo IP viene
bloccato per 1 ora. Stessa cosa per tentativi di login falliti sull'app.

**Password database**: cambiata da una password prevedibile a una stringa random di 32 caratteri.

**File .env**: permessi restrittivi (chmod 600). Solo l'utente root puo' leggerlo.

### Cosa resta da fare
- Aggiungere una chiave SSH (cosi' si entra solo con la chiave, non con la password)
- Creare un utente dedicato "lorcana" (non usare root per tutto)
- Attivare il proxy Cloudflare (nasconde l'IP del server)
- Backup criptati su server remoto

---

## Stato Avanzamento Sviluppo

> Ultimo aggiornamento: 30/03/2026

### ✅ Fase 0 — Infrastruttura (completata)
PostgreSQL 16 e Redis 7 installati e attivi. Database `lorcana` creato con utente dedicato.
Python 3.12 virtualenv configurato con tutte le dipendenze. File di progetto pronti (.env, .gitignore, requirements.txt).

### ✅ Fase 1 — Database + Import (completata)
13 tabelle create (11 originali + promo_codes, promo_redemptions) + 2 materialized views.
Dati copiati (in sola lettura) da analisidef:
- 89,763 match importati (1 mese: 23 feb — 30 mar) da match_archive.db + JSON
- 162 killer curves
- 139 archivi (solo aggregati, ~1 MB — i turni sono gia' nei match)
- 102 snapshot storici

### ✅ Fase 2 — Backend API (completata)
FastAPI funzionante con 16+ endpoint su 4 moduli (Monitor, Coach, Lab, Admin).
4 services implementano la logica di business con query SQL aggregate.
Swagger UI disponibile su `/api/docs`.

**Nota importante**: le API SQL coprono ~20% delle analisi della dashboard.
Le analisi avanzate (tech tornado, board state, loss classification, mulligan,
card synergies, player cards) vivono nel motore di analisidef (lib/, 6.7K LOC)
che non e' stato ancora portato in App_tool.

### ✅ Fase 3 — Frontend Ponte + Infrastruttura (completata)
Dashboard identica a quella di analisidef, servita da App_tool.
- Dominio `metamonitor.app` registrato su Cloudflare
- HTTPS con certificato Let's Encrypt (auto-renewal)
- Password di protezione HTTP Basic (nessuno puo' accedere senza credenziali)
- Symlink al template dashboard.html di analisidef (modifiche propagate automaticamente)
- systemd service: uvicorn si riavvia da solo se crasha, parte al boot

### ✅ Stabilizzazione (completata)
- 2 repo Git privati su GitHub:
  - `ema299/LorMonitor` (App_tool — sviluppo app, branch main + dev)
  - `ema299/LorAnalisi` (analisidef — motore analisi, backup automatico Mar+Gio)
- Backup automatico DB ogni notte alle 03:00 (retention 7 giorni)
- Import automatico nuovi match ogni giorno alle 06:30
- Import killer curves Mar+Gio alle 03:30
- Health check ogni 5 minuti con auto-restart
- robots.txt blocca indicizzazione Google

### ✅ Fase 4a — Auth (completata 30 Mar 2026)
Sistema di autenticazione completo:
- Registrazione e login con email + password
- Token JWT (15 min) + refresh token (30 giorni) con rotazione
- Password criptate con bcrypt (irreversibili)
- Profilo utente, logout, cancellazione account (GDPR)
- Tier enforcement: free/pro/team/admin
- Codici promozionali: accesso gratuito temporaneo + sconti
- 5 account test creati (tutti con accesso completo per la fase di sviluppo)

Sicurezza server:
- Firewall UFW attivo (porte 22, 80, 443)
- fail2ban attivo (SSH + nginx)
- Password DB cambiata (random 32 char)
- JWT secret generato (random 64 char)

### ✅ Da completare per Fase 4 — TODO
- [ ] Snapshot statico dashboard (copia di sicurezza da analisidef)
- [ ] Stripe checkout + webhook per pagamento
- [ ] API community: video streamer, tornei
- [ ] API user: profilo, nickname duels.ink/lorcanito

### ⏳ Fase 5 — Transizione Frontend
NON costruire SPA adesso. Lo sviluppo HTML attivo e' in analisidef.
Quando la dashboard sara' stabile:
1. Copiare dashboard.html in App_tool
2. Adattare JS per usare le API
3. Aggiungere login
Le API per profile/community/tornei saranno gia' pronte.

### ⏳ Fase 6 — PWA + Mobile iOS
Service Worker, offline, manifest.json, Capacitor per App Store.
Solo dopo che il frontend e' migrato in App_tool.

### Piano di transizione verso autonomia (futuro, 3 fasi)
- **Fase A (ponte, attuale)**: App_tool serve, analisidef calcola. Zero rischi.
- **Fase B (motore copiato)**: si porta lib/ in App_tool, si testa in parallelo.
- **Fase C (autonomia)**: si attivano i worker, si spegne analisidef.
Ogni fase e' reversibile. Si procede solo quando la precedente e' validata.

### ⚠️ Vincoli attivi
- Nessun piano Anthropic API con credito — LLM worker rimandato
- Il motore di calcolo (lib/) resta in analisidef — App_tool dipende dal suo output
- Lo sviluppo frontend e' attivo in analisidef/daily/dashboard.html, NON in App_tool
- Tab in sviluppo attivo: Profile (login, nickname), Community (video, tornei)
