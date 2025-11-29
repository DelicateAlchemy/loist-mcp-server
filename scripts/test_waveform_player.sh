#!/bin/bash

# Waveform Player Testing Script
# Tests waveform player functionality locally with ngrok tunneling

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DOCKER_COMPOSE_FILE="$PROJECT_ROOT/docker-compose.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check Docker
    if ! command_exists docker; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    # Check docker-compose
    if ! command_exists docker-compose; then
        log_error "docker-compose is not installed. Please install docker-compose first."
        exit 1
    fi

    # Check ngrok
    if ! command_exists ngrok; then
        log_warning "ngrok is not installed. Please install ngrok from https://ngrok.com/"
        log_warning "You can also run the tests without ngrok by skipping iframe embedding tests."
        NGROK_AVAILABLE=false
    else
        NGROK_AVAILABLE=true
    fi

    # Check curl
    if ! command_exists curl; then
        log_error "curl is not installed. Please install curl first."
        exit 1
    fi

    log_success "Prerequisites check completed"
}

# Start Docker environment
start_docker() {
    log_info "Starting Docker environment..."

    cd "$PROJECT_ROOT"

    # Check if containers are already running
    if docker-compose ps | grep -q "Up"; then
        log_warning "Docker containers are already running"
    else
        log_info "Starting containers with docker-compose..."
        docker-compose up -d

        # Wait for services to be ready
        log_info "Waiting for services to start..."
        sleep 10

        # Check if database is ready
        log_info "Checking database connectivity..."
        for i in {1..30}; do
            if docker-compose exec -T mcp-server python3 -c "
import sys
sys.path.insert(0, '/app')
from database import get_connection
try:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT 1')
        print('Database ready')
        sys.exit(0)
except Exception as e:
    print(f'Database not ready: {e}')
    sys.exit(1)
" 2>/dev/null; then
                log_success "Database is ready"
                break
            fi
            log_info "Waiting for database... ($i/30)"
            sleep 2
        done

        if [ $i -eq 30 ]; then
            log_error "Database failed to start within timeout"
            exit 1
        fi
    fi

    log_success "Docker environment started"
}

# Get test audio ID
get_test_audio_id() {
    log_info "Getting test audio ID..."

    # Try to get the first available audio track
    TEST_AUDIO_ID=$(docker-compose exec -T mcp-server python3 -c "
import sys
sys.path.insert(0, '/app')
from database import get_connection
import psycopg2.extras

try:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT id FROM audio_tracks LIMIT 1')
            result = cur.fetchone()
            if result:
                print(result['id'])
            else:
                print('')
except Exception as e:
    print(f'Error: {e}')
" 2>/dev/null)

    if [ -z "$TEST_AUDIO_ID" ]; then
        log_error "No audio tracks found in database. Please add an audio track first."
        log_info "You can use the process_audio_complete MCP tool to add audio tracks."
        exit 1
    fi

    log_success "Found test audio ID: $TEST_AUDIO_ID"
}

# Start ngrok tunnel
start_ngrok() {
    if [ "$NGROK_AVAILABLE" = false ]; then
        log_warning "ngrok not available, skipping ngrok setup"
        NGROK_URL=""
        return
    fi

    log_info "Starting ngrok tunnel..."

    # Check if ngrok is already running
    if pgrep -x "ngrok" > /dev/null; then
        log_warning "ngrok is already running"
        # Get the existing ngrok URL
        NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"[^"]*' | grep -o 'https://[^"]*')
    else
        # Start ngrok
        ngrok http 8080 >/dev/null &
        NGROK_PID=$!

        # Wait for ngrok to start
        log_info "Waiting for ngrok to start..."
        for i in {1..30}; do
            if NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | grep -o '"public_url":"[^"]*' | grep -o 'https://[^"]*'); then
                break
            fi
            sleep 1
        done

        if [ -z "$NGROK_URL" ]; then
            log_error "Failed to get ngrok URL"
            kill $NGROK_PID 2>/dev/null || true
            exit 1
        fi
    fi

    log_success "ngrok tunnel active at: $NGROK_URL"

    # Update environment variable for the running container
    docker-compose exec -T mcp-server bash -c "export EMBED_BASE_URL=$NGROK_URL" || true
}

