#!/usr/bin/env python3
"""
Complete GCS + Embed Player Testing Script
Tests the full pipeline: audio processing → GCS upload → embed player → oEmbed
"""

import sys
import os
import asyncio
import json
import time
from pathlib import Path

# Test audio URL (temporary, will expire)
TEST_AUDIO_URL = "http://tmpfiles.org/dl/4845257/dcd082_07herotolerance.mp3"

def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'='*60}")
    print(f"🧪 {title}")
    print(f"{'='*60}")

def print_step(step, description):
    """Print a formatted step"""
    print(f"\n📋 Step {step}: {description}")
    print("-" * 40)

async def test_gcs_connection():
    """Test GCS connection and bucket access"""
    print_step(1, "Testing GCS Connection")
    
    try:
        from src.storage.gcs_client import create_gcs_client
        
        # Create GCS client
        client = create_gcs_client()
        print(f"✅ GCS client created for bucket: {client.bucket_name}")
        
        # Test bucket access
        bucket_exists = client.bucket.exists()
        if bucket_exists:
            print(f"✅ Bucket {client.bucket_name} exists and is accessible")
        else:
            print(f"❌ Bucket {client.bucket_name} not found or not accessible")
            return False
            
        # Test listing files (should be empty initially)
        files = client.list_files(prefix="audio/", max_results=5)
        print(f"📁 Found {len(files)} existing audio files in bucket")
        
        return True
        
    except Exception as e:
        print(f"❌ GCS connection failed: {e}")
        return False

async def test_audio_processing():
    """Test complete audio processing pipeline"""
    print_step(2, "Testing Audio Processing Pipeline")
    
    try:
        from src.tools.process_audio import process_audio_complete_sync
        
        print(f"🎵 Processing audio from: {TEST_AUDIO_URL}")
        
        # Process audio with GCS upload
        result = process_audio_complete_sync({
            'source': {
                'type': 'http_url', 
                'url': TEST_AUDIO_URL
            },
            'options': {
                'maxSizeMB': 100,
                'timeout': 300
            }
        })
        
        if result.get('success'):
            audio_id = result.get('track_id')
            print(f"✅ Audio processing successful!")
            print(f"   📝 Audio ID: {audio_id}")
            print(f"   🎵 Title: {result.get('metadata', {}).get('Product', {}).get('Title', 'Unknown')}")
            print(f"   🎤 Artist: {result.get('metadata', {}).get('Product', {}).get('Artist', 'Unknown')}")
            print(f"   ⏱️  Duration: {result.get('metadata', {}).get('Format', {}).get('Duration', 0):.1f}s")
            return audio_id
        else:
            print(f"❌ Audio processing failed: {result.get('error', 'Unknown error')}")
            return None
            
    except Exception as e:
        print(f"❌ Audio processing error: {e}")
        return None

async def test_embed_player(audio_id):
    """Test embed player functionality"""
    print_step(3, "Testing Embed Player")
    
    if not audio_id:
        print("❌ No audio ID provided for embed player test")
        return False
    
    try:
        import requests
        
        # Test embed page
        embed_url = f"http://localhost:8080/embed/{audio_id}"
        print(f"🌐 Testing embed page: {embed_url}")
        
        response = requests.get(embed_url, timeout=10)
        
        if response.status_code == 200:
            print("✅ Embed page loads successfully")
            
            # Check for key elements in HTML
            html_content = response.text
            
            checks = [
                ("HTML5 audio element", '<audio id="audio-player"'),
                ("Player controls", 'id="play-button"'),
                ("Progress bar", 'id="progress-container"'),
                ("Volume control", 'id="volume-slider"'),
                ("Social sharing", 'id="share-button"'),
                ("Open Graph tags", 'property="og:title"'),
                ("Twitter Card", 'name="twitter:card"'),
                ("oEmbed discovery", 'rel="alternate" type="application/json+oembed"')
            ]
            
            for check_name, check_string in checks:
                if check_string in html_content:
                    print(f"   ✅ {check_name}")
                else:
                    print(f"   ❌ {check_name} missing")
            
            return True
        else:
            print(f"❌ Embed page failed: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Embed player test failed: {e}")
        return False

async def test_oembed_functionality(audio_id):
    """Test oEmbed endpoint functionality"""
    print_step(4, "Testing oEmbed Functionality")
    
    if not audio_id:
        print("❌ No audio ID provided for oEmbed test")
        return False
    
    try:
        import requests
        
        # Test oEmbed discovery
        discovery_url = "http://localhost:8080/.well-known/oembed.json"
        print(f"🔍 Testing oEmbed discovery: {discovery_url}")
        
        response = requests.get(discovery_url, timeout=10)
        if response.status_code == 200:
            discovery_data = response.json()
            print("✅ oEmbed discovery endpoint working")
            print(f"   📝 Provider: {discovery_data.get('provider_name')}")
        else:
            print(f"❌ oEmbed discovery failed: HTTP {response.status_code}")
            return False
        
        # Test oEmbed endpoint
        embed_url = f"https://loist.io/embed/{audio_id}"
        oembed_url = f"http://localhost:8080/oembed?url={embed_url}"
        print(f"🔗 Testing oEmbed endpoint: {oembed_url}")
        
        response = requests.get(oembed_url, timeout=10)
        if response.status_code == 200:
            oembed_data = response.json()
            print("✅ oEmbed endpoint working")
            print(f"   📝 Title: {oembed_data.get('title')}")
            print(f"   🎤 Author: {oembed_data.get('author_name')}")
            print(f"   📐 Dimensions: {oembed_data.get('width')}x{oembed_data.get('height')}")
            print(f"   🖼️  Thumbnail: {'Yes' if oembed_data.get('thumbnail_url') else 'No'}")
            return True
        else:
            print(f"❌ oEmbed endpoint failed: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ oEmbed test failed: {e}")
        return False

