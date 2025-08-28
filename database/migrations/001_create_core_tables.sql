-- Migration: Create core tables (companies, periods, line_item_definitions)
-- Version: 001
-- Description: Create the foundational tables for the financial data system
-- Author: System Migration
-- Date: 2025-01-28

-- Companies table
CREATE TABLE IF NOT EXISTS companies (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  industry TEXT,
  created_at TIMESTAMP DEFAULT NOW() NOT NULL,
  updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
  UNIQUE (name)
);

COMMENT ON TABLE companies IS 'Companies being analyzed';
COMMENT ON COLUMN companies.name IS 'Company name - must be unique';
COMMENT ON COLUMN companies.industry IS 'Industry classification';

-- Periods table for time-series data
CREATE TABLE IF NOT EXISTS periods (
  id SERIAL PRIMARY KEY,
  period_type TEXT NOT NULL,
  period_label TEXT NOT NULL,
  start_date DATE,
  end_date DATE,
  created_at TIMESTAMP DEFAULT NOW() NOT NULL,
  updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
  UNIQUE (period_label, period_type)
);

COMMENT ON TABLE periods IS 'Time periods for financial data (monthly, quarterly, yearly)';
COMMENT ON COLUMN periods.period_type IS 'Type of period: Monthly, Quarterly, Yearly';
COMMENT ON COLUMN periods.period_label IS 'Human-readable period label (e.g., 2025-Q1, 2025-01)';

-- Line item definitions for financial metrics
CREATE TABLE IF NOT EXISTS line_item_definitions (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  aliases TEXT[],
  description TEXT,
  UNIQUE (name)
);

COMMENT ON TABLE line_item_definitions IS 'Definitions of financial line items with aliases for mapping';
COMMENT ON COLUMN line_item_definitions.aliases IS 'Array of alternative names for this line item';

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name);
CREATE INDEX IF NOT EXISTS idx_periods_type_label ON periods(period_type, period_label);
CREATE INDEX IF NOT EXISTS idx_periods_dates ON periods(start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_line_items_name ON line_item_definitions(name);