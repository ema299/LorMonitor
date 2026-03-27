# Lorcana Monitor — Architettura Produzione

**Versione:** 3.0 | **Data:** 27 Marzo 2026

---

## 1. Principi

1. **3 strati con contratti fissi**: schemas (contratti) -> pipelines (orchestratori) -> lib (moduli puri). L'HTML non calcola. L'LLM non tocca il codice. I validatori sono guardiani.
2. **Fail-safe by default**: ogni componente ha backup, recovery automatico, e log strutturato. Se un pezzo si rompe, il sistema degrada senza perdere dati.
3. **Performance first**: match in PostgreSQL con indici mirati, query <100ms. Zero file scan a runtime.
4. **Privacy by design**: GDPR-compliant, dati utente criptati, password hashate, cancellazione garantita.
5. **Mobile-native**: PWA responsive, poi wrapper nativo iOS con Capacitor per App Store.
6. **Zero-downtime deploy**: reload graceful, rollback immediato, nessuna interruzione per gli utenti.

---

## 2. Stato Attuale (da migrare)

```
analisidef/                         # Sistema monolitico funzionante
  lib/              6.7K LOC        # 16 moduli Python (loader, investigate, gen_*)
  daily/            9.9K LOC        # daily_routine.py 3456 LOC (monolite), dashboard.html 5259 LOC
  generate_report.py                # Pipeline 5 fasi -> report .md
  output/           3.6 GB          # 139 archive, 132 digest, 134 killer_curves, 140 scores
  reports/          141 .md         # Report matchup (14 deck)
  daily/output/     48 MB           # dashboard_data.json + history.db

Dati sorgente:
  matches/          64K+ file JSON, 3 GB    # Match log turno per turno
  cards_db.json     1511 carte              # DB carte normalizzato
  decks_db/                                  # Decklist tornei
```

**Problemi attuali:**
- `daily_routine.py` e' un monolite da 3456 LOC che fa tutto
- 64K file JSON scansionati a ogni run (~22s per matchup)
- Nessuna auth, nessun HTTPS, porta 8060 su IP diretto
- SimpleHTTPServer, nessun rate limit, nessun log strutturato
- Nessun backup automatico, nessun recovery
- Single point of failure su tutto

---

## 3. Architettura Target

```
                    ┌──────────────────────────────────────────────────┐
                    │                   INTERNET                       │
                    └──────────────────────┬───────────────────────────┘
                                          │
                                   ┌──────┴──────┐
                                   │    nginx     │
                                   │  + SSL/TLS   │
                                   │  + rate limit│
                                   │  + gzip      │
                                   └──┬───────┬───┘
                                      │       │
                          ┌───────────┘       └───────────┐
                          │                               │
                   ┌──────┴──────┐                 ┌──────┴──────┐
                   │  Frontend   │                 │  Backend    │
                   │  Static     │                 │  FastAPI    │
                   │  (nginx)    │                 │  (uvicorn)  │
                   └─────────────┘                 └──────┬──────┘
                                                          │
                          ┌───────────────┬───────────────┼───────────────┐
                          │               │               │               │
                   ┌──────┴──────┐ ┌──────┴──────┐ ┌─────┴──────┐ ┌─────┴──────┐
                   │ PostgreSQL  │ │    Redis     │ │ LLM Worker │ │  Pipeline  │
                   │ (dati+auth) │ │ (cache+sess) │ │  (async)   │ │  (cron)    │
                   └─────────────┘ └─────────────┘ └────────────┘ └────────────┘
```

---

## 4. Alberatura App_tool

```
App_tool/
│
├── ARCHITECTURE.md
├── ARCHITECTURE_EXPLANATION.md     # Spiegazione per non-tecnici
│
├── backend/                          # FastAPI application
│   ├── main.py                       # Entrypoint uvicorn
│   ├── config.py                     # Settings (env vars, path, costanti)
│   ├── deps.py                       # Dependency injection (db session, current_user)
│   │
│   ├── api/                          # Route handlers
│   │   ├── auth.py                   # POST /login, /register, /logout, /refresh
│   │   ├── monitor.py                # GET /meta, /deck, /players, /tech
│   │   ├── coach.py                  # GET /matchup, /killer-curves, /threats
│   │   ├── lab.py                    # GET /optimizer, /mulligans, /card-scores
│   │   ├── user.py                   # GET/POST/DELETE /decks, /profile, /preferences
│   │   ├── admin.py                  # POST /refresh-daily, /refresh-curves, /health
│   │   └── webhooks.py               # Stripe webhook, monitor alerts
│   │
│   ├── models/                       # SQLAlchemy ORM models
│   │   ├── user.py                   # User, UserPreferences
│   │   ├── subscription.py           # Subscription, PaymentHistory
│   │   ├── match.py                  # Match (JSONB turns)
│   │   ├── analysis.py               # KillerCurve, Archive, ThreatLLM, DailySnapshot
│   │   └── user_deck.py              # UserDeck
│   │
│   ├── services/                     # Business logic (moduli puri)
│   │   ├── auth_service.py           # Hash, verify, JWT, refresh token, password reset
│   │   ├── stats_service.py          # WR, matrice, trend, meta share, OTP/OTD
│   │   ├── players_service.py        # Top players, pro detail, scouting
│   │   ├── tech_service.py           # Tech tornado, consensus, card impact
│   │   ├── matchup_service.py        # Killer curves, threats, playbook
│   │   ├── deck_service.py           # Optimizer, card scores, mulligan
│   │   ├── community_service.py      # Fetch duels.ink
│   │   ├── history_service.py        # Storico snapshot, trend
│   │   ├── subscription_service.py   # Stripe, tier check, paywall
│   │   └── team_service.py           # Team training, player stats
│   │
│   ├── middleware/                    # Cross-cutting concerns
│   │   ├── rate_limit.py             # Per-endpoint, per-tier rate limiting
│   │   ├── logging_mw.py             # Request/response structured logging
│   │   ├── cors.py                   # CORS policy
│   │   └── error_handler.py          # Global exception handler, error codes
│   │
│   └── workers/                      # Background jobs
│       ├── daily_pipeline.py         # Cron 07:00 — aggiorna monitor_data
│       ├── weekly_pipeline.py        # Cron lunedi — aggiorna coach_data + lab_data
│       ├── llm_worker.py             # Async — killer curves via Claude API (Batch)
│       ├── match_importer.py         # Cron 06:00 — importa nuovi match JSON -> PostgreSQL
│       └── backup_worker.py          # Cron 03:00 — pg_dump + upload offsite
│
├── schemas/                          # JSON Schema (contratti API)
│   ├── monitor.schema.json
│   ├── coach.schema.json
│   ├── lab.schema.json
│   ├── killer_curves.schema.json
│   ├── user.schema.json
│   └── validate.py                   # Validatore generico
│
├── lib/                              # Moduli puri riciclati da analisidef/lib
│   ├── loader.py                     # Interfaccia unica: load_matches(perimeter, ...)
│   ├── investigate.py                # Board state, ink budget, classify_losses
│   ├── stats.py                      # Calcoli statistici puri
│   ├── cards_dict.py                 # 1511 carte normalizzate
│   ├── formatting.py                 # Display helpers
│   ├── gen_archive.py                # Genera archivio JSON
│   ├── gen_digest.py                 # Genera digest compatto per LLM
│   └── validate_killer_curves.py     # Validazione meccanica
│
├── llm/                              # Output LLM (generati da Claude API)
│   ├── killer_curves/                # JSON validati contro schema
│   ├── threats/                      # Analisi minacce
│   ├── reviews/                      # Review tattica 6 pass
│   └── instructions/                 # Prompt per Claude
│       ├── ISTRUZIONI_KILLER_CURVES.md
│       ├── ISTRUZIONI_REVIEW.md
│       └── LORCANA_RULES_REFERENCE.md
│
├── frontend/                         # SPA statica (servita da nginx)
│   ├── index.html                    # Shell SPA
│   ├── assets/
│   │   ├── css/
│   │   │   └── app.css
│   │   ├── js/
│   │   │   ├── app.js                # Router + state management
│   │   │   ├── api.js                # Fetch wrapper con auth token
│   │   │   ├── monitor.js            # Tab Monitor
│   │   │   ├── coach.js              # Tab Coach V2
│   │   │   ├── lab.js                # Tab Lab
│   │   │   ├── team.js               # Tab Team Training
│   │   │   └── auth.js               # Login/register/logout
│   │   ├── icons/                    # PWA icons (192, 512)
│   │   └── vendor/
│   │       └── chart.min.js
│   ├── manifest.json                 # PWA manifest
│   └── sw.js                         # Service Worker (offline, cache)
│
├── mobile/                           # iOS wrapper (Capacitor)
│   ├── capacitor.config.ts
│   ├── ios/                          # Xcode project (generato)
│   └── README.md                     # Build & deploy instructions
│
├── db/                               # Database
│   ├── migrations/                   # Alembic migrations
│   │   ├── env.py
│   │   └── versions/
│   │       ├── 001_initial.py        # Users, subscriptions, matches
│   │       ├── 002_analysis.py       # Killer curves, archives, threats
│   │       └── 003_snapshots.py      # Daily snapshots, history
│   ├── seed.py                       # Import iniziale: 64K JSON -> PostgreSQL
│   └── backup.sh                     # Script pg_dump + compress + rotate
│
├── infra/                            # Configurazione infrastruttura
│   ├── nginx/
│   │   ├── lorcana.conf              # Virtual host (SSL, proxy, rate limit, headers)
│   │   └── security.conf             # CSP, HSTS, X-Frame, X-Content-Type
│   ├── systemd/
│   │   ├── lorcana-api.service       # FastAPI (uvicorn)
│   │   ├── lorcana-worker.service    # Background workers
│   │   └── lorcana-backup.timer      # Backup timer
│   ├── certbot/
│   │   └── renew.sh                  # Let's Encrypt auto-renewal
│   ├── logrotate/
│   │   └── lorcana                   # Rotazione log (7gg retain, compress)
│   ├── monitoring/
│   │   ├── healthcheck.py            # /health endpoint check + alert
│   │   └── uptime.sh                 # Cron 5min: check API, DB, disk, memory
│   └── docker-compose.yml            # Dev environment (opzionale)
│
├── scripts/                          # Utility operative
│   ├── import_matches.py             # Bulk import 64K JSON -> PostgreSQL
│   ├── migrate_killer_curves.py      # Migra output/ JSON -> PostgreSQL
│   ├── migrate_history.py            # Migra history.db SQLite -> PostgreSQL
│   ├── create_admin.py               # Crea utente admin
│   ├── benchmark_queries.py          # Misura performance query critiche
│   └── deploy.sh                     # Deploy zero-downtime (git pull + reload)
│
├── tests/                            # Test suite
│   ├── test_services/
│   ├── test_api/
│   ├── test_lib/
│   └── conftest.py                   # Fixture DB test (PostgreSQL test DB)
│
├── .env.example                      # Template variabili ambiente
├── .env.dev                          # Variabili dev (non versionato)
├── requirements.txt                  # Dipendenze Python
└── .gitignore
```

