#!/bin/bash
# Build Docker image for Music Library MCP Server

set -e

echo "🐳 Building Music Library MCP Server Docker image..."

# Build with BuildKit for better performance
DOCKER_BUILDKIT=1 docker build \
    --tag music-library-mcp:latest \
    --tag music-library-mcp:0.1.0 \
    --progress=plain \
    .

echo "✅ Docker image built successfully!"
echo ""
echo "Image tags:"
echo "  - music-library-mcp:latest"
echo "  - music-library-mcp:0.1.0"
echo ""
echo "To run: docker run -p 8080:8080 music-library-mcp:latest"
echo "Or use: docker-compose up"

