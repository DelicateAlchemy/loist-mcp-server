#!/bin/bash

# Google Cloud Storage Bucket Creation Script for Staging Environment
# Creates and configures a GCS bucket specifically for the staging environment

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration for staging environment
PROJECT_ID="${GCP_PROJECT_ID:-loist-music-library}"
BUCKET_NAME="${GCS_BUCKET_NAME:-loist-music-library-staging-audio}"
REGION="${GCS_REGION:-us-central1}"
STORAGE_CLASS="${GCS_STORAGE_CLASS:-STANDARD}"
SERVICE_ACCOUNT_EMAIL="mcp-music-library-sa@${PROJECT_ID}.iam.gserviceaccount.com"

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

# Check if gcloud is installed
check_gcloud() {
    log "Checking if gcloud CLI is installed..."

    if ! command -v gcloud &> /dev/null; then
        error "gcloud CLI is not installed. Please install it first:"
        echo "  curl https://sdk.cloud.google.com | bash"
        exit 1
    fi

    success "gcloud CLI is installed"
}

# Check if gsutil is available
check_gsutil() {
    log "Checking if gsutil is available..."

    if ! command -v gsutil &> /dev/null; then
        error "gsutil is not available. It should come with gcloud SDK."
        exit 1
    fi

    success "gsutil is available"
}

# Authenticate and set project
setup_gcloud_project() {
    log "Setting up Google Cloud project..."

    # Get current project
    CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")

    if [ "$CURRENT_PROJECT" != "$PROJECT_ID" ]; then
        log "Setting project to: $PROJECT_ID"
        gcloud config set project "$PROJECT_ID"
    fi

    success "Project set to: $PROJECT_ID"
}

# Check if bucket already exists
check_bucket_exists() {
    log "Checking if staging bucket '$BUCKET_NAME' already exists..."

    if gsutil ls -b "gs://${BUCKET_NAME}" &> /dev/null; then
        warning "Bucket 'gs://${BUCKET_NAME}' already exists"
        return 0
    fi

    log "Bucket does not exist, will create new staging bucket"
    return 1
}

# Create GCS bucket for staging
create_bucket() {
    log "Creating GCS staging bucket: gs://${BUCKET_NAME}"
    log "  Region: $REGION"
    log "  Storage Class: $STORAGE_CLASS"

    # Create bucket with uniform bucket-level access
    gsutil mb \
        -p "$PROJECT_ID" \
        -c "$STORAGE_CLASS" \
        -l "$REGION" \
        -b on \
        "gs://${BUCKET_NAME}"

    success "Staging bucket created: gs://${BUCKET_NAME}"
}

# Configure bucket labels for staging
configure_labels() {
    log "Configuring staging bucket labels..."

    gsutil label ch \
        -l "environment:staging" \
        -l "app:loist-music-library" \
        -l "purpose:staging-audio-storage" \
        -l "managed-by:script" \
        -l "auto-cleanup:true" \
        "gs://${BUCKET_NAME}"

    success "Staging bucket labels configured"
}

# Configure CORS for browser access (staging allows more permissive access)
configure_cors() {
    log "Configuring CORS for staging browser access..."

    # Create temporary CORS configuration file - more permissive for staging
    CORS_FILE=$(mktemp)
    cat > "$CORS_FILE" << 'EOF'
[
  {
    "origin": ["*"],
    "method": ["GET", "HEAD", "OPTIONS"],
    "responseHeader": [
      "Content-Type",
      "Content-Length",
      "Content-Range",
      "Accept-Ranges",
      "Cache-Control"
    ],
    "maxAgeSeconds": 3600
  }
]
EOF

    gsutil cors set "$CORS_FILE" "gs://${BUCKET_NAME}"
    rm "$CORS_FILE"

    success "Staging CORS configuration applied"
}

# Configure lifecycle policies for staging (more aggressive cleanup)
configure_lifecycle() {
    log "Configuring lifecycle policies for staging data management..."

    # Create temporary lifecycle configuration file
    LIFECYCLE_FILE=$(mktemp)
    cat > "$LIFECYCLE_FILE" << 'EOF'
{
  "lifecycle": {
    "rule": [
      {
        "action": {
          "type": "Delete"
        },
        "condition": {
          "age": 1,
          "matchesPrefix": ["temp/", "uploads/temp/", "test/"]
        }
      },
      {
        "action": {
          "type": "Delete"
        },
        "condition": {
          "age": 7,
          "matchesPrefix": ["thumbnails/temp/", "staging/"]
        }
      },
      {
        "action": {
          "type": "SetStorageClass",
          "storageClass": "NEARLINE"
        },
        "condition": {
          "age": 30,
          "matchesStorageClass": ["STANDARD"]
        }
      }
    ]
  }
}
EOF

    gsutil lifecycle set "$LIFECYCLE_FILE" "gs://${BUCKET_NAME}"
    rm "$LIFECYCLE_FILE"

    success "Staging lifecycle policies configured:"
    log "  - Delete temp/test files after 1 day"
    log "  - Delete staging content after 7 days"
    log "  - Move older files to NEARLINE after 30 days"
}

# Configure IAM permissions for staging service account
configure_iam_permissions() {
    log "Configuring IAM permissions for staging service account..."

    # Grant storage admin role to service account
    gsutil iam ch \
        "serviceAccount:${SERVICE_ACCOUNT_EMAIL}:roles/storage.objectAdmin" \
        "gs://${BUCKET_NAME}"

    success "IAM permissions granted to staging service account"
}

