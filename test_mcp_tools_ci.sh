#!/bin/bash
# Enhanced MCP Tools Testing for CI/CD
# Outputs structured JSON results with timestamps and test metadata

cd "$(dirname "$0")"

# Test configuration
TEST_START_TIME=$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ")
TEST_SUITE="mcp_tools"
OUTPUT_FILE="mcp_tools_results.json"

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

# Function to run MCP test and measure time
run_mcp_test() {
    local test_name="$1"
    local mcp_messages="$2"
    
    echo "Running test: $test_name"
    
    local start_time=$(date +%s.%N)
    
    # Create temporary message file
    echo "$mcp_messages" > /tmp/mcp_test_messages_ci.json
    
    # Run the test and capture output
    local output=$(cat /tmp/mcp_test_messages_ci.json | ./run_mcp_stdio_docker.sh 2>&1)
    local exit_code=$?
    
    local end_time=$(date +%s.%N)
    local duration=$(echo "$end_time - $start_time" | bc -l 2>/dev/null || echo "0")
    # Ensure duration has leading zero for JSON compliance
    if [[ "$duration" =~ ^\. ]]; then
        duration="0$duration"
    fi
    
    # Clean up
    rm -f /tmp/mcp_test_messages_ci.json
    
    # Write results to temporary files to avoid output contamination
    echo "$output" > "/tmp/test_output_${test_name}.txt"
    echo "$exit_code" > "/tmp/test_exit_${test_name}.txt"
    echo "$duration" > "/tmp/test_duration_${test_name}.txt"
}

echo "Starting MCP Tools CI Testing..."
echo "=================================="

# Test counters
total_tests=0
passed_tests=0
failed_tests=0
warning_tests=0

# Test 1: Initialize and Health Check
total_tests=$((total_tests + 1))
echo "Test 1: Health Check"

mcp_messages='{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "ci-test", "version": "1.0"}}}
{"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
{"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "health_check", "arguments": {}}}'

run_mcp_test "health_check" "$mcp_messages"
output=$(cat "/tmp/test_output_health_check.txt" 2>/dev/null || echo "")
exit_code=$(cat "/tmp/test_exit_health_check.txt" 2>/dev/null || echo "1")
duration=$(cat "/tmp/test_duration_health_check.txt" 2>/dev/null || echo "0")

# Validate health check response
if echo "$output" | grep -q '"status":"healthy"' && echo "$output" | grep -q '"transport":"stdio"'; then
    add_test_result "health_check" "passed" "$output" "" "$duration"
    passed_tests=$((passed_tests + 1))
    echo "✅ Health check passed"
else
    add_test_result "health_check" "failed" "$output" "Health check did not return expected status" "$duration"
    failed_tests=$((failed_tests + 1))
    echo "❌ Health check failed"
fi

# Test 2: Invalid Audio Metadata (Validation Error)
total_tests=$((total_tests + 1))
echo "Test 2: Audio Metadata Validation Error"

mcp_messages='{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "ci-test", "version": "1.0"}}}
{"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
{"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "get_audio_metadata", "arguments": {"audioId": "invalid-id"}}}'

run_mcp_test "get_audio_metadata_validation" "$mcp_messages"
output=$(cat "/tmp/test_output_get_audio_metadata_validation.txt" 2>/dev/null || echo "")
exit_code=$(cat "/tmp/test_exit_get_audio_metadata_validation.txt" 2>/dev/null || echo "1")
duration=$(cat "/tmp/test_duration_get_audio_metadata_validation.txt" 2>/dev/null || echo "0")

# Validate error response format
if echo "$output" | grep -q '"error":"INVALID_QUERY"' && echo "$output" | grep -q '"success":false'; then
    add_test_result "get_audio_metadata_validation" "passed" "$output" "" "$duration"
    passed_tests=$((passed_tests + 1))
    echo "✅ Audio metadata validation error handled correctly"
else
    add_test_result "get_audio_metadata_validation" "failed" "$output" "Expected INVALID_QUERY error not found" "$duration"
    failed_tests=$((failed_tests + 1))
    echo "❌ Audio metadata validation error failed"
fi

# Test 3: Search Library (Database Error Expected)
total_tests=$((total_tests + 1))
echo "Test 3: Search Library Database Error"

mcp_messages='{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "ci-test", "version": "1.0"}}}
{"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
{"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "search_library", "arguments": {"query": "test"}}}'

run_mcp_test "search_library_database_error" "$mcp_messages"
output=$(cat "/tmp/test_output_search_library_database_error.txt" 2>/dev/null || echo "")
exit_code=$(cat "/tmp/test_exit_search_library_database_error.txt" 2>/dev/null || echo "1")
duration=$(cat "/tmp/test_duration_search_library_database_error.txt" 2>/dev/null || echo "0")

# Validate database error response
if echo "$output" | grep -q '"error":"DATABASE_ERROR"' && echo "$output" | grep -q '"success":false'; then
    add_test_result "search_library_database_error" "passed" "$output" "" "$duration"
    passed_tests=$((passed_tests + 1))
    echo "✅ Search library database error handled correctly"
else
    add_test_result "search_library_database_error" "failed" "$output" "Expected DATABASE_ERROR not found" "$duration"
    failed_tests=$((failed_tests + 1))
    echo "❌ Search library database error failed"
fi

# Test 4: FastMCP Version Check (Warning only)
total_tests=$((total_tests + 1))
echo "Test 4: FastMCP Version Check"

if echo "$output" | grep -q 'FastMCP version: 2.12.4'; then
    add_test_result "fastmcp_version_check" "passed" "FastMCP 2.12.4 detected" "" "0"
    passed_tests=$((passed_tests + 1))
    echo "✅ FastMCP version 2.12.4 confirmed"
else
    add_test_result "fastmcp_version_check" "warning" "$output" "FastMCP version 2.12.4 not confirmed" "0"
    warning_tests=$((warning_tests + 1))
    echo "⚠️  FastMCP version check warning"
fi

# Test 5: Exception Loading Check
total_tests=$((total_tests + 1))
echo "Test 5: Exception Loading Check"

if echo "$output" | grep -q 'Exception classes loaded and verified: 10 classes'; then
    add_test_result "exception_loading_check" "passed" "10 custom exceptions loaded" "" "0"
    passed_tests=$((passed_tests + 1))
    echo "✅ All 10 custom exceptions loaded correctly"
else
    add_test_result "exception_loading_check" "failed" "$output" "Expected 10 custom exceptions not confirmed" "0"
    failed_tests=$((failed_tests + 1))
    echo "❌ Exception loading check failed"
fi

# Update final summary
update_summary $total_tests $passed_tests $failed_tests $warning_tests

# Clean up temporary files
rm -f /tmp/test_output_*.txt /tmp/test_exit_*.txt /tmp/test_duration_*.txt

echo ""
echo "=================================="
echo "MCP Tools CI Test Results:"
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