---

## 5. Database — PostgreSQL

### 5.1 Perche' PostgreSQL (non MongoDB, non SQLite)

| Criterio | PostgreSQL | MongoDB | SQLite |
|----------|-----------|---------|--------|
| Relazionale (users, subs) | Nativo | Forzato | Nativo |
| Documentale (match turns) | JSONB eccellente | Nativo | JSON1 limitato |
| Query aggregate SQL | Si | Aggregation pipeline | Si |
| Indici su JSONB | GIN, btree su path | Si | No |
| Backup/replica | pg_dump, streaming | mongodump | File copy |
| Concorrenza multi-utente | MVCC maturo | Si | Write lock globale |
| Tooling | pgAdmin, pg_stat | Compass | Limitato |
| Un solo servizio | Si | Serve mongod separato | Si (ma non scala) |
| Managed su Hetzner | Si (futuro) | No | N/A |

**Scelta: PostgreSQL.** Un DB per relazionale + documentale. SQLite non regge concorrenza. MongoDB aggiunge un servizio senza vantaggi reali per questo caso (dati misti relazionali + documenti).

### 5.2 Schema

```sql
-- ============================================================
-- UTENTI E ABBONAMENTI
-- ============================================================

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,         -- bcrypt (cost 12)
    display_name    VARCHAR(100),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    last_login      TIMESTAMPTZ,
    is_active       BOOLEAN DEFAULT true,
    is_admin        BOOLEAN DEFAULT false,
    tier            VARCHAR(20) DEFAULT 'free',     -- free, pro, team
    stripe_customer_id VARCHAR(255),
    preferences     JSONB DEFAULT '{}',             -- lingua, deck preferito, notifiche
    deletion_requested_at TIMESTAMPTZ              -- GDPR: soft delete schedulato
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_tier ON users(tier);

CREATE TABLE subscriptions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    tier            VARCHAR(20) NOT NULL,           -- pro, team
    status          VARCHAR(20) NOT NULL,           -- active, cancelled, past_due, trialing
    stripe_sub_id   VARCHAR(255) UNIQUE,
    current_period_start TIMESTAMPTZ,
    current_period_end   TIMESTAMPTZ,
    cancel_at       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_subs_user ON subscriptions(user_id);
CREATE INDEX idx_subs_status ON subscriptions(status);

CREATE TABLE password_reset_tokens (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    token_hash      VARCHAR(255) NOT NULL,          -- SHA-256 del token
    expires_at      TIMESTAMPTZ NOT NULL,
    used_at         TIMESTAMPTZ
);

CREATE TABLE user_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    refresh_token_hash VARCHAR(255) NOT NULL,
    device_info     VARCHAR(500),
    ip_address      INET,
    created_at      TIMESTAMPTZ DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL,
    revoked_at      TIMESTAMPTZ
);

CREATE INDEX idx_sessions_user ON user_sessions(user_id);

-- ============================================================
-- DECK UTENTE ("Mio Deck")
-- ============================================================

CREATE TABLE user_decks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    name            VARCHAR(100) NOT NULL,
    deck_code       VARCHAR(10) NOT NULL,           -- AmAm, ES, etc.
    cards           JSONB NOT NULL,                  -- [{card_name, count}, ...]
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_user_decks_user ON user_decks(user_id);

-- ============================================================
-- MATCH (sorgente dati principale)
-- ============================================================

CREATE TABLE matches (
    id              BIGSERIAL PRIMARY KEY,
    external_id     VARCHAR(100) UNIQUE,            -- ID originale duels.ink
    played_at       TIMESTAMPTZ NOT NULL,
    game_format     VARCHAR(20) NOT NULL,            -- core, infinity
    queue_name      VARCHAR(50),                     -- S11-BO1, INF-BO3, etc.
    perimeter       VARCHAR(20) NOT NULL,            -- set11, top, pro, friends, infinity
    deck_a          VARCHAR(10) NOT NULL,
    deck_b          VARCHAR(10) NOT NULL,
    winner          VARCHAR(10),                     -- deck_a, deck_b, draw
    player_a_name   VARCHAR(100),
    player_b_name   VARCHAR(100),
    player_a_mmr    INTEGER,
    player_b_mmr    INTEGER,
    total_turns     INTEGER,
    lore_a_final    INTEGER,
    lore_b_final    INTEGER,
    turns           JSONB NOT NULL,                  -- [{plays, abilities, challenges, ...}, ...]
    cards_a         JSONB,                           -- lista carte giocate da A
    cards_b         JSONB,                           -- lista carte giocate da B
    imported_at     TIMESTAMPTZ DEFAULT now()
);

-- Indici critici per performance (<100ms per matchup query)
CREATE INDEX idx_matches_format ON matches(game_format);
CREATE INDEX idx_matches_perimeter ON matches(perimeter);
CREATE INDEX idx_matches_decks ON matches(deck_a, deck_b);
CREATE INDEX idx_matches_date ON matches(played_at DESC);
CREATE INDEX idx_matches_mmr_a ON matches(player_a_mmr);
CREATE INDEX idx_matches_mmr_b ON matches(player_b_mmr);

-- Indice composto per la query piu' frequente:
-- "tutti i match core AmAm vs ES degli ultimi 2 giorni"
CREATE INDEX idx_matches_lookup ON matches(game_format, deck_a, deck_b, played_at DESC)
    WHERE perimeter IN ('set11', 'top', 'pro', 'friends');

-- ============================================================
-- ANALISI (output pipeline + LLM)
-- ============================================================

CREATE TABLE killer_curves (
    id              BIGSERIAL PRIMARY KEY,
    generated_at    DATE NOT NULL,
    game_format     VARCHAR(20) NOT NULL,
    our_deck        VARCHAR(10) NOT NULL,
    opp_deck        VARCHAR(10) NOT NULL,
    curves          JSONB NOT NULL,
    match_count     INTEGER,
    loss_count      INTEGER,
    version         INTEGER DEFAULT 1,
    is_current      BOOLEAN DEFAULT true,
    UNIQUE(game_format, our_deck, opp_deck, generated_at)
);

CREATE INDEX idx_kc_lookup ON killer_curves(game_format, our_deck, opp_deck, is_current)
    WHERE is_current = true;

CREATE TABLE archives (
    id              BIGSERIAL PRIMARY KEY,
    generated_at    DATE NOT NULL,
    game_format     VARCHAR(20) NOT NULL,
    our_deck        VARCHAR(10) NOT NULL,
    opp_deck        VARCHAR(10) NOT NULL,
    aggregates      JSONB NOT NULL,
    match_count     INTEGER,
    UNIQUE(game_format, our_deck, opp_deck, generated_at)
);

CREATE TABLE threats_llm (
    id              BIGSERIAL PRIMARY KEY,
    generated_at    DATE NOT NULL,
    game_format     VARCHAR(20) NOT NULL,
    our_deck        VARCHAR(10) NOT NULL,
    opp_deck        VARCHAR(10) NOT NULL,
    threats         JSONB NOT NULL,
    is_current      BOOLEAN DEFAULT true,
    UNIQUE(game_format, our_deck, opp_deck, generated_at)
);

CREATE TABLE daily_snapshots (
    id              BIGSERIAL PRIMARY KEY,
    snapshot_date   DATE NOT NULL,
    perimeter       VARCHAR(20) NOT NULL,
    data            JSONB NOT NULL,
    UNIQUE(snapshot_date, perimeter)
);

CREATE INDEX idx_snapshots_date ON daily_snapshots(snapshot_date DESC);

-- ============================================================
-- AUDIT LOG
-- ============================================================

CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    event_type      VARCHAR(50) NOT NULL,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    ip_address      INET,
    details         JSONB,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_audit_user ON audit_log(user_id, created_at DESC);
```

