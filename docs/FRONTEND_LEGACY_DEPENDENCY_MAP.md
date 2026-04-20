# Frontend Legacy Dependency Map

Data: 2026-04-20
Stato: sealed
Owner: Codex

## 1. Scopo

Questo documento definisce il perimetro del frontend live attuale.

Serve a tre cose:

- rendere esplicite le dipendenze reali del legacy
- impedire accoppiamenti accidentali con `frontend_v2/`
- fissare un contratto minimo prima del redesign

## 2. Frontend legacy in scope

Il frontend live attuale e' composto da:

- `frontend/dashboard.html`
- `frontend/assets/js/team_coaching.js`
- `frontend/assets/js/api.js`
- `frontend/assets/css/app.css`
- `frontend/chart.min.js`
- `frontend/manifest.json`
- `frontend/sw.js`
- `frontend/icon-192.svg`
- `frontend/icon-512.svg`
- `frontend/deck_icons/*`

## 3. Serving contract

Il backend attuale serve il legacy in questo modo:

- `/` -> `frontend/dashboard.html`
- `/dashboard.html` -> `frontend/dashboard.html`
- statici -> mount di `frontend/`

Questo implica che il legacy deve restare autosufficiente dentro `frontend/`.

## 4. Approved internal dependencies

Dipendenze interne deliberate del legacy:

- `dashboard.html` -> `chart.min.js`
- `dashboard.html` -> `manifest.json`
- `dashboard.html` -> `icon-192.svg`
- `dashboard.html` -> `assets/js/team_coaching.js`
- `team_coaching.js` -> endpoint backend pubblici necessari al replay/team flow
- `dashboard.html` -> endpoint backend dashboard, profile, lab, coach, replay, news

## 5. Approved backend dependencies

Endpoint osservati e considerati parte del contratto attuale:

- `/api/v1/dashboard-data`
- `/api/v1/news/ticker`
- `/api/v1/lab/tournament-lists/:deck`
- `/api/v1/lab/iwd/:our/:opp`
- `/api/v1/profile/blind-playbook/:deck`
- `/api/v1/team/replay/:game_id`
- `/api/replay/cards_db`
- `/api/replay/list`
- `/api/replay/game`
- `/api/replay/public-log`
- `/api/decks`

Nota:

- i nomi dei tab UI non definiscono i contratti backend
- il redesign non deve rinominare o spostare questi endpoint solo per motivi UX

## 6. External dependencies

Dipendenze esterne deliberate rimaste nel legacy:

- `cards.duels.ink` per thumbnail card art
- `img.youtube.com` per preview thumbnail nella tab Community
- `youtube.com` per embed video nella tab Community
- `player.twitch.tv` per eventuale embed live Twitch nella tab Community
- `unpkg.com/leaflet@1.9.4` per CSS/JS Leaflet caricati on demand nella tab Events
- `tile.openstreetmap.org` per tile map nella tab Events

Dipendenze esterne rimosse in questa fase:

- fallback CDN di Chart.js via `cdn.jsdelivr.net`

Ragione:

- il legacy deve dipendere da asset locali quando possibile
- le dipendenze esterne non essenziali aumentano fragilita' e comportamenti non deterministici
- le dipendenze esterne rimaste sono legate a feature deliberate del prodotto live, non a scorciatoie di boot della UI

## 7. Browser storage contract

Chiavi `localStorage` osservate nel legacy:

- `lorcana_format`
- `lorcana_my_deck`
- `lorcana_deck_code`
- `lorcana_deck_name`
- `lorcana_deck_id`
- `lorcana_deck_history`
- `pf_email`
- `pf_duels_nick`
- `pf_lorca_nick`
- `pf_country`
- `pf_deck`
- `pf_deck_pins`
- `pf_demo`
- `pf_studied_mus`
- `comm_clips_seen`
- `tt_notes_<nick>`
- `tt_archived_alerts`

Regola:

- queste chiavi sono parte del comportamento legacy
- `frontend_v2/` non deve riutilizzarle in modo implicito senza decisione esplicita

## 8. Seal rules

Da questo momento il legacy segue queste regole:

- nessun file nuovo del legacy viene creato in `frontend_v2/`
- nessun file nuovo della v2 viene importato da `frontend/`
- niente condivisione opportunistica di JS/CSS applicativi tra v1 e v2
- ogni fix nel legacy deve essere conservativo e orientato alla stabilita'
- ogni lavoro di redesign nasce solo in `frontend_v2/`

## 9. Fix applied to support sealing

Fix conservativi applicati:

- `dashboard.html` ora carica `assets/js/team_coaching.js` con path relativo invece che assoluto
- rimosso fallback remoto di Chart.js, mantenendo il file locale `chart.min.js`

Effetto:

- il frontend legacy e' meno dipendente dal contesto di serving
- si riduce il rischio che una preview o una v2 peschi asset del live per errore
- si riduce una dipendenza esterna non necessaria

## 10. What remains intentionally coupled

Accoppiamenti intenzionali che restano:

- backend shared
- dati live shared
- storage browser dell'utente
- thumbnail card art esterne da `cards.duels.ink`
- servizi embed/media esterni per Community
- servizi mappe esterni per Events

Questi non vanno cambiati durante il seal del legacy.

## 11. Seal completion criteria

Il legacy si considera blindato quando tutte queste condizioni sono vere:

- perimetro file in scope dichiarato
- serving contract dichiarato
- endpoint backend usati dichiarati
- chiavi storage dichiarate
- dipendenze esterne effettive dichiarate
- path applicativi critici resi non ambigui
- nessuna dipendenza dal futuro `frontend_v2/`
- nessun TODO architetturale aperto dentro il legacy per consentire la nascita della v2

Stato corrente:

- completato

Nota:

- questo non significa che il legacy sia "finito" come prodotto
- significa che il suo perimetro architetturale e' ora esplicito, stabile e separabile dalla futura v2

## 12. Next step

Il prossimo passo non e' il redesign.

Il prossimo passo e':

- scaffold pulito di `frontend_v2/`
- regole di serving della v2 senza contaminare il live
- poi nuova IA e restyling
