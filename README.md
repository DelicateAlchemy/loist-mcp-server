# Loist MCP Server

FastMCP-based server for audio ingestion and embedding with the Music Library MCP protocol.

## Overview

This project implements a Model Context Protocol (MCP) server using the FastMCP framework for managing audio file ingestion, processing, and embedding generation for a music library system.

## MCP Server Naming Strategy

This project supports both local development and production deployments with distinct naming conventions to avoid conflicts in MCP client configurations:

### Local Development
- **Cursor MCP Server Name**: `loist-music-library-local`
- **FastMCP Server Name**: `Music Library MCP - Local Development`
- **Environment**: Docker containers with local PostgreSQL + GCS integration
- **Transport**: stdio (for Cursor MCP integration)

### Production Deployment
- **Cursor MCP Server Name**: `loist-music-library` (production)
- **FastMCP Server Name**: `Music Library MCP - Production`
- **Environment**: GCloud infrastructure (Cloud SQL + GCS)
- **Transport**: Configurable (stdio/http/sse)

### Configuration Details

**Local Development (.cursor/mcp.json):**
```json
{
  "loist-music-library-local": {
    "command": "python3",
    "args": ["/Users/Gareth/loist-mcp-server/run_server.py"],
    "cwd": "/Users/Gareth/loist-mcp-server",
    "env": {
      "SERVER_TRANSPORT": "stdio",
      "SERVER_NAME": "Music Library MCP - Local Development"
    }
  }
}
```

**Production Deployment:**
```json
{
  "loist-music-library": {
    "command": "python3",
    "args": ["/path/to/production/server.py"],
    "env": {
      "SERVER_NAME": "Music Library MCP - Production"
    }
  }
}
```

This naming strategy allows both environments to coexist in Cursor MCP client configuration without conflicts.

## Prerequisites

- Python 3.11 or higher
- `uv` package manager (installed during setup)

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd loist-mcp-server
```

### 2. Install Python 3.11+

**macOS (using Homebrew):**
```bash
brew install python@3.11
```

**Linux:**
```bash
sudo apt-get update
sudo apt-get install python3.11
```

### 3. Install uv Package Manager

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Add `uv` to your PATH:
```bash
export PATH="$HOME/.local/bin:$PATH"
```

### 4. Create Virtual Environment

```bash
uv venv --python 3.11
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 5. Install Dependencies

```bash
uv pip install -r requirements.txt
```

Or install directly:
```bash
uv pip install fastmcp
```

## Project Structure

```
loist-mcp-server/
├── src/
│   ├── server.py          # Main FastMCP server implementation
│   ├── config.py          # Configuration management
│   ├── exceptions.py      # Custom exception classes
│   ├── error_utils.py     # Error handling utilities
│   └── auth/              # Authentication module
│       ├── __init__.py
│       └── bearer.py      # Bearer token authentication
├── tests/                  # Test files
├── docs/                   # Documentation
├── scripts/                # Utility scripts
├── tasks/                  # Task management files
├── requirements.txt        # Python dependencies
├── pyproject.toml         # Project configuration
├── .env.example           # Example environment variables
└── README.md              # This file
```

## Running the Server

### Development Mode (STDIO)

**Recommended: Use Docker for development** (ensures current dependencies):

```bash
# Run server directly
./run_mcp_stdio_docker.sh
```

**Alternative: Use virtual environment** (may have outdated dependencies):
```bash
source .venv/bin/activate  # Activate virtual environment
python src/server.py
```

### Using MCP Inspector (stdio)

MCP Inspector provides an interactive debugging interface for testing tools and resources.

**Option A: Standalone Inspector** (recommended)
```bash
# 1. Launch MCP Inspector (opens in browser)
npx @modelcontextprotocol/inspector@latest

# 2. In Inspector UI:
#    - Transport: stdio
#    - Command: /Users/Gareth/loist-mcp-server/run_mcp_stdio_docker.sh
#    - Working Directory: /Users/Gareth/loist-mcp-server
```

**Option B: Command line testing**
```bash
# Test tools and resources via command line
./test_mcp_tools.sh
./test_mcp_resources.sh
```

**What to test in Inspector:**
- **health_check**: Verify server status and configuration
- **get_audio_metadata**: Test with invalid ID to see error handling
- **search_library**: Test with simple query (expect database error in stdio mode)
- **Resources**: Test `music-library://audio/{id}/metadata|stream|thumbnail` URIs

