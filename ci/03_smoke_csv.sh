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

# Set trap for cleanup on exit
trap cleanup EXIT

# Initial cleanup
cleanup

# Create smoke test data if it doesn't exist
if [[ ! -f "$SMOKE_FILE" ]]; then
    echo "Creating smoke test CSV..."
    mkdir -p data
    cat > "$SMOKE_FILE" << 'EOF'
line_item,period_label,period_type,value,source_file,source_page,notes
Revenue,Feb 2025,Monthly,2390873,smoke.csv,1,smoke test
EOF
fi

# Build and start API container
echo "Building Docker image..."
docker build -t finance-server -f server/Dockerfile .

echo "Starting API container..."
docker run --rm --env-file .env -d -p "$PORT:$PORT" --name "$CONTAINER_NAME" finance-server

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
UPLOAD_RESPONSE=$(curl -sf -F "file=@$SMOKE_FILE" "http://localhost:$PORT/api/upload")

if ! echo "$UPLOAD_RESPONSE" | grep -q '"message":"File processed successfully"'; then
    echo "❌ Upload failed:"
    echo "$UPLOAD_RESPONSE"
    exit 1
fi

echo "Upload successful!"

# Verify data in database
echo "Verifying data ingestion..."
ACTUAL=$(psql "$DATABASE_URL" -t -c "
    SELECT fm.value 
    FROM financial_metrics fm 
    JOIN line_item_definitions li ON fm.line_item_id = li.id 
    JOIN periods p ON fm.period_id = p.id 
    WHERE li.name = 'Revenue' 
    AND p.period_label = 'Feb 2025'
    LIMIT 1;
" | tr -d '[:space:]')

if [[ "$ACTUAL" != "$EXPECTED_REVENUE" ]]; then
    echo "❌ Data verification failed: expected $EXPECTED_REVENUE, got $ACTUAL"
    exit 1
fi

echo "✅ 03 | Smoke CSV test passed: revenue=$ACTUAL"
exit 0