#!/bin/bash
# Update A2A Cloud Build trigger path filters to include cloudbuild-a2a-*.yaml files
# This ensures triggers fire when Cloud Build configs are updated

set -e

PROJECT_ID="loist-music-library"

echo "🔧 Updating A2A staging trigger path filter..."
gcloud builds triggers update github a2a-staging-deployment \
  --project="$PROJECT_ID" \
  --included-files="src/a2a_server/**,cloudbuild-a2a-staging.yaml" \
  --branch-pattern="^dev$" \
  --build-config="cloudbuild-a2a-staging.yaml"

echo "✅ A2A staging trigger updated"

echo ""
echo "🔧 Updating A2A production trigger path filter..."
gcloud builds triggers update github a2a-prod-deployment \
  --project="$PROJECT_ID" \
  --included-files="src/a2a_server/**,cloudbuild-a2a-prod.yaml" \
  --branch-pattern="^main$" \
  --build-config="cloudbuild-a2a-prod.yaml"

echo "✅ A2A production trigger updated"

echo ""
echo "📋 Verifying trigger configurations..."
echo ""
echo "A2A Staging Trigger:"
gcloud builds triggers describe a2a-staging-deployment \
  --project="$PROJECT_ID" \
  --format="yaml(github.push.branch,github.push.includedFiles,filename)"

echo ""
echo "A2A Production Trigger:"
gcloud builds triggers describe a2a-prod-deployment \
  --project="$PROJECT_ID" \
  --format="yaml(github.push.branch,github.push.includedFiles,filename)"

echo ""
echo "✅ Trigger path filters updated successfully!"
echo ""
echo "Path filters now include:"
echo "  - src/a2a_server/** (A2A code changes)"
echo "  - cloudbuild-a2a-staging.yaml (staging config changes)"
echo "  - cloudbuild-a2a-prod.yaml (production config changes)"

