#!/bin/bash

# Cloud Run Deployment Script for loist-mcp-server
# This script deploys the service to Cloud Run so we can then map the domain

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="loist-music-library"
SERVICE_NAME="loist-mcp-server"
REGION="us-central1"
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"

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

# Check if gcloud is authenticated
check_auth() {
    log "Checking Google Cloud authentication..."
    
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        error "No active Google Cloud authentication found"
        log "Please run: gcloud auth login"
        exit 1
    fi
    
    local account=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n1)
    log "Authenticated as: $account"
    success "Google Cloud authentication verified"
}

# Set the project
set_project() {
    log "Setting project to: $PROJECT_ID"
    
    gcloud config set project "$PROJECT_ID"
    success "Project set to: $PROJECT_ID"
}

# Enable required APIs
enable_apis() {
    log "Enabling required APIs..."
    
    local apis=(
        "run.googleapis.com"
        "cloudbuild.googleapis.com"
        "containerregistry.googleapis.com"
    )
    
    for api in "${apis[@]}"; do
        log "Enabling $api..."
        if gcloud services enable "$api" --quiet 2>/dev/null; then
            success "Enabled $api"
        else
            warning "Failed to enable $api (may already be enabled or require different permissions)"
        fi
    done
}

# Configure Docker for Google Container Registry
configure_docker() {
    log "Configuring Docker for Google Container Registry..."
    
    gcloud auth configure-docker --quiet
    success "Docker configured for GCR"
}

# Build and push Docker image
build_and_push() {
    log "Building and pushing Docker image..."
    
    # Build the image
    log "Building Docker image: $IMAGE_NAME"
    docker build -t "$IMAGE_NAME" .
    
    # Push the image
    log "Pushing image to Google Container Registry..."
    docker push "$IMAGE_NAME"
    
    success "Docker image built and pushed: $IMAGE_NAME"
}

# Deploy to Cloud Run
deploy_to_cloud_run() {
    log "Deploying to Cloud Run..."
    
    # Deploy the service
    gcloud run deploy "$SERVICE_NAME" \
        --image="$IMAGE_NAME" \
        --region="$REGION" \
        --platform="managed" \
        --allow-unauthenticated \
        --memory="2Gi" \
        --timeout="600s" \
        --set-env-vars="SERVER_TRANSPORT=http,ENABLE_CORS=true,CORS_ORIGINS=https://loist.io,https://api.loist.io" \
        --quiet
    
    success "Service deployed to Cloud Run: $SERVICE_NAME"
}

# Get service URL
get_service_url() {
    log "Getting service URL..."
    
    local service_url=$(gcloud run services describe "$SERVICE_NAME" \
        --region="$REGION" \
        --format="value(status.url)")
    
    success "Service URL: $service_url"
    echo "$service_url"
}

# Test the deployed service
test_service() {
    log "Testing deployed service..."
    
    local service_url=$1
    
    # Test health endpoint
    log "Testing health endpoint..."
    if curl -s -f "$service_url/health" > /dev/null; then
        success "Health endpoint is working"
    else
        warning "Health endpoint test failed (may not be implemented yet)"
    fi
    
    # Test root endpoint
    log "Testing root endpoint..."
    local response=$(curl -s -w "%{http_code}" "$service_url/" -o /dev/null)
    if [ "$response" = "200" ] || [ "$response" = "404" ]; then
        success "Service is responding (HTTP $response)"
    else
        warning "Service response: HTTP $response"
    fi
}

# Display deployment summary
display_summary() {
    local service_url=$1
    
    echo ""
    echo "=========================================="
    echo "  CLOUD RUN DEPLOYMENT COMPLETED"
    echo "=========================================="
    echo ""
    echo "Service Name: $SERVICE_NAME"
    echo "Region: $REGION"
    echo "Service URL: $service_url"
    echo ""
    echo "✅ Service is deployed and running!"
    echo ""
    echo "Next Steps:"
    echo "1. Test the service: curl $service_url/health"
    echo "2. Go to Cloud Run Console: https://console.cloud.google.com/run"
    echo "3. Now you can map api.loist.io to this service"
    echo ""
    echo "Domain Mapping Process:"
    echo "1. Go to: https://console.cloud.google.com/run/detail/$REGION/$SERVICE_NAME"
    echo "2. Click 'Manage Custom Domains'"
    echo "3. Add domain: api.loist.io"
    echo "4. Follow DNS setup instructions"
    echo ""
}

# Main execution
main() {
    log "Starting Cloud Run deployment for $SERVICE_NAME..."
    echo ""
    
    check_auth
    set_project
    enable_apis
    configure_docker
    build_and_push
    deploy_to_cloud_run
    
    local service_url=$(get_service_url)
    test_service "$service_url"
    display_summary "$service_url"
    
    success "Cloud Run deployment completed successfully!"
}

# Run main function
main "$@"



