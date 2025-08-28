#!/usr/bin/env bash
set -euo pipefail

# Load .env if it exists
ENV_FILE="${ENV_FILE:-.env}"
if [ -f "$ENV_FILE" ]; then
  set -a
  source "$ENV_FILE"
  set +a
  echo "Loaded .env environment variables."
else
  echo "ERROR: .env file not found. Please copy .env.example and fill in your values."
  exit 1
fi

echo "=== STEP 0: Config and YAML Validation ==="
poetry run python scripts/validate_yaml.py

echo "=== STEP 0: Database migrations ==="
echo "NOTE: Schema generation has been replaced with database migrations."
echo "To apply database schema changes, run: python database/migrate.py up"

echo "=== Config validation complete! ==="
