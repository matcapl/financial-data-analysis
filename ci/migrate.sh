#!/usr/bin/env bash
set -euo pipefail

# Database Migration Runner with State Tracking
# Ensures migrations are applied exactly once and in order

# Load .env file if present
if [[ -f .env ]]; then
    set -a
    source .env
    set +a
fi

MIGRATION_TABLE="schema_migrations"

init_migration_tracking() {
    local db_url="$1"
    echo "Initializing migration tracking..."
    
    psql "$db_url" <<SQL
CREATE TABLE IF NOT EXISTS $MIGRATION_TABLE (
    id SERIAL PRIMARY KEY,
    migration_name VARCHAR(255) UNIQUE NOT NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT NOW(),
    checksum VARCHAR(64)
);
SQL
}

get_migration_checksum() {
    local file="$1"
    if [[ -f "$file" ]]; then
        shasum -a 256 "$file" | cut -d' ' -f1
    else
        echo ""
    fi
}

has_migration_been_applied() {
    local db_url="$1"
    local migration_name="$2"
    local checksum="$3"
    
    local count=$(psql "$db_url" -t -c \
        "SELECT COUNT(*) FROM $MIGRATION_TABLE WHERE migration_name = '$migration_name' AND checksum = '$checksum';" \
        | tr -d ' ')
    
    [[ "$count" -gt 0 ]]
}

apply_migration() {
    local db_url="$1"
    local migration_file="$2"
    local migration_name="$3"
    local checksum="$4"
    
    echo "Applying migration: $migration_name"
    
    # Apply the migration in a transaction
    psql "$db_url" <<SQL
BEGIN;
$(cat "$migration_file")
INSERT INTO $MIGRATION_TABLE (migration_name, checksum) VALUES ('$migration_name', '$checksum');
COMMIT;
SQL
    
    echo "✓ Migration applied: $migration_name"
}

run_migrations() {
    local db_url="$1"
    local migrations_dir="schema"
    
    init_migration_tracking "$db_url"
    
    # Define migration order
    local migrations=(
        "financial_schema.sql"
        "question_templates.sql"
    )
    
    for migration_file in "${migrations[@]}"; do
        local full_path="$migrations_dir/$migration_file"
        local checksum=$(get_migration_checksum "$full_path")
        
        if [[ -z "$checksum" ]]; then
            echo "⚠️  Migration file not found: $full_path"
            continue
        fi
        
        if has_migration_been_applied "$db_url" "$migration_file" "$checksum"; then
            echo "⏭️  Migration already applied: $migration_file"
        else
            apply_migration "$db_url" "$full_path" "$migration_file" "$checksum"
        fi
    done
    
    echo "✅ All migrations completed for: $db_url"
}

# Usage
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    for db_var in LOCAL_DATABASE_URL DATABASE_URL; do
        if [[ -n "${!db_var:-}" ]]; then
            echo "=== Migrating $db_var ==="
            run_migrations "${!db_var}"
        else
            echo "⚠️  $db_var not set, skipping"
        fi
    done
fi
