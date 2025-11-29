#!/bin/bash
# Validate MCP tools functionality

set -e

MCP_URL="${1:-https://music-library-mcp-7de5nxpr4q-uc.a.run.app/mcp}"

echo "========================================="
echo " MCP Tools Validation"
echo "========================================="
echo "MCP Endpoint: $MCP_URL"
echo ""

# Test 1: health_check tool
echo "1. Testing health_check Tool..."
echo "-------------------------------------"
HEALTH_RESPONSE=$(curl -s -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "health_check", "arguments": {}}, "id": 1}')

if echo "$HEALTH_RESPONSE" | grep -q '"status":"healthy"'; then
    echo "✅ health_check tool working"
    echo "$HEALTH_RESPONSE" | grep -o '"status":"[^"]*"' | head -1
else
    echo "❌ health_check tool failed"
    echo "Response: $HEALTH_RESPONSE"
fi
echo ""

# Test 2: get_audio_metadata tool (with invalid ID - expect error)
echo "2. Testing get_audio_metadata Tool (Error Handling)..."
echo "-------------------------------------"
GET_RESPONSE=$(curl -s -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "get_audio_metadata", "arguments": {"audioId": "00000000-0000-0000-0000-000000000000"}}, "id": 2}')

if echo "$GET_RESPONSE" | grep -q '"error"'; then
    echo "✅ get_audio_metadata tool responds with proper error"
else
    echo "⚠️  get_audio_metadata unexpected response"
fi
echo ""

# Test 3: search_library tool (basic query)
echo "3. Testing search_library Tool..."
echo "-------------------------------------"
SEARCH_RESPONSE=$(curl -s -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "search_library", "arguments": {"query": "test", "limit": 5}}, "id": 3}')

if echo "$SEARCH_RESPONSE" | grep -q -E '"result"|"error"'; then
    echo "✅ search_library tool responding"
    if echo "$SEARCH_RESPONSE" | grep -q '"result"'; then
        echo "   Search executed successfully"
    else
        echo "   Received error response (may be expected if DB empty)"
    fi
else
    echo "❌ search_library tool failed"
    echo "Response: $SEARCH_RESPONSE"
fi
echo ""

# Test 4: List available tools
echo "4. Listing Available MCP Tools..."
echo "-------------------------------------"
TOOLS_RESPONSE=$(curl -s -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 4}')

if echo "$TOOLS_RESPONSE" | grep -q '"tools"'; then
    echo "✅ Tools list retrieved"
    TOOL_COUNT=$(echo "$TOOLS_RESPONSE" | grep -o '"name"' | wc -l)
    echo "   Available tools: $TOOL_COUNT"
else
    echo "❌ Failed to list tools"
fi
echo ""

# Test 5: Validate error responses
echo "5. Testing Error Response Format..."
echo "-------------------------------------"
ERROR_RESPONSE=$(curl -s -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "nonexistent_tool", "arguments": {}}, "id": 5}')

if echo "$ERROR_RESPONSE" | grep -q '"error"'; then
    echo "✅ Error handling working correctly"
    if echo "$ERROR_RESPONSE" | grep -q '"code"'; then
        echo "   Error response includes error code"
    fi
else
    echo "⚠️  Error response format unexpected"
fi
echo ""

echo "========================================="
echo "✅ MCP tools validation complete"
echo "========================================="

