# Environment Variables Configuration

This document describes all environment variables used by the Loist Music Library MCP Server, including their purposes, default values, and configuration examples for different deployment environments.

## Table of Contents

- [Server Identity](#server-identity)
- [Server Runtime](#server-runtime)
- [Authentication](#authentication)
- [Logging](#logging)
- [MCP Protocol](#mcp-protocol)
- [Duplicate Handling](#duplicate-handling)
- [Performance](#performance)
- [Storage Configuration](#storage-configuration)
- [Google Cloud Storage](#google-cloud-storage)
- [Database Configuration](#database-configuration)
- [CORS Configuration](#cors-configuration)
- [Embed Configuration](#embed-configuration)
- [Feature Flags](#feature-flags)
- [Python Runtime](#python-runtime)

## Server Identity

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `SERVER_NAME` | Human-readable name for the MCP server | "Music Library MCP" | "Music Library MCP - Production" |
| `SERVER_VERSION` | Version string for the server | "0.1.0" | "1.2.3" |
| `SERVER_INSTRUCTIONS` | Instructions shown to MCP clients about server capabilities | See default in config | Custom instructions for your use case |

## Server Runtime

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `SERVER_HOST` | Host address to bind the server to | "0.0.0.0" | "127.0.0.1" |
| `SERVER_PORT` | Port to bind the server to | 8080 | 3000 |
| `SERVER_TRANSPORT` | Transport protocol for MCP communication | "stdio" | "http", "sse" |

## Authentication

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `BEARER_TOKEN` | Bearer token for HTTP authentication (required if AUTH_ENABLED=true) | None | "your-secure-token-here" |
| `AUTH_ENABLED` | Whether to enable HTTP bearer token authentication | false | true |

## Logging

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) | "INFO" | "DEBUG" |
| `LOG_FORMAT` | Log output format (text or json) | "text" | "json" |

## MCP Protocol

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `MCP_PROTOCOL_VERSION` | MCP protocol version supported by the server | "2024-11-05" | "2024-11-05" |
| `INCLUDE_FASTMCP_META` | Whether to include FastMCP metadata in responses | true | false |

## Duplicate Handling

Policies for handling duplicate registrations in MCP.

| Variable | Description | Default | Options |
|----------|-------------|---------|---------|
| `ON_DUPLICATE_TOOLS` | Action when registering a tool with existing name | "error" | "error", "warn", "replace", "ignore" |
| `ON_DUPLICATE_RESOURCES` | Action when registering a resource with existing URI | "warn" | "error", "warn", "replace", "ignore" |
| `ON_DUPLICATE_PROMPTS` | Action when registering a prompt with existing name | "replace" | "error", "warn", "replace", "ignore" |

## Performance

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `MAX_WORKERS` | Maximum number of worker threads for concurrent requests | 4 | 8 |
| `REQUEST_TIMEOUT` | Timeout in seconds for individual requests | 30 | 60 |

## Storage Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `STORAGE_PATH` | Local path for temporary file storage | "./storage" | "/tmp/storage" |
| `MAX_FILE_SIZE` | Maximum allowed file size in bytes (100MB) | 104857600 | 209715200 |

## Google Cloud Storage

GCS configuration. Cloud Run uses Application Default Credentials (ADC) with IAM SignBlob for signed URLs. Local development uses keyfile credentials. Control signing method with `GCS_SIGNER_MODE`.

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `GCS_BUCKET_NAME` | Name of the GCS bucket (set via secret) | None | "my-music-bucket" |
| `GCS_PROJECT_ID` | Google Cloud project ID | None | "my-project-123" |
| `GCS_REGION` | GCS region for bucket operations | "us-central1" | "us-west1" |
| `GCS_SIGNED_URL_EXPIRATION` | Expiration time for signed URLs in seconds | 900 | 3600 |
| `GCS_SERVICE_ACCOUNT_EMAIL` | Service account email for GCS operations | None | "storage-sa@project.iam.gserviceaccount.com" |
| `GCS_SIGNER_MODE` | GCS signed URL signing method (auto, iam, keyfile) | "auto" | "iam" |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to GCS service account key file (local dev only) | None | "/app/service-account.json" |

## Database Configuration

Non-sensitive database configuration (credentials handled via secrets).

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `DB_HOST` | Database host address | None | "localhost", "127.0.0.1" |
| `DB_PORT` | Database port | 5432 | 5432 |
| `DB_NAME` | Database name | None | "music_library" |
| `DB_USER` | Database username (set via secret) | None | "music_user" |
| `DB_PASSWORD` | Database password (set via secret) | None | "secure-password" |
| `DB_CONNECTION_NAME` | Cloud SQL connection name (set via secret) | None | "project:region:instance" |
| `DB_MIN_CONNECTIONS` | Minimum database connection pool size | 2 | 1 |
| `DB_MAX_CONNECTIONS` | Maximum database connection pool size | 10 | 20 |
| `DB_COMMAND_TIMEOUT` | Database command timeout in seconds | 30 | 60 |

## CORS Configuration

Cross-Origin Resource Sharing settings for HTTP endpoints.

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `ENABLE_CORS` | Whether to enable CORS headers | true | false |
| `CORS_ORIGINS` | Allowed origins (comma-separated or "*" for all) | "*" | "https://example.com,https://app.example.com" |
| `CORS_ALLOW_CREDENTIALS` | Whether to allow credentials in CORS requests | true | false |
| `CORS_ALLOW_METHODS` | Allowed HTTP methods (comma-separated) | "GET,POST,OPTIONS" | "GET,POST,PUT,DELETE,OPTIONS" |
| `CORS_ALLOW_HEADERS` | Allowed request headers (comma-separated) | "Authorization,Content-Type,Range,X-Requested-With,Accept,Origin" | "Authorization,Content-Type" |
| `CORS_EXPOSE_HEADERS` | Headers exposed to browser (comma-separated) | "Content-Range,Accept-Ranges,Content-Length,Content-Type" | "Content-Range,Content-Type" |

## Embed Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `EMBED_BASE_URL` | Base URL for embed links and oEmbed endpoints | "https://loist.io" | "https://your-domain.com" |

**Note:** In Cloud Run deployments, this is overridden via `--set-env-vars` to support separate staging and production domains (e.g., `staging.loist.io` vs `loist.io`).

## Feature Flags

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `ENABLE_METRICS` | Whether to enable metrics collection | false | true |
| `ENABLE_HEALTHCHECK` | Whether to enable health check endpoints | true | false |

## Python Runtime

Python-specific environment variables for performance and security.

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `PYTHONUNBUFFERED` | Disable Python output buffering | 1 | 1 |
| `PYTHONDONTWRITEBYTECODE` | Prevent Python from writing .pyc files | 1 | 1 |
| `PYTHONPATH` | Additional Python path entries | "/app/src" | "/app/src:/app/lib" |
| `PYTHONHASHSEED` | Set Python hash seed for reproducibility | "random" | "12345" |

## Deployment Examples

### Local Development (docker-compose.yml)

```yaml
environment:
  # Server Configuration
  - SERVER_NAME=Music Library MCP - Local Development
  - SERVER_TRANSPORT=http
  - LOG_LEVEL=DEBUG
  - LOG_FORMAT=text

  # Authentication (disabled for dev)
  - AUTH_ENABLED=false
  - BEARER_TOKEN=dev-token-not-for-production

  # CORS (permissive for development)
  - ENABLE_CORS=true
  - CORS_ORIGINS=http://localhost:3000,http://localhost:8000,http://localhost:5173

  # Database (local PostgreSQL)
  - DB_HOST=postgres
  - DB_PORT=5432
  - DB_NAME=loist_mvp
  - DB_USER=loist_user
  - DB_PASSWORD=dev_password
```

### Cloud Run Production (cloudbuild.yaml)

```yaml
# Set via --set-env-vars in cloudbuild.yaml
SERVER_TRANSPORT=http
LOG_LEVEL=INFO
AUTH_ENABLED=false
ENABLE_CORS=true
CORS_ORIGINS=*
ENABLE_HEALTHCHECK=true
GCS_PROJECT_ID=$PROJECT_ID
SERVER_NAME=Music Library MCP
SERVER_VERSION=0.1.0
# GCS uses ADC + IAM SignBlob (no GOOGLE_APPLICATION_CREDENTIALS needed)
# ... additional variables ...
```

📚 **Complete Cloud Run Deployment Guide**: See [`docs/cloud-run-deployment.md`](docs/cloud-run-deployment.md) for comprehensive deployment setup, pipeline configuration, security considerations, and troubleshooting.

### Environment File (.env)

```bash
# Server Identity
SERVER_NAME="Music Library MCP"
SERVER_VERSION="0.1.0"

# Server Runtime
SERVER_HOST=0.0.0.0
SERVER_PORT=8080
SERVER_TRANSPORT=http

# Authentication
BEARER_TOKEN=your-secure-token-here
AUTH_ENABLED=true

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=music_library
DB_USER=music_user
DB_PASSWORD=secure_password

# Google Cloud Storage (Cloud Run uses ADC, no keyfile needed)
GCS_BUCKET_NAME=my-music-bucket
GCS_PROJECT_ID=my-project-123
# GOOGLE_APPLICATION_CREDENTIALS=/path/to/local/keyfile.json  # Local dev only

# CORS
ENABLE_CORS=true
CORS_ORIGINS=https://myapp.com,https://admin.myapp.com
```

## Security Considerations

### Sensitive Variables (Never in Code)

These variables contain sensitive information and should **never** be committed to version control:

- `BEARER_TOKEN` - Authentication token
- `DB_PASSWORD` - Database password
- `DB_USER` - Database username (sometimes considered sensitive)
- `GOOGLE_APPLICATION_CREDENTIALS` - Path to service account key (local dev only)
- `GCS_SERVICE_ACCOUNT_EMAIL` - Service account email (optional override)

### Secret Management

For production deployments:

1. **Google Cloud Run**: Use `--update-secrets` flag with Secret Manager. GCS uses ADC + IAM SignBlob (no keyfile secrets needed).
2. **Docker Compose**: Use `.env` file with `GOOGLE_APPLICATION_CREDENTIALS` for local GCS access (add to `.gitignore`)
3. **Kubernetes**: Use ConfigMaps for non-sensitive, Secrets for sensitive data

### Cloud Run Secrets Example

```yaml
# In cloudbuild.yaml
- '--update-secrets=BEARER_TOKEN=my-bearer-token-secret:latest'
- '--update-secrets=DB_PASSWORD=my-db-password-secret:latest'
- '--update-secrets=GCS_BUCKET_NAME=my-bucket-name-secret:latest'
# No GOOGLE_APPLICATION_CREDENTIALS secret needed - uses IAM SignBlob
```

## Validation

The application validates configuration on startup and provides detailed error messages for missing or invalid settings. Use the `health_check` MCP tool or `/health/live` and `/health/ready` HTTP endpoints to verify configuration after deployment.

## Configuration Loading Priority

Environment variables are loaded in this order (later sources override earlier ones):

1. Default values in `ServerConfig` class
2. Environment variables from system
3. Variables from `.env` file (if present)
4. Runtime overrides (for Cloud Run environment variables)
