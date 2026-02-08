#!/bin/bash
# A2A End-to-End Test Harness
# Tests complete A2A task workflow against docker-compose environment
#
# Run with: bash scripts/test_a2a_e2e.sh

set -e

echo "🚀 Running A2A End-to-End Test Harness..."
echo

# Configuration
A2A_URL="http://localhost:8081"
MCP_URL="http://localhost:8080"
TEST_AUDIO_URL="https://tmpfiles.org/dl/15587739/xcd321_03_3neverwannaletyoudown_instrumental30seconds.mp3"  # Test audio URL (expires in 1 hour)
MAX_READINESS_WAIT=60
MAX_POLL_ATTEMPTS=30
POLL_INTERVAL=2
TIMEOUT=120

# Global variables
TASK_ID=""
AUDIO_ID=""
TASK_RESPONSE=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}ℹ️  $1${NC}"
}

log_warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Function: poll_task
# Polls tasks/get until terminal state with exponential backoff
poll_task() {
    echo "3. Polling tasks/get until completion..."

    if [ -z "$TASK_ID" ]; then
        log_error "No task ID available for polling"
        return 1
    fi

    local request_id="poll-$(date +%s)"
    local json_payload=$(cat <<EOF
{
  "jsonrpc": "2.0",
  "id": "${request_id}",
  "method": "tasks/get",
  "params": {
    "id": "${TASK_ID}"
  }
}
EOF
)

    local attempt=1
    local total_wait_time=0
    local backoff_interval=$POLL_INTERVAL

    log_info "Starting to poll task ${TASK_ID}"
    log_info "Max attempts: ${MAX_POLL_ATTEMPTS}, Initial interval: ${POLL_INTERVAL}s"

    while [ $attempt -le $MAX_POLL_ATTEMPTS ]; do
        echo "   Attempt ${attempt}/${MAX_POLL_ATTEMPTS} (waiting ${backoff_interval}s)..."

        # Send the request
        local response
        response=$(curl -s -X POST "${A2A_URL}/" \
            -H "Content-Type: application/json" \
            -d "${json_payload}" \
            --max-time 10)

        # Check if curl succeeded
        if [ $? -ne 0 ]; then
            log_warn "Poll attempt ${attempt} failed (curl error), retrying..."
            sleep $backoff_interval
            backoff_interval=$((backoff_interval * 2))  # Exponential backoff
            if [ $backoff_interval -gt 30 ]; then
                backoff_interval=30  # Cap at 30 seconds
            fi
            attempt=$((attempt + 1))
            total_wait_time=$((total_wait_time + backoff_interval))
            continue
        fi

        # Parse JSON response
        if ! command -v jq &> /dev/null; then
            # Basic parsing without jq
            if echo "$response" | grep -q '"result":null'; then
                log_error "Task not found (result: null)"
                return 1
            fi

            local status
            status=$(echo "$response" | grep -o '"state":"[^"]*"' | head -1 | sed 's/"state":"\([^"]*\)"/\1/')

            if [ -n "$status" ]; then
                log_info "Task status: ${status}"

                case "$status" in
                    "completed")
                        log_success "Task completed successfully!"
                        return 0
                        ;;
                    "failed")
                        log_error "Task failed"
                        return 1
                        ;;
                    "canceled")
                        log_error "Task was canceled"
                        return 1
                        ;;
                    "rejected")
                        log_error "Task was rejected"
                        return 1
                        ;;
                    "working"|"submitted")
                        log_info "Task still processing (${status})..."
                        ;;
                    *)
                        log_warn "Unknown status: ${status}"
                        ;;
                esac
            else
                log_warn "Could not parse status from response (jq not available)"
                echo "Response: $response"
            fi
        else
            # Parse with jq
            if echo "$response" | jq -e '.result == null' > /dev/null 2>&1; then
                log_error "Task not found (result: null)"
                return 1
            fi

            if echo "$response" | jq -e '.error' > /dev/null 2>&1; then
                local error_code=$(echo "$response" | jq -r '.error.code')
                local error_message=$(echo "$response" | jq -r '.error.message')
                log_error "JSON-RPC error during polling: ${error_message} (code: ${error_code})"
                return 1
            fi

            local status
            status=$(echo "$response" | jq -r '.result.status.state // empty')

            if [ -n "$status" ]; then
                log_info "Task status: ${status}"

                case "$status" in
                    "completed")
                        log_success "Task completed successfully!"

                        # Store the full response for metadata validation
                        TASK_RESPONSE="$response"

                        # Extract audio_id from metadata for later validation
                        AUDIO_ID=$(echo "$response" | jq -r '.result.metadata.audio_track_id // empty')
                        if [ -n "$AUDIO_ID" ] && [ "$AUDIO_ID" != "null" ]; then
                            log_info "Extracted audio_track_id: ${AUDIO_ID}"
                        fi

                        return 0
                        ;;
                    "failed"|"canceled"|"rejected")
                        handle_task_failure "$status" "$response"
                        return 1
                        ;;
                    "working"|"submitted")
                        log_info "Task still processing (${status})..."
                        ;;
                    *)
                        log_warn "Unknown status: ${status}"
                        ;;
                esac
            else
                log_warn "Could not parse status from response"
                echo "Response: $response"
            fi
        fi

        # Wait before next attempt
        sleep $backoff_interval
        total_wait_time=$((total_wait_time + backoff_interval))

        # Exponential backoff (cap at 30 seconds)
        backoff_interval=$((backoff_interval * 2))
        if [ $backoff_interval -gt 30 ]; then
            backoff_interval=30
        fi

        attempt=$((attempt + 1))
    done

    log_error "Polling timeout after ${MAX_POLL_ATTEMPTS} attempts (${total_wait_time}s total)"
    return 1
}

