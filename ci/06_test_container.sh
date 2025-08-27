#!/usr/bin/env bash
set -euo pipefail

# Container Testing - Test inside Docker environment where the issue occurs
echo "🐳 === CONTAINER ENVIRONMENT TESTING ==="

# Load environment
if [[ -f .env ]]; then
    export $(grep -v '^#' .env | xargs)
fi

: "${DATABASE_URL:?DATABASE_URL must be set}"

# Build container
echo "🔨 Building test container..."
docker build --no-cache -t finance-server-debug -f server/Dockerfile .

# Start container with debug capabilities
echo "🚀 Starting debug container..."
CONTAINER_ID=$(docker run --rm -d \
    --env-file .env \
    -e "DATABASE_URL=${DATABASE_URL}" \
    -v "$(pwd)/data:/app/data" \
    --name finance-debug-$$ \
    finance-server-debug tail -f /dev/null)

echo "Container ID: $CONTAINER_ID"

# Test 1: Check file structure inside container
echo ""
echo "🔍 Test 1: Container file structure"
docker exec $CONTAINER_ID ls -la /app/
echo ""
echo "Scripts directory:"
docker exec $CONTAINER_ID ls -la /app/server/scripts/
echo ""

# Test 2: Test Python environment inside container
echo "🔍 Test 2: Python environment in container"
docker exec $CONTAINER_ID python3 -c "
import sys
print('Python path:')
for p in sys.path: print(f'  {p}')
print()

sys.path.insert(0, '/app/server/scripts')
try:
    from utils import get_db_connection
    print('✅ utils imported')
    from extraction import extract_data_auto
    print('✅ extraction imported')
    from field_mapper import map_and_filter_row
    print('✅ field_mapper imported')
    from normalization import normalize_data
    print('✅ normalization imported')
    from persistence import persist_data
    print('✅ persistence imported')
except ImportError as e:
    print(f'❌ Import error: {e}')
"

# Test 3: Test database connection from container
echo ""
echo "🔍 Test 3: Database connection from container"
docker exec $CONTAINER_ID python3 -c "
import sys
sys.path.insert(0, '/app/server/scripts')
try:
    from utils import get_db_connection
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM financial_metrics')
            count = cur.fetchone()[0]
            print(f'✅ Database connection OK from container, rows: {count}')
except Exception as e:
    print(f'❌ Database connection failed: {e}')
"

# Test 4: Run ingestion inside container
echo ""
echo "🔍 Test 4: Run ingestion script inside container"

# Clear test data
psql "$DATABASE_URL" -c "DELETE FROM financial_metrics WHERE source_file = 'smoke.csv';" > /dev/null

# Create test file in container
docker exec $CONTAINER_ID sh -c "
cat > /app/data/container_test.csv << 'EOF'
company_id,company_name,line_item,period_label,period_type,value,value_type,source_file,source_page,notes
1,Container Test,Revenue,2025-02,Monthly,777777,Actual,container_test.csv,1,container test
EOF
"

# Run ingestion
echo "Running ingestion inside container..."
docker exec $CONTAINER_ID python3 /app/server/scripts/ingest_xlsx.py /app/data/container_test.csv 1

# Check results
echo ""
echo "🔍 Checking database after container ingestion:"
psql "$DATABASE_URL" -c "
SELECT COUNT(*) as container_rows 
FROM financial_metrics 
WHERE source_file = 'container_test.csv'
"

# Test 5: Test API upload simulation
echo ""
echo "🔍 Test 5: Simulate API upload process inside container"

# Clear test data
psql "$DATABASE_URL" -c "DELETE FROM financial_metrics WHERE source_file = 'api_test.csv';" > /dev/null

docker exec $CONTAINER_ID sh -c "
# Create test file
cat > /app/data/api_test.csv << 'EOF'
company_id,company_name,line_item,period_label,period_type,value,value_type,source_file,source_page,notes
1,API Test,Revenue,2025-02,Monthly,888888,Actual,api_test.csv,1,api test
EOF

# Simulate the exact process that upload.js does
echo '🔄 Simulating upload.js process...'

# Test script path resolution
echo 'Testing script paths:'
for path in '/app/server/scripts/ingest_xlsx.py' '/app/scripts/ingest_xlsx.py' './server/scripts/ingest_xlsx.py'; do
    if [ -f \"\$path\" ]; then
        echo \"✅ Found script at: \$path\"
        SCRIPT_PATH=\"\$path\"
        break
    else
        echo \"❌ Not found: \$path\"
    fi
done

if [ -n \"\$SCRIPT_PATH\" ]; then
    echo \"Using script: \$SCRIPT_PATH\"
    
    # Set working directory like upload.js does
    cd /app
    echo \"Working directory: \$(pwd)\"
    
    # Run with the same environment as upload.js
    python3 \"\$SCRIPT_PATH\" /app/data/api_test.csv 1
else
    echo '❌ No script found'
fi
"

# Check API test results
echo ""
echo "🔍 Checking database after API simulation:"
psql "$DATABASE_URL" -c "
SELECT 
    fm.value, 
    p.period_label, 
    li.name as line_item,
    fm.source_file
FROM financial_metrics fm
JOIN periods p ON fm.period_id = p.id
JOIN line_item_definitions li ON fm.line_item_id = li.id
WHERE fm.source_file = 'api_test.csv'
"

# Cleanup
echo ""
echo "🧹 Cleaning up container..."
docker stop $CONTAINER_ID

echo ""
echo "🐳 Container testing complete!"
echo "This shows exactly what happens in the Docker environment where your CI runs."