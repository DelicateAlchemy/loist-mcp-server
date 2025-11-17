# Loist MCP Server

FastMCP-based server for audio ingestion and embedding with the Music Library MCP protocol.

## Overview

This project implements a Model Context Protocol (MCP) server using the FastMCP framework for managing audio file ingestion, processing, and embedding generation for a music library system.

### Architecture Highlights

The server features a modern, scalable architecture with:

- **Repository Pattern**: Clean data access abstraction with dependency injection
- **Unified Exception Framework**: Comprehensive error handling with automatic recovery strategies
- **Performance Optimizations**: 75-80% faster database operations with batch processing
- **Comprehensive Testing**: 85%+ test coverage with automated performance validation
- **Clean FastMCP Integration**: Zero workarounds for exception serialization
- **Production-Ready**: Optimized for Cloud Run with connection pooling and health monitoring

## MCP Server Naming Strategy

This project supports local development, staging, and production deployments with distinct naming conventions to avoid conflicts in MCP client configurations:

### Local Development
- **Cursor MCP Server Name**: `loist-music-library-local`
- **FastMCP Server Name**: `Music Library MCP - Local Development`
- **Environment**: Docker containers with local PostgreSQL + GCS integration
- **Transport**: stdio (for Cursor MCP integration)

### Development/Staging Environment
- **Cursor MCP Server Name**: `loist-music-library-staging`
- **FastMCP Server Name**: `Music Library MCP - Staging`
- **Environment**: Cloud Run with staging PostgreSQL + dedicated GCS staging buckets
- **Transport**: http/sse (for integration testing and QA)
- **Deployment**: Cloud Build trigger on `dev` branch (`cloudbuild-staging.yaml`)
- **Purpose**: Pre-production validation, integration testing, QA verification
- **Infrastructure**: Separate Cloud Run service, staging GCS buckets, staging database

### Production Deployment
- **Cursor MCP Server Name**: `loist-music-library` (production)
- **FastMCP Server Name**: `Music Library MCP - Production`
- **Environment**: GCloud infrastructure (Cloud SQL + GCS)
- **Transport**: Configurable (stdio/http/sse)

## Architecture

### Google Cloud Infrastructure Overview

