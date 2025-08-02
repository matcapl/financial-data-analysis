#!/usr/bin/env bash
set -euo pipefail

# Robust Local Database Reset Script
# Automatically loads .env and validates environment

# Function to load .env file
load_env() {
    if [[ -f .env ]]; then
        echo "Loading environment from .env..."
        set -a  # automatically export all variables
        source .env
        set +a  # stop automatically exporting
    else
        echo "Warning: .env file not found"
    fi
}

# Function to extract database name from URL
extract_db_name() {
    local db_url="$1"
    
    # Handle various PostgreSQL URL formats
    if [[ "$db_url" =~ postgresql://[^/]+/([^?]+) ]]; then
        echo "${BASH_REMATCH[1]}"
    elif [[ "$db_url" =~ postgres://[^/]+/([^?]+) ]]; then
        echo "${BASH_REMATCH[1]}"
    else
        echo ""
    fi
}

# Function to extract base connection URL (without database name)
extract_base_url() {
    local db_url="$1"
    
    if [[ "$db_url" =~ (postgresql://[^/]+)/[^?]+ ]]; then
        echo "${BASH_REMATCH[1]}/postgres"
    elif [[ "$db_url" =~ (postgres://[^/]+)/[^?]+ ]]; then
        echo "${BASH_REMATCH[1]}/postgres"
    else
        echo "postgresql://localhost:5432/postgres"
    fi
}

# Main execution
main() {
    echo "=== Local Database Reset ==="
    
    # Load environment variables
    load_env
    
    # Validate LOCAL_DATABASE_URL is set
    if [[ -z "${LOCAL_DATABASE_URL:-}" ]]; then
        echo "ERROR: LOCAL_DATABASE_URL not set in environment or .env file"
        echo "Expected format: postgresql://user:password@host:port/database"
        exit 1
    fi
    
    echo "Using LOCAL_DATABASE_URL: ${LOCAL_DATABASE_URL}"
    
    # Extract database name and base URL
    DB_NAME=$(extract_db_name "$LOCAL_DATABASE_URL")
    BASE_URL=$(extract_base_url "$LOCAL_DATABASE_URL")
    
    if [[ -z "$DB_NAME" ]]; then
        echo "ERROR: Could not extract database name from LOCAL_DATABASE_URL"
        echo "URL format should be: postgresql://user:password@host:port/database"
        exit 1
    fi
    
    echo "Database name extracted: $DB_NAME"
    echo "Base connection URL: $BASE_URL"
    
    # Test connectivity to PostgreSQL server
    echo "Testing PostgreSQL server connectivity..."
    if ! psql "$BASE_URL" -c "SELECT 1;" >/dev/null 2>&1; then
        echo "ERROR: Cannot connect to PostgreSQL server"
        echo "Please ensure:"
        echo "  1. PostgreSQL is running"
        echo "  2. Credentials in LOCAL_DATABASE_URL are correct"
        echo "  3. Network connectivity is available"
        exit 1
    fi
    
    echo "✓ PostgreSQL server connection successful"
    
    # Drop and recreate database
    echo "Dropping database: $DB_NAME"
    psql "$BASE_URL" -c "DROP DATABASE IF EXISTS \"$DB_NAME\";" || {
        echo "ERROR: Failed to drop database $DB_NAME"
        exit 1
    }
    
    echo "Creating database: $DB_NAME"
    psql "$BASE_URL" -c "CREATE DATABASE \"$DB_NAME\";" || {
        echo "ERROR: Failed to create database $DB_NAME"
        exit 1
    }
    
    # Verify the new database is accessible
    echo "Verifying new database accessibility..."
    if ! psql "$LOCAL_DATABASE_URL" -c "SELECT 1;" >/dev/null 2>&1; then
        echo "ERROR: Cannot connect to newly created database"
        exit 1
    fi
    
    echo "✅ Local database reset completed successfully"
    echo "Database '$DB_NAME' is ready for migrations"
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
