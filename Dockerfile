# Multi-stage Dockerfile for Music Library MCP Server
# Optimized for Google Cloud Run deployment

# ============================================================================
# Stage 1: Builder - Install dependencies
# ============================================================================
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY requirements.txt requirements-dev.txt pyproject.toml ./

# Install dependencies and create wheels for faster runtime install
RUN pip install --upgrade pip && \
    pip wheel --no-cache-dir --wheel-dir=/wheels -r requirements.txt && \
    pip wheel --no-cache-dir --wheel-dir=/wheels -r requirements-dev.txt


# ============================================================================
# Stage 2: Runtime - Minimal production image
# ============================================================================
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install runtime dependencies (if any system packages needed)
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    ca-certificates \
    libimage-exiftool-perl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash --uid 1000 fastmcpuser

# Copy wheels from builder stage
COPY --from=builder /wheels /wheels

# Copy dependency files
COPY --chown=fastmcpuser:fastmcpuser requirements.txt requirements-dev.txt pyproject.toml ./

# Install dependencies from wheels (fast, no compilation)
RUN pip install --no-cache-dir --find-links=/wheels -r requirements.txt && \
    pip install --no-cache-dir --find-links=/wheels -r requirements-dev.txt && \
    rm -rf /wheels

# Copy application code
COPY --chown=fastmcpuser:fastmcpuser src/ ./src/
COPY --chown=fastmcpuser:fastmcpuser database/ ./database/
COPY --chown=fastmcpuser:fastmcpuser run_server.py ./
COPY --chown=fastmcpuser:fastmcpuser tests/ ./tests/

# Copy templates directory
COPY --chown=fastmcpuser:fastmcpuser templates/ ./templates/

# Switch to non-root user
USER fastmcpuser

# Environment variables (can be overridden at runtime)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    SERVER_HOST=0.0.0.0 \
    SERVER_PORT=8080 \
    LOG_LEVEL=INFO

# Expose port (Cloud Run automatically maps to $PORT)
EXPOSE 8080

# Health check (for Docker, Cloud Run uses HTTP probes)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from src.server import mcp; print('healthy')" || exit 1

# Run the FastMCP server using the runner script
CMD ["python", "run_server.py"]


# ============================================================================
# Stage 3: A2A Server - A2A agent server image
# ============================================================================
FROM runtime AS a2a

# Override environment variables for A2A server
ENV SERVER_PORT=8081 \
    PORT=8081

# Expose A2A server port
EXPOSE 8081

# Health check for A2A server (Agent Card endpoint)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8081/.well-known/agent-card.json')" || exit 1

# Run the A2A server
CMD ["python", "src/a2a_server/app.py"]

