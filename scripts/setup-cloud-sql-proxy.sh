#!/bin/bash

# Cloud SQL Proxy Setup Script for Local Development
# This script sets up the Cloud SQL Proxy for connecting to a Cloud SQL instance locally

set -e  # Exit on any error

# Configuration variables
PROJECT_ID="loist-music-library"
INSTANCE_ID="loist-music-library-db"
CONNECTION_NAME="${PROJECT_ID}:us-central1:${INSTANCE_ID}"
SERVICE_ACCOUNT_KEY="/Users/Gareth/loist-mcp-server/service-account-key.json"
PROXY_PORT="5432"
CONTAINER_NAME="cloud-sql-proxy-local"

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

# Check if Docker is running
check_docker() {
    log "Checking Docker status..."
    
    if ! docker info >/dev/null 2>&1; then
        error "Docker is not running. Please start Docker Desktop and try again."
        exit 1
    fi
    
    success "Docker is running"
}

# Check if service account key exists
check_service_account() {
    log "Checking service account key..."
    
    if [ ! -f "$SERVICE_ACCOUNT_KEY" ]; then
        error "Service account key not found at: $SERVICE_ACCOUNT_KEY"
        exit 1
    fi
    
    success "Service account key found"
}

# Stop existing proxy container if running
stop_existing_proxy() {
    log "Checking for existing Cloud SQL Proxy container..."
    
    if docker ps -q -f name="$CONTAINER_NAME" | grep -q .; then
        warning "Stopping existing Cloud SQL Proxy container..."
        docker stop "$CONTAINER_NAME" || true
        docker rm "$CONTAINER_NAME" || true
        success "Existing container stopped and removed"
    else
        log "No existing Cloud SQL Proxy container found"
    fi
}

# Start Cloud SQL Proxy container
start_cloud_sql_proxy() {
    log "Starting Cloud SQL Proxy container..."
    
    docker run -d \
        --name "$CONTAINER_NAME" \
        -v "$SERVICE_ACCOUNT_KEY:/config/key.json" \
        -p "127.0.0.1:$PROXY_PORT:5432" \
        gcr.io/cloud-sql-connectors/cloud-sql-proxy:latest \
        --address 0.0.0.0 \
        --port 5432 \
        --credentials-file /config/key.json \
        "$CONNECTION_NAME"
    
    success "Cloud SQL Proxy container started"
}

# Wait for proxy to be ready
wait_for_proxy() {
    log "Waiting for Cloud SQL Proxy to be ready..."
    
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if docker logs "$CONTAINER_NAME" 2>&1 | grep -q "Ready for new connections"; then
            success "Cloud SQL Proxy is ready"
            return 0
        fi
        
        echo -n "."
        sleep 2
        ((attempt++))
    done
    
    error "Cloud SQL Proxy failed to start within expected time"
    docker logs "$CONTAINER_NAME"
    exit 1
}

# Display connection information
show_connection_info() {
    log "Cloud SQL Proxy setup complete!"
    
    echo ""
    echo "=========================================="
    echo "  CLOUD SQL PROXY SETUP COMPLETE"
    echo "=========================================="
    echo ""
    echo "Connection Details:"
    echo "  Instance: $INSTANCE_ID"
    echo "  Connection Name: $CONNECTION_NAME"
    echo "  Local Port: $PROXY_PORT"
    echo "  Container: $CONTAINER_NAME"
    echo ""
    echo "Connection String:"
    echo "  postgresql://username:password@localhost:$PROXY_PORT/database_name"
    echo ""
    echo "Docker Commands:"
    echo "  View logs: docker logs $CONTAINER_NAME"
    echo "  Stop proxy: docker stop $CONTAINER_NAME"
    echo "  Remove proxy: docker rm $CONTAINER_NAME"
    echo ""
    echo "Note: You'll need to provide database credentials when connecting."
    echo "The proxy only handles the secure connection to Cloud SQL."
    echo ""
}

# Main execution
main() {
    log "Setting up Cloud SQL Proxy for local development..."
    log "Project: $PROJECT_ID"
    log "Instance: $INSTANCE_ID"
    log "Connection: $CONNECTION_NAME"
    echo ""
    
    check_docker
    check_service_account
    stop_existing_proxy
    start_cloud_sql_proxy
    wait_for_proxy
    show_connection_info
    
    success "Cloud SQL Proxy setup completed successfully!"
}

# Run main function
main "$@"

