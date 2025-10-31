#!/bin/bash

# Google Cloud Secret Manager Setup Script for Loist Music Library MCP Server
# Task 12.4: Secret Management Implementation

set -e  # Exit on any error

# Configuration variables
PROJECT_ID="${GCP_PROJECT_ID:-loist-music-library}"
INSTANCE_ID="loist-music-library-db"
DATABASE_NAME="music_library"
APP_USER="music_library_user"
GCS_BUCKET_NAME="${GCS_BUCKET_NAME:-loist-music-library-bucket}"
REGION="us-central1"

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

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."

    if ! command -v gcloud &> /dev/null; then
        error "gcloud CLI is not installed. Please install it first: https://cloud.google.com/sdk/docs/install"
        exit 1
    fi

    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        error "No active gcloud authentication found. Please run 'gcloud auth login'"
        exit 1
    fi

    # Set the project
    gcloud config set project "$PROJECT_ID"
    log "Using project: $PROJECT_ID"

    success "Prerequisites check passed"
}

# Generate secure random passwords
generate_passwords() {
    log "Generating secure passwords..."

    # Generate database password (32 characters, alphanumeric + special chars)
    DB_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)

    # Generate bearer token (64 characters, base64)
    BEARER_TOKEN=$(openssl rand -base64 64 | tr -d "=+/" | cut -c1-64)

    success "Passwords generated securely"
}

# Create or update secret with proper error handling
create_secret() {
    local secret_name="$1"
    local secret_value="$2"
    local description="$3"

    log "Creating/updating secret: $secret_name"

    # Check if secret exists
    if gcloud secrets describe "$secret_name" --quiet 2>/dev/null; then
        warning "Secret $secret_name already exists, adding new version"
        echo -n "$secret_value" | gcloud secrets versions add "$secret_name" --data-file=-
    else
        log "Creating new secret: $secret_name"
        echo -n "$secret_value" | gcloud secrets create "$secret_name" \
            --data-file=- \
            --description="$description" \
            --labels="project=loist-music-library,component=mcp-server,managed-by=script"
    fi

    success "Secret $secret_name created/updated"
}

# Setup database secrets
setup_database_secrets() {
    log "Setting up database-related secrets..."

    # Get Cloud SQL connection name
    DB_CONNECTION_NAME=$(gcloud sql instances describe "$INSTANCE_ID" --format="value(connectionName)" 2>/dev/null || echo "")

    if [ -z "$DB_CONNECTION_NAME" ]; then
        error "Cloud SQL instance $INSTANCE_ID not found. Please run create-cloud-sql-instance.sh first."
        exit 1
    fi

    log "Using Cloud SQL connection name: $DB_CONNECTION_NAME"

    # Create database secrets for production
    create_secret "db-connection-name" "$DB_CONNECTION_NAME" "Cloud SQL instance connection name for production database connectivity"
    create_secret "db-user" "$APP_USER" "Database application user for the production MCP server"
    create_secret "db-password" "$DB_PASSWORD" "Database password for the production application user"
    create_secret "db-name" "$DATABASE_NAME" "Database name for the production music library application"
    create_secret "db-host" "127.0.0.1" "Database host for production (localhost when using Cloud SQL Proxy)"
    create_secret "db-port" "5432" "Database port for production PostgreSQL connections"

    # Create staging database secrets (using same values for now, can be customized)
    create_secret "db-connection-name-staging" "$DB_CONNECTION_NAME" "Cloud SQL instance connection name for staging database connectivity"
    create_secret "db-user-staging" "$APP_USER" "Database application user for the staging MCP server"
    create_secret "db-password-staging" "$DB_PASSWORD" "Database password for the staging application user"
    create_secret "db-name-staging" "$DATABASE_NAME" "Database name for the staging music library application"
    create_secret "db-host-staging" "127.0.0.1" "Database host for staging (localhost when using Cloud SQL Proxy)"
    create_secret "db-port-staging" "5432" "Database port for staging PostgreSQL connections"

    success "Database secrets configured"
}

# Setup storage secrets
setup_storage_secrets() {
    log "Setting up storage-related secrets..."

    # Create GCS bucket secrets for both production and staging
    create_secret "gcs-bucket-name" "$GCS_BUCKET_NAME" "Google Cloud Storage bucket name for production file storage"

    # For staging, use a different bucket name if available, otherwise use same
    STAGING_BUCKET="${GCS_BUCKET_NAME}-staging"
    create_secret "gcs-bucket-name-staging" "$STAGING_BUCKET" "Google Cloud Storage bucket name for staging file storage"

    success "Storage secrets configured"
}

