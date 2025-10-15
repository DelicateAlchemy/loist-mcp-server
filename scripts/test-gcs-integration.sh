#!/bin/bash

# GCS Integration Test Runner for Task 11.4
# This script sets up the environment and runs real GCS integration tests

set -e

echo "🧪 GCS Integration Test Runner for Task 11.4"
echo "=============================================="

# Check if we're in the right directory
if [ ! -f "src/server.py" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    exit 1
fi

# Check for required environment variables
echo "📋 Checking environment configuration..."

if [ -z "$GCS_BUCKET_NAME" ]; then
    echo "❌ Error: GCS_BUCKET_NAME environment variable is required"
    echo "   Set it to your test bucket name (e.g., 'loist-music-library-dev')"
    exit 1
fi

if [ -z "$GCS_PROJECT_ID" ]; then
    echo "❌ Error: GCS_PROJECT_ID environment variable is required"
    echo "   Set it to your GCP project ID"
    exit 1
fi

echo "✅ GCS_BUCKET_NAME: $GCS_BUCKET_NAME"
echo "✅ GCS_PROJECT_ID: $GCS_PROJECT_ID"

# Check for credentials
if [ -n "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    if [ -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
        echo "✅ GOOGLE_APPLICATION_CREDENTIALS: $GOOGLE_APPLICATION_CREDENTIALS"
    else
        echo "❌ Error: GOOGLE_APPLICATION_CREDENTIALS file not found: $GOOGLE_APPLICATION_CREDENTIALS"
        exit 1
    fi
else
    # Check for gcloud auth
    if gcloud auth application-default print-access-token >/dev/null 2>&1; then
        echo "✅ Using gcloud application-default credentials"
    else
        echo "❌ Error: No GCS credentials found"
        echo "   Either set GOOGLE_APPLICATION_CREDENTIALS or run: gcloud auth application-default login"
        exit 1
    fi
fi

# Check if bucket exists and is accessible
echo "🔍 Verifying bucket access..."
if gsutil ls "gs://$GCS_BUCKET_NAME" >/dev/null 2>&1; then
    echo "✅ Bucket $GCS_BUCKET_NAME is accessible"
else
    echo "❌ Error: Cannot access bucket $GCS_BUCKET_NAME"
    echo "   Please check your permissions and bucket name"
    exit 1
fi

# Check Python dependencies
echo "🐍 Checking Python dependencies..."
if ! python -c "import google.cloud.storage" 2>/dev/null; then
    echo "❌ Error: google-cloud-storage package not installed"
    echo "   Run: pip install google-cloud-storage"
    exit 1
fi

if ! python -c "import pytest" 2>/dev/null; then
    echo "❌ Error: pytest package not installed"
    echo "   Run: pip install pytest"
    exit 1
fi

echo "✅ All dependencies are available"

# Set up test environment
echo "🔧 Setting up test environment..."

# Create test-specific environment variables
export TEST_GCS_BUCKET_NAME="$GCS_BUCKET_NAME"
export TEST_GCS_PROJECT_ID="$GCS_PROJECT_ID"

# Add src to Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

echo "✅ Test environment configured"

# Run the tests
echo "🚀 Running GCS integration tests..."
echo ""

# Run tests with verbose output and stop on first failure
python -m pytest tests/test_real_gcs_integration.py \
    -v \
    -s \
    --tb=short \
    --maxfail=1 \
    --durations=10

# Check test results
if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 All GCS integration tests passed!"
    echo ""
    echo "✅ Task 11.4 validation complete:"
    echo "   - GCS client connection verified"
    echo "   - File upload/download operations tested"
    echo "   - Signed URL generation validated"
    echo "   - Cache system integration confirmed"
    echo "   - Error handling verified"
    echo "   - Performance and reliability tested"
    echo ""
    echo "🚀 Ready to proceed with Task 11.5 (MCP Tools Validation)"
else
    echo ""
    echo "❌ GCS integration tests failed!"
    echo ""
    echo "🔍 Troubleshooting tips:"
    echo "   - Check your GCS credentials and permissions"
    echo "   - Verify the bucket exists and is accessible"
    echo "   - Ensure you have the required IAM roles:"
    echo "     * Storage Object Admin (for upload/delete)"
    echo "     * Storage Object Viewer (for read operations)"
    echo "   - Check network connectivity to Google Cloud"
    echo ""
    exit 1
fi