# Function: validate_metadata
# Validates task metadata contains expected audio processing results
validate_metadata() {
    echo "4. Validating task metadata..."

    if [ -z "$TASK_RESPONSE" ]; then
        log_error "No task response available for metadata validation"
        return 1
    fi

    if ! command -v jq &> /dev/null; then
        log_warn "jq not available, skipping detailed metadata validation"
        log_info "Basic validation: task completed successfully"
        return 0
    fi

    # Check metadata exists
    if ! echo "$TASK_RESPONSE" | jq -e '.result.metadata' > /dev/null 2>&1; then
        log_error "No metadata found in task response"
        return 1
    fi

    log_success "Task metadata found"

    # Check for audio_track_id
    local audio_track_id
    audio_track_id=$(echo "$TASK_RESPONSE" | jq -r '.result.metadata.audio_track_id // empty')
    if [ -z "$audio_track_id" ] || [ "$audio_track_id" = "null" ]; then
        log_error "audio_track_id missing from task metadata"
        return 1
    fi

    log_success "Audio track ID found: ${audio_track_id}"

    # Update AUDIO_ID for database verification
    AUDIO_ID="$audio_track_id"

    # Check for processing_result
    if ! echo "$TASK_RESPONSE" | jq -e '.result.metadata.processing_result' > /dev/null 2>&1; then
        log_error "processing_result missing from task metadata"
        return 1
    fi

    log_success "Processing result found in metadata"

    # Validate processing result structure
    local processing_result
    processing_result=$(echo "$TASK_RESPONSE" | jq -r '.result.metadata.processing_result')

    # Check success field
    local success
    success=$(echo "$processing_result" | jq -r '.success // empty')
    if [ "$success" != "true" ]; then
        log_error "Processing result success is not true"
        return 1
    fi

    # Check required fields in processing result
    local required_fields=("audio_id" "metadata" "resources" "processing_time")
    for field in "${required_fields[@]}"; do
        if ! echo "$processing_result" | jq -e ".${field}" > /dev/null 2>&1; then
            log_error "Required field '${field}' missing from processing result"
            return 1
        fi
    done

    log_success "All required processing result fields present"

    # Validate metadata structure in processing result
    if ! echo "$processing_result" | jq -e '.metadata.product' > /dev/null 2>&1; then
        log_error "metadata.product missing from processing result"
        return 1
    fi

    if ! echo "$processing_result" | jq -e '.metadata.format' > /dev/null 2>&1; then
        log_error "metadata.format missing from processing result"
        return 1
    fi

    log_success "Processing result metadata structure is valid"

    # Validate product metadata has expected fields
    local product_fields=("title")
    for field in "${product_fields[@]}"; do
        if ! echo "$processing_result" | jq -e ".metadata.product.${field}" > /dev/null 2>&1; then
            log_error "Required product field '${field}' missing from processing result metadata"
            return 1
        fi
    done

    log_success "Product metadata contains required fields"

    # Validate format metadata has expected fields
    local format_fields=("duration" "channels" "sample_rate" "bitrate")
    for field in "${format_fields[@]}"; do
        if ! echo "$processing_result" | jq -e ".metadata.format.${field}" > /dev/null 2>&1; then
            log_error "Required format field '${field}' missing from processing result metadata"
            return 1
        fi
    done

    log_success "Format metadata contains required fields"

    # Extract and display some key values for verification
    local title artist duration processing_time
    title=$(echo "$processing_result" | jq -r '.metadata.product.title // "N/A"')
    artist=$(echo "$processing_result" | jq -r '.metadata.product.artist // "N/A"')
    duration=$(echo "$processing_result" | jq -r '.metadata.format.duration // "N/A"')
    processing_time=$(echo "$processing_result" | jq -r '.processing_time // "N/A"')

    log_info "Extracted audio metadata:"
    log_info "  Title: ${title}"
    log_info "  Artist: ${artist}"
    log_info "  Duration: ${duration} seconds"
    log_info "  Processing time: ${processing_time} seconds"

    log_success "Metadata validation completed successfully"
    return 0
}

