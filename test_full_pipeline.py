#!/usr/bin/env python3
"""
Test the full audio processing pipeline using process_audio_complete MCP tool.
"""

import sys
import os
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, 'src')

from src.tools.process_audio import process_audio_complete_sync

def test_mp3_blob_url():
    """Test MP3 blob URL processing"""
    print("\n🎵 Testing MP3 Blob URL Processing")

    # MP3 test case from handover note
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

    try:
        print(f"📥 Processing MP3: {source['filename']}")
        input_data = {"source": source, "options": options}
        result = process_audio_complete_sync(input_data)

        if 'error' in result:
            print(f"❌ Failed: {result['error']}")
            return False
        else:
            print("✅ MP3 processing successful!")
            print(f"   🎵 Audio ID: {result.get('audioId')}")
            print(f"   🎵 Title: {result.get('metadata', {}).get('Product', {}).get('Title', 'Unknown')}")
            print(f"   🎵 Artist: {result.get('metadata', {}).get('Product', {}).get('Artist', 'Unknown')}")
            return True

    except Exception as e:
        print(f"❌ MP3 processing failed: {e}")
        return False

def test_m4a_blob_url():
    """Test M4A blob URL processing"""
    print("\n🎵 Testing M4A Blob URL Processing")

    # M4A test case from handover note
    source = {
        "type": "http_url",
        "url": "https://codahosted.io/docs/RQFw0P6Rnl/blobs/bl-k6EbXdUMyg/732d207c8844bcad6e3408d3c1996caf18450081243ac76ab6412373d36174dbdfffb310c5b674d6659ab4f24dae053c89b1f68f08b255997512f495516d54353fe85cf3a97a01883165c7c8e20f08b9ecd1e7bf597bba038f15242590926db6da2acd61",
        "filename": "Unknown Track.m4a",
        "mimeType": "audio/mp4"
    }

    options = {
        "maxSizeMB": 100,
        "timeout": 300,
        "validateFormat": True
    }

    try:
        print(f"📥 Processing M4A: {source['filename']}")
        result = process_audio_complete(source=source, options=options)

        if 'error' in result:
            print(f"❌ Failed: {result['error']}")
            return False
        else:
            print("✅ M4A processing successful!")
            print(f"   🎵 Audio ID: {result.get('audioId')}")
            print(f"   🎵 Title: {result.get('metadata', {}).get('Product', {}).get('Title', 'Unknown')}")
            print(f"   🎵 Artist: {result.get('metadata', {}).get('Product', {}).get('Artist', 'Unknown')}")
            return True

    except Exception as e:
        print(f"❌ M4A processing failed: {e}")
        return False

def main():
    """Run full pipeline tests"""
    print("🎯 Full Audio Processing Pipeline Test")
    print("=" * 50)

    # Test results
    results = {}

    # Test MP3 processing
    results['mp3_processing'] = test_mp3_blob_url()

    # Test M4A processing
    results['m4a_processing'] = test_m4a_blob_url()

    # Summary
    print("\n" + "=" * 50)
    print("📊 Pipeline Test Results")

    passed = sum(1 for result in results.values() if result)
    total = len(results)

    print(f"Tests Passed: {passed}/{total}")

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name}: {status}")

    if passed == total:
        print("\n🎉 Full pipeline is working! GCS authentication resolved.")
        print("\n🚀 Next steps:")
        print("   1. Test embed URLs with generated audio IDs")
        print("   2. Verify embed players load correctly")
        print("   3. Test oEmbed functionality")
    else:
        print("\n⚠️  Some pipeline tests failed.")
        print("   Check error messages above for troubleshooting.")

if __name__ == "__main__":
    main()