### 5.3 Materialized Views (precalcolo)

```sql
CREATE MATERIALIZED VIEW mv_meta_share AS
SELECT game_format, perimeter, deck_a as deck,
       COUNT(*) as games,
       COUNT(*) FILTER (WHERE winner = 'deck_a') as wins
FROM matches
WHERE played_at >= now() - INTERVAL '2 days'
GROUP BY game_format, perimeter, deck_a;

CREATE MATERIALIZED VIEW mv_matchup_matrix AS
SELECT game_format, perimeter, deck_a, deck_b,
       COUNT(*) as games,
       COUNT(*) FILTER (WHERE winner = 'deck_a') as wins_a,
       AVG(total_turns) as avg_turns
FROM matches
WHERE played_at >= now() - INTERVAL '7 days'
GROUP BY game_format, perimeter, deck_a, deck_b;
```

### 5.4 Performance Target

| Query | Target | Strategia |
|-------|--------|-----------|
| WR matchup (2gg, 1 perimetro) | <50ms | Indice composto `idx_matches_lookup` |
| Matrice 12x12 (tutti matchup) | <500ms | 1 query aggregata con GROUP BY |
| Killer curves correnti | <10ms | Indice parziale `WHERE is_current = true` |
| Top players (70) con WR | <200ms | Materialized view, refresh daily |
| Storico 30gg per deck | <100ms | `daily_snapshots` + indice data |
| Login utente | <50ms | Indice email, bcrypt in-memory |
| Import 1 match | <5ms | Prepared statement, batch commit |

### 5.5 Import Iniziale

```bash
# Fase 1: import bulk 64K match JSON -> PostgreSQL
python scripts/import_matches.py --source /mnt/HC_Volume_104764377/finanza/Lor/matches/
# Stima: ~10 min per 64K file (batch insert 1000/commit)

# Fase 2: migra killer curves
python scripts/migrate_killer_curves.py --source analisidef/output/

# Fase 3: migra history
python scripts/migrate_history.py --source analisidef/daily/output/history.db

# Fase 4: verifica
python scripts/benchmark_queries.py
```

---

## 6. Scalabilita'

### 6.1 Capacity del VPS attuale (2 vCPU, 4GB RAM)

| Metrica | Valore | Collo di bottiglia |
|---------|--------|-------------------|
| Richieste API concorrenti | ~100-150 | CPU (4 uvicorn worker) |
| Utenti registrati | Migliaia | Solo spazio disco |
| Utenti attivi simultanei | ~50-80 | RAM (PostgreSQL + Redis + uvicorn) |
| Query PostgreSQL/sec | ~500-1000 | Con indici e cache |
| Tempo risposta medio | <100ms | Cache hit ~5ms, DB ~50ms |

50-80 simultanei = ~200-500 utenti attivi giornalieri = ~1000-2000 registrati.
Per un prodotto Lorcana di nicchia, sufficiente per mesi.

### 6.2 Upgrade Path

```
Fase 1: Stesso VPS, upgrade RAM (sufficiente fino a ~200 utenti simultanei)
┌────────────────────────────────────────┐
│  CX31: 2 vCPU, 8GB RAM — 9 EUR/mese  │
│  Tutto sullo stesso server             │
└────────────────────────────────────────┘

Fase 2: Separa il DB (fino a ~500 utenti simultanei)
┌──────────────┐    ┌──────────────────────┐
│  VPS App     │───→│  PostgreSQL managed   │
│  CX21, 5€/m │    │  Hetzner, 15 EUR/m    │
└──────────────┘    └──────────────────────┘

Fase 3: Scala orizzontale (500+ simultanei, improbabile per Lorcana)
┌──────────┐
│  nginx   │──→ VPS App 1 (uvicorn)
│  load    │──→ VPS App 2 (uvicorn)  ──→ PostgreSQL managed
│ balancer │──→ VPS App 3 (uvicorn)      + Redis managed
└──────────┘
```

**Principio**: l'architettura non blocca la scala. Ogni pezzo e' separato — se il DB e' il collo, lo sposti. Se l'API non regge, aggiungi worker o nodi. nginx fa gia' load balancing nativo.

### 6.3 Bottleneck reale: pipeline, non API

Le richieste utente sono letture — veloci, cachate. Il pezzo pesante e' la pipeline notturna:

```
06:00  Import match (I/O disco + INSERT bulk)
07:00  Pipeline daily (query aggregate + materialized view refresh)
08:00  LLM worker (CPU + rete verso Claude API)
```

Gira di notte quando nessuno usa l'app. Se servisse, si sposta su un worker separato.

---

## 7. Backend — FastAPI

### 7.1 API Endpoints

```
/api/v1/
│
├── auth/
│   ├── POST /register              # Email + password -> JWT
│   ├── POST /login                  # Email + password -> access + refresh token
│   ├── POST /logout                 # Revoca refresh_token
│   ├── POST /refresh                # refresh_token -> nuovo access_token
│   ├── POST /forgot-password        # Invia email reset
│   ├── POST /reset-password         # Token + nuova password
│   ├── GET  /me                     # Profilo utente corrente
│   └── DELETE /me                   # GDPR: richiesta cancellazione account
│
├── monitor/                         # [FREE: community only] [PRO: tutti i perimetri]
│   ├── GET /meta?perimeter=set11&format=core
│   ├── GET /deck/{code}?perimeter=set11
│   ├── GET /players/{deck}?perimeter=set11&limit=20
│   ├── GET /tech-tornado?perimeter=set11
│   ├── GET /matchup-matrix?format=core&perimeter=set11
│   └── GET /leaderboard?queue=S11-BO1&limit=70
│
├── coach/                           # [PRO only]
│   ├── GET /matchup/{our}/{opp}?format=core
│   ├── GET /killer-curves/{our}/{opp}?format=core
│   ├── GET /threats/{our}/{opp}?format=core
│   ├── GET /playbook/{our}/{opp}?format=core
│   └── GET /history/{our}/{opp}?days=30
│
├── lab/                             # [PRO only]
│   ├── GET /optimizer/{our}/{opp}?format=core
│   ├── GET /mulligans/{our}/{opp}?format=core&mode=blind
│   ├── GET /card-scores/{our}/{opp}?format=core
│   └── GET /card-impact/{our}/{opp}?format=core
│
├── user/
│   ├── GET    /decks
│   ├── POST   /decks               # Salva deck nel profilo
│   ├── PUT    /decks/{id}           # Aggiorna deck
│   ├── DELETE /decks/{id}
│   ├── GET    /preferences
│   ├── PUT    /preferences          # Lingua, notifiche, deck preferito
│   └── GET    /export               # GDPR: esporta tutti i dati utente
│
├── team/                            # [TEAM tier only]
│   ├── GET /roster
│   ├── GET /player/{name}/stats
│   ├── GET /overview
│   └── GET /weaknesses
│
├── admin/                           # [Admin only]
│   ├── POST /refresh-daily
│   ├── POST /refresh-curves/{deck}
│   ├── GET  /health
│   ├── GET  /metrics
│   └── GET  /logs?level=error&limit=100
│
└── webhooks/
    └── POST /stripe                 # Webhook Stripe (signature verificata)
```

### 7.2 Paywall (Tier Enforcement)

```python
# backend/deps.py
TIER_LEVEL = {"free": 0, "pro": 1, "team": 2}

def require_tier(min_tier: str):
    async def check(current_user = Depends(get_current_user)):
        if TIER_LEVEL.get(current_user.tier, 0) < TIER_LEVEL[min_tier]:
            raise HTTPException(403, {"error": "upgrade_required", "required_tier": min_tier})
        return current_user
    return check

# Uso:
@router.get("/killer-curves/{our}/{opp}")
async def get_killer_curves(our: str, opp: str, user = Depends(require_tier("pro"))):
    ...
```

---

## 8. Sicurezza — 5 Livelli

### 8.1 Livello 1: Rete

```
- nginx: unico punto esposto a internet
- Firewall UFW: solo porte 80, 443, 22
- SSH: solo key authentication, no password, no root login
- PostgreSQL: listen su localhost only (127.0.0.1:5432)
- Redis: listen su localhost only (127.0.0.1:6379)
- Nessun servizio interno esposto all'esterno
```

### 8.2 Livello 2: Trasporto

