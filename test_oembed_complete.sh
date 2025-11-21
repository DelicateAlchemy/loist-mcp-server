#!/bin/bash

# Complete oEmbed Testing Suite
# Tests all aspects of the oEmbed implementation

echo "🎵 Complete oEmbed Testing Suite"
echo "================================"

NGROK_URL="https://857daa7fb123.ngrok-free.app"
AUDIO_ID="f1008aeb-c0a1-44cb-a46d-967a6ac5fc72"

echo "Using ngrok URL: $NGROK_URL"
echo "Using test audio ID: $AUDIO_ID"
echo ""

# Test 1: oEmbed endpoint with valid URL
echo "1. Testing oEmbed endpoint with valid audio URL:"
OEMBED_URL="$NGROK_URL/oembed?url=$NGROK_URL/embed/$AUDIO_ID"
echo "   URL: $OEMBED_URL"
echo "   Response:"
curl -s "$OEMBED_URL" | jq '.html' 2>/dev/null || curl -s "$OEMBED_URL"
echo ""

# Test 2: oEmbed endpoint error handling
echo "2. Testing oEmbed endpoint error handling:"
echo "   Missing URL parameter:"
curl -s "$NGROK_URL/oembed" | jq '.' 2>/dev/null || curl -s "$NGROK_URL/oembed"
echo ""

echo "   Invalid URL format:"
curl -s "$NGROK_URL/oembed?url=https://example.com/embed/test" | jq '.' 2>/dev/null || curl -s "$NGROK_URL/oembed?url=https://example.com/embed/test"
echo ""

echo "   Invalid audio ID format:"
curl -s "$NGROK_URL/oembed?url=$NGROK_URL/embed/invalid-id" | jq '.' 2>/dev/null || curl -s "$NGROK_URL/oembed?url=$NGROK_URL/embed/invalid-id"
echo ""

# Test 3: Embed page with oEmbed discovery
echo "3. Testing embed page with oEmbed discovery:"
EMBED_URL="$NGROK_URL/embed/$AUDIO_ID"
echo "   URL: $EMBED_URL"
echo "   oEmbed discovery link:"
curl -s "$EMBED_URL" | grep -i "oembed\|alternate" || echo "   No oEmbed discovery found"
echo ""

# Test 4: External validator testing URLs
echo "4. URLs for external oEmbed validators:"
echo "   Twitter Card Validator: https://cards-dev.twitter.com/validator"
echo "   Facebook Debugger: https://developers.facebook.com/tools/debug/"
echo "   LinkedIn Preview: https://www.linkedin.com/post-inspector/"
echo ""
echo "   Test these URLs in the validators:"
echo "   - Embed page: $EMBED_URL"
echo "   - Direct oEmbed: $OEMBED_URL"
echo ""

echo "✅ oEmbed testing complete!"
