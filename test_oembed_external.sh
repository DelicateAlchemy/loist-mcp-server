#!/bin/bash

# Test oEmbed implementation with external services
# This script demonstrates how to test oEmbed responses

echo "🧪 Testing oEmbed Implementation with External Services"
echo "======================================================"

# Set your public URL (ngrok, staging, etc.)
PUBLIC_URL="${PUBLIC_URL:-https://your-ngrok-url.ngrok.io}"

echo "Using public URL: $PUBLIC_URL"
echo ""

# Test 1: Direct oEmbed endpoint access
echo "1. Testing direct oEmbed endpoint access:"
OEMBED_URL="$PUBLIC_URL/oembed?url=$PUBLIC_URL/embed/test-audio-id"
echo "   URL: $OEMBED_URL"

# Use curl to test the endpoint
curl -s "$OEMBED_URL" | jq . 2>/dev/null || curl -s "$OEMBED_URL"
echo ""

# Test 2: Embed page access
echo "2. Testing embed page access:"
EMBED_URL="$PUBLIC_URL/embed/test-audio-id"
echo "   URL: $EMBED_URL"

curl -s -I "$EMBED_URL" | head -3
echo ""

# Test 3: HTML meta tags validation
echo "3. Testing HTML meta tags (oEmbed discovery):"
curl -s "$EMBED_URL" | grep -i "oembed" || echo "   No oEmbed discovery links found"
echo ""

# Test 4: Test with external oEmbed consumers
echo "4. Test URLs for external services:"
echo "   Twitter Card Validator: https://cards-dev.twitter.com/validator"
echo "   Facebook Debugger: https://developers.facebook.com/tools/debug/"
echo "   LinkedIn Preview: https://www.linkedin.com/post-inspector/"
echo ""
echo "   Use these URLs in the validators:"
echo "   - $EMBED_URL"
echo "   - $PUBLIC_URL/oembed?url=$EMBED_URL"
echo ""

echo "5. Manual testing commands:"
echo "   # Test oEmbed JSON response"
echo "   curl '$PUBLIC_URL/oembed?url=$PUBLIC_URL/embed/test-id'"
echo ""
echo "   # Test embed page HTML"
echo "   curl '$PUBLIC_URL/embed/test-id'"
echo ""
echo "   # Test with real audio ID (replace with actual ID)"
echo "   curl '$PUBLIC_URL/oembed?url=$PUBLIC_URL/embed/550e8400-e29b-41d4-a716-446655440000'"

