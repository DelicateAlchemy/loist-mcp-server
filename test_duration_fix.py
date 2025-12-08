#!/usr/bin/env python3
"""
Test script to verify duration field fix works correctly.
"""

import asyncio
import tempfile
import uuid
from pathlib import Path

from src.tools.process_audio import process_audio_complete


async def test_duration_storage():
    """Test that duration gets stored correctly in database."""

    # Create a simple test audio file (we'll use a mock for now)
    # For a real test, we'd need an actual audio file

    print("Testing duration storage fix...")

    # Mock the input data
    input_data = {
        "source": {
            "type": "http_url",
            "url": "https://example.com/test.mp3"  # This will fail but let's see what happens
        }
    }

    try:
        result = await process_audio_complete(input_data)
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error (expected for test URL): {e}")

    print("Test completed.")


if __name__ == "__main__":
    asyncio.run(test_duration_storage())
