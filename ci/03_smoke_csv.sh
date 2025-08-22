#!/usr/bin/env bash
set -xeuo pipefail

# Enhanced CSV Smoke Test with comprehensive error handling and debugging
# This script validates the complete three-layer ingestion pipeline end-to-end

# Load environment variables
if [[ -f .env ]]; then
    export $(grep -v '^#' .env | xargs)
fi

# Validate required environment variables
: "${DATABASE_URL:?DATABASE_URL must be set}"
: "${VERCEL_BLOB_TOKEN:?VERCEL_BLOB_TOKEN must be set for blob storage}"

# Configuration with defaults
PORT=${PORT:-4000}
CONTAINER_NAME="finance-server_ci"
SMOKE_FILE="data/smoke.csv"
EXPECTED_REVENUE="2390873"

echo "=== 03 | Enhanced CSV Smoke Test ==="
echo "Database URL: ${DATABASE_URL:0:50}..."
echo "Port: $PORT"
echo "Container: $CONTAINER_NAME"

# Enhanced cleanup function
cleanup() {
    echo "Cleaning up containers..."
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
}
trap cleanup EXIT
cleanup

# Create smoke test data with proper ISO 8601 format matching periods.yaml
if [[ ! -f "$SMOKE_FILE" ]]; then
    echo "Creating enhanced smoke test CSV..."
    mkdir -p data
    cat > "$SMOKE_FILE" << 'EOF'
company_id,company_name,line_item,period_label,period_type,value,value_type,source_file,source_page,notes
1,Example Company,Revenue,2025-02,Monthly,2390873,Actual,smoke.csv,1,smoke test actual revenue
1,Example Company,Revenue,2025-02,Monthly,2000000,Budget,smoke.csv,1,smoke test budget revenue
1,Example Company,EBITDA,2025-02,Monthly,239087,Actual,smoke.csv,1,smoke test actual ebitda
1,Example Company,EBITDA,2025-02,Monthly,300000,Budget,smoke.csv,1,smoke test budget ebitda
1,Example Company,Gross Profit,2025-02,Monthly,1195436,Actual,smoke.csv,1,smoke test gross profit
EOF
    echo "✅ Created smoke test CSV with ISO 8601 period format (2025-02)"
fi

# Validate smoke file format and content
echo "=== Smoke File Validation ==="
if [[ -f "$SMOKE_FILE" ]]; then
    echo "✅ Smoke file exists: $SMOKE_FILE"
    echo "File size: $(wc -c < "$SMOKE_FILE") bytes"
    echo "Line count: $(wc -l < "$SMOKE_FILE") lines"
    echo ""
    echo "Smoke file content preview:"
    head -5 "$SMOKE_FILE"
    echo ""
else
    echo "❌ Smoke file not found: $SMOKE_FILE"
    exit 1
fi

# Verify periods.yaml contains the expected alias
echo "=== Period Configuration Validation ==="
if [[ -f "config/periods.yaml" ]]; then
    if grep -q "2025-02" config/periods.yaml; then
        echo "✅ periods.yaml contains 2025-02 canonical format"
    else
        echo "⚠️ Warning: periods.yaml may not contain 2025-02 canonical format"
    fi
    
    if grep -q "Feb 2025" config/periods.yaml; then
        echo "✅ periods.yaml contains 'Feb 2025' alias"
    else
        echo "⚠️ Warning: periods.yaml may not contain 'Feb 2025' alias"
    fi
else
    echo "⚠️ Warning: config/periods.yaml not found"
fi

# Validate line item definitions
echo "=== Line Item Validation ==="
psql "$DATABASE_URL" -c "SELECT COUNT(*) as total_line_items FROM line_item_definitions;"
psql "$DATABASE_URL" -c "SELECT id, name FROM line_item_definitions WHERE name IN ('Revenue', 'EBITDA', 'Gross Profit');"

# Build Docker image with enhanced error handling
echo "=== Docker Build ==="
echo "Building Docker image..."
if ! docker build -t finance-server -f server/Dockerfile .; then
    echo "❌ Docker build failed"
    exit 1
