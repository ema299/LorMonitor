# Lorcana Monitor — Business Plan

**Versione:** 4.2 timing-corrected + conversion-recalibrated | **Data:** 26 Aprile 2026
**Scope:** documento ufficiale di business di `metamonitor.app`.

**Changelog — v4.1 → v4.2 (26/04, post stress-test):**

- **NUOVO v4.2 (26/04, recalibrated):** §11 conversion rate scenari ricalibrati su benchmark consumer-SaaS reali (0.5% / 1.5% / 3% — il vecchio "Base" 3% era di fatto Ottimistico) · §11.4 Coach numbers ridimensionati a outreach plausibile · §11.6 vincolo bancario marcato come P0 upstream · §12 ristrutturato in **Phase A pre-launch (Mag-Ago)** + **Phase B Set 12 hard launch (Set 2026)** dopo correzione timing Ravensburger (Set 12 = Settembre, non Maggio) · §12.0 step bancario gating esplicitato.
- **NUOVO v4.1 (24/04 sera, reality-aligned):** §2.2 struttura frontend reale = **7 tab primary (non 5+2)** · §2.2a fake paywall + interest tracking già live · §2.4 limitazioni attuali dichiarate · §3.2 conversion loop diagnosi→prescrizione→applicazione · §6 tabella Tier con mental model · §6.4 posizionamento Replay come engagement, non revenue · §9.2 Board Lab stato reale V3 (stub + legacy `team_coaching.js`) · §12.1 settimana 1 Launch Plan riscritta (no tab rename, no drawer, focus privacy + Play + swap) · §12.2 nota "W2 no code"
- **NUOVO v4.0 (mattina, riscrittura strategica GPT 24/04 06:48 — `BP_STRATEGIST_POINT.md`):** §1 Executive Summary · §2 Prodotto · §3 Core Value Proposition · §4 Mercato · §5 Posizionamento · §6 Business Model (2 SKU, €9/€39) · §7 Go-To-Market · §8 Strategia di Prodotto · §9 Coaching e Board Lab · §10 Rischi · §11 Proiezioni · §12 Launch Plan 14 gg
- **EREDITATO dalla v3.1 (22/04) perché ancora valido:** §13 Landscape legale Duels.ink · §14 Ravensburger · §15 Piani contingenza dati · §16 Tech Moat · §17 Struttura fiscale · §18 Feature escluse
- **Originali intatti in** `analisidef/BUSINESS_PLAN.md` (v3.1) e `analisidef/business/BP_STRATEGIST_POINT.md` (Refined v1) — questo documento li consolida, non li sovrascrive.

**Decisioni preservate (non rinegoziabili pre-launch):**
- V3 resta a **7 tab primary** (Home · Play · Meta · Deck · Team · Improve · Events). NO 5+2. NO drawer. NO Pro Tools / Community contenitore.
- Meta e Deck non si toccano salvo bug. Sono già maturi.
- Pagamento reale SOLO dopo struttura fiscale chiara. Fino ad allora: fake paywall + interest tracking (già live).
- Focus pre-launch: Play (conversion clarity), privacy minima, Board Lab wiring minimo. Improve resta debole pre-launch, migliorato post-launch.

**Ruolo dei documenti complementari:**
- **Prodotto e architettura V3**: vedi [`V3_ARCHITECT_POINT.md`](V3_ARCHITECT_POINT.md) in questa cartella.
- **TODO operativo App_tool / V3 / Migration**: vedi [`TODO.md`](TODO.md) in questa cartella.

---

## 1. Executive Summary

Lorcana Monitor è **uno strumento di performance che spiega le sconfitte e migliora le decisioni** dei giocatori Disney Lorcana TCG. Non è una dashboard e non è una piattaforma community. Il prodotto esiste tecnicamente (50K-300K match log reali parsati turn-by-turn, 268 killer curves LLM-generate, loss detection, mulligan trainer, replay viewer, Board Lab). Il business è ancora da costruire.

Realtà strategica di fondo:

- Il mercato competitivo Lorcana è piccolo (30K-50K giocatori seri nel mondo).
- La sottoscrizione analytics da sola è un pilastro revenue fragile a questa scala.
- Il coaching tooling (Board Lab + Pro Tools) monetizza meglio per utente e ha upside B2B.
- La fornitura dati dipende dallo scraping `duels.ink` — rischio reale, gestibile ma non eliminabile.
- Community features (streaming, events, school) generano goodwill e acquisizione, **non revenue**. Sono marketing, non SKU.

Il piano che segue mantiene tutte le feature core, semplifica la storia di monetizzazione a **un prodotto insight + un prodotto coaching**, e lancia in 7 giorni con postura lead-capture-first.

---

## 2. Descrizione Prodotto

### 2.1 Cosa è fisicamente costruito oggi

| Strato | Asset | Stato |
|--------|-------|-------|
| Data | 50K-300K match log (turn-by-turn, plays/abilities/challenges/quests) scrapati da `duels.ink` | Live, raccolta daily |
| Analytics | Loss classification (9 dimensioni + 3 livelli detection: keywords × abilities × patterns) | 100% data-driven, zero hardcode |
| LLM pipeline | 268 killer curves (worst-case opponent sequences), validate (9 check strutturali + 1 semantico) | Batch martedì, ~$4/run |
| Frontend | PWA, 7 tab live legacy, V3 redesign 7 tab pronto allo swap | Dev-hosted, swap V3 = ultima azione settimana 1 (§12.1) |
| Coaching tool | Board Lab: upload `.replay.gz`, viewer animato con mano completa, annotazioni coach | Live, label enrichment pending |
| Replay viewer | Viewer step-by-step match reali (read-only) | Live |
| Deck tools | Mulligan trainer su mani PRO reali, Meta Deck Optimizer, consensus/comparator | Live |

### 2.2 Struttura frontend reale (V3, 24/04/2026)

**7 tab primary:** Home · Play · Meta · Deck · Team · Improve · Events
(Community è reso nello stesso tab di Events, stesso render lane.)

Questa struttura **NON cambia per il lancio**. Il BP v4.0 di stamattina ipotizzava una riorganizzazione 5+2 (drawer) che oggi resta un'ipotesi di lungo termine, non un prerequisito di lancio. Motivi:

- Meta e Deck sono già maturi sulla nav attuale.
- Team è primary perché ospita Board Lab (il coaching SKU).
- Improve è primary perché è il gancio retention per nickname bridge.
- Riordinare la nav ora bloccherebbe il lancio senza spostare la conversione.

Il business plan ragiona su *cosa vende ogni tab*, non sulla tassonomia.

### 2.2a Fake paywall + interest tracking (già live in V3)

Il V3 oggi espone client-side gate + server-side waitlist, senza pagamento reale:

- `wrapPremium(html, ctx)` in `monolith.js:872` — wrapper su contenuto Pro
- `recordPaywallIntent(tier)` — click su lock → POST `/api/v1/user/interest` (Bearer optional) → segnale WTP persistito
- Dopo il click, fake local unlock per non frustrare l'utente (segnale WTP, non revenue)

Il pagamento reale (Paddle) si attiva SOLO dopo struttura fiscale definita (SRL / vincolo bancario, §17). Fino ad allora, il prodotto vive in **waitlist economy**: validiamo la curva di interesse, non monetizziamo.

### 2.3 Cosa il prodotto NON è

- Non è un meta oracle (lane di Lorcanito).
- Non è un coach marketplace (lane di Metafy).
- Non è un deck database (lane di inkDecks).
- Non è un'app casual di deckbuilding/collection (lane della Companion App Ravensburger).
- Non è un simulatore.

Esclusioni deliberate. Ogni feature request va verificata contro questa lista.

### 2.4 Limitazioni attuali (dichiarate, non nascoste)

Onestà intellettuale verso utente e stakeholder. Ogni limite qui è noto, comunicato in UI, e ha un path di miglioramento:

