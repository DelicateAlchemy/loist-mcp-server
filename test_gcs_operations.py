#!/usr/bin/env python3
"""
Test script for GCS operations with real buckets.
Tests upload, signed URL generation, and retrieval operations.
"""

import os
import tempfile
from pathlib import Path
from src.storage.gcs_client import GCSClient, generate_signed_url
from src.storage.manager import AudioStorageManager

def test_gcs_operations():
    """Test GCS operations with real buckets."""
    print("🔍 Testing GCS operations with real buckets...")
    
    # Use staging bucket for testing
    bucket_name = "loist-music-library-bucket-staging"
    
    try:
        # Initialize GCS client
        print(f"📦 Initializing GCS client for bucket: {bucket_name}")
        gcs_client = GCSClient(bucket_name=bucket_name)
        print(f"✅ GCS client initialized successfully")
        
        # Test 1: List files in bucket
        print("\n📋 Testing file listing...")
        files = gcs_client.list_files(prefix="audio/")
        print(f"📁 Found {len(files)} files in audio/ directory")
        for file in files[:3]:  # Show first 3 files
            print(f"  - {file}")
        
        # Test 2: Upload a test file
        print("\n📤 Testing file upload...")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("This is a test file for GCS operations.\n")
            test_file_path = f.name
        
        destination_path = "test/test-file.txt"
        upload_result = gcs_client.upload_file(test_file_path, destination_path)
        print(f"✅ File uploaded successfully: {upload_result}")
        
        # Test 3: Generate signed URL
        print("\n🔗 Testing signed URL generation...")
        signed_url = gcs_client.generate_signed_url(destination_path, expiration_minutes=15)
        print(f"✅ Signed URL generated: {signed_url[:100]}...")
        
        # Test 4: Verify signed URL works (basic check)
        print("\n🔍 Testing signed URL accessibility...")
        import requests
        response = requests.head(signed_url, timeout=10)
        if response.status_code == 200:
            print("✅ Signed URL is accessible")
        else:
            print(f"⚠️  Signed URL returned status: {response.status_code}")
        
        # Test 5: Test storage manager
        print("\n🏗️  Testing AudioStorageManager...")
        storage_manager = AudioStorageManager(bucket_name=bucket_name)
        print("✅ AudioStorageManager initialized successfully")
        
        # Test 6: Clean up test file
        print("\n🧹 Cleaning up test file...")
        gcs_client.delete_file(destination_path)
        print("✅ Test file deleted successfully")
        
        # Clean up local test file
        os.unlink(test_file_path)
        
        print("\n🎉 All GCS operations completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ GCS operation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_gcs_operations()
    exit(0 if success else 1)
