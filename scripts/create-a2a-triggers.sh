#!/bin/bash
# Create A2A Cloud Build triggers for staging and production
# This script creates the triggers if they don't exist
#
# IMPORTANT: Make sure cloudbuild-a2a-staging.yaml and cloudbuild-a2a-prod.yaml
# are pushed to GitHub before running this script, as Cloud Build validates
# that the build config files exist in the repository.

set -e

PROJECT_ID="loist-music-library"
REPO_NAME="DelicateAlchemy/loist-mcp-server"
SERVICE_ACCOUNT="loist-music-library-sa@${PROJECT_ID}.iam.gserviceaccount.com"

echo "🔧 Creating A2A Cloud Build triggers..."
echo ""

# Check if triggers already exist
STAGING_EXISTS=$(gcloud builds triggers list --project="$PROJECT_ID" --filter="name:a2a-staging-deployment" --format="value(name)" 2>/dev/null || echo "")
PROD_EXISTS=$(gcloud builds triggers list --project="$PROJECT_ID" --filter="name:a2a-prod-deployment" --format="value(name)" 2>/dev/null || echo "")

# Create A2A Staging Trigger
if [ -z "$STAGING_EXISTS" ]; then
  echo "📦 Creating A2A staging trigger..."
  gcloud builds triggers create github \
    --project="$PROJECT_ID" \
    --name="a2a-staging-deployment" \
    --description="Deploy A2A agent server to staging on dev branch" \
    --repo-name="loist-mcp-server" \
    --repo-owner="DelicateAlchemy" \
    --branch-pattern="^dev$" \
    --build-config="cloudbuild-a2a-staging.yaml" \
    --service-account="$SERVICE_ACCOUNT" \
    --no-require-approval

  echo "✅ A2A staging trigger created"
else
  echo "⚠️  A2A staging trigger already exists, skipping creation"
  echo "   Use ./scripts/update-a2a-trigger-paths.sh to update it"
fi

echo ""

# Create A2A Production Trigger
if [ -z "$PROD_EXISTS" ]; then
  echo "📦 Creating A2A production trigger..."
  gcloud builds triggers create github \
    --project="$PROJECT_ID" \
    --name="a2a-prod-deployment" \
    --description="Deploy A2A agent server to production on main branch" \
    --repo-name="loist-mcp-server" \
    --repo-owner="DelicateAlchemy" \
    --branch-pattern="^main$" \
    --build-config="cloudbuild-a2a-prod.yaml" \
    --service-account="$SERVICE_ACCOUNT" \
    --no-require-approval

  echo "✅ A2A production trigger created"
else
  echo "⚠️  A2A production trigger already exists, skipping creation"
  echo "   Use ./scripts/update-a2a-trigger-paths.sh to update it"
fi

echo ""
echo "📋 Verifying trigger configurations..."
echo ""
echo "All A2A Triggers:"
gcloud builds triggers list \
  --project="$PROJECT_ID" \
  --filter="name~a2a" \
  --format="table(name,description,github.push.branch,filename,includedFiles)"

echo ""
echo "✅ A2A triggers setup complete!"
echo ""
echo "Triggers configured:"
echo "  - a2a-staging-deployment: Triggers on dev branch for src/a2a_server/** or cloudbuild-a2a-staging.yaml"
echo "  - a2a-prod-deployment: Triggers on main branch for src/a2a_server/** or cloudbuild-a2a-prod.yaml"

