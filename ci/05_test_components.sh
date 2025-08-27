#!/usr/bin/env bash
set -euo pipefail

# Individual Component Tests - Test each script in isolation
echo "🔧 === INDIVIDUAL COMPONENT TESTS ==="

# Load environment
if [[ -f .env ]]; then
    export $(grep -v '^#' .env | xargs)
fi

: "${DATABASE_URL:?DATABASE_URL must be set}"

echo "Database: ${DATABASE_URL:0:50}..."
echo ""

# Test 1: Test extraction.py directly
echo "🔍 Test 1: extraction.py standalone"
python3 server/scripts/extraction.py data/smoke.csv || echo "❌ extraction.py failed"
echo ""

# Test 2: Test ingest_xlsx.py with verbose output  
echo "🔍 Test 2: ingest_xlsx.py with detailed logging"
# Clear test data first
psql "$DATABASE_URL" -c "DELETE FROM financial_metrics WHERE source_file = 'smoke.csv';" > /dev/null

echo "Running: python3 server/scripts/ingest_xlsx.py data/smoke.csv 1"
python3 server/scripts/ingest_xlsx.py data/smoke.csv 1

# Check what actually got inserted
echo "Database check after ingestion:"
psql "$DATABASE_URL" -c "SELECT COUNT(*) as inserted_rows FROM financial_metrics WHERE source_file = 'smoke.csv';"
echo ""

# Test 3: Test calc_metrics.py
echo "🔍 Test 3: calc_metrics.py standalone"
python3 server/scripts/calc_metrics.py 1 || echo "❌ calc_metrics.py failed"
echo ""

# Test 4: Test questions_engine.py
echo "🔍 Test 4: questions_engine.py standalone"  
python3 server/scripts/questions_engine.py 1 || echo "❌ questions_engine.py failed"
echo ""

# Test 5: Manual database verification
echo "🔍 Test 5: Manual database verification"
echo "--- Tables and row counts ---"
psql "$DATABASE_URL" -c "
SELECT 
    'companies' as table_name, COUNT(*) as rows FROM companies
UNION ALL  
SELECT 
    'financial_metrics', COUNT(*) FROM financial_metrics
UNION ALL
SELECT 
    'periods', COUNT(*) FROM periods  
UNION ALL
SELECT
    'line_item_definitions', COUNT(*) FROM line_item_definitions;
"

echo ""
echo "--- Sample financial_metrics data ---"
psql "$DATABASE_URL" -c "
SELECT 
    fm.id,
    c.name as company,
    li.name as line_item,
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
echo "Check the output above to see where the pipeline is failing."