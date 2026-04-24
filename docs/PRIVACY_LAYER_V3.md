# Sensitive Data & Privacy Architecture — V3 Launch Layer

**Scope:** delta additivo su architettura App_tool esistente. Nessun refactor auth, nessun refactor DB, nessuna modifica al modello V3.
**Target:** incollare come §13 (o §10.1) in `ARCHITECTURE.md`.
**Data:** 24 Aprile 2026
**Stato:** ready-to-paste

---

## 13.1 Verdetto GO incrementale

Il layer privacy per il lancio V3 si implementa come **delta additivo** sullo schema e sugli endpoint già in produzione. Nessun componente esistente viene sostituito.

Base già in produzione (da NON toccare):
- `users` (id UUID, `tier`, `preferences` JSONB, `deletion_requested_at`, `stripe_customer_id`)
- `user_sessions`, `password_reset_tokens`
- `user_decks`, `promo_codes`, `promo_redemptions`
- `team_replays`, `team_roster`
- `user_service.export_user_data()` + `GET /api/user/export` (GDPR export attivo)
- Soft-delete flow via `deletion_requested_at`

Cosa aggiungiamo pre-lancio: **1 migration additiva** (`team_replays` ownership) + **access-control su 4 endpoint** + **consenso UI** + **anonymization response** del Replay Viewer pubblico. Tutto il resto (tabelle dedicate per consensi, identity links, privacy events) può restare in `users.preferences` JSONB fino a 30 giorni post-lancio.

Unico blocker reale: l'ownership dei replay. Senza `user_id` su `team_replays`, Board Lab non ha un concetto di proprietà → rischio GDPR concreto. M1 risolve questo in una migration zero-downtime.

---

## 13.2 Data Classification

| Categoria | Tipo | Storage | Personale | Anonymization | Retention | Access |
|---|---|---|---|---|---|---|
| Public aggregated data (meta, WR, matchup stats) | Derivato | `dashboard_data` blob (Redis) + `daily_snapshots` (PG) | No | N/A | Rolling 90gg | Public |
| Scraped match logs (duels.ink) | Grezzo | `matches` (PG) + FS `/matches/<DDMMYY>/` | No (non-PII; contiene solo nickname pubblici duels.ink) | Mascheramento nickname solo in output pubblico | Indefinito (storico statistico) | Internal |
| Player nicknames (duels/lorcanito) come stringhe in log | Sensibile low | In `matches.turns[].player` (esistente) | Sì (identificabile) | Sì nel Replay Viewer pubblico (→ "Player/Opponent A") | Come match logs | Internal, mai in risposte API pubbliche |
| User profile data (email, password_hash, tier) | PII | `users` | Sì | No (serve per auth) | Fino a deletion request +30gg | Owner + admin |
| User nicknames duels/lorcanito + country | PII low | `users.preferences.nicknames` JSONB | Sì | No internamente; mai esposti pubblicamente | Con account | Owner + admin |
| Saved decks | Config | `user_decks` | No (non PII di per sé) | No | Con account | Owner |
| Replay uploads Team/Board Lab (.gz parsed) | **PII + contenuto utente** | `team_replays` (esistente) + ownership M1 | Sì | No per owner/coach assegnato | Con account (+30gg post-delete) | **Owner only + assigned coach** |
| Coaching session notes (futuro) | PII + contenuto | `coaching_session_notes` (tabella entro 30gg se serve) | Sì | No | Con account | Owner + student + assigned coach |
| Student/team data (roster) | Low PII (solo nickname scelto) | `team_roster` (esistente) | Low | No | Con account team coach | Team coach only |
| Email / waitlist | PII low | `users.preferences.waitlist_joined_at` + (opzionale) `email_subscribers` | Sì | No | Fino a unsubscribe | Internal |
| Promo / trial state | Derivato | `promo_codes`, `promo_redemptions` (esistenti) | No | N/A | Audit permanente | Internal |
| Future payment data | PII + PCI | NON in DB nostro. Solo token PSP (Paddle/Stripe customer_id già in `users.stripe_customer_id`) | Sì | No | Secondo PSP | Internal + PSP |

