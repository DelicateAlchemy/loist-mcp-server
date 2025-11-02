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

# Test 3: MCP endpoint responds
echo "3. Testing MCP Endpoint Response..."
echo "-------------------------------------"
MCP_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" "$SERVICE_URL/mcp" 2>&1)
HTTP_CODE=$(echo "$MCP_RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)

if [ "$HTTP_CODE" == "200" ] || [ "$HTTP_CODE" == "405" ] || [ "$HTTP_CODE" == "406" ]; then
    echo "✅ MCP endpoint responding (HTTP $HTTP_CODE)"
    echo "Note: Full MCP protocol testing requires MCP Inspector"
    echo "      See: docs/local-testing-mcp.md"
else
    echo "❌ MCP endpoint not responding properly (HTTP $HTTP_CODE)"
    exit 1
fi
echo ""

echo "========================================="
echo "✅ Cloud Run validation complete"
echo "========================================="

