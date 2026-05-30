-- =============================================================================
-- schema.sql — RxCheck interaction database schema
--
-- Dialect : PostgreSQL 15+
-- Changes from SQLite prototype:
--   • PRAGMA directives removed (PG handles concurrency natively)
--   • INTEGER PRIMARY KEY AUTOINCREMENT → BIGSERIAL
--   • TEXT COLLATE NOCASE → citext extension (case-insensitive text type)
--   • pg_trgm extension enabled for trigram-similarity drug search
--   • TEXT (JSON arrays) → JSONB for brand_names
--   • GIN indexes for trigram and JSONB columns
--   • etl_sync_state table for ETL fault-tolerance / checkpointing
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Extensions  (idempotent — safe to re-run)
-- ---------------------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- trigram similarity: word % 'token'
CREATE EXTENSION IF NOT EXISTS citext;    -- case-insensitive TEXT type


-- ---------------------------------------------------------------------------
-- drugs
-- Canonical drug registry.  generic_name is the unique lookup key (citext
-- gives us case-insensitive equality without a custom collation).
-- brand_names is stored as JSONB, e.g. '["Lasix","Frusemide"]'.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS drugs (
    id           BIGSERIAL    PRIMARY KEY,
    generic_name citext       NOT NULL UNIQUE,
    brand_names  JSONB        NOT NULL DEFAULT '[]'::jsonb
);

-- B-tree index on the citext column (implicit via UNIQUE, kept explicit for
-- documentation and to survive index-level changes).
CREATE INDEX IF NOT EXISTS idx_drugs_name
    ON drugs (generic_name);

-- GIN trigram index — enables fast  generic_name % 'query'  lookups used by
-- the high-precision similarity search in app.py::_resolve_drug_ids().
CREATE INDEX IF NOT EXISTS idx_drugs_name_trgm
    ON drugs USING GIN (generic_name gin_trgm_ops);

-- GIN index on brand_names JSONB for future jsonb_path_ops queries
CREATE INDEX IF NOT EXISTS idx_drugs_brands
    ON drugs USING GIN (brand_names jsonb_path_ops);


-- ---------------------------------------------------------------------------
-- interactions
-- Canonical interaction record.  drug_a_id < drug_b_id ALWAYS (enforced by
-- etl.py and app.py) so every pair has exactly one row regardless of order.
--
-- severity   : 'high' | 'medium' | 'low'  (mirrors the old INTERACTION_RULES)
-- description: human-readable clinical consequence
-- action_text: clinical recommendation
-- source     : provenance string, e.g. 'openFDA SPL' or 'RxCheck seed data'
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS interactions (
    drug_a_id    BIGINT       NOT NULL REFERENCES drugs (id) ON DELETE CASCADE,
    drug_b_id    BIGINT       NOT NULL REFERENCES drugs (id) ON DELETE CASCADE,
    severity     TEXT         NOT NULL CHECK (severity IN ('high', 'medium', 'low')),
    description  TEXT         NOT NULL DEFAULT '',
    action_text  TEXT         NOT NULL DEFAULT '',
    source       TEXT         NOT NULL DEFAULT 'openFDA SPL',

    PRIMARY KEY (drug_a_id, drug_b_id),

    -- Prevent accidental self-interactions
    CONSTRAINT chk_no_self_interaction CHECK (drug_a_id < drug_b_id)
);

-- The composite PK covers the primary lookup pattern, but an explicit named
-- index makes the query plan transparent and survives PK refactoring.
CREATE INDEX IF NOT EXISTS idx_interactions_lookup
    ON interactions (drug_a_id, drug_b_id);

-- Secondary indexes for "find all interactions involving drug X"
CREATE INDEX IF NOT EXISTS idx_interactions_drug_a
    ON interactions (drug_a_id);

CREATE INDEX IF NOT EXISTS idx_interactions_drug_b
    ON interactions (drug_b_id);


-- ---------------------------------------------------------------------------
-- etl_sync_state
-- Single-row checkpoint table for ETL fault-tolerance.
-- The ETL pipeline reads last_successful_skip before each run and resumes
-- from that offset.  It writes back only after a full batch has been
-- committed, so a crash between writes leaves the state at the last safe
-- position and the next run replays at most one batch.
--
-- Invariant: this table always has exactly one row (id = 1).  The row is
-- inserted by the ETL script on first run.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS etl_sync_state (
    id                   INT          PRIMARY KEY DEFAULT 1
                                      CHECK (id = 1),       -- enforces singleton
    last_successful_skip INT          NOT NULL DEFAULT 0,
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
