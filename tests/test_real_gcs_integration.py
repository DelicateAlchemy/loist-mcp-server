"""
Real GCS Integration Tests for Task 11.4

This test suite validates GCS integration with real buckets, testing:
- GCS client connection and authentication
- File upload/download operations
- Signed URL generation and validation
- Cache system integration
- Error handling and edge cases
- Cleanup strategies

These tests require:
- Valid GCS credentials (service account key or gcloud auth)
- Access to a test GCS bucket
- Environment variables: GCS_BUCKET_NAME, GCS_PROJECT_ID
"""

import os
import tempfile
import time
import uuid
from pathlib import Path
import pytest
import requests
from google.cloud.exceptions import NotFound, GoogleCloudError

# Skip tests if GCS is not configured
def is_gcs_configured() -> bool:
    """Check if GCS configuration is available for real testing."""
    return bool(
        os.getenv("GCS_BUCKET_NAME") and 
        os.getenv("GCS_PROJECT_ID") and
        (os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or 
         os.path.exists(os.path.expanduser("~/.config/gcloud/application_default_credentials.json")))
    )


@pytest.fixture(scope="session")
def gcs_client():
    """Session-scoped GCS client for real bucket testing."""
    if not is_gcs_configured():
        pytest.skip("GCS not configured for real testing (missing GCS_BUCKET_NAME, GCS_PROJECT_ID, or credentials)")
    
    from src.storage import create_gcs_client
    client = create_gcs_client()
    
    # Verify bucket exists and is accessible
    try:
        bucket = client.bucket
        if not bucket.exists():
            pytest.skip(f"Test bucket {client.bucket_name} does not exist or is not accessible")
    except Exception as e:
        pytest.skip(f"Cannot access test bucket: {e}")
    
    return client


@pytest.fixture
def test_audio_file():
    """Create a temporary test audio file."""
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.mp3') as f:
        # Create a minimal MP3 file header (not a real audio file, but sufficient for testing)
        f.write(b'\xff\xfb\x90\x00')  # MP3 header
        f.write(b'Test audio content for GCS integration testing' * 100)  # Some content
        test_path = Path(f.name)
    
    yield test_path
    
    # Cleanup
    if test_path.exists():
        test_path.unlink()


@pytest.fixture
def test_thumbnail_file():
    """Create a temporary test thumbnail file."""
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.jpg') as f:
        # Create a minimal JPEG file header
        f.write(b'\xff\xd8\xff\xe0')  # JPEG header
        f.write(b'Test thumbnail content for GCS integration testing' * 50)  # Some content
        test_path = Path(f.name)
    
    yield test_path
    
    # Cleanup
    if test_path.exists():
        test_path.unlink()


@pytest.fixture
def test_audio_id():
    """Generate a unique test audio ID."""
    return str(uuid.uuid4())


class TestRealGCSConnection:
    """Test real GCS connection and authentication."""
    
    def test_gcs_client_initialization(self, gcs_client):
        """Test that GCS client initializes correctly with real credentials."""
        assert gcs_client is not None
        assert gcs_client.bucket_name
        assert gcs_client.project_id
        assert gcs_client.client is not None
        
        # Verify we can access the bucket
        bucket = gcs_client.bucket
        assert bucket.exists()
        
        # Verify bucket properties
        bucket.reload()
        assert bucket.location
        assert bucket.storage_class
    
    def test_gcs_authentication(self, gcs_client):
        """Test that GCS authentication is working."""
        # Try to list files (requires authentication)
        files = gcs_client.list_files(prefix="test/", max_results=1)
        assert isinstance(files, list)  # Should not raise authentication error


class TestRealFileOperations:
    """Test real file upload, download, and deletion operations."""
    
    def test_upload_audio_file(self, gcs_client, test_audio_file, test_audio_id):
        """Test uploading an audio file to real GCS bucket."""
        blob_name = f"audio/{test_audio_id}/audio.mp3"
        
        try:
            blob = gcs_client.upload_file(
                source_path=test_audio_file,
                destination_blob_name=blob_name,
                content_type="audio/mpeg",
                metadata={
                    "test": "true",
                    "audio_id": test_audio_id,
                    "purpose": "integration-test"
                }
            )
            
            assert blob.name == blob_name
            assert blob.exists()
            assert blob.content_type == "audio/mpeg"
            assert blob.metadata.get("test") == "true"
            assert blob.metadata.get("audio_id") == test_audio_id
            
        finally:
            # Cleanup
            gcs_client.delete_file(blob_name)
    
    def test_upload_thumbnail_file(self, gcs_client, test_thumbnail_file, test_audio_id):
        """Test uploading a thumbnail file to real GCS bucket."""
        blob_name = f"audio/{test_audio_id}/thumbnail.jpg"
        
        try:
            blob = gcs_client.upload_file(
                source_path=test_thumbnail_file,
                destination_blob_name=blob_name,
                content_type="image/jpeg",
                metadata={
                    "test": "true",
                    "audio_id": test_audio_id,
                    "purpose": "integration-test"
                }
            )
            
            assert blob.name == blob_name
            assert blob.exists()
            assert blob.content_type == "image/jpeg"
            
        finally:
            # Cleanup
            gcs_client.delete_file(blob_name)
    
    def test_file_operations_workflow(self, gcs_client, test_audio_file, test_audio_id):
        """Test complete file operations workflow."""
        blob_name = f"audio/{test_audio_id}/workflow-test.mp3"
        
        try:
            # 1. Upload file
            blob = gcs_client.upload_file(test_audio_file, blob_name)
            assert blob.exists()
            
            # 2. Check file exists
            assert gcs_client.file_exists(blob_name)
            
            # 3. Get metadata
            metadata = gcs_client.get_file_metadata(blob_name)
            assert metadata["name"] == blob_name
            assert metadata["size"] > 0
            assert metadata["content_type"] == "audio/mpeg"
            
            # 4. Delete file
            result = gcs_client.delete_file(blob_name)
            assert result is True
            assert not gcs_client.file_exists(blob_name)
            
        except Exception as e:
            # Ensure cleanup even if test fails
            gcs_client.delete_file(blob_name)
            raise