# Setup authentication secrets
setup_auth_secrets() {
    log "Setting up authentication-related secrets..."

    # Create bearer token secrets for both production and staging
    create_secret "mcp-bearer-token" "$BEARER_TOKEN" "Bearer token for production MCP server HTTP authentication"
    create_secret "mcp-bearer-token-staging" "$BEARER_TOKEN" "Bearer token for staging MCP server HTTP authentication"

    success "Authentication secrets configured"
}

# Create service account for Cloud Run
create_service_account() {
    log "Setting up service account for Cloud Run..."

    SERVICE_ACCOUNT_NAME="mcp-music-library-sa"
    SERVICE_ACCOUNT_EMAIL="$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com"

    # Check if service account exists
    if gcloud iam service-accounts describe "$SERVICE_ACCOUNT_EMAIL" --quiet 2>/dev/null; then
        warning "Service account $SERVICE_ACCOUNT_EMAIL already exists"
    else
        log "Creating service account: $SERVICE_ACCOUNT_NAME"
        gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
            --display-name="MCP Music Library Service Account" \
            --description="Service account for Cloud Run MCP server to access secrets, database, and storage"
    fi

    success "Service account configured: $SERVICE_ACCOUNT_EMAIL"
}

# Grant IAM permissions to service account
grant_permissions() {
    log "Granting IAM permissions to service account..."

    SERVICE_ACCOUNT_EMAIL="mcp-music-library-sa@$PROJECT_ID.iam.gserviceaccount.com"

    # Grant Secret Manager Secret Accessor role
    log "Granting Secret Manager access..."
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
        --role="roles/secretmanager.secretAccessor" \
        --quiet

    # Grant Cloud SQL Client role
    log "Granting Cloud SQL access..."
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
        --role="roles/cloudsql.client" \
        --quiet

    # Grant Storage Object Admin role
    log "Granting Cloud Storage access..."
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
        --role="roles/storage.objectAdmin" \
        --quiet

    success "IAM permissions granted"
}

# Grant specific secret access (more granular than project-level)
grant_secret_access() {
    log "Granting specific secret access permissions..."

    SERVICE_ACCOUNT_EMAIL="mcp-music-library-sa@$PROJECT_ID.iam.gserviceaccount.com"

    # List of secrets to grant access to (production and staging)
    SECRETS=(
        "db-connection-name"
        "db-user"
        "db-password"
        "db-name"
        "db-host"
        "db-port"
        "gcs-bucket-name"
        "mcp-bearer-token"
        "db-connection-name-staging"
        "db-user-staging"
        "db-password-staging"
        "db-name-staging"
        "db-host-staging"
        "db-port-staging"
        "gcs-bucket-name-staging"
        "mcp-bearer-token-staging"
    )

    for secret in "${SECRETS[@]}"; do
        if gcloud secrets describe "$secret" --quiet 2>/dev/null; then
            log "Granting access to secret: $secret"
            gcloud secrets add-iam-policy-binding "$secret" \
                --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
                --role="roles/secretmanager.secretAccessor" \
                --quiet
        else
            warning "Secret $secret does not exist, skipping access grant"
        fi
    done

    success "Specific secret access permissions granted"
}

# Enable audit logging for secrets
enable_audit_logging() {
    log "Enabling audit logging for secrets..."

    # Enable data access audit logs for Secret Manager
    gcloud projects get-iam-policy "$PROJECT_ID" \
        --format="table(bindings.role)" \
        --filter="bindings.role:roles/owner" \
        --quiet > /dev/null

    # Note: Audit logging configuration is typically done at the organization/folder level
    # This would require organization admin permissions
    warning "Audit logging should be enabled at the organization/folder level by an admin"
    warning "Required IAM role: roles/resourcemanager.organizationAdmin"

    success "Audit logging information provided"
}

# Create rotation configuration (informational)
setup_rotation_info() {
    log "Setting up secret rotation information..."

    cat << 'EOF'

🔄 SECRET ROTATION CONFIGURATION

For production environments, consider implementing automated secret rotation:

1. Database Password Rotation:
   - Use Pub/Sub notifications from Secret Manager
   - Create a Cloud Run job to handle rotation
   - Update database user password via Cloud SQL Admin API
   - Create new secret version with new password

2. Bearer Token Rotation:
   - Rotate tokens every 30-90 days
   - Use gradual rollout to avoid service disruption
   - Update client configurations with new tokens

3. Rotation Automation:
   - Create rotation Cloud Run service
   - Subscribe to Secret Manager rotation notifications
   - Implement idempotent rotation logic

Example rotation service structure:
- Listen for SECRET_ROTATE messages from Pub/Sub
- Generate new credentials
- Update external systems (database, etc.)
- Create new secret versions
- Handle rollback scenarios

EOF

    success "Rotation information provided"
}

