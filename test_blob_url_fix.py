#!/usr/bin/env python3
"""
Test script for the blob URL filename override fix.
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any

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


def test_downloader_filename_override():
    """Test that the downloader respects filename overrides."""

    from src.downloader import download_from_url

    # Test URL that has no extension (simulating blob URL)
    test_url = "https://httpbin.org/bytes/1024"  # Returns binary data

    print("Testing downloader filename override...")

    # Test without filename override (should get .bin)
    try:
        temp_path_1 = download_from_url(test_url, max_size_mb=1, timeout_seconds=30)
        print(f"Without override: {temp_path_1} (suffix: {temp_path_1.suffix})")

        # Clean up
        if temp_path_1.exists():
            temp_path_1.unlink()

    except Exception as e:
        print(f"Error without override: {e}")

    # Test with filename override (should get .mp3)
    try:
        temp_path_2 = download_from_url(
            test_url,
            max_size_mb=1,
            timeout_seconds=30,
            filename_override="test-song.mp3"
        )
        print(f"With override: {temp_path_2} (suffix: {temp_path_2.suffix})")

        # Verify the extension is correct
        if temp_path_2.suffix == ".mp3":
            print("✅ Filename override working correctly!")
        else:
            print(f"❌ Expected .mp3, got {temp_path_2.suffix}")

        # Clean up
        if temp_path_2.exists():
            temp_path_2.unlink()

    except Exception as e:
        print(f"Error with override: {e}")


def test_get_file_extension_logic():
    """Test the _get_file_extension method directly."""

    from src.downloader.http_downloader import HTTPDownloader

    downloader = HTTPDownloader()

    # Test cases
    test_cases = [
        ("https://example.com/song.mp3", None, ".mp3"),
        ("https://example.com/song.wav", None, ".wav"),
        ("https://example.com/blob/xyz123", None, ".bin"),  # No extension
        ("https://example.com/blob/xyz123", "song.mp3", ".mp3"),  # With override
        ("https://example.com/blob/xyz123", "music.flac", ".flac"),  # With override
    ]

    print("\nTesting _get_file_extension logic...")

    for url, filename_override, expected in test_cases:
        result = downloader._get_file_extension(url, filename_override)
        status = "✅" if result == expected else "❌"
        print(f"{status} URL: {url}, Override: {filename_override}, Expected: {expected}, Got: {result}")


if __name__ == "__main__":
    print("Blob URL Filename Override Fix Test")
    print("=" * 50)

    test_get_file_extension_logic()
    test_downloader_filename_override()

    print("\nTest completed!")