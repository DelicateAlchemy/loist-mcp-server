# MCP Server Testing Guide

## Server Overview

Your MCP server is a **Music Library MCP Server** built with FastMCP that provides audio processing, storage, and embedding capabilities. It's currently configured to run on `stdio` transport by default.

## Available MCP Tools

### 1. `health_check()` 
- **Purpose**: Verify server is running and get status information
- **Returns**: Server status, version, transport, log level, authentication status
- **Usage**: Basic connectivity test
- **Example**: `health_check()`

### 2. `process_audio_complete(source, options=None)`
- **Purpose**: Complete audio processing pipeline
- **Parameters**:
  - `source`: Dict with `type`, `url`, `headers`, `filename`, `mimeType`
  - `options`: Dict with `maxSizeMB`, `timeout`, `validateFormat`
- **Returns**: Audio ID, metadata, and resource URIs
- **Pipeline**: Download → Extract metadata → Upload to GCS → Save to DB
- **Example**: 
  ```python
  await process_audio_complete(
      source={"type": "http_url", "url": "https://example.com/song.mp3"},
      options={"maxSizeMB": 100}
  )
  ```

### 3. `get_audio_metadata(audioId)`
- **Purpose**: Retrieve metadata for processed audio track
- **Parameters**: `audioId` (UUID string)
- **Returns**: Complete metadata and resource URIs
- **Example**: `await get_audio_metadata("550e8400-e29b-41d4-a716-446655440000")`

### 4. `search_library(query, filters=None, limit=20, offset=0, sortBy="relevance", sortOrder="desc")`
- **Purpose**: Search across all processed audio
- **Parameters**:
  - `query`: Search string (1-500 chars)
  - `filters`: Optional filters (genre, year, duration, format, artist, album)
  - `limit`: Max results (1-100)
  - `offset`: Results to skip
  - `sortBy`: Field to sort by
  - `sortOrder`: "asc" or "desc"
- **Returns**: Search results with pagination
- **Example**: 
  ```python
  await search_library(
      query="beatles",
      filters={"genre": ["Rock"], "year": {"min": 1960, "max": 1970}},
      limit=20
  )
  ```

## Available MCP Resources

### 1. `music-library://audio/{audioId}/stream`
- **Purpose**: Stream audio files with range request support
- **Returns**: Signed GCS URL for audio streaming
- **Features**: HTTP Range requests, proper Content-Type, caching

### 2. `music-library://audio/{audioId}/metadata`
- **Purpose**: Get complete audio metadata as JSON
- **Returns**: JSON with Product and Format information

### 3. `music-library://audio/{audioId}/thumbnail`
- **Purpose**: Get audio artwork/thumbnails
- **Returns**: Signed GCS URL for thumbnail image

## Custom Routes

### 1. `/embed/{audioId}` (GET)
- **Purpose**: HTML5 audio player embed page
- **Features**: 
  - Custom audio player UI
  - Metadata display
  - Open Graph and Twitter Card tags
  - oEmbed discovery
  - Keyboard shortcuts
  - Responsive design
- **Example**: `GET /embed/550e8400-e29b-41d4-a716-446655440000`
- **Returns**: HTML page with audio player

### 2. `/oembed` (GET)
- **Purpose**: oEmbed endpoint for rich media previews
- **Query Parameters**:
  - `url` (required): Embed URL to generate oEmbed data for
  - `format` (optional): Response format, 'json' or 'xml' (default: 'json')
  - `maxwidth` (optional): Maximum width for embed (default: 500)
  - `maxheight` (optional): Maximum height for embed (default: 200)
- **Returns**: JSON response following oEmbed v1.0 specification
- **Example**: 
  ```bash
  GET /oembed?url=https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000&maxwidth=800&maxheight=300
  ```
- **Response Format**:
  ```json
  {
    "version": "1.0",
    "type": "rich",
    "provider_name": "Loist Music Library",
    "provider_url": "https://loist.io",
    "title": "Track Title",
    "author_name": "Artist Name",
    "html": "<iframe src='...' width='800' height='300' ...></iframe>",
    "width": 800,
    "height": 300,
    "thumbnail_url": "...",
    "cache_age": 3600
  }
  ```

## Server Configuration

- **Transport**: `stdio` (default), `http`, or `sse`
- **Port**: 8080 (when using HTTP/SSE)
- **Authentication**: Bearer token (optional)
- **CORS**: Configurable for iframe embedding
- **Logging**: Configurable level and format

## Authentication System

### Overview
Your MCP server uses a **Simple Bearer Token Authentication** system that's designed for MVP testing. It's implemented in `src/auth/bearer.py` and extends FastMCP's `AuthProvider`.

