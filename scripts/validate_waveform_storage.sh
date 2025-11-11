#!/bin/bash
# Waveform Storage Validation Script
# Validates GCS upload/download functionality
#
# Run with: bash scripts/validate_waveform_storage.sh

set -e

echo "🔍 Validating waveform storage..."
echo

# Check for required environment variables
echo "1. Checking environment variables..."
if [ -z "$GOOGLE_CLOUD_PROJECT" ]; then
    echo "❌ GOOGLE_CLOUD_PROJECT not set"
    echo "   Please set: export GOOGLE_CLOUD_PROJECT=your-project-id"
    exit 1
fi

if [ -z "$GCS_BUCKET_NAME" ]; then
    echo "❌ GCS_BUCKET_NAME not set"
    echo "   Please set: export GCS_BUCKET_NAME=your-bucket-name"
    exit 1
fi

echo "✅ Environment variables configured"
echo "   Project: $GOOGLE_CLOUD_PROJECT"
echo "   Bucket: $GCS_BUCKET_NAME"
echo

# Create test SVG file
echo "2. Creating test SVG file..."
TEST_SVG="/tmp/test_waveform_storage.svg"
cat > "$TEST_SVG" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2000 200" preserveAspectRatio="none">
  <path d="M0,100 L100,80 L200,120 L300,90 L400,110 L500,85 L600,115 L700,95 L800,105 L900,75 L1000,125 L1100,85 L1200,115 L1300,95 L1400,105 L1500,70 L1600,130 L1700,90 L1800,110 L1900,80 L2000,100" stroke="#000000" stroke-width="1" fill="none"/>
</svg>
EOF

if [ ! -f "$TEST_SVG" ]; then
    echo "❌ Failed to create test SVG file"
    exit 1
fi

echo "✅ Created test SVG file: $TEST_SVG"
echo

# Test GCS upload
echo "3. Testing GCS upload..."
python3 -c "
import sys
sys.path.insert(0, 'src')

from storage.waveform_storage import upload_waveform_svg
from pathlib import Path
import uuid

try:
    # Generate test IDs
    audio_id = str(uuid.uuid4())
    content_hash = 'a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3'[:8]
    
    print(f'Test audio_id: {audio_id}')
    print(f'Test content_hash: {content_hash}')
    
    # Upload SVG
    gcs_path = upload_waveform_svg(
        svg_path=Path('$TEST_SVG'),
        audio_id=audio_id,
        content_hash=content_hash
    )
    
    print(f'✅ Upload successful')
    print(f'   GCS path: {gcs_path}')
    
    # Test signed URL generation
    signed_url = __import__('storage.waveform_storage', fromlist=['get_waveform_signed_url']).get_waveform_signed_url(audio_id)
    
    if signed_url:
        print(f'✅ Signed URL generated')
        print(f'   URL: {signed_url[:100]}...')
    else:
        print('❌ Signed URL generation failed')
        import sys
        sys.exit(1)
        
except Exception as e:
    print(f'❌ GCS upload test failed: {e}')
    import traceback
    traceback.print_exc()
    import sys
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ GCS storage test failed"
    exit 1
fi

echo
echo "🎉 Waveform storage validation passed!"
echo "   Test SVG uploaded successfully to GCS"
echo "   Signed URL generation working"