# Function: verify_db_linkage
# Verifies bidirectional database linkage between A2A tasks and audio tracks
verify_db_linkage() {
    echo "5. Verifying database linkage..."

    if [ -z "$TASK_ID" ] || [ -z "$AUDIO_ID" ]; then
        log_error "Missing TASK_ID or AUDIO_ID for database verification"
        return 1
    fi

    log_info "Checking bidirectional linkage between task ${TASK_ID} and audio track ${AUDIO_ID}"

    # Check 1: Verify audio_tracks.a2a_task_id links to A2A task
    echo "   Checking audio_tracks.a2a_task_id → A2A task linkage..."

    local db_a2a_task_id
    db_a2a_task_id=$(docker-compose exec -T postgres psql -U loist_user -d loist_mvp -t -c \
        "SELECT a2a_task_id FROM audio_tracks WHERE id = '${AUDIO_ID}';" 2>/dev/null | tr -d '[:space:]')

    if [ $? -ne 0 ]; then
        log_error "Failed to query database for audio_tracks linkage (database connection error)"
        log_info "This may indicate PostgreSQL is not running or accessible"
        return 1
    fi

    if [ -z "$db_a2a_task_id" ]; then
        log_error "No audio track found with ID ${AUDIO_ID}"
        return 1
    fi

    if [ "$db_a2a_task_id" != "$TASK_ID" ]; then
        log_error "Database linkage mismatch: audio_tracks.a2a_task_id = '${db_a2a_task_id}', expected '${TASK_ID}'"
        return 1
    fi

    log_success "✓ audio_tracks.a2a_task_id correctly links to task ${TASK_ID}"

    # Check 2: Verify task.metadata.audio_track_id links back (if available)
    echo "   Checking A2A task metadata → audio_tracks linkage..."

    if ! command -v jq &> /dev/null; then
        log_warn "jq not available, skipping reverse linkage check from task metadata"
    else
        # Note: In the current implementation, we can't directly query the A2A tasks table
        # since it's managed by the SDK and may have different schema/structure.
        # However, we can verify the linkage is stored in task metadata during creation.

        local task_audio_track_id
        task_audio_track_id=$(echo "$TASK_RESPONSE" | jq -r '.result.metadata.audio_track_id // empty')

        if [ -n "$task_audio_track_id" ] && [ "$task_audio_track_id" != "null" ]; then
            if [ "$task_audio_track_id" != "$AUDIO_ID" ]; then
                log_error "Task metadata linkage mismatch: task.metadata.audio_track_id = '${task_audio_track_id}', expected '${AUDIO_ID}'"
                return 1
            fi
            log_success "✓ task.metadata.audio_track_id correctly links to audio track ${AUDIO_ID}"
        else
            log_warn "Task metadata does not contain audio_track_id (may be expected depending on implementation)"
        fi
    fi

    # Check 3: Verify the audio track actually exists and has expected metadata
    echo "   Verifying audio track exists with valid metadata..."

    local track_count
    track_count=$(docker-compose exec -T postgres psql -U loist_user -d loist_mvp -t -c \
        "SELECT COUNT(*) FROM audio_tracks WHERE id = '${AUDIO_ID}' AND status = 'COMPLETED';" 2>/dev/null | tr -d '[:space:]')

    if [ $? -ne 0 ]; then
        log_error "Failed to verify audio track status"
        return 1
    fi

    if [ "$track_count" != "1" ]; then
        log_error "Audio track ${AUDIO_ID} not found or not in COMPLETED status (found ${track_count} records)"
        return 1
    fi

    log_success "✓ Audio track ${AUDIO_ID} exists and is in COMPLETED status"

    # Check 4: Verify the audio track has required metadata fields
    local has_metadata
    has_metadata=$(docker-compose exec -T postgres psql -U loist_user -d loist_mvp -t -c \
        "SELECT CASE WHEN title IS NOT NULL AND duration_seconds IS NOT NULL THEN 'true' ELSE 'false' END FROM audio_tracks WHERE id = '${AUDIO_ID}';" 2>/dev/null | tr -d '[:space:]')

    if [ "$has_metadata" != "true" ]; then
        log_error "Audio track ${AUDIO_ID} is missing required metadata (title, duration)"
        return 1
    fi

    log_success "✓ Audio track has required metadata fields"

    log_success "Database linkage verification completed successfully"
    log_info "Bidirectional linkage confirmed: A2A task ↔ Audio track"
    return 0
}

