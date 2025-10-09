#!/bin/bash

# Google Cloud Storage Bucket Creation Script for MCP Music Library Server
# This script creates and configures a GCS bucket for audio file storage

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-loist-music-library}"
BUCKET_NAME="${GCS_BUCKET_NAME:-loist-music-library-audio}"
REGION="${GCS_REGION:-us-central1}"  # Same region as Cloud SQL
STORAGE_CLASS="${GCS_STORAGE_CLASS:-STANDARD}"  # For frequent access (streaming)
SERVICE_ACCOUNT_EMAIL="loist-music-library-sa@${PROJECT_ID}.iam.gserviceaccount.com"

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
    log "Checking if bucket '$BUCKET_NAME' already exists..."
    
    if gsutil ls -b "gs://${BUCKET_NAME}" &> /dev/null; then
        warning "Bucket 'gs://${BUCKET_NAME}' already exists"
        return 0
    fi
    
    log "Bucket does not exist, will create new bucket"
    return 1
}

# Create GCS bucket
create_bucket() {
    log "Creating GCS bucket: gs://${BUCKET_NAME}"
    log "  Region: $REGION"
    log "  Storage Class: $STORAGE_CLASS"
    
    # Create bucket with uniform bucket-level access
    gsutil mb \
        -p "$PROJECT_ID" \
        -c "$STORAGE_CLASS" \
        -l "$REGION" \
        -b on \
        "gs://${BUCKET_NAME}"
    
    success "Bucket created: gs://${BUCKET_NAME}"
}

# Configure bucket labels
configure_labels() {
    log "Configuring bucket labels..."
    
    gsutil label ch \
        -l "environment:production" \
        -l "app:loist-music-library" \
        -l "purpose:audio-storage" \
        -l "managed-by:script" \
        "gs://${BUCKET_NAME}"
    
    success "Bucket labels configured"
}

# Configure CORS for browser access
configure_cors() {
    log "Configuring CORS for browser access..."
    
    # Create temporary CORS configuration file
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
      "Range"
    ],
    "maxAgeSeconds": 3600
  }
]
EOF
    
    gsutil cors set "$CORS_FILE" "gs://${BUCKET_NAME}"
    rm "$CORS_FILE"
    
    success "CORS configuration applied"
}

# Configure lifecycle policies
configure_lifecycle() {
    log "Configuring lifecycle policies for temporary file cleanup..."
    
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
          "matchesPrefix": ["temp/", "uploads/temp/"]
        }
      },
      {
        "action": {
          "type": "Delete"
        },
        "condition": {
          "age": 7,
          "matchesPrefix": ["thumbnails/temp/"]
        }
      }
    ]
  }
}
EOF
    
    gsutil lifecycle set "$LIFECYCLE_FILE" "gs://${BUCKET_NAME}"
    rm "$LIFECYCLE_FILE"
    
    success "Lifecycle policies configured:"
    log "  - Delete temp/ and uploads/temp/ files after 1 day"
    log "  - Delete thumbnails/temp/ files after 7 days"
}

# Configure IAM permissions for service account
configure_iam_permissions() {
    log "Configuring IAM permissions for service account..."
    
    # Grant storage admin role to service account
    gsutil iam ch \
        "serviceAccount:${SERVICE_ACCOUNT_EMAIL}:roles/storage.objectAdmin" \
        "gs://${BUCKET_NAME}"
    
    success "IAM permissions granted to service account"
}

# Create bucket directory structure
create_directory_structure() {
    log "Creating bucket directory structure..."
    
    # Create placeholder files to establish directory structure
    echo "Audio files directory" | gsutil cp - "gs://${BUCKET_NAME}/audio/.placeholder"
    echo "Thumbnail images directory" | gsutil cp - "gs://${BUCKET_NAME}/thumbnails/.placeholder"
    echo "Temporary uploads directory" | gsutil cp - "gs://${BUCKET_NAME}/temp/.placeholder"
    
    success "Directory structure created:"
    log "  - audio/ - Permanent audio file storage"
    log "  - thumbnails/ - Album/track thumbnails"
    log "  - temp/ - Temporary uploads (deleted after 24 hours)"
}

# Verify bucket configuration
verify_bucket() {
    log "Verifying bucket configuration..."
    
    echo ""
    log "=== Bucket Information ==="
    gsutil ls -L -b "gs://${BUCKET_NAME}"
    
    echo ""
    success "Bucket verification complete!"
}

# Generate environment configuration
generate_env_config() {
    log "Generating environment configuration..."
    
    ENV_FILE=".env.gcs"
    
    cat > "$ENV_FILE" << EOF
# Google Cloud Storage Configuration
# Generated on $(date)

# Bucket Configuration
GCS_BUCKET_NAME=${BUCKET_NAME}
GCS_PROJECT_ID=${PROJECT_ID}
GCS_REGION=${REGION}
GCS_STORAGE_CLASS=${STORAGE_CLASS}

# Service Account
GCS_SERVICE_ACCOUNT_EMAIL=${SERVICE_ACCOUNT_EMAIL}

# Bucket Paths
GCS_AUDIO_PATH=audio
GCS_THUMBNAIL_PATH=thumbnails
GCS_TEMP_PATH=temp

# Signed URL Configuration
GCS_SIGNED_URL_EXPIRATION=900  # 15 minutes in seconds

# Full bucket URL
GCS_BUCKET_URL=gs://${BUCKET_NAME}
EOF
    
    success "Environment configuration saved to: $ENV_FILE"
    warning "Add $ENV_FILE to your .gitignore if not already present"
}

# Display cost estimation
display_cost_estimation() {
    log "=== Cost Estimation ==="
    echo ""
    log "Storage Costs (STANDARD class in us-central1):"
    log "  - Storage: \$0.020 per GB/month"
    log "  - Class A Operations (uploads): \$0.05 per 10,000 operations"
    log "  - Class B Operations (downloads): \$0.004 per 10,000 operations"
    log "  - Network Egress: \$0.12 per GB (first 1TB), then \$0.11 per GB"
    echo ""
    log "Example Monthly Costs:"
    log "  - 1,000 tracks (5GB): ~\$0.10/month + operations"
    log "  - 10,000 tracks (50GB): ~\$1.00/month + operations"
    log "  - 100,000 tracks (500GB): ~\$10.00/month + operations"
    echo ""
    warning "Actual costs depend on usage patterns (uploads/downloads)"
    log "Monitor costs at: https://console.cloud.google.com/billing"
}

# Main execution
main() {
    log "Starting GCS bucket creation for Loist Music Library..."
    echo ""
    
    # Pre-flight checks
    check_gcloud
    check_gsutil
    setup_gcloud_project
    
    # Check if bucket exists
    if check_bucket_exists; then
        warning "Bucket already exists. Skipping creation but will configure settings..."
    else
        # Create bucket
        create_bucket
    fi
    
    # Configure bucket
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
    success "=== GCS Bucket Setup Complete! ==="
    echo ""
    log "Next steps:"
    log "  1. Source the environment file: source .env.gcs"
    log "  2. Test bucket access with your application"
    log "  3. Implement signed URL generation in your code"
    log "  4. Set up monitoring and alerting"
    echo ""
    log "Bucket URL: gs://${BUCKET_NAME}"
    log "Console: https://console.cloud.google.com/storage/browser/${BUCKET_NAME}?project=${PROJECT_ID}"
}

# Run main function
main "$@"