# Test endpoints
test_endpoints() {
    log_info "Testing waveform player endpoints..."

    BASE_URL="http://localhost:8080"

    # Test standard embed endpoint
    log_info "Testing standard embed endpoint..."
    if curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/embed/$TEST_AUDIO_ID" | grep -q "200"; then
        log_success "Standard embed endpoint works"
    else
        log_error "Standard embed endpoint failed"
    fi

    # Test waveform endpoints
    endpoints=(
        "/embed/$TEST_AUDIO_ID/waveform"
        "/embed/$TEST_AUDIO_ID/waveform/mobile"
        "/embed/$TEST_AUDIO_ID/waveform/desktop"
    )

    for endpoint in "${endpoints[@]}"; do
        log_info "Testing $endpoint..."
        if curl -s -o /dev/null -w "%{http_code}" "$BASE_URL$endpoint" | grep -q "200"; then
            log_success "$endpoint works"
        else
            log_error "$endpoint failed"
        fi
    done
}

# Test query parameter template selection
test_template_query_params() {
    log_info "Testing query parameter template selection..."

    BASE_URL="http://localhost:8080"

    # Test standard template (default)
    log_info "Testing standard template (default)..."
    if curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/embed/$TEST_AUDIO_ID" | grep -q "200"; then
        log_success "Standard template works"
    else
        log_error "Standard template failed"
    fi

    # Test waveform template via query parameter
    log_info "Testing waveform template via query parameter..."
    response=$(curl -s "$BASE_URL/embed/$TEST_AUDIO_ID?template=waveform")
    if echo "$response" | grep -q "embed-waveform.html\|waveform-container\|interactive_mode"; then
        log_success "Waveform template via query parameter works"
    else
        log_error "Waveform template via query parameter failed"
        log_info "Response preview: $(echo "$response" | head -c 200)..."
    fi

    # Test invalid template falls back to standard
    log_info "Testing invalid template parameter..."
    response=$(curl -s "$BASE_URL/embed/$TEST_AUDIO_ID?template=invalid")
    if echo "$response" | grep -q "embed.html" && ! echo "$response" | grep -q "embed-waveform.html"; then
        log_success "Invalid template falls back to standard"
    else
        log_warning "Invalid template fallback behavior unclear"
    fi

    # Test waveform template with different user agents (device detection)
    log_info "Testing waveform template with mobile user agent..."
    response=$(curl -s -H "User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15" \
        "$BASE_URL/embed/$TEST_AUDIO_ID?template=waveform")
    if echo "$response" | grep -q "is_mobile.*true\|device_type.*mobile"; then
        log_success "Mobile device detection in waveform template works"
    else
        log_warning "Mobile device detection in waveform template may not be working"
    fi

    log_info "Testing waveform template with desktop user agent..."
    response=$(curl -s -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" \
        "$BASE_URL/embed/$TEST_AUDIO_ID?template=waveform")
    if echo "$response" | grep -q "is_desktop.*true\|device_type.*desktop"; then
        log_success "Desktop device detection in waveform template works"
    else
        log_warning "Desktop device detection in waveform template may not be working"
    fi
}

# Test device detection
test_device_detection() {
    log_info "Testing device detection..."

    BASE_URL="http://localhost:8080"

    # Test auto-detection (no device param)
    log_info "Testing auto device detection..."
    response=$(curl -s "$BASE_URL/embed/$TEST_AUDIO_ID/waveform")
    if echo "$response" | grep -q "device_type.*desktop\|device_type.*mobile"; then
        log_success "Auto device detection works"
    else
        log_warning "Auto device detection may not be working as expected"
    fi

    # Test explicit device override
    log_info "Testing explicit device override..."
    mobile_response=$(curl -s "$BASE_URL/embed/$TEST_AUDIO_ID/waveform?device=mobile")
    if echo "$mobile_response" | grep -q "device_type.*mobile"; then
        log_success "Mobile device override works"
    else
        log_error "Mobile device override failed"
    fi

    desktop_response=$(curl -s "$BASE_URL/embed/$TEST_AUDIO_ID/waveform?device=desktop")
    if echo "$desktop_response" | grep -q "device_type.*desktop"; then
        log_success "Desktop device override works"
    else
        log_error "Desktop device override failed"
    fi
}

# Test MCP tools
test_mcp_tools() {
    log_info "Testing MCP tools..."

    # Test list_embed_templates
    log_info "Testing list_embed_templates MCP tool..."
    result=$(docker-compose exec -T mcp-server python3 -c "
import sys
sys.path.insert(0, '/app')
import asyncio
from src.server import list_embed_templates

async def test():
    result = await list_embed_templates()
    if result.get('success'):
        print('SUCCESS')
        templates = result.get('templates', [])
        print(f'Found {len(templates)} templates')
        for template in templates:
            print(f'- {template[\"name\"]}: {template[\"id\"]}')
    else:
        print('FAILED')
        print(result.get('error', 'Unknown error'))

asyncio.run(test())
" 2>/dev/null)

    if echo "$result" | grep -q "SUCCESS"; then
        log_success "list_embed_templates MCP tool works"
        echo "$result" | grep -E "(Found|- .*:)" | sed 's/^/  /'
    else
        log_error "list_embed_templates MCP tool failed"
    fi

    # Test get_embed_url
    log_info "Testing get_embed_url MCP tool..."
    result=$(docker-compose exec -T mcp-server python3 -c "
import sys
sys.path.insert(0, '/app')
import asyncio
from src.server import get_embed_url

async def test():
    result = await get_embed_url('$TEST_AUDIO_ID', 'waveform')
    if result.get('success'):
        print('SUCCESS')
        print(f'Embed URL: {result.get(\"embedUrl\", \"N/A\")}')
        print(f'Template: {result.get(\"template\", \"N/A\")}')
        print(f'Waveform available: {result.get(\"waveformAvailable\", \"N/A\")}')
    else:
        print('FAILED')
        print(result.get('error', 'Unknown error'))

asyncio.run(test())
" 2>/dev/null)

    if echo "$result" | grep -q "SUCCESS"; then
        log_success "get_embed_url MCP tool works"
        echo "$result" | grep -E "(Embed URL|Template|Waveform available)" | sed 's/^/  /'
    else
        log_error "get_embed_url MCP tool failed"
    fi

    # Test check_waveform_availability
    log_info "Testing check_waveform_availability MCP tool..."
    result=$(docker-compose exec -T mcp-server python3 -c "
import sys
sys.path.insert(0, '/app')
import asyncio
from src.server import check_waveform_availability

async def test():
    result = await check_waveform_availability('$TEST_AUDIO_ID')
    if result.get('success'):
        print('SUCCESS')
        print(f'Waveform available: {result.get(\"waveformAvailable\", \"N/A\")}')
        if result.get('waveformUrl'):
            print('Waveform URL available')
    else:
        print('FAILED')
        print(result.get('error', 'Unknown error'))

asyncio.run(test())
" 2>/dev/null)

    if echo "$result" | grep -q "SUCCESS"; then
        log_success "check_waveform_availability MCP tool works"
        echo "$result" | grep -E "(Waveform available|Waveform URL)" | sed 's/^/  /'
    else
        log_error "check_waveform_availability MCP tool failed"
    fi
}

# Test iframe embedding
test_iframe_embedding() {
    if [ "$NGROK_AVAILABLE" = false ] || [ -z "$NGROK_URL" ]; then
        log_warning "ngrok not available or not running, skipping iframe embedding test"
        return
    fi

    log_info "Testing iframe embedding..."

    # Create a simple test HTML file
    TEST_HTML="$PROJECT_ROOT/test_waveform_iframe.html"
    cat > "$TEST_HTML" << EOF
<!DOCTYPE html>
<html>
<head>
    <title>Waveform Player Test</title>
    <style>
        iframe { width: 100%; height: 200px; border: 1px solid #ccc; }
        .test-section { margin: 20px 0; padding: 10px; border: 1px solid #ddd; }
    </style>
</head>
<body>
    <h1>Waveform Player Iframe Test</h1>

    <div class="test-section">
        <h2>Standard Player</h2>
        <iframe src="$NGROK_URL/embed/$TEST_AUDIO_ID" title="Standard Player"></iframe>
    </div>

    <div class="test-section">
        <h2>Waveform Player (Auto-detect)</h2>
        <iframe src="$NGROK_URL/embed/$TEST_AUDIO_ID/waveform" title="Waveform Player"></iframe>
    </div>

    <div class="test-section">
        <h2>Waveform Player (Mobile)</h2>
        <iframe src="$NGROK_URL/embed/$TEST_AUDIO_ID/waveform/mobile" title="Mobile Waveform"></iframe>
    </div>

    <div class="test-section">
        <h2>Waveform Player (Desktop)</h2>
        <iframe src="$NGROK_URL/embed/$TEST_AUDIO_ID/waveform/desktop" title="Desktop Waveform"></iframe>
    </div>
</body>
</html>
EOF

    log_success "Created test iframe page: $TEST_HTML"
    log_info "Open $TEST_HTML in your browser to test iframe embedding"
    log_info "Test URL: file://$TEST_HTML"
}

# Cleanup function
cleanup() {
    log_info "Cleaning up..."

    # Kill ngrok if we started it
    if [ -n "$NGROK_PID" ]; then
        kill "$NGROK_PID" 2>/dev/null || true
        log_info "Stopped ngrok"
    fi

    # Remove test file
    if [ -f "$PROJECT_ROOT/test_waveform_iframe.html" ]; then
        rm "$PROJECT_ROOT/test_waveform_iframe.html"
        log_info "Removed test HTML file"
    fi
}

# Main test function
run_tests() {
    log_info "Starting Waveform Player Tests"
    log_info "================================"

    check_prerequisites
    start_docker
    get_test_audio_id
    start_ngrok
    test_endpoints
    test_template_query_params
    test_device_detection
    test_mcp_tools
    test_iframe_embedding

    log_info "================================"
    log_success "Waveform Player Tests Completed"

    if [ "$NGROK_AVAILABLE" = true ] && [ -n "$NGROK_URL" ]; then
        log_info "Test URLs:"
        log_info "  Standard Player: $NGROK_URL/embed/$TEST_AUDIO_ID"
        log_info "  Waveform Player: $NGROK_URL/embed/$TEST_AUDIO_ID/waveform"
        log_info "  Mobile Waveform: $NGROK_URL/embed/$TEST_AUDIO_ID/waveform/mobile"
        log_info "  Desktop Waveform: $NGROK_URL/embed/$TEST_AUDIO_ID/waveform/desktop"
        log_info "  Iframe Test Page: file://$PROJECT_ROOT/test_waveform_iframe.html"
    fi
}

# Parse command line arguments
SKIP_IFRAME=false
for arg in "$@"; do
    case $arg in
        --skip-iframe)
            SKIP_IFRAME=true
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --skip-iframe    Skip iframe embedding tests"
            echo "  --help          Show this help message"
            echo ""
            echo "This script tests the waveform player functionality including:"
            echo "- Docker environment setup"
            echo "- Endpoint availability"
            echo "- Device detection"
            echo "- MCP tools"
            echo "- Iframe embedding (requires ngrok)"
            exit 0
            ;;
    esac
done

# Trap for cleanup
trap cleanup EXIT

# Run tests
run_tests
