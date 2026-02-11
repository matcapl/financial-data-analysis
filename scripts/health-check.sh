#!/usr/bin/env bash
set -euo pipefail

# Health Check Script for Production Deployment
# This script verifies the application and database are healthy

LOG() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] [HEALTH] $*"; }

LOG "Starting health check..."

# Load environment variables
ENV_FILE="${ENV_FILE:-.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a; source "$ENV_FILE"; set +a
  LOG "Loaded environment from $ENV_FILE"
else
  LOG "Warning: $ENV_FILE not found. Using environment variables."
fi

# Default values
TIMEOUT=${HEALTH_CHECK_TIMEOUT:-30}
APP_URL=${APP_URL:-http://localhost:4000}

# Function to check database connectivity
check_database() {
    LOG "Checking database connectivity..."
    
    if [ -z "${DATABASE_URL:-}" ]; then
        LOG "❌ DATABASE_URL not set"
        return 1
    fi
    
    # Determine Python command (prefer virtual environment)
    if [ -f .venv/bin/python3 ]; then
        PYTHON_CMD=".venv/bin/python3"
    elif [ -f .venv/bin/python ]; then
        PYTHON_CMD=".venv/bin/python"
    elif command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        LOG "❌ Python not found"
        return 1
    fi
    
    # Test database connection and migration status
    if $PYTHON_CMD -c "
import sys
sys.path.insert(0, 'server/app')
from app.utils.utils import get_db_connection
try:
    conn = get_db_connection()
    with conn.cursor() as cur:
        # Check basic connectivity
        cur.execute('SELECT 1')
        
        # Check if migrations table exists and get status
        cur.execute('''
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'schema_migrations'
            )
        ''')
        
        if cur.fetchone()[0]:
            cur.execute('SELECT COUNT(*) FROM schema_migrations')
            migration_count = cur.fetchone()[0]
            print(f'Database connected. Applied migrations: {migration_count}')
        else:
            print('Database connected. No migrations table found.')
            
    conn.close()
except Exception as e:
    print(f'Database connection failed: {e}')
    sys.exit(1)
"; then
        LOG "✅ Database health check passed"
        return 0
    else
        LOG "❌ Database health check failed"
        return 1
    fi
}

# Function to check application health
check_application() {
    LOG "Checking application health..."
    
    local health_endpoint="$APP_URL/health"
    local retries=0
    local max_retries=5
    
    while [ $retries -lt $max_retries ]; do
        if curl -f -s -m "$TIMEOUT" "$health_endpoint" > /dev/null 2>&1; then
            LOG "✅ Application health check passed"
            return 0
        else
            retries=$((retries + 1))
            LOG "⏳ Application not ready, retry $retries/$max_retries..."
            sleep 2
        fi
    done
    
    LOG "❌ Application health check failed after $max_retries attempts"
    return 1
}

# Function to check migration status
check_migration_status() {
    LOG "Checking migration status..."
    
    # Determine Python command (prefer virtual environment)
    if [ -f .venv/bin/python3 ]; then
        PYTHON_CMD=".venv/bin/python3"
    elif [ -f .venv/bin/python ]; then
        PYTHON_CMD=".venv/bin/python"
    elif command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        LOG "❌ Python not found"
        return 1
    fi
    
    if $PYTHON_CMD database/migrate.py status > /dev/null 2>&1; then
        LOG "✅ Migration status check passed"
        
        # Get pending migrations count
        local pending_count
        pending_count=$($PYTHON_CMD database/migrate.py status | grep "Pending migrations:" | grep -o '[0-9]*' || echo "0")
        
        if [ "$pending_count" -gt 0 ]; then
            LOG "⚠️  Warning: $pending_count pending migrations found"
        else
            LOG "✅ No pending migrations"
        fi
        
        return 0
    else
        LOG "❌ Migration status check failed"
        return 1
    fi
}

# Run all health checks
EXIT_CODE=0

check_database || EXIT_CODE=1
check_migration_status || EXIT_CODE=1
check_application || EXIT_CODE=1

if [ $EXIT_CODE -eq 0 ]; then
    LOG "✅ All health checks passed"
else
    LOG "❌ Health check failed"
fi

exit $EXIT_CODE