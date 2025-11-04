#!/bin/bash

# Test script to validate Open Graph and Twitter Card meta tags
echo "=== Open Graph & Twitter Card Validation Test ==="
echo ""

# Test URL
LOCAL_URL="http://localhost:8080/embed/324a6ab1-1b56-4ad5-adde-a7349df56472"
NGROK_URL="https://857daa7fb123.ngrok-free.app/embed/324a6ab1-1b56-4ad5-adde-a7349df56472"

echo "Testing URL: $LOCAL_URL"
echo ""

# Function to extract and validate meta tags
validate_meta_tags() {
    local url=$1
    local label=$2

    echo "=== $label ==="

    # Get HTML content
    html=$(curl -s "$url" 2>/dev/null)

    if [ $? -ne 0 ] || [ -z "$html" ]; then
        echo "❌ Failed to fetch HTML from $url"
        return 1
    fi

    echo "✅ Successfully fetched HTML"

    # Check Open Graph tags
    echo ""
    echo "Open Graph Tags:"
    og_tags=("og:type" "og:title" "og:description" "og:audio" "og:audio:type" "og:image" "og:url" "og:site_name")

    for tag in "${og_tags[@]}"; do
        if echo "$html" | grep -q "property=\"$tag\""; then
            content=$(echo "$html" | grep "property=\"$tag\"" | sed 's/.*content="\([^"]*\)".*/\1/' | head -1)
            if [ -n "$content" ]; then
                echo "✅ $tag: \"$content\""
            else
                echo "⚠️  $tag: present but empty"
            fi
        else
            echo "❌ $tag: missing"
        fi
    done

    # Check Twitter Card tags
    echo ""
    echo "Twitter Card Tags:"
    twitter_tags=("twitter:card" "twitter:title" "twitter:description" "twitter:image" "twitter:player" "twitter:player:width" "twitter:player:height")

    for tag in "${twitter_tags[@]}"; do
        if echo "$html" | grep -q "name=\"$tag\""; then
            content=$(echo "$html" | grep "name=\"$tag\"" | sed 's/.*content="\([^"]*\)".*/\1/' | head -1)
            if [ -n "$content" ]; then
                echo "✅ $tag: \"$content\""
            else
                echo "⚠️  $tag: present but empty"
            fi
        else
            echo "❌ $tag: missing"
        fi
    done

    # Check oEmbed discovery
    echo ""
    echo "oEmbed Discovery:"
    if echo "$html" | grep -q "rel=\"alternate\".*application/json+oembed"; then
        echo "✅ oEmbed discovery link present"
        oembed_url=$(echo "$html" | grep "rel=\"alternate\".*application/json+oembed" | sed 's/.*href="\([^"]*\)".*/\1/')
        echo "   URL: $oembed_url"
    else
        echo "❌ oEmbed discovery link missing"
    fi

    echo ""
}

# Test localhost
validate_meta_tags "$LOCAL_URL" "Localhost Test"

# Test ngrok (if accessible)
echo "Testing ngrok URL..."
if curl -s --max-time 5 "$NGROK_URL" > /dev/null 2>&1; then
    validate_meta_tags "$NGROK_URL" "Ngrok Test"
else
    echo "⚠️  Ngrok URL not accessible (tunnel may be down)"
    echo ""
fi

echo "=== Summary ==="
echo ""
echo "Expected Results:"
echo "✅ All Open Graph tags should be present and populated"
echo "✅ All Twitter Card tags should be present and populated"
echo "✅ oEmbed discovery link should be present"
echo "✅ Audio and image URLs should be signed GCS URLs"
echo ""
echo "For online validation:"
echo "1. Open Graph: https://opengraph.xyz/"
echo "2. Twitter Cards: https://cards-dev.twitter.com/validator"
echo "3. Use the ngrok URL for external validation services"
echo ""
echo "Test completed."
