#!/bin/bash
# Task Queue Validation Script
# Validates Cloud Tasks integration
#
# Run with: bash scripts/validate_task_queue.sh

set -e

echo "🔍 Validating task queue integration..."
echo

# Check environment variables
echo "1. Checking environment variables..."
if [ -z "$GOOGLE_CLOUD_PROJECT" ]; then
    echo "❌ GOOGLE_CLOUD_PROJECT not set"
    echo "   Please set: export GOOGLE_CLOUD_PROJECT=your-project-id"
    exit 1
fi

echo "✅ Environment variables configured"
echo "   Project: $GOOGLE_CLOUD_PROJECT"
echo

# Test Cloud Tasks enqueueing
echo "2. Testing Cloud Tasks enqueueing..."
python3 -c "
import sys
sys.path.insert(0, 'src')

from tasks.queue import enqueue_waveform_generation
import uuid
import os

try:
    # Generate test data
    audio_id = str(uuid.uuid4())
    audio_gcs_path = f'gs://test-bucket/audio/{audio_id}.mp3'
    source_hash = 'a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3'
    
    print(f'Test audio_id: {audio_id}')
    print(f'Test audio_gcs_path: {audio_gcs_path}')
    print(f'Test source_hash: {source_hash}')
    
    # Test enqueue_waveform_generation
    print('Testing enqueue_waveform_generation...')
    task_id = enqueue_waveform_generation(
        audio_id=audio_id,
        audio_gcs_path=audio_gcs_path,
        source_hash=source_hash
    )
    
    print(f'✅ Task enqueued successfully')
    print(f'   Task ID: {task_id}')
    
    # Validate task_id format (should be numeric for Cloud Tasks)
    if not task_id.isdigit():
        print(f'⚠️  Task ID format unexpected: {task_id}')
        print('   (This may be normal depending on Cloud Tasks configuration)')
    
except Exception as e:
    print(f'❌ Task queue test failed: {e}')
    import traceback
    traceback.print_exc()
    
    # Check if this is a common Cloud Tasks error
    if 'Cloud Tasks client creation failed' in str(e):
        print()
        print('💡 This error typically means:')
        print('   1. GOOGLE_APPLICATION_CREDENTIALS is not set')
        print('   2. The service account key file does not exist')
        print('   3. Running outside GCP (Cloud Tasks requires GCP environment)')
        print()
        print('   For local development, Cloud Tasks may not be available.')
        print('   Consider using local task queue simulation for testing.')
        
    import sys
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ Task queue test failed"
    exit 1
fi

echo
echo "🎉 Task queue validation passed!"
echo "   Cloud Tasks integration working correctly"