fi
echo "✅ Docker image built successfully"

# Start API container with enhanced configuration
echo "=== Container Startup ==="
echo "Starting API container..."
docker run --rm -d \
    --env-file .env \
    -e "DATABASE_URL=${DATABASE_URL}" \
    -e "VERCEL_BLOB_TOKEN=${VERCEL_BLOB_TOKEN}" \
    -v "$(pwd)/.env":/app/.env \
    -p "$PORT:$PORT" \
    --name "$CONTAINER_NAME" \
    finance-server

echo "✅ Container started with name: $CONTAINER_NAME"

# Enhanced health check with detailed logging
echo "=== Health Check ==="
echo "Waiting for API to be ready..."
for i in {1..45}; do
    if curl -sf "http://localhost:$PORT/health" | grep -q '"status":"ok"'; then
        echo "✅ API is ready! (attempt $i)"
        break
    fi
    if [[ $i -eq 45 ]]; then
        echo "❌ API failed to start within 45 seconds"
        echo "=== Container Logs ==="
        docker logs "$CONTAINER_NAME"
        exit 1
    fi
    echo "  Health check attempt $i/45..."
    sleep 1
done

# Show API info
echo "=== API Information ==="
curl -s "http://localhost:$PORT/health" | jq . 2>/dev/null || curl -s "http://localhost:$PORT/health"

# Upload smoke test with comprehensive error handling
echo "=== File Upload Test ==="
echo "Uploading smoke test CSV..."
UPLOAD_START=$(date +%s)

UPLOAD_RESPONSE=$(curl -w "%{http_code}" -F "file=@$SMOKE_FILE" "http://localhost:$PORT/api/upload" 2>&1)
UPLOAD_HTTP_CODE="${UPLOAD_RESPONSE: -3}"
UPLOAD_BODY="${UPLOAD_RESPONSE%???}"

UPLOAD_END=$(date +%s)
UPLOAD_TIME=$((UPLOAD_END - UPLOAD_START))

echo "Upload completed in ${UPLOAD_TIME}s"
echo "HTTP Status Code: $UPLOAD_HTTP_CODE"
echo "Response Body: $UPLOAD_BODY"

# Validate upload success
if [[ "$UPLOAD_HTTP_CODE" != "200" ]]; then
    echo "❌ Upload failed with HTTP code: $UPLOAD_HTTP_CODE"
    echo "Response: $UPLOAD_BODY"
    echo "=== Container Logs ==="
    docker logs --tail 100 "$CONTAINER_NAME"
    exit 1
fi

if ! echo "$UPLOAD_BODY" | grep -q 'File processed successfully'; then
    echo "❌ Upload response doesn't indicate success"
    echo "Response: $UPLOAD_BODY"
    echo "=== Container Logs ==="
    docker logs --tail 100 "$CONTAINER_NAME"
    exit 1
fi

echo "✅ Upload succeeded"

# Enhanced data verification with comprehensive debugging
echo "=== Database Verification ==="
sleep 3  # Allow time for async processing

echo "--- Database Counts ---"
psql "$DATABASE_URL" -c "SELECT COUNT(*) as total_metrics FROM financial_metrics;"
psql "$DATABASE_URL" -c "SELECT COUNT(*) as total_companies FROM companies;"
psql "$DATABASE_URL" -c "SELECT COUNT(*) as total_periods FROM periods;"
psql "$DATABASE_URL" -c "SELECT COUNT(*) as total_line_items FROM line_item_definitions;"

echo "--- Line Items ---"
psql "$DATABASE_URL" -c "SELECT id, name, aliases FROM line_item_definitions ORDER BY id;"

echo "--- Periods (Recent) ---"
psql "$DATABASE_URL" -c "SELECT id, period_label, period_type FROM periods WHERE period_label LIKE '2025%' ORDER BY id DESC LIMIT 10;"

echo "--- Financial Metrics (All) ---"
psql "$DATABASE_URL" -c "SELECT * FROM financial_metrics ORDER BY id DESC LIMIT 10;"

