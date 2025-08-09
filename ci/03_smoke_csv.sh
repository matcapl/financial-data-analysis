#!/usr/bin/env bash
set -euo pipefail

echo "03 | Running Smoke CSV test..."

# Stop/remove any prior container with this name
docker stop finance-server_ci 2>/dev/null || true
docker rm finance-server_ci 2>/dev/null || true

ENV_FILE="${ENV_FILE:-.env}"
if [ -f "$ENV_FILE" ]; then
  set -a
  source "$ENV_FILE"
  set +a
fi
: "${DATABASE_URL:?DATABASE_URL must be set}"

# Prepare unique smoke.csv
SUFFIX="$(date +%s)$((RANDOM%10000))"
cat > data/smoke.csv <<EOF
company_id,company_name,line_item,period_label,period_type,value,value_type,source_file,source_page,notes
1,Example_Company_E,Revenue,Feb 2025,Monthly,2390873,Actual,smoke.csv,1,smoke_test_$SUFFIX
EOF

# Ensure the line-item exists
psql "$DATABASE_URL" <<SQL
INSERT INTO line_item_definitions(name)
 SELECT 'Revenue'
  WHERE NOT EXISTS(SELECT 1 FROM line_item_definitions WHERE name='Revenue');
SQL

# Start server
docker build -t finance-server -f server/Dockerfile . >/dev/null
docker run -d --rm --env-file .env -p 4000:4000 --name finance-server_ci finance-server
sleep 5

# Upload and verify
curl -fs -F "file=@data/smoke.csv" http://localhost:4000/api/upload
ACTUAL=$(psql "$DATABASE_URL" -t -c "
  SELECT to_char(value,'FM9G999G999D00')
    FROM financial_metrics fm
    JOIN line_item_definitions li ON fm.line_item_id=li.id
    JOIN periods p ON fm.period_id=p.id
   WHERE li.name='Revenue'
     AND p.period_label='Feb 2025'
     AND p.period_type='Monthly';
" | tr -d '[:space:]')

EXPECTED="2,390,873.00"
if [[ "$ACTUAL" != "$EXPECTED" ]]; then
  echo "03 | Smoke CSV test FAILED: expected $EXPECTED, got $ACTUAL" >&2
  docker logs finance-server_ci >&2
  docker stop finance-server_ci
  exit 1
fi

echo "03 | Smoke CSV test passed: revenue=$ACTUAL"
docker stop finance-server_ci
