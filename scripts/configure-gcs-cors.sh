#!/bin/bash
# Configure CORS for existing GCS bucket to allow browser access to waveform SVGs

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Configuration
BUCKET_NAME="${GCS_BUCKET_NAME:-loist-mvp-audio-files}"

log "Configuring CORS for GCS bucket: gs://${BUCKET_NAME}"

# Check if gsutil is installed
if ! command -v gsutil &> /dev/null; then
    error "gsutil is not installed. Please install Google Cloud SDK."
    exit 1
fi

# Check if bucket exists
if ! gsutil ls -b "gs://${BUCKET_NAME}" &> /dev/null; then
    error "Bucket 'gs://${BUCKET_NAME}' does not exist"
    exit 1
fi

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
      "Range",
      "Cache-Control",
      "Access-Control-Allow-Origin",
      "Access-Control-Allow-Methods",
      "Access-Control-Allow-Headers"
    ],
    "maxAgeSeconds": 3600
  }
]
EOF

log "CORS configuration:"
cat "$CORS_FILE"
echo ""

# Apply CORS configuration
log "Applying CORS configuration to bucket..."
if gsutil cors set "$CORS_FILE" "gs://${BUCKET_NAME}"; then
    success "CORS configuration applied successfully"
else
    error "Failed to apply CORS configuration"
    rm "$CORS_FILE"
    exit 1
fi

# Cleanup
rm "$CORS_FILE"

# Verify CORS configuration
log "Verifying CORS configuration..."
gsutil cors get "gs://${BUCKET_NAME}"

success "CORS configuration complete for gs://${BUCKET_NAME}"
success "Waveform SVGs should now be accessible from browser"