```
- TLS 1.2+ obbligatorio (Let's Encrypt, auto-renewal certbot)
- HSTS header: forza HTTPS, il browser non prova mai HTTP
- HTTP :80 → redirect 301 a HTTPS :443
```

### 8.3 Livello 3: Autenticazione e Autorizzazione

```
AUTENTICAZIONE (chi sei):

  Password:
  - bcrypt cost 12 (~250ms per hash — resiste a brute force)
  - Minimo 8 caratteri
  - Controllata contro lista password comuni (top 10K)
  - Mai loggata, mai trasmessa in chiaro, mai salvata in plain text

  Token:
  - Access token JWT: 15 minuti durata, HS256, secret da env var (256 bit random)
  - Refresh token: 30 giorni durata, hashato in DB (user_sessions), revocabile
  - Il client manda: Authorization: Bearer <access_token>

  Flusso:
  1. POST /login → email + password → verifica bcrypt
  2. OK → ritorna access_token (15min) + refresh_token (30gg)
  3. Ogni richiesta: middleware verifica JWT → estrae user_id, tier, is_admin
  4. Token scaduto: POST /refresh con refresh_token → nuovo access_token
  5. Logout: revoca refresh_token in DB (revoked_at = now)

AUTORIZZAZIONE (cosa puoi fare):

  Tier enforcement:
  - free: monitor community, killer curves parziali, mulligan limitato
  - pro: tutti i perimetri, coach, lab, storico
  - team: tutto + team training + 5 account
  - admin: trigger pipeline, health, metrics, logs

  Data isolation:
  - user_id preso dal JWT server-side, MAI dal client
  - Ogni utente vede/modifica solo i SUOI dati
  - Admin: accesso a tutto
```

### 8.4 Livello 4: Rate Limiting

```
  Login:          5 tentativi / 15 minuti per IP
  API free tier:  100 richieste / minuto
  API pro tier:   500 richieste / minuto
  API team tier:  1000 richieste / minuto
  Webhook Stripe: nessun limit (IP whitelist)
```

### 8.5 Livello 5: Headers HTTP e Protezione Web

```
  Content-Security-Policy: default-src 'self'; script-src 'self'; img-src 'self' cards.duels.ink
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=()
  CORS: solo dominio proprio (lorcanamonitor.com)
  Cookie (se usati): Secure, HttpOnly, SameSite=Strict
  CSRF: non necessario con JWT Bearer (no cookie auth)
```

### 8.6 Attacchi Comuni — Difese

| Attacco | Difesa |
|---------|--------|
| Brute force login | Rate limit 5/15min per IP + bcrypt lento (250ms) |
| SQL injection | SQLAlchemy ORM (zero SQL raw) + Pydantic validation |
| XSS | CSP header + no innerHTML con dati utente |
| CSRF | JWT Bearer (non cookie-based) → CSRF non applicabile |
| Token theft | Access token 15min (vita breve) + refresh revocabile |
| Session hijacking | Refresh token hashato in DB, legato a IP/device |
| Privilege escalation | user_id dal JWT server-side, mai dal client |
| DDoS | nginx rate limit + Cloudflare free tier (futuro) |
| Stripe webhook spoofing | Verifica HMAC-SHA256 signature + IP whitelist |

---

## 9. Pagamenti — Stripe + Apple Pay + Google Pay

### 9.1 Metodi di pagamento (tutti via Stripe)

```
┌─────────────────────────────────────────────────┐
│           STRIPE CHECKOUT (hosted)               │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │  Carte   │  │  Apple   │  │  Google  │      │
│  │ Visa/MC/ │  │   Pay    │  │   Pay    │      │
│  │ Amex     │  │          │  │          │      │
│  └──────────┘  └──────────┘  └──────────┘      │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │  SEPA    │  │  iDEAL   │  │  Bancon- │      │
│  │  (EU DD) │  │   (NL)   │  │  tact    │      │
│  └──────────┘  └──────────┘  └──────────┘      │
│                                                  │
│  Apple Pay e Google Pay: abilitati con toggle   │
│  nel dashboard Stripe. Zero codice extra.       │
│  Su iPhone vedono Apple Pay, su Android Google.  │
└─────────────────────────────────────────────────┘
```

**PayPal**: integrazione separata (non via Stripe per subscription). NON prioritario alla Fase 1 — aggiungere solo se utenti lo richiedono. Complessita' doppia per ~10-15% del mercato.

### 9.2 Flusso Pagamento

```
1. Utente clicca "Upgrade to Pro"
   → Frontend: POST /api/v1/subscribe {tier: "pro"}

2. Backend:
   - Verifica utente loggato (JWT)
   - Crea Stripe Checkout Session:
     · price: STRIPE_PRICE_PRO_MONTHLY (12 EUR)
     · mode: "subscription"
     · payment_method_types: [card] (Apple/Google Pay inclusi)
     · success_url: /dashboard?upgraded=true
     · cancel_url: /pricing
     · customer_email: utente.email
   - Ritorna {checkout_url: "https://checkout.stripe.com/..."}

3. Frontend: redirect a Stripe Checkout (pagina hosted da Stripe)
   I dati della carta NON toccano MAI il nostro server (PCI compliant)

4. Utente paga (carta, Apple Pay, Google Pay, SEPA)

5. Stripe manda webhook: POST /webhooks/stripe
   - Backend verifica firma HMAC-SHA256 (STRIPE_WEBHOOK_SECRET)
   - Event checkout.session.completed:
     → Crea record subscription (status: active)
     → user.tier = 'pro'
     → Audit log: "subscription_created"

6. Redirect a success_url → utente vede dashboard Pro
```

### 9.3 Rinnovi e Cancellazioni

```
Rinnovo mensile automatico:
  - Stripe tenta il pagamento
  - Webhook invoice.paid → rinnova current_period_end
  - Webhook invoice.payment_failed → subscription.status = 'past_due'
  - Dopo 3 tentativi falliti → status = 'cancelled', user.tier = 'free'

Cancellazione volontaria:
  - Utente cancella dal profilo
  - Backend: subscription.cancel_at = fine periodo corrente
  - Accesso pro fino a scadenza, poi downgrade automatico

Webhook gestiti:
  - checkout.session.completed → attiva subscription
  - invoice.paid → rinnova
  - invoice.payment_failed → past_due
  - customer.subscription.deleted → tier = free
  - charge.refunded → log
```

### 9.4 Sicurezza Pagamenti

| Aspetto | Gestione |
|---------|---------|
| Dati carte | Mai sul nostro server. Stripe Checkout e' hosted. PCI DSS compliance automatica |
| Webhook auth | Signature HMAC-SHA256 verificata + IP whitelist nginx |
| Doppia verifica | Webhook + polling stripe.Subscription.retrieve() |
| Frode | Stripe Radar incluso (ML anti-frode, gratis) |
| SCA (EU PSD2) | Stripe gestisce 3D Secure automaticamente per carte EU |
| Refund | Via Stripe Dashboard o API. Webhook charge.refunded |

### 9.5 Fee Stripe

```
Carta EU:       1.5% + 0.25 EUR
Carta non-EU:   2.5% + 0.25 EUR
Apple/Google Pay: stessa fee (passa via Stripe)
SEPA Direct Debit: 0.35 EUR flat

Su 12 EUR/mese Pro:
  Carta EU: 0.43 EUR fee → incassi 11.57 EUR
  SEPA:     0.35 EUR fee → incassi 11.65 EUR
```

### 9.6 iOS App Store — In-App Purchase

Se l'app e' su App Store con contenuti digitali, Apple richiede IAP (30% fee, o 15% small business).

```
Strategia consigliata:

Fase 1: Solo PWA (no App Store)
  - PWA su iOS funziona (Add to Home Screen)
  - Zero fee Apple, zero review process
  - Pagamento via web (Stripe, 1.5%)

Fase 2: App Store con pagamento web-only
  - App iOS e' solo un viewer, login con credenziali web
  - Pagamento avviene su lorcanamonitor.com (non nell'app)
  - Apple non puo' forzare IAP se il pagamento e' esterno
  - MA: non puoi linkare al sito di pagamento dall'app

Fase 3: Dual pricing (se necessario)
  - Web: 12 EUR/mese (Stripe)
  - iOS: 15 EUR/mese (IAP, Apple prende 30%)
```

---

## 10. Privacy e GDPR

### 10.1 Dati Personali Raccolti

| Dato | Necessario | Conservazione | Base legale |
|------|-----------|---------------|-------------|
| Email | Si (login) | Fino a cancellazione account | Contratto |
| Password hash | Si (auth) | Fino a cancellazione account | Contratto |
| IP address (log) | Si (sicurezza) | 90 giorni, poi anonimizzato | Interesse legittimo |
| Stripe customer ID | Si (pagamento) | Fino a cancellazione + 10 anni fiscali | Obbligo legale |
| Preferenze utente | No (opzionale) | Fino a cancellazione account | Consenso |
| Deck salvati | No (opzionale) | Fino a cancellazione account | Contratto |

### 10.2 Diritti Utente (GDPR Art. 15-22)

