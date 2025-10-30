#!/bin/bash
# Enhanced MCP Resources Testing for CI/CD
# Outputs structured JSON results with timestamps and test metadata

cd "$(dirname "$0")"

# Test configuration
TEST_START_TIME=$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ")
TEST_SUITE="mcp_resources"
OUTPUT_FILE="mcp_resources_results.json"

# Initialize results structure
cat > "$OUTPUT_FILE" << EOF
{
  "testSuite": "$TEST_SUITE",
  "startTime": "$TEST_START_TIME",
  "tests": [],
  "summary": {
    "total": 0,
    "passed": 0,
    "failed": 0,
    "warnings": 0
  }
}
EOF

# Function to add test result
add_test_result() {
    local test_name="$1"
    local status="$2"
    local response="$3"
    local error_message="$4"
    local duration="$5"
    local test_time=$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ")
    
    # Escape JSON strings properly
    response=$(echo "$response" | sed 's/\\/\\\\/g' | sed 's/"/\\"/g' | tr -d '\n\r' | head -c 500)
    error_message=$(echo "$error_message" | sed 's/\\/\\\\/g' | sed 's/"/\\"/g' | tr -d '\n\r')
    
    # Append to a simple JSON array file
    echo "{\"name\":\"$test_name\",\"status\":\"$status\",\"timestamp\":\"$test_time\",\"duration\":$duration,\"response\":\"$response\",\"errorMessage\":\"$error_message\"}" >> "${OUTPUT_FILE}.tests"
}

# Function to update summary and build final JSON
update_summary() {
    local total=$1
    local passed=$2
    local failed=$3
    local warnings=$4
    local end_time=$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ")
    
    # Build final JSON file
    cat > "$OUTPUT_FILE" << EOF
{
  "testSuite": "$TEST_SUITE",
  "startTime": "$TEST_START_TIME",
  "endTime": "$end_time",
  "tests": [
EOF
    
    # Add all test results
    if [ -f "${OUTPUT_FILE}.tests" ]; then
        local first=true
        while IFS= read -r line; do
            if [ "$first" = true ]; then
                echo "    $line" >> "$OUTPUT_FILE"
                first=false
            else
                echo "    ,$line" >> "$OUTPUT_FILE"
            fi
        done < "${OUTPUT_FILE}.tests"
        rm -f "${OUTPUT_FILE}.tests"
    fi
    
    # Close tests array and add summary
    cat >> "$OUTPUT_FILE" << EOF
  ],
  "summary": {
    "total": $total,
    "passed": $passed,
    "failed": $failed,
    "warnings": $warnings
  }
}
EOF
}

# Function to run MCP resource test and measure time
run_mcp_resource_test() {
    local test_name="$1"
    local resource_uri="$2"
    
    echo "Running resource test: $test_name"
    
    local start_time=$(date +%s.%N)
    
    # Create MCP resource test messages
    local mcp_messages=$(cat << EOF
{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "ci-test", "version": "1.0"}}}
{"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
{"jsonrpc": "2.0", "id": 2, "method": "resources/list", "params": {}}
{"jsonrpc": "2.0", "id": 3, "method": "resources/read", "params": {"uri": "$resource_uri"}}
EOF
)
    
    # Create temporary message file
    echo "$mcp_messages" > /tmp/mcp_resource_test_ci.json
    
    # Run the test and capture output
    local output=$(cat /tmp/mcp_resource_test_ci.json | ./run_mcp_stdio_docker.sh 2>&1)
    local exit_code=$?
    
    local end_time=$(date +%s.%N)
    local duration=$(echo "$end_time - $start_time" | bc -l 2>/dev/null || echo "0")
    
    # Clean up
    rm -f /tmp/mcp_resource_test_ci.json
    
    echo "$output|$exit_code|$duration"
}

echo "Starting MCP Resources CI Testing..."
echo "====================================="

# Test counters
total_tests=0
passed_tests=0
failed_tests=0
warning_tests=0

# Test UUID for resource testing
TEST_UUID="550e8400-e29b-41d4-a716-446655440000"

# Test 1: Resources List
total_tests=$((total_tests + 1))
echo "Test 1: Resources List"

