#!/bin/bash
# Update staging secrets to use correct database name

set -e

PROJECT_ID="loist-music-library"
STAGING_DB_NAME="loist_mvp_staging"

echo "========================================="
echo " Updating Staging Database Secrets"
echo "========================================="
echo ""

echo "Updating db-name-staging secret to: $STAGING_DB_NAME"

# Update the staging database name secret
echo -n "$STAGING_DB_NAME" | gcloud secrets versions add "db-name-staging" \
    --data-file=- \
    --project="$PROJECT_ID" \
    --quiet

echo "✅ Staging database secret updated successfully"
echo ""
echo "========================================="
echo " Secrets Updated"
echo "========================================="
echo "db-name-staging: $STAGING_DB_NAME"
echo ""
echo "The staging environment will now use the correct database name."