**Regola operativa:** ogni categoria sopra "low PII" viene loggata nel `GET /api/user/export` (GDPR) e cancellata su `deletion_requested_at`.

---

## 13.3 Storage Rules e Ownership

### 13.3.1 Principi

1. **Ownership esplicita obbligatoria** per ogni dato user-generated: `user_id` NOT NULL (o con backfill plan).
2. **Privacy default = private.** Upload, replay, notes non sono pubblici salvo flag esplicito + consenso.
3. **Scraped data != user data.** I match logs scrapati da duels.ink sono statistiche aggregate: non trattati come dati personali dell'utente-finale della dashboard.
4. **JSONB `preferences` come escape hatch** per campi non-critici che non meritano ancora tabella dedicata (consensi, nicknames, waitlist).
5. **Niente duplicazione.** Se `preferences` basta, non crei tabella dedicata. Si promuove a tabella quando serve versioning, audit append-only, o query relazionali.

### 13.3.2 Cosa resta in `users.preferences` (no migration)

```jsonc
// users.preferences JSONB — struttura consolidata V3
{
  // Nickname bridge
  "nicknames": {
    "duels": "player_nick_here",
    "lorcanito": "player_nick_here",
    "country": "IT"
  },

  // Consensi (append-only, versionati)
  "consents": {
    "tos":             { "version": "1.0", "accepted_at": "2026-05-01T10:00:00Z" },
    "privacy":         { "version": "1.0", "accepted_at": "2026-05-01T10:00:00Z" },
    "replay_upload":   { "version": "1.0", "accepted_at": "2026-05-03T15:22:00Z" },
    "marketing":       { "version": "1.0", "accepted_at": null }  // opt-in esplicito
  },

  // Fake paywall / waitlist (pre-monetizzazione)
  "waitlist_joined_at": "2026-05-01T10:00:00Z",
  "interest_to_pay":    { "tier": "pro", "at": "2026-05-10T12:00:00Z" },

  // UI preferences (già esistenti)
  "theme": "dark",
  "pinned_decks": ["ES", "AmAm", "RS"]
}
```

**Regola di lettura:** ogni chiave sopra ha default sicuro (vuoto/null) quando assente. Nessun crash se un utente legacy non ha `preferences.consents`.

### 13.3.3 Cosa va in tabella dedicata (M1 pre-lancio)

Solo `team_replays` viene esteso. Nessun'altra tabella nuova pre-lancio.

---

## 13.4 Migration M1 — `team_replays` ownership

**Obbligatoria pre-lancio. Additive. Zero-downtime.**

### 13.4.1 Schema

```sql
-- Alembic migration: <revision>_team_replays_ownership.py
-- Up:

ALTER TABLE team_replays
  ADD COLUMN user_id UUID NULL REFERENCES users(id) ON DELETE CASCADE,
  ADD COLUMN is_private BOOLEAN NOT NULL DEFAULT true,
  ADD COLUMN consent_version VARCHAR(10) NULL,
  ADD COLUMN uploaded_via VARCHAR(20) NULL,   -- 'team_lab' | 'board_lab' | 'api'
  ADD COLUMN shared_with JSONB NOT NULL DEFAULT '[]'::jsonb;
  -- shared_with = array di user_id UUID string a cui l'owner ha esplicitamente
  -- dato accesso (coach assegnato). Vuoto = solo owner.

CREATE INDEX IF NOT EXISTS idx_team_replays_user ON team_replays(user_id)
  WHERE user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_team_replays_private
  ON team_replays(is_private, user_id);

-- Down:
DROP INDEX IF EXISTS idx_team_replays_private;
DROP INDEX IF EXISTS idx_team_replays_user;
ALTER TABLE team_replays
  DROP COLUMN IF EXISTS shared_with,
  DROP COLUMN IF EXISTS uploaded_via,
  DROP COLUMN IF EXISTS consent_version,
  DROP COLUMN IF EXISTS is_private,
  DROP COLUMN IF EXISTS user_id;
```

### 13.4.2 Backfill strategy

