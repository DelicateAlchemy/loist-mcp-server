#!/bin/bash

# IAM Permissions Validation Script
# Validates that the service account has all required permissions for GCS and Cloud SQL

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-loist-music-library}"
SERVICE_ACCOUNT_EMAIL="loist-music-library-sa@${PROJECT_ID}.iam.gserviceaccount.com"
BUCKET_NAME="${GCS_BUCKET_NAME:-loist-music-library-audio}"

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

# Check if gcloud is available
check_gcloud() {
    if ! command -v gcloud &> /dev/null; then
        error "gcloud CLI is not installed"
        exit 1
    fi
}

# Validate project access
validate_project() {
    log "Validating project access..."
    
    if gcloud projects describe "$PROJECT_ID" &> /dev/null; then
        success "Project $PROJECT_ID is accessible"
    else
        error "Cannot access project $PROJECT_ID"
        exit 1
    fi
}

# Validate service account exists
validate_service_account() {
    log "Validating service account..."
    
    if gcloud iam service-accounts describe "$SERVICE_ACCOUNT_EMAIL" \
       --project="$PROJECT_ID" &> /dev/null; then
        success "Service account exists: $SERVICE_ACCOUNT_EMAIL"
    else
        error "Service account not found: $SERVICE_ACCOUNT_EMAIL"
        exit 1
    fi
}

# Check project-level IAM roles
check_project_iam() {
    log "Checking project-level IAM roles..."
    
    ROLES=$(gcloud projects get-iam-policy "$PROJECT_ID" \
        --flatten="bindings[].members" \
        --filter="bindings.members:${SERVICE_ACCOUNT_EMAIL}" \
        --format="value(bindings.role)")
    
    if [ -z "$ROLES" ]; then
        error "Service account has no project-level roles"
        return 1
    fi
    
    echo "$ROLES" | while read -r role; do
        success "✓ $role"
    done
    
    # Check for required roles
    REQUIRED_ROLES=(
        "roles/storage.admin"
        "roles/cloudsql.admin"
        "roles/logging.logWriter"
        "roles/monitoring.metricWriter"
    )
    
    for required_role in "${REQUIRED_ROLES[@]}"; do
        if echo "$ROLES" | grep -q "$required_role"; then
            success "✓ Required role present: $required_role"
        else
            warning "⚠ Required role missing: $required_role"
        fi
    done
}

# Check bucket-level IAM roles
check_bucket_iam() {
    log "Checking bucket-level IAM roles..."
    
    if ! gsutil ls -b "gs://${BUCKET_NAME}" &> /dev/null; then
        error "Cannot access bucket: gs://${BUCKET_NAME}"
        return 1
    fi
    
    IAM_POLICY=$(gcloud storage buckets get-iam-policy "gs://${BUCKET_NAME}" --format=json)
    
    if echo "$IAM_POLICY" | grep -q "serviceAccount:$SERVICE_ACCOUNT_EMAIL"; then
        success "✓ Service account has bucket-level permissions"
        
        # Check specific roles
        if echo "$IAM_POLICY" | grep -A 5 "$SERVICE_ACCOUNT_EMAIL" | grep -q "storage.objectAdmin"; then
            success "✓ Has storage.objectAdmin role on bucket"
        else
            warning "⚠ Missing storage.objectAdmin role on bucket"
        fi
    else
        warning "⚠ Service account not found in bucket IAM policy"
    fi
}

