-- Migration: Add user preferences table
-- Version: 005
-- Description: Add user preferences table
-- Author: Developer
-- Date: 2025-08-28

-- Migration Up (Apply changes)
CREATE TABLE IF NOT EXISTS user_preferences (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL,
  preference_key TEXT NOT NULL,
  preference_value JSONB,
  created_at TIMESTAMP DEFAULT NOW() NOT NULL,
  updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
  UNIQUE (user_id, preference_key)
);

COMMENT ON TABLE user_preferences IS 'User-specific preference settings';
COMMENT ON COLUMN user_preferences.preference_value IS 'JSON value for flexible preference storage';

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id ON user_preferences(user_id);

-- Migration Down (Rollback changes - update schema_migrations.rollback_sql manually if needed)
-- This migration does not support automatic rollback