- **Nessun backfill automatico.** I record pre-M1 restano `user_id = NULL`.
- L'access-control (§13.5) nega accesso a qualunque record con `user_id IS NULL` tranne che a utenti `is_admin=true`.
- Dopo 30 giorni di operatività M1: decidi manualmente se hard-delete degli orphan oppure backfill da `player_name` + matching nickname → `users.preferences.nicknames.duels`.
- `NOT NULL` su `user_id` rimandato a M2 (post-backfill).

### 13.4.3 SQLAlchemy model update

```python
# backend/models/team.py — additive
class TeamReplay(Base):
    __tablename__ = "team_replays"
    # ... campi esistenti ...
    user_id = mapped_column(UUID(as_uuid=True),
                            ForeignKey("users.id", ondelete="CASCADE"),
                            nullable=True, index=True)
    is_private = mapped_column(Boolean, nullable=False, server_default="true")
    consent_version = mapped_column(String(10), nullable=True)
    uploaded_via = mapped_column(String(20), nullable=True)
    shared_with = mapped_column(JSONB, nullable=False, server_default="[]")
```

---

## 13.5 Access-Control Policy — `/api/v1/team/replay/*`

### 13.5.1 Policy matrix

| Endpoint | Metodo | Autorizzazione | Filtro query |
|---|---|---|---|
| `/api/v1/team/replay/upload` | POST | `user authenticated` + `user.consent.replay_upload not null` | Assegna `user_id = current_user.id`, `is_private = true`, `consent_version = current` |
| `/api/v1/team/replay/list` | GET | `user authenticated` | `WHERE user_id = current_user.id OR current_user.id IN shared_with OR current_user.is_admin` |
| `/api/v1/team/replay/{game_id}` | GET | `user authenticated` | Stessa WHERE + check per-record |
| `/api/v1/team/replay/{game_id}` | DELETE | `user authenticated` + `replay.user_id == current_user.id OR current_user.is_admin` | — |
| `/api/v1/team/replay/{game_id}/share` | POST | `user authenticated` + `replay.user_id == current_user.id` | Aggiunge user_id target a `shared_with` |

### 13.5.2 Deps helper (FastAPI)

```python
# backend/deps.py — additive
def require_replay_access(
    game_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TeamReplay:
    replay = db.query(TeamReplay).filter(TeamReplay.game_id == game_id).first()
    if replay is None:
        raise HTTPException(404, "replay not found")
    if user.is_admin:
        return replay
    if replay.user_id is None:
        # orphan legacy record, nessuno può accedere tranne admin
        raise HTTPException(403, "replay access denied")
    if replay.user_id == user.id:
        return replay
    if str(user.id) in (replay.shared_with or []):
        return replay
    raise HTTPException(403, "replay access denied")


def require_replay_owner(
    game_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TeamReplay:
    replay = db.query(TeamReplay).filter(TeamReplay.game_id == game_id).first()
    if replay is None:
        raise HTTPException(404, "replay not found")
    if user.is_admin:
        return replay
    if replay.user_id != user.id:
        raise HTTPException(403, "replay access denied — not owner")
    return replay
```

### 13.5.3 Consent check upload

```python
# backend/api/team.py — upload endpoint
@router.post("/replay/upload")
def upload_replay(payload: ReplayUploadIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    consent = (user.preferences or {}).get("consents", {}).get("replay_upload")
    if not consent or not consent.get("accepted_at"):
        raise HTTPException(412, "replay_upload consent required")

    replay = TeamReplay(
        game_id=payload.game_id,
        user_id=user.id,
        is_private=True,
        consent_version=consent.get("version", "1.0"),
        uploaded_via="board_lab",
        replay_data=payload.replay_data,
        # ... altri campi esistenti
    )
    db.add(replay); db.commit()
    return {"id": str(replay.id)}
```

---

## 13.6 Board Lab — Regole Operative

