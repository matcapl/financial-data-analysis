-- Migration: Add context_key to raw facts and canonical metrics
-- Version: 007
-- Description: Add deterministic statement/table context to avoid coordinate collisions across sections
-- Author: Clawd
-- Date: 2026-01-13

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'extracted_facts_raw' AND column_name = 'context_key') THEN
        ALTER TABLE extracted_facts_raw ADD COLUMN context_key TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'financial_metrics' AND column_name = 'context_key') THEN
        ALTER TABLE financial_metrics ADD COLUMN context_key TEXT;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_raw_facts_context ON extracted_facts_raw(context_key);
CREATE INDEX IF NOT EXISTS idx_financial_metrics_context ON financial_metrics(context_key);

/*ROLLBACK_START
DROP INDEX IF EXISTS idx_financial_metrics_context;
DROP INDEX IF EXISTS idx_raw_facts_context;
ALTER TABLE financial_metrics DROP COLUMN IF EXISTS context_key;
ALTER TABLE extracted_facts_raw DROP COLUMN IF EXISTS context_key;
ROLLBACK_END*/