### HTTP Mode (with CORS for iframe embedding)

Set transport to HTTP in `.env`:
```env
SERVER_TRANSPORT=http
SERVER_PORT=8080
ENABLE_CORS=true
```

Then run:
```bash
source .venv/bin/activate
python src/server.py
```

Server will be available at `http://localhost:8080/mcp`

### SSE Mode (Server-Sent Events)

Set transport to SSE in `.env`:
```env
SERVER_TRANSPORT=sse
SERVER_PORT=8080
```

## Features

### Current Implementation

- ✅ FastMCP server initialization (v2.12.4, MCP v1.16.0)
- ✅ Advanced configuration management with Pydantic
- ✅ Lifespan hooks (startup/shutdown)
- ✅ Bearer token authentication (SimpleBearerAuth)
- ✅ Centralized error handling & logging
- ✅ CORS configuration for iframe embedding
- ✅ Health check tool with extended status
- ✅ Structured logging (JSON/text formats)
- ✅ Duplicate handling policies
- ✅ Environment variable support
- ✅ Multiple transport modes (STDIO, HTTP, SSE)
- ✅ Python 3.11+ support

### Planned Features

- 🔄 Advanced OAuth providers (GitHub, Google, etc.)
- 🔄 JWT token support
- 🔄 Audio file ingestion tools
- 🔄 Embedding generation
- 🔄 Docker containerization
- 🔄 PostgreSQL integration
- 🔄 Google Cloud Storage integration

## Docker

### Building the Docker Image

Using the build script:
```bash
./scripts/docker/build.sh
```

Or manually:
```bash
docker build -t music-library-mcp:latest .
```

**Image Details:**
- Base: Python 3.11-slim
- Size: ~245MB (multi-stage build)
- User: Non-root (fastmcpuser)
- Security: Minimal attack surface

### Running with Docker

Using the run script:
```bash
./scripts/docker/run.sh
```

Or manually:
```bash
docker run --rm -p 8080:8080 \
  -e SERVER_TRANSPORT=http \
  -e LOG_LEVEL=INFO \
  -e AUTH_ENABLED=false \
  music-library-mcp:latest
```

### Using Docker Compose

For local development with hot reload:

```bash
docker-compose up
```

Services:
- **mcp-server**: FastMCP server on port 8080
- **postgres**: PostgreSQL (commented out, ready for Phase 2)

### Cloud Run Deployment

Build and push to Google Container Registry:

```bash
# Configure gcloud
gcloud config set project YOUR_PROJECT_ID

# Build for Cloud Run
docker build -t gcr.io/YOUR_PROJECT_ID/music-library-mcp:latest .

# Push to GCR
docker push gcr.io/YOUR_PROJECT_ID/music-library-mcp:latest

# Deploy to Cloud Run
gcloud run deploy music-library-mcp \
  --image gcr.io/YOUR_PROJECT_ID/music-library-mcp:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --timeout 600s \
  --set-env-vars "SERVER_TRANSPORT=http,LOG_LEVEL=INFO"
```

## GitHub Actions CI/CD

The project includes automated workflows for database provisioning and testing.

### Quick Setup

Configure GitHub Secrets for database workflows:

```bash
# 1. Create service account and key
gcloud iam service-accounts create github-actions \
    --display-name="GitHub Actions CI/CD" \
    --project=loist-music-library

gcloud iam service-accounts keys create github-actions-key.json \
    --iam-account=github-actions@loist-music-library.iam.gserviceaccount.com

# 2. Add to GitHub Secrets:
# - GCLOUD_SERVICE_KEY (contents of github-actions-key.json)
# - DB_USER (music_library_user)
# - DB_PASSWORD (from .env.database)

# 3. Clean up local key
rm github-actions-key.json
```

📚 **Full Documentation:**
- [GitHub Actions Setup Guide](docs/github-actions-setup.md) - Detailed setup instructions
- [Quick Setup Guide](docs/github-secrets-quick-setup.md) - 5-minute quick start

### Available Workflows

The **Database Provisioning** workflow supports four actions:

| Action | Description | Trigger |
|--------|-------------|---------|
| `provision` | Create Cloud SQL instance | Manual dispatch |
| `migrate` | Run database migrations | Manual dispatch / Push to main |
| `test` | Run database tests | Manual dispatch / Pull requests |
| `health-check` | Verify instance health | Manual dispatch |

### Running Workflows

