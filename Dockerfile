# Multi-stage Dockerfile for Music Library MCP Server
# Optimized for Google Cloud Run deployment with security and minimal size
#
# Security Features:
# - Non-root user execution (fastmcpuser)
# - Minimal attack surface with Alpine Linux
# - Proper file permissions (644/755)
# - No world-writable files
# - Ephemeral/stateless container design
# - Security hardening environment variables
# - Cleaned up build artifacts and cache files

# ============================================================================
# Stage 1: Builder - Install dependencies
# ============================================================================
FROM python:3.11-alpine AS builder

WORKDIR /build

# Install build dependencies (Alpine uses apk)
RUN apk add --no-cache \
    build-base \
    linux-headers

# Upgrade pip
RUN pip install --upgrade pip

# Copy dependency files first (for better caching)
COPY requirements.txt pyproject.toml ./

# Install dependencies and create wheels for faster runtime install
RUN pip wheel --wheel-dir=/wheels -r requirements.txt


# ============================================================================
# Stage 2: Runtime - Minimal production image
# ============================================================================
FROM python:3.11-alpine AS runtime

WORKDIR /app

# Install minimal runtime dependencies (Alpine uses apk)
RUN apk add --no-cache \
    ca-certificates \
    postgresql-client \
    postgresql-dev \
    ffmpeg

# Create non-root user and directories
RUN addgroup -g 1000 -S fastmcpuser \
    && adduser -u 1000 -S fastmcpuser -G fastmcpuser \
    && mkdir -p /app \
    && chown -R fastmcpuser:fastmcpuser /app

# Copy wheels from builder stage
COPY --from=builder /wheels /wheels

# Copy dependency files
COPY --chown=fastmcpuser:fastmcpuser requirements.txt pyproject.toml ./

# Install dependencies from wheels (fast, no compilation)
RUN pip install --no-cache-dir --find-links=/wheels -r requirements.txt && \
    rm -rf /wheels && \
    find /usr/local -type f -name "*.pyc" -delete && \
    find /usr/local -type d -name "__pycache__" -exec rm -rf {} + || true

# Copy application code with proper permissions
COPY --chown=fastmcpuser:fastmcpuser src/ ./src/
COPY --chown=fastmcpuser:fastmcpuser database/ ./database/
COPY --chown=fastmcpuser:fastmcpuser templates/ ./templates/

# Ensure proper permissions and remove any world-writable files
RUN find /app -type f -exec chmod 644 {} \; && \
    find /app -type d -exec chmod 755 {} \; && \
    chmod +x /app/src/server.py

# Switch to non-root user
USER fastmcpuser

# Environment variables (can be overridden at runtime)

# Server Identity (set at runtime for environment-specific names)
# ENV SERVER_NAME - Set via Cloud Run --set-env-vars per environment
ENV SERVER_VERSION="0.1.0"
ENV SERVER_INSTRUCTIONS="MCP server for audio ingestion and embedding. Use health_check to verify server status. Future capabilities will include audio file processing and embedding generation."

# Server Runtime
ENV SERVER_HOST="0.0.0.0"
ENV SERVER_PORT="8080"
ENV SERVER_TRANSPORT="http"

# Logging
ENV LOG_LEVEL="INFO"
ENV LOG_FORMAT="text"

# MCP Protocol
ENV MCP_PROTOCOL_VERSION="2024-11-05"
ENV INCLUDE_FASTMCP_META="true"

# Duplicate Handling Policies
ENV ON_DUPLICATE_TOOLS="error"
ENV ON_DUPLICATE_RESOURCES="warn"
ENV ON_DUPLICATE_PROMPTS="replace"

# Performance
ENV MAX_WORKERS="4"
ENV REQUEST_TIMEOUT="30"

# Storage Configuration
ENV STORAGE_PATH="/tmp/storage"
ENV MAX_FILE_SIZE="104857600"

# Google Cloud Storage (non-sensitive defaults)
ENV GCS_REGION="us-central1"
ENV GCS_SIGNED_URL_EXPIRATION="900"

# Database Configuration (non-sensitive defaults)
ENV DB_PORT="5432"
ENV DB_MIN_CONNECTIONS="2"
ENV DB_MAX_CONNECTIONS="10"
ENV DB_COMMAND_TIMEOUT="30"

# CORS Configuration
ENV ENABLE_CORS="true"
ENV CORS_ORIGINS="*"
ENV CORS_ALLOW_CREDENTIALS="true"
ENV CORS_ALLOW_METHODS="GET,POST,OPTIONS"
ENV CORS_ALLOW_HEADERS="Authorization,Content-Type,Range,X-Requested-With,Accept,Origin"
ENV CORS_EXPOSE_HEADERS="Content-Range,Accept-Ranges,Content-Length,Content-Type"

# Embed Configuration (set at runtime via Cloud Run --set-env-vars)
# ENV EMBED_BASE_URL - Do not set default, must be configured per environment

# Feature Flags
ENV ENABLE_METRICS="false"
ENV ENABLE_HEALTHCHECK="true"

# Python Runtime (security hardening)
ENV PYTHONUNBUFFERED="1"
ENV PYTHONDONTWRITEBYTECODE="1"
ENV PYTHONPATH="/app/src"
ENV PYTHONHASHSEED="random"

# Container Ephemeral/Stateless Configuration
ENV HOME="/tmp"
ENV TMPDIR="/tmp"

# Expose port (Cloud Run automatically maps to $PORT)
EXPOSE 8080

# Health check for Docker/local development (Cloud Run uses HTTP probes)
# Note: For production Cloud Run deployment, implement HTTP health endpoint at /health
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import sys; sys.path.insert(0, 'src'); from server import mcp; print('healthy')" || exit 1

# Run the FastMCP server
# Use absolute path for Python to ensure Cloud Run compatibility
CMD ["/usr/local/bin/python", "/app/src/server.py"]

