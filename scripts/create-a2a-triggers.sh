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
  
  # Use import method because direct create sometimes fails with INVALID_ARGUMENT
  TEMP_DIR=$(mktemp -d)
  cat > "$TEMP_DIR/trigger-staging.yaml" << EOF
description: Deploy A2A agent server to staging on dev branch
filename: cloudbuild-a2a-staging.yaml
github:
  name: loist-mcp-server
  owner: DelicateAlchemy
  push:
    branch: ^dev$
name: a2a-staging-deployment
serviceAccount: projects/$PROJECT_ID/serviceAccounts/$SERVICE_ACCOUNT
EOF
  
  gcloud beta builds triggers import \
    --project="$PROJECT_ID" \
    --source="$TEMP_DIR/trigger-staging.yaml"
  
  rm -rf "$TEMP_DIR"
  echo "✅ A2A staging trigger created"
else
  echo "⚠️  A2A staging trigger already exists, skipping creation"
fi

echo ""

# Create A2A Production Trigger
if [ -z "$PROD_EXISTS" ]; then
  echo "📦 Creating A2A production trigger..."
  
  # Use import method because direct create sometimes fails with INVALID_ARGUMENT
  TEMP_DIR=$(mktemp -d)
  cat > "$TEMP_DIR/trigger-prod.yaml" << EOF
description: Deploy A2A agent server to production on main branch
filename: cloudbuild-a2a-prod.yaml
github:
  name: loist-mcp-server
  owner: DelicateAlchemy
  push:
    branch: ^main$
name: a2a-prod-deployment
serviceAccount: projects/$PROJECT_ID/serviceAccounts/$SERVICE_ACCOUNT
EOF
  
  gcloud beta builds triggers import \
    --project="$PROJECT_ID" \
    --source="$TEMP_DIR/trigger-prod.yaml"
  
  rm -rf "$TEMP_DIR"
  echo "✅ A2A production trigger created"
else
  echo "⚠️  A2A production trigger already exists, skipping creation"
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
echo "  - a2a-staging-deployment: Triggers on ANY push to dev branch (mirrors MCP staging trigger)"
echo "  - a2a-prod-deployment: Triggers on ANY push to main branch (mirrors MCP production trigger)"
echo ""
echo "Note: Triggers fire on any code change, not just A2A code, to support branch merges."

