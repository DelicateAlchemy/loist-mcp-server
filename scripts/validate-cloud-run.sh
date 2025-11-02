#!/bin/bash
# Validate Cloud Run service accessibility and MCP protocol

set -e

SERVICE_URL="${1:-https://music-library-mcp-7de5nxpr4q-uc.a.run.app}"

echo "========================================="
echo " Cloud Run Service Validation"
echo "========================================="
echo "Service URL: $SERVICE_URL"
echo ""

# Test 1: Service accessibility
echo "1. Testing Service Accessibility..."
echo "-------------------------------------"
if curl -f -s -o /dev/null -w "%{http_code}" "$SERVICE_URL" | grep -q "200\|404"; then
    echo "✅ Service is accessible"
else
    echo "❌ Service is not accessible"
    exit 1
fi
echo ""

# Test 2: SSL/HTTPS
echo "2. Verifying SSL/HTTPS..."
echo "-------------------------------------"
if curl -s -I "$SERVICE_URL" | grep -q "HTTP/2 "; then
    echo "✅ HTTPS enabled"
else
    echo "❌ HTTPS not configured"
fi
echo ""

# Test 3: MCP health check endpoint
echo "3. Testing MCP Health Check..."
echo "-------------------------------------"
HEALTH_RESPONSE=$(curl -s -X POST "$SERVICE_URL/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "health_check", "arguments": {}}, "id": 1}')

if echo "$HEALTH_RESPONSE" | grep -q '"status"'; then
    echo "✅ Health check endpoint working"
    echo "Response: $HEALTH_RESPONSE" | head -c 200
    echo "..."
else
    echo "❌ Health check failed"
    echo "Response: $HEALTH_RESPONSE"
    exit 1
fi
echo ""

# Test 4: MCP protocol handshake
echo "4. Testing MCP Protocol Handshake..."
echo "-------------------------------------"
INIT_RESPONSE=$(curl -s -X POST "$SERVICE_URL/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}}, "id": 1}')

if echo "$INIT_RESPONSE" | grep -q '"result"'; then
    echo "✅ MCP initialize handshake successful"
else
    echo "❌ MCP initialize failed"
    echo "Response: $INIT_RESPONSE"
    exit 1
fi
echo ""

# Test 5: JSON-RPC 2.0 compliance
echo "5. Validating JSON-RPC 2.0 Format..."
echo "-------------------------------------"
if echo "$INIT_RESPONSE" | grep -q '"jsonrpc":"2.0"'; then
    echo "✅ JSON-RPC 2.0 compliant"
else
    echo "⚠️  JSON-RPC version not confirmed"
fi
echo ""

echo "========================================="
echo "✅ Cloud Run validation complete"
echo "========================================="