| Area | Limite oggi | Path di miglioramento |
|------|-------------|------------------------|
| **Mulligan Trainer** | Dataset thin su alcuni matchup (specialmente Infinity + perimetri piccoli). Confidence badge va mostrato sempre. | Crescita naturale del dataset + confidence/sample size surface (post-launch) |
| **How to Respond** | Generato per **archetype standard-deck**, non personalizzato sulla lista dell'utente. Funziona bene su consensus, meno su liste rogue. | Fase B LLM + nickname bridge adoption sbloccano personalized (post-launch 60 gg) |
| **Improve / personal stats** | Richiede nickname bridge attivato. Finché l'utente non inserisce duels/lorcanito nick, Improve è povero (è raccolta di strumenti, non percorso). | Onboarding più aggressivo sul bridge (pre-launch) + ristrutturazione percorso (post-launch 30 gg) |
| **Board Lab V3** | Upload/viewer in V3 è stub (`team.js:300` "coming soon"); flusso completo è nel legacy `team_coaching.js` (copia 1936 LOC) caricato come ultimo script. | Refactor post-launch 30-60 gg. Per lancio: wiring minimo (access-control + consent). |
| **Meta regionale (country segmentation)** | Non implementato. Richiede ≥500 utenti con country impostato. | Post-launch, naturalmente dopo nickname bridge adoption. |
| **Replay v2 animato dashboard viewer** | Legacy usa viewer statico `rv*`. L'animato è solo dentro Board Lab. | Post-launch, se dati d'uso lo giustificano. |

Queste limitazioni non bloccano il lancio. Vanno **dichiarate nelle copy UI** (honesty badge, banner confidence, "based on N games"), non nascoste. La trasparenza sul limite è un vantaggio competitivo vs tool che vendono hype.

---

## 3. Core Value Proposition

> **"Stop losing the same way. See the exact turn your match ends, the exact cards that kill you, and the exact response that would have held."**

Una frase. Una promessa. Analisi turn-by-turn del fallimento + risposta prescrittiva, sul deck e matchup reali dell'utente, ancorata a dati match veri.

Tutto il resto — community, school, events, meta overview, deckbuilding tools — è infrastruttura di supporto. Non è il sales pitch.

### 3.1 L'UNICO core value driver

Il tab Play + le killer curves. Quello è il prodotto. Se un utente potenziale non trae valore da Play entro 60 secondi, niente altro conta.

Ogni altra feature è:
- **Acquisizione** (Meta, Community, Events, Set 12 Hub) — porta dentro l'utente.
- **Retention** (Improve, personal stats) — lo tiene dentro.
- **Upsell** (Board Lab + Team analytics) — lo monetizza.

Play è dove il valore nasce e dove la conversione avviene.

### 3.2 Il conversion loop (unico imbuto)

```
  Meta / Home            →  Play                    →  Play deep            →  Upgrade
  [acquisizione]            [diagnosi]                  [prescrizione]          [Pro/Coach]

  "guarda il field"         "vs chi perdo"              "come rispondo"         "voglio tutto
                            "quale curve mi schianta"   "mulligan reveal"        + mia sessione"
                            "guarda il replay"
                            → engagement "wow"          → paywall soft          → paywall hard
```

Regole del loop:

1. **Insight è gratis.** Killer curve top visibile, matchup worst WR visibile, meta fitness visibile. Tutto il "ti spieghiamo cosa non va" è free.
2. **Il replay è engagement, non prodotto.** Il Replay Viewer (oggi embedded in Team e legacy) fa venire voglia di pagare. Non è quello che si paga. Vale come hook acquisition e come "wow moment".
3. **La prescrizione è Pro.** How to Respond completo, mulligan con outcome reveal, killer curves deep multi-profilo = **€9/mese**.
4. **L'applicazione è Coach.** Prendi un replay tuo o di uno studente, annota, esporta, condividi pagina pubblica = **€39/mese**.

Non vendiamo analytics. Vendiamo **la risposta**.

---

## 4. Analisi di Mercato

### 4.1 Mercato addressable — numeri onesti

| Strato | Stima | Fonte / ragionamento |
|--------|-------|----------------------|
| Giocatori Lorcana totali globali | 500K-1M | Disclosure Ravensburger, event attendance, Discord scale |
| Giocatori competitivi attivi | 30K-50K | Popolazioni ranked duels.ink + lorcanito + circuito tornei |
| Seri abbastanza da pagare per analytics | 3K-8K (TAM realistico) | 10-15% del subset competitivo storicamente WTP per tool TCG |
| Buyer seri di coaching | 300-800 | ~10% utenti paying analytics compra coaching |
| Coach nel mercato | 10-30 worldwide | Superficie Metafy + Discord |

**Implicazione:** la sottoscrizione consumer è un pilastro constrained. La monetizzazione coaching-side (B2B2C) deve portare peso presto.

### 4.2 Traiettoria mercato (non gonfiata)

- Lorcana ha 2.5 anni. Primo World nel 2025. Crescita ma non esplosione.
- Il rank-and-file è concentrato su `duels.ink` (no client ufficiale).
- Ravensburger potrebbe lanciare un client ufficiale in 12-24 mesi. È il più grande singolo evento di mercato da pianificare.
- Ladder regionali (Giappone, Cina) attivi ma piccoli; non mercato a breve.

### 4.3 Cosa si muove domani

Il rischio binario: Ravensburger fa uscire un client digitale ufficiale. Quando lo fa, la questione dati si fa più facile (API migliore, probabilmente) ma la competizione aumenta (analytics first-party diventa plausibile). Posizione: arrivare come partner analytics ovvio prima che l'analytics first-party esca.

---

## 5. Posizionamento Competitivo

| Player | Cosa fa | Overlap | La nostra posizione |
|--------|---------|---------|---------------------|
| Lorcanito | Meta dashboard + WR aggregati | Sì, su superficie meta | Noi non siamo meta oracle; spieghiamo perdite individuali. Core non-overlapping. |
| Statcana | Tracker manuale personale | Marginale | Loro self-reported; noi data-extracted. |
| Dreamborn / inkDecks | Deck builder / DB tornei | No | Ci serviamo da loro, non li rimpiazziamo. |
| Metafy coach | Sessioni 1:1 paid | No (noi li abilitiamo) | Gli vendiamo un tool; gli studenti arrivano preparati. |
| Ravensburger Companion App | Deck builder + collection ufficiali | No (per ora) | Noi analytics, loro lifestyle. Non-overlapping. |
| Analytics Ravensburger futuri (ipotetici) | ? | Potenzialmente sì | Arrivare prima, guadagnare status partner, o pivot multi-TCG. |

**Postura strategica:** non combattere questi attori. Vendere a loro o attraverso loro. Ogni riga competitor è o un complemento o un futuro acquirente.

### 5.1 Perché nessuno ha costruito questo

Il moat è 18 mesi di lavoro dati + pipeline compounding:

- 50K-300K match log con fedeltà turn-by-turn (nessuna API pubblica li offre).
- Tassonomia loss classification (9 dimensioni × 3 livelli detection).
- Killer curves LLM validate (0 FAIL su 268 file).
- Ability profile auto-parser (2800+ carte, trigger+effect+scope).

Un competitor che partisse oggi ha bisogno di 12-18 mesi per arrivare alla pari. Quella è la finestra.

---

## 6. Business Model

Due SKU. Non di più. La complessità era il peccato del piano precedente.

| Tier | Prezzo | Ruolo (mental model) | Cosa sblocca |
|------|--------|----------------------|--------------|
| **Free** | €0 | **Diagnosi.** Ti diciamo cosa non va. | Meta fitness, matrix light, killer curves top-1 per matchup (3 matchup/giorno), mulligan senza reveal (5 mani/giorno), Community, Events |
| **Pro** | €9/mese (€79/anno) | **Prescrizione.** Ti diciamo cosa fare. | Tutti i matchup illimitati, killer curves multi-profilo, Mulligan Trainer con outcome reveal, How to Respond completo OTP/OTD, Improve full (My Stats, Blind Playbook, nickname bridge), Card Impact, Deck Recommendation Engine |
| **Coach** | €39/mese | **Applicazione.** Lavori sul replay con studenti. | Tutto di Pro + Board Lab (upload `.replay.gz`, viewer animato, annotazioni coach, export PDF sessione) + Team KPI + roster studenti fino a 10 + coach page pubblica `/coach/<slug>` + affiliate 20% recurring |

### 6.1 Decisioni di prezzo

