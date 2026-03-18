-- ════════════════════════════════════════════════════
-- DE Senior Template — PostgreSQL Schema Init
-- Runs automatically on first postgres container start
-- ════════════════════════════════════════════════════

-- Schemas
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS dw;
CREATE SCHEMA IF NOT EXISTS meta;
CREATE SCHEMA IF NOT EXISTS partman;

-- Extensions
CREATE EXTENSION IF NOT EXISTS pg_partman SCHEMA partman;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- ── meta.pipeline_runs ──────────────────────────────
CREATE TABLE IF NOT EXISTS meta.pipeline_runs (
    id              BIGSERIAL PRIMARY KEY,
    dag_id          TEXT NOT NULL,
    platform        TEXT,
    run_date        DATE NOT NULL DEFAULT CURRENT_DATE,
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    finished_at     TIMESTAMPTZ,
    status          TEXT CHECK (status IN ('running','success','failed','skipped')),
    rows_extracted  INT DEFAULT 0,
    rows_loaded     INT DEFAULT 0,
    minio_key       TEXT,
    error_message   TEXT,
    duration_secs   INT GENERATED ALWAYS AS (
        EXTRACT(EPOCH FROM (finished_at - started_at))::INT
    ) STORED
);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_date
    ON meta.pipeline_runs (run_date DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status
    ON meta.pipeline_runs (status, dag_id);

-- ── meta.data_quality_log ──────────────────────────
CREATE TABLE IF NOT EXISTS meta.data_quality_log (
    id          BIGSERIAL PRIMARY KEY,
    checked_at  TIMESTAMPTZ DEFAULT NOW(),
    table_name  TEXT NOT NULL,
    test_name   TEXT NOT NULL,
    status      TEXT CHECK (status IN ('pass', 'fail')),
    row_count   INT,
    details     TEXT
);

-- ── meta.schema_versions ───────────────────────────
CREATE TABLE IF NOT EXISTS meta.schema_versions (
    id          BIGSERIAL PRIMARY KEY,
    platform    TEXT NOT NULL,
    version     TEXT NOT NULL,
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    schema_hash TEXT,
    notes       TEXT
);

-- ── raw.facebook_ads ────────────────────────────────────
-- Staging buffer: TRUNCATE before every pipeline run (idempotent)
-- No PK — staging is always fresh, duplicates impossible
CREATE TABLE IF NOT EXISTS raw.facebook_ads (
    campaign_id     TEXT,
    campaign_name   TEXT,
    ad_set_id       TEXT,
    ad_set_name     TEXT,
    ad_id           TEXT,
    ad_name         TEXT,
    date            DATE,
    spend           NUMERIC(12, 4),   -- FB returns string, coerced to numeric
    impressions     INT,
    clicks          INT,
    leads           INT DEFAULT 0,    -- EC-05: may be 0 if no lead form
    loaded_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Comments
COMMENT ON SCHEMA raw  IS 'Staging buffer — TRUNCATE before each pipeline run';
COMMENT ON SCHEMA dw   IS 'Data Warehouse — fact/dim, partitioned monthly, UPSERT only';
COMMENT ON SCHEMA meta IS 'Observability — pipeline runs, quality checks, schema versions';