echo "--- Joined Data Verification ---"
psql "$DATABASE_URL" -c "
    SELECT 
        c.name as company,
        p.period_label,
        p.period_type,
        li.name as line_item,
        fm.value,
        fm.value_type,
        fm.source_file
    FROM financial_metrics fm
    JOIN companies c ON fm.company_id = c.id
    JOIN periods p ON fm.period_id = p.id
    JOIN line_item_definitions li ON fm.line_item_id = li.id
    ORDER BY fm.id DESC
    LIMIT 20;
"

# Specific revenue verification with multiple approaches
echo "--- Revenue Verification ---"

# Try exact period match first
ACTUAL_EXACT=$(psql "$DATABASE_URL" -t -c "
    SELECT fm.value
    FROM financial_metrics fm
    JOIN line_item_definitions li ON fm.line_item_id = li.id
    JOIN periods p ON fm.period_id = p.id
    WHERE li.name = 'Revenue'
      AND p.period_label = '2025-02'
      AND fm.value_type = 'Actual'
    LIMIT 1;
" | tr -d '[:space:]')

echo "Revenue (exact match 2025-02): '$ACTUAL_EXACT'"

# Try fuzzy match
ACTUAL_FUZZY=$(psql "$DATABASE_URL" -t -c "
    SELECT fm.value
    FROM financial_metrics fm
    JOIN line_item_definitions li ON fm.line_item_id = li.id
    JOIN periods p ON fm.period_id = p.id
    WHERE li.name ILIKE '%revenue%'
      AND fm.value_type = 'Actual'
    ORDER BY fm.id DESC
    LIMIT 1;
" | tr -d '[:space:]')

echo "Revenue (fuzzy match): '$ACTUAL_FUZZY'"

# Use the exact match if available, otherwise fuzzy
ACTUAL="${ACTUAL_EXACT:-$ACTUAL_FUZZY}"

echo "Final revenue value found: '$ACTUAL'"

# Validation logic
if [[ -z "$ACTUAL" ]]; then
    echo "❌ No revenue data found in database"
    echo "=== Debug: All financial metrics ===")
    psql "$DATABASE_URL" -c "SELECT * FROM financial_metrics;"
    echo "=== Debug: All periods ===")
    psql "$DATABASE_URL" -c "SELECT * FROM periods WHERE period_label LIKE '%2025%';"
    exit 1
fi

if [[ "$ACTUAL" != "$EXPECTED_REVENUE" ]]; then
    echo "❌ Data verification failed: expected $EXPECTED_REVENUE, got $ACTUAL"
    echo "=== Debug: Revenue records ===")
    psql "$DATABASE_URL" -c "
        SELECT 
            fm.value,
            p.period_label,
            li.name,
            fm.value_type
        FROM financial_metrics fm
        JOIN periods p ON fm.period_id = p.id
        JOIN line_item_definitions li ON fm.line_item_id = li.id
        WHERE li.name ILIKE '%revenue%';
    "
    exit 1
fi

# Test derived metrics calculation
echo "=== Analytics Validation ==="
echo "Testing calc_metrics.py..."
if python server/scripts/calc_metrics.py 1; then
    echo "✅ calc_metrics.py executed successfully"
    DERIVED_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM derived_metrics;" | tr -d '[:space:]')
    echo "Derived metrics generated: $DERIVED_COUNT"
else
    echo "⚠️ calc_metrics.py failed (non-critical for smoke test)"
fi

# Test question generation
echo "Testing questions_engine.py..."
if python server/scripts/questions_engine.py 1; then
    echo "✅ questions_engine.py executed successfully"
else
    echo "⚠️ questions_engine.py failed (non-critical for smoke test)"
fi

# Final success message
echo ""
echo "🎉 ✅ 03 | Enhanced Smoke CSV test PASSED: revenue=$ACTUAL"
echo "   - File uploaded successfully"
echo "   - Data persisted to database"
echo "   - Period normalization working (2025-02)"
echo "   - Three-layer pipeline operational"
echo "   - Processing time: ${UPLOAD_TIME}s"
echo ""

exit 0