| Diritto | Implementazione |
|---------|----------------|
| **Accesso** | `GET /api/v1/user/export` — dump JSON completo |
| **Rettifica** | `PUT /api/v1/user/preferences` + `PUT /decks/{id}` |
| **Cancellazione** | `DELETE /api/v1/auth/me` — soft delete, hard delete dopo 30gg |
| **Portabilita'** | Export JSON machine-readable (stesso endpoint accesso) |
| **Opposizione** | Unsubscribe email nel profilo |

### 10.3 Flusso Cancellazione Account

```
1. DELETE /api/v1/auth/me
   → user.deletion_requested_at = now()
   → user.is_active = false
   → revoca tutte le sessioni
   → email conferma: "Account schedulato per cancellazione in 30 giorni"

2. Dopo 30 giorni (worker):
   → DELETE CASCADE: user_decks, subscriptions, user_sessions, password_reset_tokens
   → Anonimizza audit_log: user_id = NULL
   → DELETE users WHERE id = ...
   → Log: "account_permanently_deleted"

3. Stripe:
   → Cancella subscription se attiva
   → Dati fiscali conservati 10 anni (obbligo legale)
```

### 10.4 Cosa NON loggare MAI

- Password (neanche hashate)
- JWT token completi
- Numeri carte (gestiti da Stripe, non toccano il server)
- Refresh token in chiaro
- Dati personali nel log applicativo (solo user_id UUID)

---

## 11. Dominio e Routing

### 11.1 DNS (Cloudflare free tier)

```
A     lorcanamonitor.com      → 157.180.46.188
A     www.lorcanamonitor.com  → 157.180.46.188
MX    lorcanamonitor.com      → mail provider (Resend/Postmark)
TXT   _dmarc                  → "v=DMARC1; p=quarantine"
TXT   @                       → "v=spf1 include:resend.com -all"
```

Cloudflare: gestione DNS + proxy opzionale (DDoS protection, CDN) + analytics gratis.

### 11.2 Routing nginx

```
https://lorcanamonitor.com/                → frontend static (index.html SPA)
https://lorcanamonitor.com/assets/*        → CSS, JS, immagini (cache 7gg)
https://lorcanamonitor.com/api/v1/*        → FastAPI reverse proxy
https://lorcanamonitor.com/health          → nginx diretto (200 OK, uptime check)
http://*                                   → redirect 301 → https://*
```

### 11.3 nginx Config

```nginx
upstream api {
    server 127.0.0.1:8000;
}

# Rate limit zones
limit_req_zone $binary_remote_addr zone=api:10m rate=100r/m;
limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;

server {
    listen 443 ssl http2;
    server_name lorcanamonitor.com www.lorcanamonitor.com;

    ssl_certificate /etc/letsencrypt/live/lorcanamonitor.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/lorcanamonitor.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "strict-origin" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;

    # Frontend statico
    location / {
        root /var/www/lorcana/frontend;
        try_files $uri $uri/ /index.html;

        location ~* \.(js|css|png|jpg|svg|woff2)$ {
            expires 7d;
            add_header Cache-Control "public, immutable";
        }
    }

    # API
    location /api/ {
        proxy_pass http://api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        limit_req zone=api burst=20 nodelay;
    }

    # Login: rate limit piu' aggressivo
    location /api/v1/auth/login {
        proxy_pass http://api;
        limit_req zone=login burst=3 nodelay;
    }

    # Webhook Stripe: IP whitelist, no rate limit
    location /api/v1/webhooks/stripe {
        proxy_pass http://api;
        allow 3.18.12.63;
        allow 3.130.192.163;
        deny all;
    }

    # Health check (no auth, no rate limit)
    location /health {
        proxy_pass http://api/api/v1/admin/health;
    }
}

# Redirect HTTP -> HTTPS
server {
    listen 80;
    server_name lorcanamonitor.com www.lorcanamonitor.com;
    return 301 https://lorcanamonitor.com$request_uri;
}
```

---

## 12. Backup, Recovery, Disaster Plan

### 12.1 Strategia Backup (3-2-1)

```
3 copie dei dati:
  1. PostgreSQL live (VPS Hetzner)
  2. Backup locale compresso (stesso VPS, volume separato)
  3. Backup remoto criptato (Hetzner Storage Box, ~3 EUR/mese)

2 supporti diversi:
  - SSD VPS (produzione)
  - HDD Storage Box (backup offsite)

1 copia offsite:
  - Storage Box in datacenter diverso dal VPS
```

### 12.2 Schedule

| Cosa | Frequenza | Retention | Dove |
|------|-----------|-----------|------|
| PostgreSQL full dump | Giornaliero 03:00 | 7 giorni rolling | Locale + offsite |
| PostgreSQL WAL archiving | Continuo | 48 ore | Locale |
| Match JSON originali | Immutabili | Permanente | Volume Hetzner |
| Codice + config | Ad ogni push | Completo | Git (GitHub/GitLab) |
| .env (secrets) | Ad ogni modifica | Volume + Storage Box | MAI su Git |
| Killer curves (storico) | In PostgreSQL | Tutte le versioni | (nel dump) |

### 12.3 Script Backup

```bash
#!/bin/bash
# db/backup.sh — systemd timer ogni giorno 03:00

set -euo pipefail

BACKUP_DIR="/mnt/HC_Volume_104764377/backups/lorcana"
REMOTE="u123456@u123456.your-storagebox.de"
DATE=$(date +%Y%m%d_%H%M)
RETAIN_DAYS=7

# 1. Dump PostgreSQL (formato custom, compresso)
pg_dump -Fc -Z6 lorcana > "${BACKUP_DIR}/pg_${DATE}.dump"

# 2. Cripta con GPG (AES-256)
gpg --batch --symmetric --cipher-algo AES256 \
    --passphrase-file /root/.backup_passphrase \
    "${BACKUP_DIR}/pg_${DATE}.dump"
rm "${BACKUP_DIR}/pg_${DATE}.dump"

# 3. Upload offsite
scp "${BACKUP_DIR}/pg_${DATE}.dump.gpg" "${REMOTE}:lorcana/"

# 4. Cleanup locale
find "${BACKUP_DIR}" -name "pg_*.dump.gpg" -mtime +${RETAIN_DAYS} -delete

# 5. Cleanup remoto
ssh "${REMOTE}" "find lorcana/ -name 'pg_*.dump.gpg' -mtime +${RETAIN_DAYS} -delete"

# 6. Log + alert se errore
echo "[$(date)] Backup OK: pg_${DATE}.dump.gpg" >> /var/log/lorcana/backup.log
```

### 12.4 Disaster Recovery — 5 Scenari

**Scenario 1: Processo crasha (FastAPI, worker, nginx)**
```
Difesa:    systemd Restart=always, RestartSec=5
Recovery:  Automatico in 5 secondi
Downtime:  5 secondi
Dati persi: Zero
```

**Scenario 2: PostgreSQL crasha**
```
Difesa:    WAL (Write-Ahead Log) garantisce consistency
Recovery:  systemd riavvia PostgreSQL, WAL replay automatico
Downtime:  10-30 secondi
Dati persi: Zero (WAL e' il journal)
```

**Scenario 3: Disco corrotto (dati PostgreSQL persi)**
```
Difesa:    Backup giornaliero (pg_dump) locale + offsite
Recovery:
  1. Stop servizi
  2. pg_restore dall'ultimo dump locale
     Se corrotto: scarica da Storage Box offsite
  3. Replay WAL se disponibili (point-in-time recovery)
  4. Restart servizi
Downtime:  15-30 minuti
Dati persi: Max 24 ore (tra un backup e l'altro)
Mitigazione: WAL archiving continuo riduce a ~minuti
```

**Scenario 4: VPS completamente morto**
```
Difesa:
  - Volume Hetzner indipendente dal VPS (sopravvive)
  - Backup offsite su Storage Box
  - Codice su Git
Recovery:
  1. Crea nuovo VPS Hetzner (stessa region per montare il volume)
  2. Monta il volume (match JSON e backup locali gia' li')
  3. apt install postgresql nginx redis python3
  4. git clone → /opt/lorcana
  5. Restore .env da backup sicuro
  6. pg_restore dal dump su Storage Box
  7. certbot certonly (nuovo certificato SSL)
  8. systemctl start lorcana-api lorcana-worker
  9. Aggiorna DNS (nuovo IP, propaga in <5 min con Cloudflare TTL basso)
Downtime:  30-60 minuti
Dati persi: Max 24 ore
```

**Scenario 5: Datacenter Hetzner down (catastrofico)**
```
Difesa:
  - Storage Box in datacenter diverso
  - Git repo esterno (GitHub/GitLab)
Recovery:
  1. Provisiona VPS in altro datacenter Hetzner (o altro cloud)
  2. Restore tutto da Storage Box + Git
  3. Rigenera SSL, aggiorna DNS
Downtime:  1-2 ore
Probabilita': Bassissima (Hetzner SLA 99.9%)
```

### 12.5 Test Backup Mensile

