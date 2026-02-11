-- Migration: Add normalization/mapping rejection capture
-- Version: 009
-- Description: Persist rejected candidate facts (with reasons) to avoid silent drop-on-floor
-- Author: Clawd
-- Date: 2026-01-25

CREATE TABLE IF NOT EXISTS fact_rejections (
    id SERIAL PRIMARY KEY,

    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,

    stage TEXT NOT NULL,               -- e.g. mapping | normalization | persistence
    reason TEXT NOT NULL,              -- stable code: missing_period | value_parse_failed | kpi_quality_too_small | ...

    context_key TEXT,

    line_item_text TEXT,
    scenario TEXT,
    value_text TEXT,
    value_numeric DECIMAL(18,4),
    currency TEXT,

    period_label_raw TEXT,
    period_label_canonical TEXT,
    period_type TEXT,

    source_file TEXT,
    source_page INTEGER,
    source_table INTEGER,
    source_row INTEGER,
    source_col TEXT,

    extraction_method TEXT,
    confidence REAL,

    details JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fact_rejections_company_created ON fact_rejections(company_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_fact_rejections_document ON fact_rejections(document_id);
CREATE INDEX IF NOT EXISTS idx_fact_rejections_reason ON fact_rejections(reason);

/*ROLLBACK_START
DROP INDEX IF EXISTS idx_fact_rejections_reason;
DROP INDEX IF EXISTS idx_fact_rejections_document;
DROP INDEX IF EXISTS idx_fact_rejections_company_created;
DROP TABLE IF EXISTS fact_rejections;
ROLLBACK_END*/
