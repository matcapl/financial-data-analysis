#!/usr/bin/env bash
set -euo pipefail

# CI/CD Database Migration Runner
# This script is used in CI/CD pipelines to apply database migrations safely
echo "=== CI/CD Database Migration System ==="
echo "Applying database migrations in CI/CD environment..."

# Load env
ENV_FILE="${ENV_FILE:-.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a; source "$ENV_FILE"; set +a
  echo "Loaded environment from $ENV_FILE"
else
  echo "Warning: $ENV_FILE not found. Using environment variables."
fi

# Verify required environment variables
: "${DATABASE_URL:?DATABASE_URL must be set for migrations}"

# Use virtual environment Python if available, otherwise system python
if [ -f .venv/bin/python3 ]; then
    PYTHON_CMD=".venv/bin/python3"
elif [ -f .venv/bin/python ]; then
    PYTHON_CMD=".venv/bin/python"
else
    PYTHON_CMD="python3"
fi

echo "Using Python: $PYTHON_CMD"

# Check migration status before applying
echo "Checking current migration status..."
$PYTHON_CMD database/migrate.py status || {
    echo "❌ Migration status check failed"
    exit 1
}

# Apply pending migrations
echo "Applying pending migrations..."
if $PYTHON_CMD database/migrate.py up; then
    echo "✅ Database migrations completed successfully"
    
    # Show final migration status
    echo "Final migration status:"
    $PYTHON_CMD database/migrate.py status
else
    echo "❌ Migration failed"
    exit 1
fi

# Optional: Update rollback SQL for new migrations
echo "Updating rollback SQL for migrations..."
$PYTHON_CMD database/migrate.py update-rollback || {
    echo "⚠️  Warning: Failed to update rollback SQL (non-critical)"
}
