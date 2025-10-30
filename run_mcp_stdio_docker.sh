#!/bin/bash
# Script to run MCP server in Docker with stdio transport for MCP Inspector
# This ensures we use the current Docker environment with proper dependencies

cd "$(dirname "$0")"

# Run the Docker container in stdio mode for MCP Inspector
docker run --rm -i \
  -e SERVER_TRANSPORT=stdio \
  -e AUTH_ENABLED=false \
  -e LOG_LEVEL=DEBUG \
  -e LOG_FORMAT=text \
  -v "$(pwd)/service-account-key.json:/app/service-account-key.json:ro" \
  -v "$(pwd)/database:/app/database:ro" \
  -v "$(pwd)/templates:/app/templates:ro" \
  music-library-mcp:latest \
  python src/server.py
