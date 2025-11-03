#!/bin/bash
# Test EMBED_BASE_URL configuration fix in staging environment

set -e

PROJECT_ID="loist-music-library"
STAGING_URL="https://music-library-mcp-staging-123456789.us-central1.run.app"  # Will be updated with actual URL

echo "========================================="
echo " Testing EMBED_BASE_URL Configuration Fix"
echo "========================================="
echo ""

# Get the actual staging URL from Cloud Run
echo "Getting staging service URL..."
STAGING_URL=$(gcloud run services describe music-library-mcp-staging \
    --project="$PROJECT_ID" \
    --region=us-central1 \
    --format="value(status.url)" 2>/dev/null || echo "")

if [ -z "$STAGING_URL" ]; then
    echo "❌ Could not retrieve staging service URL"
    echo "Make sure the staging service is deployed and running"
    exit 1
fi

echo "Staging URL: $STAGING_URL"
echo ""

# Test audio processing with MCP call
echo "Testing MCP process_audio_complete call..."

# Use a sample audio URL for testing
TEST_AUDIO_URL="https://tmpfiles.org/dl/6548927/xcd397_04_3yourtaxi_instrumental30seconds.mp3"

# Create MCP request payload
MCP_REQUEST='{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "mcp_loist-music-library-staging_process_audio_complete",
    "arguments": {
      "source": {
        "type": "http_url",
        "url": "'"$TEST_AUDIO_URL"'"
      }
    }
  }
}'

echo "Sending MCP request to staging server..."
echo "Request: $MCP_REQUEST"
echo ""

# Make the HTTP request to the staging server
RESPONSE=$(curl -s -X POST "$STAGING_URL" \
    -H "Content-Type: application/json" \
    -d "$MCP_REQUEST" 2>/dev/null || echo "")

echo "Response: $RESPONSE"
echo ""

# Check if the response contains the expected embed URL
if echo "$RESPONSE" | grep -q "staging.loist.io"; then
    echo "✅ SUCCESS: EMBED_BASE_URL fix is working!"
    echo "Response contains 'staging.loist.io' as expected"
    echo ""
    echo "========================================="
    echo " EMBED_BASE_URL FIX VERIFIED"
    echo "========================================="
    echo ""
    echo "The staging server is correctly returning embed links with:"
    echo "https://staging.loist.io/embed/{audioId}"
    echo ""
    echo "This confirms the EMBED_BASE_URL environment variable"
    echo "is being properly injected at runtime in Cloud Run."
else
    echo "❌ FAILED: EMBED_BASE_URL fix is not working"
    echo ""
    echo "Expected: Response should contain 'staging.loist.io'"
    echo "Actual: Response does not contain staging URL"
    echo ""
    echo "Possible issues:"
    echo "1. Cloud Run deployment didn't use the correct EMBED_BASE_URL"
    echo "2. Database migration failed, preventing audio processing"
    echo "3. MCP server configuration issue"
    echo ""
    exit 1
fi

echo "========================================="
echo " Test completed successfully!"
echo "========================================="