- **€9 Pro, non €12.** Frizione più bassa in un mercato piccolo conta più del margine ottico. Annuale €79 ancora commitment.
- **€39 Coach, non €49.** I coach rivendono valore; la loro sensibilità al prezzo è minore di un hobbyista ma la churn è alta se il ROI non è chiaro. Entry più economico, dimostra ROI, alza dopo.
- **No tier affiliate a scala.** Un flat 20% recurring per qualsiasi utente paying che ne porta un altro. Gestito manualmente per i primi 12 mesi.
- **No one-shot report.** Erano diluitivi e poco chiari.

### 6.2 Cosa è stato rimosso dai piani precedenti

- Programma affiliate a 4 tier → sostituito da rate flat singolo.
- Prodotto one-shot report → rimosso (SKU poco chiaro).
- Deck marketplace / card pricing / trading → resta fuori (ecosystem violations).
- Tier "Team" separato sopra Coach → consolidato in Coach (fino a 10 studenti copre già capitani team).

### 6.3 Payment plumbing

**Paddle** come Merchant of Record. Fee extra 3-5% vs Stripe, ma elimina la contabilità EU VAT OSS — un costo che il founder solo non può assorbire in tempo.

**Pre-lancio: nessun pagamento reale.** Solo fake paywall + interest tracking (§2.2a). Paddle si attiva dopo chiusura struttura SRL/fiscale (§17).

### 6.4 Posizionamento del Replay (chiarimento strategico)

Il Replay Viewer non va venduto come feature principale. È **engagement + acquisition + wow moment**, non revenue driver.

