#!/bin/bash

# Local Development Setup Script
# This script helps set up the local development environment

set -e  # Exit on any error

# Configuration variables
PROJECT_ROOT="/Users/Gareth/loist-mcp-server"
ENV_FILE="$PROJECT_ROOT/.env.local"
SERVICE_ACCOUNT_KEY="$PROJECT_ROOT/service-account-key.json"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if .env.local exists
check_env_file() {
    log "Checking for .env.local file..."
    
    if [ -f "$ENV_FILE" ]; then
        success ".env.local file found"
        return 0
    else
        warning ".env.local file not found"
        return 1
    fi
}

# Create .env.local from template
create_env_file() {
    log "Creating .env.local file..."
    
    cat > "$ENV_FILE" << 'EOF'
# Local Development Environment Configuration
# This file contains environment variables for local development
# DO NOT commit this file to version control

# ============================================================================
# Server Configuration
# ============================================================================
SERVER_NAME="Music Library MCP - Local Development"
SERVER_VERSION="0.1.0"
SERVER_HOST="0.0.0.0"
SERVER_PORT="8080"
SERVER_TRANSPORT="http"
LOG_LEVEL="DEBUG"
LOG_FORMAT="text"

# ============================================================================
# Authentication
# ============================================================================
AUTH_ENABLED=false
BEARER_TOKEN=""

# ============================================================================
# Google Cloud Storage Configuration
# ============================================================================
GCS_BUCKET_NAME="loist-music-library-dev"
GCS_PROJECT_ID="loist-music-library"
GCS_REGION="us-central1"
GCS_SIGNED_URL_EXPIRATION="900"
GCS_SERVICE_ACCOUNT_EMAIL=""
GOOGLE_APPLICATION_CREDENTIALS="/Users/Gareth/loist-mcp-server/service-account-key.json"

# ============================================================================
# Database Configuration (Cloud SQL Proxy)
# ============================================================================
# Cloud SQL Proxy connection (when proxy is running)
DB_HOST="localhost"
DB_PORT="5432"
DB_NAME="music_library"
DB_USER="music_library_user"
DB_PASSWORD=""
DB_CONNECTION_NAME="loist-music-library:us-central1:loist-music-library-db"
DB_MIN_CONNECTIONS="2"
DB_MAX_CONNECTIONS="10"
DB_COMMAND_TIMEOUT="30"

# ============================================================================
# CORS Configuration
# ============================================================================
ENABLE_CORS=true
CORS_ORIGINS="http://localhost:3000,http://localhost:8080,http://127.0.0.1:3000,http://127.0.0.1:8080"
CORS_ALLOW_CREDENTIALS=true
CORS_ALLOW_METHODS="GET,POST,OPTIONS"
CORS_ALLOW_HEADERS="Authorization,Content-Type,Range,X-Requested-With,Accept,Origin"
CORS_EXPOSE_HEADERS="Content-Range,Accept-Ranges,Content-Length,Content-Type"

# ============================================================================
# Feature Flags
# ============================================================================
ENABLE_METRICS=false
ENABLE_HEALTHCHECK=true

# ============================================================================
# Storage Configuration
# ============================================================================
STORAGE_PATH="./storage"
MAX_FILE_SIZE="104857600"

# ============================================================================
# Performance Configuration
# ============================================================================
MAX_WORKERS="4"
REQUEST_TIMEOUT="30"

# ============================================================================
# Development-Specific Settings
# ============================================================================
DEBUG=true
FLASK_ENV="development"
EOF
    
    success ".env.local file created"
}

# Check if service account key exists
check_service_account() {
    log "Checking for service account key..."
    
    if [ -f "$SERVICE_ACCOUNT_KEY" ]; then
        success "Service account key found"
        return 0
    else
        error "Service account key not found at: $SERVICE_ACCOUNT_KEY"
        return 1
    fi
}

# Check if Cloud SQL Proxy is running
check_cloud_sql_proxy() {
    log "Checking if Cloud SQL Proxy is running..."
    
    if docker ps -q -f name="cloud-sql-proxy-local" | grep -q .; then
        success "Cloud SQL Proxy is running"
        return 0
    else
        warning "Cloud SQL Proxy is not running"
        echo "To start Cloud SQL Proxy, run:"
        echo "  ./scripts/setup-cloud-sql-proxy.sh"
        return 1
    fi
}

# Check if Docker image is built
check_docker_image() {
    log "Checking if Docker image is built..."
    
    if docker images | grep -q "loist-mcp-server:local"; then
        success "Docker image 'loist-mcp-server:local' is built"
        return 0
    else
        warning "Docker image 'loist-mcp-server:local' is not built"
        echo "To build Docker image, run:"
        echo "  docker build -t loist-mcp-server:local ."
        return 1
    fi
}

# Display setup status
show_setup_status() {
    log "Local development setup status:"
    echo ""
    echo "=========================================="
    echo "  LOCAL DEVELOPMENT SETUP STATUS"
    echo "=========================================="
    echo ""
    
    # Check .env.local
    if check_env_file; then
        echo "✓ .env.local file is configured"
    else
        echo "✗ .env.local file is missing"
    fi
    
    # Check service account
    if check_service_account; then
        echo "✓ Service account key is available"
    else
        echo "✗ Service account key is missing"
    fi
    
    # Check Cloud SQL Proxy
    if check_cloud_sql_proxy; then
        echo "✓ Cloud SQL Proxy is running"
    else
        echo "✗ Cloud SQL Proxy is not running"
    fi
    
    # Check Docker image
    if check_docker_image; then
        echo "✓ Docker image is built"
    else
        echo "✗ Docker image is not built"
    fi
    
    echo ""
}

# Display next steps
show_next_steps() {
    log "Next steps for local development:"
    echo ""
    echo "1. Update database credentials in .env.local:"
    echo "   - Set DB_PASSWORD to your actual database password"
    echo "   - Update other database settings if needed"
    echo ""
    echo "2. Start the application:"
    echo "   - Run with Docker: docker run -p 8080:8080 --env-file .env.local loist-mcp-server:local"
    echo "   - Or run locally: python src/server.py"
    echo ""
    echo "3. Test the application:"
    echo "   - Health check: curl http://localhost:8080/health"
    echo "   - MCP endpoints: curl http://localhost:8080/mcp/tools"
    echo ""
}

# Main execution
main() {
    log "Setting up local development environment..."
    echo ""
    
    # Create .env.local if it doesn't exist
    if ! check_env_file; then
        create_env_file
    fi
    
    # Show setup status
    show_setup_status
    
    # Show next steps
    show_next_steps
    
    success "Local development setup check completed!"
}

# Run main function
main "$@"
