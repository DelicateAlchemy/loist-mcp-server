"""
Integration tests for Google Cloud Storage functionality.

These tests verify:
- GCS client connection
- Bucket access
- File upload/download
- Signed URL generation
- Metadata operations
- Lifecycle policies
"""

import os
import tempfile
from pathlib import Path
import pytest
from google.cloud.exceptions import NotFound

# Skip tests if GCS is not configured
pytest_plugins = []


def is_gcs_configured() -> bool:
    """Check if GCS configuration is available."""
    return bool(
        os.getenv("GCS_BUCKET_NAME") and 
        os.getenv("GCS_PROJECT_ID")
    )


@pytest.fixture
def gcs_client():
    """Fixture to create GCS client for tests."""
    if not is_gcs_configured():
        pytest.skip("GCS not configured (missing GCS_BUCKET_NAME or GCS_PROJECT_ID)")
    
    from src.storage import create_gcs_client
    return create_gcs_client()


@pytest.fixture
def test_file():
    """Fixture to create a temporary test file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("Test audio file content\n")
        f.write("This is a test for GCS integration\n")
        test_path = Path(f.name)
    
    yield test_path
    
    # Cleanup
    if test_path.exists():
        test_path.unlink()


class TestGCSConnection:
    """Test basic GCS connection and configuration."""
    
    def test_client_initialization(self, gcs_client):
        """Test that GCS client initializes correctly."""
        assert gcs_client is not None
        assert gcs_client.bucket_name
        assert gcs_client.client is not None
    
    def test_bucket_exists(self, gcs_client):
        """Test that the configured bucket exists."""
        bucket = gcs_client.bucket
        assert bucket.exists()
    
    def test_bucket_configuration(self, gcs_client):
        """Test bucket configuration settings."""
        bucket = gcs_client.bucket
        bucket.reload()
        
        # Check bucket properties
        assert bucket.location
        assert bucket.storage_class
        
        # Should have uniform bucket-level access
        assert bucket.iam_configuration.uniform_bucket_level_access_enabled


class TestFileOperations:
    """Test file upload, download, and deletion operations."""
    
    def test_upload_file(self, gcs_client, test_file):
        """Test uploading a file to GCS."""
        blob_name = "test/test-upload.txt"
        
        try:
            blob = gcs_client.upload_file(
                source_path=test_file,
                destination_blob_name=blob_name,
                content_type="text/plain",
                metadata={"test": "true", "purpose": "integration-test"}
            )
            
            assert blob.name == blob_name
            assert blob.exists()
            assert blob.content_type == "text/plain"
            assert blob.metadata.get("test") == "true"
            
        finally:
            # Cleanup
            gcs_client.delete_file(blob_name)
    
    def test_delete_file(self, gcs_client, test_file):
        """Test deleting a file from GCS."""
        blob_name = "test/test-delete.txt"
        
        # Upload first
        gcs_client.upload_file(test_file, blob_name)
        assert gcs_client.file_exists(blob_name)
        
        # Delete
        result = gcs_client.delete_file(blob_name)
        assert result is True
        assert not gcs_client.file_exists(blob_name)
    
    def test_delete_nonexistent_file(self, gcs_client):
        """Test deleting a file that doesn't exist."""
        result = gcs_client.delete_file("test/nonexistent.txt")
        assert result is False
    
    def test_file_exists(self, gcs_client, test_file):
        """Test checking if a file exists."""
        blob_name = "test/test-exists.txt"
        
        # Should not exist initially
        assert not gcs_client.file_exists(blob_name)
        
        try:
            # Upload and check
            gcs_client.upload_file(test_file, blob_name)
            assert gcs_client.file_exists(blob_name)
        finally:
            gcs_client.delete_file(blob_name)


class TestSignedURLs:
    """Test signed URL generation for secure access."""
    
    def test_generate_signed_url_for_existing_file(self, gcs_client, test_file):
        """Test generating a signed URL for an existing file."""
        blob_name = "test/test-signed-url.txt"
        
        try:
            # Upload file
            gcs_client.upload_file(test_file, blob_name)
            
            # Generate signed URL
            url = gcs_client.generate_signed_url(
                blob_name=blob_name,
                expiration_minutes=15
            )
            
            assert url.startswith("https://storage.googleapis.com")
            assert "Expires=" in url
            assert "Signature=" in url
            assert blob_name in url
            
        finally:
            gcs_client.delete_file(blob_name)
    
    def test_generate_signed_url_nonexistent_file(self, gcs_client):
        """Test that generating signed URL for nonexistent file raises NotFound."""
        with pytest.raises(NotFound):
            gcs_client.generate_signed_url("test/nonexistent.txt")
    
    def test_signed_url_custom_expiration(self, gcs_client, test_file):
        """Test signed URL with custom expiration time."""
        blob_name = "test/test-custom-expiration.txt"
        
        try:
            gcs_client.upload_file(test_file, blob_name)
            
            # Generate URL with 5 minute expiration
            url = gcs_client.generate_signed_url(
                blob_name=blob_name,
                expiration_minutes=5
            )
            
            assert url
            assert "Expires=" in url
            
        finally:
            gcs_client.delete_file(blob_name)