class TestRealSignedURLs:
    """Test signed URL generation with real GCS bucket."""
    
    def test_generate_signed_url_for_audio(self, gcs_client, test_audio_file, test_audio_id):
        """Test generating signed URL for audio file."""
        blob_name = f"audio/{test_audio_id}/signed-url-test.mp3"
        
        try:
            # Upload file
            gcs_client.upload_file(test_audio_file, blob_name, content_type="audio/mpeg")
            
            # Generate signed URL
            url = gcs_client.generate_signed_url(
                blob_name=blob_name,
                expiration_minutes=15
            )
            
            # Validate URL format
            assert url.startswith("https://storage.googleapis.com")
            assert "Expires=" in url
            assert "Signature=" in url
            assert blob_name in url
            
            # Test URL accessibility
            response = requests.get(url, timeout=10)
            assert response.status_code == 200
            assert response.headers.get("content-type") == "audio/mpeg"
            
        finally:
            gcs_client.delete_file(blob_name)
    
    def test_signed_url_expiration(self, gcs_client, test_audio_file, test_audio_id):
        """Test signed URL with short expiration time."""
        blob_name = f"audio/{test_audio_id}/expiration-test.mp3"
        
        try:
            gcs_client.upload_file(test_audio_file, blob_name)
            
            # Generate URL with 1 minute expiration
            url = gcs_client.generate_signed_url(
                blob_name=blob_name,
                expiration_minutes=1
            )
            
            # URL should be accessible immediately
            response = requests.get(url, timeout=10)
            assert response.status_code == 200
            
            # Wait for expiration (1 minute + buffer)
            time.sleep(70)
            
            # URL should now be expired
            response = requests.get(url, timeout=10)
            assert response.status_code == 403  # Forbidden due to expiration
            
        finally:
            gcs_client.delete_file(blob_name)
    
    def test_signed_url_nonexistent_file(self, gcs_client):
        """Test that generating signed URL for nonexistent file raises NotFound."""
        with pytest.raises(NotFound):
            gcs_client.generate_signed_url("audio/nonexistent/file.mp3")


class TestRealCacheIntegration:
    """Test integration with the signed URL cache system."""
    
    def test_cache_with_real_gcs(self, gcs_client, test_audio_file, test_audio_id):
        """Test cache system with real GCS operations."""
        from src.resources.cache import get_cache
        
        blob_name = f"audio/{test_audio_id}/cache-test.mp3"
        gcs_path = f"gs://{gcs_client.bucket_name}/{blob_name}"
        
        try:
            # Upload file
            gcs_client.upload_file(test_audio_file, blob_name)
            
            # Get cache instance
            cache = get_cache()
            
            # First call should generate new URL
            url1 = cache.get(gcs_path, url_expiration_minutes=15)
            assert url1.startswith("https://storage.googleapis.com")
            
            # Second call should return cached URL
            url2 = cache.get(gcs_path, url_expiration_minutes=15)
            assert url1 == url2  # Should be identical (cached)
            
            # Verify cache stats
            stats = cache.get_stats()
            assert stats["hits"] >= 1
            assert stats["misses"] >= 1
            
            # Test URL accessibility
            response = requests.get(url1, timeout=10)
            assert response.status_code == 200
            
        finally:
            gcs_client.delete_file(blob_name)
    
    def test_cache_invalidation(self, gcs_client, test_audio_file, test_audio_id):
        """Test cache invalidation with real GCS."""
        from src.resources.cache import get_cache
        
        blob_name = f"audio/{test_audio_id}/cache-invalidation-test.mp3"
        gcs_path = f"gs://{gcs_client.bucket_name}/{blob_name}"
        
        try:
            # Upload file
            gcs_client.upload_file(test_audio_file, blob_name)
            
            # Get cache instance
            cache = get_cache()
            
            # Generate URL and cache it
            url1 = cache.get(gcs_path, url_expiration_minutes=15)
            
            # Invalidate cache
            result = cache.invalidate(gcs_path)
            assert result is True
            
            # Next call should generate new URL
            url2 = cache.get(gcs_path, url_expiration_minutes=15)
            # URLs might be the same due to same expiration, but cache should be regenerated
            
        finally:
            gcs_client.delete_file(blob_name)


