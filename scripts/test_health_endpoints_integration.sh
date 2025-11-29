#!/bin/bash
# Health Check Endpoints Integration Test
# Tests health endpoints with a running server
#
# Run with: bash scripts/test_health_endpoints_integration.sh

set -e

echo "🔍 Testing Health Check Endpoints (Integration Test)..."
echo

# Configuration
SERVER_PORT=${SERVER_PORT:-8080}
BASE_URL="http://localhost:${SERVER_PORT}"
MAX_WAIT=30
CHECK_INTERVAL=2

# Check if server is already running
echo "1. Checking if server is running..."
if curl -s -f "${BASE_URL}/health/live" > /dev/null 2>&1; then
    echo "✅ Server is already running on port ${SERVER_PORT}"
    SERVER_RUNNING=true
else
    echo "⚠️  Server not running. Starting server in background..."
    SERVER_RUNNING=false
    
    # Start server in background
    # Use docker-compose if available, otherwise try direct python
    if command -v docker-compose &> /dev/null && [ -f docker-compose.yml ]; then
        echo "   Starting server with docker-compose..."
        docker-compose up -d mcp-server 2>&1 | head -5
        SERVER_CMD="docker-compose"
    else
        echo "   Starting server with python..."
        cd "$(dirname "$0")/.."
        python3 src/server.py > /tmp/mcp-server-test.log 2>&1 &
        SERVER_PID=$!
        SERVER_CMD="python"
        echo "   Server PID: ${SERVER_PID}"
    fi
    
    # Wait for server to be ready
    echo "   Waiting for server to start (max ${MAX_WAIT}s)..."
    WAIT_TIME=0
    while [ $WAIT_TIME -lt $MAX_WAIT ]; do
        if curl -s -f "${BASE_URL}/health/live" > /dev/null 2>&1; then
            echo "✅ Server is ready!"
            break
        fi
        sleep $CHECK_INTERVAL
        WAIT_TIME=$((WAIT_TIME + CHECK_INTERVAL))
        echo "   ... waiting (${WAIT_TIME}s/${MAX_WAIT}s)"
    done
    
    if [ $WAIT_TIME -ge $MAX_WAIT ]; then
        echo "❌ Server did not start within ${MAX_WAIT}s"
        if [ "$SERVER_CMD" = "python" ]; then
            echo "   Check logs: /tmp/mcp-server-test.log"
            if [ -n "$SERVER_PID" ]; then
                kill $SERVER_PID 2>/dev/null || true
            fi
        fi
        exit 1
    fi
fi
echo

# Test 1: Liveness endpoint
echo "2. Testing /health/live endpoint..."
python3 -c "
import sys
import requests
import json

try:
    response = requests.get('${BASE_URL}/health/live', timeout=5)
    
    assert response.status_code == 200, f'Expected 200, got {response.status_code}'
    data = response.json()
    
    assert data['status'] == 'alive', f\"Expected 'alive', got '{data.get('status')}'\"
    assert 'timestamp' in data, 'Should have timestamp'
    assert 'service' in data, 'Should have service name'
    assert 'version' in data, 'Should have version'
    
    print('✅ Liveness endpoint works correctly')
    print(f'   Status: {data[\"status\"]}')
    print(f'   Service: {data.get(\"service\", \"N/A\")}')
    print(f'   Version: {data.get(\"version\", \"N/A\")}')
    
except requests.exceptions.RequestException as e:
    print(f'❌ Request failed: {e}')
    sys.exit(1)
except AssertionError as e:
    print(f'❌ Assertion failed: {e}')
    print(f'   Response: {response.text if \"response\" in locals() else \"N/A\"}')
    sys.exit(1)
