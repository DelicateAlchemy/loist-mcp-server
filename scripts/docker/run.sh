#!/bin/bash
# Run Music Library MCP Server in Docker

set -e

echo "🚀 Starting Music Library MCP Server..."

docker run \
    --name music-library-mcp \
    --rm \
    -p 8080:8080 \
    -e SERVER_TRANSPORT=http \
    -e LOG_LEVEL=INFO \
    -e AUTH_ENABLED=false \
    -e ENABLE_CORS=true \
    music-library-mcp:latest

echo "✅ Server stopped"

