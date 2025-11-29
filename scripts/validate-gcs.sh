#!/bin/bash
# Validate Google Cloud Storage operations

set -e

PROJECT_ID="loist-music-library"
BUCKET_NAME="${GCS_BUCKET_NAME:-loist-mvp-audio-files}"

echo "========================================="
echo " Google Cloud Storage Validation"
echo "========================================="
echo "Bucket: gs://$BUCKET_NAME"
echo ""

# Test 1: Bucket exists
echo "1. Verifying Bucket Existence..."
echo "-------------------------------------"
if gsutil ls -p $PROJECT_ID "gs://$BUCKET_NAME" &> /dev/null; then
    echo "✅ Bucket exists: gs://$BUCKET_NAME"
else
    echo "❌ Bucket not found: gs://$BUCKET_NAME"
    exit 1
fi
echo ""

# Test 2: Bucket permissions
echo "2. Checking Bucket Permissions..."
echo "-------------------------------------"
gsutil iam get "gs://$BUCKET_NAME" | head -20 2>&1
echo "✅ IAM policy retrieved"
echo ""

# Test 3: Test file upload (dry run)
echo "3. Testing File Upload Capability..."
echo "-------------------------------------"
TEST_FILE="/tmp/test-upload-$(date +%s).txt"
echo "This is a test file" > $TEST_FILE

if gsutil cp $TEST_FILE "gs://$BUCKET_NAME/test/" 2>&1; then
    echo "✅ File upload successful"
    # Clean up test file
    gsutil rm "gs://$BUCKET_NAME/test/$(basename $TEST_FILE)" 2>&1 || true
else
    echo "❌ File upload failed"
    exit 1
fi

rm -f $TEST_FILE
echo ""

# Test 4: Bucket location and storage class
echo "4. Bucket Configuration..."
echo "-------------------------------------"
gsutil ls -L -b "gs://$BUCKET_NAME" | grep -E "Location|Storage class|Versioning" 2>&1
echo ""

# Test 5: Bucket size and object count
echo "5. Bucket Statistics..."
echo "-------------------------------------"
OBJECT_COUNT=$(gsutil ls -r "gs://$BUCKET_NAME/**" 2>/dev/null | wc -l || echo "0")
echo "Object count: $OBJECT_COUNT"
echo ""

echo "========================================="
echo "✅ GCS validation complete"
echo "========================================="

