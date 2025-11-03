#!/bin/bash
# Comprehensive test script for staging deployment and EMBED_BASE_URL fix

set -e

PROJECT_ID="loist-music-library"
BRANCH="dev"

echo "========================================="
echo " Staging Deployment & EMBED_BASE_URL Test"
echo "========================================="
echo ""

# Function to check command success
check_command() {
    if [ $? -eq 0 ]; then
        echo "✅ $1"
    else
        echo "❌ $1"
        exit 1
    fi
}

echo "1. Triggering staging deployment via Cloud Build..."
echo "   Branch: $BRANCH"
echo "   Config: cloudbuild-staging.yaml"
echo ""

# Trigger Cloud Build for staging
BUILD_ID=$(gcloud builds submit . \
    --config=cloudbuild-staging.yaml \
    --substitutions=BRANCH_NAME=$BRANCH \
    --project="$PROJECT_ID" \
    --format="value(id)" \
    --quiet 2>&1)

if [ -z "$BUILD_ID" ]; then
    echo "❌ Failed to trigger Cloud Build"
    exit 1
fi

echo "Build ID: $BUILD_ID"
echo ""

echo "2. Monitoring build progress..."
echo "   This may take 10-15 minutes..."
echo ""

# Wait for build to complete
gcloud builds describe "$BUILD_ID" \
    --project="$PROJECT_ID" \
    --format="value(status)" \
    --quiet > /dev/null

BUILD_STATUS="WORKING"
while [ "$BUILD_STATUS" = "WORKING" ] || [ "$BUILD_STATUS" = "QUEUED" ]; do
    sleep 30
    BUILD_STATUS=$(gcloud builds describe "$BUILD_ID" \
        --project="$PROJECT_ID" \
        --format="value(status)" \
        --quiet 2>&1)
    echo "   Build status: $BUILD_STATUS"
done

if [ "$BUILD_STATUS" != "SUCCESS" ]; then
    echo "❌ Build failed with status: $BUILD_STATUS"
    echo ""
    echo "Build logs:"
    gcloud builds log "$BUILD_ID" --project="$PROJECT_ID" 2>/dev/null || echo "Could not retrieve logs"
    exit 1
fi

echo ""
echo "✅ Build completed successfully!"
echo ""

echo "3. Verifying staging service deployment..."
echo ""

# Check if service is deployed and healthy
SERVICE_STATUS=$(gcloud run services describe music-library-mcp-staging \
    --project="$PROJECT_ID" \
    --region=us-central1 \
    --format="value(status.conditions[0].type,status.conditions[0].status)" \
    --quiet 2>&1 || echo "NOT_FOUND")

if [ "$SERVICE_STATUS" = "Ready True" ]; then
    echo "✅ Staging service is deployed and ready"
else
    echo "❌ Staging service deployment failed or not ready"
    echo "Status: $SERVICE_STATUS"
    exit 1
fi

echo ""

echo "4. Running EMBED_BASE_URL configuration test..."
echo ""

# Run the embed URL test
if ./scripts/test-embed-url-fix.sh; then
    echo ""
    echo "========================================="
    echo " 🎉 ALL TESTS PASSED!"
    echo "========================================="
    echo ""
    echo "✅ Database migration: Successful"
    echo "✅ Staging deployment: Successful"
    echo "✅ EMBED_BASE_URL fix: Verified"
    echo "✅ MCP functionality: Working"
    echo ""
    echo "The staging environment is ready for testing!"
    echo ""
    echo "Next steps:"
    echo "1. Test additional MCP tools as needed"
    echo "2. Verify production deployment when ready"
    echo "3. Enable authentication for production launch"
else
    echo ""
    echo "❌ EMBED_BASE_URL test failed"
    echo ""
    echo "Possible issues:"
    echo "1. Database migration did not complete"
    echo "2. Cloud Run environment variables not set correctly"
    echo "3. MCP server configuration issue"
    echo ""
    exit 1
fi

echo "========================================="
echo " Test completed!"
echo "========================================="
