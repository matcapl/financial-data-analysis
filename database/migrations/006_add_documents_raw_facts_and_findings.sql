-- Migration: Add documents, raw extracted facts, and reconciliation findings
-- Version: 006
-- Description: Introduce first-class provenance and findings for board-pack reconciliation
-- Author: Clawd
-- Date: 2026-01-13

-- Documents table: one row per uploaded source file
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    original_filename TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    uploaded_at TIMESTAMP DEFAULT NOW() NOT NULL,
    file_hash TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_documents_company_uploaded ON documents(company_id, uploaded_at DESC);

-- Raw extracted facts: preserves what was extracted + coordinates before normalization/mapping decisions
CREATE TABLE IF NOT EXISTS extracted_facts_raw (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,

    line_item_text TEXT,
    scenario TEXT,
    value_text TEXT,
    value_numeric DECIMAL(18,4),
    currency TEXT,

    period_label TEXT,
    period_type TEXT,

    source_page INTEGER,
    source_table INTEGER,
    source_row INTEGER,
    source_col TEXT,

    extraction_method TEXT,
    confidence REAL,

    created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_raw_facts_doc ON extracted_facts_raw(document_id);
CREATE INDEX IF NOT EXISTS idx_raw_facts_company_period ON extracted_facts_raw(company_id, period_label);
CREATE INDEX IF NOT EXISTS idx_raw_facts_line_item ON extracted_facts_raw(line_item_text);

-- Reconciliation findings: deterministic checks over canonical facts (and links back to evidence)
CREATE TABLE IF NOT EXISTS reconciliation_findings (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,

    finding_type TEXT NOT NULL,
    severity TEXT NOT NULL,

    metric_name TEXT,
    scenario TEXT,
    period_id INTEGER REFERENCES periods(id) ON DELETE SET NULL,

    message TEXT NOT NULL,
    evidence JSONB DEFAULT '{}'::jsonb,

    created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_findings_company_created ON reconciliation_findings(company_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_findings_doc ON reconciliation_findings(document_id);

-- Extend canonical facts (financial_metrics) with provenance hooks back to documents and coordinates
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'financial_metrics' AND column_name = 'document_id') THEN
        ALTER TABLE financial_metrics ADD COLUMN document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'financial_metrics' AND column_name = 'source_table') THEN
        ALTER TABLE financial_metrics ADD COLUMN source_table INTEGER;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'financial_metrics' AND column_name = 'source_col') THEN
        ALTER TABLE financial_metrics ADD COLUMN source_col TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'financial_metrics' AND column_name = 'extraction_method') THEN
        ALTER TABLE financial_metrics ADD COLUMN extraction_method TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'financial_metrics' AND column_name = 'confidence') THEN
        ALTER TABLE financial_metrics ADD COLUMN confidence REAL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_financial_metrics_document ON financial_metrics(document_id);

-- ROLLBACK SQL
/*ROLLBACK_START
DROP INDEX IF EXISTS idx_financial_metrics_document;
ALTER TABLE financial_metrics DROP COLUMN IF EXISTS confidence;
ALTER TABLE financial_metrics DROP COLUMN IF EXISTS extraction_method;
ALTER TABLE financial_metrics DROP COLUMN IF EXISTS source_col;
ALTER TABLE financial_metrics DROP COLUMN IF EXISTS source_table;
ALTER TABLE financial_metrics DROP COLUMN IF EXISTS document_id;

DROP INDEX IF EXISTS idx_findings_doc;
DROP INDEX IF EXISTS idx_findings_company_created;
DROP TABLE IF EXISTS reconciliation_findings;

DROP INDEX IF EXISTS idx_raw_facts_line_item;
DROP INDEX IF EXISTS idx_raw_facts_company_period;
DROP INDEX IF EXISTS idx_raw_facts_doc;
DROP TABLE IF EXISTS extracted_facts_raw;

DROP INDEX IF EXISTS idx_documents_company_uploaded;
DROP TABLE IF EXISTS documents;
ROLLBACK_END*/
