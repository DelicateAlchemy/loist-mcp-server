#!/bin/bash
# Test script to validate MCP tools via stdio

cd "$(dirname "$0")"

# Create a temporary file with MCP messages
cat > /tmp/mcp_test_messages.json << 'EOF'
{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}}
{"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
{"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "health_check", "arguments": {}}}
{"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "get_audio_metadata", "arguments": {"audioId": "nonexistent-id"}}}
{"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "search_library", "arguments": {"query": "test"}}}
EOF

echo "Testing MCP tools via Docker stdio..."
echo "======================================="

# Run the test
cat /tmp/mcp_test_messages.json | ./run_mcp_stdio_docker.sh 2>/dev/null | grep -E '^\{"jsonrpc"'

# Clean up
rm -f /tmp/mcp_test_messages.json
