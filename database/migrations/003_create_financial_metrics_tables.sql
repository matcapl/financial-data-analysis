-- Migration: Create financial metrics and derived metrics tables
-- Version: 003
-- Description: Create tables for storing financial metrics and calculated derived metrics
-- Author: System Migration 
-- Date: 2025-01-28

-- Financial metrics table (raw data from uploaded files)
CREATE TABLE IF NOT EXISTS financial_metrics (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    period_id INTEGER NOT NULL REFERENCES periods(id) ON DELETE CASCADE,
    line_item_id INTEGER NOT NULL REFERENCES line_item_definitions(id) ON DELETE CASCADE,
    value DECIMAL(15,2),
    value_type TEXT,              -- ✅ ADDED: Type of value (actual, budget, forecast)
    frequency TEXT,               -- ✅ ADDED: Data frequency (monthly, quarterly, annual)
    currency TEXT,                -- ✅ ADDED: Currency code (USD, GBP, EUR)
    source_file TEXT,
    source_sheet TEXT,
    source_row INTEGER,
    source_page INTEGER,
    source_type TEXT,             -- ✅ ADDED: Type of source (pdf, excel, csv)
    notes TEXT,                   -- ✅ ADDED: Additional notes/metadata
    hash TEXT,                    -- ✅ ADDED: Hash for deduplication
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    UNIQUE (company_id, period_id, line_item_id, value_type, source_file)
);

-- Add missing columns if they don't exist (for existing installations)
DO $$ 
BEGIN
    -- Existing columns
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'financial_metrics' AND column_name = 'source_sheet') THEN
        ALTER TABLE financial_metrics ADD COLUMN source_sheet TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'financial_metrics' AND column_name = 'source_row') THEN
        ALTER TABLE financial_metrics ADD COLUMN source_row INTEGER;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'financial_metrics' AND column_name = 'source_page') THEN
        ALTER TABLE financial_metrics ADD COLUMN source_page INTEGER;
    END IF;
    
    -- ✅ MISSING COLUMNS FROM PERSISTENCE LAYER
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'financial_metrics' AND column_name = 'value_type') THEN
        ALTER TABLE financial_metrics ADD COLUMN value_type TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'financial_metrics' AND column_name = 'frequency') THEN
        ALTER TABLE financial_metrics ADD COLUMN frequency TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'financial_metrics' AND column_name = 'currency') THEN
        ALTER TABLE financial_metrics ADD COLUMN currency TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'financial_metrics' AND column_name = 'source_type') THEN
        ALTER TABLE financial_metrics ADD COLUMN source_type TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'financial_metrics' AND column_name = 'notes') THEN
        ALTER TABLE financial_metrics ADD COLUMN notes TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'financial_metrics' AND column_name = 'hash') THEN
        ALTER TABLE financial_metrics ADD COLUMN hash TEXT;
    END IF;
END $$;

COMMENT ON TABLE financial_metrics IS 'Raw financial data extracted from uploaded files';
COMMENT ON COLUMN financial_metrics.value IS 'The financial value/amount';
COMMENT ON COLUMN financial_metrics.value_type IS 'Type of value: actual, budget, forecast, variance';
COMMENT ON COLUMN financial_metrics.frequency IS 'Reporting frequency: monthly, quarterly, annual';
COMMENT ON COLUMN financial_metrics.currency IS 'Currency code (ISO 4217): USD, GBP, EUR, etc.';
COMMENT ON COLUMN financial_metrics.source_file IS 'Original filename where this data was extracted';
COMMENT ON COLUMN financial_metrics.source_sheet IS 'Excel sheet name or page identifier';
COMMENT ON COLUMN financial_metrics.source_row IS 'Row number in source file';
COMMENT ON COLUMN financial_metrics.source_page IS 'Page number for PDF sources';
COMMENT ON COLUMN financial_metrics.source_type IS 'Type of source file: pdf, excel, csv';
COMMENT ON COLUMN financial_metrics.notes IS 'Additional metadata or processing notes';
COMMENT ON COLUMN financial_metrics.hash IS 'Hash for deduplication and data integrity';

-- Derived metrics table (calculated values) - handle existing structure
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'derived_metrics') THEN
        -- Create new table if it doesn't exist
        CREATE TABLE derived_metrics (
            id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            period_id INTEGER NOT NULL REFERENCES periods(id) ON DELETE CASCADE,
            metric_name TEXT NOT NULL,
            metric_value DECIMAL(15,4),
            calculation_method TEXT,
            dependencies TEXT[],
            created_at TIMESTAMP DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
            UNIQUE (company_id, period_id, metric_name)
        );
    ELSE
        -- Add new columns to existing table if needed
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'derived_metrics' AND column_name = 'metric_name') THEN
            ALTER TABLE derived_metrics ADD COLUMN metric_name TEXT;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'derived_metrics' AND column_name = 'metric_value') THEN
            ALTER TABLE derived_metrics ADD COLUMN metric_value DECIMAL(15,4);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'derived_metrics' AND column_name = 'calculation_method') THEN
            ALTER TABLE derived_metrics ADD COLUMN calculation_method TEXT;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'derived_metrics' AND column_name = 'dependencies') THEN
            ALTER TABLE derived_metrics ADD COLUMN dependencies TEXT[];
        END IF;
    END IF;
END $$;

COMMENT ON TABLE derived_metrics IS 'Calculated financial metrics derived from raw data';
COMMENT ON COLUMN derived_metrics.metric_name IS 'Name of the calculated metric (e.g., ROI, Profit Margin)';
COMMENT ON COLUMN derived_metrics.calculation_method IS 'Formula or method used to calculate this metric';
COMMENT ON COLUMN derived_metrics.dependencies IS 'Array of line items this calculation depends on';

-- Create performance indexes
CREATE INDEX IF NOT EXISTS idx_financial_metrics_company_period ON financial_metrics(company_id, period_id);
CREATE INDEX IF NOT EXISTS idx_financial_metrics_line_item ON financial_metrics(line_item_id);
CREATE INDEX IF NOT EXISTS idx_financial_metrics_source ON financial_metrics(source_file);
CREATE INDEX IF NOT EXISTS idx_financial_metrics_value_type ON financial_metrics(value_type);
CREATE INDEX IF NOT EXISTS idx_financial_metrics_currency ON financial_metrics(currency);
CREATE INDEX IF NOT EXISTS idx_derived_metrics_company_period ON derived_metrics(company_id, period_id);
CREATE INDEX IF NOT EXISTS idx_derived_metrics_name ON derived_metrics(metric_name);

-- ROLLBACK SQL (automatically extracted by migration system)
/*ROLLBACK_START
-- Drop indexes first
DROP INDEX IF EXISTS idx_financial_metrics_company_period;
DROP INDEX IF EXISTS idx_financial_metrics_line_item;
DROP INDEX IF EXISTS idx_financial_metrics_source;
DROP INDEX IF EXISTS idx_financial_metrics_value_type;
DROP INDEX IF EXISTS idx_financial_metrics_currency;
DROP INDEX IF EXISTS idx_derived_metrics_company_period;
DROP INDEX IF EXISTS idx_derived_metrics_name;

-- Drop tables (derived_metrics first due to potential references)
DROP TABLE IF EXISTS derived_metrics;
DROP TABLE IF EXISTS financial_metrics;
ROLLBACK_END*/