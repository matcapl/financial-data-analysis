#!/usr/bin/env bash
set -xeuo pipefail

# Comprehensive Three-Layer Ingestion Testing Suite
# Tests each component individually to isolate problems

echo "🔬 === COMPREHENSIVE INGESTION TESTING SUITE ==="
echo "Testing each layer individually to isolate problems"
echo ""

# Load environment
if [[ -f .env ]]; then
    export $(grep -v '^#' .env | xargs)
fi

: "${DATABASE_URL:?DATABASE_URL must be set}"

# Test configuration
TEST_FILE="data/test_minimal.csv"
COMPANY_ID=1
EXPECTED_ROWS=2

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_test() { echo -e "${BLUE}🔍 TEST: $1${NC}"; }
print_pass() { echo -e "${GREEN}✅ PASS: $1${NC}"; }
print_fail() { echo -e "${RED}❌ FAIL: $1${NC}"; }
print_warn() { echo -e "${YELLOW}⚠️  WARN: $1${NC}"; }

# Create minimal test data
create_test_data() {
    print_test "Creating minimal test CSV"
    mkdir -p data
    cat > "$TEST_FILE" << 'EOF'
company_id,company_name,line_item,period_label,period_type,value,value_type,source_file,source_page,notes
1,Test Company,Revenue,2025-02,Monthly,1000000,Actual,test_minimal.csv,1,test revenue
1,Test Company,Revenue,2025-02,Monthly,950000,Budget,test_minimal.csv,1,test budget
EOF
    print_pass "Test data created: $TEST_FILE ($(wc -l < "$TEST_FILE") lines)"
    echo "Content:"
    cat "$TEST_FILE"
    echo ""
}

