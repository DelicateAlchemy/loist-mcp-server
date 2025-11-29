#!/bin/bash
# Waveform Database Validation Script
# Validates database operations for waveform metadata
#
# Run with: bash scripts/validate_waveform_database.sh

set -e

echo "🔍 Validating waveform database operations..."
echo

# Check database connection
echo "1. Checking database connection..."
python3 -c "
import sys
sys.path.insert(0, 'src')

try:
    from database.pool import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT 1')
            result = cur.fetchone()
            if result[0] == 1:
                print('✅ Database connection successful')
            else:
                print('❌ Database query failed')
                sys.exit(1)
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ Database connection test failed"
    exit 1
fi
echo

# Test waveform metadata operations
echo "2. Testing waveform metadata operations..."
python3 -c "
import sys
sys.path.insert(0, 'src')

from database.operations import update_waveform_metadata, get_waveform_metadata, check_waveform_cache, save_audio_metadata
import uuid

try:
    # Generate test data
    audio_id = str(uuid.uuid4())
    gcs_path = f'gs://test-bucket/waveforms/{audio_id}/abc123.svg'
    source_hash = 'a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3'

    print(f'Test audio_id: {audio_id}')
    print(f'Test GCS path: {gcs_path}')
    print(f'Test source hash: {source_hash}')

    # First, create a test audio track
    print('Creating test audio track...')
    test_metadata = {
        'title': 'Test Waveform Track',
        'artist': 'Test Artist',
        'album': 'Test Album',
        'format': 'MP3',
        'duration_seconds': 180.0,
        'sample_rate': 44100,
        'bitrate': 320000,
        'channels': 2,
        'file_size_bytes': 7200000
    }
    save_audio_metadata(
        metadata=test_metadata,
        audio_gcs_path=f'gs://test-bucket/audio/{audio_id}.mp3',
        track_id=audio_id
    )
    print('✅ Test audio track created')

    # Test update_waveform_metadata
    print('Testing update_waveform_metadata...')
    update_waveform_metadata(audio_id, gcs_path, source_hash)
    print('✅ update_waveform_metadata successful')
    
    # Test get_waveform_metadata
    print('Testing get_waveform_metadata...')
    metadata = get_waveform_metadata(audio_id)
    if metadata:
        print('✅ get_waveform_metadata successful')
        print(f'   Retrieved GCS path: {metadata.get(\"waveform_gcs_path\")}')
        print(f'   Retrieved source hash: {metadata.get(\"source_audio_hash\")}')
        
        # Verify data integrity
        if metadata.get('waveform_gcs_path') != gcs_path:
            print('❌ GCS path mismatch')
            sys.exit(1)
        if metadata.get('source_audio_hash') != source_hash:
            print('❌ Source hash mismatch')
            sys.exit(1)
    else:
        print('❌ get_waveform_metadata returned None')
        sys.exit(1)
    
    # Test check_waveform_cache (cache hit)
    print('Testing check_waveform_cache (cache hit)...')
    cached_path = check_waveform_cache(audio_id, source_hash)
    if cached_path == gcs_path:
        print('✅ check_waveform_cache (hit) successful')
    else:
        print(f'❌ check_waveform_cache (hit) failed: expected {gcs_path}, got {cached_path}')
        sys.exit(1)
    
    # Test check_waveform_cache (cache miss)
    print('Testing check_waveform_cache (cache miss)...')
    wrong_hash = 'different' + source_hash[9:]
    cached_path = check_waveform_cache(audio_id, wrong_hash)
    if cached_path is None:
        print('✅ check_waveform_cache (miss) successful')
    else:
        print(f'❌ check_waveform_cache (miss) failed: expected None, got {cached_path}')
        sys.exit(1)
    
    # Test non-existent audio ID
    print('Testing non-existent audio ID...')
    fake_id = str(uuid.uuid4())
    metadata = get_waveform_metadata(fake_id)
    if metadata is None:
        print('✅ Non-existent audio ID handling successful')
    else:
        print('❌ Non-existent audio ID returned data')
        sys.exit(1)
        
except Exception as e:
    print(f'❌ Database operations test failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ Database operations test failed"
    exit 1
fi

echo
echo "🎉 Waveform database validation passed!"
echo "   All database operations working correctly"
