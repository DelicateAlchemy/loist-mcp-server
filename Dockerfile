# Multi-stage Dockerfile for Music Library MCP Server
# Optimized for Google Cloud Run deployment with security and minimal size
#
# Security Features:
# - Non-root user execution (fastmcpuser/nonroot)
# - Minimal attack surface with Alpine/distroless images
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
    linux-headers \
    && pip install --upgrade pip

# Copy dependency files
COPY requirements.txt pyproject.toml ./

# Install dependencies and create wheels for faster runtime install
RUN pip wheel --no-cache-dir --wheel-dir=/wheels -r requirements.txt


# ============================================================================
# Stage 2: Runtime - Minimal production image
# ============================================================================
FROM python:3.11-alpine AS runtime

WORKDIR /app

# Install minimal runtime dependencies (Alpine uses apk)
RUN apk add --no-cache \
    ca-certificates \
    && addgroup -g 1000 -S fastmcpuser \
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

# Ensure proper permissions and remove any world-writable files
RUN find /app -type f -exec chmod 644 {} \; && \
    find /app -type d -exec chmod 755 {} \; && \
    chmod +x /app/src/server.py

# Switch to non-root user
USER fastmcpuser

# Environment variables (can be overridden at runtime)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SERVER_HOST=0.0.0.0 \
    SERVER_PORT=8080 \
    LOG_LEVEL=INFO \
    # Security hardening
    PYTHONPATH=/app/src \
    PYTHONHASHSEED=random \
    # Ensure container is ephemeral/stateless
    HOME=/tmp \
    TMPDIR=/tmp

# Expose port (Cloud Run automatically maps to $PORT)
EXPOSE 8080

# Health check for Docker/local development (Cloud Run uses HTTP probes)
# Note: For production Cloud Run deployment, implement HTTP health endpoint at /health
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import sys; sys.path.insert(0, 'src'); from server import mcp; print('healthy')" || exit 1

# Run the FastMCP server
CMD ["python", "src/server.py"]


# ============================================================================
# Stage 3: Distroless - Ultra-minimal production image (alternative)
# Note: Distroless removes shell access, so health checks and debugging are limited.
# Use 'runtime' stage for production unless minimal attack surface is critical.
# ============================================================================
FROM gcr.io/distroless/python3-debian12:nonroot AS distroless

WORKDIR /app

# Copy Python runtime and application from runtime stage
# Note: This requires careful dependency management as distroless has no package manager
COPY --from=runtime --chown=nonroot:nonroot /usr/local /usr/local
COPY --from=runtime --chown=nonroot:nonroot /app /app

# Switch to non-root user (distroless provides 'nonroot' user)
USER nonroot

# Environment variables (can be overridden at runtime)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SERVER_HOST=0.0.0.0 \
    SERVER_PORT=8080 \
    LOG_LEVEL=INFO \
    # Security hardening
    PYTHONPATH=/app/src \
    PYTHONHASHSEED=random \
    # Ensure container is ephemeral/stateless
    HOME=/tmp \
    TMPDIR=/tmp

# Expose port (Cloud Run automatically maps to $PORT)
EXPOSE 8080

# Run the FastMCP server (no shell available in distroless - no health checks possible)
CMD ["python", "src/server.py"]