1. Go to **Actions** tab in GitHub
2. Select **Database Provisioning** workflow
3. Click **Run workflow**
4. Choose action (provision, migrate, test, health-check)
5. Click **Run workflow**

## Development

### Install Development Dependencies

```bash
uv pip install -e ".[dev]"
```

### Running Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black src/ tests/
```

### Linting

```bash
ruff check src/ tests/
```

## Configuration

Configuration is managed through environment variables using the `src/config.py` module with Pydantic Settings.

### Environment Variables

Create a `.env` file in the project root (see `.env.example` for reference):

```env
# Server Identity
SERVER_NAME="Music Library MCP - Local Development"
SERVER_VERSION="0.1.0"
SERVER_INSTRUCTIONS="Your custom instructions here"

# Server Runtime
SERVER_HOST=0.0.0.0
SERVER_PORT=8080
SERVER_TRANSPORT=stdio  # Options: stdio, http, sse

# Authentication (future)
BEARER_TOKEN=your-secret-token-here
AUTH_ENABLED=false

# Logging
LOG_LEVEL=INFO    # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT=text   # Options: json, text

# MCP Protocol
MCP_PROTOCOL_VERSION=2024-11-05
INCLUDE_FASTMCP_META=true

# Duplicate Handling Policies
ON_DUPLICATE_TOOLS=error      # Options: error, warn, replace, ignore
ON_DUPLICATE_RESOURCES=warn   # Options: error, warn, replace, ignore
ON_DUPLICATE_PROMPTS=replace  # Options: error, warn, replace, ignore

# Performance
MAX_WORKERS=4
REQUEST_TIMEOUT=30

# Feature Flags
ENABLE_CORS=true
CORS_ORIGINS=*
ENABLE_METRICS=false
ENABLE_HEALTHCHECK=true
```

### Configuration Features

- **Centralized Configuration**: All settings in `src/config.py` using Pydantic
- **Environment Variable Support**: Override any setting via `.env` file
- **Sensible Defaults**: Server works out-of-the-box without configuration
- **Type Safety**: Pydantic validates all configuration values
- **Lifespan Management**: Startup and shutdown hooks for resource management

## Error Handling & Logging

The server implements comprehensive error handling and structured logging for debugging and monitoring.

### Error Handling Architecture

**Custom Exception Hierarchy:**
- `MusicLibraryError` - Base exception for all errors
- `AudioProcessingError` - Audio file processing failures
- `StorageError` - GCS/storage operation failures
- `ValidationError` - Input validation failures
- `ResourceNotFoundError` - Missing resources
- `TimeoutError` - Operation timeouts
- `AuthenticationError` - Authentication failures
- `RateLimitError` - Rate limit exceeded
- `ExternalServiceError` - External service failures

### Error Responses

All errors return standardized responses:

```json
{
  "success": false,
  "error": "ERROR_CODE",
  "message": "Human-readable error message",
  "details": {
    "additional": "context",
    "if": "available"
  }
}
```

**Error Codes:**
- `AUDIO_PROCESSING_FAILED` - Audio processing error
- `STORAGE_ERROR` - Storage operation failed
- `VALIDATION_ERROR` - Invalid input
- `RESOURCE_NOT_FOUND` - Resource doesn't exist
- `TIMEOUT` - Operation timed out
- `AUTHENTICATION_FAILED` - Auth error
- `RATE_LIMIT_EXCEEDED` - Too many requests
- `EXTERNAL_SERVICE_ERROR` - External service unavailable
- `INTERNAL_ERROR` - Unexpected server error

### Structured Logging

Logging supports both text and JSON formats:

**Text Format** (human-readable):
```
2025-10-09 11:54:43 - server - INFO - [server.health_check:86] - Health check passed
```

**JSON Format** (structured):
```json
{"timestamp":"2025-10-09 11:54:43","logger":"server","level":"INFO","message":"Health check passed","module":"server","function":"health_check","line":86}
```

Configure via environment variables:
```env
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT=text  # text or json
```

### Error Handling Utilities

**`create_error_response(error)`** - Format error for MCP protocol  
**`log_error(error, context)`** - Log with structured context  
**`handle_tool_error(error, tool_name, args)`** - Handle tool errors  
**`handle_resource_error(error, uri)`** - Handle resource errors  
**`safe_execute(func, *args)`** - Execute with error capture

### Implementation Example

```python
from exceptions import AudioProcessingError
from error_utils import handle_tool_error

