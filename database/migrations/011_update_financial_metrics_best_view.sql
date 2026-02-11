-- Migration: Improve financial_metrics_best with scale-outlier filtering
-- Version: 011
-- Description: Filter obvious scale-mismatched candidates using per-company median bands
-- Date: 2026-01-31

-- This keeps the best-view robust across companies without hardcoding business-specific scales.
--
-- IMPORTANT: `CREATE OR REPLACE VIEW` cannot change a view's column list.
-- We drop and recreate to keep a stable, backward-compatible shape:
--   financial_metrics columns + `line_item_name` + `rn`
--
-- Strategy:
-- - compute median per (company, line_item, value_type) for Monthly data
-- - filter rows outside [median*0.1, median*10] when median is available
-- - keep existing tiny-year/footnote filters

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
        percentile_cont(0.5) WITHIN GROUP (ORDER BY value) AS median_value
    FROM base
    WHERE period_type = 'Monthly'
      AND value IS NOT NULL
    GROUP BY company_id, line_item_id, value_type
),
filtered AS (
    SELECT b.*
    FROM base b
    LEFT JOIN medians m
      ON m.company_id = b.company_id
     AND m.line_item_id = b.line_item_id
     AND m.value_type = b.value_type
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
            PARTITION BY f.company_id, f.period_id, f.line_item_id, f.value_type
            ORDER BY COALESCE(f.confidence, 0) DESC, f.id DESC
        ) AS rn
    FROM filtered f
)
SELECT *
FROM ranked
WHERE rn = 1;

/*ROLLBACK_START
-- Restore view by dropping it (previous migration 008 can recreate if needed).
DROP VIEW IF EXISTS financial_metrics_best;
ROLLBACK_END*/
