-- Migration: Filter Revenue YTD candidates that fail reconciliation
-- Version: 014
-- Date: 2026-02-03

-- Goal:
-- - Prevent mismatched Revenue YTD facts from being promoted/used as corroboration.
-- - Keep Period-scoped monthly Revenue unaffected.
--
-- Approach:
-- 1) Select best Period Revenue (Monthly, Actual) per month.
-- 2) Compute derived YTD as cumulative sum per calendar year.
-- 3) Filter Revenue YTD candidates in the best view when derived vs ingested mismatch exceeds tolerances.

DROP VIEW IF EXISTS financial_metrics_best;

CREATE VIEW financial_metrics_best AS
WITH base AS (
    SELECT
        fm.*,
        li.name AS line_item_name,
        p.period_type,
        p.period_label,
        COALESCE(fm.period_scope, 'Period') AS period_scope_n
    FROM financial_metrics fm
    JOIN line_item_definitions li ON fm.line_item_id = li.id
    JOIN periods p ON p.id = fm.period_id
),
medians AS (
    SELECT
        company_id,
        line_item_id,
        value_type,
        period_scope_n,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY value) AS median_value
    FROM base
    WHERE period_type = 'Monthly'
      AND value IS NOT NULL
    GROUP BY company_id, line_item_id, value_type, period_scope_n
),
median_filtered AS (
    SELECT b.*
    FROM base b
    LEFT JOIN medians m
      ON m.company_id = b.company_id
     AND m.line_item_id = b.line_item_id
     AND m.value_type = b.value_type
     AND m.period_scope_n = b.period_scope_n
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
            PARTITION BY f.company_id, f.period_id, f.line_item_id, f.value_type, f.period_scope_n
            ORDER BY COALESCE(f.confidence, 0) DESC, f.id DESC
        ) AS rn
    FROM median_filtered f
),
best_candidates AS (
    SELECT *
    FROM ranked
    WHERE rn = 1
),
-- Best Period Revenue (Monthly, Actual)
best_period_revenue AS (
    SELECT
        bc.company_id,
        bc.period_label,
        bc.value AS revenue_period_value,
        SUBSTRING(bc.period_label, 1, 4)::int AS year
    FROM best_candidates bc
    WHERE bc.line_item_name = 'Revenue'
      AND bc.value_type = 'Actual'
      AND bc.period_type = 'Monthly'
      AND bc.period_scope_n = 'Period'
),
period_revenue_with_ytd AS (
    SELECT
        pr.company_id,
        pr.period_label,
        pr.year,
        SUM(pr.revenue_period_value) OVER (
            PARTITION BY pr.company_id, pr.year
            ORDER BY pr.period_label
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS derived_ytd
    FROM best_period_revenue pr
),
-- Identify mismatched YTD months
mismatched_revenue_ytd AS (
    SELECT
        bc.company_id,
        bc.period_id,
        bc.id AS financial_metrics_id,
        bc.period_label,
        bc.value AS ingested_ytd,
        pry.derived_ytd,
        (pry.derived_ytd - bc.value) AS diff,
        CASE WHEN bc.value = 0 THEN NULL ELSE ((pry.derived_ytd - bc.value) / bc.value) * 100 END AS diff_pct
    FROM best_candidates bc
    JOIN period_revenue_with_ytd pry
      ON pry.company_id = bc.company_id
     AND pry.period_label = bc.period_label
    WHERE bc.line_item_name = 'Revenue'
      AND bc.value_type = 'Actual'
      AND bc.period_type = 'Monthly'
      AND bc.period_scope_n = 'YTD'
      AND (
        ABS(pry.derived_ytd - bc.value) > 1000
        AND (bc.value <> 0)
        AND (ABS(((pry.derived_ytd - bc.value) / bc.value) * 100) > 2.0)
      )
)
SELECT bc.*
FROM best_candidates bc
LEFT JOIN mismatched_revenue_ytd bad
  ON bad.financial_metrics_id = bc.id
WHERE bad.financial_metrics_id IS NULL;

/*ROLLBACK_START
-- Conservative rollback: recreate the prior view definition from migration 012.
DROP VIEW IF EXISTS financial_metrics_best;
ROLLBACK_END*/