```bash
# Cron primo lunedi del mese: test restore su DB temporaneo
createdb lorcana_test_restore
pg_restore -d lorcana_test_restore /mnt/HC_Volume_104764377/backups/lorcana/pg_LATEST.dump
# Se fallisce: alert Telegram
dropdb lorcana_test_restore
```

---

## 13. Logging e Monitoring

### 13.1 3 Tipi di Log

**Request log** (ogni richiesta API → `/var/log/lorcana/api.log`):
```json
{
    "ts": "2026-03-27T07:01:23Z",
    "level": "INFO",
    "method": "GET",
    "path": "/api/v1/coach/killer-curves/AmAm/ES",
    "status": 200,
    "duration_ms": 45,
    "user_id": "uuid-...",
    "tier": "pro",
    "ip": "1.2.3.4"
}
```

**Audit log** (eventi sensibili → tabella `audit_log` in DB):
- login, login_failed, logout
- password_change, password_reset
- subscription_created, subscription_cancelled
- account_delete_requested, account_permanently_deleted
- admin_action (refresh pipeline, etc.)
- Conservato 1 anno

**Security log** (anomalie → alert Telegram immediato):
- Rate limit superato
- JWT invalid/expired/tampered
- Tier violation (free prova ad accedere a pro)
- Stripe webhook signature invalida
- Login falliti ripetuti (>5 dallo stesso IP)

### 13.2 Livelli

| Livello | Cosa | Esempio |
|---------|------|---------|
| ERROR | Blocca la richiesta | DB connection failed, Stripe webhook invalido |
| WARN | Anomalia non bloccante | Rate limit vicino, LLM timeout, disk 80% |
| INFO | Operazione normale | Request completata, pipeline OK, backup OK |
| DEBUG | Troubleshooting (solo dev) | Query SQL, token decoded, cache hit/miss |

### 13.3 Log Rotation

```
/var/log/lorcana/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

### 13.4 Health Check

```python
# GET /api/v1/admin/health
{
    "status": "healthy",        # healthy, degraded, down
    "checks": {
        "database":    {"status": "ok", "latency_ms": 2},
        "redis":       {"status": "ok", "latency_ms": 1},
        "disk_free_gb": 59,
        "memory_used_pct": 43,
        "last_daily_pipeline": "2026-03-27T07:01:00Z",
        "last_backup": "2026-03-27T03:00:00Z",
        "match_count": 64347,
        "active_users": 42,
        "uptime_seconds": 86400
    }
}
```

### 13.5 Alerting (Telegram)

```bash
# infra/monitoring/uptime.sh — cron ogni 5 minuti

