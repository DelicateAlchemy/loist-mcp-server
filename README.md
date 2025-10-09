# Loist MCP Server

FastMCP-based server for audio ingestion and embedding with the Music Library MCP protocol.

## Overview

This project implements a Model Context Protocol (MCP) server using the FastMCP framework for managing audio file ingestion, processing, and embedding generation for a music library system.

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

### Development Mode

```bash
source .venv/bin/activate  # Activate virtual environment
python src/server.py dev
```

### Production Mode

```bash
source .venv/bin/activate
python src/server.py
```

## Features

### Current Implementation

- ✅ FastMCP server initialization (v2.12.4, MCP v1.16.0)
- ✅ Advanced configuration management with Pydantic
- ✅ Lifespan hooks (startup/shutdown)
- ✅ Bearer token authentication (SimpleBearerAuth)
- ✅ Centralized error handling & logging
- ✅ Health check tool with extended status
- ✅ Structured logging (JSON/text formats)
- ✅ Duplicate handling policies
- ✅ Environment variable support
- ✅ Python 3.11+ support

### Planned Features

- 🔄 Advanced OAuth providers (GitHub, Google, etc.)
- 🔄 JWT token support
- 🔄 Audio file ingestion
- 🔄 Embedding generation
- 🔄 CORS configuration
- 🔄 Docker containerization
- 🔄 HTTP/SSE transport modes

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
SERVER_NAME="Music Library MCP"
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

