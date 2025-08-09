#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${ENV_FILE:-.env}"
if [ -f "$ENV_FILE" ]; then
  set -a
  source "$ENV_FILE"
  set +a
fi
: "${DATABASE_URL:?DATABASE_URL must be set}"

echo "02 | Resetting schema (applying base SQL files)..."
psql "$DATABASE_URL" -f schema/001_financial_schema.sql
psql "$DATABASE_URL" -f schema/002_question_templates.sql

echo "02 | Schema reset complete."
