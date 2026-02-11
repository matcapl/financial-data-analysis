-- Migration: Backfill period_scope from existing context/text
-- Version: 013
-- Date: 2026-02-02

-- Best-effort backfill: mark rows as YTD when source metadata indicates it.

UPDATE financial_metrics
SET period_scope = 'YTD'
WHERE COALESCE(period_scope, 'Period') = 'Period'
  AND (
    COALESCE(context_key, '') ILIKE '%ytd%'
    OR COALESCE(source_col, '') ILIKE '%ytd%'
    OR COALESCE(notes, '') ILIKE '%ytd%'
  );

UPDATE extracted_facts_raw
SET period_scope = 'YTD'
WHERE COALESCE(period_scope, 'Period') = 'Period'
  AND (
    COALESCE(context_key, '') ILIKE '%ytd%'
    OR COALESCE(source_col, '') ILIKE '%ytd%'
  );

/*ROLLBACK_START
-- Conservative rollback: no-op (can't safely infer previous values)
ROLLBACK_END*/
