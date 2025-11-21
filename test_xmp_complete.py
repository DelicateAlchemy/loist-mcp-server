#!/usr/bin/env python3
"""
Test complete XMP extraction and database persistence.
"""

import sys
import os
import tempfile
import requests
from pathlib import Path

# Add src to path
sys.path.insert(0, '/app/src')

from metadata import (
    extract_metadata_with_fallback,
    enhance_metadata_with_xmp,
    should_attempt_xmp_extraction
)
from database.operations import save_audio_metadata, get_connection
import uuid

def test_complete_xmp_workflow():
    """Test the complete XMP extraction and database persistence workflow."""

    # URL of the test WAV file
    test_url = "https://tmpfiles.org/dl/10109368/hpe334_01_1legendofkyoto_instrumental.wav"

    print("🎵 Testing Complete XMP Workflow")
    print("=" * 50)

    # Download the test file
    print(f"Downloading test file: {test_url}")
    try:
        response = requests.get(test_url, timeout=30)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Failed to download test file: {e}")
        return

    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
        temp_file.write(response.content)
        temp_path = Path(temp_file.name)

    print(f"Downloaded to: {temp_path}")
    print(f"File size: {temp_path.stat().st_size} bytes")

    try:
        # Step 1: Basic metadata extraction
        print("\n📊 Step 1: Basic metadata extraction...")
        basic_metadata, was_repaired = extract_metadata_with_fallback(temp_path)
        print(f"Basic metadata keys: {list(basic_metadata.keys())}")
        print(f"Title: {basic_metadata.get('title', 'N/A')}")
        print(f"Artist: {basic_metadata.get('artist', 'N/A')}")

        # Step 2: XMP enhancement
        if should_attempt_xmp_extraction(temp_path, basic_metadata):
            print("\n🎯 Step 2: XMP enhancement...")
            enhanced_metadata = enhance_metadata_with_xmp(temp_path, basic_metadata)

            xmp_enhanced = enhanced_metadata.get('_xmp_enhanced', False)
            print(f"XMP Enhanced: {xmp_enhanced}")

            if xmp_enhanced:
                xmp_fields = enhanced_metadata.get('_xmp_fields', [])
                print(f"XMP Fields found: {xmp_fields}")

                # Show before/after comparison
                print("\n🔄 Before vs After:")
                for field in ['artist', 'title', 'album', 'composer', 'publisher', 'record_label', 'isrc']:
                    before = basic_metadata.get(field, 'N/A')
                    after = enhanced_metadata.get(field, 'N/A')
                    if before != after:
                        print(f"  {field}: '{before}' → '{after}' ⭐")
                    else:
                        print(f"  {field}: '{before}'")

                # Step 3: Database persistence
                print("\n💾 Step 3: Database persistence...")
                track_id = str(uuid.uuid4())

                # Prepare database record with XMP fields
                db_metadata = {
                    "artist": enhanced_metadata.get("artist", ""),
                    "title": enhanced_metadata.get("title", "Untitled"),
                    "album": enhanced_metadata.get("album", ""),
                    "genre": enhanced_metadata.get("genre"),
                    "year": enhanced_metadata.get("year"),
                    "duration": enhanced_metadata.get("duration", 0),
                    "channels": enhanced_metadata.get("channels", 2),
                    "sample_rate": enhanced_metadata.get("sample_rate", 44100),
                    "bitrate": enhanced_metadata.get("bitrate", 0),
                    "format": enhanced_metadata.get("format", ""),
                    # XMP fields
                    "composer": enhanced_metadata.get("composer"),
                    "publisher": enhanced_metadata.get("publisher"),
                    "record_label": enhanced_metadata.get("record_label"),
                    "isrc": enhanced_metadata.get("isrc"),
                }

                print("Database record to save:")
                for key, value in db_metadata.items():
                    if value is not None and value != "":
                        print(f"  {key}: {value}")

                # Save to database
                try:
                    saved_record = save_audio_metadata(
                        metadata=db_metadata,
                        audio_gcs_path=f"gs://test/audio/{track_id}/test.wav",
                        thumbnail_gcs_path=None,
                        track_id=track_id
                    )
                    print(f"✅ Successfully saved to database with ID: {track_id}")

                    # Verify the data was saved correctly
                    print("\n🔍 Step 4: Verification...")
                    conn = get_connection()
                    try:
                        with conn.cursor() as cur:
                            cur.execute("""
                                SELECT artist, title, album, composer, publisher, record_label, isrc
                                FROM audio_tracks WHERE id = %s
                            """, (track_id,))

                            result = cur.fetchone()
                            if result:
                                print("Database record verification:")
                                fields = ['artist', 'title', 'album', 'composer', 'publisher', 'record_label', 'isrc']
                                for i, field in enumerate(fields):
                                    value = result[i]
                                    if value:
                                        print(f"  {field}: '{value}' ✅")
                                    else:
                                        print(f"  {field}: None")
                            else:
                                print("❌ Record not found in database")

                    finally:
                        conn.close()

                except Exception as e:
                    print(f"❌ Database save failed: {e}")
                    import traceback
                    traceback.print_exc()

        else:
            print("Skipping XMP extraction based on existing metadata quality")

    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        if temp_path.exists():
            temp_path.unlink()
            print(f"\n🧹 Cleaned up temp file: {temp_path}")

if __name__ == "__main__":
    test_complete_xmp_workflow()
