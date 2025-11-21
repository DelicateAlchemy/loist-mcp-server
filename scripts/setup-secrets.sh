#!/bin/bash

# Secret Management Setup Script for Loist MCP Server
# This script creates and manages all secrets required for the Cloud Run deployment

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-loist-music-library}"
SERVICE_ACCOUNT_EMAIL="loist-music-library-sa@${PROJECT_ID}.iam.gserviceaccount.com"
CLOUD_SQL_INSTANCE="loist-music-library-db"
DATABASE_NAME="music_library"
DATABASE_USER="music_library_user"
GCS_BUCKET="loist-music-library-audio"

# Logging functions
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

# Enable Secret Manager API
enable_secret_manager() {
    log "Enabling Secret Manager API..."
    gcloud services enable secretmanager.googleapis.com --quiet
    success "Secret Manager API enabled"
}

# Create or update database secrets
create_database_secrets() {
    log "Creating database secrets..."
    
    # Get Cloud SQL instance connection name
    local connection_name=$(gcloud sql instances describe "$CLOUD_SQL_INSTANCE" --format="value(connectionName)" 2>/dev/null || echo "")
    
    if [ -z "$connection_name" ]; then
        error "Cloud SQL instance $CLOUD_SQL_INSTANCE not found"
        log "Please create the Cloud SQL instance first"
        exit 1
    fi
    
    # Generate secure passwords if they don't exist
    local db_password=$(openssl rand -base64 32)
    local bearer_token=$(openssl rand -base64 32)
    
    # Create or update secrets
    echo -n "$connection_name" | gcloud secrets create db-host --data-file=- --quiet 2>/dev/null || \
        echo -n "$connection_name" | gcloud secrets versions add db-host --data-file=-
    
    echo -n "$DATABASE_NAME" | gcloud secrets create db-name --data-file=- --quiet 2>/dev/null || \
        echo -n "$DATABASE_NAME" | gcloud secrets versions add db-name --data-file=-
    
    echo -n "$DATABASE_USER" | gcloud secrets create db-user --data-file=- --quiet 2>/dev/null || \
        echo -n "$DATABASE_USER" | gcloud secrets versions add db-user --data-file=-
    
    echo -n "$db_password" | gcloud secrets create db-password --data-file=- --quiet 2>/dev/null || \
        echo -n "$db_password" | gcloud secrets versions add db-password --data-file=-
    
    echo -n "$GCS_BUCKET" | gcloud secrets create gcs-bucket-name --data-file=- --quiet 2>/dev/null || \
        echo -n "$GCS_BUCKET" | gcloud secrets versions add gcs-bucket-name --data-file=-
    
    echo -n "$bearer_token" | gcloud secrets create mcp-bearer-token --data-file=- --quiet 2>/dev/null || \
        echo -n "$bearer_token" | gcloud secrets versions add mcp-bearer-token --data-file=-
    
    success "Database secrets created/updated"
    log "Database connection: $connection_name"
    log "Database name: $DATABASE_NAME"
    log "Database user: $DATABASE_USER"
    log "GCS bucket: $GCS_BUCKET"
    warning "Database password and bearer token have been generated and stored securely"
}

# Configure IAM permissions for secrets
configure_secret_permissions() {
    log "Configuring IAM permissions for secrets..."
    
    # List of secrets to grant access to
    local secrets=(
        "db-host"
        "db-name" 
        "db-user"
        "db-password"
        "gcs-bucket-name"
        "mcp-bearer-token"
    )
    
    # Grant Secret Manager Secret Accessor role to service account
    for secret in "${secrets[@]}"; do
        log "Granting access to secret: $secret"
        gcloud secrets add-iam-policy-binding "$secret" \
            --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
            --role="roles/secretmanager.secretAccessor" \
            --quiet
    done
    
    success "IAM permissions configured for all secrets"
}

# Verify secrets are accessible
verify_secrets() {
    log "Verifying secret access..."
    
    local secrets=(
        "db-host"
        "db-name"
        "db-user" 
        "db-password"
        "gcs-bucket-name"
        "mcp-bearer-token"
    )
    
    for secret in "${secrets[@]}"; do
        if gcloud secrets versions access latest --secret="$secret" >/dev/null 2>&1; then
            success "Secret $secret is accessible"
        else
            error "Secret $secret is not accessible"
            return 1
        fi
    done
    
    success "All secrets are accessible"
}

# Display secret management summary
display_summary() {
    echo ""
    echo "=========================================="
    echo "  SECRET MANAGEMENT SETUP COMPLETED"
    echo "=========================================="
    echo ""
    echo "Project: $PROJECT_ID"
    echo "Service Account: $SERVICE_ACCOUNT_EMAIL"
    echo ""
    echo "Secrets Created/Updated:"
    echo "  - db-host: Cloud SQL connection name"
    echo "  - db-name: Database name ($DATABASE_NAME)"
    echo "  - db-user: Database user ($DATABASE_USER)"
    echo "  - db-password: Generated secure password"
    echo "  - gcs-bucket-name: GCS bucket name ($GCS_BUCKET)"
    echo "  - mcp-bearer-token: Generated secure token"
    echo ""
    echo "IAM Permissions:"
    echo "  - Service account has Secret Manager Secret Accessor role"
    echo "  - Access granted to all required secrets"
    echo ""
    echo "Next Steps:"
    echo "  1. Update your Cloud Run deployment to use these secrets"
    echo "  2. Test the deployment with secret injection"
    echo "  3. Verify all services can access their required secrets"
    echo ""
    echo "To view a secret value:"
    echo "  gcloud secrets versions access latest --secret=SECRET_NAME"
    echo ""
    echo "To update a secret:"
    echo "  echo -n 'new_value' | gcloud secrets versions add SECRET_NAME --data-file=-"
    echo ""
}

# Main execution
main() {
    log "Starting secret management setup for Loist MCP Server..."
    echo ""
    
    check_auth
    set_project
    enable_secret_manager
    create_database_secrets
    configure_secret_permissions
    verify_secrets
    display_summary
    
    success "Secret management setup completed successfully!"
}

# Run main function
main "$@"
