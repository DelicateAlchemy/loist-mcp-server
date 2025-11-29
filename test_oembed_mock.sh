#!/bin/bash

# Mock external service testing for oEmbed
# Tests oEmbed responses without requiring external services

echo "🎭 Mock Testing oEmbed Implementation"
echo "===================================="

# Set test URLs
BASE_URL="${BASE_URL:-http://localhost:8080}"
TEST_AUDIO_ID="550e8400-e29b-41d4-a716-446655440000"
EMBED_URL="$BASE_URL/embed/$TEST_AUDIO_ID"
OEMBED_URL="$BASE_URL/oembed?url=$EMBED_URL"

echo "Test URLs:"
echo "  Embed URL: $EMBED_URL"
echo "  oEmbed URL: $OEMBED_URL"
echo ""

# Function to test endpoint
test_endpoint() {
    local url="$1"
    local description="$2"
    
    echo "Testing $description:"
    echo "  URL: $url"
    
    local response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" "$url")
    local body=$(echo "$response" | head -n -1)
    local status=$(echo "$response" | tail -n 1 | cut -d: -f2)
    
    if [[ "$status" == "200" ]]; then
        echo "  ✅ Status: $status (OK)"
        # Try to parse JSON
        if echo "$body" | jq . >/dev/null 2>&1; then
            echo "  📄 JSON Response:"
            echo "$body" | jq '.version, .type, .title, .provider_name' 2>/dev/null || echo "    (JSON parsing failed)"
        else
            echo "  📄 HTML Response (first 200 chars):"
            echo "$body" | head -c 200
            echo "..."
        fi
    else
        echo "  ❌ Status: $status (Failed)"
        echo "  📄 Response: $body"
    fi
    echo ""
}

# Test embed page
test_endpoint "$EMBED_URL" "embed page"

# Test oEmbed endpoint
test_endpoint "$OEMBED_URL" "oEmbed endpoint"

# Test oEmbed with invalid URL
INVALID_URL="$BASE_URL/oembed?url=$BASE_URL/invalid/test"
echo "Testing oEmbed with invalid URL:"
echo "  URL: $INVALID_URL"
curl -s "$INVALID_URL" | jq . 2>/dev/null || echo "  Response parsing failed"
echo ""

# Test oEmbed discovery
echo "Testing oEmbed discovery endpoint:"
DISCOVERY_URL="$BASE_URL/.well-known/oembed.json"
echo "  URL: $DISCOVERY_URL"
curl -s "$DISCOVERY_URL" | jq . 2>/dev/null || echo "  Discovery endpoint not accessible"
echo ""

echo "🎯 Mock testing complete!"
echo ""
echo "Next steps for real external testing:"
echo "1. Set up ngrok: ngrok http 8080"
echo "2. Update EMBED_BASE_URL to ngrok URL"
echo "3. Run this script again with BASE_URL=https://your-ngrok-url"
echo "4. Test with external validators (Twitter, Facebook, etc.)"

