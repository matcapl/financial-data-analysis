#!/usr/bin/env bash
set -euo pipefail

# Load env
if [[ -f .env ]]; then
  set -a; source .env; set +a
fi

# Function to apply schema files to a given database URL
apply_schema() {
  local url=$1
  echo "Applying schema to $url"
  psql "$url" -f schema/001_financial_schema.sql
  psql "$url" -f schema/002_question_templates.sql
}

# Apply to remote
apply_schema "$DATABASE_URL"

# Apply to local if set
if [[ -n "${LOCAL_DATABASE_URL:-}" ]]; then
  apply_schema "$LOCAL_DATABASE_URL"
else
  echo "Warning: LOCAL_DATABASE_URL not set, skipping local apply."
fi

echo "Schema and seed SQL applied to both remote and local databases."