# Function: cleanup
# Cleanup function called on exit
cleanup() {
    local exit_code=$?

    if [ $exit_code -ne 0 ]; then
        echo
        log_error "Test failed with exit code ${exit_code}"
        echo "Debug information:"
        echo "  TASK_ID: ${TASK_ID:-N/A}"
        echo "  AUDIO_ID: ${AUDIO_ID:-N/A}"
        echo "  Test audio URL: ${TEST_AUDIO_URL}"
        echo
        echo "Troubleshooting:"
        echo "  - Check docker-compose logs: docker-compose logs --tail=50"
        echo "  - Verify servers are running: docker-compose ps"
        echo "  - Check A2A server logs: docker-compose logs a2a-server --tail=20"
        echo "  - Check MCP server logs: docker-compose logs mcp-server --tail=20"
    else
        echo
        log_success "All tests passed! 🎉"
    fi
}

# Trap to ensure cleanup runs on exit
trap cleanup EXIT

# Function: handle_task_failure
# Handles failed, canceled, or rejected tasks
handle_task_failure() {
    local status="$1"
    local response="$2"

    case "$status" in
        "failed")
            log_error "Task processing failed"

            # Check if we have error in metadata
            if command -v jq &> /dev/null && [ -n "$response" ]; then
                if echo "$response" | jq -e '.result.metadata.error' > /dev/null 2>&1; then
                    log_info "✓ Error found in task metadata"
                    local error_details
                    error_details=$(echo "$response" | jq -r '.result.metadata.error // empty')
                    log_info "Error details: ${error_details}"
                else
                    log_warn "Expected error in task.metadata.error, but not found"
                fi
            fi

            return 1
            ;;
        "canceled")
            log_error "Task was canceled"
            return 1
            ;;
        "rejected")
            log_error "Task was rejected"
            return 1
            ;;
        *)
            log_error "Unknown terminal state: ${status}"
            return 1
            ;;
    esac
}

# Function: send_message
# Sends message/send JSON-RPC request to A2A server
send_message() {
    echo "2. Sending message/send JSON-RPC request..."

    local request_id="e2e-test-$(date +%s)"
    local json_payload=$(cat <<EOF
{
  "jsonrpc": "2.0",
  "id": "${request_id}",
  "method": "message/send",
  "params": {
    "message": {
      "messageId": "${request_id}",
      "role": "user",
      "parts": [
        {
          "type": "text",
          "text": "Process this audio: ${TEST_AUDIO_URL}"
        }
      ]
    }
  }
}
EOF
)

    log_info "Sending JSON-RPC request to ${A2A_URL}/"
    log_info "Request ID: ${request_id}"

    # Send the request and capture response
    local response
    response=$(curl -s -X POST "${A2A_URL}/" \
        -H "Content-Type: application/json" \
        -d "${json_payload}" \
        --max-time 180)

    # Check if curl succeeded
    if [ $? -ne 0 ]; then
        log_error "Failed to send message/send request (curl error)"
        return 1
    fi

    # Parse JSON response
    if ! command -v jq &> /dev/null; then
        log_warn "jq not available, using basic JSON parsing"
        # Basic parsing without jq
        if echo "$response" | grep -q '"result"'; then
            TASK_ID=$(echo "$response" | grep -o '"id":"[^"]*"' | head -1 | sed 's/"id":"\([^"]*\)"/\1/')
            if [ -n "$TASK_ID" ]; then
                log_success "Task created with ID: ${TASK_ID}"
                return 0
            fi
        fi

        if echo "$response" | grep -q '"error"'; then
            log_error "JSON-RPC error response received"
            echo "Response: $response"
            return 1
        fi

        log_error "Unable to parse JSON response (jq not available)"
        echo "Response: $response"
        return 1
    fi

    # Parse with jq if available
    if echo "$response" | jq -e '.result' > /dev/null 2>&1; then
        TASK_ID=$(echo "$response" | jq -r '.result.id')
        local task_status=$(echo "$response" | jq -r '.result.status.state')

        if [ "$TASK_ID" = "null" ] || [ -z "$TASK_ID" ]; then
            log_error "Task ID not found in response"
            echo "Response: $response"
            return 1
        fi

        log_success "Task created successfully"
        log_info "Task ID: ${TASK_ID}"
        log_info "Initial status: ${task_status}"
        return 0
    fi

    if echo "$response" | jq -e '.error' > /dev/null 2>&1; then
        local error_code=$(echo "$response" | jq -r '.error.code')
        local error_message=$(echo "$response" | jq -r '.error.message')

        log_error "JSON-RPC error: ${error_message} (code: ${error_code})"
        echo "Full response: $response"
        return 1
    fi

    log_error "Invalid JSON-RPC response format"
    echo "Response: $response"
    return 1
}

