#!/bin/bash
# Database migration script for Cloud Build
# This script runs migrations during deployment

set -e

echo "Running database migrations..."

# Get database credentials from secrets
DB_PASSWORD=$(gcloud secrets versions access latest --secret=db-password-staging --format="value" 2>/dev/null || echo "")
DB_CONNECTION_NAME=$(gcloud secrets versions access latest --secret=db-connection-name-staging --format="value" 2>/dev/null || echo "")
DB_NAME=loist_mvp_staging

if [ -z "$DB_PASSWORD" ] || [ -z "$DB_CONNECTION_NAME" ]; then
    echo "Database secrets not available, skipping migrations"
    exit 0
fi

# Set environment variables for the migration script
export DB_NAME="$DB_NAME"
export DB_USER="music_library_user"
export DB_PASSWORD="$DB_PASSWORD"
export DB_CONNECTION_NAME="$DB_CONNECTION_NAME"

# Run migrations using the existing migration script
python3 database/migrate.py --action=up --database-url="postgresql://music_library_user:$DB_PASSWORD@/loist_mvp_staging?host=/cloudsql/$DB_CONNECTION_NAME"
