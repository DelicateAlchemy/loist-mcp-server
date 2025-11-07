#!/usr/bin/env python3
"""
Test signed URL generation for GCS bucket access.

This script tests if signed URL generation works with the correct GCS bucket
configuration, simulating what the embed endpoint does.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

def test_signed_url_generation():
    """Test signed URL generation with correct bucket configuration."""

    print("🔍 Testing Signed URL Generation")
    print("=" * 50)

    # Set up environment like staging
    os.environ['GCS_BUCKET_NAME'] = 'loist-music-library-bucket-staging'
    os.environ['GCS_PROJECT_ID'] = 'loist-music-library'
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/Users/Gareth/loist-mcp-server/service-account-key.json'

    # Import after setting environment
    try:
        from src.storage import generate_signed_url
        from src.config import config

        print("✅ Imports successful")
        print(f"Config GCS bucket name: {config.gcs_bucket_name}")
        print(f"Env GCS_BUCKET_NAME: {os.getenv('GCS_BUCKET_NAME')}")

        # Test path that should exist in staging bucket
        test_audio_path = 'gs://loist-music-library-bucket-staging/audio/ba8c6d62-0779-4af2-bef4-022138928b3c/ba8c6d62-0779-4af2-bef4-022138928b3c.mp3'

        print(f"\nTesting signed URL generation for: {test_audio_path}")

        try:
            signed_url = generate_signed_url(
                blob_name='audio/ba8c6d62-0779-4af2-bef4-022138928b3c/ba8c6d62-0779-4af2-bef4-022138928b3c.mp3',
                bucket_name='loist-music-library-bucket-staging',
                expiration_minutes=15
            )

            print("✅ Signed URL generated successfully!")
            print(f"URL: {signed_url[:100]}...")

            # Test if URL is accessible (basic check)
            import requests
            response = requests.head(signed_url, timeout=10)
            print(f"HTTP Status: {response.status_code}")

            if response.status_code == 200:
                print("✅ Signed URL is accessible!")
                print(f"Content-Type: {response.headers.get('content-type')}")
                print(f"Content-Length: {response.headers.get('content-length')}")
            else:
                print(f"⚠️  Signed URL returned status: {response.status_code}")

        except Exception as e:
            print(f"❌ Signed URL generation failed: {e}")
            import traceback
            print("Full traceback:")
            traceback.print_exc()

    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

    return True

def test_config_loading():
    """Test configuration loading."""

    print("\n" + "=" * 50)
    print("Testing Configuration Loading")
    print("=" * 50)

    # Test different bucket configurations
    test_configs = [
        {
            'name': 'Correct staging bucket',
            'env': {'GCS_BUCKET_NAME': 'loist-music-library-bucket-staging'},
            'expected': 'loist-music-library-bucket-staging'
        },
        {
            'name': 'Wrong bucket (old)',
            'env': {'GCS_BUCKET_NAME': 'loist-music-library-staging-audio'},
            'expected': 'loist-music-library-staging-audio'
        },
        {
            'name': 'No env var (should use config default)',
            'env': {},
            'expected': None  # Config default is None
        }
    ]

    for test_config in test_configs:
        print(f"\nTesting: {test_config['name']}")

        # Set environment
        for key, value in test_config['env'].items():
            os.environ[key] = value

        # Clear env var if not in test
        if 'GCS_BUCKET_NAME' not in test_config['env']:
            os.environ.pop('GCS_BUCKET_NAME', None)

        try:
            # Reload config
            import importlib
            import src.config
            importlib.reload(src.config)
            from src.config import config

            actual = config.gcs_bucket_name
            expected = test_config['expected']

            if actual == expected:
                print(f"✅ Config loaded correctly: {actual}")
            else:
                print(f"❌ Config mismatch - Expected: {expected}, Got: {actual}")

        except Exception as e:
            print(f"❌ Config loading failed: {e}")

if __name__ == "__main__":
    print("🔧 Loist Music Library - Signed URL Generation Test")
    print("=" * 60)

    # Test configuration loading
    test_config_loading()

    # Test signed URL generation
    test_signed_url_generation()

    print("\n" + "=" * 60)
    print("Test completed.")
    print("=" * 60)
