-- Migration: Seed initial data
-- Version: 002  
-- Description: Insert minimal essential data for system operation
-- Author: System Migration
-- Date: 2025-01-28

-- Generate time periods (last 20 years) - Essential for system operation
WITH
  today AS (
    SELECT date_trunc('month', now())::date AS current_month
  ),
  boundaries AS (
    SELECT
      (current_month - INTERVAL '20 years')::date AS start_month,
      current_month AS end_month
    FROM today
  ),
  monthly AS (
    SELECT
      to_char(m, 'YYYY-MM') AS period_label,
      'Monthly' AS period_type,
      m AS start_date,
      (m + INTERVAL '1 month' - INTERVAL '1 day')::date AS end_date
    FROM boundaries,
    generate_series(boundaries.start_month,
                    boundaries.end_month,
                    INTERVAL '1 month') AS m
  ),
  quarterly AS (
    SELECT
      to_char(q, 'YYYY') || '-Q' || to_char(q, 'Q') AS period_label,
      'Quarterly' AS period_type,
      q AS start_date,
      (q + INTERVAL '3 months' - INTERVAL '1 day')::date AS end_date
    FROM boundaries,
    generate_series(boundaries.start_month,
                    boundaries.end_month,
                    INTERVAL '3 months') AS q
  ),
  yearly AS (
    SELECT
      to_char(y, 'YYYY') AS period_label,
      'Yearly' AS period_type,
      y AS start_date,
      (y + INTERVAL '1 year' - INTERVAL '1 day')::date AS end_date
    FROM boundaries,
    generate_series(date_trunc('year', boundaries.start_month),
                    date_trunc('year', boundaries.end_month),
                    INTERVAL '1 year') AS y
  ),
  all_periods AS (
    SELECT * FROM monthly
    UNION
    SELECT * FROM quarterly
    UNION
    SELECT * FROM yearly
  )
INSERT INTO periods (period_label, period_type, start_date, end_date, created_at, updated_at)
SELECT period_label, period_type, start_date, end_date, now(), now()
FROM all_periods
ON CONFLICT (period_label, period_type) DO NOTHING;

-- Insert only essential line item definitions required for basic system operation
INSERT INTO line_item_definitions (name, aliases, description) VALUES
  ('Revenue', '{sales,income,turnover,total_revenue,rev}'::TEXT[], 'Total revenue from operations'),
  ('Gross Profit', '{gross_profit,grossincome,"gross income"}'::TEXT[], 'Revenue minus cost of goods sold'),
  ('EBITDA', '{earnings_before_interest,earnings_before_taxes,earnings_before_interest_taxes,operating_profit}'::TEXT[], 'Earnings before interest, taxes, depreciation, amortization')
ON CONFLICT (name) DO NOTHING;

-- ROLLBACK SQL (automatically extracted by migration system)
/*ROLLBACK_START
-- Delete essential seeded data (in reverse order)
DELETE FROM line_item_definitions WHERE name IN (
  'Revenue', 'Gross Profit', 'EBITDA'
);

-- Delete generated periods (careful: this will remove ALL generated periods)
-- Note: This is a destructive rollback - only run if you're sure
DELETE FROM periods WHERE period_type IN ('Monthly', 'Quarterly', 'Yearly');
ROLLBACK_END*/