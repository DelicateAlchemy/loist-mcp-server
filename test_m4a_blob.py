#!/usr/bin/env python3
"""
Test the blob URL fix with an M4A file.
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

def test_m4a_blob_url():
    """Test the M4A blob URL with our fix."""

    from src.tools.process_audio import process_audio_complete_sync

    # Test case for M4A file
    source = {
        "type": "http_url",
        "url": "https://codahosted.io/docs/RQFw0P6Rnl/blobs/bl-k6EbXdUMyg/732d207c8844bcad6e3408d3c1996caf18450081243ac76ab6412373d36174dbdfffb310c5b674d6659ab4f24dae053c89b1f68f08a255997512f495516d54353fe85cf3a97a01883165c7c8e20f08b9ecd1e7bf597bba038f15242590926db6da2acd61",
        "filename": "Unknown Track.m4a",
        "mimeType": "audio/mp4"
    }

    options = {
        "maxSizeMB": 100,
        "timeout": 300,
        "validateFormat": True
    }

    print("Testing process_audio_complete with M4A blob URL...")
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
            print("🎉 M4A blob URL processing completed successfully!")
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
    success = test_m4a_blob_url()
    exit(0 if success else 1)