HEALTH=$(curl -sf http://localhost:8000/api/v1/admin/health)
STATUS=$(echo "$HEALTH" | jq -r '.status')

if [ "$STATUS" != "healthy" ]; then
    curl -X POST "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
        -d "chat_id=${TG_CHAT}" \
        -d "text=Lorcana Monitor: status=${STATUS}"
fi

# Alert disco <5GB
DISK_FREE=$(df --output=avail /mnt/HC_Volume_104764377 | tail -1)
if [ "$DISK_FREE" -lt 5242880 ]; then
    curl -X POST "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
        -d "chat_id=${TG_CHAT}" -d "text=Disco quasi pieno: ${DISK_FREE}KB"
fi
```

---

## 14. Performance Optimization

### 14.1 Da 22s a <100ms per Matchup

| Oggi | Domani | Speedup |
|------|--------|---------|
| Scan 64K file JSON da disco | Query PostgreSQL con indice composto | **200x** |
| Parse JSON in Python per ogni file | Dati strutturati in colonne + JSONB | **50x** |
| Ricalcola WR ad ogni request | Materialized view, refresh 1x/giorno | **Istantaneo** |
| Dashboard_data.json 4MB embedded | API per tab, dati on-demand | **10x meno banda** |

### 14.2 Caching (Redis)

```
Redis (in-memory, ~50MB):

  cache:monitor:{perimeter}:{format}       TTL: 1 ora
  cache:coach:{our}:{opp}:{format}         TTL: 6 ore
  cache:lab:{our}:{opp}:{format}           TTL: 6 ore
  cache:leaderboard:{queue}                TTL: 30 minuti

Invalidazione:
  Dopo pipeline daily: delete pattern cache:monitor:*
  Dopo LLM worker: delete cache:coach:{matchup aggiornato}
  Dopo admin refresh: delete specifico

Fallback: se Redis down, query diretta PostgreSQL (piu' lento, funziona)
```

### 14.3 Compressione e CDN

- **nginx gzip**: HTML, JSON, JS, CSS
- **Brotli** (opzionale): 15-25% meglio di gzip su JSON
- **CDN (futuro)**: Cloudflare free tier per static assets + DDoS protection
- **Immagini carte**: proxy cache da cards.duels.ink, nginx 30gg cache

---

## 15. Frontend — PWA + Mobile

### 15.1 PWA (Fase 1)

Il dashboard attuale diventa Progressive Web App:
- `manifest.json` per "Add to Home Screen" su iOS/Android
- `sw.js` Service Worker per cache offline
- Tutte le richieste via `fetch('/api/v1/...')` con Bearer token
- Responsive gia' fatto (viewport, safe area, touch target 44px)

**Cache strategy (Service Worker):**
```
Assets statici (CSS, JS, chart.min.js): Cache First, 7gg
API data (monitor, coach, lab): Network First, fallback su cache
Immagini carte (cards.duels.ink): Cache First, 30gg
Auth endpoints: Network Only (mai cachati)
```

### 15.2 iOS Nativo (Fase 2 — Capacitor)

Stesso codice web wrappato con Capacitor per App Store:
- Push notification native (nuove killer curves, meta shift)
- Touch ID / Face ID per login
- Badge icona con alert non letti
- Stesso backend, stessa API

```bash
# Build
npm install @capacitor/core @capacitor/ios
npx cap add ios
npx cap sync ios
# → Apri Xcode, build, submit
```

**Perche' Capacitor e non React Native:**
- Zero rewrite (il frontend e' gia' HTML/JS)
- 1 codebase per web + iOS + Android
- Plugin nativi (push, biometrics) senza riscrivere

---

## 16. Pipeline e Workers

### 16.1 Schedule

| Ora | Worker | Cosa fa |
|-----|--------|---------|
| 03:00 | `backup_worker.py` | pg_dump + GPG + upload offsite |
| 06:00 | `match_importer.py` | Importa nuovi JSON match → PostgreSQL |
| 06:30 | `match_importer.py` | Refresh materialized views |
| 07:00 | `daily_pipeline.py` | Genera dati Monitor |
| 07:01 | `daily_pipeline.py` | Raccoglie killer curves, parsa threats |
| Lunedi 08:00 | `weekly_pipeline.py` | Genera dati Coach + Lab |
| On-demand | `llm_worker.py` | Killer curves via Claude API Batch |

### 16.2 LLM Worker (Claude API)

```
Oggi (analisidef):
  claude -p "..." --model sonnet < digest.json > killer_curves.json
  Seriale, 1 alla volta, ~3 ore per 50 matchup

Domani (App_tool):
  Claude API Batch (50% sconto, asincrono)
  + Prompt Caching (cards_db + system prompt cachati, 90% risparmio input)
  = ~6 EUR/mese per 50 matchup/notte
```

### 16.3 Resilienza

| Failure | Recovery |
|---------|----------|
| Import match interrotto | `external_id UNIQUE` → ON CONFLICT DO NOTHING → riparte |
| Pipeline daily fallisce | systemd Restart=always. Dati vecchi restano serviti |
| LLM timeout | Retry con backoff. Killer curves vecchie restano current |
| Backup fallisce | Alert Telegram. Volume Hetzner persistente |
| PostgreSQL down | systemd riavvia. WAL recovery automatico |
| Redis down | Fallback a PostgreSQL diretto |
| Disco pieno | Alert a 5GB. Match JSON vecchi archivabili |

---

## 17. Workflow Dev/Prod e Deploy

### 17.1 Git

```
Repository: github.com/user/lorcana-monitor (privato)

Branches:
  main          → produzione (deployed sul VPS)
  develop       → sviluppo
  feature/*     → feature branch (da develop)
  hotfix/*      → fix urgenti (da main, merge in main + develop)
```

### 17.2 Ambienti

```
DEV (stesso VPS o locale):
  - uvicorn --reload --port 8001
  - PostgreSQL database "lorcana_dev"
  - Redis database 1
  - .env.dev: APP_ENV=development, LOG_LEVEL=DEBUG
  - Stripe test mode (sk_test_..., carte fake 4242...)

PROD (VPS Hetzner):
  - uvicorn via systemd, 4 worker, porta 8000
  - PostgreSQL database "lorcana"
  - Redis database 0
  - .env: APP_ENV=production, LOG_LEVEL=INFO
  - Stripe live mode (sk_live_...)
  - nginx :443 davanti
```

### 17.3 Deploy Zero-Downtime

```bash
#!/bin/bash
# scripts/deploy.sh

set -euo pipefail
LOG="/var/log/lorcana/deploy.log"
echo "[$(date)] Deploy started" >> "$LOG"

cd /opt/lorcana

# 1. Pull codice
git fetch origin main
git reset --hard origin/main

# 2. Dipendenze (solo se cambiate)
if git diff HEAD~1 --name-only | grep -q "requirements.txt"; then
    venv/bin/pip install -r requirements.txt >> "$LOG" 2>&1
fi

# 3. Migra database
venv/bin/alembic upgrade head >> "$LOG" 2>&1

# 4. Validazione schema
venv/bin/python -m schemas.validate >> "$LOG" 2>&1

# 5. Reload graceful (zero downtime)
#    SIGHUP → uvicorn ricarica i worker uno alla volta
#    Worker attivi finiscono le richieste, poi si riavviano col codice nuovo
systemctl reload lorcana-api

# 6. Verifica health
sleep 2
STATUS=$(curl -sf http://localhost:8000/api/v1/admin/health | jq -r '.status')
if [ "$STATUS" = "healthy" ]; then
    echo "[$(date)] Deploy OK" >> "$LOG"
else
    echo "[$(date)] Deploy WARN: health=$STATUS" >> "$LOG"
    # Alert Telegram
    curl -sf -X POST "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
        -d "chat_id=${TG_CHAT}" -d "text=Deploy: health=$STATUS"
fi
```

**Perche' e' zero-downtime:** `systemctl reload` (non restart) invia SIGHUP a uvicorn. I worker attivi finiscono le richieste in corso, poi ripartono col codice nuovo. In ogni momento almeno 1-2 worker sono attivi.

### 17.4 Rollback

```bash
# Rollback codice (immediato, <10 secondi)
ssh vps 'cd /opt/lorcana && git reset --hard HEAD~1 && systemctl reload lorcana-api'

# Rollback database migration
ssh vps 'cd /opt/lorcana && venv/bin/alembic downgrade -1'

# Rollback nucleare (restore da backup)
ssh vps 'pg_restore -d lorcana --clean /mnt/HC_Volume/backups/pg_LATEST.dump'
```

### 17.5 CI/CD (Fase 2, opzionale)

```
GitHub Actions (gratis, 2000 min/mese):
  push su main →
    1. pytest (PostgreSQL test in Docker)
    2. Se OK: SSH al VPS, esegue deploy.sh
    3. Se FAIL: notifica, non deploya

Per Fase 1: deploy manuale con deploy.sh e' sufficiente.
```

---

## 18. Infrastruttura Hetzner

### 18.1 Server Attuale

| Risorsa | Valore |
|---------|--------|
| OS | Ubuntu 24.04 LTS |
| CPU | 2 vCPU |
| RAM | 3.7 GB |
| Volume montato | 89 GB (30% usato, 59 GB liberi) |
| IP | 157.180.46.188 |

### 18.2 Layout Produzione

```
┌─────────────────────────────────────────────────────┐
│  Hetzner VPS                                         │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │  nginx   │  │ FastAPI  │  │ PostgreSQL│          │
│  │  :443    │→ │ :8000    │→ │ :5432     │          │
│  │  SSL/TLS │  │ 4 worker │  │           │          │
│  └──────────┘  └──────────┘  └──────────┘          │
│  ┌──────────┐  ┌──────────┐                         │
│  │  Redis   │  │ Workers  │                         │
│  │  :6379   │  │ cron +   │                         │
│  │          │  │ LLM      │                         │
│  └──────────┘  └──────────┘                         │
│                                                      │
│  Volume: /mnt/HC_Volume (89GB)                      │
│    - Match JSON originali (3GB, read-only)          │
│    - PostgreSQL data                                 │
│    - Backup locali                                   │
│                                                      │
│  Hetzner Storage Box (100GB, offsite, ~3 EUR/mese)  │
└─────────────────────────────────────────────────────┘
```

### 18.3 systemd Services

```ini
# lorcana-api.service
[Unit]
Description=Lorcana Monitor API
After=network.target postgresql.service redis.service

[Service]
Type=exec
User=lorcana
WorkingDirectory=/opt/lorcana/backend
EnvironmentFile=/opt/lorcana/.env
ExecStart=/opt/lorcana/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 4
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=5
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/var/log/lorcana /opt/lorcana/output

[Install]
WantedBy=multi-user.target
```

```ini
# lorcana-worker.service
[Unit]
Description=Lorcana Monitor Workers
After=network.target postgresql.service

[Service]
Type=exec
User=lorcana
WorkingDirectory=/opt/lorcana/backend
EnvironmentFile=/opt/lorcana/.env
ExecStart=/opt/lorcana/venv/bin/python -m workers.scheduler
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## 19. Variabili Ambiente (.env)

```bash
# Database
DATABASE_URL=postgresql://lorcana:STRONG_PASSWORD@localhost:5432/lorcana
DATABASE_URL_DEV=postgresql://lorcana:devpass@localhost:5432/lorcana_dev
REDIS_URL=redis://localhost:6379/0

# Auth
JWT_SECRET=<256-bit-random-hex>
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30

# Stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_PRO_MONTHLY=price_...
STRIPE_PRICE_TEAM_MONTHLY=price_...

# Claude API
ANTHROPIC_API_KEY=sk-ant-...

# Paths
MATCH_JSON_DIR=/mnt/HC_Volume_104764377/finanza/Lor/matches
CARDS_DB_PATH=/mnt/HC_Volume_104764377/finanza/Lor/cards_db.json
DECKS_DB_DIR=/mnt/HC_Volume_104764377/finanza/Lor/decks_db

# Backup
BACKUP_LOCAL_DIR=/mnt/HC_Volume_104764377/backups/lorcana
BACKUP_REMOTE=u123456@u123456.your-storagebox.de
BACKUP_GPG_PASSPHRASE_FILE=/root/.backup_passphrase

# Monitoring
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...

# App
APP_ENV=production
LOG_LEVEL=INFO
CORS_ORIGINS=https://lorcanamonitor.com
```

---

## 20. Dipendenze

```
# requirements.txt
fastapi>=0.115
uvicorn[standard]>=0.30
sqlalchemy>=2.0
alembic>=1.13
asyncpg>=0.30              # PostgreSQL async driver
psycopg2-binary>=2.9       # PostgreSQL sync (scripts)
redis>=5.0
pydantic>=2.0
python-jose[cryptography]  # JWT
passlib[bcrypt]             # Password hashing
stripe>=10.0
httpx>=0.27                 # Async HTTP (duels.ink, Claude API)
anthropic>=0.40             # Claude API SDK
python-multipart>=0.0.9    # Form data
structlog>=24.0             # Structured logging
apscheduler>=3.10           # Scheduler workers
```

---

## 21. Costi Produzione

| Voce | Mese 1-3 | Mese 6 | Mese 12 |
|------|----------|--------|---------|
| VPS Hetzner CX21 | 5 EUR | 5 EUR | 9 EUR (upgrade CX31) |
| Volume 100GB | 4 EUR | 4 EUR | 4 EUR |
| Storage Box 100GB (backup) | 3 EUR | 3 EUR | 3 EUR |
| Dominio (.com) | 1 EUR | 1 EUR | 1 EUR |
| SSL (Let's Encrypt) | 0 | 0 | 0 |
| Claude API (Batch + Cache) | 0* | 0* | 8 EUR |
| Stripe fees (1.5% + 0.25) | 5 EUR | 40 EUR | 130 EUR |
| Apple Developer (iOS) | 0** | 8 EUR | 8 EUR |
| Email (Resend) | 0 | 0 | 10 EUR |
| **Totale** | **~18 EUR** | **~61 EUR** | **~173 EUR** |

*Coperto da Anthropic Startup Program ($25K crediti)
**iOS solo da Fase 2

---

## 22. Rilascio — Piano Operativo

> **Nota**: App_tool e' un progetto nuovo costruito in parallelo. `analisidef/` resta invariata.
> Gli script di import leggono i dati da analisidef in sola lettura (copia, non migrazione).
>
> **Vincolo API**: al 27/03/2026 non c'e' un piano Anthropic API con credito attivo.
> Tutto cio' che richiede chiamate Claude API (generazione killer curves, threat analysis,
> review tattiche) e' rimandato. Il backend serve i dati LLM gia' generati da analisidef
> e importati nel DB. Quando sara' disponibile credito API si aggiungera' il worker LLM.

### Fase 0 — Preparazione ✅ completata 27/03/2026
- [x] PostgreSQL 16 installato e attivo su VPS
- [x] Redis 7 installato e attivo
- [x] DB `lorcana` creato con utente `lorcana_app`
- [x] Python 3.12 virtualenv con dipendenze (SQLAlchemy, Alembic, asyncpg, psycopg2, pydantic)
- [x] File progetto: `requirements.txt`, `.env.example`, `.env`, `.gitignore`
- [x] `backend/config.py` — settings centralizzati da `.env`
- [ ] Creare utente sistema `lorcana` (non root) — rimandato a deploy produzione
- [ ] Setup firewall UFW (80, 443, 22) — rimandato a deploy produzione

### Fase 1 — Database + Import ✅ completata 27/03/2026
- [x] 11 tabelle PostgreSQL via Alembic migration autogenerata dai modelli ORM:
  - Auth: `users`, `user_sessions`, `password_reset_tokens`
  - Subscriptions: `subscriptions`
  - User data: `user_decks`
  - Match data: `matches` (BIGSERIAL, JSONB turns, 7 indici incl. composto `idx_matches_lookup`)
  - Analisi: `killer_curves`, `archives`, `threats_llm`, `daily_snapshots`
  - Audit: `audit_log`
- [x] 2 materialized views: `mv_meta_share`, `mv_matchup_matrix`
- [x] 7 modelli SQLAlchemy ORM in `backend/models/`
- [x] 2 Alembic migrations (001_initial + 002_widen_perimeter)
- [x] `scripts/import_matches.py`: 2,317 match importati da `/mnt/.../matches/` (JSON → PostgreSQL, batch 1000, winner fix v2)
- [x] `scripts/import_killer_curves.py`: 128 killer_curves importate da `analisidef/output/`
- [x] `scripts/import_history.py`: 102 snapshot storici importati da `analisidef/daily/output/history.db` (SQLite → PostgreSQL)
- [x] `scripts/benchmark_queries.py` — 5/6 query sotto target:
  - Matchup singolo: 49ms (target <50ms) ✅
  - Matrice 12x12: 6ms (target <500ms) ✅
  - Killer curves: 2ms (target <10ms) ✅
  - Meta share: 4ms (target <200ms) ✅
  - Top players: 4ms (target <200ms) ✅
  - Snapshot (tutti): 1.5s (target <100ms) — OK con query filtrate per perimeter
- [ ] Backup automatico + test restore — da configurare

### Fase 2 — Backend API ✅ completata 27/03/2026
- [x] FastAPI scaffold + `backend/main.py` (entrypoint con CORS, error handler, router mount)
- [x] `backend/deps.py` — dependency injection (db session)
- [x] 4 service modules in `backend/services/`:
  - `stats_service.py` — WR, matrice matchup, meta share, OTP/OTD, trend giornaliero
  - `players_service.py` — top players, leaderboard MMR, player detail
  - `matchup_service.py` — dettaglio matchup, killer curves, threats, storico
  - `deck_service.py` — card scores, deck breakdown, history snapshots
- [x] 4 route modules in `backend/api/`:
  - `monitor.py` — 7 endpoint (meta, deck, matchup-matrix, otp-otd, trend, leaderboard, winrates)
  - `coach.py` — 4 endpoint (matchup detail, killer-curves, threats, history)
  - `lab.py` — 2 endpoint (card-scores, history snapshots)
  - `admin.py` — 3 endpoint (health, refresh-views, metrics)
- [x] `backend/middleware/error_handler.py` — global exception handler
- [x] CORS middleware configurato (permissive in dev)
- [x] Swagger UI attivo su `/api/docs`
- [x] Bug fix: corretto `determine_winner()` in import_matches.py (winner in `data.winner`, non `entry.winner`)
- [x] Re-import match: 2,317 match con winner corretto (1,154 deck_a / 1,076 deck_b / 87 draw)
- [x] Tutti 16 endpoint testati con curl — risposte corrette
- [ ] Test suite automatizzata — da aggiungere
- [ ] Deploy uvicorn + systemd — rimandato a infra produzione
- [ ] Rate limiting per-endpoint — rimandato a Fase 3 (con tier enforcement)

### Fase 3 — Frontend Ponte (dashboard identica via analisidef)

> **Strategia**: App_tool serve la stessa dashboard di analisidef, leggendo il
> `dashboard_data.json` gia' prodotto dalla daily routine. Zero riscrittura del motore.
> analisidef continua a girare e a calcolare tutto. App_tool si occupa solo di servire.

- [x] Endpoint `GET /api/v1/dashboard-data` — `backend/api/dashboard.py`, legge `analisidef/daily/output/dashboard_data.json`
- [x] Template `dashboard.html` copiato in `App_tool/frontend/`, `loadData()` modificato per fetch da `/api/v1/dashboard-data`
- [x] File statici copiati: `manifest.json`, `icon-192.svg`, `icon-512.svg`
- [x] Verificato: dashboard su App_tool identica a quella su porta 8060
- [x] systemd service `lorcana-api.service` — uvicorn 2 workers, auto-restart, boot-enabled
- [x] nginx reverse proxy (porta 80 → uvicorn 8100) con security headers, gzip, timeouts
- [x] Dominio `metamonitor.app` registrato su Cloudflare, DNS A record → 157.180.46.188
- [x] SSL Let's Encrypt configurato (certbot + auto-renewal), scadenza 25/06/2026
- [x] HTTP → HTTPS redirect automatico (301)
- [x] Password protection HTTP Basic (nginx) — rimuovere quando si apre al pubblico

### Stabilizzazione infrastruttura ✅ completata 27/03/2026
- [x] Git repo `ema299/LorMonitor` su GitHub (privato), primo commit 49 file
- [x] Symlink `frontend/dashboard.html` → analisidef (dashboard sempre aggiornata con le modifiche in analisidef)
- [x] Backup automatico DB: cron 03:00, `scripts/backup.sh` (pg_dump + gzip, retention 7gg, dir `/backups/lorcana/`)
- [x] Import match automatico: cron 06:30, `scripts/import_matches.py` (ON CONFLICT DO NOTHING, solo nuovi)
- [x] Import killer curves: cron Mar+Gio 03:30, `scripts/import_killer_curves.py` (dopo batch generation analisidef)
- [x] `robots.txt` — blocca tutti i crawler (Disallow: /)
- [x] Health check: cron ogni 5 min, `scripts/healthcheck.sh` (auto-restart se API non risponde)
- [ ] Alerting Telegram — da aggiungere
- [ ] Load testing — da fare prima del lancio pubblico

**Cron schedule completo (App_tool):**
```
*/5 * * * *   healthcheck.sh          → auto-restart se down
0   3 * * *   backup.sh               → pg_dump + gzip + cleanup 7gg
30  3 * * 2,4 import_killer_curves.py  → importa nuove curve dopo batch
30  6 * * *   import_matches.py        → importa nuovi match da /matches/
```

**Cron schedule analisidef (invariato):**
```
0   2 * * 2,4 run_all_killer_curves.sh → genera killer curves (Claude API batch)
0   7 * * *   lorcana_monitor.py report
1   7 * * *   daily_routine.py         → genera dashboard_data.json
5   7 * * *   generate_and_send.py
```

### Piano di transizione verso autonomia (futuro)

```
OGGI — Fase A (ponte):
  lorcana_monitor.py cattura match → /matches/
  analisidef daily_routine → dashboard_data.json (calcoli, 6.7K LOC in lib/)
  App_tool serve dashboard_data.json via API → frontend identico
  App_tool ha il suo DB PostgreSQL (88K match, 162 killer curves)
  Le due cose coesistono senza interferire.

DOMANI — Fase B (motore copiato):
  Copiare analisidef/lib/ (16 moduli) in App_tool/lib/
  Adattare per leggere da PostgreSQL invece che da file JSON
  Testare: stessi input → stessi output (confronto con analisidef)
  Non sostituisce analisidef, gira in parallelo per validazione.

DOPO — Fase C (autonomia):
  Attivare worker cron in App_tool (daily_pipeline, match_importer)
  Verificare output identico per N giorni
  Spegnere daily routine di analisidef
  App_tool diventa autonoma. lorcana_monitor.py resta attivo.

Rischi e mitigazioni:
  Fase A: nessun rischio — analisidef non cambia
  Fase B: calcoli divergenti → confronto automatico output
  Fase C: worker fallisce → fallback a ultimo JSON di analisidef
```

### Fase 4 — Auth + Pagamento (3-4 giorni)
- [ ] Auth endpoints (register, login, logout, refresh, reset)
- [ ] JWT middleware (python-jose, 15min access + 30d refresh)
- [ ] Stripe (checkout, webhook, cancellation)
- [ ] Paywall enforcement per tier (free/pro/team)
- [ ] GDPR (export, delete)
- [ ] Audit log integration

### Fase 5 — Frontend PWA (4-5 giorni)
- [ ] manifest.json + Service Worker (offline cache)
- [ ] Login/register UI
- [ ] Test iOS Safari PWA
- [ ] Bottom nav mobile

### Fase 6 — Mobile iOS (3-4 giorni)
- [ ] Capacitor setup
- [ ] Push notifications
- [ ] Face ID login
- [ ] Build + submit App Store

### Fase 7 — Stabilizzazione continua
- [x] Backup automatico (cron 03:00, pg_dump, 7gg retention)
- [x] Health check (cron 5min, auto-restart)
- [x] robots.txt (no indexing)
- [x] Git repo GitHub (privato)
- [ ] Alerting Telegram (notifica se health check fallisce)
- [ ] Load testing (100 concurrent)
- [ ] Test restore backup mensile
- [ ] Aggiornamento dipendenze
