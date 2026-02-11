-- Migration: Add period_scope to support Monthly vs YTD disambiguation
-- Version: 012
-- Date: 2026-01-31

-- 1) Add period_scope columns
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'financial_metrics' AND column_name = 'period_scope'
    ) THEN
        ALTER TABLE financial_metrics ADD COLUMN period_scope TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'extracted_facts_raw' AND column_name = 'period_scope'
    ) THEN
        ALTER TABLE extracted_facts_raw ADD COLUMN period_scope TEXT;
    END IF;
END $$;

-- 2) Backfill existing rows to a safe default
UPDATE financial_metrics SET period_scope = COALESCE(period_scope, 'Period');
UPDATE extracted_facts_raw SET period_scope = COALESCE(period_scope, 'Period');

-- 3) Update uniqueness to avoid Monthly-vs-YTD collision within the same source
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'financial_metrics_company_id_period_id_line_item_id_value_type_source_file_key'
    ) THEN
        ALTER TABLE financial_metrics
        DROP CONSTRAINT financial_metrics_company_id_period_id_line_item_id_value_type_source_file_key;
    END IF;
END $$;

ALTER TABLE financial_metrics
    ADD CONSTRAINT financial_metrics_unique_fact_key
    UNIQUE (company_id, period_id, line_item_id, value_type, period_scope, source_file);

-- 4) Recreate best view to partition by period_scope as well
DROP VIEW IF EXISTS financial_metrics_best;

CREATE VIEW financial_metrics_best AS
WITH base AS (
    SELECT
        fm.*,
        li.name AS line_item_name,
        p.period_type
    FROM financial_metrics fm
    JOIN line_item_definitions li ON fm.line_item_id = li.id
    JOIN periods p ON p.id = fm.period_id
),
medians AS (
    SELECT
        company_id,
        line_item_id,
        value_type,
        period_scope,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY value) AS median_value
    FROM base
    WHERE period_type = 'Monthly'
      AND value IS NOT NULL
    GROUP BY company_id, line_item_id, value_type, period_scope
),
filtered AS (
    SELECT b.*
    FROM base b
    LEFT JOIN medians m
      ON m.company_id = b.company_id
     AND m.line_item_id = b.line_item_id
     AND m.value_type = b.value_type
     AND m.period_scope = COALESCE(b.period_scope, 'Period')
    WHERE NOT (
        b.line_item_name IN ('Revenue', 'Gross Profit', 'EBITDA')
        AND (
            ABS(b.value) < 1000
            OR (ABS(b.value) BETWEEN 1900 AND 2100)
        )
    )
      AND (
        m.median_value IS NULL
        OR m.median_value = 0
        OR (
            ABS(b.value) >= ABS(m.median_value) * 0.1
            AND ABS(b.value) <= ABS(m.median_value) * 10
        )
      )
),
ranked AS (
    SELECT
        f.*,
        ROW_NUMBER() OVER (
            PARTITION BY f.company_id, f.period_id, f.line_item_id, f.value_type, COALESCE(f.period_scope, 'Period')
            ORDER BY COALESCE(f.confidence, 0) DESC, f.id DESC
        ) AS rn
    FROM filtered f
)
SELECT *
FROM ranked
WHERE rn = 1;

/*ROLLBACK_START
ALTER TABLE financial_metrics DROP CONSTRAINT IF EXISTS financial_metrics_unique_fact_key;
-- Old constraint may not be recreatable automatically; prefer restoring from migration 003.
ALTER TABLE financial_metrics DROP COLUMN IF EXISTS period_scope;
ALTER TABLE extracted_facts_raw DROP COLUMN IF EXISTS period_scope;
DROP VIEW IF EXISTS financial_metrics_best;
ROLLBACK_END*/
