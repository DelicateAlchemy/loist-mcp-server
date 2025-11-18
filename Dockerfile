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
COPY requirements.txt pyproject.toml ./

# Install dependencies and create wheels for faster runtime install
RUN pip install --upgrade pip && \
    pip wheel --no-cache-dir --wheel-dir=/wheels -r requirements.txt


# ============================================================================
# Stage 2: Runtime - Minimal production image
# ============================================================================
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies (if any system packages needed)
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash --uid 1000 fastmcpuser

# Copy wheels from builder stage
COPY --from=builder /wheels /wheels

# Copy dependency files
COPY --chown=fastmcpuser:fastmcpuser requirements.txt pyproject.toml ./

# Install dependencies from wheels (fast, no compilation)
RUN pip install --no-cache-dir --find-links=/wheels -r requirements.txt && \
    rm -rf /wheels

# Copy application code
COPY --chown=fastmcpuser:fastmcpuser src/ ./src/
COPY --chown=fastmcpuser:fastmcpuser database/ ./database/
COPY --chown=fastmcpuser:fastmcpuser run_server.py ./

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
    CMD python -c "import sys; sys.path.insert(0, 'src'); from server import mcp; print('healthy')" || exit 1

# Run the FastMCP server using the runner script
CMD ["python", "run_server.py"]

