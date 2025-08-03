# Make this code executable: bash: chmod +x ci/smoke_test.sh

# Then Run it: bash: ./ci/smoke_test.sh

#!/usr/bin/env bash
set -euo pipefail

# If the DB is uninitialized (i.e. have run 001_reset but not 002_migrate.sh yet)
# Then run migrations first to ensure consistency
# ./ci/migrate.sh
# Mayb use automated check below to test, if unknown

# If the schema_migrations table doesn’t exist, run migrations
if ! psql "$DATABASE_URL" -tAc "SELECT 1 FROM information_schema.tables WHERE table_name='schema_migrations'" | grep -q 1; then
  echo "Schema not initialized—running migrations"
  ci/002_migrate.sh
fi

# Load .env file if present
if [[ -f .env ]]; then
    set -a
    source .env
    set +a
fi

# Load environment variables from .env
LOCAL_DB=$(grep '^LOCAL_DATABASE_URL=' .env 2>/dev/null | cut -d '=' -f2- || echo "")
EXTERNAL_DB=$(grep '^DATABASE_URL=' .env 2>/dev/null | cut -d '=' -f2- || echo "")

for DB_NAME in "LOCAL" "EXTERNAL"; do
  if [[ "$DB_NAME" == "LOCAL" ]]; then
    if [[ -z "$LOCAL_DB" ]]; then
      echo "Skipping LOCAL test: LOCAL_DATABASE_URL not found in .env"
      continue
    fi
    export DATABASE_URL="$LOCAL_DB"
  else
    if [[ -z "$EXTERNAL_DB" ]]; then
      echo "Skipping EXTERNAL test: DATABASE_URL not found in .env"
      continue
    fi
    export DATABASE_URL="$EXTERNAL_DB"
  fi

  echo "=== Testing with $DB_NAME database ==="

  # Generate a random suffix for uniqueness (macOS compatible)
  SUFFIX=$(date +%s)$(printf "%04d" $((RANDOM % 10000)))

  # Create the smoke CSV with a unique notes field
  cat > data/smoke.csv <<EOF
company_id,company_name,line_item,period_label,period_type,value,source_file,source_page,notes
1,Wilson Group,Revenue,Feb 2025,Monthly,2390873,smoke.csv,1,smoke_test_$SUFFIX
EOF

  psql "$DATABASE_URL" <<SQL
INSERT INTO line_item_definitions (name)
  SELECT 'Revenue'       WHERE NOT EXISTS (SELECT 1 FROM line_item_definitions WHERE name='Revenue');
INSERT INTO line_item_definitions (name)
  SELECT 'Gross Profit'  WHERE NOT EXISTS (SELECT 1 FROM line_item_definitions WHERE name='Gross Profit');
INSERT INTO line_item_definitions (name)
  SELECT 'EBITDA'        WHERE NOT EXISTS (SELECT 1 FROM line_item_definitions WHERE name='EBITDA');
SQL

  docker build -t finance-server -f server/Dockerfile . >/dev/null
  docker stop finance-server_ci 2>/dev/null || true
  docker run --rm --env-file .env -d -p 4000:4000 --name finance-server_ci finance-server
  sleep 5

  curl -fs -F "file=@data/smoke.csv" http://localhost:4000/api/upload

  EXPECTED="2,390,873.00"
  ACTUAL=$(psql "$DATABASE_URL" -t -c "
    SELECT to_char(value, 'FM9G999G999D00')
    FROM financial_metrics fm
     JOIN line_item_definitions li ON fm.line_item_id=li.id
     JOIN periods p ON fm.period_id=p.id
     WHERE li.name='Revenue' AND p.period_label='Feb 2025';
  " | tr -d '[:space:]')

  if [[ "$ACTUAL" != "$EXPECTED" ]]; then
    echo "Smoke test failed for $DB_NAME: expected $EXPECTED, got $ACTUAL" >&2
    docker logs finance-server_ci >&2
    docker stop finance-server_ci
    exit 1
  fi

  echo "Smoke test passed for $DB_NAME: revenue=$ACTUAL"
  docker stop finance-server_ci
done
