# Frontend Legacy Seal Checklist

Data: 2026-04-20
Stato: complete
Owner: Codex

## Scopo

Checklist finale per dichiarare il frontend live pronto a convivere con una futura `frontend_v2/` senza contaminazioni architetturali.

## Checklist

- [x] `frontend/` identificato come unico perimetro del prodotto live
- [x] `frontend_v2/` esclusa da ogni dipendenza del legacy
- [x] serving contract del legacy documentato
- [x] file applicativi del legacy mappati
- [x] endpoint backend usati dal legacy mappati
- [x] chiavi `localStorage` usate dal legacy mappate
- [x] dipendenze esterne effettive del legacy mappate
- [x] fallback CDN non essenziale rimosso dal boot del frontend
- [x] path applicativo critico `team_coaching.js` reso relativo
- [x] regole di separazione tra v1 e v2 documentate
- [x] nessun cambiamento richiesto a `ARCHITECTURE.md`
- [x] nessun cambiamento richiesto a `.py` in `lib/`

## Decisione

Il legacy e' considerato architetturalmente blindato per l'avvio della fase successiva.

Questo autorizza:

- scaffold della futura `frontend_v2/`

Questo non autorizza ancora:

- redesign dentro `frontend/`
- condivisione opportunistica di JS/CSS tra legacy e v2
- refactor backend trainato da naming o IA della nuova UI
