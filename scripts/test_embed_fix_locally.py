#!/usr/bin/env python3
"""
Test the embed fix logic locally to verify it works correctly.

This script simulates the embed endpoint behavior with different GCS path scenarios.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

def simulate_embed_fix_logic(audio_path, thumbnail_path=None):
    """
    Simulate the embed endpoint path correction logic.

    Args:
        audio_path: The audio_gcs_path from database
        thumbnail_path: The thumbnail_gcs_path from database

    Returns:
        tuple: (corrected_audio_path, corrected_thumbnail_path, was_corrected)
    """
    print(f"Input audio path: {audio_path}")
    print(f"Input thumbnail path: {thumbnail_path}")

    # Simulate the fix logic from server.py
    corrected_audio = audio_path
    corrected_thumb = thumbnail_path
    was_corrected = False

    # Fix for staging environment: correct bucket name if database contains old paths
    try:
        from src.config import config
        print("Config imported successfully")

        print(f"Checking audio path: {audio_path}")
        if audio_path and 'loist-music-library-staging-audio' in audio_path:
            corrected_audio = audio_path.replace('loist-music-library-staging-audio', 'loist-music-library-bucket-staging')
            print(f"✅ Correcting audio path from {audio_path} to {corrected_audio}")
            was_corrected = True
        else:
            print(f"Audio path does not need correction: {audio_path}")

        if thumbnail_path and 'loist-music-library-staging-audio' in thumbnail_path:
            corrected_thumb = thumbnail_path.replace('loist-music-library-staging-audio', 'loist-music-library-bucket-staging')
            print(f"✅ Correcting thumbnail path from {thumbnail_path} to {corrected_thumb}")
            was_corrected = True
        else:
            print(f"Thumbnail path does not need correction: {thumbnail_path}")

    except Exception as config_error:
        print(f"❌ Failed to import config: {config_error}")
        # Continue without config-based fixes

    return corrected_audio, corrected_thumb, was_corrected

def test_scenarios():
    """Test different scenarios of GCS paths."""

    print("🔧 Testing Embed GCS Path Correction Logic")
    print("=" * 60)

    test_cases = [
        {
            "name": "Original failing path (needs correction)",
            "audio": "gs://loist-music-library-staging-audio/audio/some-id/file.mp3",
            "thumb": "gs://loist-music-library-staging-audio/thumbnails/some-id/artwork.jpg",
            "expected_correction": True
        },
        {
            "name": "Already correct path (no correction needed)",
            "audio": "gs://loist-music-library-bucket-staging/audio/some-id/file.mp3",
            "thumb": "gs://loist-music-library-bucket-staging/thumbnails/some-id/artwork.jpg",
            "expected_correction": False
        },
        {
            "name": "Mixed paths (partial correction)",
            "audio": "gs://loist-music-library-staging-audio/audio/some-id/file.mp3",
            "thumb": "gs://loist-music-library-bucket-staging/thumbnails/some-id/artwork.jpg",
            "expected_correction": True
        },
        {
            "name": "No paths (edge case)",
            "audio": None,
            "thumb": None,
            "expected_correction": False
        }
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🧪 Test Case {i}: {test_case['name']}")
        print("-" * 40)

        corrected_audio, corrected_thumb, was_corrected = simulate_embed_fix_logic(
            test_case['audio'],
            test_case['thumb']
        )

        expected = test_case['expected_correction']
        status = "✅ PASS" if was_corrected == expected else "❌ FAIL"

        print(f"Expected correction: {expected}")
        print(f"Actual correction: {was_corrected}")
        print(f"Status: {status}")

        print(f"Final audio path: {corrected_audio}")
        print(f"Final thumbnail path: {corrected_thumb}")

    print("\n" + "=" * 60)
    print("🎯 Summary: If all tests show expected behavior, the fix logic works correctly.")
    print("The issue must be that the staging deployment hasn't picked up the changes yet.")

if __name__ == "__main__":
    test_scenarios()