The system is built on Google Cloud Platform with a modern serverless architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                    Google Cloud Platform                    │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────┐ │
│  │ Cloud Build │───▶│  Artifact    │───▶│   Cloud Run     │ │
│  │   CI/CD     │    │  Registry    │    │ (Serverless)    │ │
│  └─────────────┘    └──────────────┘    └─────────────────┘ │
│                                                ▲             │
│  ┌─────────────┐    ┌──────────────┐         │             │
│  │   Cloud     │    │    Secret    │         │             │
│  │    SQL      │◀───┤   Manager    │◀────────┘             │
│  │(PostgreSQL) │    │              │                       │
│  └─────────────┘    └──────────────┘                       │
│                                                             │
│  ┌─────────────┐    ┌──────────────┐                       │
│  │   Cloud     │    │     IAM      │                       │
│  │  Storage    │◀───┤  SignBlob    │◀──────────────────────┘
│  │   (GCS)     │    │    API       │                        
│  └─────────────┘    └──────────────┘                        
└─────────────────────────────────────────────────────────────┘
```

**Key Infrastructure Components:**
- **Cloud Run**: Serverless container platform with auto-scaling
- **Cloud SQL**: Managed PostgreSQL with connection pooling
- **Cloud Storage**: Object storage with signed URL generation via IAM SignBlob
- **Cloud Build**: Automated CI/CD with vulnerability scanning
- **Secret Manager**: Secure credential and configuration management
- **Artifact Registry**: Container image storage and management
- **IAM**: Service account impersonation for secure GCS access

### Application Architecture

The server implements a layered architecture with clear separation of concerns:

```
┌─────────────────┐
│   FastMCP       │  ← Protocol Layer (MCP v1.16.0)
│   Protocol      │
├─────────────────┤
│ Business Logic  │  ← Service Layer (Repository Pattern)
│ Repository      │
├─────────────────┤
│ Data Access     │  ← Persistence Layer
│ PostgreSQL      │    (Cloud SQL + GCS)
│ Google Cloud    │
│ Storage         │
└─────────────────┘
```

### Key Architectural Improvements

#### Repository Pattern Implementation
- **Clean Data Access**: Abstract interface with multiple implementations
- **Dependency Injection**: Testable code with mock repositories
- **Performance**: Optimized batch operations and connection pooling

#### Unified Exception Framework
- **Consistent Error Handling**: Single framework across all components
- **Recovery Strategies**: Automatic retry and circuit breaker patterns
- **FastMCP Integration**: Clean error serialization without workarounds

#### Database Performance Optimizations
- **Batch Operations**: 5x faster bulk inserts
- **Smart Indexing**: 10+ performance indexes for optimal queries
- **Connection Pooling**: Optimized for Cloud Run serverless

#### Comprehensive Testing Strategy
- **85%+ Coverage**: Unit, integration, and performance tests
- **Database Testing Infrastructure**: Complete testing for migrations, connection pools, transactions, full-text search, and data integrity
- **Automated Validation**: Performance regression detection
- **Docker Integration**: Isolated test database environment
- **CI/CD Integration**: Automated testing on every deployment

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

## Development & Testing

### Development Workflow

The project follows a structured development workflow with comprehensive testing:

1. **Feature Development**: Use Task Master for task breakdown and tracking
2. **Code Implementation**: Follow repository pattern and exception framework
3. **Testing**: Run comprehensive test suite with `pytest`
4. **Performance Validation**: Automated performance regression testing
5. **Documentation**: Update technical docs for architectural changes

### Testing Strategy

The project implements a multi-layer testing approach:

#### Unit Testing
```bash
# Run all unit tests
pytest tests/test_*.py -v

# Run with coverage
pytest --cov=src --cov-report=html
```

#### Integration Testing
```bash
# Database integration tests
pytest tests/test_*_integration.py -v

# Performance benchmarks
pytest tests/test_database_operations_integration.py::TestBatchOperations -v
```

#### Test Categories
- **85%+ Coverage**: Comprehensive unit and integration tests
- **Performance Testing**: Automated regression detection
- **Exception Testing**: Unified framework validation
- **Repository Testing**: Dependency injection and mocking
- **Full-Text Search Testing**: Index validation, query accuracy, performance, and relevance testing

#### Security Scanning
```bash
# Run comprehensive security scan
./scripts/security-scan.sh

# Run individual security tools
bandit -r src/ -f json -o reports/bandit-scan.json
safety scan --output json --target .
```

#### Security Categories
- **Bandit Analysis**: Python security vulnerability scanning
- **Safety Checks**: Dependency vulnerability assessment
- **Custom Security**: Hardcoded secrets, debug code, file permissions
- **Baseline Enforcement**: Zero-tolerance for high-severity issues

### Documentation

Comprehensive documentation is available in the `docs/` directory:

- **[Architecture Overview](docs/architecture-overview.md)**: Complete system architecture
- **[Exception Handling Guide](docs/exception-handling-guide.md)**: Unified error framework
- **[Database Best Practices](docs/database-best-practices.md)**: Performance optimizations
- **[Module Organization Guide](docs/module-organization-guide.md)**: Code structure patterns
- **[Testing Strategy](docs/testing-strategy-and-recovery.md)**: Comprehensive testing approach
- **[Security Scanning Guide](docs/security-scanning.md)**: Security infrastructure and scanning tools

### Key Development Commands

```bash
# Run full test suite
pytest

# Run with performance monitoring
pytest --durations=10

# Run database integration tests
pytest tests/test_database_operations_integration.py

# Generate coverage report
pytest --cov=src --cov-report=html && open htmlcov/index.html

# Run security scanning
./scripts/security-scan.sh

