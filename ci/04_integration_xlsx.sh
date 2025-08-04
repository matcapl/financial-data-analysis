#!/usr/bin/env bash
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL must be set}"

echo "04 | Running XLSX integration test..."

# Ensure line-items exist
psql "$DATABASE_URL" <<SQL
INSERT INTO line_item_definitions(name)
 SELECT 'Revenue'       WHERE NOT EXISTS(SELECT 1 FROM line_item_definitions WHERE name='Revenue');
INSERT INTO line_item_definitions(name)
 SELECT 'Gross Profit'  WHERE NOT EXISTS(SELECT 1 FROM line_item_definitions WHERE name='Gross Profit');
INSERT INTO line_item_definitions(name)
 SELECT 'EBITDA'        WHERE NOT EXISTS(SELECT 1 FROM line_item_definitions WHERE name='EBITDA');
SQL

# Start server
docker rm -f finance-server_ci 2>/dev/null || true
docker build -t finance-server -f server/Dockerfile . >/dev/null
docker run -d --rm --env-file .env -p 4000:4000 --name finance-server_ci finance-server
sleep 5

# Upload and verify
curl -fs -F "file=@data/test.xlsx" http://localhost:4000/api/upload
ACTUAL_COUNT=$(psql "$DATABASE_URL" -t -c "
  SELECT COUNT(*)
    FROM financial_metrics fm
    JOIN periods p ON fm.period_id=p.id
   WHERE p.period_label='Feb 2025'
     AND p.period_type='Monthly';
" | tr -d '[:space:]')

EXPECTED_COUNT=4
if [[ "$ACTUAL_COUNT" -ne $EXPECTED_COUNT ]]; then
  echo "04 | XLSX test FAILED: expected $EXPECTED_COUNT rows, got $ACTUAL_COUNT" >&2
  docker logs finance-server_ci >&2
  docker stop finance-server_ci
  exit 1
fi

echo "04 | XLSX test passed: rows=$ACTUAL_COUNT"
docker stop finance-server_ci
