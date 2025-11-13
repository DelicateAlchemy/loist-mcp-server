#!/bin/bash
# Database migration script for post-deployment
# This script runs all migrations after deployment is complete

set -e

echo "Running database migrations..."

# Determine environment from command line argument or detect from context
ENVIRONMENT="${1:-auto}"

if [ "$ENVIRONMENT" = "production" ] || [ "$ENVIRONMENT" = "auto" ]; then
    echo "Trying production environment..."
    DB_PASSWORD=$(gcloud secrets versions access latest --secret=db-password 2>/dev/null || echo "")
    DB_CONNECTION_NAME=$(gcloud secrets versions access latest --secret=db-connection-name 2>/dev/null || echo "")
    DB_NAME=$(gcloud secrets versions access latest --secret=db-name 2>/dev/null || echo "")
fi

# If production secrets not available or staging requested, try staging
if [ -z "$DB_PASSWORD" ] || [ -z "$DB_CONNECTION_NAME" ] || [ "$ENVIRONMENT" = "staging" ]; then
    if [ "$ENVIRONMENT" = "auto" ]; then
        echo "Production secrets not available, trying staging..."
    fi
    DB_PASSWORD=$(gcloud secrets versions access latest --secret=db-password-staging 2>/dev/null || echo "")
    DB_CONNECTION_NAME=$(gcloud secrets versions access latest --secret=db-connection-name-staging 2>/dev/null || echo "")
    DB_NAME=$(gcloud secrets versions access latest --secret=db-name-staging 2>/dev/null || echo "loist_mvp_staging")
fi

if [ -z "$DB_PASSWORD" ] || [ -z "$DB_CONNECTION_NAME" ]; then
    echo "Database secrets not available:"
    echo "  DB_PASSWORD: ${DB_PASSWORD:+set}${DB_PASSWORD:-not set}"
    echo "  DB_CONNECTION_NAME: ${DB_CONNECTION_NAME:+set}${DB_CONNECTION_NAME:-not set}"
    echo "Skipping migrations"
    exit 0
fi

echo "Connecting to database: $DB_CONNECTION_NAME"

# Start Cloud SQL proxy in background
echo "Starting Cloud SQL proxy..."
./cloud_sql_proxy -instances=$DB_CONNECTION_NAME=tcp:5432 &
PROXY_PID=$!

# Wait for proxy to start
sleep 5

# Function to run migration if not already applied
run_migration_if_needed() {
    local migration_file=$1
    local migration_name=$2

    echo "Checking if $migration_name migration is needed..."

    # Extract migration number from filename (e.g., "001" from "001_initial_schema.sql")
    local migration_num=$(echo "$migration_file" | sed 's/.*\/\([0-9]\+\)_.*\.sql/\1/')

    # Check if migration has been applied by looking for the migration record
    PGPASSWORD="$DB_PASSWORD" psql \
      -h localhost \
      -p 5432 \
      -U music_library_user \
      -d "$DB_NAME" \
      -c "SELECT 1 FROM schema_migrations WHERE version = '$migration_num';" \
      --quiet \
      2>/dev/null | grep -q "1" && {
        echo "Migration $migration_num ($migration_name) already applied, skipping"
        return 0
      }

    echo "Applying migration $migration_num ($migration_name)..."

    # Run the migration
    PGPASSWORD="$DB_PASSWORD" psql \
      -h localhost \
      -p 5432 \
      -U music_library_user \
      -d "$DB_NAME" \
      -f "$migration_file" \
      -v ON_ERROR_STOP=1 \
      --quiet \
      2>&1 || {
        echo "Migration $migration_num failed"
        exit 1
      }

    # Record the migration as applied
    PGPASSWORD="$DB_PASSWORD" psql \
      -h localhost \
      -p 5432 \
      -U music_library_user \
      -d "$DB_NAME" \
      -c "INSERT INTO schema_migrations (version, name, applied_at) VALUES ('$migration_num', '$migration_name', NOW());" \
      --quiet \
      2>/dev/null || {
        echo "Warning: Failed to record migration $migration_num as applied"
      }

    echo "Migration $migration_num completed successfully"
}

# Create schema_migrations table if it doesn't exist
echo "Ensuring schema_migrations table exists..."
PGPASSWORD="$DB_PASSWORD" psql \
  -h localhost \
  -p 5432 \
  -U music_library_user \
  -d "$DB_NAME" \
  -c "
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version VARCHAR(10) PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        applied_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_schema_migrations_applied_at ON schema_migrations(applied_at DESC);
  " \
  --quiet \
  2>/dev/null || {
    echo "Warning: Could not create schema_migrations table"
  }

# Run migrations in order
run_migration_if_needed "database/migrations/001_initial_schema.sql" "initial_schema"
run_migration_if_needed "database/migrations/002_add_waveform_support.sql" "waveform_support"
run_migration_if_needed "database/migrations/002_performance_indexes.sql" "performance_indexes"

echo "All migrations completed successfully!"

# Clean up Cloud SQL proxy
echo "Cleaning up Cloud SQL proxy..."
kill $PROXY_PID
wait $PROXY_PID 2>/dev/null || true

echo "Migration process complete!"