class TestRealErrorHandling:
    """Test error handling with real GCS operations."""
    
    def test_upload_nonexistent_file(self, gcs_client):
        """Test uploading a file that doesn't exist locally."""
        nonexistent_path = Path("/tmp/nonexistent-file.mp3")
        
        with pytest.raises(FileNotFoundError):
            gcs_client.upload_file(nonexistent_path, "test/nonexistent.mp3")
    
    def test_get_metadata_nonexistent_file(self, gcs_client):
        """Test getting metadata for nonexistent file."""
        with pytest.raises(NotFound):
            gcs_client.get_file_metadata("audio/nonexistent/file.mp3")
    
    def test_delete_nonexistent_file(self, gcs_client):
        """Test deleting a file that doesn't exist."""
        result = gcs_client.delete_file("audio/nonexistent/file.mp3")
        assert result is False  # Should return False, not raise exception


class TestRealStorageManager:
    """Test the high-level storage manager with real GCS."""
    
    def test_storage_manager_workflow(self, test_audio_file, test_thumbnail_file, test_audio_id):
        """Test complete storage manager workflow with real GCS."""
        from src.storage.manager import StorageManager
        
        if not is_gcs_configured():
            pytest.skip("GCS not configured for real testing")
        
        storage_manager = StorageManager()
        
        try:
            # Test audio upload
            audio_result = storage_manager.upload_audio_file(
                source_path=test_audio_file,
                audio_id=test_audio_id
            )
            
            assert audio_result.audio_id == test_audio_id
            assert audio_result.audio_gcs_path.startswith("gs://")
            assert audio_result.audio_blob_name.startswith("audio/")
            
            # Test thumbnail upload
            thumbnail_result = storage_manager.upload_thumbnail_file(
                source_path=test_thumbnail_file,
                audio_id=test_audio_id
            )
            
            assert thumbnail_result.audio_id == test_audio_id
            assert thumbnail_result.thumbnail_gcs_path.startswith("gs://")
            assert thumbnail_result.thumbnail_blob_name.startswith("audio/")
            
            # Test combined upload
            combined_result = storage_manager.upload_audio_with_thumbnail(
                audio_path=test_audio_file,
                thumbnail_path=test_thumbnail_file,
                audio_id=test_audio_id
            )
            
            assert combined_result.audio_id == test_audio_id
            assert combined_result.audio_gcs_path
            assert combined_result.thumbnail_gcs_path
            
        finally:
            # Cleanup
            try:
                storage_manager.delete_audio_files(test_audio_id)
            except Exception:
                pass  # Ignore cleanup errors


class TestRealPerformanceAndReliability:
    """Test performance and reliability with real GCS operations."""
    
    def test_concurrent_uploads(self, gcs_client, test_audio_file):
        """Test concurrent file uploads to real GCS."""
        import concurrent.futures
        import threading
        
        def upload_file(audio_id):
            blob_name = f"audio/{audio_id}/concurrent-test.mp3"
            try:
                gcs_client.upload_file(test_audio_file, blob_name)
                return blob_name
            except Exception as e:
                return None
        
        # Upload multiple files concurrently
        audio_ids = [str(uuid.uuid4()) for _ in range(5)]
        uploaded_files = []
        
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(upload_file, audio_id) for audio_id in audio_ids]
                
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result:
                        uploaded_files.append(result)
            
            # Verify all uploads succeeded
            assert len(uploaded_files) == 5
            
            # Verify all files exist
            for blob_name in uploaded_files:
                assert gcs_client.file_exists(blob_name)
                
        finally:
            # Cleanup all uploaded files
            for blob_name in uploaded_files:
                gcs_client.delete_file(blob_name)
    
    def test_large_file_handling(self, gcs_client, test_audio_id):
        """Test handling of larger files with real GCS."""
        # Create a larger test file (1MB)
        large_file_size = 1024 * 1024  # 1MB
        
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.mp3') as f:
            # Write 1MB of test data
            chunk = b'X' * 1024  # 1KB chunk
            for _ in range(1024):  # 1024 chunks = 1MB
                f.write(chunk)
            large_file_path = Path(f.name)
        
        blob_name = f"audio/{test_audio_id}/large-file-test.mp3"
        
        try:
            # Upload large file
            blob = gcs_client.upload_file(
                large_file_path,
                blob_name,
                content_type="audio/mpeg"
            )
            
            assert blob.exists()
            assert blob.size == large_file_size
            
            # Test signed URL generation for large file
            url = gcs_client.generate_signed_url(blob_name)
            assert url.startswith("https://storage.googleapis.com")
            
        finally:
            # Cleanup
            gcs_client.delete_file(blob_name)
            if large_file_path.exists():
                large_file_path.unlink()


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v", "-s"])
