#!/bin/bash
# Grant logging permissions to the compute service account for Cloud Build

set -e

PROJECT_ID="loist-music-library"
COMPUTE_SA_EMAIL="872391508675-compute@developer.gserviceaccount.com"

echo "========================================="
echo " Granting Logging Permissions to Compute SA"
echo "========================================="
echo ""

echo "Granting roles/logging.logWriter to $COMPUTE_SA_EMAIL..."

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$COMPUTE_SA_EMAIL" \
    --role="roles/logging.logWriter" \
    --quiet

echo "✅ Successfully granted logging permissions"
echo ""
echo "========================================="
echo " Logging permissions granted!"
echo "========================================="
echo ""
echo "The compute service account can now write logs to Cloud Logging."
echo "You can now run Cloud Build locally."
