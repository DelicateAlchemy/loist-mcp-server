#!/bin/bash
# Database migration script for Cloud Build
# This script runs migrations during deployment

set -e

echo "Running database migrations..."

# Use Cloud Build service account to access secrets
echo "Authenticating with service account..."
gcloud auth list
echo "Testing secret access..."

DB_PASSWORD=$(gcloud secrets versions access latest --secret=db-password-staging --format="value" 2>&1 || echo "")
DB_CONNECTION_NAME=$(gcloud secrets versions access latest --secret=db-connection-name-staging --format="value" 2>&1 || echo "")
DB_NAME=loist_mvp_staging

echo "DB_PASSWORD length: ${#DB_PASSWORD}"
echo "DB_CONNECTION_NAME: $DB_CONNECTION_NAME"

if [ -z "$DB_PASSWORD" ] || [ -z "$DB_CONNECTION_NAME" ] || [[ "$DB_PASSWORD" == *"ERROR"* ]]; then
    echo "Database secrets not available or access failed, skipping migrations"
    echo "DB_PASSWORD: '$DB_PASSWORD'"
    echo "DB_CONNECTION_NAME: '$DB_CONNECTION_NAME'"
    exit 0
fi

echo "Connecting to database: $DB_CONNECTION_NAME"

# Use psql directly via Cloud SQL proxy (simpler than Python script)
PGPASSWORD="$DB_PASSWORD" psql \
  -h "/cloudsql/$DB_CONNECTION_NAME" \
  -U music_library_user \
  -d loist_mvp_staging \
  -f database/migrations/001_initial_schema.sql \
  -v ON_ERROR_STOP=1 \
  --quiet \
  2>&1 || {
    # If it fails, check if the table already exists
    echo "Migration failed, checking if schema already exists..."
    PGPASSWORD="$DB_PASSWORD" psql \
      -h "/cloudsql/$DB_CONNECTION_NAME" \
      -U music_library_user \
      -d loist_mvp_staging \
      -c "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'audio_tracks');" \
      --quiet \
      2>/dev/null | grep -q "t" && {
        echo "Database schema already exists, skipping migration"
        exit 0
      }
    # If we get here, there's a real error
    echo "Migration failed and schema doesn't exist"
    exit 1
  }

echo "Migration completed successfully!"