# Run individual security tools
bandit -r src/
safety scan --target .
```

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
│   ├── exceptions/         # Unified exception framework
│   │   ├── __init__.py    # Framework exports
│   │   ├── handler.py     # Core exception handler
│   │   ├── context.py     # Exception context system
│   │   ├── recovery.py    # Recovery strategies
│   │   ├── config.py      # Configuration options
│   │   └── fastmcp_integration.py # FastMCP integration
│   │
│   ├── repositories/       # Data access layer
│   │   ├── __init__.py    # Repository exports
│   │   └── audio_repository.py # Audio repository interface & implementations
│   │
│   ├── fastmcp_setup.py   # Clean FastMCP initialization
│   ├── server.py          # MCP server and tool registration
│   ├── config.py          # Application configuration
│   │
│   ├── resources/         # MCP resource handlers
│   │   ├── __init__.py
│   │   ├── metadata.py    # Metadata resource
│   │   ├── audio_stream.py # Audio streaming resource
│   │   └── thumbnail.py   # Thumbnail resource
│   │
│   ├── tools/             # MCP tool implementations
│   │   ├── __init__.py
│   │   ├── process_audio.py # Audio processing tool
│   │   └── query_tools.py # Search and query tools
│   │
│   ├── auth/              # Authentication module
│   │   ├── __init__.py
│   │   └── bearer.py      # Bearer token authentication
│   │
│   └── exceptions.py      # Legacy exception classes (backward compatibility)
│
├── database/              # Database layer
│   ├── __init__.py
│   ├── operations.py      # Database operations
│   ├── pool.py           # Connection pooling
│   ├── config.py         # Database configuration
│   └── migrations/       # Schema migrations
│
├── tests/                 # Comprehensive test suite
│   ├── conftest.py       # Test configuration and fixtures
│   ├── test_*.py         # Unit tests
│   ├── test_*_integration.py # Integration tests
│   └── __pycache__/
│
├── docs/                  # Technical documentation
│   ├── architecture-overview.md      # System architecture
│   ├── exception-handling-guide.md   # Error framework
│   ├── database-best-practices.md    # DB optimizations
│   ├── module-organization-guide.md  # Code structure
│   ├── testing-strategy-and-recovery.md # Testing approach
│   └── [additional docs...]
│
├── scripts/               # Utility scripts
├── tasks/                 # Task Master files
├── requirements.txt       # Python dependencies
├── pyproject.toml        # Project configuration
├── .env.example          # Example environment variables
└── README.md             # This file
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

#### Architecture & Design
- ✅ **Repository Pattern**: Clean data access abstraction with dependency injection
- ✅ **Unified Exception Framework**: Comprehensive error handling with recovery strategies
- ✅ **Performance Optimizations**: 75-80% faster database operations with batch processing
- ✅ **Clean FastMCP Integration**: Zero workarounds for exception serialization
- ✅ **Layered Architecture**: Clear separation between protocol, business logic, and data layers

#### FastMCP & Protocol
- ✅ FastMCP server initialization (v2.12.4, MCP v1.16.0)
- ✅ Advanced configuration management with Pydantic
- ✅ Lifespan hooks (startup/shutdown)
- ✅ Multiple transport modes (STDIO, HTTP, SSE)
- ✅ Tool and resource registration patterns

#### Database & Storage
- ✅ PostgreSQL integration with optimized connection pooling
- ✅ Google Cloud Storage for audio file management
- ✅ Comprehensive indexing strategy (10+ performance indexes)
- ✅ Batch operations with transaction management
- ✅ Migration system with zero-downtime deployments

#### Error Handling & Reliability
- ✅ Unified exception framework with automatic recovery
- ✅ Circuit breaker and retry patterns
- ✅ Structured error responses with context
- ✅ Comprehensive logging with performance monitoring
- ✅ Health checks and system monitoring

#### Security & Configuration
- ✅ Bearer token authentication (SimpleBearerAuth)
- ✅ CORS configuration for iframe embedding
- ✅ Environment-based configuration management
- ✅ Sensitive data masking in error messages
- ✅ Input validation and sanitization

#### Testing & Quality
- ✅ Comprehensive test suite (85%+ coverage)
- ✅ Automated performance regression testing
- ✅ Repository pattern testing with mocks
- ✅ Integration testing with Docker database
- ✅ Exception framework validation
- ✅ **Security Scanning Infrastructure**: Bandit, Safety, custom checks
- ✅ **Security Baseline Enforcement**: Zero-tolerance for high-severity issues

#### Development Experience
- ✅ Task Master integration for structured development
- ✅ Comprehensive documentation suite
- ✅ Type hints and documentation standards
- ✅ Development/production configuration profiles
- ✅ Clean module organization with clear boundaries

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

Using the comprehensive build and validation script:
```bash
./scripts/test-container-build.sh
```

Or using the build script:
```bash
./scripts/docker/build.sh
```

Or manually:
```bash
docker build -t music-library-mcp:latest .
```

**Image Details:**
- **Multi-stage Build**: Builder (Alpine) → Runtime (Alpine)
- **Base Image**: `python:3.11-alpine`
- **Size**: ~180MB (highly optimized multi-stage build)
- **User**: Non-root (`fastmcpuser` with UID 1000)
- **Security**: Hardened with minimal attack surface, proper permissions, and stateless design
- **Dependencies**: Includes `psutil`, `fastmcp`, and all required libraries
- **Health Checks**: Built-in health check with 30s startup period for Cloud Run compatibility

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

The project includes a comprehensive automated deployment pipeline using Google Cloud Build with vulnerability scanning, optimized builds, and complete environment variable configuration.

#### Automated Deployment (Recommended)

Use the Cloud Build pipeline defined in `cloudbuild.yaml`:

```bash
# Trigger automated deployment via Cloud Build triggers
# Push to main/dev branch to automatically trigger deployment
git push origin main  # Production deployment
git push origin dev   # Staging deployment
```

#### Manual Deployment (Alternative)

For manual deployment, use the provided scripts:

```bash
# 1. Create Artifact Registry repository (one-time setup)
./scripts/create-artifact-registry.sh

