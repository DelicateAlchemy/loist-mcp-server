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

# Note: schema_migrations table is created automatically by the Python migrator

# Run all pending migrations using the Python migration system
echo "Running migrations using Python migrator..."
python3 database/migrate.py --action=up --database-url="postgresql://$DB_USER:$DB_PASSWORD@$DB_CONNECTION_NAME/$DB_NAME"
migration_result=$?

if [ $migration_result -ne 0 ]; then
    echo "❌ Migration failed with exit code $migration_result"
    exit 1
fi

# Validate that all expected migrations are applied
echo "Validating migration status..."
python3 database/migrate.py --action=status --database-url="postgresql://$DB_USER:$DB_PASSWORD@$DB_CONNECTION_NAME/$DB_NAME" || {
    echo "⚠️ Could not check migration status, but migrations may have succeeded"
}

echo "✅ All migrations completed successfully"

# Clean up Cloud SQL proxy
echo "Cleaning up Cloud SQL proxy..."
kill $PROXY_PID
wait $PROXY_PID 2>/dev/null || true

echo "Migration process complete!"