1. **Upload sempre privato di default** (`is_private = true`). Nessun toggle pubblico nella UI V3 al lancio.
2. **Ownership fissa all'upload:** `user_id = current_user.id` non modificabile.
3. **Consenso obbligatorio prima del primo upload:** checkbox UI → scrive `users.preferences.consents.replay_upload = {version, accepted_at}`.
4. **Sharing opt-in esplicito:** l'owner può aggiungere `user_id` del coach assegnato tramite `POST /api/v1/team/replay/{id}/share`. Nessuno "shared by default".
5. **Delete owner-only:** `DELETE /api/v1/team/replay/{id}` ammesso solo al proprietario o admin. Hard delete (non soft — non ha senso conservare un replay richiesto di eliminazione).
6. **Tier check Coach:** accesso a Board Lab UI gated da `user.tier in ('coach','admin')`. Non Coach → paywall soft (§13.8).
7. **Nessun public sharing URL** al lancio. Se in futuro serve "public replay link", richiede flag `is_private = false` + consenso dedicato `public_share`.
8. **Export sessione PDF:** consentito solo a owner o coach con accesso `shared_with`. Non anonimizzato (è un artefatto per il proprietario).
9. **Retention:** replay restano finché l'account esiste. On `deletion_requested_at +30gg` → hard delete.
10. **Rate limit upload:** max 20 replay/giorno per utente free, 200/giorno per Pro/Coach. Enforce a livello middleware (§13.10 post-launch).

---

## 13.7 Public Replay Viewer — Regole

Il Replay Viewer dentro Play mostra match reali da `matches` (scraped duels.ink). Queste **non sono uploads utente** e hanno regole separate.

1. **Sempre anonymized in response API.** Il backend sostituisce nickname reali con placeholder prima di serializzare.
2. **Mapping anonymization:**
   - Nostro player (perspective) → `"Player"`
   - Avversario → `"Opponent A"` (se match singolo)
   - In lista di match multipli dello stesso matchup → `"Opponent A"`, `"Opponent B"`, `"Opponent C"`... allocati deterministicamente per seed + match_id
3. **Mai raw nickname duels.ink nella response pubblica** di `GET /api/replay/public-log`, `GET /api/replay/game`, `GET /api/replay/list`.
4. **Nessun link a profili esterni** (duels.ink, lorcanito) dal Replay Viewer pubblico.
5. **Label UI fissa:** ogni istanza del viewer pubblico ha badge "Example match" in alto a destra.
6. **No audit per-open al lancio.** Tracciare chi apre quale replay è overhead inutile pre-monetizzazione. Entro 30gg, se servisse per abuse prevention, si aggiunge a `audit`.
7. **Differenza con Board Lab:** Board Lab mostra il proprio nickname (o vuoto) perché è l'upload del proprietario. Il Replay Viewer pubblico **non mostra mai nicknames reali**, neanche quello dell'utente loggato.

### 13.7.1 Implementazione anonymization

```python
# backend/services/replay_anonymizer.py — nuovo file
def anonymize_replay_payload(payload: dict, perspective: int | None = None) -> dict:
    """Sostituisce nicknames con placeholder. Idempotente.
       Chiamato da replay_archive_service e match_log_features_service prima
       del return delle API pubbliche."""
    # Mantieni struttura, sostituisci solo i campi identificativi
    # player_name, opponent_name, ownerPlayerId, ...
    ...
```

Chiamato in:
- `replay_archive_service.list_replays()`
- `replay_archive_service.get_game()`
- `match_log_features_service.build_viewer_public_log()`

**Nessun cambiamento** in `backend/services/replay_service.py` (Board Lab parser) — quello è owner-visible, non passa dall'anonymizer.

---

## 13.8 Fake Paywall / Waitlist (Pre-Monetizzazione)

Al lancio non fatturiamo ancora. Il paywall serve comunque per misurare intent e stratificare UI.

### 13.8.1 Cosa salviamo, cosa NON salviamo

