-- Migration: Create migrations tracking table
-- Version: 000
-- Description: Initialize database migration system
-- Author: System
-- Date: 2025-01-28

-- Create migrations tracking table
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(255) PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rollback_sql TEXT,
    checksum VARCHAR(64)
);

-- Insert this migration as the first one
INSERT INTO schema_migrations (version, description, checksum) 
VALUES ('000', 'Create migrations tracking table', 'init')
ON CONFLICT (version) DO NOTHING;

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_migrations_applied_at ON schema_migrations(applied_at);

COMMENT ON TABLE schema_migrations IS 'Tracks applied database migrations';
COMMENT ON COLUMN schema_migrations.version IS 'Migration version number (e.g., 001, 002, etc.)';
COMMENT ON COLUMN schema_migrations.description IS 'Human-readable description of the migration';
COMMENT ON COLUMN schema_migrations.applied_at IS 'Timestamp when migration was applied';
COMMENT ON COLUMN schema_migrations.rollback_sql IS 'SQL statements to rollback this migration';
COMMENT ON COLUMN schema_migrations.checksum IS 'Checksum to verify migration file integrity';