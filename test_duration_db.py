#!/usr/bin/env python3
"""
Test script to verify duration field database operations work correctly.
"""

from database.operations import save_audio_metadata


def test_duration_field_mapping():
    """Test that duration field gets stored correctly."""

    # Test data that mimics what process_audio.py would send
    test_metadata = {
        "artist": "Test Artist",
        "title": "Test Track",
        "album": "Test Album",
        "genre": "Test Genre",
        "year": 2024,
        "duration_seconds": 245.5,  # This is what our fix should store
        "channels": 2,
        "sample_rate": 44100,
        "bitrate": 128,
        "format": "mp3"
    }

    print("Testing database save with duration_seconds field...")
    print(f"Input data: duration_seconds = {test_metadata['duration_seconds']}")

    try:
        # This should work if our database operations are correct
        audio_id = save_audio_metadata(test_metadata)
        print(f"✅ Successfully saved audio with ID: {audio_id}")

        # Verify it was stored correctly
        from database import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT duration_seconds FROM audio_tracks WHERE id = %s', (str(audio_id),))
                result = cur.fetchone()
                if result and result[0] == 245.5:
                    print(f"✅ Duration stored correctly: {result[0]}")
                else:
                    print(f"❌ Duration not stored correctly: {result[0] if result else 'None'}")

    except Exception as e:
        print(f"❌ Error: {e}")

    print("Test completed.")


if __name__ == "__main__":
    test_duration_field_mapping()