@mcp.tool()
def process_audio(url: str) -> dict:
    try:
        # Process audio
        result = process_audio_file(url)
        return {"success": True, "data": result}
    except AudioProcessingError as e:
        return handle_tool_error(e, "process_audio", {"url": url})
```

## Authentication

The server implements bearer token authentication for secure access control.

### Enabling Authentication

Set these environment variables in your `.env` file:

```env
AUTH_ENABLED=true
BEARER_TOKEN=your-secret-token-here
```

**Important Security Notes:**
- 🔒 **Never commit bearer tokens to version control**
- 🔑 Use strong, randomly generated tokens (minimum 32 characters)
- 🔄 Rotate tokens regularly in production
- 📝 Store tokens securely (e.g., using a secrets manager)

### Development Mode (No Authentication)

For local development, authentication can be disabled:

```env
AUTH_ENABLED=false
```

The server will run without authentication and log a warning.

### Using the Server with Authentication

When authentication is enabled, all MCP protocol requests must include a valid bearer token in the Authorization header:

```
Authorization: Bearer your-secret-token-here
```

### Authentication Implementation

- **SimpleBearerAuth**: MVP implementation in `src/auth/bearer.py`
- **Token Verification**: Validates bearer tokens against configured value
- **Access Control**: Returns `AccessToken` with client_id and scopes
- **Logging**: Tracks authentication attempts and failures

### Future Authentication Plans

- JWT token support with expiration
- OAuth providers (GitHub, Google, Microsoft)
- API key management system
- Role-based access control (RBAC)

## CORS Configuration

The server supports CORS (Cross-Origin Resource Sharing) for iframe embedding and cross-origin requests.

### Enabling CORS

CORS is enabled by default for HTTP and SSE transports. Configure via environment variables:

```env
# CORS Configuration
ENABLE_CORS=true
CORS_ORIGINS=*  # Development: allow all
CORS_ALLOW_CREDENTIALS=true
CORS_ALLOW_METHODS=GET,POST,OPTIONS
CORS_ALLOW_HEADERS=Authorization,Content-Type,Range,X-Requested-With,Accept,Origin
CORS_EXPOSE_HEADERS=Content-Range,Accept-Ranges,Content-Length,Content-Type
```

### Production CORS Setup

**⚠️ Security Warning:** Never use `CORS_ORIGINS=*` with `CORS_ALLOW_CREDENTIALS=true` in production!

For production, specify exact origins:

```env
CORS_ORIGINS=https://www.notion.so,https://app.slack.com,https://discord.com
```

### CORS Headers Explained

**Allow Headers** - Headers clients can send:
- `Authorization` - Bearer token authentication
- `Content-Type` - Request content type
- `Range` - For audio seeking/streaming
- `X-Requested-With`, `Accept`, `Origin` - Standard CORS headers

**Expose Headers** - Headers clients can read:
- `Content-Range` - Byte range information for seeking
- `Accept-Ranges` - Server supports range requests
- `Content-Length` - File size for progress tracking
- `Content-Type` - Response content type

### CORS for Different Use Cases

**Iframe Embedding (Notion, Slack, Discord):**
```env
CORS_ORIGINS=https://www.notion.so,https://app.slack.com,https://discord.com
CORS_ALLOW_CREDENTIALS=true
```

**Audio Streaming with Range Requests:**
```env
CORS_ALLOW_HEADERS=Range,Authorization,Content-Type
CORS_EXPOSE_HEADERS=Content-Range,Accept-Ranges,Content-Length
```

**Development (Local Testing):**
```env
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

### Testing CORS

Test CORS with curl:
```bash
curl -i -H "Origin: https://www.notion.so" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: Authorization,Content-Type" \
     -X OPTIONS http://localhost:8080/mcp
```

Should see headers:
```
Access-Control-Allow-Origin: https://www.notion.so
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: Authorization, Content-Type, Range, ...
```

## API Documentation

### Health Check

**Tool:** `health_check`

Returns the current status of the server.

**Returns:**
```json
{
  "status": "healthy",
  "service": "Music Library MCP",
  "version": "0.1.0"
}
```

## Contributing

1. Create a feature branch from `main`
2. Make your changes
3. Run tests and linting
4. Submit a pull request

## Version History

- **0.1.0** (Current) - Initial project setup with FastMCP framework

## License

[License information to be added]

## Support

For issues and questions, please open an issue on the project repository.

