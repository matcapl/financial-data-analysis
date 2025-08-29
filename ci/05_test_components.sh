#!/usr/bin/env bash
set -euo pipefail

# Individual Component Tests - Test each script in isolation
echo "🔧 === INDIVIDUAL COMPONENT TESTS ==="

# Load environment
if [[ -f .env ]]; then
    echo "Loading .env environment variables."
    export $(grep -v '^#' .env | xargs)
fi

: "${DATABASE_URL:?DATABASE_URL must be set}"

echo "Database: ${DATABASE_URL:0:50}..."
echo ""

# Activate uv virtual environment if present
if [[ -f .venv/bin/activate ]]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

# Test 1: Test extraction.py directly
echo "🔍 Test 1: extraction.py standalone"
uv run python - <<'PYCODE'
import sys
sys.path.insert(0, 'server/scripts')
from extraction import extract_data
data = extract_data('data/sample_data.csv')
print(f'✅ extraction.py returned {len(data)} rows')
PYCODE

echo ""

# Test 2: Test ingest_xlsx.py with detailed logging
echo "🔍 Test 2: ingest_xlsx.py with detailed logging"
# Clear test data first
psql "$DATABASE_URL" -c "DELETE FROM financial_metrics WHERE source_file = 'sample_data.csv';" > /dev/null

echo "Running: uv run python server/scripts/ingest_xlsx.py data/sample_data.csv 1"
uv run python server/scripts/ingest_xlsx.py data/sample_data.csv 1

echo "Database check after ingestion:"
psql "$DATABASE_URL" -c \
"SELECT COUNT(*) AS inserted_rows
FROM financial_metrics
WHERE source_file = 'sample_data.csv';"

echo ""

# Test 3: Test calc_metrics.py
echo "🔍 Test 3: calc_metrics.py standalone"
echo "Running: uv run python server/scripts/calc_metrics.py 1"
uv run python server/scripts/calc_metrics.py 1 && \
echo "✅ calc_metrics.py completed" || echo "❌ calc_metrics.py failed"

echo ""

# Test 4: Test questions_engine.py
echo "🔍 Test 4: questions_engine.py standalone"
echo "Running: uv run python server/scripts/questions_engine.py 1"
uv run python server/scripts/questions_engine.py 1 && \
echo "✅ questions_engine.py completed" || echo "❌ questions_engine.py failed"

echo ""

# Test 5: Manual database verification
echo "🔍 Test 5: Manual database verification"
echo "--- Tables and row counts ---"
psql "$DATABASE_URL" -c "
SELECT 'companies' AS table_name, COUNT(*) AS rows FROM companies
UNION ALL
SELECT 'financial_metrics', COUNT(*) FROM financial_metrics
UNION ALL
SELECT 'periods', COUNT(*) FROM periods
UNION ALL
SELECT 'line_item_definitions', COUNT(*) FROM line_item_definitions;
"

echo ""
echo "--- Sample financial_metrics data ---"
psql "$DATABASE_URL" -c "
SELECT
    fm.id,
    c.name AS company,
    li.name AS line_item,
    p.period_label,
    fm.value,
    fm.value_type,
    fm.source_file
FROM financial_metrics fm
LEFT JOIN companies c ON fm.company_id = c.id
LEFT JOIN line_item_definitions li ON fm.line_item_id = li.id
LEFT JOIN periods p ON fm.period_id = p.id
ORDER BY fm.id DESC
LIMIT 10;
"

echo ""
echo "🔍 Component testing complete!"
# echo "Check the output above to see where the pipeline is failing."