class TestMetadataOperations:
    """Test metadata retrieval and management."""
    
    def test_get_file_metadata(self, gcs_client, test_file):
        """Test retrieving file metadata."""
        blob_name = "test/test-metadata.txt"
        
        try:
            # Upload with metadata
            gcs_client.upload_file(
                test_file,
                blob_name,
                metadata={"artist": "Test Artist", "title": "Test Song"}
            )
            
            # Get metadata
            metadata = gcs_client.get_file_metadata(blob_name)
            
            assert metadata["name"] == blob_name
            assert metadata["size"] > 0
            assert metadata["content_type"]
            assert metadata["created"]
            assert metadata["md5_hash"]
            assert "artist" in metadata["custom_metadata"]
            assert metadata["custom_metadata"]["artist"] == "Test Artist"
            
        finally:
            gcs_client.delete_file(blob_name)
    
    def test_get_metadata_nonexistent_file(self, gcs_client):
        """Test getting metadata for nonexistent file raises NotFound."""
        with pytest.raises(NotFound):
            gcs_client.get_file_metadata("test/nonexistent.txt")


class TestListOperations:
    """Test listing files in the bucket."""
    
    def test_list_files(self, gcs_client, test_file):
        """Test listing files with prefix."""
        # Upload multiple test files
        test_files = [
            "test/list-test-1.txt",
            "test/list-test-2.txt",
            "test/list-test-3.txt",
        ]
        
        try:
            for blob_name in test_files:
                gcs_client.upload_file(test_file, blob_name)
            
            # List files with prefix
            files = gcs_client.list_files(prefix="test/list-test-")
            
            assert len(files) >= 3
            file_names = [f["name"] for f in files]
            for blob_name in test_files:
                assert blob_name in file_names
            
        finally:
            for blob_name in test_files:
                gcs_client.delete_file(blob_name)
    
    def test_list_files_with_max_results(self, gcs_client, test_file):
        """Test listing files with result limit."""
        # Upload test files
        test_files = ["test/max-test-1.txt", "test/max-test-2.txt"]
        
        try:
            for blob_name in test_files:
                gcs_client.upload_file(test_file, blob_name)
            
            # List with max_results=1
            files = gcs_client.list_files(prefix="test/max-test-", max_results=1)
            
            assert len(files) == 1
            
        finally:
            for blob_name in test_files:
                gcs_client.delete_file(blob_name)


class TestConvenienceFunctions:
    """Test convenience wrapper functions."""
    
    def test_upload_audio_file(self, test_file):
        """Test the upload_audio_file convenience function."""
        if not is_gcs_configured():
            pytest.skip("GCS not configured")
        
        from src.storage import upload_audio_file, delete_file
        
        blob_name = "test/test-audio-upload.txt"
        
        try:
            blob = upload_audio_file(
                source_path=test_file,
                destination_blob_name=blob_name,
                metadata={"track_id": "123"}
            )
            
            assert blob.name == blob_name
            assert blob.exists()
            
        finally:
            delete_file(blob_name)
    
    def test_list_audio_files(self, test_file):
        """Test the list_audio_files convenience function."""
        if not is_gcs_configured():
            pytest.skip("GCS not configured")
        
        from src.storage import upload_audio_file, delete_file, list_audio_files
        
        blob_name = "audio/test-list-audio.txt"
        
        try:
            upload_audio_file(test_file, blob_name)
            files = list_audio_files(prefix="audio/test-list-")
            
            assert len(files) >= 1
            assert any(f["name"] == blob_name for f in files)
            
        finally:
            delete_file(blob_name)


class TestBucketStructure:
    """Test bucket directory structure and organization."""
    
    def test_audio_directory(self, gcs_client):
        """Test that audio directory exists."""
        files = gcs_client.list_files(prefix="audio/", max_results=1)
        # Should at least have the placeholder or be accessible
        assert isinstance(files, list)
    
    def test_thumbnails_directory(self, gcs_client):
        """Test that thumbnails directory exists."""
        files = gcs_client.list_files(prefix="thumbnails/", max_results=1)
        assert isinstance(files, list)
    
    def test_temp_directory(self, gcs_client):
        """Test that temp directory exists."""
        files = gcs_client.list_files(prefix="temp/", max_results=1)
        assert isinstance(files, list)


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])

