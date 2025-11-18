#!/bin/bash

# Domain Verification Setup Script for api.loist.io
# This script helps verify domain ownership in Google Cloud Console

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="loist-music-library"
DOMAIN="api.loist.io"
ROOT_DOMAIN="loist.io"

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

# Enable required APIs for domain verification
enable_apis() {
    log "Enabling required APIs for domain verification..."
    
    local apis=(
        "run.googleapis.com"
        "cloudresourcemanager.googleapis.com"
        "dns.googleapis.com"
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

# Generate domain verification instructions
generate_verification_instructions() {
    log "Generating domain verification instructions..."
    
    echo ""
    echo "=========================================="
    echo "  DOMAIN VERIFICATION FOR $DOMAIN"
    echo "=========================================="
    echo ""
    echo "Follow these steps to verify domain ownership:"
    echo ""
    echo "1. Go to Google Cloud Console:"
    echo "   https://console.cloud.google.com/security/domain-verification"
    echo ""
    echo "2. Click 'Add Domain' and enter: $ROOT_DOMAIN"
    echo ""
    echo "3. Choose verification method:"
    echo "   - DNS TXT record (recommended)"
    echo "   - HTML file upload"
    echo "   - Google Analytics"
    echo "   - Google Tag Manager"
    echo ""
    echo "4. If using DNS TXT record:"
    echo "   - Google will provide a TXT record to add"
    echo "   - Add it to your DNS provider for $ROOT_DOMAIN"
    echo "   - Wait for verification (can take up to 24 hours)"
    echo ""
    echo "5. Once verified, you can map subdomains like $DOMAIN"
    echo ""
    echo "Alternative: Use Google Search Console for verification:"
    echo "   https://search.google.com/search-console"
    echo ""
}

# Check current domain verification status
check_domain_status() {
    log "Checking current domain verification status..."
    
    # Try to list verified domains (this might not work with service account)
    if gcloud domains list 2>/dev/null; then
        success "Domain listing successful"
    else
        warning "Cannot list domains (may require user authentication)"
        log "Please check domain verification status manually in Google Cloud Console"
    fi
}

# Create Cloud Run deployment preparation
prepare_cloud_run_config() {
    log "Preparing Cloud Run configuration for $DOMAIN..."
    
    cat > cloudbuild.yaml << 'EOL'
# Cloud Build configuration for Cloud Run deployment
steps:
  # Build the container image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/loist-mcp-server:$COMMIT_SHA', '.']
  
  # Push the container image to Container Registry
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/loist-mcp-server:$COMMIT_SHA']
  
  # Deploy container image to Cloud Run
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'deploy'
      - 'loist-mcp-server'
      - '--image'
      - 'gcr.io/$PROJECT_ID/loist-mcp-server:$COMMIT_SHA'
      - '--region'
      - 'us-central1'
      - '--platform'
      - 'managed'
      - '--allow-unauthenticated'
      - '--memory'
      - '2Gi'
      - '--timeout'
      - '600s'
      - '--set-env-vars'
      - 'SERVER_TRANSPORT=http,ENABLE_CORS=true,CORS_ORIGINS=https://loist.io,https://api.loist.io'
      - '--set-secrets'
      - 'GCS_BUCKET_NAME=gcs-bucket-name:latest'
      - '--set-secrets'
      - 'DB_HOST=db-host:latest,DB_PASSWORD=db-password:latest,DB_NAME=db-name:latest,DB_USER=db-user:latest'

images:
  - 'gcr.io/$PROJECT_ID/loist-mcp-server:$COMMIT_SHA'
EOL

    success "Created cloudbuild.yaml for Cloud Run deployment"
}

# Display next steps
display_next_steps() {
    echo ""
    echo "=========================================="
    echo "  NEXT STEPS FOR DOMAIN SETUP"
    echo "=========================================="
    echo ""
    echo "1. ✅ Domain verification instructions generated"
    echo "2. ✅ Cloud Run deployment config created"
    echo ""
    echo "Next actions:"
    echo ""
    echo "📋 DOMAIN VERIFICATION:"
    echo "   - Go to: https://console.cloud.google.com/security/domain-verification"
    echo "   - Add domain: $ROOT_DOMAIN"
    echo "   - Complete verification using DNS TXT record"
    echo ""
    echo "🚀 CLOUD RUN DEPLOYMENT:"
    echo "   - Deploy service: gcloud builds submit --config cloudbuild.yaml"
    echo "   - Or use: gcloud run deploy --source . --platform managed --region us-central1"
    echo ""
    echo "🌐 DOMAIN MAPPING:"
    echo "   - After verification, map $DOMAIN to Cloud Run service"
    echo "   - Add CNAME record: $DOMAIN -> ghs.googlehosted.com"
    echo ""
    echo "📝 DNS RECORDS TO ADD (after Cloud Run deployment):"
    echo "   Type: CNAME"
    echo "   Name: api"
    echo "   Value: ghs.googlehosted.com"
    echo "   TTL: 3600 (or default)"
    echo ""
}

# Main execution
main() {
    log "Starting domain verification setup for $DOMAIN..."
    echo ""
    
    check_auth
    set_project
    enable_apis
    generate_verification_instructions
    check_domain_status
    prepare_cloud_run_config
    display_next_steps
    
    success "Domain verification setup completed!"
    echo ""
    log "Ready for domain verification and Cloud Run deployment"
}

# Run main function
main "$@"