# Function: wait_for_readiness
# Waits for both MCP and A2A servers to be ready
wait_for_readiness() {
    echo "1. Checking docker-compose readiness..."

    # Check if docker-compose is running
    if ! docker-compose ps | grep -q "Up"; then
        log_warn "Docker containers not running. Starting docker-compose..."
        docker-compose up -d

        # Wait a bit for containers to start
        sleep 5
    fi

    log_info "Docker containers are running"

    # Wait for MCP server (port 8080)
    echo "   Waiting for MCP server (port 8080)..."
    local mcp_ready=false
    local wait_time=0

    while [ $wait_time -lt $MAX_READINESS_WAIT ]; do
        if curl -s -f "${MCP_URL}/health/ready" > /dev/null 2>&1; then
            log_success "MCP server ready on port 8080"
            mcp_ready=true
            break
        fi

        sleep 2
        wait_time=$((wait_time + 2))
        echo "      ... waiting (${wait_time}s/${MAX_READINESS_WAIT}s)"
    done

    if [ "$mcp_ready" = false ]; then
        log_error "MCP server did not become ready within ${MAX_READINESS_WAIT}s"
        return 1
    fi

    # Wait for A2A server (port 8081)
    echo "   Waiting for A2A server (port 8081)..."
    local a2a_ready=false
    wait_time=0

    while [ $wait_time -lt $MAX_READINESS_WAIT ]; do
        if curl -s -f "${A2A_URL}/.well-known/agent-card.json" > /dev/null 2>&1; then
            log_success "A2A server ready on port 8081"
            a2a_ready=true
            break
        fi

        sleep 2
        wait_time=$((wait_time + 2))
        echo "      ... waiting (${wait_time}s/${MAX_READINESS_WAIT}s)"
    done

    if [ "$a2a_ready" = false ]; then
        log_error "A2A server did not become ready within ${MAX_READINESS_WAIT}s"
        return 1
    fi

    log_success "Both servers are ready"
    return 0
}

# Main execution
main() {
    # Pre-flight checks
    echo "Performing pre-flight checks..."

    # Check if docker-compose is available
    if ! command -v docker-compose &> /dev/null; then
        log_error "docker-compose command not found. Please install Docker and docker-compose."
        exit 1
    fi

    # Check if docker is running
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running. Please start Docker."
        exit 1
    fi

    log_success "Pre-flight checks passed"

    # Step 1: Wait for readiness
    if ! wait_for_readiness; then
        log_error "Server readiness check failed"
        exit 1
    fi

    # Step 2: Send message/send request
    if ! send_message; then
        log_error "message/send request failed"
        exit 1
    fi

    # Step 3: Poll tasks/get until completion
    if ! poll_task; then
        log_error "Task polling failed or timed out"
        exit 1
    fi

    # Step 4: Validate task metadata
    if ! validate_metadata; then
        log_error "Metadata validation failed"
        exit 1
    fi

    # Step 5: Verify database linkage
    if ! verify_db_linkage; then
        log_error "Database linkage verification failed"
        exit 1
    fi

    echo
    echo "🎉 A2A E2E test harness completed successfully!"
    echo "   Full workflow validation passed: task creation → processing → metadata → database linkage"
    echo
    echo "📋 Summary:"
    echo "   ✅ Docker compose readiness"
    echo "   ✅ message/send JSON-RPC request"
    echo "   ✅ tasks/get polling until completion"
    echo "   ✅ Task metadata validation"
    echo "   ✅ Database bidirectional linkage"
    echo
}

# Run main function
main "$@"
