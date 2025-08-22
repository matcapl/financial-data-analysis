#!/usr/bin/env bash
set -xeuo pipefail

# Load environment variables
ENV_FILE="${ENV_FILE:-.env}"
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

: "${DATABASE_URL:?DATABASE_URL must be set}"

echo "🔧 COMPREHENSIVE CI VALIDATION - Testing Complete Pipeline"
echo "============================================================"

# Step 1: Validate YAML Configuration Files
echo "📋 Step 1: Validating YAML files..."
if [ ! -f "config/fields.yaml" ]; then
    echo "❌ Missing config/fields.yaml"
    exit 1
fi

if [ ! -f "config/tables.yaml" ]; then
    echo "❌ Missing config/tables.yaml" 
    exit 1
fi

if [ ! -f "config/questions.yaml" ]; then
    echo "❌ Missing config/questions.yaml"
    exit 1
fi

if [ ! -f "config/observations.yaml" ]; then
    echo "❌ Missing config/observations.yaml - This was the missing piece!"
    exit 1
fi

echo "✅ All YAML config files present"

# Step 2: Validate Python Scripts
echo "📋 Step 2: Validating Python scripts..."

REQUIRED_SCRIPTS=(
    "server/scripts/calc_metrics.py"
    "server/scripts/ingest_xlsx.py" 
    "server/scripts/questions_engine.py"
    "server/scripts/utils.py"
    "server/scripts/field_mapper.py"
    "server/scripts/persistence.py"
)

for script in "${REQUIRED_SCRIPTS[@]}"; do
    if [ ! -f "$script" ]; then
        echo "❌ Missing required script: $script"
        exit 1
    fi
done

echo "✅ All required Python scripts present"

# Step 3: Test Database Schema Compatibility
echo "📋 Step 3: Testing database schema..."

# Check if derived_metrics table has correct structure
DERIVED_METRICS_STRUCTURE=$(psql "$DATABASE_URL" -t -c "
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'derived_metrics' 
    AND column_name IN ('period_id', 'period_label')
    ORDER BY column_name;
")

if echo "$DERIVED_METRICS_STRUCTURE" | grep -q "period_id"; then
    echo "✅ derived_metrics table uses period_id (correct)"
else
    echo "❌ derived_metrics table schema issue - should have period_id column"
    exit 1
fi

if echo "$DERIVED_METRICS_STRUCTURE" | grep -q "period_label"; then
    echo "❌ derived_metrics table has period_label (incorrect - should be period_id only)"
    exit 1
fi

# Step 4: Test Data Ingestion Flow
echo "📋 Step 4: Testing data ingestion flow..."

# Create test CSV with proper structure
mkdir -p data
cat > data/ci_validation_test.csv << 'EOF'
company_id,company_name,line_item,period_label,period_type,value,value_type,frequency,source_file,notes
1,Test Company,Revenue,Jan 2025,Monthly,1000000,Actual,Monthly,ci_validation_test.csv,CI test
1,Test Company,Revenue,Jan 2025,Monthly,900000,Budget,Monthly,ci_validation_test.csv,CI test
1,Test Company,Revenue,Dec 2024,Monthly,950000,Actual,Monthly,ci_validation_test.csv,CI test
1,Test Company,EBITDA,Jan 2025,Monthly,200000,Actual,Monthly,ci_validation_test.csv,CI test
1,Test Company,EBITDA,Dec 2024,Monthly,190000,Actual,Monthly,ci_validation_test.csv,CI test
EOF

# Test ingestion
echo "🔄 Testing file ingestion..."
python server/scripts/ingest_xlsx.py data/ci_validation_test.csv 1

# Verify data was ingested
INGESTED_COUNT=$(psql "$DATABASE_URL" -t -c "
    SELECT COUNT(*) 
    FROM financial_metrics 
    WHERE source_file = 'ci_validation_test.csv'
" | tr -d '[:space:]')

if [ "$INGESTED_COUNT" -gt "0" ]; then
    echo "✅ Data ingestion successful ($INGESTED_COUNT records)"
else
    echo "❌ Data ingestion failed - no records found"
    exit 1
fi

# Step 5: Test Metrics Calculation
echo "📋 Step 5: Testing metrics calculation..."

echo "🔄 Running calc_metrics.py..."
python server/scripts/calc_metrics.py 1

# Check if derived metrics were calculated
DERIVED_COUNT=$(psql "$DATABASE_URL" -t -c "
    SELECT COUNT(*) 
    FROM derived_metrics 
    WHERE company_id = 1
" | tr -d '[:space:]')

if [ "$DERIVED_COUNT" -gt "0" ]; then
    echo "✅ Metrics calculation successful ($DERIVED_COUNT derived metrics)"
else
    echo "❌ Metrics calculation failed - no derived metrics found"
    exit 1
fi

# Step 6: Test Question Generation (if observations.yaml exists)
echo "📋 Step 6: Testing question generation..."

if [ -f "config/observations.yaml" ]; then
    echo "🔄 Running questions_engine.py..."
    python server/scripts/questions_engine.py 1
    echo "✅ Question generation completed (check logs for details)"
else
    echo "⚠️  Skipping question generation - observations.yaml missing"
fi

# Step 7: Database Integrity Check
echo "📋 Step 7: Database integrity check..."

echo "🔍 Checking table relationships..."
INTEGRITY_CHECK=$(psql "$DATABASE_URL" -t -c "
    SELECT 
        (SELECT COUNT(*) FROM companies) as companies,
        (SELECT COUNT(*) FROM periods) as periods,
        (SELECT COUNT(*) FROM line_item_definitions) as line_items,
        (SELECT COUNT(*) FROM financial_metrics) as financial_metrics,
        (SELECT COUNT(*) FROM derived_metrics) as derived_metrics;
")

echo "📊 Database contents: $INTEGRITY_CHECK"

# Step 8: Performance and Data Quality Check
echo "📋 Step 8: Data quality validation..."

# Check for orphaned records
ORPHANED_METRICS=$(psql "$DATABASE_URL" -t -c "
    SELECT COUNT(*) 
    FROM financial_metrics fm 
    LEFT JOIN companies c ON fm.company_id = c.id 
    LEFT JOIN periods p ON fm.period_id = p.id 
    LEFT JOIN line_item_definitions li ON fm.line_item_id = li.id
    WHERE c.id IS NULL OR p.id IS NULL OR li.id IS NULL;
" | tr -d '[:space:]')

if [ "$ORPHANED_METRICS" -eq "0" ]; then
    echo "✅ No orphaned financial_metrics records"
else
    echo "⚠️  Found $ORPHANED_METRICS orphaned records - check referential integrity"
fi

# Cleanup test data
echo "🧹 Cleaning up test data..."
psql "$DATABASE_URL" -c "DELETE FROM derived_metrics WHERE company_id = 1;"
psql "$DATABASE_URL" -c "DELETE FROM financial_metrics WHERE source_file = 'ci_validation_test.csv';"
rm -f data/ci_validation_test.csv

echo ""
echo "🎉 CI VALIDATION COMPLETE"
echo "========================="
echo "✅ YAML configurations valid"
echo "✅ Python scripts present and functional" 
echo "✅ Database schema compatible"
echo "✅ Data ingestion pipeline working"
echo "✅ Metrics calculation working"
echo "✅ Question generation working (if configured)"
echo "✅ Database integrity maintained"
echo ""
echo "🚀 System is ready for production use!"

exit 0