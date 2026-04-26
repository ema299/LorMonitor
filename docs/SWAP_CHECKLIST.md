# V3 Swap Checklist — Pre-launch runbook

**Scope:** chiudere il pre-launch (Sezione A) trasferendo V3 da staging
(`frontend_v3/`) a serving live, con backend allineato e smoke verde.

**Stato al 26/04/2026:**
- 35 commit ahead di `origin/dev`, no push
- 2 migrations applicate sul DB (`b8e72d4a9c3f` session notes, `c4f9e1d8a2b6` user_consents)
- Backend live `:8100` ancora con bytecode pre-restart → endpoint nuovi rispondono 405
- A.5 V3 swap PENDING come ULTIMA azione
- A.5 QA end-to-end PENDING (manuale, 1 dev day)
- A.1 alias mail Cloudflare PENDING (ops DNS, non-code)

---

## Step 1 — Pre-flight (verifica stato)

```bash
# Branch + commit ahead
cd /mnt/HC_Volume_104764377/finanza/Lor/Analisi_deck/App_tool
git status
git log --oneline origin/dev..HEAD

# Alembic head allineato
venv/bin/alembic current
# atteso: c4f9e1d8a2b6 (head)
venv/bin/alembic heads
# atteso: 7894044b7dd3 (Set12 cassetto, dormant) + c4f9e1d8a2b6 (current)

# DB tabelle nuove esistono
psql -c "\dt replay_session_notes" -c "\dt user_consents"
```

**Se alembic non è a `c4f9e1d8a2b6`:** apply esplicitamente (NON `upgrade head` —
romperebbe il cassetto Set12):

```bash
venv/bin/alembic upgrade c4f9e1d8a2b6
```

---

## Step 2 — Backend restart (attiva endpoint nuovi)

I nuovi endpoint in `b8e72d4a9c3f` + `c4f9e1d8a2b6` non sono live finché il
service non ricarica il bytecode. Senza restart, `DELETE replay`, `notes`
round-trip e `GET /consents` rispondono 405.

```bash
sudo systemctl restart lorcana-api
sleep 3
curl -s http://localhost:8100/api/v1/health
# atteso: {"status":"ok"}

# Verifica nuovi endpoint registrati
curl -s -X DELETE http://localhost:8100/api/v1/team/replay/__smoke__
# atteso: 401 (auth required) — NON 405 (method not allowed)
```

Se 405: bytecode non ricaricato → re-run `daemon-reload` + restart.

---

## Step 3 — Smoke test live (token-based)

Servono token JWT reali per coverage completa. Skip-friendly se mancano.

```bash
# Token setup (esempio — usa account test reali)
export USER_A_TOKEN="eyJhbGc..."
export USER_B_TOKEN="eyJhbGc..."
export USER_A_GAME_ID="xxxx-yyyy-zzzz"  # disposable, T5 lo CANCELLA
export ADMIN_TOKEN="eyJhbGc..."

# Privacy layer (8 check, copre Privacy V3 + B.2 notes + B.3 consents)
venv/bin/python3 scripts/privacy_smoke_test.py --base http://localhost:8100

# Replay ownership round-trip (7 check, copre B.2 + B.3)
venv/bin/python3 scripts/replay_ownership_smoke.py --base http://localhost:8100
```

**Atteso:**
- T1 schema columns + endpoint registered → PASS
- T2 cross-user deny → PASS
- T3 consent gate → PASS (412 senza consent, 200 con)
- T4 anonymization → PASS (Player/Opponent placeholders)
- T5 GDPR export keys → PASS (profile, decks, preferences, team_replays, replay_session_notes, user_consents)
- T6 interest waitlist → PASS
- T7 orphan denied / notes round-trip → PASS
- T8 consent dual-write → PASS

Se un check P0 fallisce → STOP, non procedere a swap. Diagnosi prima di
qualsiasi modifica produzione.

---

## Step 4 — A.5 V3 swap one-liner

Dopo che Step 1-3 sono verdi, esegui il flip serving da `frontend/` (legacy)
a `frontend_v3/`. È UNA riga in `backend/main.py::_serve_dashboard()`.

```bash
# Verifica path attuale
grep -n "FRONTEND_DIR\|_serve_dashboard" backend/main.py | head -5

# Modifica: edit backend/main.py
# Cambia: FRONTEND_DIR = "frontend"
# In:     FRONTEND_DIR = "frontend_v3"

# Restart backend
sudo systemctl restart lorcana-api
sleep 3
curl -s http://localhost:8100/ | head -3
# atteso: <!DOCTYPE html> + linke a frontend_v3/assets/...
```

