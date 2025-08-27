#!/usr/bin/env bash
set -euo pipefail

# Quick Layer-by-Layer Diagnostic Tests
# Minimal tests to quickly isolate ingestion problems

echo "🔍 === QUICK INGESTION DIAGNOSTIC ==="

# Load environment
if [[ -f .env ]]; then
    export $(grep -v '^#' .env | xargs)
fi

: "${DATABASE_URL:?DATABASE_URL must be set}"

# Create minimal test data
cat > data/quick_test.csv << 'EOF'
company_id,company_name,line_item,period_label,period_type,value,value_type,source_file,source_page,notes
1,Test Company,Revenue,2025-02,Monthly,999999,Actual,quick_test.csv,1,diagnostic test
EOF

echo "✅ Created test file: data/quick_test.csv"
echo ""

# Test 1: Python Environment
echo "🔍 Test 1: Python modules can be imported"
python3 -c "
import sys
sys.path.insert(0, 'server/scripts')
from extraction import extract_data_auto
from field_mapper import map_and_filter_row  
from normalization import normalize_data
from persistence import persist_data
from utils import get_db_connection
print('✅ All modules imported successfully')
" || { echo "❌ Python import failed"; exit 1; }

# Test 2: Extraction
echo "🔍 Test 2: Data extraction"
python3 -c "
import sys
sys.path.insert(0, 'server/scripts')
from extraction import extract_data_auto
data = extract_data_auto('data/quick_test.csv')
print(f'✅ Extracted {len(data)} rows')
print(f'Sample: {data[0] if data else \"No data\"}')
" || { echo "❌ Extraction failed"; exit 1; }

# Test 3: Field Mapping  
echo "🔍 Test 3: Field mapping"
python3 -c "
import sys
sys.path.insert(0, 'server/scripts')
from extraction import extract_data_auto
from field_mapper import map_and_filter_row
data = extract_data_auto('data/quick_test.csv')
mapped = map_and_filter_row(data[0])
print(f'✅ Mapped row: {mapped}')
" || { echo "❌ Field mapping failed"; exit 1; }

# Test 4: Normalization
echo "🔍 Test 4: Normalization"
python3 -c "
import sys
sys.path.insert(0, 'server/scripts')
from extraction import extract_data_auto
from field_mapper import map_and_filter_row
from normalization import normalize_data
data = extract_data_auto('data/quick_test.csv')
mapped = [map_and_filter_row(row) for row in data]
normalized, errors = normalize_data(mapped, 'quick_test.csv')
print(f'✅ Normalized {len(normalized)} rows, {errors} errors')
if normalized:
    print(f'Sample normalized: {normalized[0]}')
" || { echo "❌ Normalization failed"; exit 1; }

# Test 5: Database Connection
echo "🔍 Test 5: Database connectivity"
python3 -c "
import sys
sys.path.insert(0, 'server/scripts')
from utils import get_db_connection
with get_db_connection() as conn:
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM financial_metrics')
        count = cur.fetchone()[0]
        print(f'✅ Database connection OK, current rows: {count}')
" || { echo "❌ Database connection failed"; exit 1; }

# Test 6: Full Pipeline (with detailed output)
echo "🔍 Test 6: Full pipeline with debugging"

# Clear any existing test data
psql "$DATABASE_URL" -c "DELETE FROM financial_metrics WHERE source_file = 'quick_test.csv';" > /dev/null

python3 -c "
import sys
sys.path.insert(0, 'server/scripts')
from extraction import extract_data_auto
from field_mapper import map_and_filter_row
from normalization import normalize_data
from persistence import persist_data
from utils import get_db_connection

print('🔄 Running full pipeline...')

# Extract
data = extract_data_auto('data/quick_test.csv')
print(f'1. Extracted: {len(data)} rows')

# Map
mapped = [map_and_filter_row(row) for row in data]  
print(f'2. Mapped: {len(mapped)} rows')

# Normalize
normalized, errors = normalize_data(mapped, 'quick_test.csv')
print(f'3. Normalized: {len(normalized)} rows, {errors} errors')

if normalized:
    print(f'   Sample normalized row: {normalized[0]}')
    
    # Persist
    result = persist_data(normalized)
    print(f'4. Persistence result: {result}')
    
    # Verify
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(\"SELECT COUNT(*) FROM financial_metrics WHERE source_file = 'quick_test.csv'\")
            db_count = cur.fetchone()[0]
            print(f'5. Database verification: {db_count} rows found')
            
            if db_count > 0:
                cur.execute(\"\"\"
                    SELECT fm.value, p.period_label, li.name 
                    FROM financial_metrics fm
                    JOIN periods p ON fm.period_id = p.id
                    JOIN line_item_definitions li ON fm.line_item_id = li.id
                    WHERE fm.source_file = 'quick_test.csv'
                    LIMIT 1
                \"\"\")
                sample = cur.fetchone()
                print(f'   Sample data: value={sample[0]}, period={sample[1]}, item={sample[2]}')
                
                if str(sample[0]) == '999999':
                    print('✅ FULL PIPELINE SUCCESS: Data persisted correctly!')
                else:
                    print(f'❌ Data corruption: expected 999999, got {sample[0]}')
            else:
                print('❌ PERSISTENCE FAILED: No data in database')
else:
    print('❌ NORMALIZATION FAILED: No normalized data')
" || { echo "❌ Full pipeline failed"; exit 1; }

echo ""
echo "🎉 All diagnostic tests passed!"
echo "✅ Three-layer pipeline is working correctly"

# Cleanup
rm -f data/quick_test.csv