#!/bin/bash
# Database migration script for Cloud Build
# This script runs migrations during deployment

set -e

echo "Running database migrations..."

# Use Cloud Build service account to access secrets
DB_PASSWORD=$(gcloud secrets versions access latest --secret=db-password-staging --format="value" 2>/dev/null || echo "")
DB_CONNECTION_NAME=$(gcloud secrets versions access latest --secret=db-connection-name-staging --format="value" 2>/dev/null || echo "")
DB_NAME=$(gcloud secrets versions access latest --secret=db-name-staging --format="value" 2>/dev/null || echo "loist_mvp_staging")

if [ -z "$DB_PASSWORD" ] || [ -z "$DB_CONNECTION_NAME" ]; then
    echo "Database secrets not available, skipping migrations"
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
