#!/usr/bin/env bash
set -euo pipefail

# Load environment variables
if [[ -f .env ]]; then
    export $(grep -v '^#' .env | xargs)
fi

# Configuration
PORT=${PORT:-4000}
CONTAINER_NAME="finance-server_integration"
TEST_FILE="data/financial_data_template.xlsx"
MIN_EXPECTED_ROWS=5

echo "=== 04 | Starting XLSX Integration Test ==="

# Clean up function
cleanup() {
    echo "Cleaning up containers..."
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
}

trap cleanup EXIT
cleanup

# Check if test file exists
if [[ ! -f "$TEST_FILE" ]]; then
    echo "❌ Test file not found: $TEST_FILE"
    echo "Please ensure the financial_data_template.xlsx file exists in the data/ directory"
    exit 1
fi

# Record initial row count
INITIAL_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM financial_metrics;" | tr -d '[:space:]')
echo "Initial financial_metrics count: $INITIAL_COUNT"

# Start container
echo "Starting API container for integration test..."
docker run --rm --env-file .env -d -p "$PORT:$PORT" --name "$CONTAINER_NAME" finance-server

# Health check with detailed logging
echo "Waiting for API health check..."
for i in {1..30}; do
    if curl -sf "http://localhost:$PORT/health" >/dev/null 2>&1; then
        echo "API health check passed"
        break
    fi
    if [[ $i -eq 30 ]]; then
        echo "❌ API health check failed"
        docker logs --tail 50 "$CONTAINER_NAME"
        exit 1
    fi
    sleep 1
done

# Upload Excel file
echo "Uploading Excel file: $TEST_FILE"
UPLOAD_START=$(date +%s)

UPLOAD_RESPONSE=$(curl -sf -w "%{http_code}" -F "file=@$TEST_FILE" "http://localhost:$PORT/api/upload" || echo "CURL_FAILED")

UPLOAD_END=$(date +%s)
UPLOAD_TIME=$((UPLOAD_END - UPLOAD_START))

if [[ "$UPLOAD_RESPONSE" == "CURL_FAILED" ]] || ! echo "$UPLOAD_RESPONSE" | grep -q "200$"; then
    echo "❌ Excel upload failed:"
    echo "$UPLOAD_RESPONSE"
    docker logs --tail 100 "$CONTAINER_NAME"
    exit 1
fi

echo "✅ Excel upload completed in ${UPLOAD_TIME}s"

# Verify data processing
echo "Verifying processed data..."
sleep 2  # Allow time for async processing

FINAL_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM financial_metrics;" | tr -d '[:space:]')
ADDED_ROWS=$((FINAL_COUNT - INITIAL_COUNT))

if [[ $ADDED_ROWS -lt $MIN_EXPECTED_ROWS ]]; then
    echo "❌ Insufficient data processed: expected at least $MIN_EXPECTED_ROWS rows, got $ADDED_ROWS"
    
    # Debug: Show what was actually inserted
    echo "Recent financial_metrics entries:"
    psql "$DATABASE_URL" -c "
        SELECT c.name as company, p.period_label, li.name as line_item, fm.value 
        FROM financial_metrics fm 
        JOIN companies c ON fm.company_id = c.id 
        JOIN periods p ON fm.period_id = p.id 
        JOIN line_item_definitions li ON fm.line_item_id = li.id 
        ORDER BY fm.id DESC 
        LIMIT 10;
    "
    exit 1
fi

# Check if derived metrics were calculated
DERIVED_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM derived_metrics;" | tr -d '[:space:]')
echo "Derived metrics generated: $DERIVED_COUNT"

# Check if questions were generated
QUESTIONS_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM questions;" | tr -d '[:space:]')
echo "Questions generated: $QUESTIONS_COUNT"

echo "✅ 04 | XLSX Integration test passed: $ADDED_ROWS rows added, $DERIVED_COUNT derived metrics, $QUESTIONS_COUNT questions"
exit 0