| Tipo | Esempio | Ruolo commerciale |
|------|---------|-------------------|
| Replay Viewer (match log pubblico) | "Guarda come Ruby/Sapphire ti chiude T5" | Acquisizione, condivisibile, anonimizzato |
| Replay Viewer embedded in Team | Analisi match teammate | Engagement interno team |
| Board Lab (upload proprio `.gz`) | Coach annota sessione studente | **Coach tier €39/m** (l'unico che monetizza direttamente) |

Chi paga non paga per "vedere replay". Paga per **killer curves full + mulligan reveal + How to Respond + coaching workspace**. Il replay è quello che lo convince a pagare, non quello che compra.

Implicazione: nessun paywall sul primo replay per matchup. Paywall sul **4° matchup aperto nel giorno** (Pro trigger), sul **mulligan outcome reveal** (Pro trigger), sull'**ingresso Board Lab** (Coach trigger). Il replay resta hook, il paywall scatta sul "dopo".

---

## 7. Go-To-Market

Zero acquisizione paid per i primi 6 mesi. Se il prodotto è abbastanza buono, i canali sotto funzionano; se no, spesa paid non aggiusta.

### 7.1 Canali primari

| Canale | Effort | Risultato atteso 90gg |
|--------|--------|------------------------|
| **Set 12 launch hub** (lead magnet: Meta Preview PDF gated da email) | Asset 1-tempo, 3 giorni build | 100-250 email, 50-120 Discord |
| **Creator seed** (2 YouTuber italiani + 1 EU + 1 NA, Pro gift, data story hand-delivered) | 4h/settimana | 1-2 menzioni video/mese, ~500 visite referral ognuna |
| **Asset virale** (screenshot matchup matrix heatmap, condivisibile settimanale) | Automatizzato | Trazione organica X / Reddit |
| **Coach outreach** (DM 10 coach Metafy-adjacent con: "i tuoi studenti arrivano preparati, 20% affiliate su Pro") | 3h | 2-4 coach partner entro day 60 |
| **Presenza Discord** (rispondere domande in Lorcana Discord con screenshot) | 30min/giorno | Trust building slow-burn |

### 7.2 Cosa NON si fa nei primi 90 giorni

- No Google Ads, no Meta Ads.
- No sponsorship influencer.
- No stand conferenze.
- No comunicato stampa.
- No SEO content farm.

Tutto downstream di conversione validata. Prima: il prodotto converte 3% degli utenti registrati a Pro?

### 7.3 Finestra Set 12 (Maggio 2026)

Singolo miglior momento di acquisizione nei prossimi 6 mesi. Pianifica specificamente attorno a questo.

- 7 giorni engineering → launch-ready.
- 7 giorni content → Set 12 meta preview, PDF, social asset.
- 14 giorni misurazione → cosa ha convertito, cosa no, uccidi quello che non funziona.

Piano dettagliato: vedi §12.

---

## 8. Strategia di Prodotto

### 8.1 Focus nei prossimi 90 giorni

Una frase per priorità:

1. **Il tab Play deve essere il miglior matchup coach in TCG.** Ogni ora spesa lì aggiunge valore difendibile.
2. **Board Lab deve dare la sensazione di una sessione di coaching in un browser.** Quello è l'intera ragione di esistere dello SKU coaching.
3. **Set 12 Hub deve catturare lead.** Tutto il resto in Home è secondario.

### 8.2 Ignora fino al giorno 91

- Country segmentation (nice, non revenue driver).
- School of Lorcana build completo (goodwill, spedisci placeholder e avanti).
- Meta Deck Optimizer polish (carino, non wedge).
- Error Detection / replay review per utenti (scope enorme, post-validazione).
- Espansione multi-TCG (uccide focus, uccide differenziazione).
- Board editor / tactical whiteboard drawing (over-build; Board Lab basta).

### 8.3 Principi ecosistema (ereditati, ancora corretti)

| Principio | Regola |
|-----------|--------|
| Teaching ≠ Coaching ≠ Analytics | Non collassarli. School è teaching, Board Lab è enabler di coaching, Play è analytics. |
| Il tool supporta, non rimpiazza | Non rimpiazziamo duels.ink, lorcanito, Ravensburger, o coach umani. Rendiamo ognuno di loro più utile. |
| Boost ecosistema, non estrai | Ogni feature deve aiutare almeno un altro attore, mai togliere valore a uno. |
| Tabletop è l'endgame | Digitale è pratica; tornei fisici chiudono il ciclo. Tab Events esiste per questo. |

---

## 9. Ruolo di Coaching e Board Lab

Questa sezione conta più di qualsiasi singolo tab redesign.

### 9.1 Perché il coaching è il vero percorso di monetizzazione

Un hobbyista paga €9/mese per un tool finché la sua curiosità non svanisce, a meno che il tool non sia parte di un habit loop. Un coach paga €39/mese per un tool che gli fa guadagnare €100-300/mese in fee studenti, e non fa churn finché lo fanno i suoi studenti.

L'unit economics racconta la storia:

- 100 utenti Pro × €9 × ~60% gross retention a 12m → €5.400/anno, fragile.
- 10 Coach × €39 × ~80% gross retention + ognuno porta 3 studenti Pro → €4.680 diretti + €2.430 indiretti, più stabile.

Il coaching è l'engine revenue a volume più basso, stabilità più alta. Pro è l'engine a volume. Servono entrambi; nessuno dei due da solo basta.

### 9.2 Ruolo strategico di Board Lab

Board Lab non è una feature viewer. È **la giustificazione del tier Coach**. Senza Board Lab, non c'è motivo di pagare €39 invece di €9. Con Board Lab, il coach ha:

- Un artefatto di sessione (replay annotato con le note del coach).
- Un PDF esportabile per lo studente.
- Una pagina coach pubblica per atterrare studenti futuri.
- Un tool che gli studenti non possono replicare gratis su duels.ink.

Board Lab deve dare la sensazione di una sessione di coaching in un browser.

**Stato reale al 24/04/2026.** Oggi Board Lab vive fisicamente nel legacy (`frontend/` via `team_coaching.js`, 1936 LOC). In V3 è esposto come **stub** (`frontend_v3/assets/js/dashboard/team.js:300` "coming soon"): l'intero flusso upload → viewer animato passa ancora per il legacy bundle caricato come ultimo script in `frontend_v3/dashboard.html`.

**Per il lancio basta il minimo indispensabile:**
- Upload `.replay.gz` owner-only (ownership già in DB via migration M1 `9a1e47b3f0c2` del 24/04)
- Access-control `require_replay_access` / `require_replay_owner` (già attivo, Privacy Layer V3)
- 412 handling su upload senza consent (consent modal V3 è il gap)

**Label enrichment** (quale carta giocata, chi ha cantato, chi ha banished) e **coach flow completo** → post-launch 30 gg.

Board Lab resta la giustificazione del Coach tier. Ma non va ricostruito pre-lancio: vive nel legacy, è già funzionante lì. Il V3 lo usa via wiring minimo al primo launch.

### 9.3 Posizionamento vs Metafy

Non siamo un coach marketplace. Siamo **la workstation del coach**. Metafy possiede booking e pagamento. Noi possediamo la sessione stessa. È non-overlapping e mutuamente rinforzante: Metafy beneficia da coach che producono sessioni migliori; noi beneficiamo da coach Metafy-sourced che pagano €39/mese.

Messaggio di outreach ai coach: "Hai già studenti. Ti diamo il tool che rende la tua sessione worth double, per €39/mese, e 20% affiliate su qualsiasi studente Pro che porti."

### 9.4 Pagina coach pubblica

Ogni Coach ha una pagina pubblica a `metamonitor.app/coach/<slug>` che mostra:

- Numero studenti, trend WR improvement (aggregato, anonimizzato).
- Testimonianze.
- Link contatto (il loro Discord / Metafy / email, non il nostro).

È un tool di lead-gen per loro e un asset SEO per noi. Basso costo engineering.

---

## 10. Analisi Rischi

### 10.1 Rischio dati

| Rischio | Probabilità | Impatto | Mitigazione |
|---------|-------------|---------|-------------|
| duels.ink blocca scraping | Media (12m) | Critico | (a) 300K+ match storici restano usabili per mesi; (b) lorcanito come fonte secondaria; (c) self-upload replay player (già supportato via Board Lab); (d) simulation engine come fallback ultimo. |
| duels.ink chiude (scenario Pixelborn) | Medio-bassa | Critico | Come sopra. Più: Ravensburger potrebbe riempire il gap, diventiamo analytics del nuovo client. |
| Cease and desist Ravensburger | Bassa | Alto | Postura compliance: disclaimer unofficial, no loghi/art, dominio non-Lorcana (`metamonitor.app`), canale legal response rapido. |
| Anche lorcanito chiude | Bassa | Medio | Accelera simulation engine. Costo engine gestibile ($50-100/mese). |

Dettagli legali completi: §13 (Duels.ink) e §14 (Ravensburger). Piani di contingenza dettagliati: §15.

### 10.2 Rischio legale (pragmatico)

- No ToS pubblico su duels.ink → scraping non è violazione contrattuale.
- Match data aggregati = fatti, non copyrightable.
- Nomi carte come testo = fair use in contesto analitico.
- Immagini carte e loghi = evitare totalmente (regola compliance primaria).
- Disclaimer "Unofficial fan-made tool" in footer, About page, e copy marketing Pro.
- Replay viewer mostra **nomi avversario anonimizzati** ("Opponent A") by default. I match propri dell'utente usano la sua identità solo dentro la sua sessione loggata.
- Email contatto Legal@ per risposta rapida a qualsiasi cease-and-desist.

Stessa postura di op.gg, Mobalytics, Dotabuff, Untapped.gg. Precedente favorevole. Nessuna partnership è richiesta per operare; partnership sarebbe upside.

### 10.3 Rischio TAM

Scenario onesto: cap a 400-600 utenti paganti globali anche nel caso ottimistico. Un business €50K/anno a regime. Questo è:

- Bene come side business solo founder.
- Non bene come business venture-scale.

Se l'obiettivo è scala venture, il piano deve includere espansione multi-TCG dal mese 12 in poi. Se l'obiettivo è un indie SaaS sostenibile parallelo al day job, solo Lorcana basta.

**Questo deve essere deciso dal founder prima di decisioni di capitale.**

### 10.4 Rischio esecuzione

Founder solo, part-time, dipendente bancario. Vincoli concreti:

- ~10-15 ore/settimana realistiche.
- Contratto bancario potrebbe restrizionare attività secondarie → verifica PRIMA del revenue.
- Non puoi prendere soldi investitori senza risolvere questo legalmente (o SRL intestata a terzi o cambio employment).

Mitigazione: leggi contratto, consulta commercialista 1 ora, decidi struttura prima della prima fattura. Vedi §17 per dettaglio.

### 10.5 Rischio complessità

Ogni piano precedente era over-scope. Questo deliberatamente:
- Due SKU, non cinque.
- Un tier affiliate, non quattro.
- No SKU one-shot.
- Un momento di lancio (Set 12).
- Un focus monetizzazione (Play → Pro) + un engine B2B (Board Lab → Coach).

Resta monomaniaco su questi finché i dati non dicono diversamente.

---

## 11. Proiezioni Finanziarie (recalibrate v4.2)

Tre scenari ricalibrati su conversion rate consumer-SaaS realistici (benchmark op.gg Plus ~0.3%, hsreplay ~0.5%, indie TCG/gaming tools 1-2%). Le percentuali v4.1 (1% / 3% / 5%) erano sovrastimate di una tacca: il vecchio "Base" è ora "Ottimistico", e il nuovo "Pessimistico" 0.5% è più aderente al base-rate consumer SaaS in nicchie da 30-50K competitive players.

Tutti gli scenari assumono founder solo, no paid acquisition, **mese 0 = Set 12 launch (Settembre 2026 atteso, non Maggio come v4.1)**. I 4-5 mesi precedenti (Maggio-Agosto 2026) sono **Phase A pre-launch waitlist** (vedi §12): utenti registrati e lead crescono ma intent Pro non monetizza fino a Paddle attivo (post SRL chiusa, vedi §11.6 + §17).

### 11.1 Pessimistico (conversion ~0.5%)

| Metrica | M3 | M6 | M12 |
|---------|----|----|-----|
| Utenti registrati | 250 | 600 | 1.500 |
| Pro (€9/m) | 1 | 3 | 8 |
| Coach (€39/m) | 0 | 0 | 1 |
| Revenue Pro | €9/m | €27/m | €72/m |
| Revenue Coach | €0 | €0 | €39/m |
| **MRR totale** | **€9** | **€27** | **€111** |
| Annual run rate M12 | | | **€1.332** |

Conclusione: sotto break-even fisso (€330/m) per tutto il primo anno. Prodotto/canale/TAM da rivedere strutturalmente. **Decisione kill/pivot entro M6.**

### 11.2 Base (conversion ~1.5%, mediana consumer SaaS)

| Metrica | M3 | M6 | M12 |
|---------|----|----|-----|
| Utenti registrati | 400 | 1.200 | 3.000 |
| Pro (€9/m) | 6 | 18 | 45 |
| Coach (€39/m) | 0 | 2 | 4 |
| Revenue Pro | €54/m | €162/m | €405/m |
| Revenue Coach | €0 | €78/m | €156/m |
| **MRR totale** | **€54** | **€240** | **€561** |
| Annual run rate M12 | | | **€6.732** |

Conclusione: marginalmente sopra floor fisso (€330) **da M9-M10**, non da M6 come v4.1 ipotizzava. Side business operativo ma nessuna luxury: copre VPS/LLM/Paddle, copre commercialista solo da M10+. **Decisione M12: continua come side business o ricalibra canale.**

### 11.3 Ottimistico (conversion ~3%, coach diventano canale)

| Metrica | M3 | M6 | M12 |
|---------|----|----|-----|
| Utenti registrati | 600 | 2.000 | 5.000 |
| Pro (€9/m) | 18 | 60 | 150 |
| Coach (€39/m) | 1 | 4 | 8 |
| Revenue Pro | €162/m | €540/m | €1.350/m |
| Revenue Coach | €39/m | €156/m | €312/m |
| **MRR totale** | **€201** | **€696** | **€1.662** |
| Annual run rate M12 | | | **€19.944** |

Conclusione: corrisponde a quello che il BP v4.1 chiamava "Base". È il home-run, non la mediana. Side business sostenibile, copre tutti i costi e lascia margine reinvestimento. Soglia per considerare full-time switch o espansione multi-TCG. **Decisione M12: scale o no.**

### 11.4 Coach numbers — nota di realtà sul funnel

I numeri Coach sopra (4 a M12 Base, 8 a M12 Ottimistico) assumono **outreach sistematico 40-80 touchpoint** in Phase A (vedi §12.2) verso coach Metafy-adjacent + judges + content creator coach-track. Il piano v4.1 prevedeva 5-10 DM totali, che con conversion cold DM 10-20% → 1-2 coach max.

Senza scaling outreach, i Coach realistici sono:

| Scenario | Coach a M12 (con outreach v4.1, 5-10 DM) | Coach a M12 (con outreach scalato, 40-80 DM) |
|----------|-------------------------------------------|------------------------------------------------|
| Pessimistico | 0 | 0-1 |
| Base | 1 (€39 MRR) | 2-4 (€78-156 MRR) |
| Ottimistico | 2 (€78 MRR) | 6-8 (€234-312 MRR) |

**Decisione di scope:** o triplichi outreach Coach in Phase A, o accetti il downgrade Coach revenue (-€80 a -€230 MRR a M12 vs tabelle 11.1-11.3 sopra).

### 11.5 Costi (invariati v4.1)

| Voce | Mensile |
|------|---------|
| VPS + dominio + SSL | €22 |
| OpenAI (killer curves batch + spy) | €18 |
| Claude subscription (dev, droppable at scale) | €0-100 |
| Email service (Resend) | €0-20 |
| Paddle fees (~5% su revenue) | variabile |
| Commercialista + SRL fisso | €290/m (€3.5K/anno) |
| **Floor fisso** | **~€330/m** |

Break-even: ~40 Pro o 9 Coach. Raggiunto **scenario Base ~M9-M10**, **scenario Ottimistico ~M5-M6**, **scenario Pessimistico mai entro M12**.

### 11.6 Bancario constraint = P0 upstream

Il vincolo §17 (founder dipendente bancario, possibile incompatibilità SRL/secondary activity per CCNL bancario) è il **vero gating event di tutto §11**. Senza risoluzione, tutti i numeri sopra sono accademici: non puoi incassare legalmente. Questo P0 va chiuso nelle prime 2 settimane di Phase A (vedi §12.0), pena scivolamento del Phase B Set 12.

Tre esiti possibili:
1. **SRL personale OK** (nessuna incompatibilità contrattuale) → strada lineare, Paddle attivabile a Settembre 2026.
2. **SRL incompatibile, fiduciaria possibile** (intestata a persona di fiducia, founder consulente tecnico) → strada percorribile ma con governance esplicita su account Stripe/Paddle/dominio/banking. Rischio operativo non trascurabile.
3. **Entrambi bloccati** → riconsidera roadmap: o cambio employment, o partner co-founder con cui condividere quote, o waitlist economy permanente (non monetizzi, raccogli email per opzionalità futura). Nessuno di questi è "kill", ma ognuno cambia drasticamente §11.

---

## 12. Launch Plan — Phase A pre-launch + Phase B Set 12 (recalibrato v4.2)

**Cambio di struttura vs v4.1.** Il piano "14 giorni a launch" assumeva Set 12 a Maggio 2026 come finestra di acquisizione primaria. La verifica timing (vedi `CLAUDE.md` §Set12 readiness — *"Prossima finestra rotation attesa — Settembre 2026, non ancora annunciato ufficialmente"*) conferma che **Set 12 è atteso Settembre 2026, non Maggio**. Il piano si riorganizza in due fasi:

- **Phase A — Pre-launch waitlist economy (Maggio-Agosto 2026, ~16 settimane).** Soft launch metamonitor.app live in modalità free + fake paywall. Build email list, valida Play conversion, sblocca SRL/bancario, scala outreach Coach. Nessun "launch event" pubblico.
- **Phase B — Set 12 hard launch (Settembre 2026, finestra 14 giorni).** Quando Ravensburger annuncia Set 12 release date, attiva Set 12 Hub messaging, flip Paddle billing on, push intensivo creator/Discord/Reddit. Questo è il vero launch event.

### 12.0 Pre-condizione P0 — Bancario constraint (settimane 1-2 di Phase A)

Niente Phase B può partire senza:
1. Verifica contratto banca + regolamento interno (1h lettura founder).
2. Consulto commercialista startup digitali (1h, €50-100).
3. Decisione struttura: SRL personale (se compatibile) o SRL fiduciaria (se incompatibile, con governance esplicita su account/dominio/billing/banking).
4. Apertura SRL prima del primo intent-to-real conversion (Phase B D-day).

Senza questi 4 step chiusi entro Luglio 2026, il fake paywall resta fake all'infinito e il Phase B Settembre slitta.

### 12.1 Phase A — Settimane 1-3: Technical readiness (Maggio 2026)

I task tecnici del v4.1 §12.1 restano corretti, solo riallocati su 3 settimane invece di 7 giorni (no fretta artificiale, qualità sopra cadenza). Si lavora con `~10-15h/sett` realistiche.

| Settimana | Task | Ore |
|-----------|------|-----|
| W1 | V3 swap-ready: verifica `backend/main.py:_serve_dashboard()` flip legacy→V3 (una riga). Play conversion clarity (titolo insight + How to Respond accordion). Paywall trigger 4° matchup/giorno **DONE** via `play_gate.js`. Verifica Resend/email pipeline + Discord server live. | 12-15 |
| W2 | Privacy minima V3: consent modal port da legacy commit `1abbdd0`. 412 handling Board Lab upload. Verifica `POST /api/v1/user/consent` + GDPR export (fix `05845e3`). Board Lab wiring minimo: access-control `/api/v1/team/replay/*` + ownership M1 `9a1e47b3f0c2`. | 10-12 |
| W3 | QA mobile + desktop, tab switch, paywall triggers, consent flow, upload owner-only. **Set 12 Hub structure pronta ma disabled** (feature flag), si accende solo a annuncio Ravensburger. Verifica disclaimer footer + alias `legal@`. Soft launch pubblico metamonitor.app. | 8-10 |

**Fine W3 (~fine Maggio 2026):** V3 live su `metamonitor.app`, free tier completo, fake paywall attivo, struttura tab 7 primary invariata. Modalità "soft, no announce" — link condivisibile a chi chiede direttamente, no push organico ancora.

### 12.2 Phase A — Mesi 2-4 (Giugno-Agosto 2026): Waitlist + Coach outreach sistematico

Tempo founder ~10-15h/sett. Allocazione raccomandata:

| Attività | Ore/sett | Output 90gg target |
|----------|----------|---------------------|
| **Coach outreach sistematico** (40-80 touchpoint totali su 12 settimane = 4-7 DM/sett, CRM minimo per tracking) | 3-4h | 8-15 conversazioni avviate, 3-5 coach interessati alla beta gratuita Phase A |
| **Creator seed** (5-8 YouTuber/streamer Lorcana, gift Pro full access, hand-deliver data story personalizzata) | 2-3h | 2-3 creator engaged, 1 menzione video entro Agosto |
| **Discord presence** (2-3 server IT/EU/NA, rispondere a domande con screenshot, no spam) | 3-4h | Trust building, 50-150 utenti registrati referenziali |
| **Asset content low-burn** (1 thread X o post Reddit/sett con matchup matrix screenshot) | 1-2h | 100-300 visite/post organic, slow burn email capture |
| **Bug fix + small UX polish** | 2-3h | Mantieni qualità, no nuove feature |

**Cosa NON si fa Mesi 2-4:**
- No Set 12 Hub push (è disabled, lo accendi solo a annuncio Ravensburger).
- No paid ads.
- No comunicato stampa.
- No nuove feature core (Board Lab refactor, Improve restructure, Country segmentation → tutto post Phase B).

**Target fine Phase A (fine Agosto 2026):**
- 200-500 utenti registrati.
- 80-150 email in waitlist.
- 50-100 membri Discord.
- 20-50 intent-to-pay registrati via fake paywall (segnale WTP, validation pre-Paddle).
- 3-5 coach in conversazione attiva (1-2 confermati per Phase B beta).
- SRL aperta, Paddle account configurato, billing pronto da accendere.

### 12.3 Phase B — Settembre 2026: Set 12 hard launch (finestra 14 giorni)

Trigger: Ravensburger annuncia Set 12 release date. Da quel momento, finestra di **2 settimane intense** (rimette il founder a ~25-30h/sett per 14 giorni).

| Giorno | Task | Ore |
|--------|------|-----|
| D-7 a D-1 | Set 12 Meta Preview content (10-15 predizioni matchup ancorate alle killer curves esistenti). PDF gated email (WeasyPrint da markdown). Demo video 60s (tab Play → killer curve). 5 screenshot social. | 18-22 |
| D-3 | Flip Paddle billing on. Test conversion fake → real su 1-2 utenti waitlist disponibili. | 2-3 |
| D-day | Set 12 release: attiva Set 12 Hub feature flag. Newsletter alla email list. Annuncio Discord (IT + EU + NA). Thread X con matrix. Post Reddit r/Lorcana. | 6-8 |
| D+1 a D+7 | Push outreach personale (DM 8-12 creator + 5-10 coach con angolo Set 12 specifico). Live tweets/threads. Monitor signups + conversion. | 3-4h/giorno |
| D+7 a D+14 | Misurazione: cosa converte, cosa no. Iterazione copy paywall, fix bug bloccanti. **Nessuna nuova feature.** | 2-3h/giorno |

**Target fine Phase B (D+14):**
- +400-800 utenti registrati (delta vs fine Phase A).
- +100-200 email aggiuntive in waitlist.
- 10-30 conversioni Pro reali (€90-270 MRR).
- 1-2 conversioni Coach reali (€39-78 MRR).
- Conversion rate fake→real misurato su almeno 30 utenti (calibra modello §11).

### 12.4 Gate decisione Phase B+30 (Ottobre 2026)

Guarda i numeri post-lancio (con la nuova scala v4.2):

- **Conversion > 2%**: scala. Considera light paid retargeting (€50-100/sett su Reddit Lorcana ads), valuta creator part-time (€200-400/mese).
- **Conversion 0.5-2%**: il prodotto converte ma sotto-canale. Raddoppia outreach creator/coach, considera affiliate aggressivo (30% recurring, non 20%).
- **Conversion < 0.5%**: **stop scaling**. Intervista 10 utenti registrati non-paganti. Diagnosi prodotto vs prezzo vs canale. Non scrivere altro codice finché la diagnosi non è chiara. Decisione kill/pivot entro Dicembre 2026.

### 12.5 Cosa il Phase B NON include

- No Product Hunt launch (audience sbagliata).
- No paid ads pre-D+30.
- No comunicato stampa generalist.
- No espansione multi-TCG announce (resta opzione M12+).
- No annuncio pubblico tier Pro fino a D+14 metriche confermano che il funnel funziona.

---

# Sezioni Ereditate dalla v3.1 (22/04) — ancora valide

Le sezioni sotto (§13-§18) vengono da `analisidef/BUSINESS_PLAN.md` v3.1 del 22/04, preservate qui perché il riscritto strategist di oggi non le copre ma restano corrette e operative.

---

## 13. Landscape legale duels.ink

### 13.1 Stato attuale

- Accesso via API non documentate (leaderboard, meta stats)
- Richiede session cookie per autenticazione (solo Board Lab upload)
- Nessun accordo formale
- **Rischio critico:** possono bloccare l'accesso in qualsiasi momento

### 13.2 Analisi legale documenti pubblici

**Cosa dicono i documenti pubblici di Duels:**
- **Nessuna pagina Terms of Service pubblica.** Il sito ha solo Privacy Policy e About, nessun ToS/User Agreement/EULA. Legalmente rilevante: senza ToS non c'è contratto esplicito che l'utente (o un terzo come noi) accetta, quindi nessuna clausola "no scraping" vincolante.
- **Privacy Policy** copre solo raccolta dati utente (Discord/Google OAuth, game states storati per review). Non menziona scraping, accesso automatizzato, uso commerciale di terzi, proprietà match data.
- **About** dichiara esplicitamente: *"free, unofficial fan-made simulator"*, *"not affiliated with, endorsed by, or sponsored by Disney or Ravensburger"*, operano *"under Ravensburger's Fan Content Policy"*.
- **Clausola chiave:** *"We are expressly prohibited from charging you to use or access this content."* Duels stessi non possono monetizzare. Questa frase viene probabilmente dalla loro auto-interpretazione cautelativa — **non** risulta da Community Code o Marketing Materials Policy pubblici. In ogni caso: **Duels non ha i diritti commerciali per darci partnership formali monetizzabili**, perché loro stessi non ce li hanno.

**Cosa significa per noi:**
- Scrapare Duels senza ToS espliciti: **rischio legale basso** (nessun contratto violato, dati match aggregati sono fatti non opere creative di Duels).
- Non avere risposta alle nostre email (2 tentativi 10/04 e 17/04) **non è ostilità**: è strutturale. Non possono offrire ciò che non hanno.
- Il vero interlocutore legale per il nostro prodotto è **Ravensburger**, non Duels (vedi §14).

**Email contatto Duels:** contact@duels.ink (silente dopo 2 outreach 10/04 e 17/04).

### 13.3 Strategia outreach — archiviata

**Stato outreach al 20 Aprile 2026:** 2 email inviate (v5 il 10/04, follow-up il 17/04), nessuna risposta. L'analisi legale sopra spiega strutturalmente perché. **Decisione: sospendere ulteriori outreach a Duels come partner commerciale.** Proseguire come tool di terze parti in good standing, focalizzare energie su Ravensburger (interlocutore legale reale) e Piano C simulazione (§15).

### 13.4 Posizionamento — non competiamo con nessuno

| Attore | Ruolo loro | Nostro valore per loro |
|--------|------------|------------------------|
| **duels.ink** | Simulatore, match engine | Portiamo utenti engaged, analytics geo-segmentati che non hanno |
| **lorcanito** | Simulatore, engine open source | Portiamo visibilità, possibile integrazione dati |
| **Ravensburger** | IP owner, eventi ufficiali | Promuoviamo il gioco in mercati che si spengono, gratis |
| **Youtuber/pro** | Contenuti, audience | Diamo dati esclusivi per video, non rubiamo audience |
| **Negozi** | Retail, eventi | Diamo visibilità ai tornei, non vendiamo carte |
| **Coach (Metafy)** | Sessioni 1:1 | Diamo tool data-driven, non rubiamo studenti |

Tutti ci guadagnano. Nessuno si sente minacciato.

### 13.5 Strategia lorcanito (fonte secondaria)

Lorcanito è il secondo simulatore (~200-400 match/giorno, 2056 ranked, log superiori a duels.ink). Engine open source (MIT, `TheCardGoat/lorcana-engine`).

**Pitch:** stessa leva di duels.ink — credito, link, nickname bridge, community push.
**Cosa chiedere:** API per export match log (oggi solo client-side IndexedDB/Nakama), o endpoint history per nickname.
**Leva:** avere entrambi i simulatori integrati ci rende la piattaforma analytics di riferimento.

---

## 14. Landscape legale Ravensburger

**Conclusione: il nostro prodotto non ha divieti espliciti ed opera in zona tollerata, stessa posizione di tutti i tool analytics TCG esistenti (op.gg, Mobalytics, Untapped, Dotabuff).**

### 14.1 Documenti analizzati

| Documento | Scope | Applicabilità |
|-----------|-------|---------------|
| **Community Code** (effective 10 May 2023) | Comportamento community (no cheating, no harassment, no contenuti adulti, no impersonation Ravensburger) | Indiretta — ci vincola a non violare il codice |
| **Hobby Store Program T&C** | Licenza uso marketing materials per negozi fisici approvati | **Non applicabile** — riguarda solo negozi retail |
| **Marketing Materials Policy** | Uso materiali promozionali forniti agli HSP | **Non applicabile** — noi non riceviamo materiali |
| **Content Creation FAQ** | Content creator via Ambassador Program (Klear) | Opt-in — non dipendiamo |
| **Legal Notice disneylorcana.com** | Copyright/trademark generico | Applicabile come a qualsiasi uso IP Disney/Lorcana |

### 14.2 Community Code — cosa NON dice

- Nessun divieto esplicito di tool di terze parti
- Nessun divieto di monetizzazione (Pro tier, subscription)
- Nessun divieto di scraping / API non documentate
- Nessun divieto di Patreon, advertising, revenue share
- Nessuna clausola tipo "Fan Content Policy" stile Wizards of the Coast o Blizzard

### 14.3 Community Code — cosa dice e ci riguarda

- *"Creation, use, sale, trade, or distribution of counterfeit or unauthorized Ravensburger names or products"* — rilevante se usiamo loghi/immagini carte, non rilevante se usiamo solo dati aggregati e nomi carte come testo (fair use analitico).
- Clausola **"Future-Proofing" / "sole discretion"**: *"whether an action is in violation, in letter or spirit [...], is to be determined at the sole discretion of Ravensburger and the Disney Lorcana Organized Play Team"*. **Questo è il rischio residuo principale** — possono decidere arbitrariamente che siamo in violazione.

### 14.4 Companion App ufficiale Ravensburger

Launched 2023 a Gen Con, gratuita iOS/Android, include deck building + collection tracker + game guides. Implicazioni:
- **Positivo:** il concept "app Lorcana di terzi" non è ostile di per sé, loro stessi lo fanno.
- **Negativo:** siamo nello stesso spazio prodotto. Se Lorcana Monitor cresce, possono vederci come competitor del loro ecosistema. Mitigazione: posizionarci su analytics competitivo (non coperto dalla Companion App), non su deck building casual.

### 14.5 Matrice rischio per azione

| Azione | Rischio legale | Note |
|--------|----------------|------|
| Scrapare Duels.ink | Basso | No ToS violato, dati aggregati = fatti |
| Aggregare winrate/matchup | Basso | Fatti, non opere creative |
| Usare nomi carte come testo | Basso | Fair use in contesto analitico |
| Monetizzare Pro tier su analytics | Medio | Nessun divieto esplicito, ma clausola "sole discretion" resta |
| Usare immagini carte | **Alto** | Copyright Disney/Ravensburger |
| Usare loghi "Disney Lorcana" | **Alto** | Trademark |
| Dire "official" o "endorsed" | **Alto** | Impersonation, violazione Community Code |
| Generare match simulati (Piano C) | Basso | Dati nostri, pulito legalmente |

### 14.6 Checklist protettiva (implementare pre-launch pubblico)

1. Footer + About page con disclaimer esplicito: *"Lorcana Monitor is an unofficial fan-made analytics tool. Not affiliated with, endorsed by, or sponsored by Disney or Ravensburger. Disney Lorcana TCG is a trademark of Disney and Ravensburger."* — **già implementato** (Privacy Layer V3, 24/04).
2. Zero loghi Disney/Lorcana nel prodotto e nel marketing.
3. Zero immagini carte (o thumbnail piccoli con attribuzione, zona grigia ma tollerata dagli altri tool TCG — decidere caso per caso).
4. Nomi carte come testo è OK.
5. Statement "Community Code compliant" visibile nel footer.
6. Canale contatto pubblico (`legal@metamonitor.app` alias Cloudflare pendente — oggi `monitorteamfe@gmail.com`) per eventuali cease & desist.
7. Brand name / dominio / payment descriptor: NON enfatizzare "Lorcana" — già fatto: `metamonitor.app`.

**Bottom line:** monetizzare analytics Lorcana via SaaS è fattibile. Non è zona grigia oscura, è zona "tollerata come tutti gli altri analytics tool TCG esistenti". **Non servono partnership formali con Duels o Ravensburger per operare legalmente.**

---

## 15. Piani di Contingenza Dati

Dipendenza critica: la fonte dati primaria (duels.ink) può sparire per 3 motivi — Ravensburger chiude il simulatore (come Pixelborn), duels.ink ci blocca, o duels.ink muore per mancanza di fondi. Serve un piano per ogni scenario.

### 15.1 Piano A — Fonti alternative reali (attivabile in 2-4 settimane)

**A1. Lorcanito.com**
Secondo simulatore, ~200-400 match/giorno, 2056 ranked, log di qualità superiore a duels.ink.
- **Problema:** dati solo client-side (IndexedDB/Nakama), no API batch
- **Azione:** contattare per partnership dati
- **Open source:** engine MIT su GitHub (`TheCardGoat/lorcana-engine`)

**A2. inkDecks.com**
Database tornei ufficiali (già attivo via `decks_db_builder.py`).

**A3. Player Self-Import**
Giocatore esporta `.replay.gz` e lo carica in Board Lab. Già funzionante.

### 15.2 Piano B — Client ufficiale Ravensburger (medio termine 12-24 mesi)

Se Ravensburger lancia client digitale ufficiale:
- Diventiamo **partner analytics naturale** — unico tool con 12+ mesi di pipeline
- Client ufficiale avrà API documentate → accesso più pulito
- Dati storici (50K+ match) restano unici
- Il prodotto funziona identico: cambia solo la fonte

### 15.3 Piano C — Simulazione AI (indipendenza totale)

**L'idea: generare match sintetici con AI e analizzarli con la nostra pipeline.**

```
Engine Lorcana (regole)     ← open source MIT (TheCardGoat/lorcana-engine)
     +
Agent AI (decisioni)        ← heuristic (90%) + LLM decisioni complesse (10%)
     ↓
Match log sintetico         ← stesso formato dei match reali
     ↓
Pipeline esistente          ← investigate → archive → digest → killer curves
```

**Costi stimati:**
- Engine: fork open source + adattamento (~1-2 settimane)
- Agent heuristic: ~1 settimana
- Agent LLM solo decisioni chiave: ~$0.001/match
- **10.000 match simulati per matchup: ~$10 e qualche ora compute**
- Costo mensile (tutti i 132 matchup): ~$50-100

**Vantaggi unici:**

| Vantaggio | Dettaglio |
|-----------|-----------|
| **Indipendenza totale** | Zero dipendenza da duels.ink, lorcanito, chiunque |
| **Volume on demand** | 10K match per matchup → statistiche solidissime |
| **Espansione day-one** | Simuliamo match con carte nuove PRIMA dei match reali |
| **What-if analysis** | "Se taglio Ward da Stitch?" → 1000 partite → risposta |
| **Meta predittivo** | "Se esce questa carta, come cambia il meta?" → valore enorme |
| **Deck optimizer validato** | Optimizer propone → 1000 simulazioni → validazione statistica |
| **Contenuto esclusivo** | Nessun competitor può fare meta predictions pre-espansione |

**Raccomandazione: attivare Piano C in parallelo come feature premium (meta predictions, what-if) anche PRIMA di perdere duels.ink. È sia contingency che differenziatore di prodotto.**

### 15.4 Confronto Piani

| | Piano A | Piano B | Piano C |
|---|---|---|---|
| **Quando** | 2-4 settimane | 12-24 mesi | 4-5 settimane |
| **Costo** | $0 | $0 | ~$50-100/mese |
| **Volume** | 200-400/giorno | Dipende Ravensburger | Illimitato |
| **Qualità** | Reale | Reale | Sintetica (calibrare) |
| **Indipendenza** | Parziale | Parziale | **Totale** |
| **Meta prediction** | No | No | **Sì** |
| **What-if** | No | No | **Sì** |

---

## 16. Tech Moat — Cosa Non Si Replica

Vantaggio competitivo tecnico. Un competitor che volesse replicare Lorcana Monitor oggi dovrebbe:

**1. Dati (6+ mesi di raccolta)**
- 50K+ match log turno per turno (non solo risultati)
- Play detail con `ink_paid`, `is_shift`, `is_sung` per ogni carta
- Ability log con effetti runtime
- Board state ricostruito per ogni half-turn
- Nessuna API pubblica offre questi dati — serve monitor attivo

**2. Pipeline di analisi (3+ mesi di sviluppo)**
- Loss classification a 9 dimensioni + alert heuristici
- Loss detection 3 livelli: keywords × abilities × patterns
- Ability profile auto-parsed per 2800+ carte (trigger + effects + scope)
- 7 flag meccanici data-driven (zero carte hardcodate)
- Loss profiles con example games diversificate
- Digest compatto per LLM (~50KB da archivi 2-14MB)

**3. LLM pipeline (2+ mesi di tuning)**
- 268 killer curves validate (9 check automatici, 0 FAIL)
- Prompt monolitico ottimizzato (~60-80KB, ~15-20K token)
- Color guard dinamico (nessuna lista hardcodata)
- Our Playbook: neutralizzazioni, win behavior, key combos, singer tips
- Postfix automatico (`is_shift`, `is_sung`, nomi, response colors)
- Triage stabilità (STABLE/UNSTABLE) per update incrementale
- KC Spy: canary giornaliero + auto-fix

**4. Community + network (non replicabile)**
- Youtuber, judge, pro player — relazioni personali
- Rete negozi italiani
- Credibilità nella scena competitiva

**Tempo stimato per replicare da zero: 12-18 mesi + competenze LLM + rete community.**

---

## 17. Struttura Fiscale e Societaria

### 17.1 Vincolo: Founder Dipendente Bancario

Il founder è dipendente bancario con RAL > 30K EUR. Questo impone vincoli specifici:

- **Forfettario escluso** — regime forfettario richiede reddito dipendente < 30K EUR/anno
- **Incompatibilità bancaria** — CCNL bancario e molti regolamenti interni richiedono autorizzazione per attività secondarie o le vietano
- **Socio/amministratore SRL** — potrebbe essere incompatibile col ruolo bancario

**Azione prioritaria:** verificare contratto di lavoro e regolamento interno banca prima di aprire qualsiasi posizione fiscale.

### 17.2 Strategia Raccomandata

**Fase 0 — Pre-revenue (ora)**
- NON aprire nulla. Sviluppa prodotto, valida mercato, contatta creator.
- Verifica vincolo bancario (contratto + regolamento interno).
- Consulto commercialista specializzato in startup digitali (1h, 50-100 EUR).
- Nessun obbligo fiscale finché non incassi.

**Fase 1 — Primi clienti (3-5 clienti paganti confermati)**
- Apri SRL (o SRL innovativa se qualifichi).
- Se incompatibilità bancaria: SRL intestata a persona di fiducia, tu come consulente tecnico informale.
- Costo costituzione: ~1.000 EUR (notaio + CCIAA).
- Commercialista: ~3.000-5.000 EUR/anno.

**Fase 2 — Scale (revenue > 50K/anno)**
- Valuta transizione a SRL innovativa per credito R&D.
- Valuta se lasciare il lavoro bancario (quando revenue > stipendio netto).

### 17.3 Paddle come Merchant of Record

Per eliminare complessità IVA internazionale:

| | Stripe (tu vendi) | Paddle (Paddle vende) |
|---|-------------------|------------------------|
| IVA | Tu la gestisci (OSS, dichiarazioni per paese) | Paddle gestisce tutto |
| Fatture ai clienti | Tu le emetti | Paddle le emette |
| Tu ricevi | Pagamenti da clienti (con IVA da versare) | Una fattura B2B da Paddle (netto commissioni) |
| Fee | 2.9% + 0.25 EUR | 5-8% |
| Complessità contabile | Alta | Minima |

**Costo extra Paddle vs Stripe:** ~2-5% revenue in più. Vale la pena per semplicità contabile.

### 17.4 Proiezione Fiscale Anno 1 (SRL + Paddle, scenario Base €15K revenue)

```
Revenue lorda:                          15.000 EUR
- Paddle fee (5%):                        -750 EUR
= Fatturato SRL:                        14.250 EUR
- Costi deducibili (VPS, LLM, commercialista, tools): ~5.620 EUR
= Utile ante imposte:                    8.630 EUR
- IRES 24%:                              -2.071 EUR
- IRAP 3.9%:                               -337 EUR
= Utile netto SRL:                       6.222 EUR

Distribuendo dividendi (ritenuta 26%):   4.604 EUR netto (31% revenue lordo)
Lasciando nella SRL (reinvesti):         6.222 EUR disponibile crescita
```

**Confronto P.IVA ordinaria:** stessa revenue, IRPEF 43% + INPS 26% = netto ~4.200 EUR. La SRL conviene già dal primo anno.

---

## 18. Deliberately Absent Features

Quello che **scegliamo di non fare** è importante quanto quello che facciamo. Ogni feature in questa tabella è stata considerata e scartata perché viola uno dei 4 principi ecosystem design (§8.3).

| Feature evitata | Motivo | Chi danneggerebbe | Principio violato |
|-----------------|--------|-------------------|-------------------|
| Sessione 1:1 personal coaching | Lane di Metafy | Metafy | P1 Teaching≠Coaching, P3 Don't extract |
| Coach marketplace (booking, payment split) | Complesso + Metafy lo fa già | Metafy, noi stessi | P2 Support don't replace |
| Autorità "meta oracle" | Lane di Lorcanito | Lorcanito, Duels | P3 Don't extract |
| Paid tournament con montepremi | Community Code Ravensburger lo vieta | Ravensburger | P3 Don't extract (legal) |
| Card price tracker / marketplace | Lane TCGPlayer / Dreamborn / negozi | Negozi online, LGS | P3 Don't extract |
| Card selling / trading | Lane LGS e negozi | LGS | P3 Don't extract, P4 tabletop |
| Esclusiva su replay ufficiali | Non è nostro diritto | Ravensburger, Duels | P3 Don't extract |
| Digital-only brand identity | Alienerebbe Ravensburger, LGS | Ravensburger, LGS | P4 Tabletop is endgame |
| Anti-cheat / reporting tool verso Duels | Non è il nostro ruolo | Duels, Ravensburger | P2 Support don't replace |
| API pubblica gratis dei dati aggregati | Toglierebbe ragione d'essere al Pro tier | Noi stessi | Sostenibilità |
| Coaching AI automatizzato ("chiedi al bot") | Crossa linea verso Metafy | Metafy | P1 Teaching≠Coaching |
| Cheat sheet live durante partita su Duels | Genera backlash Ravensburger | Ravensburger, Duels | P3, P4 |
| Branding Disney/Lorcana nel dominio/UI | Copyright + percezione official impropria | Ravensburger | Legal |

**Regola operativa:** quando arriva una nuova feature idea, prima di svilupparla passa per questa tabella. Se appartiene a una di queste categorie, si scarta. Se è nuova ma viola un principio, si aggiunge qui.

---

## Verifica finale

- [x] Eseguibile da 1 persona, part-time
- [x] Phase A pre-launch (Mag-Ago) + Phase B Set 12 hard launch (Set 2026) — timing allineato a Ravensburger reale
- [x] Nessuna dipendenza da feature non esistenti
- [x] Tutte feature core preservate (killer curves, Play, Replay Viewer, Board Lab, Meta, Deck, Mulligan, Community)
- [x] Un core value driver identificato (Play + killer curves)
- [x] Board Lab posizionato come coaching tool, non side feature
- [x] Rischio dati riconosciuto, mitigato (Piano A+B+C)
- [x] Legale pragmatico, non over-focused
- [x] TAM onesto (30-50K competitive → 1-3K paying realistic, 3-8K cap teorico)
- [x] Solo 2 SKU, pricing defendible (€9 Pro / €39 Coach)
- [x] Conversion rate scenari ricalibrati su benchmark consumer-SaaS reali (0.5% / 1.5% / 3%)
- [x] Decision gate definiti (M6 kill/pivot, M12 scale/continue, Phase B+30 canale)
- [x] Feature esplicitamente escluse documentate
- [x] Struttura fiscale coperta (SRL + Paddle + vincolo bancario)
- [x] Vincolo bancario marcato come P0 upstream (§11.6 + §12.0) — gate prerequisito di Phase B
- [x] Rischio legale coperto (Duels ToS + Ravensburger Community Code)
- [x] Coach outreach sizing realistico (40-80 touchpoint, non 5-10)

Plan finalizzato — v4.2.

---

*Documento consolidato il 24 Aprile 2026 da:*
- *`analisidef/business/BP_STRATEGIST_POINT.md` (Refined v1, GPT 24/04 06:48) — base §1-§12*
- *`analisidef/BUSINESS_PLAN.md` (v3.1, 22/04) — §13-§18 ereditati*
- *Complementari: `V3_ARCHITECT_POINT.md` (architettura/overview V3) e `TODO.md` (operativo).*

*Patch v4.2 (26 Aprile 2026): timing Set 12 corretto a Settembre, conversion ricalibrate, launch plan ristrutturato in Phase A + Phase B, vincolo bancario marcato P0.*