| Dato | Dove | Quando | Note |
|---|---|---|---|
| Email iscritta alla waitlist | `users.email` + `users.preferences.waitlist_joined_at` | Su click "notify me" | Crea user con `tier='free'` se non esiste |
| Intent to pay (quale tier l'utente ha cliccato) | `users.preferences.interest_to_pay = { tier, at }` | Su click paywall "Unlock Pro" / "Unlock Coach" | Overwrite sull'ultimo click |
| Promo code riscattato pre-lancio | `promo_redemptions` (esistente) | Su redeem | Funziona identico a oggi |
| Carta di credito | **MAI. Zero.** | — | Nessuna integrazione Stripe/Paddle attiva al lancio |
| Subscription status | `users.tier` (esistente) | Upgrade via promo code | Stripe integration rimandata |

### 13.8.2 Flusso paywall soft

```
User clicca "Unlock Pro — €9/m"
  ↓
  writeInterest('pro')                 // POST /api/v1/user/interest
  ↓
  UI overlay: "Sei in waitlist. Ti scriveremo quando apriamo i pagamenti.
              Intanto, codice promo? [ input ]"
  ↓
  Se promo valido → redeem → tier='pro' per N giorni (logica esistente)
  Altrimenti → nessun cambio tier, solo intent registrato
```

### 13.8.3 Endpoint nuovo (1 solo)

```python
# backend/api/user.py — additive
@router.post("/interest")
def register_interest(
    tier: str = Body(..., regex="^(pro|coach)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prefs = user.preferences or {}
    prefs["interest_to_pay"] = {
        "tier": tier,
        "at": datetime.utcnow().isoformat()
    }
    user.preferences = prefs
    db.commit()
    return {"ok": True}
```

### 13.8.4 Cosa evitare

- **Nessuna tabella `subscriptions` al lancio.** Arriva con Stripe/Paddle.
- **Nessun campo `trial_expires_at` dedicato.** Se serve un trial, si concede via promo code `TRIAL14D` → `promo_codes.duration_days=14`.
- **Nessun lock hard.** Se l'unlock è solo UI-side (come oggi con `PRO_UNLOCKED`), **non è sicuro lato server**: sostituisci con check `user.tier` enforced da `require_pro` / `require_coach` deps.

---

## 13.9 GDPR Export / Delete — Impact

`GET /api/user/export` esiste già (`user_service.export_user_data`). Va **esteso** per includere i dati V3.

### 13.9.1 Estensione export

```python
# backend/services/user_service.py — additive
def export_user_data(db: Session, user: User) -> dict:
    return {
        "exported_at": datetime.utcnow().isoformat(),
        "user": {...},  # esistente
        "decks": [...],  # esistente
        "preferences": user.preferences or {},  # include consensi, nicknames, waitlist
        "team_replays": [
            {
                "game_id": r.game_id,
                "uploaded_at": r.created_at.isoformat(),
                "is_private": r.is_private,
                "consent_version": r.consent_version,
                "uploaded_via": r.uploaded_via,
                "shared_with": r.shared_with,
                "turn_count": r.turn_count,
                "replay_data": r.replay_data,  # incluso completo
            }
            for r in db.query(TeamReplay).filter(TeamReplay.user_id == user.id).all()
        ],
        "promo_redemptions": [...],  # se esistente, o da aggiungere
    }
```

### 13.9.2 Soft-delete flow (delete request)

```
User clicca "Delete account" nella UI V3
  ↓
  POST /api/user/delete-request
  ↓
  user.deletion_requested_at = now()                   (già supportato)
  user.is_active = false                               (blocca login)
  ↓
  (grazie di 30 giorni — recovery via email admin se utente cambia idea)
  ↓
  Cron job nightly:
    SELECT id FROM users WHERE deletion_requested_at < now() - interval '30 days'
    → per ogni user:
        DELETE FROM team_replays WHERE user_id = :uid  (hard)
        DELETE FROM user_decks WHERE user_id = :uid    (hard)
        DELETE FROM promo_redemptions WHERE user_id = :uid  (hard)
        DELETE FROM user_sessions WHERE user_id = :uid      (hard)
        UPDATE users SET email='deleted_<uid>@local', password_hash='', preferences='{}',
                         display_name=NULL, stripe_customer_id=NULL
          WHERE id = :uid
        -- user row resta per integrità referenziale audit; PII cancellata
```

Cron job `db/purge_deleted_users.py` da creare entro 30gg post-lancio. **Non blocker al lancio** se nessun utente chiede delete nei primi 30 giorni — basta monitorare la coda.

### 13.9.3 Cosa l'export NON include

- `matches` scrapati che contengono il nickname duels dell'utente → **non** sono "user data" del prodotto, sono dati aggregati. Se l'utente vuole la rimozione dai nostri log statistici, richiede processo manuale (contatto `legal@`) e comporta ricalcolo aggregati (evento raro, post-lancio).
- Log analytics aggregati dove l'utente appare in forma statistica → non estraibili come riga singola.

Questa distinzione va scritta chiaramente nella Privacy Policy ma non impatta l'implementazione al lancio.

---

## 13.10 Checklist Operativa

### A. Pre-lancio (OBBLIGATORI, ≤7 giorni)

| # | Task | Owner | Effort |
|---|---|---|---|
| A1 | Alembic migration M1 (`team_replays` ownership) scritta + applicata su staging + applicata su prod | BE | 1h |
| A2 | Update `TeamReplay` SQLAlchemy model con nuovi campi | BE | 30min |
| A3 | Deps helper `require_replay_access` / `require_replay_owner` in `backend/deps.py` | BE | 1h |
| A4 | Wiring access-control su 5 endpoint `/api/v1/team/replay/*` | BE | 1h |
| A5 | Endpoint `POST /api/user/interest` (waitlist soft paywall) | BE | 30min |
| A6 | `replay_anonymizer.py` + wiring in `replay_archive_service` + `match_log_features_service` | BE | 2h |
| A7 | Consent checkbox UI Board Lab prima del primo upload → `preferences.consents.replay_upload` | FE | 1h |
| A8 | Disclaimer footer "Unofficial fan-made" + `/about` page minimale + `legal@` alias | Ops | 30min |
| A9 | Extend `export_user_data()` con `team_replays` + `preferences` | BE | 30min |
| A10 | Smoke test access-control: utente A non vede replay utente B (curl + assertion) | QA | 1h |

**Totale: ~9h.** Budget cuscinetto: 2 giorni di calendar time part-time.

### B. Entro 30 giorni post-lancio

| # | Task | Trigger |
|---|---|---|
| B1 | Tabella dedicata `user_consents` con versioning append-only | Quando servono audit per consent change |
| B2 | Tabella dedicata `user_identity_links` | Quando > 2 provider (oggi duels + lorcanito) |
| B3 | Endpoint `DELETE /api/v1/team/replay/{id}` owner-only | Il prima possibile post-lancio, bassa priorità se no feedback |
| B4 | Endpoint `POST /api/v1/team/replay/{id}/share` (coach assignment) | Quando un coach reale paga |
| B5 | Rate-limit upload replay (20/giorno free, 200 pro) | Se abuse osservato |
| B6 | Cron `db/purge_deleted_users.py` | Obbligatorio appena il primo utente chiede delete |
| B7 | Privacy events log (usa `audit` esistente) per export, delete, consent revoke | Nice-to-have |
| B8 | Backfill decision per `team_replays` orphan (user_id IS NULL) | Dopo 30gg |
| B9 | Alembic `NOT NULL` su `team_replays.user_id` (M1.5) | Dopo backfill |

### C. Post-monetizzazione

| # | Task |
|---|---|
| C1 | Webhook Paddle/Stripe → `subscriptions` table |
| C2 | `invoices` table + endpoint download |
| C3 | Admin UI: search utente, export/delete manuale, revoke consent |
| C4 | Automated retention policy cron (replay > 365gg di utenti cancellati, audit > 7 anni, etc.) |
| C5 | Cookie banner se serve (solo se attivi analytics non-essenziali tipo GA) |
| C6 | DPIA completa (Data Protection Impact Assessment) |
| C7 | Data Processing Agreement con subprocessor (Hetzner, Paddle, Resend, OpenAI, Anthropic) |

---

*Fine §13 Sensitive Data & Privacy Architecture — V3 Launch Layer.*
