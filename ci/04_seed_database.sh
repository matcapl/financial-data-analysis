#!/usr/bin/env bash
set -euo pipefail

# CI/CD Database Seeding Script
# This script seeds the database with reference data and examples

LOG() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"; }

LOG "=== CI/CD Database Seeding ==="

# Load environment
ENV_FILE="${ENV_FILE:-.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a; source "$ENV_FILE"; set +a
  LOG "Loaded environment from $ENV_FILE"
else
  LOG "Warning: $ENV_FILE not found. Using environment variables."
fi

# Verify required environment variables
: "${DATABASE_URL:?DATABASE_URL must be set for seeding}"

# Determine Python command
if [ -f .venv/bin/python3 ]; then
    PYTHON_CMD=".venv/bin/python3"
elif [ -f .venv/bin/python ]; then
    PYTHON_CMD=".venv/bin/python"
else
    PYTHON_CMD="python3"
fi

LOG "Using Python: $PYTHON_CMD"

# Check if migrations are up to date first
LOG "Verifying migrations are applied..."
if ! $PYTHON_CMD database/migrate.py status | grep -q "Pending migrations: 0"; then
    LOG "❌ Pending migrations found. Apply migrations first."
    exit 1
fi

LOG "✅ Migrations are up to date"

# Run database seeding
LOG "Running database seeding..."
if $PYTHON_CMD database/seed.py; then
    LOG "✅ Database seeding completed successfully"
else
    LOG "❌ Database seeding failed"
    exit 1
fi

# Verify seeding results
LOG "Verifying seeding results..."
VERIFICATION_RESULT=$($PYTHON_CMD -c "
import sys
sys.path.insert(0, 'server/scripts')
from utils import get_db_connection

try:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Check critical counts
            cur.execute('SELECT COUNT(*) FROM question_templates')
            templates = cur.fetchone()[0]
            
            cur.execute('SELECT COUNT(*) FROM line_item_definitions')
            line_items = cur.fetchone()[0]
            
            cur.execute('SELECT COUNT(*) FROM companies')
            companies = cur.fetchone()[0]
            
            if templates < 5:
                print(f'ERROR: Insufficient question templates ({templates})')
                sys.exit(1)
                
            if line_items < 10:
                print(f'ERROR: Insufficient line items ({line_items})')
                sys.exit(1)
                
            if companies < 2:
                print(f'ERROR: Insufficient companies ({companies})')
                sys.exit(1)
                
            print(f'SUCCESS: Templates={templates}, LineItems={line_items}, Companies={companies}')
            
except Exception as e:
    print(f'ERROR: Verification failed: {e}')
    sys.exit(1)
")

if echo "$VERIFICATION_RESULT" | grep -q "SUCCESS"; then
    LOG "✅ Seeding verification passed: $VERIFICATION_RESULT"
else
    LOG "❌ Seeding verification failed: $VERIFICATION_RESULT"
    exit 1
fi

LOG "Database seeding pipeline completed successfully"