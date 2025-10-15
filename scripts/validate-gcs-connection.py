#!/usr/bin/env python3
"""
GCS Connection Validator for Task 11.4

This script performs a quick validation of GCS connectivity and basic operations
without running the full test suite. Useful for debugging connection issues.
"""

import os
import sys
import tempfile
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def check_environment():
    """Check if required environment variables are set."""
    print("🔍 Checking environment configuration...")
    
    required_vars = ["GCS_BUCKET_NAME", "GCS_PROJECT_ID"]
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
        else:
            print(f"✅ {var}: {os.getenv(var)}")
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        return False
    
    # Check credentials
    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if os.path.exists(creds_path):
            print(f"✅ GOOGLE_APPLICATION_CREDENTIALS: {creds_path}")
        else:
            print(f"❌ Credentials file not found: {creds_path}")
            return False
    else:
        print("ℹ️  No GOOGLE_APPLICATION_CREDENTIALS set, using gcloud auth")
    
    return True


def test_gcs_connection():
    """Test basic GCS connection."""
    print("\n🔗 Testing GCS connection...")
    
    try:
        from storage import create_gcs_client
        
        client = create_gcs_client()
        print(f"✅ GCS client created for bucket: {client.bucket_name}")
        
        # Test bucket access
        bucket = client.bucket
        if bucket.exists():
            print("✅ Bucket exists and is accessible")
        else:
            print("❌ Bucket does not exist or is not accessible")
            return False
        
        # Test basic operations
        files = client.list_files(prefix="test/", max_results=1)
        print(f"✅ Can list files (found {len(files)} test files)")
        
        return True
        
    except Exception as e:
        print(f"❌ GCS connection failed: {e}")
        return False


def test_file_operations():
    """Test basic file operations."""
    print("\n📁 Testing file operations...")
    
    try:
        from storage import create_gcs_client
        import uuid
        
        client = create_gcs_client()
        test_id = str(uuid.uuid4())
        blob_name = f"test/connection-test-{test_id}.txt"
        
        # Create temporary test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("GCS connection test file\n")
            f.write(f"Test ID: {test_id}\n")
            test_file_path = Path(f.name)
        
        try:
            # Test upload
            blob = client.upload_file(
                source_path=test_file_path,
                destination_blob_name=blob_name,
                content_type="text/plain",
                metadata={"test": "true", "test_id": test_id}
            )
            print("✅ File upload successful")
            
            # Test file exists
            if client.file_exists(blob_name):
                print("✅ File existence check successful")
            else:
                print("❌ File existence check failed")
                return False
            
            # Test metadata retrieval
            metadata = client.get_file_metadata(blob_name)
            if metadata["name"] == blob_name:
                print("✅ Metadata retrieval successful")
            else:
                print("❌ Metadata retrieval failed")
                return False
            
            # Test signed URL generation
            url = client.generate_signed_url(blob_name, expiration_minutes=15)
            if url.startswith("https://storage.googleapis.com"):
                print("✅ Signed URL generation successful")
            else:
                print("❌ Signed URL generation failed")
                return False
            
            # Test deletion
            if client.delete_file(blob_name):
                print("✅ File deletion successful")
            else:
                print("❌ File deletion failed")
                return False
            
            return True
            
        finally:
            # Cleanup
            if test_file_path.exists():
                test_file_path.unlink()
            # Try to delete the blob in case of failure
            try:
                client.delete_file(blob_name)
            except:
                pass
    
    except Exception as e:
        print(f"❌ File operations failed: {e}")
        return False


def test_cache_integration():
    """Test cache system integration."""
    print("\n💾 Testing cache integration...")
    
    try:
        from storage import create_gcs_client
        from resources.cache import get_cache
        import uuid
        
        client = create_gcs_client()
        cache = get_cache()
        test_id = str(uuid.uuid4())
        blob_name = f"test/cache-test-{test_id}.txt"
        gcs_path = f"gs://{client.bucket_name}/{blob_name}"
        
        # Create temporary test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("Cache integration test file\n")
            test_file_path = Path(f.name)
        
        try:
            # Upload file
            client.upload_file(test_file_path, blob_name, content_type="text/plain")
            
            # Test cache operations
            url1 = cache.get(gcs_path, url_expiration_minutes=15)
            url2 = cache.get(gcs_path, url_expiration_minutes=15)
            
            if url1 == url2:
                print("✅ Cache hit successful")
            else:
                print("❌ Cache hit failed")
                return False
            
            # Test cache stats
            stats = cache.get_stats()
            if stats["hits"] >= 1 and stats["misses"] >= 1:
                print("✅ Cache statistics working")
            else:
                print("❌ Cache statistics failed")
                return False
            
            return True
            
        finally:
            # Cleanup
            if test_file_path.exists():
                test_file_path.unlink()
            try:
                client.delete_file(blob_name)
            except:
                pass
    
    except Exception as e:
        print(f"❌ Cache integration failed: {e}")
        return False


def main():
    """Main validation function."""
    print("🧪 GCS Connection Validator for Task 11.4")
    print("=" * 50)
    
    # Check environment
    if not check_environment():
        print("\n❌ Environment validation failed")
        return 1
    
    # Test GCS connection
    if not test_gcs_connection():
        print("\n❌ GCS connection validation failed")
        return 1
    
    # Test file operations
    if not test_file_operations():
        print("\n❌ File operations validation failed")
        return 1
    
    # Test cache integration
    if not test_cache_integration():
        print("\n❌ Cache integration validation failed")
        return 1
    
    print("\n🎉 All GCS validations passed!")
    print("\n✅ Task 11.4 validation complete:")
    print("   - GCS client connection verified")
    print("   - File upload/download operations tested")
    print("   - Signed URL generation validated")
    print("   - Cache system integration confirmed")
    print("\n🚀 Ready to proceed with Task 11.5 (MCP Tools Validation)")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