async def test_gcs_signed_urls(audio_id):
    """Test GCS signed URL generation"""
    print_step(5, "Testing GCS Signed URLs")
    
    if not audio_id:
        print("❌ No audio ID provided for GCS test")
        return False
    
    try:
        from src.resources.cache import get_cache
        
        # Test cache/signed URL generation
        cache = get_cache()
        
        # Test audio stream URL
        audio_path = f"audio/{audio_id}/audio.mp3"  # Assuming this path structure
        try:
            stream_url = cache.get(audio_path, url_expiration_minutes=15)
            print(f"✅ Generated signed URL for audio stream")
            print(f"   🔗 URL: {stream_url[:100]}...")
            
            # Test URL accessibility
            import requests
            head_response = requests.head(stream_url, timeout=10)
            if head_response.status_code == 200:
                print(f"   ✅ Audio stream URL is accessible")
                print(f"   📊 Content-Type: {head_response.headers.get('content-type', 'Unknown')}")
                print(f"   📏 Content-Length: {head_response.headers.get('content-length', 'Unknown')} bytes")
            else:
                print(f"   ❌ Audio stream URL not accessible: HTTP {head_response.status_code}")
                
        except Exception as e:
            print(f"❌ Failed to generate signed URL: {e}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ GCS signed URL test failed: {e}")
        return False

async def test_database_integration(audio_id):
    """Test database integration"""
    print_step(6, "Testing Database Integration")
    
    if not audio_id:
        print("❌ No audio ID provided for database test")
        return False
    
    try:
        from database import get_audio_metadata_by_id
        
        # Test metadata retrieval
        metadata = get_audio_metadata_by_id(audio_id)
        
        if metadata:
            print("✅ Audio metadata found in database")
            print(f"   🎵 Title: {metadata.get('title', 'Unknown')}")
            print(f"   🎤 Artist: {metadata.get('artist', 'Unknown')}")
            print(f"   💿 Album: {metadata.get('album', 'Unknown')}")
            print(f"   📅 Year: {metadata.get('year', 'Unknown')}")
            print(f"   ⏱️  Duration: {metadata.get('duration', 0):.1f}s")
            print(f"   🎧 Format: {metadata.get('format', 'Unknown')}")
            print(f"   📁 Audio Path: {metadata.get('audio_gcs_path', 'Unknown')}")
            print(f"   🖼️  Thumbnail Path: {metadata.get('thumbnail_gcs_path', 'None')}")
            return True
        else:
            print("❌ Audio metadata not found in database")
            return False
            
    except Exception as e:
        print(f"❌ Database integration test failed: {e}")
        return False

async def main():
    """Run complete GCS + Embed Player test suite"""
    print_section("GCS + Embed Player Complete Test Suite")
    print(f"🎵 Test Audio: {TEST_AUDIO_URL}")
    print(f"⏰ Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test results tracking
    results = {}
    
    # Step 1: Test GCS connection
    results['gcs_connection'] = await test_gcs_connection()
    if not results['gcs_connection']:
        print("\n❌ GCS connection failed. Please check your configuration.")
        return
    
    # Step 2: Test audio processing
    audio_id = await test_audio_processing()
    results['audio_processing'] = audio_id is not None
    
    if not audio_id:
        print("\n❌ Audio processing failed. Cannot continue with remaining tests.")
        return
    
    # Step 3: Test database integration
    results['database_integration'] = await test_database_integration(audio_id)
    
    # Step 4: Test GCS signed URLs
    results['gcs_signed_urls'] = await test_gcs_signed_urls(audio_id)
    
    # Step 5: Test embed player
    results['embed_player'] = await test_embed_player(audio_id)
    
    # Step 6: Test oEmbed functionality
    results['oembed'] = await test_oembed_functionality(audio_id)
    
    # Summary
    print_section("Test Results Summary")
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    print(f"📊 Tests Passed: {passed}/{total}")
    print(f"🎵 Audio ID: {audio_id}")
    print(f"🌐 Embed URL: http://localhost:8080/embed/{audio_id}")
    print(f"🔗 oEmbed URL: http://localhost:8080/oembed?url=https://loist.io/embed/{audio_id}")
    
    print("\n📋 Detailed Results:")
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name}: {status}")
    
    if passed == total:
        print(f"\n🎉 All tests passed! Your GCS + Embed Player setup is working perfectly!")
        print(f"\n🚀 Next steps:")
        print(f"   1. Open embed player: http://localhost:8080/embed/{audio_id}")
        print(f"   2. Test oEmbed: http://localhost:8080/oembed?url=https://loist.io/embed/{audio_id}")
        print(f"   3. Share on social media to test Open Graph/Twitter Cards")
    else:
        print(f"\n⚠️  Some tests failed. Please check the error messages above.")
    
    print(f"\n⏰ Completed at: {time.strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    asyncio.run(main())
