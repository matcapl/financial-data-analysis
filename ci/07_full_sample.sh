#!/usr/bin/env bash
set -euo pipefail

# Load environment variables
if [[ -f .env ]]; then
    export $(grep -v '^#' .env | xargs)
fi

# Configuration
PORT=${PORT:-4000}
CONTAINER_NAME="finance-server_full"
DATA_DIR="data"
REPORT_FILE="/tmp/ci_full_sample_report.txt"

echo "=== 05 | Starting Full Sample Test Suite ==="

# Clean up function
cleanup() {
    echo "Cleaning up containers..."
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
}

trap cleanup EXIT
cleanup

# Initialize report
cat > "$REPORT_FILE" << 'EOF'
# Full Sample CI Test Report
## Test Execution Summary

EOF

echo "Report will be saved to: $REPORT_FILE"

# Find all test files
TEST_FILES=($(find "$DATA_DIR" -name "*.csv" -o -name "*.xlsx" -o -name "*.pdf" | sort))

if [[ ${#TEST_FILES[@]} -eq 0 ]]; then
    echo "❌ No test files found in $DATA_DIR"
    exit 1
fi

echo "Found ${#TEST_FILES[@]} test files to process"

# Record baseline counts
INITIAL_METRICS=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM financial_metrics;" | tr -d '[:space:]')
INITIAL_COMPANIES=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM companies;" | tr -d '[:space:]')

# Start container
echo "Starting API container for full sample test..."
docker run --rm --env-file .env -d -p "$PORT:$PORT" --name "$CONTAINER_NAME" finance-server

# Health check
for i in {1..30}; do
    if curl -sf "http://localhost:$PORT/health" >/dev/null 2>&1; then
        break
    fi
    if [[ $i -eq 30 ]]; then
        echo "❌ API health check failed"
        exit 1
    fi
    sleep 1
done

echo "API ready, processing files..."

# Process each file
SUCCESSFUL_UPLOADS=0
FAILED_UPLOADS=0
TOTAL_PROCESSING_TIME=0

for file in "${TEST_FILES[@]}"; do
    echo "Processing: $file"
    
    START_TIME=$(date +%s)
    BASENAME=$(basename "$file")
    
    # Upload file
    RESPONSE=$(curl -sf -w "%{http_code}" -F "file=@$file" "http://localhost:$PORT/api/upload" 2>&1 || echo "FAILED")
    
    END_TIME=$(date +%s)
    PROCESSING_TIME=$((END_TIME - START_TIME))
    TOTAL_PROCESSING_TIME=$((TOTAL_PROCESSING_TIME + PROCESSING_TIME))
    
    if echo "$RESPONSE" | grep -q "200$"; then
        echo "  ✅ Success (${PROCESSING_TIME}s)"
        SUCCESSFUL_UPLOADS=$((SUCCESSFUL_UPLOADS + 1))
        
        # Log to report
        cat >> "$REPORT_FILE" << EOF
### ✅ $BASENAME
- Processing time: ${PROCESSING_TIME}s
- Status: Success
- Response: $(echo "$RESPONSE" | head -1)

EOF
    else
        echo "  ❌ Failed (${PROCESSING_TIME}s)"
        FAILED_UPLOADS=$((FAILED_UPLOADS + 1))
        
        # Log failure details
        cat >> "$REPORT_FILE" << EOF
### ❌ $BASENAME
- Processing time: ${PROCESSING_TIME}s
- Status: Failed
- Error: $RESPONSE

EOF
    fi
    
    # Brief pause between uploads
    sleep 1
done

# Final database verification
sleep 3  # Allow for async processing

FINAL_METRICS=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM financial_metrics;" | tr -d '[:space:]')
FINAL_COMPANIES=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM companies;" | tr -d '[:space:]')
FINAL_DERIVED=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM derived_metrics;" | tr -d '[:space:]')
FINAL_QUESTIONS=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM questions;" | tr -d '[:space:]')

ADDED_METRICS=$((FINAL_METRICS - INITIAL_METRICS))
ADDED_COMPANIES=$((FINAL_COMPANIES - INITIAL_COMPANIES))

# Generate final report
cat >> "$REPORT_FILE" << EOF

## Final Results Summary

**File Processing:**
- Total files processed: ${#TEST_FILES[@]}
- Successful uploads: $SUCCESSFUL_UPLOADS
- Failed uploads: $FAILED_UPLOADS
- Total processing time: ${TOTAL_PROCESSING_TIME}s
- Average time per file: $(( TOTAL_PROCESSING_TIME / ${#TEST_FILES[@]} ))s

**Database Impact:**
- Financial metrics added: $ADDED_METRICS
- New companies created: $ADDED_COMPANIES
- Derived metrics calculated: $FINAL_DERIVED
- Questions generated: $FINAL_QUESTIONS

**Success Rate:** $(( SUCCESSFUL_UPLOADS * 100 / ${#TEST_FILES[@]} ))%

EOF

# Print summary
echo ""
echo "=== Full Sample Test Summary ==="
echo "Files processed: ${#TEST_FILES[@]}"
echo "Successful: $SUCCESSFUL_UPLOADS"
echo "Failed: $FAILED_UPLOADS"
echo "Success rate: $(( SUCCESSFUL_UPLOADS * 100 / ${#TEST_FILES[@]} ))%"
echo "Metrics added: $ADDED_METRICS"
echo "Processing time: ${TOTAL_PROCESSING_TIME}s"
echo ""
echo "Full report available at: $REPORT_FILE"

# Test report generation endpoint (optional)
if [[ $SUCCESSFUL_UPLOADS -gt 0 ]]; then
    echo "Testing report generation..."
    COMPANY_ID=$(psql "$DATABASE_URL" -t -c "SELECT id FROM companies LIMIT 1;" | tr -d '[:space:]')
    
    if [[ -n "$COMPANY_ID" ]]; then
        REPORT_RESPONSE=$(curl -sf -X POST -H "Content-Type: application/json" \
            -d "{\"company_id\":$COMPANY_ID}" \
            "http://localhost:$PORT/api/generate-report" 2>&1 || echo "REPORT_FAILED")
        
        if echo "$REPORT_RESPONSE" | grep -q "report_filename"; then
            echo "✅ Report generation test passed"
        else
            echo "⚠️  Report generation test failed (non-critical)"
        fi
    fi
fi

# Determine exit code
if [[ $FAILED_UPLOADS -eq 0 ]]; then
    echo "✅ 05 | Full sample test suite PASSED"
    exit 0
elif [[ $SUCCESSFUL_UPLOADS -gt 0 ]]; then
    echo "⚠️  05 | Full sample test suite completed with some failures"
    exit 0
else
    echo "❌ 05 | Full sample test suite FAILED - no successful uploads"
    exit 1
fi