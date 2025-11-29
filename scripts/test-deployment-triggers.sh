#!/bin/bash
# Test Cloud Build trigger configuration and automated deployment

set -e

PROJECT_ID="loist-music-library"

echo "========================================="
echo " Cloud Build Trigger Configuration Test"
echo "========================================="
echo ""

# Check production trigger
echo "1. Production Trigger (main branch):"
echo "-------------------------------------"
gcloud builds triggers describe production-deployment-init-location \
  --project=$PROJECT_ID \
  --format="table(name,github.push.branch,filename,disabled,approvalConfig.approvalRequired)" 2>&1

echo ""

# Check staging trigger  
echo "2. Staging Trigger (dev branch):"
echo "-------------------------------------"
if gcloud builds triggers describe staging-deployment-dev-branch \
  --project=$PROJECT_ID \
  --format="table(name,github.push.branch,filename,disabled)" 2>&1; then
    echo "✅ Staging trigger configured"
else
    echo "❌ Staging trigger not found"
fi

echo ""

# Recent builds
echo "3. Recent Cloud Build Deployments:"
echo "-------------------------------------"
gcloud builds list --project=$PROJECT_ID --limit=5 \
  --format="table(id,status,createTime,source.repoSource.branchName,images)" 2>&1

echo ""
echo "========================================="
echo "✅ Trigger test complete"
echo "========================================="

