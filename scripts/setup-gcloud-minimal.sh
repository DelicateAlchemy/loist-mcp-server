#!/bin/bash

# Google Cloud Setup Script for MCP Music Library Server (Minimal - No Secret Manager)
# This script sets up the necessary Google Cloud services without Secret Manager

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-loist-music-library}"
SERVICE_ACCOUNT_NAME="loist-music-library-sa"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
ROLES=(
    "roles/cloudsql.admin"
    "roles/storage.admin"
    "roles/monitoring.metricWriter"
    "roles/logging.logWriter"
)

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

# Check if gcloud is installed
check_gcloud() {
    log "Checking if gcloud CLI is installed..."
    
    if ! command -v gcloud &> /dev/null; then
        error "gcloud CLI is not installed. Please install it first:"
        echo "  curl https://sdk.cloud.google.com | bash"
        echo "  exec -l $SHELL"
        echo "  gcloud init"
        exit 1
    fi
    
    success "gcloud CLI is installed"
}

# Authenticate with Google Cloud
authenticate() {
    log "Authenticating with Google Cloud..."
    
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        log "No active authentication found. Starting authentication..."
        gcloud auth login
    else
        log "Already authenticated with Google Cloud"
    fi
    
    success "Authentication completed"
}

# Set the project
set_project() {
    log "Setting project to: $PROJECT_ID"
    
    gcloud config set project "$PROJECT_ID"
    
    # Verify project exists
    if ! gcloud projects describe "$PROJECT_ID" &> /dev/null; then
        error "Project $PROJECT_ID does not exist or you don't have access to it"
        log "Available projects:"
        gcloud projects list --format="table(projectId,name)"
        exit 1
    fi
    
    success "Project set to: $PROJECT_ID"
}

# Enable required APIs (without Secret Manager)
enable_apis() {
    log "Enabling required Google Cloud APIs..."
    
    local apis=(
        "sqladmin.googleapis.com"
        "storage.googleapis.com"
        "monitoring.googleapis.com"
        "logging.googleapis.com"
        "cloudresourcemanager.googleapis.com"
    )
    
    for api in "${apis[@]}"; do
        log "Enabling $api..."
        gcloud services enable "$api" --quiet
    done
    
    success "All required APIs enabled"
}

# Create service account
create_service_account() {
    log "Creating service account: $SERVICE_ACCOUNT_NAME"
    
    if gcloud iam service-accounts describe "$SERVICE_ACCOUNT_EMAIL" &> /dev/null; then
        warning "Service account $SERVICE_ACCOUNT_EMAIL already exists"
    else
        gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
            --display-name="Loist Music Library Service Account" \
            --description="Service account for MCP Music Library Server" \
            --quiet
        
        success "Service account created: $SERVICE_ACCOUNT_EMAIL"
    fi
}

# Assign roles to service account
assign_roles() {
    log "Assigning roles to service account..."
    
    for role in "${ROLES[@]}"; do
        log "Assigning role: $role"
        gcloud projects add-iam-policy-binding "$PROJECT_ID" \
            --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
            --role="$role" \
            --quiet
    done
    
    success "All roles assigned to service account"
}

# Create service account key
create_service_account_key() {
    log "Creating service account key..."
    
    local key_file="service-account-key.json"
    
    if [ -f "$key_file" ]; then
        warning "Service account key file already exists: $key_file"
        read -p "Do you want to overwrite it? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log "Skipping service account key creation"
            return
        fi
    fi
    
    gcloud iam service-accounts keys create "$key_file" \
        --iam-account="$SERVICE_ACCOUNT_EMAIL" \
        --quiet
    
    success "Service account key created: $key_file"
    warning "Keep this file secure and add it to .gitignore"
}

# Display setup summary
display_summary() {
    echo ""
    echo "=========================================="
    echo "  GOOGLE CLOUD SETUP COMPLETED (MINIMAL)"
    echo "=========================================="
    echo ""
    echo "Project: $PROJECT_ID"
    echo "Service Account: $SERVICE_ACCOUNT_EMAIL"
    echo "Key File: service-account-key.json"
    echo ""
    echo "Note: Secret Manager was skipped (billing required)"
    echo "Passwords will be stored in .env.database file"
    echo ""
    echo "Next Steps:"
    echo "  1. Add service-account-key.json to .gitignore"
    echo "  2. Set GCP_PROJECT_ID environment variable"
    echo "  3. Run the Cloud SQL instance creation script"
    echo "  4. Configure your application with the database credentials"
    echo ""
    echo "Environment Variables to Set:"
    echo "  export GCP_PROJECT_ID=$PROJECT_ID"
    echo "  export GOOGLE_APPLICATION_CREDENTIALS=./service-account-key.json"
    echo ""
}

# Main execution
main() {
    log "Starting Google Cloud setup for MCP Music Library Server (Minimal)..."
    echo ""
    
    check_gcloud
    authenticate
    set_project
    enable_apis
    create_service_account
    assign_roles
    create_service_account_key
    display_summary
    
    success "Google Cloud setup completed successfully!"
}

# Run main function
main "$@"
