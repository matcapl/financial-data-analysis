#!/usr/bin/env bash
set -euo pipefail

# CI/CD Database Migration Verification Script
# This script verifies the migration system is ready for deployment

LOG() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"; }

LOG "=== CI/CD Migration System Check ==="

# Load environment
ENV_FILE="${ENV_FILE:-.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a; source "$ENV_FILE"; set +a
  LOG "Loaded environment from $ENV_FILE"
else
  LOG "Warning: $ENV_FILE not found. Using environment variables."
fi

# Verify required environment variables
: "${DATABASE_URL:?DATABASE_URL must be set for migrations}"

# Determine Python command
if [ -f .venv/bin/python3 ]; then
    PYTHON_CMD=".venv/bin/python3"
elif [ -f .venv/bin/python ]; then
    PYTHON_CMD=".venv/bin/python"
else
    PYTHON_CMD="python3"
fi

LOG "Using Python: $PYTHON_CMD"

# Test 1: Verify migration system is accessible
LOG "→ Testing migration system accessibility..."
if $PYTHON_CMD database/migrate.py --help > /dev/null 2>&1; then
    LOG "✅ Migration system accessible"
else
    LOG "❌ Migration system not accessible"
    exit 1
fi

# Test 2: Verify database connectivity
LOG "→ Testing database connectivity..."
if $PYTHON_CMD -c "
import sys
sys.path.insert(0, 'server/scripts')
from utils import get_db_connection
try:
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute('SELECT 1')
    conn.close()
    print('Database connection successful')
except Exception as e:
    print(f'Database connection failed: {e}')
    sys.exit(1)
"; then
    LOG "✅ Database connectivity verified"
else
    LOG "❌ Database connectivity failed"
    exit 1
fi

# Test 3: Check migration file integrity
LOG "→ Checking migration file integrity..."
MIGRATION_COUNT=$(find database/migrations -name "*.sql" -not -name "000_*" | wc -l)
LOG "Found $MIGRATION_COUNT migration files"

if [ "$MIGRATION_COUNT" -eq 0 ]; then
    LOG "❌ No migration files found"
    exit 1
fi

# Verify all migrations have rollback SQL
LOG "→ Verifying rollback SQL coverage..."
MISSING_ROLLBACK=0
for migration in database/migrations/*.sql; do
    if [[ "$(basename "$migration")" == "000_"* ]]; then
        continue  # Skip initialization migration
    fi
    
    if ! grep -q "ROLLBACK_START" "$migration"; then
        LOG "⚠️  Missing rollback SQL in $(basename "$migration")"
        MISSING_ROLLBACK=$((MISSING_ROLLBACK + 1))
    fi
done

if [ "$MISSING_ROLLBACK" -gt 0 ]; then
    LOG "⚠️  $MISSING_ROLLBACK migrations missing rollback SQL"
else
    LOG "✅ All migrations have rollback SQL"
fi

# Test 4: Dry-run migration status check
LOG "→ Performing dry-run migration status check..."
if $PYTHON_CMD database/migrate.py status > /dev/null 2>&1; then
    LOG "✅ Migration status check successful"
else
    LOG "❌ Migration status check failed"
    exit 1
fi

# Test 5: Verify migration dependencies
LOG "→ Checking migration dependencies..."
PYTHON_DEPS=("psycopg2" "pathlib")
for dep in "${PYTHON_DEPS[@]}"; do
    if $PYTHON_CMD -c "import $dep" 2>/dev/null; then
        LOG "✅ Python dependency $dep available"
    else
        LOG "❌ Missing Python dependency: $dep"
        exit 1
    fi
done

LOG "✅ CI/CD Migration System Check PASSED"
LOG "System is ready for migration deployment"