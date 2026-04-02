-- Phase 0: Static data tables for App_tool independence from analisidef
-- Run: psql -d lorcana -f scripts/migration/create_new_tables.sql

-- Cards database (from cards_db.json)
CREATE TABLE IF NOT EXISTS cards (
    name            TEXT PRIMARY KEY,
    ink             TEXT,
    card_type       TEXT,           -- Character, Action, Song, Item, Location
    cost            INTEGER,
    str             INTEGER,
    will            INTEGER,
    lore            INTEGER,
    ability         TEXT,
    classifications TEXT,
    set_code        TEXT,
    card_number     TEXT,
    rarity          TEXT,
    image_path      TEXT,           -- "{set_num}/{number}" for thumbnail URL
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Deck consensus lists (from inkdecks snapshots)
CREATE TABLE IF NOT EXISTS consensus_lists (
    id              BIGSERIAL PRIMARY KEY,
    deck            TEXT NOT NULL,
    card_name       TEXT NOT NULL,
    avg_qty         NUMERIC(3,1) NOT NULL,
    snapshot_date   DATE NOT NULL,
    is_current      BOOLEAN DEFAULT true,
    UNIQUE(deck, card_name, snapshot_date)
);
CREATE INDEX IF NOT EXISTS idx_consensus_current ON consensus_lists (deck) WHERE is_current = true;

-- Reference decklists (tournament winning lists)
CREATE TABLE IF NOT EXISTS reference_decklists (
    id              BIGSERIAL PRIMARY KEY,
    deck            TEXT NOT NULL,
    player          TEXT,
    rank            TEXT,
    event           TEXT,
    event_date      TEXT,
    record          TEXT,
    cards           JSONB NOT NULL,     -- [{qty, name}, ...]
    snapshot_date   DATE NOT NULL,
    is_current      BOOLEAN DEFAULT true,
    UNIQUE(deck, player, snapshot_date)
);

-- Matchup reports (parsed from .md reports — playbook, optimizer, etc.)
CREATE TABLE IF NOT EXISTS matchup_reports (
    id              BIGSERIAL PRIMARY KEY,
    game_format     TEXT NOT NULL,
    our_deck        TEXT NOT NULL,
    opp_deck        TEXT NOT NULL,
    report_type     TEXT NOT NULL,       -- playbook, decklist, overview, board_state
    data            JSONB NOT NULL,
    generated_at    DATE NOT NULL,
    is_current      BOOLEAN DEFAULT true,
    UNIQUE(game_format, our_deck, opp_deck, report_type, generated_at)
);
CREATE INDEX IF NOT EXISTS idx_reports_lookup ON matchup_reports
    (game_format, our_deck, opp_deck, report_type) WHERE is_current = true;
