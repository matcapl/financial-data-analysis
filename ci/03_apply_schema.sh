#!/usr/bin/env bash
set -euo pipefail

echo "=== Database Migration System ==="
echo "Schema generation has been replaced with database migrations."
echo ""
echo "To apply database migrations:"
echo "  python database/migrate.py up"
echo ""
echo "To check migration status:"
echo "  python database/migrate.py status"
echo ""
echo "To create new migrations:"
echo "  python database/migrate.py create 'Description'"
echo ""
echo "See database/README.md for full documentation."

# Load env
if [[ -f .env ]]; then
  set -a; source .env; set +a
fi

# Run migrations using the new system
echo "Applying database migrations..."

# Use virtual environment Python if available, otherwise system python
if [ -f .venv/bin/python3 ]; then
    PYTHON_CMD=".venv/bin/python3"
elif [ -f .venv/bin/python ]; then
    PYTHON_CMD=".venv/bin/python"
else
    PYTHON_CMD="python3"
fi

echo "Using Python: $PYTHON_CMD"
$PYTHON_CMD database/migrate.py up

echo "Database migrations completed successfully."