**Verifica visiva minima:**
1. Apri `https://metamonitor.app/` in browser pulito (incognito)
2. Conferma 7 tab: Home · Play · Meta · Deck · Team · Improve · Events
3. Hard refresh + DevTools → Application → "Clear site data" se Service Worker cachato

---

## Step 5 — QA end-to-end manuale (A.5)

Stima: 1 dev day. Matrix da spuntare:

### Tab switching
- [ ] Home → Play → Meta → Deck → Team → Improve → Events: tutti caricano senza errori console
- [ ] Bottom nav mobile funziona
- [ ] Format toggle Core/Infinity propaga a tutti i tab

### Privacy boundary (A.5 P0 just shipped)
- [ ] Senza nickname linkato: Improve mostra hero CTA "Step 1 — unlock your data"
- [ ] Con nickname linkato: bridge stats card mostra "X matches, Y% WR"
- [ ] Demo mode: badge "Demo bridge active" + "Stats below are not yours."
- [ ] No "claim language" residuo: cerca "My Stats", "Your account" — non devono apparire

### Paywall triggers
- [ ] 4° matchup/giorno in Play → overlay paywall "How to Respond" gated
- [ ] Counter localStorage `play_matchups_viewed_YYYY-MM-DD` reset 00:00 UTC
- [ ] Click "Unlock PRO — €9/month" → POST /api/v1/user/interest

### Consent flow
- [ ] Upload .replay.gz prima volta → consent modal blocca
- [ ] Accept consent → POST /api/v1/user/consent → upload retry → 200
- [ ] Verifica `preferences.consents.replay_upload` + row in `user_consents` tabella

### Board Lab (B.2 closures)
- [ ] Tab Team senza roster → Board Lab visibile (no blank state)
- [ ] Upload .replay.gz autenticato → ownership su `team_replays.user_id`
- [ ] Notes panel inline visibile solo se `is_owner=true`
- [ ] Autosave 1.5s dopo 5+ char di typing
- [ ] DELETE button owner-only → 204 + replay sparisce dalla list
- [ ] Other user (cross-account) non vede i tuoi replay

### Mobile + Desktop
- [ ] Breakpoints: ≤640px iPhone, 641-900px tablet, >900px desktop
- [ ] No feature desktop-only
- [ ] Footer disclaimer + `/about.html` link visibile

### Service Worker (A.5 P1 auto)
- [ ] `frontend_v3/sw.js` self-destruct: dopo prima visita pulisce cache utenti legacy
- [ ] Bump `CACHE_NAME` se serve forzare refresh client esistenti

---

## Step 6 — Rollback (se Step 4-5 falliscono)

Lo swap è una singola riga, rollback < 1 minuto:

```bash
# Edit backend/main.py FRONTEND_DIR torna a "frontend"
sudo systemctl restart lorcana-api
# Verify legacy serving
curl -s http://localhost:8100/ | grep -o "frontend_v3" | head -1
# atteso: vuoto (= legacy attivo)
```

Le migrations applicate (`b8e72d4a9c3f` + `c4f9e1d8a2b6`) **non vanno
rolled back** — sono additive, non rompono il legacy. Le tabelle nuove
restano in DB, il legacy semplicemente non le usa.

---

## Step 7 — Post-swap (azioni residue)

| Item | Fonte | Azione |
|---|---|---|
| A.1 alias mail Cloudflare | TODO §A.1 | DNS only: `legal@metamonitor.app` → `monitorteamfe@gmail.com` su Cloudflare Email Routing. Quando up, swap indietro le 3 occorrenze in footer/about |
| 26 file dirty pre-esistenti | git status | KC pipeline + Deck WIP + ARCHITECTURE.md + frontend legacy + lab.js Mulligan badge — separato da V3 swap |
| Push origin/dev | git | Quando pronti: `git push origin dev` (35 commit) |
| C.4 SW cleanup | TODO §C.4 | Post-launch: dopo che tutti i client legacy sono stati toccati ≥1 volta, rimuovi `sw.js` self-destruct + sostituisci con network-first HTML |

---

## Riferimenti

- TODO Master: [`TODO.md`](TODO.md) §A pre-launch
- BP §12.1 settimana 1 launch plan
- Privacy Layer V3: [`PRIVACY_LAYER_V3.md`](PRIVACY_LAYER_V3.md)
- Memorie persistenti rilevanti: `feedback_v3_nav_sacred.md`, `feedback_v3_service_worker_cache.md`, `project_b7_coach_workspace.md` (post-launch)

---

*Generato 2026-04-26 a chiusura sessione 4-commit (B.1 nickname bridge, A.5 privacy boundary, B.2 owner round-trip + session notes, B.3 user_consents).*