# 2. Build and push image
docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT/music-library-repo/music-library-mcp:latest .
docker push us-central1-docker.pkg.dev/YOUR_PROJECT/music-library-repo/music-library-mcp:latest

# 3. Deploy to Cloud Run
gcloud run deploy music-library-mcp \
  --image us-central1-docker.pkg.dev/YOUR_PROJECT/music-library-repo/music-library-mcp:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --timeout 600s \
  --set-env-vars-file env-vars.yaml
```

#### Deployment Features

- ✅ **Automated CI/CD**: GitHub-triggered Cloud Build deployments for `main` and `dev` branches
- ✅ **Vulnerability Scanning**: Automated image vulnerability detection
- ✅ **Multi-stage Optimization**: Alpine builder → Alpine runtime for security and reliability
- ✅ **Comprehensive Environment Variables**: 50+ environment variables configured
- ✅ **Secret Management**: Database and GCS credentials via Secret Manager
- ✅ **Artifact Registry**: Modern container registry with better performance
- ✅ **Build Optimization**: Layer caching, BuildKit, and high-performance machines
- ✅ **Deployment Validation**: Automated validation scripts for post-deployment verification
- ✅ **Database Migrations**: Automatic migration execution during deployment (all schemas applied)

#### Deployment Validation

Validate deployments using the comprehensive validation suite:

```bash
# Run full validation
./scripts/validate-deployment.sh

