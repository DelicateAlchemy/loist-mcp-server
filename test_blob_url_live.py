#!/usr/bin/env python3
"""
Test the blob URL fix with the actual process_audio_complete function.
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set up environment like run_server.py does
if not os.getenv('GOOGLE_CLOUD_PROJECT'):
    os.environ.setdefault('DATABASE_URL', 'postgresql://loist_user:dev_password@localhost:5432/loist_mvp')
    os.environ.setdefault('GCS_PROJECT_ID', 'loist-music-library')
    os.environ.setdefault('GCS_BUCKET_NAME', 'loist-mvp-audio-files')
    os.environ.setdefault('GCS_REGION', 'us-central1')
    os.environ.setdefault('GOOGLE_APPLICATION_CREDENTIALS', './service-account-key.json')
    os.environ.setdefault('SERVER_TRANSPORT', 'http')
    os.environ.setdefault('SERVER_PORT', '8080')
    os.environ.setdefault('AUTH_ENABLED', 'false')
    os.environ.setdefault('ENABLE_CORS', 'true')
    os.environ.setdefault('CORS_ORIGINS', 'http://localhost:3000,http://localhost:8000,http://localhost:5173')

def test_process_audio_complete():
    """Test the process_audio_complete function directly."""

    from src.tools.process_audio import process_audio_complete_sync

    # Test case from the handover note
    source = {
        "type": "http_url",
        "url": "https://codahosted.io/docs/RQFw0P6Rnl/blobs/bl-TZMkzyaTCD/e2274c542db187d517d11a92534874cafb8023ce5de9a664be0d4557e84cc0024ee1f206c3776c7864542b2996b7bb14927dad8f5ca89350bbf37cb6845d541933b1e3456bf5b1b2400a9ba34193ba86ca3320f88ae7a353ee5c0c0ab1ed0566e549caef",
        "filename": "Europapa Joost.mp3",
        "mimeType": "audio/mpeg"
    }

    options = {
        "maxSizeMB": 100,
        "timeout": 300,
        "validateFormat": True
    }

    print("Testing process_audio_complete with blob URL...")
    print(f"Source: {source}")
    print(f"Options: {options}")

    try:
        result = process_audio_complete_sync({
            "source": source,
            "options": options
        })

        print("✅ SUCCESS!")
        print(f"Result: {result}")

        if result.get("success"):
            print("🎉 Blob URL processing completed successfully!")
            print(f"Audio ID: {result.get('audioId')}")
            return True
        else:
            print(f"❌ Processing failed: {result.get('error')} - {result.get('message')}")
            return False

    except Exception as e:
        print(f"❌ Exception during processing: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_process_audio_complete()
    exit(0 if success else 1)
