#!/bin/bash
# Create staging database for loist-mvp-staging

set -e

PROJECT_ID="loist-music-library"
INSTANCE_ID="loist-music-library-db"
STAGING_DB_NAME="loist_mvp_staging"
APP_USER="music_library_user"

echo "========================================="
echo " Creating Staging Database"
echo "========================================="
echo ""

# Check if database already exists
echo "Checking if staging database exists..."
DB_EXISTS=$(gcloud sql databases list \
  --instance=$INSTANCE_ID \
  --project=$PROJECT_ID \
  --format="value(name)" | grep -c "^$STAGING_DB_NAME$" || echo "0")

if [ "$DB_EXISTS" -gt 0 ]; then
    echo "✅ Staging database '$STAGING_DB_NAME' already exists"
else
    echo "Creating staging database: $STAGING_DB_NAME"

    gcloud sql databases create "$STAGING_DB_NAME" \
        --instance="$INSTANCE_ID" \
        --project="$PROJECT_ID" \
        --quiet

    echo "✅ Staging database '$STAGING_DB_NAME' created successfully"
fi

echo ""
echo "========================================="
echo " Staging Database Ready"
echo "========================================="
echo "Database: $STAGING_DB_NAME"
echo "Instance: $INSTANCE_ID"
echo "User: $APP_USER"
echo ""
echo "The staging database is now ready for migrations."