# Create bucket directory structure for staging
create_directory_structure() {
    log "Creating staging bucket directory structure..."

    # Create placeholder files to establish directory structure
    echo "Staging audio files directory" | gsutil cp - "gs://${BUCKET_NAME}/audio/.placeholder"
    echo "Staging thumbnail images directory" | gsutil cp - "gs://${BUCKET_NAME}/thumbnails/.placeholder"
    echo "Staging temporary uploads directory" | gsutil cp - "gs://${BUCKET_NAME}/temp/.placeholder"
    echo "Staging test data directory" | gsutil cp - "gs://${BUCKET_NAME}/test/.placeholder"
    echo "Staging-specific content directory" | gsutil cp - "gs://${BUCKET_NAME}/staging/.placeholder"

    success "Staging directory structure created:"
    log "  - audio/ - Permanent staging audio file storage"
    log "  - thumbnails/ - Staging album/track thumbnails"
    log "  - temp/ - Temporary staging uploads (deleted after 24 hours)"
    log "  - test/ - Test data and validation files (deleted after 24 hours)"
    log "  - staging/ - Staging-specific content (deleted after 7 days)"
}

# Verify bucket configuration
verify_bucket() {
    log "Verifying staging bucket configuration..."

    echo ""
    log "=== Staging Bucket Information ==="
    gsutil ls -L -b "gs://${BUCKET_NAME}"

    echo ""
    success "Staging bucket verification complete!"
}

# Generate staging environment configuration
generate_env_config() {
    log "Generating staging environment configuration..."

    ENV_FILE=".env.gcs-staging"

    cat > "$ENV_FILE" << EOF
# Google Cloud Storage Configuration - STAGING ENVIRONMENT
# Generated on $(date)

# Bucket Configuration
GCS_BUCKET_NAME=${BUCKET_NAME}
GCS_PROJECT_ID=${PROJECT_ID}
GCS_REGION=${REGION}
GCS_STORAGE_CLASS=${STORAGE_CLASS}
GCS_ENVIRONMENT=staging

# Service Account
GCS_SERVICE_ACCOUNT_EMAIL=${SERVICE_ACCOUNT_EMAIL}

# Bucket Paths
GCS_AUDIO_PATH=audio
GCS_THUMBNAIL_PATH=thumbnails
GCS_TEMP_PATH=temp
GCS_TEST_PATH=test
GCS_STAGING_PATH=staging

# Signed URL Configuration
GCS_SIGNED_URL_EXPIRATION=900  # 15 minutes in seconds

# Full bucket URL
GCS_BUCKET_URL=gs://${BUCKET_NAME}

# Staging-specific settings
GCS_AUTO_CLEANUP=true
GCS_RETENTION_DAYS_TEMP=1
GCS_RETENTION_DAYS_STAGING=7
EOF

    success "Staging environment configuration saved to: $ENV_FILE"
    warning "Add $ENV_FILE to your .gitignore if not already present"
}

# Display cost estimation for staging
display_cost_estimation() {
    log "=== Staging Environment Cost Estimation ==="
    echo ""
    log "Storage Costs (STANDARD class in us-central1):"
    log "  - Storage: \$0.020 per GB/month"
    log "  - Class A Operations (uploads): \$0.05 per 10,000 operations"
    log "  - Class B Operations (downloads): \$0.004 per 10,000 operations"
    log "  - Network Egress: \$0.12 per GB (first 1TB), then \$0.11 per GB"
    echo ""
    log "Staging Environment Considerations:"
    log "  - Aggressive cleanup policies reduce storage costs"
    log "  - Test data is automatically deleted"
    log "  - Lower usage expected than production"
    echo ""
    log "Example Monthly Staging Costs:"
    log "  - 100 tracks (5GB test data): ~\$0.10/month + operations"
    log "  - With auto-cleanup: Costs further reduced by temporary data deletion"
    echo ""
    warning "Monitor staging costs at: https://console.cloud.google.com/billing"
}

# Main execution
main() {
    log "Starting GCS staging bucket creation for Loist Music Library..."
    echo ""

    # Pre-flight checks
    check_gcloud
    check_gsutil
    setup_gcloud_project

    # Check if bucket exists
    if check_bucket_exists; then
        warning "Staging bucket already exists. Skipping creation but will configure settings..."
    else
        # Create bucket
        create_bucket
    fi

    # Configure staging bucket
    configure_labels
    configure_cors
    configure_lifecycle
    configure_iam_permissions
    create_directory_structure

    # Verification
    verify_bucket

    # Post-creation tasks
    generate_env_config
    display_cost_estimation

    echo ""
    success "=== STAGING GCS BUCKET SETUP COMPLETE! ==="
    echo ""
    log "Next steps:"
    log "  1. Source the environment file: source .env.gcs-staging"
    log "  2. Test staging bucket access with your application"
    log "  3. Verify auto-cleanup policies work as expected"
    log "  4. Monitor costs and adjust lifecycle policies if needed"
    echo ""
    log "Staging Bucket URL: gs://${BUCKET_NAME}"
    log "Console: https://console.cloud.google.com/storage/browser/${BUCKET_NAME}?project=${PROJECT_ID}"
}

# Run main function
main "$@"
