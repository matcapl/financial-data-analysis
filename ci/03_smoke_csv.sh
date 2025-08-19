#!/usr/bin/env bash
set -euo pipefail

# Load environment variables
if [[ -f .env ]]; then
  export $(grep -v '^#' .env | xargs)
fi

# Configuration with defaults
PORT=${PORT:-4000}
CONTAINER_NAME="finance-server_ci"
SMOKE_FILE="data/smoke.csv"
EXPECTED_REVENUE="2390873"

echo "=== 03 | Starting CSV Smoke Test ==="

# Clean up any existing containers
cleanup() {
  echo "Cleaning up containers..."
  docker stop "$CONTAINER_NAME" 2>/dev/null || true
  docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
}
trap cleanup EXIT
cleanup

# Create smoke test data if it doesn't exist
if [[ ! -f "$SMOKE_FILE" ]]; then
  echo "Creating smoke test CSV..."
  mkdir -p data
  cat > "$SMOKE_FILE" << 'EOF'
company_id,company_name,line_item,period_label,period_type,value,value_type,source_file,source_page,notes
10001,Example_Company_1,Revenue,Feb 2025,Monthly,2390873,Actual,smoke.csv,1,smoke test
10001,Example_Company_1,Revenue,Feb 2025,Monthly,2000000,Budget,smoke.csv,1,smoke test
10001,Example_Company_1,EBITDA,Feb 2025,Monthly,239087,Actual,smoke.csv,1,smoke test
10001,Example_Company_1,EBITDA,Feb 2025,Monthly,300000,Budget,smoke.csv,1,smoke test
EOF
fi

# Ensure blob token is set
if [[ -z "${VERCEL_BLOB_TOKEN:-}" ]]; then
  echo "❌ ERROR: VERCEL_BLOB_TOKEN is not set in CI environment"
  exit 1
fi
echo "✅ CI has VERCEL_BLOB_TOKEN"

# Build the Docker image
echo "Building Docker image..."
docker build -t finance-server -f server/Dockerfile .

# Start the API container in detached mode
echo "Starting API container..."
docker run --rm -d \
  --env-file .env \
  -e VERCEL_BLOB_TOKEN \
  -v "$(pwd)/.env":/app/.env \
  -p "$PORT:$PORT" \
  --name "$CONTAINER_NAME" \
  finance-server

# Wait for health check
echo "Waiting for API to be ready..."
for i in {1..30}; do
  if curl -sf "http://localhost:$PORT/health" | grep -q '"status":"ok"'; then
    echo "API is ready!"
    break
  fi
  if [[ $i -eq 30 ]]; then
    echo "❌ API failed to start within 30 seconds"
    docker logs "$CONTAINER_NAME"
    exit 1
  fi
  sleep 1
done

# Upload smoke test file
echo "Uploading smoke test CSV..."
UPLOAD_RESPONSE=$(curl -sf -F "file=@$SMOKE_FILE" "http://localhost:$PORT/api/upload" 2>&1)
echo "Upload response: $UPLOAD_RESPONSE"

# After the upload, show more detailed logs
echo "=== Detailed Container Logs ==="
docker logs "$CONTAINER_NAME" 2>&1 | grep -A 20 -B 5 "ingestion\|error\|failed"

# Check for pipeline success
if ! echo "$UPLOAD_RESPONSE" | grep -q 'File processed successfully'; then
  echo "❌ Upload failed:"
  echo "$UPLOAD_RESPONSE"
  echo "Container logs:"
  docker logs --tail 100 "$CONTAINER_NAME"
  exit 1
fi

# Check blobUrl is non-null
if echo "$UPLOAD_RESPONSE" | grep -q '"blobUrl":null'; then
  echo "❌ Blob upload failed: blobUrl is null"
  exit 1
fi

echo "✅ Upload and blob storage succeeded"

# Replace the current verification section with this debug version:
echo "Verifying data ingestion..."

# First, let's see what's actually in the database
echo "=== Database Debug Info ==="
psql "$DATABASE_URL" -c "SELECT COUNT(*) as total_metrics FROM financial_metrics;"
psql "$DATABASE_URL" -c "SELECT COUNT(*) as total_line_items FROM line_item_definitions;"
psql "$DATABASE_URL" -c "SELECT COUNT(*) as total_periods FROM periods;"
psql "$DATABASE_URL" -c "SELECT COUNT(*) as total_companies FROM companies;"

echo "=== Line Items ==="
psql "$DATABASE_URL" -c "SELECT id, name FROM line_item_definitions;"

echo "=== Periods ==="
psql "$DATABASE_URL" -c "SELECT id, period_label FROM periods;"

echo "=== Financial Metrics ==="
psql "$DATABASE_URL" -c "SELECT * FROM financial_metrics LIMIT 5;"

# Try a broader search for Revenue
ACTUAL=$(psql "$DATABASE_URL" -t -c "
  SELECT fm.value
  FROM financial_metrics fm
  JOIN line_item_definitions li ON fm.line_item_id = li.id
  JOIN periods p ON fm.period_id = p.id
  WHERE li.name ILIKE '%revenue%'
  LIMIT 1;
" | tr -d '[:space:]')

echo "Found revenue value: '$ACTUAL'"

if [[ -z "$ACTUAL" ]]; then
  echo "❌ No revenue data found in database"
  exit 1
fi

if [[ "$ACTUAL" != "$EXPECTED_REVENUE" ]]; then
  echo "❌ Data verification failed: expected $EXPECTED_REVENUE, got $ACTUAL"
  exit 1
fi

echo "✅ 03 | Smoke CSV test passed: revenue=$ACTUAL"
exit 0