# Individual component validation
./scripts/test-deployment-triggers.sh  # Cloud Build triggers
./scripts/validate-cloud-run.sh        # Service accessibility
./scripts/validate-database.sh         # Database connectivity
./scripts/validate-gcs.sh              # Storage operations
```

**Validation Documentation**:
- [Deployment Validation Guide](docs/deployment-validation-guide.md) - How to run validations
- [Validation Results](docs/deployment-validation-results.md) - Latest validation status
- [Troubleshooting Guide](docs/troubleshooting-deployment.md) - Common issues
- [Rollback Procedures](docs/deployment-rollback-procedure.md) - How to rollback

📚 **Full Deployment Documentation**: See [`docs/cloud-run-deployment.md`](docs/cloud-run-deployment.md) for complete setup instructions, troubleshooting, and configuration details.

#### Custom Domain & HTTPS Configuration

For production deployments with custom domains and automatic HTTPS:

- **Current Status**: Domain mapping configured but blocked by service readiness issues
- **Implementation**: Global External Application Load Balancer (recommended)
- **SSL Certificates**: Google-managed certificates with automatic provisioning
- **DNS Configuration**: A/AAAA records pointing to load balancer IP

📚 **Custom Domain Setup Guide**: See [`docs/custom-domain-mapping-guide.md`](docs/custom-domain-mapping-guide.md) for comprehensive HTTPS and custom domain implementation.

## Cloud Build CI/CD - GitHub Triggers Only

The project uses **Google Cloud Build exclusively** for all CI/CD operations. GitHub serves only as a trigger mechanism for Cloud Build pipelines.

### Architecture

```
GitHub (Triggers Only)
    ↓
Google Cloud Build (Full CI/CD)
    ↓
Production/Staging Deployment
```

### Cloud Build Pipelines

#### Production Pipeline (`cloudbuild.yaml`)
**Triggered by pushes to `main` branch**

1. **Unit Tests** - Fast tests without external dependencies (75% coverage required)
2. **Database Tests** - Integration tests using testcontainers (70% coverage required)
3. **Database Connectivity** - Verify database connectivity before deployment
4. **MCP Validation** - Protocol compliance testing
5. **Static Analysis** - Code quality checks (black, isort, mypy, flake8, bandit)
6. **Database Migrations** - Apply all pending database migrations
7. **Build & Deploy** - Container build and Cloud Run deployment

#### Staging Pipeline (`cloudbuild-staging.yaml`)
**Triggered by pushes to `dev` branch**

Same comprehensive pipeline as production but with:
- Relaxed coverage thresholds (65% unit, 60% database)
- Warning-only test failures (continues deployment)
- Staging-specific environment variables and secrets
- Database migrations run post-deployment (not during Cloud Build)

### Test Strategy

**Marker-based automatic filtering** using root `conftest.py`:

```python
# Database tests: pytest -m "requires_db" (with testcontainers)
# Unit tests: pytest -m "not (requires_db or requires_gcs or slow)"
# GCS tests: pytest -m "requires_gcs"
```

**Test Execution:**

| Environment | Unit Tests | Database Tests | Failure Behavior |
|-------------|------------|----------------|------------------|
| Production  | ✅ Blocking | ✅ Blocking    | Fail build       |
| Staging     | ⚠️ Warning  | ⚠️ Warning     | Continue deploy  |

### Database Testing with TestContainers

- **Isolated Testing**: Fresh PostgreSQL container per test run
- **No External Dependencies**: Self-contained CI/CD environment
- **Parallel Execution**: Tests run concurrently for speed
- **Production Ready**: Validates real database interactions

### Artifact Storage

All test artifacts automatically stored in Google Cloud Storage:
- `gs://$PROJECT_ID-build-artifacts/$COMMIT_SHA/`
- Test results, coverage reports, MCP validation, migration status

### GitHub Configuration

**Minimal trigger workflow** (`.github/workflows/cloud-build-trigger.yml`):

```yaml
name: Cloud Build Trigger
on:
  push:
    branches: [ main, dev ]
jobs:
  trigger-cloud-build:
    runs-on: ubuntu-latest
    steps:
    - name: Trigger Cloud Build
      run: gcloud builds submit --config=cloudbuild.yaml
```

### Benefits