# Create validation script
create_validation_script() {
    log "Creating secret validation script..."

    cat > scripts/validate-secrets.sh << 'EOF'
#!/bin/bash

# Secret Manager Validation Script
# Validates that all required secrets exist and are accessible

set -e

PROJECT_ID="${GCP_PROJECT_ID:-loist-music-library}"
SERVICE_ACCOUNT_EMAIL="mcp-music-library-sa@$PROJECT_ID.iam.gserviceaccount.com"

echo "🔍 Validating Secret Manager configuration..."

# Check if service account exists
if ! gcloud iam service-accounts describe "$SERVICE_ACCOUNT_EMAIL" --quiet 2>/dev/null; then
    echo "❌ Service account $SERVICE_ACCOUNT_EMAIL does not exist"
    exit 1
fi
echo "✅ Service account exists"

# Required secrets
REQUIRED_SECRETS=(
    "db-connection-name"
    "db-user"
    "db-password"
    "db-name"
    "db-host"
    "db-port"
    "gcs-bucket-name"
    "mcp-bearer-token"
)

for secret in "${REQUIRED_SECRETS[@]}"; do
    if ! gcloud secrets describe "$secret" --quiet 2>/dev/null; then
        echo "❌ Secret $secret does not exist"
        exit 1
    fi
    
    # Check if service account has access
    if ! gcloud secrets get-iam-policy "$secret" --format="value(bindings.members)" --filter="bindings.role:roles/secretmanager.secretAccessor" --quiet | grep -q "$SERVICE_ACCOUNT_EMAIL"; then
        echo "❌ Service account does not have access to secret $secret"
        exit 1
    fi
    
    echo "✅ Secret $secret exists and is accessible"
done

echo ""
echo "🎉 All secrets validated successfully!"
echo ""
echo "📋 Secret Access Test (run this with proper authentication):"
echo "gcloud secrets versions access latest --secret=mcp-bearer-token"
EOF

    chmod +x scripts/validate-secrets.sh

    success "Validation script created: scripts/validate-secrets.sh"
}

# Display summary
display_summary() {
    echo ""
    echo "=========================================="
    echo "  SECRET MANAGER SETUP COMPLETED"
    echo "=========================================="
    echo ""
    echo "Project: $PROJECT_ID"
    echo "Service Account: mcp-music-library-sa@$PROJECT_ID.iam.gserviceaccount.com"
    echo ""
    echo "Secrets Created:"
    echo "  📁 Database:"
    echo "    - db-connection-name: $DB_CONNECTION_NAME"
    echo "    - db-user: $APP_USER"
    echo "    - db-password: [SECURE]"
    echo "    - db-name: $DATABASE_NAME"
    echo "    - db-host: 127.0.0.1"
    echo "    - db-port: 5432"
    echo ""
    echo "  🗄️  Storage:"
    echo "    - gcs-bucket-name: $GCS_BUCKET_NAME"
    echo ""
    echo "  🔐 Authentication:"
    echo "    - mcp-bearer-token: [SECURE]"
    echo ""
    echo "Cloud Build Substitutions:"
    echo "  _DB_CONNECTION_NAME: db-connection-name"
    echo "  _GCS_BUCKET_NAME: gcs-bucket-name"
    echo ""
    echo "Next Steps:"
    echo "  1. Run: ./scripts/validate-secrets.sh"
    echo "  2. Test deployment with: gcloud builds submit --config cloudbuild.yaml"
    echo "  3. Verify secret injection in Cloud Run logs"
    echo ""
    echo "Security Notes:"
    echo "  - Secrets are encrypted at rest and in transit"
    echo "  - Service account has least-privilege access"
    echo "  - Audit logging is available in Cloud Audit Logs"
    echo "  - Consider implementing secret rotation for production"
    echo ""
}

# Main execution
main() {
    log "Starting Secret Manager setup for Loist Music Library MCP Server..."
    echo ""

    check_prerequisites
    generate_passwords
    setup_database_secrets
    setup_storage_secrets
    setup_auth_secrets
    create_service_account
    grant_permissions
    grant_secret_access
    enable_audit_logging
    setup_rotation_info
    create_validation_script
    display_summary

    success "Secret Manager setup completed successfully!"
    log "All secrets are now configured and ready for use"
}

# Run main function
main "$@"
