#!/bin/bash

# Deploy to staging for oEmbed testing
# Uses existing staging deployment with public URL

echo "🚀 Deploying to Staging for oEmbed Testing"
echo "==========================================="

# Build and deploy to staging
echo "1. Building and deploying to staging..."
gcloud builds submit --config cloudbuild-staging.yaml

# Wait for deployment
echo "2. Waiting for deployment to complete..."
sleep 30

# Get staging URL
STAGING_URL=$(gcloud run services describe music-library-mcp-staging \
  --region=us-central1 \
  --format="value(status.url)")

echo "3. Staging deployment complete!"
echo "   URL: $STAGING_URL"
echo ""

# Test oEmbed endpoints
echo "4. Testing oEmbed endpoints on staging:"

# Test with a sample audio ID (you'll need to replace with real ID)
TEST_ID="550e8400-e29b-41d4-a716-446655440000"
EMBED_URL="$STAGING_URL/embed/$TEST_ID"
OEMBED_URL="$STAGING_URL/oembed?url=$EMBED_URL"

echo "   Embed URL: $EMBED_URL"
echo "   oEmbed URL: $OEMBED_URL"
echo ""

echo "5. Test commands:"
echo "   # Test embed page"
echo "   curl -I '$EMBED_URL'"
echo ""
echo "   # Test oEmbed response"
echo "   curl '$OEMBED_URL' | jq ."
echo ""

echo "6. External service testing URLs:"
echo "   Twitter: https://cards-dev.twitter.com/validator"
echo "   Facebook: https://developers.facebook.com/tools/debug/"
echo "   LinkedIn: https://www.linkedin.com/post-inspector/"
echo ""
echo "   Use this URL in the validators: $EMBED_URL"

