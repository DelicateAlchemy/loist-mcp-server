#!/usr/bin/env python3
"""
Simple GCS + Embed Player Test
Tests basic functionality without complex async handling
"""

import sys
import os
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, 'src')

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

def test_gcs_connection():
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

def test_database_connection():
    """Test database connection"""
    print_step(2, "Testing Database Connection")
    
    try:
        from database.pool import get_connection_pool
        
        pool = get_connection_pool()
        health = pool.health_check()
        
        if health['healthy']:
            print("✅ Database connection successful")
            print(f"   📊 Active connections: {health.get('active_connections', 'Unknown')}")
            print(f"   📊 Pool size: {health.get('pool_size', 'Unknown')}")
            return True
        else:
            print(f"❌ Database health check failed: {health}")
            return False
            
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def test_audio_download():
    """Test basic audio download functionality"""
    print_step(3, "Testing Audio Download")
    
    try:
        from src.downloader import download_from_url
        import tempfile
        
        print(f"🎵 Downloading audio from: {TEST_AUDIO_URL}")
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            # Download the file
            result = download_from_url(TEST_AUDIO_URL, temp_path)
            
            if result['success']:
                file_size = os.path.getsize(temp_path)
                print(f"✅ Audio download successful!")
                print(f"   📁 File: {temp_path}")
                print(f"   📏 Size: {file_size:,} bytes")
                print(f"   🎵 Duration: {result.get('duration', 'Unknown')}s")
                return temp_path
            else:
                print(f"❌ Audio download failed: {result.get('error', 'Unknown error')}")
                return None
                
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                
    except Exception as e:
        print(f"❌ Audio download test failed: {e}")
        return None

def test_gcs_upload():
    """Test GCS file upload"""
    print_step(4, "Testing GCS Upload")
    
    try:
        from src.storage.gcs_client import create_gcs_client
        import tempfile
        import uuid
        
        # Create a test file
        test_content = b"Test audio content for GCS upload"
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            temp_file.write(test_content)
            temp_path = temp_file.name
        
        try:
            # Create GCS client and upload
            client = create_gcs_client()
            test_blob_name = f"test/audio-{uuid.uuid4()}.mp3"
            
            blob = client.upload_file(
                source_path=temp_path,
                destination_blob_name=test_blob_name,
                content_type="audio/mpeg"
            )
            
            print(f"✅ GCS upload successful!")
            print(f"   📁 Blob: {test_blob_name}")
            print(f"   📏 Size: {blob.size} bytes")
            print(f"   🔗 URL: gs://{client.bucket_name}/{test_blob_name}")
            
            # Test file existence
            if client.file_exists(test_blob_name):
                print(f"   ✅ File exists in GCS")
            else:
                print(f"   ❌ File not found in GCS")
            
            # Clean up test file
            client.delete_file(test_blob_name)
            print(f"   🗑️  Test file cleaned up")
            
            return True
            
        finally:
            # Clean up local temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                
    except Exception as e:
        print(f"❌ GCS upload test failed: {e}")
        return False

def test_server_health():
    """Test if MCP server is running"""
    print_step(5, "Testing Server Health")
    
    try:
        import requests
        
        # Test health endpoint
        health_url = "http://localhost:8080/health"
        print(f"🌐 Testing server health: {health_url}")
        
        response = requests.get(health_url, timeout=5)
        
        if response.status_code == 200:
            health_data = response.json()
            print("✅ Server is running and healthy")
            print(f"   📝 Service: {health_data.get('service', 'Unknown')}")
            print(f"   📝 Version: {health_data.get('version', 'Unknown')}")
            print(f"   📝 Status: {health_data.get('status', 'Unknown')}")
            return True
        else:
            print(f"❌ Server health check failed: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Server not running - start with: docker-compose up mcp-server")
        return False
    except Exception as e:
        print(f"❌ Server health test failed: {e}")
        return False

def main():
    """Run simple GCS + Embed Player test suite"""
    print_section("GCS + Embed Player Simple Test Suite")
    print(f"🎵 Test Audio: {TEST_AUDIO_URL}")
    print(f"⏰ Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test results tracking
    results = {}
    
    # Step 1: Test GCS connection
    results['gcs_connection'] = test_gcs_connection()
    
    # Step 2: Test database connection
    results['database_connection'] = test_database_connection()
    
    # Step 3: Test audio download
    results['audio_download'] = test_audio_download() is not None
    
    # Step 4: Test GCS upload
    results['gcs_upload'] = test_gcs_upload()
    
    # Step 5: Test server health
    results['server_health'] = test_server_health()
    
    # Summary
    print_section("Test Results Summary")
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    print(f"📊 Tests Passed: {passed}/{total}")
    
    print("\n📋 Detailed Results:")
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name}: {status}")
    
    if passed == total:
        print(f"\n🎉 All basic tests passed! Your GCS setup is working!")
        print(f"\n🚀 Next steps:")
        print(f"   1. Start the MCP server: docker-compose up mcp-server")
        print(f"   2. Test the embed player with a real audio file")
        print(f"   3. Test oEmbed functionality")
    else:
        print(f"\n⚠️  Some tests failed. Please check the error messages above.")
        if not results['gcs_connection']:
            print(f"   💡 Fix GCS: Check bucket permissions and service account")
        if not results['database_connection']:
            print(f"   💡 Fix Database: Start PostgreSQL with docker-compose up postgres")
        if not results['server_health']:
            print(f"   💡 Fix Server: Start MCP server with docker-compose up mcp-server")
    
    print(f"\n⏰ Completed at: {time.strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
