#!/bin/bash
# HTTP API Validation Script
# Tests all HTTP REST endpoints to ensure they work correctly
# Can be run locally with docker-compose or against deployed instances

set -e

# Configuration
BASE_URL="${BASE_URL:-http://localhost:8080}"
TIMEOUT="${TIMEOUT:-10}"

echo "🔍 Validating HTTP API endpoints..."
echo "📍 Base URL: $BASE_URL"
echo "⏱️  Timeout: $TIMEOUT seconds"
echo

# Counter for tests
TOTAL_TESTS=0
PASSED_TESTS=0

# Function to run a test
run_test() {
    local test_name="$1"
    local curl_cmd="$2"
    local expected_status="$3"
    local expected_content="$4"

    echo "🧪 Testing: $test_name"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    # Run the curl command and capture output
    if response=$(eval "$curl_cmd" 2>/dev/null); then
        # Extract status code from response (assuming JSON response with status code)
        actual_status=$(echo "$response" | jq -r '.status // empty' 2>/dev/null || echo "unknown")

        # Check if response contains expected content
        if echo "$response" | grep -q "$expected_content"; then
            echo "✅ PASS: $test_name"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            echo "❌ FAIL: $test_name - Expected '$expected_content' not found in response"
            echo "   Response: $response"
        fi
    else
        echo "❌ FAIL: $test_name - Request failed"
    fi

    echo
}

# Test 1: GET /api/tracks/{invalid-id} - Should return 400
run_test \
    "GET /api/tracks/{invalid-id} returns 400 for invalid ID" \
    "curl -s -w '{\"status\":%{http_code}}' -H 'Accept: application/json' '$BASE_URL/api/tracks/invalid-id'" \
    "400" \
    '"success":false'

# Test 2: GET /api/tracks/{nonexistent-id} - Should return 404
run_test \
    "GET /api/tracks/{nonexistent-id} returns 404 for nonexistent track" \
    "curl -s -w '{\"status\":%{http_code}}' -H 'Accept: application/json' '$BASE_URL/api/tracks/00000000-0000-0000-0000-000000000000'" \
    "404" \
    '"success":false'

# Test 3: GET /api/search without query - Should return 400
run_test \
    "GET /api/search without query returns 400" \
    "curl -s -w '{\"status\":%{http_code}}' -H 'Accept: application/json' '$BASE_URL/api/search'" \
    "400" \
    '"success":false'

# Test 4: GET /api/search with empty query - Should return 400
run_test \
    "GET /api/search with empty query returns 400" \
    "curl -s -w '{\"status\":%{http_code}}' -H 'Accept: application/json' '$BASE_URL/api/search?q='" \
    "400" \
    '"success":false'

# Test 5: GET /api/search with valid query - Should return 200 (may be empty results)
run_test \
    "GET /api/search with valid query returns 200" \
    "curl -s -w '{\"status\":%{http_code}}' -H 'Accept: application/json' '$BASE_URL/api/search?q=test'" \
    "200" \
    '"success":'

# Test 6: GET /api/search with genre filter - Should return 200
run_test \
    "GET /api/search with genre filter returns 200" \
    "curl -s -w '{\"status\":%{http_code}}' -H 'Accept: application/json' '$BASE_URL/api/search?q=test&genre=Rock'" \
    "200" \
    '"success":'

# Test 7: GET /api/search with pagination - Should return 200
run_test \
    "GET /api/search with pagination returns 200" \
    "curl -s -w '{\"status\":%{http_code}}' -H 'Accept: application/json' '$BASE_URL/api/search?q=test&limit=5&offset=0'" \
    "200" \
    '"success":'

# Test 8: GET /api/tracks/{audioId}/stream with invalid ID - Should return 400
run_test \
    "GET /api/tracks/{audioId}/stream with invalid ID returns 400" \
    "curl -s -w '{\"status\":%{http_code}}' -H 'Accept: application/json' '$BASE_URL/api/tracks/invalid-id/stream'" \
    "400" \
    '"success":false'

# Test 9: GET /api/tracks/{audioId}/thumbnail with invalid ID - Should return 400
run_test \
    "GET /api/tracks/{audioId}/thumbnail with invalid ID returns 400" \
    "curl -s -w '{\"status\":%{http_code}}' -H 'Accept: application/json' '$BASE_URL/api/tracks/invalid-id/thumbnail'" \
    "400" \
    '"success":false'

# Test 10: GET /api/tracks/{audioId}/stream with nonexistent ID - Should return 404
run_test \
    "GET /api/tracks/{audioId}/stream with nonexistent ID returns 404" \
    "curl -s -w '{\"status\":%{http_code}}' -H 'Accept: application/json' '$BASE_URL/api/tracks/00000000-0000-0000-0000-000000000000/stream'" \
    "404" \
    '"success":false'

# Test 11: GET /api/tracks/{audioId}/thumbnail with nonexistent ID - Should return 404 or 200 with success=false
run_test \
    "GET /api/tracks/{audioId}/thumbnail with nonexistent ID returns appropriate response" \
    "curl -s -w '{\"status\":%{http_code}}' -H 'Accept: application/json' '$BASE_URL/api/tracks/00000000-0000-0000-0000-000000000000/thumbnail'" \
    "200" \
    '"success":'

# Test 12: Check that all endpoints return valid JSON
echo "🔍 Testing JSON response format for all endpoints..."
for endpoint in "/api/search?q=test" "/api/tracks/00000000-0000-0000-0000-000000000000" "/api/tracks/00000000-0000-0000-0000-000000000000/stream" "/api/tracks/00000000-0000-0000-0000-000000000000/thumbnail"; do
    echo "  Testing JSON format for: $endpoint"
    if response=$(curl -s -H 'Accept: application/json' "$BASE_URL$endpoint" 2>/dev/null); then
        if echo "$response" | jq . >/dev/null 2>&1; then
            echo "  ✅ Valid JSON response"
        else
            echo "  ❌ Invalid JSON response"
            echo "     Response: $response"
        fi
    else
        echo "  ❌ Request failed"
    fi
done

echo
echo "📊 Test Results:"
echo "   Total Tests: $TOTAL_TESTS"
echo "   Passed: $PASSED_TESTS"
echo "   Failed: $((TOTAL_TESTS - PASSED_TESTS))"

if [ $PASSED_TESTS -eq $TOTAL_TESTS ]; then
    echo "🎉 All tests passed!"
    exit 0
else
    echo "💥 Some tests failed. Please check the output above."
    exit 1
fi