# Test 0: Database connectivity
test_database_connection() {
    print_test "Database connection from host"
    
    if psql "$DATABASE_URL" -c "SELECT 1;" > /dev/null 2>&1; then
        print_pass "Database connection OK"
    else
        print_fail "Database connection failed"
        return 1
    fi
    
    # Check required tables exist
    local tables_exist=$(psql "$DATABASE_URL" -t -c "
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_name IN ('financial_metrics', 'companies', 'periods', 'line_item_definitions')
    " | tr -d ' ')
    
    if [[ "$tables_exist" -eq 4 ]]; then
        print_pass "Required tables exist"
    else
        print_fail "Missing tables (found $tables_exist/4)"
        return 1
    fi
}

# Test 1: Python environment and imports
test_python_environment() {
    print_test "Python environment and module imports"
    
    if python3 -c "
import sys
sys.path.insert(0, 'server/scripts')

try:
    from extraction import extract_data_auto
    from field_mapper import map_and_filter_row  
    from normalization import normalize_data
    from persistence import persist_data
    from utils import get_db_connection
    print('✅ All required modules imported successfully')
except ImportError as e:
    print(f'❌ Import error: {e}')
    exit(1)
"; then
        print_pass "Python environment OK"
    else
        print_fail "Python import issues"
        return 1
    fi
}

# Test 2: Layer 1 - Data Extraction
test_extraction_layer() {
    print_test "Layer 1: Data Extraction"
    
    python3 << EOF
import sys
sys.path.insert(0, 'server/scripts')

from extraction import extract_data_auto

try:
    data = extract_data_auto('$TEST_FILE')
    print(f'✅ Extracted {len(data)} rows')
    
    if len(data) >= $EXPECTED_ROWS:
        print('✅ Row count matches expectation')
    else:
        print(f'❌ Expected at least $EXPECTED_ROWS rows, got {len(data)}')
        exit(1)
    
    # Check required fields
    required_fields = ['line_item', 'period_label', 'value', 'value_type']
    sample_row = data[0]
    
    for field in required_fields:
        if field in sample_row and sample_row[field] is not None:
            print(f'✅ Field "{field}": {sample_row[field]}')
        else:
            print(f'❌ Missing or null field: {field}')
            exit(1)
            
    print('✅ EXTRACTION LAYER: PASSED')
    
except Exception as e:
    print(f'❌ Extraction failed: {e}')
    exit(1)
EOF
    
    if [[ $? -eq 0 ]]; then
        print_pass "Extraction layer working"
    else
        print_fail "Extraction layer failed"
        return 1
    fi
}

# Test 3: Layer 2 - Field Mapping
test_field_mapping_layer() {
    print_test "Layer 2: Field Mapping"
    
    python3 << EOF
import sys
sys.path.insert(0, 'server/scripts')

from extraction import extract_data_auto
from field_mapper import map_and_filter_row

try:
    # Get raw data
    raw_data = extract_data_auto('$TEST_FILE')
    print(f'✅ Got {len(raw_data)} raw rows')
    
    # Test field mapping
    mapped_rows = []
    for i, row in enumerate(raw_data):
        try:
            mapped_row = map_and_filter_row(row)
            mapped_rows.append(mapped_row)
            print(f'✅ Row {i+1} mapped: {mapped_row.get("line_item", "unknown")} = {mapped_row.get("value", "N/A")}')
        except Exception as e:
            print(f'❌ Row {i+1} mapping failed: {e}')
            exit(1)
    
    if len(mapped_rows) == len(raw_data):
        print(f'✅ All {len(mapped_rows)} rows mapped successfully')
        print('✅ FIELD MAPPING LAYER: PASSED')
    else:
        print(f'❌ Mapping failed: {len(mapped_rows)}/{len(raw_data)} rows')
        exit(1)
        
except Exception as e:
    print(f'❌ Field mapping failed: {e}')
    exit(1)
EOF

    if [[ $? -eq 0 ]]; then
        print_pass "Field mapping layer working"
    else
        print_fail "Field mapping layer failed"
        return 1
    fi
}

# Test 4: Layer 3 - Normalization
test_normalization_layer() {
    print_test "Layer 3: Normalization"
    
    python3 << EOF
import sys
sys.path.insert(0, 'server/scripts')

from extraction import extract_data_auto
from field_mapper import map_and_filter_row
from normalization import normalize_data

try:
    # Get mapped data
    raw_data = extract_data_auto('$TEST_FILE')
    mapped_rows = []
    for row in raw_data:
        mapped_rows.append(map_and_filter_row(row))
    
    print(f'✅ Got {len(mapped_rows)} mapped rows')
    
    # Test normalization
    normalized_rows, error_count = normalize_data(mapped_rows, '$TEST_FILE')
    
    if error_count > 0:
        print(f'⚠️  {error_count} normalization errors')
    
    if len(normalized_rows) > 0:
        print(f'✅ Normalized {len(normalized_rows)} rows')
        
        # Check normalization quality
        for i, row in enumerate(normalized_rows[:3]):  # Check first 3
            period_id = row.get('period_id')
            line_item_id = row.get('line_item_id') 
            company_id = row.get('company_id')
            value = row.get('value')
            
            print(f'   Row {i+1}: company_id={company_id}, period_id={period_id}, line_item_id={line_item_id}, value={value}')
            
            if not all([period_id, line_item_id, company_id, value is not None]):
                print(f'❌ Row {i+1} missing required normalized fields')
                exit(1)
        
        print('✅ NORMALIZATION LAYER: PASSED')
    else:
        print('❌ No rows normalized successfully')
        exit(1)
        
except Exception as e:
    print(f'❌ Normalization failed: {e}')
    exit(1)
EOF

    if [[ $? -eq 0 ]]; then
        print_pass "Normalization layer working"  
    else
        print_fail "Normalization layer failed"
        return 1
    fi
}

# Test 5: Layer 4 - Database Persistence
test_persistence_layer() {
    print_test "Layer 4: Database Persistence"
    
    # Clear any existing test data
    psql "$DATABASE_URL" -c "DELETE FROM financial_metrics WHERE source_file = 'test_minimal.csv';" > /dev/null
    
    python3 << EOF
import sys
sys.path.insert(0, 'server/scripts')

from extraction import extract_data_auto
from field_mapper import map_and_filter_row
from normalization import normalize_data
from persistence import persist_data

try:
    # Get normalized data
    raw_data = extract_data_auto('$TEST_FILE')
    mapped_rows = [map_and_filter_row(row) for row in raw_data]
    normalized_rows, error_count = normalize_data(mapped_rows, '$TEST_FILE')
    
    print(f'✅ Ready to persist {len(normalized_rows)} rows')
    
    # Test persistence
    result = persist_data(normalized_rows)
    
    print(f'✅ Persistence result:')
    print(f'   Inserted: {result["inserted"]}')
    print(f'   Skipped: {result["skipped"]}') 
    print(f'   Errors: {result["errors"]}')
    
    if result["inserted"] >= $EXPECTED_ROWS:
        print('✅ PERSISTENCE LAYER: PASSED')
    else:
        print(f'❌ Expected to insert {$EXPECTED_ROWS} rows, only inserted {result["inserted"]}')
        if result.get("error_details"):
            print('Error details:', result["error_details"][:3])
        exit(1)
        
except Exception as e:
    print(f'❌ Persistence failed: {e}')
    import traceback
    traceback.print_exc()
    exit(1)
EOF

    if [[ $? -eq 0 ]]; then
        print_pass "Persistence layer working"
    else
        print_fail "Persistence layer failed"
        return 1
    fi
}

# Test 6: Database Verification
test_database_verification() {
    print_test "Database verification"
    
    local actual_count=$(psql "$DATABASE_URL" -t -c "
        SELECT COUNT(*) 
        FROM financial_metrics 
        WHERE source_file = 'test_minimal.csv'
    " | tr -d ' ')
    
    if [[ "$actual_count" -ge "$EXPECTED_ROWS" ]]; then
        print_pass "Database contains $actual_count rows (expected >= $EXPECTED_ROWS)"
    else
        print_fail "Database contains $actual_count rows (expected >= $EXPECTED_ROWS)"
        
        # Show what's actually in the database
        echo "Database contents:"
        psql "$DATABASE_URL" -c "
            SELECT fm.value, p.period_label, li.name as line_item, fm.value_type
            FROM financial_metrics fm
            JOIN periods p ON fm.period_id = p.id  
            JOIN line_item_definitions li ON fm.line_item_id = li.id
            WHERE fm.source_file = 'test_minimal.csv'
        "
        return 1
    fi
    
    # Test specific data integrity
    local revenue_actual=$(psql "$DATABASE_URL" -t -c "
        SELECT fm.value
        FROM financial_metrics fm
        JOIN line_item_definitions li ON fm.line_item_id = li.id
        JOIN periods p ON fm.period_id = p.id
        WHERE li.name = 'Revenue' 
        AND p.period_label = '2025-02'
        AND fm.value_type = 'Actual'
        AND fm.source_file = 'test_minimal.csv'
        LIMIT 1
    " | tr -d ' ')
    
    if [[ "$revenue_actual" == "1000000" ]]; then
        print_pass "Revenue data correctly stored: $revenue_actual"
    else
        print_fail "Revenue data incorrect: expected 1000000, got '$revenue_actual'"
        return 1
    fi
}

# Test 7: End-to-end Integration Test
test_full_integration() {
    print_test "Full integration test (ingest_xlsx.py)"
    
    # Clear test data
    psql "$DATABASE_URL" -c "DELETE FROM financial_metrics WHERE source_file = 'test_minimal.csv';" > /dev/null
    
    # Run the actual ingestion script
    if python3 server/scripts/ingest_xlsx.py "$TEST_FILE" "$COMPANY_ID"; then
        print_pass "ingest_xlsx.py executed successfully"
    else
        print_fail "ingest_xlsx.py failed"
        return 1
    fi
    
    # Verify results
    local final_count=$(psql "$DATABASE_URL" -t -c "
        SELECT COUNT(*) 
        FROM financial_metrics 
        WHERE source_file = 'test_minimal.csv'
    " | tr -d ' ')
    
    if [[ "$final_count" -ge "$EXPECTED_ROWS" ]]; then
        print_pass "Full integration successful: $final_count rows inserted"
    else
        print_fail "Full integration failed: only $final_count rows inserted"
        return 1
    fi
}

# Test 8: Upload API Integration  
test_upload_api() {
    print_test "Upload API integration test"
    
    # Clear test data
    psql "$DATABASE_URL" -c "DELETE FROM financial_metrics WHERE source_file = 'test_minimal.csv';" > /dev/null
    
    # Build and start container
    print_warn "Building Docker container for API test..."
    if ! docker build -t finance-server-test -f server/Dockerfile . > /dev/null 2>&1; then
        print_fail "Docker build failed"
        return 1
    fi
    
    # Start container
    local container_name="finance-test-$$"
    docker run --rm -d \
        --env-file .env \
        -e "DATABASE_URL=${DATABASE_URL}" \
        -p 4001:4000 \
        --name "$container_name" \
        finance-server-test > /dev/null
    
    # Wait for health check
    local health_ok=false
    for i in {1..30}; do
        if curl -sf http://localhost:4001/health > /dev/null 2>&1; then
            health_ok=true
            break
        fi
        sleep 1
    done
    
    if [[ "$health_ok" == "false" ]]; then
        print_fail "API health check failed"
        docker stop "$container_name" > /dev/null 2>&1
        return 1
    fi
    
    # Test file upload
    local upload_response=$(curl -sf -w "%{http_code}" -F "file=@$TEST_FILE" "http://localhost:4001/api/upload" 2>/dev/null || echo "FAILED")
    
    # Clean up container
    docker stop "$container_name" > /dev/null 2>&1
    
    if [[ "$upload_response" =~ 200$ ]]; then
        print_pass "API upload successful"
        
        # Verify database
        local api_count=$(psql "$DATABASE_URL" -t -c "
            SELECT COUNT(*) 
            FROM financial_metrics 
            WHERE source_file = 'test_minimal.csv'
        " | tr -d ' ')
        
        if [[ "$api_count" -ge "$EXPECTED_ROWS" ]]; then
            print_pass "API integration complete: $api_count rows in database"
        else
            print_fail "API integration failed: only $api_count rows in database"
            return 1
        fi
    else
        print_fail "API upload failed: $upload_response"
        return 1
    fi
}

# Main test execution
main() {
    echo "Starting comprehensive ingestion testing..."
    echo "Database: ${DATABASE_URL:0:50}..."
    echo ""
    
    # Create test data
    create_test_data
    
    # Run tests in sequence
    local tests=(
        "test_database_connection"
        "test_python_environment"  
        "test_extraction_layer"
        "test_field_mapping_layer"
        "test_normalization_layer"
        "test_persistence_layer"
        "test_database_verification"
        "test_full_integration"
        "test_upload_api"
    )
    
    local passed=0
    local failed=0
    local failed_tests=()
    
    for test in "${tests[@]}"; do
        echo ""
        if $test; then
            ((passed++))
        else
            ((failed++))
            failed_tests+=("$test")
        fi
    done
    
    # Summary
    echo ""
    echo "=========================================="
    echo "🔬 COMPREHENSIVE TESTING RESULTS"
    echo "=========================================="
    echo -e "${GREEN}✅ Passed: $passed${NC}"
    
    if [[ $failed -gt 0 ]]; then
        echo -e "${RED}❌ Failed: $failed${NC}"
        echo ""
        echo "Failed tests:"
        for test in "${failed_tests[@]}"; do
            echo -e "${RED}  - $test${NC}"
        done
        echo ""
        echo "🔧 Fix the failed tests in order, then re-run"
        exit 1
    else
        echo ""
        echo "🎉 ALL TESTS PASSED! 🎉"
        echo "✅ Three-layer ingestion pipeline working correctly"
        echo "✅ Database persistence confirmed" 
        echo "✅ API integration functional"
        echo ""
        echo "🚢 Ready for Railway deployment!"
        exit 0
    fi
    
    # Cleanup
    rm -f "$TEST_FILE"
}

# Run main function
main "$@"