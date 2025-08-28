#!/usr/bin/env bash
set -euo pipefail

# Production Deployment Start Script
# This script runs database migrations before starting the application

LOG() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] [DEPLOY] $*"; }

LOG "Starting production deployment..."

# Verify required environment variables
: "${DATABASE_URL:?DATABASE_URL must be set for production deployment}"

# Determine Python command (for containerized environments)
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    LOG "❌ Python not found in PATH"
    exit 1
fi

LOG "Using Python: $PYTHON_CMD"

# Run database migrations
LOG "Running database migrations..."
if $PYTHON_CMD database/migrate.py up; then
    LOG "✅ Database migrations completed successfully"
else
    LOG "❌ Database migrations failed"
    exit 1
fi

# Update rollback SQL (non-critical)
LOG "Updating rollback SQL..."
$PYTHON_CMD database/migrate.py update-rollback || {
    LOG "⚠️  Warning: Failed to update rollback SQL (non-critical)"
}

# Seed database with reference data (non-critical for production)
LOG "Seeding database with reference data..."
$PYTHON_CMD database/seed.py || {
    LOG "⚠️  Warning: Database seeding failed (non-critical for production)"
}

# Show final migration status
LOG "Final migration status:"
$PYTHON_CMD database/migrate.py status

# Start the Node.js application
LOG "Starting Node.js application..."
cd server && node api/index.js