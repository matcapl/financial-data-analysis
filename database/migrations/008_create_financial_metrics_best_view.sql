-- Migration: Create best-candidate view over financial_metrics
-- Version: 008
-- Description: Provide a stable, quality-filtered "best facts" view for observations/questions/reporting
-- Date: 2026-01-20

-- Select one best row per (company, period, line_item, value_type)
-- Preference order: highest confidence, then newest id.
-- Also filters out extremely likely KPI noise (years, tiny footnotes) for headline KPIs.

CREATE OR REPLACE VIEW financial_metrics_best AS
WITH ranked AS (
    SELECT
        fm.*,
        li.name AS line_item_name,
        ROW_NUMBER() OVER (
            PARTITION BY fm.company_id, fm.period_id, fm.line_item_id, fm.value_type
            ORDER BY COALESCE(fm.confidence, 0) DESC, fm.id DESC
        ) AS rn
    FROM financial_metrics fm
    JOIN line_item_definitions li ON fm.line_item_id = li.id
    WHERE NOT (
        li.name IN ('Revenue', 'Gross Profit', 'EBITDA')
        AND (
            ABS(fm.value) < 1000
            OR (ABS(fm.value) BETWEEN 1900 AND 2100)
        )
    )
)
SELECT *
FROM ranked
WHERE rn = 1;

-- ROLLBACK SQL
/*ROLLBACK_START
DROP VIEW IF EXISTS financial_metrics_best;
ROLLBACK_END*/