- ✅ **Single Source of Truth**: All CI/CD logic in Cloud Build
- ✅ **Cost Effective**: No duplicate GitHub Actions infrastructure
- ✅ **Better Performance**: Optimized for Google Cloud
- ✅ **Security**: Secrets in Google Secret Manager
- ✅ **Scalability**: Handles large builds and complex testing

### Documentation

- [Cloud Build CI/CD Setup](docs/cloud-build-ci-cd-setup.md) - Complete Cloud Build configuration guide
- [Testing Practices Guide](docs/testing-practices-guide.md) - Comprehensive testing infrastructure
- [Cloud Run Deployment](docs/cloud-run-deployment.md) - Production deployment details

📚 **Full Documentation:**
- [Testing Practices Guide](docs/testing-practices-guide.md) - Comprehensive testing infrastructure and CI/CD
- [Pre-PR Testing Guide](docs/pre-pr-testing-guide.md) - Local testing before pull requests
- [Cloud Run Deployment](docs/cloud-run-deployment.md) - Production deployment details
- [Security Scanning](docs/security-scanning.md) - Security scanning and vulnerability management

### Running Workflows

1. Go to **Actions** tab in GitHub
2. Select desired workflow:
   - **MCP Server Validation** (runs automatically on push/PR)
   - **Database Provisioning** (manual dispatch)
3. For manual workflows: Click **Run workflow** → Choose action → **Run workflow**

## Development

### Install Development Dependencies

```bash
uv pip install -e ".[dev]"
```

### Running Tests

```bash
# Install testing dependencies first (if not already installed)
pip install pytest pytest-asyncio pytest-mock pytest-cov

# Run all tests
pytest tests/

# Run tests with coverage report
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_process_audio_complete.py
```

### Code Quality & Static Analysis

The project uses comprehensive static analysis tools for code quality assurance:

#### Automated Quality Checks (Recommended)

```bash
# Install pre-commit hooks for automated quality checks
pip install pre-commit
pre-commit install

# Run all quality checks on staged files
pre-commit run

# Run all quality checks on all files
pre-commit run --all-files
```

#### Manual Quality Checks

##### Code Formatting & Import Sorting

```bash
# Install formatting tools
pip install black isort

# Format code with black (100 char line length)
black src/ tests/ database/

# Sort imports with isort (compatible with black)
isort src/ tests/ database/

# Check formatting without making changes
black --check --diff src/ tests/ database/
isort --check-only --diff src/ tests/ database/
```

##### Linting & Code Quality

```bash
# Install linting tools
pip install flake8 pylint bandit safety

# Fast linting with flake8 (PEP8 + PyFlakes + McCabe)
flake8 src/ tests/ database/

# Comprehensive analysis with pylint
pylint src/ tests/ database/

# Security vulnerability scanning
bandit -r src/ database/

# Dependency vulnerability scanning
safety check
```

##### Type Checking

```bash
# Install type checking tools
pip install mypy

# Run type checking with strict settings
mypy src/ database/

# Run with detailed error codes
mypy src/ database/ --show-error-codes

# Check specific module
mypy src/server.py
```

## Configuration

Configuration is managed through environment variables using the `src/config.py` module with Pydantic Settings. The server supports 50+ environment variables across all functional areas.

### Environment Variables

📚 **Complete Environment Variables Reference**: See [`docs/environment-variables.md`](docs/environment-variables.md) for comprehensive documentation of all environment variables, their purposes, default values, and configuration examples.

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
- **Automated Deployment Config**: Cloud Build pipeline automatically configures 50+ environment variables
- **Secret Management**: Sensitive data (database credentials, GCS keys) managed via Google Secret Manager
- **Validation Scripts**: `scripts/validate-env-config.sh` ensures configuration consistency across environments

### Deployment-Specific Configuration

- **Local Development**: Basic configuration via `.env` file with sensible defaults
- **Cloud Run Production**: Comprehensive environment variables configured via `cloudbuild.yaml`
- **Docker Compose**: Environment-specific overrides for development and staging
- **Validation**: Automated scripts ensure configuration consistency across all deployment methods

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


# Force staging deployment with embed fixes
