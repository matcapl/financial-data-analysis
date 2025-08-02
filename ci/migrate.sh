#!/usr/bin/env bash
set -euo pipefail

echo "Applying financial schema..."
psql "$DATABASE_URL" -f schema/financial_schema.sql

echo "Applying question templates..."
psql "$DATABASE_URL" -f schema/question_templates.sql

echo "Migration complete."
