-- Migration: Add Companies House number to companies
-- Version: 010
-- Description: Add optional Companies House number (UK) for stable company identity
-- Author: Clawd
-- Date: 2026-01-25

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'companies'
          AND column_name = 'companies_house_number'
    ) THEN
        ALTER TABLE companies ADD COLUMN companies_house_number TEXT;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS idx_companies_house_number_unique
ON companies(companies_house_number)
WHERE companies_house_number IS NOT NULL;

/*ROLLBACK_START
DROP INDEX IF EXISTS idx_companies_house_number_unique;
ALTER TABLE companies DROP COLUMN IF EXISTS companies_house_number;
ROLLBACK_END*/
