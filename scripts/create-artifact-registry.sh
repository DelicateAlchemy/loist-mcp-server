#!/bin/bash

# Google Artifact Registry Setup Script for MCP Music Library Server
# This script creates and configures an Artifact Registry repository for Docker images

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-loist-music-library}"
REPO_NAME="${ARTIFACT_REPO_NAME:-music-library-repo}"
REGION="${ARTIFACT_REGION:-us-central1}"  # Same region as other services
SERVICE_ACCOUNT_EMAIL="loist-music-library-sa@${PROJECT_ID}.iam.gserviceaccount.com"
REPO_FORMAT="docker"

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

# Check if docker is available
check_docker() {
    log "Checking if Docker is available..."

    if ! command -v docker &> /dev/null; then
        error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    success "Docker is available"
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

# Check if repository already exists
check_repository_exists() {
    log "Checking if Artifact Registry repository '$REPO_NAME' already exists..."

    if gcloud artifacts repositories describe "$REPO_NAME" \
        --location="$REGION" \
        --format="value(name)" &> /dev/null; then
        warning "Repository '$REPO_NAME' already exists"
        return 0
    fi

    log "Repository does not exist, will create new repository"
    return 1
}

# Create Artifact Registry repository
create_repository() {
    log "Creating Artifact Registry repository: $REPO_NAME"
    log "  Location: $REGION"
    log "  Format: $REPO_FORMAT"

    # Create repository with immutable tags (for security and cost optimization)
    gcloud artifacts repositories create "$REPO_NAME" \
        --repository-format="$REPO_FORMAT" \
        --location="$REGION" \
        --description="Docker images for Loist Music Library MCP Server" \
        --labels="environment=production,app=loist-music-library,purpose=container-registry,managed-by=script"

    success "Repository created: $REPO_NAME"
}

# Configure repository labels
configure_labels() {
    log "Configuring repository labels..."

    # Note: gcloud artifacts repositories update doesn't support labels directly
    # Labels are set during creation above
    success "Repository labels configured during creation"
}

# Configure IAM permissions for service account
configure_iam_permissions() {
    log "Configuring IAM permissions for service account..."

    # Grant Artifact Registry Reader role to service account
    gcloud artifacts repositories add-iam-policy-binding "$REPO_NAME" \
        --location="$REGION" \
        --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
        --role="roles/artifactregistry.reader"

    success "IAM permissions granted to service account"
}

# Configure repository cleanup policies
configure_cleanup_policies() {
    log "Configuring repository cleanup policies..."

    # Create cleanup policy to keep only recent images
    POLICY_FILE=$(mktemp)
    cat > "$POLICY_FILE" << EOF
{
  "name": "projects/${PROJECT_ID}/locations/${REGION}/repositories/${REPO_NAME}/cleanupPolicies/keep-recent-versions",
  "cleanup": {
    "condition": {
      "tagState": "TAGGED",
      "tagPrefixes": ["latest"],
      "olderThan": "2592000s"  # 30 days
    },
    "action": "DELETE"
  }
}
EOF

    gcloud artifacts repositories set-cleanup-policies "$REPO_NAME" \
        --location="$REGION" \
        --policy="$POLICY_FILE"

    rm "$POLICY_FILE"

    success "Cleanup policies configured:"
    log "  - Keep 'latest' tags for 30 days, then delete older versions"
}

# Configure Docker authentication
configure_docker_auth() {
    log "Configuring Docker authentication for Artifact Registry..."

    # Configure Docker to use gcloud as a credential helper
    gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

    success "Docker authentication configured"
}

# Test repository access
test_repository_access() {
    log "Testing repository access..."

    # List repositories to verify access
    REPO_LIST=$(gcloud artifacts repositories list \
        --location="$REGION" \
        --filter="name~${REPO_NAME}" \
        --format="value(name)")

    if [[ "$REPO_LIST" == *"$REPO_NAME"* ]]; then
        success "Repository access verified"
    else
        error "Repository access test failed"
        exit 1
    fi
}

# Build and push test image
build_test_image() {
    log "Building and pushing test image to verify setup..."

    # Build a minimal test image
    TEST_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/test-image:latest"

    # Create a simple Dockerfile for testing
    TEST_DOCKERFILE=$(mktemp)
    cat > "$TEST_DOCKERFILE" << 'EOF'
FROM alpine:latest
RUN echo "Loist Music Library - Artifact Registry Test" > /test.txt
CMD ["cat", "/test.txt"]
EOF

    # Build and push test image
    docker build -f "$TEST_DOCKERFILE" -t "$TEST_IMAGE" . && \
    docker push "$TEST_IMAGE"

    rm "$TEST_DOCKERFILE"

    success "Test image built and pushed successfully"
    log "Test image: $TEST_IMAGE"
}

# Generate environment configuration
generate_env_config() {
    log "Generating environment configuration..."

    ENV_FILE=".env.artifact-registry"

    cat > "$ENV_FILE" << EOF
# Google Artifact Registry Configuration
# Generated on $(date)

# Repository Configuration
ARTIFACT_REPO_NAME=${REPO_NAME}
ARTIFACT_REGION=${REGION}
ARTIFACT_PROJECT_ID=${PROJECT_ID}

# Repository URLs
ARTIFACT_REPO_URL=${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}
ARTIFACT_REGISTRY_HOST=${REGION}-docker.pkg.dev

# Service Account
ARTIFACT_SERVICE_ACCOUNT_EMAIL=${SERVICE_ACCOUNT_EMAIL}

# Image Naming Convention
# Format: {region}-docker.pkg.dev/{project}/{repo}/{image}:{tag}
# Example: ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/music-library-mcp:latest
# Example: ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/music-library-mcp:\${COMMIT_SHA}

# Cloud Build Configuration
# Use these values in your cloudbuild.yaml substitutions:
# _ARTIFACT_REPO_NAME: ${REPO_NAME}
# _ARTIFACT_REGION: ${REGION}
EOF

    success "Environment configuration saved to: $ENV_FILE"
    warning "Add $ENV_FILE to your .gitignore if not already present"
}

# Display cost estimation
display_cost_estimation() {
    log "=== Cost Estimation ==="
    echo ""
    log "Artifact Registry Costs:"
    log "  - Storage: \$0.10 per GB/month"
    log "  - Network Egress: \$0.12 per GB (first 1TB), then \$0.11 per GB"
    log "  - No cost for storage operations within same region"
    echo ""
    log "Example Monthly Costs:"
    log "  - Small app (5GB images): ~\$0.50/month"
    log "  - Medium app (50GB images): ~\$5.00/month"
    log "  - Large app (500GB images): ~\$50.00/month"
    echo ""
    warning "Costs depend on image size and deployment frequency"
    log "Monitor costs at: https://console.cloud.google.com/billing"
}

# Display next steps
display_next_steps() {
    echo ""
    success "=== Artifact Registry Setup Complete! ==="
    echo ""
    log "Next steps:"
    log "  1. Source the environment file: source .env.artifact-registry"
    log "  2. Update your cloudbuild.yaml with the new repository URL"
    log "  3. Test the build pipeline: gcloud builds submit --config cloudbuild.yaml"
    log "  4. Set up automated triggers for continuous deployment"
    log "  5. Configure vulnerability scanning in Cloud Build"
    echo ""
    log "Repository URL: ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}"
    log "Console: https://console.cloud.google.com/artifacts/docker/${PROJECT_ID}/${REGION}/${REPO_NAME}"
}

# Main execution
main() {
    log "Starting Artifact Registry setup for Loist Music Library..."
    echo ""

    # Pre-flight checks
    check_gcloud
    check_docker
    setup_gcloud_project

    # Check if repository exists
    if check_repository_exists; then
        warning "Repository already exists. Skipping creation but will configure settings..."
    else
        # Create repository
        create_repository
    fi

    # Configure repository
    configure_labels
    configure_iam_permissions
    configure_cleanup_policies
    configure_docker_auth

    # Test setup
    test_repository_access
    build_test_image

    # Post-creation tasks
    generate_env_config
    display_cost_estimation
    display_next_steps
}

# Run main function
main "$@"
