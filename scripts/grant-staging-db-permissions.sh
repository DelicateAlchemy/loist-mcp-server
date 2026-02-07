#!/bin/bash
# Grant database permissions to music_library_user for loist_mvp_staging database

set -e

PROJECT_ID="loist-music-library"
INSTANCE_ID="loist-music-library-db"
STAGING_DB_NAME="loist_mvp_staging"
APP_USER="music_library_user"

echo "========================================="
echo " Granting Database Permissions"
echo "========================================="
echo "Database: $STAGING_DB_NAME"
echo "User: $APP_USER"
echo ""

# Get the database password from secrets
echo "Getting database password from secrets..."
DB_PASSWORD=$(gcloud secrets versions access latest --secret=db-password --project=$PROJECT_ID)

# Create a temporary SQL file
SQL_FILE="/tmp/grant_permissions.sql"
cat > "$SQL_FILE" << SQL_EOF
-- Grant database-level permissions
GRANT ALL PRIVILEGES ON DATABASE $STAGING_DB_NAME TO $APP_USER;

-- Connect to the database and grant schema permissions  
\c $STAGING_DB_NAME;

-- Grant all existing permissions
GRANT ALL ON SCHEMA public TO $APP_USER;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $APP_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $APP_USER;

-- Grant future permissions
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $APP_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $APP_USER;
SQL_EOF

echo "Connecting to Cloud SQL instance and executing permissions..."

# Use gcloud sql connect to run the SQL
gcloud sql connect "$INSTANCE_ID" \
  --project="$PROJECT_ID" \
  --user=postgres \
  --quiet < "$SQL_FILE"

# Clean up
rm -f "$SQL_FILE"

echo ""
echo "========================================="
echo " Permissions Granted Successfully"
echo "========================================="
echo "User '$APP_USER' now has full access to '$STAGING_DB_NAME'"
