#!/usr/bin/env bash
set -xeuo pipefail

ENV_FILE="${ENV_FILE:-.env}"
if [ -f "$ENV_FILE" ]; then
  set -a
  source "$ENV_FILE"
  set +a
fi
: "${DATABASE_URL:?DATABASE_URL must be set}"

echo "01 | Dropping all tables..."
psql "$DATABASE_URL" <<'SQL'
DO $$
DECLARE
    tbl RECORD;
BEGIN
    FOR tbl IN
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
    LOOP
        EXECUTE format('DROP TABLE IF EXISTS %I.%I CASCADE',
                       tbl.table_schema, tbl.table_name);
    END LOOP;
END$$;
SQL
echo "01 | All tables dropped."