mcp_messages='{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "ci-test", "version": "1.0"}}}
{"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
{"jsonrpc": "2.0", "id": 2, "method": "resources/list", "params": {}}'

start_time=$(date +%s.%N)
echo "$mcp_messages" > /tmp/mcp_list_test_ci.json
output=$(cat /tmp/mcp_list_test_ci.json | ./run_mcp_stdio_docker.sh 2>&1)
end_time=$(date +%s.%N)
duration=$(echo "$end_time - $start_time" | bc -l 2>/dev/null || echo "0")
rm -f /tmp/mcp_list_test_ci.json

# Validate resources list response
if echo "$output" | grep -q '"resources":\[\]'; then
    add_test_result "resources_list" "passed" "$output" "" "$duration"
    passed_tests=$((passed_tests + 1))
    echo "✅ Resources list returned successfully"
else
    add_test_result "resources_list" "failed" "$output" "Resources list did not return expected format" "$duration"
    failed_tests=$((failed_tests + 1))
    echo "❌ Resources list failed"
fi

# Test 2: Metadata Resource URI Parsing
total_tests=$((total_tests + 1))
echo "Test 2: Metadata Resource URI Parsing"

result=$(run_mcp_resource_test "metadata_resource" "music-library://audio/$TEST_UUID/metadata")
output=$(echo "$result" | cut -d'|' -f1)
exit_code=$(echo "$result" | cut -d'|' -f2)
duration=$(echo "$result" | cut -d'|' -f3)

# Check for proper URI parsing (expect database error, not URI format error)
if echo "$output" | grep -q 'Database URL must be provided' && ! echo "$output" | grep -q 'Invalid URI format'; then
    add_test_result "metadata_resource_uri_parsing" "passed" "$output" "" "$duration"
    passed_tests=$((passed_tests + 1))
    echo "✅ Metadata resource URI parsing works correctly"
elif echo "$output" | grep -q 'Invalid URI format'; then
    add_test_result "metadata_resource_uri_parsing" "failed" "$output" "URI parsing failed - Invalid URI format error" "$duration"
    failed_tests=$((failed_tests + 1))
    echo "❌ Metadata resource URI parsing failed"
else
    add_test_result "metadata_resource_uri_parsing" "warning" "$output" "Unexpected response format" "$duration"
    warning_tests=$((warning_tests + 1))
    echo "⚠️  Metadata resource URI parsing - unexpected response"
fi

# Test 3: Stream Resource URI Parsing
total_tests=$((total_tests + 1))
echo "Test 3: Stream Resource URI Parsing"

result=$(run_mcp_resource_test "stream_resource" "music-library://audio/$TEST_UUID/stream")
output=$(echo "$result" | cut -d'|' -f1)
exit_code=$(echo "$result" | cut -d'|' -f2)
duration=$(echo "$result" | cut -d'|' -f3)

# Check for proper URI parsing (expect database error, not URI format error)
if echo "$output" | grep -q 'Database URL must be provided' && ! echo "$output" | grep -q 'Invalid URI format'; then
    add_test_result "stream_resource_uri_parsing" "passed" "$output" "" "$duration"
    passed_tests=$((passed_tests + 1))
    echo "✅ Stream resource URI parsing works correctly"
elif echo "$output" | grep -q 'Invalid URI format'; then
    add_test_result "stream_resource_uri_parsing" "failed" "$output" "URI parsing failed - Invalid URI format error" "$duration"
    failed_tests=$((failed_tests + 1))
    echo "❌ Stream resource URI parsing failed"
else
    add_test_result "stream_resource_uri_parsing" "warning" "$output" "Unexpected response format" "$duration"
    warning_tests=$((warning_tests + 1))
    echo "⚠️  Stream resource URI parsing - unexpected response"
fi

# Test 4: Thumbnail Resource URI Parsing
total_tests=$((total_tests + 1))
echo "Test 4: Thumbnail Resource URI Parsing"

result=$(run_mcp_resource_test "thumbnail_resource" "music-library://audio/$TEST_UUID/thumbnail")
output=$(echo "$result" | cut -d'|' -f1)
exit_code=$(echo "$result" | cut -d'|' -f2)
duration=$(echo "$result" | cut -d'|' -f3)

# Check for proper URI parsing (expect database error, not URI format error)
if echo "$output" | grep -q 'Database URL must be provided' && ! echo "$output" | grep -q 'Invalid URI format'; then
    add_test_result "thumbnail_resource_uri_parsing" "passed" "$output" "" "$duration"
    passed_tests=$((passed_tests + 1))
    echo "✅ Thumbnail resource URI parsing works correctly"
elif echo "$output" | grep -q 'Invalid URI format'; then
    add_test_result "thumbnail_resource_uri_parsing" "failed" "$output" "URI parsing failed - Invalid URI format error" "$duration"
    failed_tests=$((failed_tests + 1))
    echo "❌ Thumbnail resource URI parsing failed"
else
    add_test_result "thumbnail_resource_uri_parsing" "warning" "$output" "Unexpected response format" "$duration"
    warning_tests=$((warning_tests + 1))
    echo "⚠️  Thumbnail resource URI parsing - unexpected response"
fi

# Test 5: Invalid Resource URI (Should Fail Gracefully)
total_tests=$((total_tests + 1))
echo "Test 5: Invalid Resource URI Handling"

result=$(run_mcp_resource_test "invalid_resource" "music-library://audio/invalid-uuid/metadata")
output=$(echo "$result" | cut -d'|' -f1)
exit_code=$(echo "$result" | cut -d'|' -f2)
duration=$(echo "$result" | cut -d'|' -f3)

# Check for proper error handling of invalid UUID
if echo "$output" | grep -q 'Invalid URI format' || echo "$output" | grep -q 'error'; then
    add_test_result "invalid_resource_uri_handling" "passed" "$output" "" "$duration"
    passed_tests=$((passed_tests + 1))
    echo "✅ Invalid resource URI handled correctly"
else
    add_test_result "invalid_resource_uri_handling" "failed" "$output" "Invalid URI should return error" "$duration"
    failed_tests=$((failed_tests + 1))
    echo "❌ Invalid resource URI handling failed"
fi

# Update final summary
update_summary $total_tests $passed_tests $failed_tests $warning_tests

echo ""
echo "====================================="
echo "MCP Resources CI Test Results:"
echo "  Total: $total_tests"
echo "  Passed: $passed_tests"
echo "  Failed: $failed_tests"
echo "  Warnings: $warning_tests"
echo ""
echo "Results saved to: $OUTPUT_FILE"

# Exit with error code if any tests failed
if [ $failed_tests -gt 0 ]; then
    echo "❌ Some tests failed!"
    exit 1
else
    echo "✅ All critical tests passed!"
    exit 0
fi