### How It Works
1. **Token Validation**: Server validates incoming requests against a configured bearer token
2. **Access Control**: Returns `AccessToken` with client info, scopes, and claims
3. **Flexible Configuration**: Can be enabled/disabled via environment variables

### Configuration Options

#### Environment Variables
```bash
# Enable/disable authentication
AUTH_ENABLED=true|false

# Set the bearer token (required if AUTH_ENABLED=true)
BEARER_TOKEN=your-secret-token-here
```

#### Authentication States
1. **Disabled** (`AUTH_ENABLED=false`): All requests allowed, no token required
2. **Enabled without token** (`AUTH_ENABLED=true`, no `BEARER_TOKEN`): Server warns but allows requests
3. **Enabled with token** (`AUTH_ENABLED=true`, `BEARER_TOKEN` set): Validates all requests

### Local Testing Setup

#### Option 1: Disable Authentication (Recommended for Local Testing)
```bash
# In your .env file or environment
AUTH_ENABLED=false
BEARER_TOKEN=""
```

#### Option 2: Enable Authentication with Test Token
```bash
# In your .env file or environment
AUTH_ENABLED=true
BEARER_TOKEN=dev-token-not-for-production
```

### Testing Authentication

#### 1. Test with Authentication Disabled
```bash
# Set environment
export AUTH_ENABLED=false

# Start server
python src/server.py

# Test health check (should work without token)
curl http://localhost:8080/mcp/health_check
```

#### 2. Test with Authentication Enabled
```bash
# Set environment
export AUTH_ENABLED=true
export BEARER_TOKEN=test-token-123

# Start server
python src/server.py

# Test without token (should fail)
curl http://localhost:8080/mcp/health_check

# Test with valid token (should work)
curl -H "Authorization: Bearer test-token-123" http://localhost:8080/mcp/health_check

# Test with invalid token (should fail)
curl -H "Authorization: Bearer wrong-token" http://localhost:8080/mcp/health_check
```

#### 3. Test MCP Client Integration
When using MCP clients like Cursor, the authentication is handled automatically if configured in your MCP client settings.

### Docker Testing
The `docker-compose.yml` is pre-configured for local development:
```yaml
environment:
  - AUTH_ENABLED=false
  - BEARER_TOKEN=dev-token-not-for-production
```

### Security Notes
- **For Production**: This simple token system is NOT suitable for production
- **Token Management**: No expiration, rotation, or user management
- **Future Improvements**: Consider JWT, OAuth, or RBAC for production use
- **Local Development**: Authentication is typically disabled for easier testing

## Testing Your MCP Server

### Quick Start for Local Testing

#### 1. Set Up Environment (Choose One)

**Option A: Disable Authentication (Easiest)**
```bash
# Create .env file in project root
echo "AUTH_ENABLED=false" > .env
echo "SERVER_TRANSPORT=http" >> .env
echo "LOG_LEVEL=DEBUG" >> .env
```

**Option B: Enable Authentication**
```bash
# Create .env file in project root
echo "AUTH_ENABLED=true" > .env
echo "BEARER_TOKEN=test-token-123" >> .env
echo "SERVER_TRANSPORT=http" >> .env
echo "LOG_LEVEL=DEBUG" >> .env
```

#### 2. Start the Server
```bash
# From project root
cd /Users/Gareth/loist-mcp-server
python src/server.py
```

#### 3. Test Basic Connectivity

**With Authentication Disabled:**
```bash
# Test health check
curl http://localhost:8080/mcp/health_check

# Expected response:
# {"status": "healthy", "service": "Music Library MCP", ...}
```

**With Authentication Enabled:**
```bash
# Test without token (should fail)
curl http://localhost:8080/mcp/health_check

# Test with token (should work)
curl -H "Authorization: Bearer test-token-123" http://localhost:8080/mcp/health_check
```

### Testing MCP Tools

#### 1. Health Check
```python
# Via MCP client (like Cursor)
result = health_check()
print(f"Server status: {result['status']}")
```

#### 2. Process Audio (if you have test audio)
```python
# Process an audio file
result = await process_audio_complete(
    source={
        "type": "http_url", 
        "url": "https://example.com/test-audio.mp3"
    },
    options={"maxSizeMB": 50}
)
audio_id = result["audioId"]
```

#### 3. Retrieve Metadata
```python
# Get metadata for processed audio
metadata = await get_audio_metadata(audio_id)
print(f"Title: {metadata['metadata']['Product']['Title']}")
```

#### 4. Search Library
```python
# Search for audio
results = await search_library(
    query="test",
    limit=10
)
print(f"Found {results['total']} results")
```