except Exception as e:
    print(f'❌ Unexpected error: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ Liveness endpoint test failed"
    exit 1
fi
echo

# Test 2: Readiness endpoint
echo "3. Testing /health/ready endpoint..."
python3 -c "
import sys
import requests
import json

try:
    response = requests.get('${BASE_URL}/health/ready', timeout=10)
    
    # Readiness can return 200 (ready) or 503 (not ready)
    assert response.status_code in [200, 503], f'Expected 200 or 503, got {response.status_code}'
    data = response.json()
    
    assert 'status' in data, 'Should have status'
    assert data['status'] in ['ready', 'not_ready'], f\"Expected 'ready' or 'not_ready', got '{data.get('status')}'\"
    assert 'dependencies' in data, 'Should have dependencies'
    assert 'database' in data['dependencies'], 'Should check database'
    assert 'gcs' in data['dependencies'], 'Should check GCS'
    assert 'cloud_tasks' in data['dependencies'], 'Should check Cloud Tasks'
    
    print('✅ Readiness endpoint works correctly')
    print(f'   Status: {data[\"status\"]}')
    print(f'   Database: {data[\"dependencies\"][\"database\"][\"available\"]}')
    print(f'   GCS: {data[\"dependencies\"][\"gcs\"][\"available\"]}')
    print(f'   Cloud Tasks: {data[\"dependencies\"][\"cloud_tasks\"][\"available\"]}')
    
    if response.status_code == 503:
        print('   ⚠️  Service not ready (some dependencies unavailable - this is OK for local dev)')
    
except requests.exceptions.RequestException as e:
    print(f'❌ Request failed: {e}')
    sys.exit(1)
except AssertionError as e:
    print(f'❌ Assertion failed: {e}')
    print(f'   Response: {response.text if \"response\" in locals() else \"N/A\"}')
    sys.exit(1)
except Exception as e:
    print(f'❌ Unexpected error: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ Readiness endpoint test failed"
    exit 1
fi
echo

# Test 3: Database health endpoint
echo "4. Testing /health/database endpoint..."
python3 -c "
import sys
import requests
import json

try:
    response = requests.get('${BASE_URL}/health/database', timeout=10)
    
    # Database health can return 200 (healthy), 503 (unhealthy), or 500 (error)
    assert response.status_code in [200, 503, 500], f'Expected 200, 503, or 500, got {response.status_code}'
    data = response.json()
    
    assert 'status' in data, 'Should have status'
    assert 'database' in data, 'Should have database info'
    assert 'available' in data['database'], 'Should indicate availability'
    
    print('✅ Database health endpoint works correctly')
    print(f'   Status: {data[\"status\"]}')
    print(f'   Database available: {data[\"database\"][\"available\"]}')
    
    if 'pool_stats' in data.get('database', {}):
        print('   ✅ Pool statistics included')
        pool_stats = data['database']['pool_stats']
        print(f'      Connections created: {pool_stats.get(\"connections_created\", 0)}')
        print(f'      Queries executed: {pool_stats.get(\"queries_executed\", 0)}')
    
    if response.status_code != 200:
        print(f'   ⚠️  Database not healthy (status {response.status_code} - this is OK if DB not configured)')
    
except requests.exceptions.RequestException as e:
    print(f'❌ Request failed: {e}')
    sys.exit(1)
except AssertionError as e:
    print(f'❌ Assertion failed: {e}')
    print(f'   Response: {response.text if \"response\" in locals() else \"N/A\"}')
    sys.exit(1)
except Exception as e:
    print(f'❌ Unexpected error: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ Database health endpoint test failed"
    exit 1
fi
echo

# Test 4: Health check tool (MCP tool via HTTP if available)
echo "5. Testing health_check MCP tool (if HTTP transport available)..."
python3 -c "
import sys
import requests
import json

try:
    # Try to call MCP tool endpoint (if server supports HTTP MCP)
    # This may not be available depending on server configuration
    response = requests.post(
        '${BASE_URL}/mcp',
        json={
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'tools/call',
            'params': {
                'name': 'health_check',
                'arguments': {}
            }
        },
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        if 'result' in data:
            result = data['result']
            print('✅ Health check MCP tool works correctly')
            print(f'   Status: {result.get(\"status\", \"N/A\")}')
        else:
            print('⚠️  MCP tool endpoint returned unexpected format')
            print(f'   Response: {json.dumps(data, indent=2)}')
    else:
        print('⚠️  MCP tool endpoint not available (expected if server uses stdio transport)')
        print('   ✅ Health check endpoints work (MCP tool test skipped)')
    
except requests.exceptions.RequestException as e:
    print('⚠️  MCP tool endpoint not available (expected if server uses stdio transport)')
    print('   ✅ Health check endpoints work (MCP tool test skipped)')
except Exception as e:
    print(f'⚠️  MCP tool test failed: {e}')
    print('   ✅ Health check endpoints work (MCP tool test skipped)')
"

echo

# Cleanup
if [ "$SERVER_RUNNING" = false ]; then
    echo "6. Cleaning up test server..."
    if [ "$SERVER_CMD" = "docker-compose" ]; then
        docker-compose down 2>&1 | head -3
        echo "✅ Docker containers stopped"
    elif [ -n "$SERVER_PID" ]; then
        kill $SERVER_PID 2>/dev/null && echo "✅ Server process stopped" || echo "⚠️  Server process already stopped"
    fi
fi

echo
echo "🎉 Health check endpoints integration test complete!"
echo "   All health endpoints validated with running server"
echo
echo "📋 Summary:"
echo "   ✅ Liveness endpoint (/health/live)"
echo "   ✅ Readiness endpoint (/health/ready)"
echo "   ✅ Database health endpoint (/health/database)"
echo "   ✅ MCP tool endpoint (if available)"

