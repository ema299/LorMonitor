# Frontend V3

Nuovo workspace frontend separato dal live.

Obiettivo:

- partire da una copia fedele della dashboard `8100`
- snellire il monolite senza perdere oggetti, badge, immagini e densita'
- riposizionare gli oggetti dentro la nuova IA
- fare il restyling solo dopo il riposizionamento

Vincoli:

- non toccare `frontend/`
- non toccare `backend/`
- non toccare Python o serving live
- non disturbare `127.0.0.1:8100`
- sfruttare gli stessi input, gli stessi endpoint e gli stessi script Python gia' esistenti

Stato attuale della base:

- `dashboard.html` e' la copia V3 della dashboard live dentro workspace separato
- il grosso CSS inline e il grosso JS inline sono stati estratti in asset dedicati
- il dominio `monitor` e' stato separato in `assets/js/dashboard/monitor.js`
- il dominio `profile` e' stato separato in `assets/js/dashboard/profile.js`
- i domini `community` e `events` sono stati separati in `assets/js/dashboard/community_events.js`
- il dominio `team` e' stato separato in `assets/js/dashboard/team.js`
- il dominio `coach_v2` e il replay viewer sono stati separati in `assets/js/dashboard/coach_v2.js`
- il dominio `lab` e' stato separato in `assets/js/dashboard/lab.js`
- la UI condivisa residua e' stata separata in `assets/js/dashboard/shared_ui.js`
- `v3.html` punta alla baseline `dashboard.html` come entrypoint comodo
- la shell sperimentale modulare resta disponibile dentro `assets/js/` come materiale di supporto, ma non e' il flusso principale di questa fase

Documenti guida V3:

- `frontend_v3/docs/ARCHITECTURE.md`
- `frontend_v3/docs/MILESTONES.md`
- `frontend_v3/docs/PREVIEW_SERVER.md`

Nota:

`frontend_v2/` e' stato rimosso il 2026-04-22 (nessuna dipendenza runtime, nessun consumer). Il redesign attivo vive qui.
