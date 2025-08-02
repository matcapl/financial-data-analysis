-- Migration: financial_schema.sql
-- This file can be run multiple times safely

-- Create companies table
CREATE TABLE IF NOT EXISTS companies (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  industry TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Add unique constraint if missing
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'companies_name_key') THEN
        ALTER TABLE companies ADD CONSTRAINT companies_name_key UNIQUE (name);
    END IF;
END $$;

-- Seed companies (idempotent)
INSERT INTO companies (id, name, industry)
VALUES (1, 'Wilson Group', 'Technology')
ON CONFLICT (name) DO UPDATE SET
    industry = EXCLUDED.industry,
    updated_at = NOW();

-- Reset sequence
SELECT setval(pg_get_serial_sequence('companies', 'id'), GREATEST(1, (SELECT COALESCE(MAX(id), 0) FROM companies)));

-- Create periods table
CREATE TABLE IF NOT EXISTS periods (
  id SERIAL PRIMARY KEY,
  period_type TEXT NOT NULL,
  period_label TEXT NOT NULL,
  start_date DATE,
  end_date DATE,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create line_item_definitions table
CREATE TABLE IF NOT EXISTS line_item_definitions (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  statement_type TEXT,
  category TEXT,
  default_weight NUMERIC(5,2),
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Add unique constraint if missing, with cleanup
DO $$ 
BEGIN
    -- Clean up duplicates first
    DELETE FROM line_item_definitions d
    USING (
      SELECT name, MIN(id) AS keep_id
      FROM line_item_definitions
      GROUP BY name
      HAVING COUNT(*) > 1
    ) dupes
    WHERE d.name = dupes.name AND d.id <> dupes.keep_id;
    
    -- Add constraint if missing
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'line_item_definitions_name_key') THEN
        ALTER TABLE line_item_definitions ADD CONSTRAINT line_item_definitions_name_key UNIQUE (name);
    END IF;
END $$;

-- Seed line_item_definitions (idempotent)
INSERT INTO line_item_definitions (name, statement_type, category, default_weight)
VALUES
  ('Revenue',      'Income Statement', 'Revenue',       1.00),
  ('Gross Profit', 'Income Statement', 'Profitability', 0.80),
  ('EBITDA',       'Income Statement', 'Profitability', 0.90)
ON CONFLICT (name) DO UPDATE SET
    statement_type = EXCLUDED.statement_type,
    category = EXCLUDED.category,
    default_weight = EXCLUDED.default_weight,
    updated_at = NOW();

-- Create financial_metrics table
CREATE TABLE IF NOT EXISTS financial_metrics (
  id SERIAL PRIMARY KEY,
  company_id INT NOT NULL REFERENCES companies(id),
  period_id INT NOT NULL REFERENCES periods(id),
  line_item_id INT NOT NULL REFERENCES line_item_definitions(id),
  value_type TEXT,
  frequency TEXT,
  value NUMERIC,
  currency TEXT,
  source_file TEXT,
  source_page INT,
  source_type TEXT,
  notes TEXT,
  corroboration_status TEXT,
  hash TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Add unique constraint on hash if missing
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'financial_metrics_hash_key') THEN
        ALTER TABLE financial_metrics ADD CONSTRAINT financial_metrics_hash_key UNIQUE (hash);
    END IF;
END $$;

-- Create indexes for financial_metrics
CREATE INDEX IF NOT EXISTS idx_financial_metrics_company_period
  ON financial_metrics(company_id, period_id);
CREATE INDEX IF NOT EXISTS idx_financial_metrics_line_item
  ON financial_metrics(line_item_id);
CREATE INDEX IF NOT EXISTS idx_financial_metrics_hash
  ON financial_metrics(hash);

-- Create derived_metrics table
CREATE TABLE IF NOT EXISTS derived_metrics (
  id SERIAL PRIMARY KEY,
  base_metric_id INT NOT NULL REFERENCES financial_metrics(id),
  calculation_type TEXT,
  frequency TEXT,
  company_id INT NOT NULL REFERENCES companies(id),
  period_id INT NOT NULL REFERENCES periods(id),
  calculated_value NUMERIC,
  unit TEXT,
  source_ids TEXT,
  calculation_note TEXT,
  corroboration_status TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create indexes for derived_metrics
CREATE INDEX IF NOT EXISTS idx_derived_metrics_base
  ON derived_metrics(base_metric_id);
CREATE INDEX IF NOT EXISTS idx_derived_metrics_company_period
  ON derived_metrics(company_id, period_id);

-- Create question_templates table
CREATE TABLE IF NOT EXISTS question_templates (
  id SERIAL PRIMARY KEY,
  metric TEXT NOT NULL,
  calculation_type TEXT NOT NULL,
  base_question TEXT NOT NULL,
  trigger_threshold NUMERIC NOT NULL,
  trigger_operator TEXT CHECK (trigger_operator IN ('>', '<', '>=', '<=', '=')),
  default_weight NUMERIC(5,2) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Seed basic question_templates (idempotent)
INSERT INTO question_templates (metric, calculation_type, base_question, trigger_threshold, trigger_operator, default_weight)
VALUES
  ('Revenue',      'MoM Growth', 'Revenue increased by {change}% month-over-month. What factors contributed to this growth?',      2.0, '>=', 3.00),
  ('Revenue',      'MoM Growth', 'Revenue decreased by {change}% month-over-month. What caused this decline?',                    -2.0, '<=', 4.00),
  ('Gross Profit', 'MoM Growth', 'Gross profit rose by {change}% month-over-month. What operational improvements contributed?',   2.0, '>=', 3.00),
  ('Gross Profit', 'MoM Growth', 'Gross profit dropped by {change}% month-over-month. What cost pressures emerged?',             -2.0, '<=', 4.00),
  ('EBITDA',       'MoM Growth', 'EBITDA increased by {change}% month-over-month. What operational efficiencies were achieved?',  2.0, '>=', 4.00),
  ('EBITDA',       'MoM Growth', 'EBITDA decreased by {change}% month-over-month. What cost controls are needed?',               -2.0, '<=', 5.00)
ON CONFLICT DO NOTHING;

-- Create live_questions table
CREATE TABLE IF NOT EXISTS live_questions (
  id SERIAL PRIMARY KEY,
  derived_metric_id INT NOT NULL REFERENCES derived_metrics(id),
  template_id INT NOT NULL REFERENCES question_templates(id),
  question_text TEXT,
  category TEXT,
  composite_score NUMERIC,
  scorecard TEXT,
  status TEXT,
  owner TEXT,
  deadline DATE,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create indexes for live_questions
CREATE INDEX IF NOT EXISTS idx_live_questions_status
  ON live_questions(status);
CREATE INDEX IF NOT EXISTS idx_live_questions_score
  ON live_questions(composite_score);

-- Create question_logs table
CREATE TABLE IF NOT EXISTS question_logs (
  id SERIAL PRIMARY KEY,
  live_question_id INT NOT NULL REFERENCES live_questions(id),
  change_type TEXT,
  changed_by TEXT,
  old_value TEXT,
  new_value TEXT,
  change_note TEXT,
  changed_on TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create generated_reports table
CREATE TABLE IF NOT EXISTS generated_reports (
  id SERIAL PRIMARY KEY,
  generated_on TIMESTAMP NOT NULL DEFAULT NOW(),
  filter_type TEXT,
  parameters JSONB,
  output_summary TEXT,
  report_file_path TEXT,
  company_id INT NOT NULL REFERENCES companies(id),
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
