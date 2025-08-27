#!/usr/bin/env bash
set -euo pipefail

# Load env
if [[ -f .env ]]; then
  set -a; source .env; set +a
fi

# Function to drop all tables in a given database URL
drop_all() {
  local url=$1
  echo "Dropping all tables on $url"
  psql "$url" <<SQL
  DO
  \$do\$
  BEGIN
    EXECUTE (
      SELECT 'DROP TABLE IF EXISTS '
             || string_agg(quote_ident(tablename), ', ')
             || ' CASCADE'
      FROM pg_tables
      WHERE schemaname = 'public'
    );
  END
  \$do\$;
SQL
}

# Drop remote
drop_all "$DATABASE_URL"

# Drop local if set
if [[ -n "${LOCAL_DATABASE_URL:-}" ]]; then
  drop_all "$LOCAL_DATABASE_URL"
else
  echo "Warning: LOCAL_DATABASE_URL not set, skipping local drop."
fi

echo "All tables dropped on both remote and local databases."
