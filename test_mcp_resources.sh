#!/bin/bash
# Test script to validate MCP resources via stdio

cd "$(dirname "$0")"

# Create a temporary file with MCP resource messages
cat > /tmp/mcp_resource_messages.json << 'EOF'
{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}}
{"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
{"jsonrpc": "2.0", "id": 2, "method": "resources/list", "params": {}}
{"jsonrpc": "2.0", "id": 3, "method": "resources/read", "params": {"uri": "music-library://audio/550e8400-e29b-41d4-a716-446655440000/metadata"}}
{"jsonrpc": "2.0", "id": 4, "method": "resources/read", "params": {"uri": "music-library://audio/550e8400-e29b-41d4-a716-446655440000/stream"}}
{"jsonrpc": "2.0", "id": 5, "method": "resources/read", "params": {"uri": "music-library://audio/550e8400-e29b-41d4-a716-446655440000/thumbnail"}}
EOF

echo "Testing MCP resources via Docker stdio..."
echo "=========================================="

# Run the test
cat /tmp/mcp_resource_messages.json | ./run_mcp_stdio_docker.sh 2>/dev/null | grep -E '^\{"jsonrpc"'

# Clean up
rm -f /tmp/mcp_resource_messages.json
