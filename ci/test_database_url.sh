#!/usr/bin/env bash
set -euo pipefail

LOG() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"; }

LOG "Starting database URL tests"
LOG "Current directory: $(pwd)"

ENV_FILE="${ENV_FILE:-.env}"
if [[ -f "$ENV_FILE" ]]; then
  LOG "Loading environment from $ENV_FILE"
  source "$ENV_FILE"
  LOG "Environment loaded"
else
  LOG "❌ ENV_FILE not found: $ENV_FILE"
  exit 1
fi

run_tests() {
  local name=$1
  local url=$2

  # Extract host and db name
  local info
  info=$(echo "$url" | sed -E 's#.*://[^@]+@([^:/]+):?[0-9]*/([^?]+).*#\1/\2#')
  LOG "=== Testing $name at $info ==="

  LOG "→ Connectivity test"
  if psql "$url" -c "SELECT current_database(), inet_client_addr();" >/dev/null 2>&1; then
    LOG "✅ $name connection OK"
  else
    LOG "❌ $name connection FAILED"
  fi

  LOG "→ List tables"
  if tables=$(psql "$url" -Atc "SELECT tablename FROM pg_tables WHERE schemaname='public';"); then
    LOG "✅ $name tables: $tables"
  else
    LOG "❌ $name table list FAILED"
  fi

  for tbl in companies line_item_definitions periods; do
    LOG "→ Row count in $tbl"
    if count=$(psql "$url" -Atc "SELECT COUNT(*) FROM public.$tbl;"); then
      LOG "    $tbl: $count rows"
    else
      LOG "    ❌ count for $tbl FAILED"
    fi
  done
}

# 1. Local DB first
if [[ -n "${LOCAL_DATABASE_URL:-}" ]]; then
  run_tests "LocalDB" "$LOCAL_DATABASE_URL"
else
  LOG "LOCAL_DATABASE_URL not set; skipping local DB tests"
fi

# 2. External NeonDB
if [[ -n "${DATABASE_URL:-}" ]]; then
  NEON_URL="${DATABASE_URL}"
  run_tests "NeonDB" "$NEON_URL"
else
  LOG "❌ DATABASE_URL is not set"
  exit 1
fi

LOG "Database URL tests complete"
