#!/usr/bin/env bash
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL must be set}"

echo "02 | Resetting schema (applying base SQL files)..."
psql "$DATABASE_URL" <<'SQL'
-- Core financial schema
\i schema/001_financial_schema.sql

-- Question templates schema
\i schema/002_question_templates.sql
SQL
echo "02 | Schema reset complete."