#### 5. Test Embed Page
```bash
# Test embed page (requires valid audioId)
curl http://localhost:8080/embed/550e8400-e29b-41d4-a716-446655440000

# Or open in browser:
# http://localhost:8080/embed/{audioId}
```

#### 6. Test oEmbed Endpoint
```bash
# Test oEmbed with required url parameter
curl "http://localhost:8080/oembed?url=https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000"

# Test with maxwidth and maxheight
curl "http://localhost:8080/oembed?url=https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000&maxwidth=800&maxheight=300"

# Test with invalid URL (should return 400)
curl "http://localhost:8080/oembed?url=https://example.com/invalid"

# Test with missing url parameter (should return 400)
curl "http://localhost:8080/oembed"

# Test with non-existent audio ID (should return 404)
curl "http://localhost:8080/oembed?url=https://loist.io/embed/00000000-0000-0000-0000-000000000000"
```

### Testing with Docker

#### 1. Build and Run with Docker Compose
```bash
# From project root
docker-compose up --build

# Server will be available at http://localhost:8080
# Authentication is disabled by default in docker-compose.yml
```

#### 2. Test Docker Setup
```bash
# Test health check
curl http://localhost:8080/mcp/health_check

# Test embed page (if you have audio)
curl http://localhost:8080/embed/test-audio-id

# Test oEmbed endpoint
curl "http://localhost:8080/oembed?url=https://loist.io/embed/test-audio-id&maxwidth=500&maxheight=200"
```

### Testing MCP Resources

#### 1. Test Audio Stream Resource
```bash
# Get signed URL for audio stream
curl http://localhost:8080/mcp/resources/music-library://audio/{audioId}/stream
```

#### 2. Test Metadata Resource
```bash
# Get metadata as JSON
curl http://localhost:8080/mcp/resources/music-library://audio/{audioId}/metadata
```

#### 3. Test Thumbnail Resource
```bash
# Get signed URL for thumbnail
curl http://localhost:8080/mcp/resources/music-library://audio/{audioId}/thumbnail
```

## Transport Options

### stdio (Default)
- Direct process communication
- Used by MCP clients like Cursor
- No HTTP server needed

### HTTP
- REST API endpoints
- CORS support for web embedding
- Accessible via browser

### SSE (Server-Sent Events)
- Real-time communication
- Good for streaming responses

## Next Steps for Testing

1. **Start with health_check()** - Verify server is running
2. **Test with sample audio** - Use process_audio_complete with a test URL
3. **Verify storage** - Check if files are uploaded to GCS
4. **Test retrieval** - Use get_audio_metadata and search_library
5. **Test embed page** - Switch to HTTP transport and test the player

## Troubleshooting

### Common Issues and Solutions

#### 1. Authentication Issues
**Problem**: "Invalid bearer token" or "Authentication required"
```bash
# Check your .env file
cat .env | grep AUTH

# Solution: Disable auth for local testing
echo "AUTH_ENABLED=false" > .env
```

#### 2. Server Won't Start
**Problem**: Import errors or missing dependencies
```bash
# Install dependencies
pip install -r requirements.txt

# Check Python path
python -c "import src.server"
```

#### 3. Port Already in Use
**Problem**: "Address already in use" on port 8080
```bash
# Find what's using port 8080
lsof -i :8080

# Kill the process or use different port
export SERVER_PORT=8081
```

#### 4. GCS Connection Issues
**Problem**: "No credentials found" or GCS errors
```bash
# Check service account key
ls -la service-account-key.json

# Set credentials path
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

#### 5. Database Connection Issues
**Problem**: "Connection refused" or database errors
```bash
# Check if PostgreSQL is running
docker-compose ps

# Start database
docker-compose up postgres -d
```

#### 6. MCP Client Can't Connect
**Problem**: MCP client (like Cursor) can't connect to server
```bash
# Check transport mode
echo $SERVER_TRANSPORT

# For MCP clients, use stdio
export SERVER_TRANSPORT=stdio
```

### Debug Mode
Enable debug logging for detailed troubleshooting:
```bash
export LOG_LEVEL=DEBUG
export LOG_FORMAT=text
python src/server.py
```

### Health Check Endpoints
Test server health at different levels:
```bash
# Basic health check
curl http://localhost:8080/mcp/health_check

# Check server logs
docker-compose logs mcp-server

# Check database connection
docker-compose exec mcp-server python -c "from database import test_connection; test_connection()"
```

### Environment Validation
Verify your environment is properly configured:
```bash
# Check all environment variables
env | grep -E "(AUTH|SERVER|GCS|DB)"

# Validate configuration
python -c "from src.config import config; print(config.validate_credentials())"
```
