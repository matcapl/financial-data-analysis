#!/usr/bin/env bash
set -euo pipefail

# Container Testing - Test inside Docker environment where the issue occurs
echo "🐳 === CONTAINER ENVIRONMENT TESTING ==="

# Load environment
if [[ -f .env ]]; then
    echo "Loading .env environment variables."
    export $(grep -v '^#' .env | xargs)
fi

: "${DATABASE_URL:?DATABASE_URL must be set}"

# Build container
echo "🔨 Building test container..."
docker build --no-cache -t finance-server-debug -f server/Dockerfile .

# Start container
echo "🚀 Starting debug container..."
CONTAINER_ID=$(docker run --rm -d \
    --env-file .env \
    -e "DATABASE_URL=${DATABASE_URL}" \
    -v "$(pwd)/data:/app/data" \
    --name finance-debug-$$ \
    finance-server-debug \
    tail -f /dev/null)
echo "Container ID: $CONTAINER_ID"
echo ""

# Test 1: File structure
echo "🔍 Test 1: Container file structure"
docker exec "$CONTAINER_ID" ls -la /app/
docker exec "$CONTAINER_ID" ls -la /app/server/scripts/
echo ""

# Test 2: Python environment in container
echo "🔍 Test 2: Python environment in container"
docker exec "$CONTAINER_ID" uv run python - <<'PYCODE'
import sys
print('Python path:')
for p in sys.path: print(f'  {p}')
sys.path.insert(0, '/app/server/scripts')
try:
    from utils import get_db_connection; print('✅ utils imported')
    from extraction import extract_data; print('✅ extraction imported')
    from field_mapper import map_and_filter_row; print('✅ field_mapper imported')
    from normalization import normalize_data; print('✅ normalization imported')
    from persistence import persist_data; print('✅ persistence imported')
except ImportError as e:
    print(f'❌ Import error: {e}')
PYCODE
echo ""

# Test 3: Database connection from container
echo "🔍 Test 3: Database connection from container"
docker exec "$CONTAINER_ID" uv run python - <<'PYCODE'
import sys
sys.path.insert(0, '/app/server/scripts')
from utils import get_db_connection
with get_db_connection() as conn:
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM financial_metrics')
        count = cur.fetchone()[0]
        print(f'✅ Database connection OK from container, rows: {count}')
PYCODE
echo ""

# Test 4: Run ingestion inside container
echo "🔍 Test 4: Run ingestion inside container"
psql "$DATABASE_URL" -c "DELETE FROM financial_metrics WHERE source_file = 'container_test.csv';" > /dev/null

docker exec "$CONTAINER_ID" sh -c "cat > /app/data/container_test.csv << 'EOF'
company_id,company_name,line_item,period_label,period_type,value,value_type,source_file,source_page,notes
1,Container Test,Revenue,2025-02,Monthly,777777,Actual,container_test.csv,1,container test
EOF"

echo "Running ingestion inside container..."
docker exec "$CONTAINER_ID" uv run python /app/server/scripts/ingest_xlsx.py /app/data/container_test.csv 1

echo "🔍 Checking database after container ingestion:"
psql "$DATABASE_URL" -c "
SELECT COUNT(*) AS container_rows
FROM financial_metrics
WHERE source_file = 'container_test.csv';
"
echo ""

# Test 5: Simulate API upload inside container
echo "🔍 Test 5: Simulate API upload process inside container"
psql "$DATABASE_URL" -c "DELETE FROM financial_metrics WHERE source_file = 'api_test.csv';" > /dev/null

docker exec "$CONTAINER_ID" sh -c "cat > /app/data/api_test.csv << 'EOF'
company_id,company_name,line_item,period_label,period_type,value,value_type,source_file,source_page,notes
1,API Test,Revenue,2025-02,Monthly,888888,Actual,api_test.csv,1,api test
EOF"

docker exec "$CONTAINER_ID" sh -c '
echo "🔄 Simulating upload.js process..."
for p in "/app/server/scripts/ingest_xlsx.py" "/app/scripts/ingest_xlsx.py" "./server/scripts/ingest_xlsx.py"; do
  if [ -f "$p" ]; then echo "✅ Found script at: $p"; SCRIPT="$p"; break; else echo "❌ Not found: $p"; fi
done
if [ -n "$SCRIPT" ]; then
  cd /app
  echo "Working directory: $(pwd)"
  uv run python "$SCRIPT" /app/data/api_test.csv 1
else
  echo "❌ No script found"
fi
'

echo "🔍 Checking database after API simulation:"
psql "$DATABASE_URL" -c "
SELECT fm.value, p.period_label, li.name AS line_item, fm.source_file
FROM financial_metrics fm
JOIN periods p ON fm.period_id = p.id
JOIN line_item_definitions li ON fm.line_item_id = li.id
WHERE fm.source_file = 'api_test.csv';
"
echo ""

# Cleanup container and test files
echo "🧹 Cleaning up container and test data..."
docker stop "$CONTAINER_ID" >/dev/null
rm -f data/container_test.csv data/api_test.csv

echo ""
echo "🐳 Container testing complete!"