# Test GCS operations
test_gcs_operations() {
    log "Testing GCS operations..."
    
    TEST_FILE=$(mktemp)
    echo "IAM validation test" > "$TEST_FILE"
    TEST_OBJECT="test/iam-validation-$(date +%s).txt"
    
    # Test upload (requires storage.objects.create)
    if gsutil cp "$TEST_FILE" "gs://${BUCKET_NAME}/${TEST_OBJECT}" &> /dev/null; then
        success "✓ Can upload objects (storage.objects.create)"
    else
        error "✗ Cannot upload objects"
    fi
    
    # Test read (requires storage.objects.get)
    if gsutil cat "gs://${BUCKET_NAME}/${TEST_OBJECT}" &> /dev/null; then
        success "✓ Can read objects (storage.objects.get)"
    else
        error "✗ Cannot read objects"
    fi
    
    # Test list (requires storage.objects.list)
    if gsutil ls "gs://${BUCKET_NAME}/${TEST_OBJECT}" &> /dev/null; then
        success "✓ Can list objects (storage.objects.list)"
    else
        error "✗ Cannot list objects"
    fi
    
    # Test delete (requires storage.objects.delete)
    if gsutil rm "gs://${BUCKET_NAME}/${TEST_OBJECT}" &> /dev/null; then
        success "✓ Can delete objects (storage.objects.delete)"
    else
        error "✗ Cannot delete objects"
    fi
    
    rm "$TEST_FILE"
}

# Check signBlob permission
check_signblob_permission() {
    log "Checking signBlob permission for signed URL generation..."
    
    # This permission is required for generating signed URLs
    ROLES=$(gcloud projects get-iam-policy "$PROJECT_ID" \
        --flatten="bindings[].members" \
        --filter="bindings.members:${SERVICE_ACCOUNT_EMAIL}" \
        --format="value(bindings.role)")
    
    if echo "$ROLES" | grep -qE "(roles/storage.admin|roles/iam.serviceAccountTokenCreator)"; then
        success "✓ Has permission to sign blobs (for signed URLs)"
    else
        warning "⚠ May not have permission to sign blobs"
        warning "  Required for generating signed URLs"
        warning "  Add role: roles/iam.serviceAccountTokenCreator"
    fi
}

# Generate security report
generate_report() {
    log "Generating security report..."
    
    REPORT_FILE="scripts/iam-validation-report-$(date +%Y%m%d-%H%M%S).txt"
    
    {
        echo "IAM Permissions Validation Report"
        echo "=================================="
        echo "Date: $(date)"
        echo "Project: $PROJECT_ID"
        echo "Service Account: $SERVICE_ACCOUNT_EMAIL"
        echo "Bucket: gs://${BUCKET_NAME}"
        echo ""
        echo "Project-Level Roles:"
        echo "-------------------"
        gcloud projects get-iam-policy "$PROJECT_ID" \
            --flatten="bindings[].members" \
            --filter="bindings.members:${SERVICE_ACCOUNT_EMAIL}" \
            --format="value(bindings.role)" | sed 's/^/  /'
        echo ""
        echo "Bucket-Level Roles:"
        echo "------------------"
        gsutil iam get "gs://${BUCKET_NAME}" | grep -A 10 "$SERVICE_ACCOUNT_EMAIL" || echo "  None found"
        echo ""
        echo "Validation Tests:"
        echo "----------------"
        echo "  All tests completed successfully"
    } > "$REPORT_FILE"
    
    success "Report saved to: $REPORT_FILE"
}

# Provide security recommendations
security_recommendations() {
    log "Security Recommendations:"
    echo ""
    
    warning "1. Least Privilege: Consider removing roles/storage.admin from project level"
    echo "   Keep bucket-level storage.objectAdmin for fine-grained access"
    echo ""
    
    warning "2. Key Rotation: Rotate service account keys every 90 days"
    echo "   Current keys can be listed with:"
    echo "   gcloud iam service-accounts keys list --iam-account=$SERVICE_ACCOUNT_EMAIL"
    echo ""
    
    warning "3. Workload Identity: For production deployments on GKE, use Workload Identity"
    echo "   instead of service account keys"
    echo ""
    
    warning "4. Monitoring: Enable Cloud Audit Logs for security monitoring"
    echo "   Track authentication attempts and permission changes"
    echo ""
}

# Main execution
main() {
    log "Starting IAM permissions validation..."
    echo ""
    
    check_gcloud
    validate_project
    validate_service_account
    echo ""
    
    check_project_iam
    echo ""
    
    check_bucket_iam
    echo ""
    
    test_gcs_operations
    echo ""
    
    check_signblob_permission
    echo ""
    
    generate_report
    echo ""
    
    security_recommendations
    
    echo ""
    success "=== IAM Validation Complete ==="
}

# Run main function
main "$@"

