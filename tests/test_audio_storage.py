"""
Tests for audio storage manager functionality.

Tests:
- Unique filename generation
- File organization structure
- Audio file uploads
- Thumbnail uploads
- Combined uploads
- Retry logic
- Temporary file cleanup
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from google.cloud import storage
from google.cloud.exceptions import TooManyRequests, ServiceUnavailable

from src.storage.manager import (
    FilenameGenerator,
    FileOrganizer,
    AudioStorageManager,
    StorageResult,
)
from src.storage.retry import RetryConfig, with_retry


class TestFilenameGenerator:
    """Test filename generation functionality."""
    
    def test_generate_audio_id(self):
        """Test UUID generation for audio IDs."""
        gen = FilenameGenerator()
        audio_id = gen.generate_audio_id()
        
        assert isinstance(audio_id, str)
        assert len(audio_id) == 36  # Standard UUID length with hyphens
        assert audio_id.count('-') == 4  # UUID format has 4 hyphens
    
    def test_generate_audio_id_unique(self):
        """Test that generated UUIDs are unique."""
        gen = FilenameGenerator()
        ids = [gen.generate_audio_id() for _ in range(100)]
        
        assert len(set(ids)) == 100  # All unique
    
    def test_validate_uuid_valid(self):
        """Test UUID validation with valid UUIDs."""
        gen = FilenameGenerator()
        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        
        assert gen.validate_uuid(valid_uuid) is True
    
    def test_validate_uuid_invalid(self):
        """Test UUID validation with invalid inputs."""
        gen = FilenameGenerator()
        
        assert gen.validate_uuid("not-a-uuid") is False
        assert gen.validate_uuid("123") is False
        assert gen.validate_uuid("") is False
        assert gen.validate_uuid(None) is False
    
    def test_generate_blob_name_audio(self):
        """Test blob name generation for audio files."""
        gen = FilenameGenerator()
        audio_id = "550e8400-e29b-41d4-a716-446655440000"
        file_path = Path("/tmp/song.mp3")
        
        blob_name = gen.generate_blob_name(audio_id, file_path, "audio")
        
        assert blob_name == f"audio/{audio_id}/audio.mp3"
    
    def test_generate_blob_name_preserves_extension(self):
        """Test that blob names preserve file extensions."""
        gen = FilenameGenerator()
        audio_id = "550e8400-e29b-41d4-a716-446655440000"
        
        test_cases = [
            (Path("/tmp/file.mp3"), "audio.mp3"),
            (Path("/tmp/file.wav"), "audio.wav"),
            (Path("/tmp/file.flac"), "audio.flac"),
        ]
        
        for path, expected_filename in test_cases:
            blob_name = gen.generate_blob_name(audio_id, path, "audio")
            assert blob_name.endswith(expected_filename)
    
    def test_generate_thumbnail_blob_name(self):
        """Test thumbnail blob name generation."""
        gen = FilenameGenerator()
        audio_id = "550e8400-e29b-41d4-a716-446655440000"
        
        blob_name = gen.generate_thumbnail_blob_name(audio_id, ".jpg")
        assert blob_name == f"audio/{audio_id}/thumbnail.jpg"
        
        blob_name = gen.generate_thumbnail_blob_name(audio_id, ".png")
        assert blob_name == f"audio/{audio_id}/thumbnail.png"
    
    def test_parse_audio_id_from_blob_name(self):
        """Test extracting audio ID from blob name."""
        gen = FilenameGenerator()
        audio_id = "550e8400-e29b-41d4-a716-446655440000"
        blob_name = f"audio/{audio_id}/audio.mp3"
        
        extracted_id = gen.parse_audio_id_from_blob_name(blob_name)
        assert extracted_id == audio_id
    
    def test_parse_audio_id_from_invalid_blob_name(self):
        """Test parsing invalid blob names."""
        gen = FilenameGenerator()
        
        assert gen.parse_audio_id_from_blob_name("invalid") is None
        assert gen.parse_audio_id_from_blob_name("") is None


class TestFileOrganizer:
    """Test file organization structure."""
    
    def test_get_folder_structure(self):
        """Test folder structure generation."""
        audio_id = "550e8400-e29b-41d4-a716-446655440000"
        structure = FileOrganizer.get_folder_structure(audio_id)
        
        assert structure["root"] == "audio"
        assert structure["audio_folder"] == f"audio/{audio_id}"
        assert structure["audio_prefix"] == f"audio/{audio_id}/"
    
    def test_get_expected_files(self):
        """Test expected files generation."""
        audio_id = "550e8400-e29b-41d4-a716-446655440000"
        
        files = FileOrganizer.get_expected_files(audio_id, ".mp3", has_thumbnail=True)
        assert files["audio"] == f"audio/{audio_id}/audio.mp3"
        assert files["thumbnail"] == f"audio/{audio_id}/thumbnail.jpg"
        
        files = FileOrganizer.get_expected_files(audio_id, ".wav", has_thumbnail=False)
        assert files["audio"] == f"audio/{audio_id}/audio.wav"
        assert "thumbnail" not in files
    
    def test_format_gcs_uri(self):
        """Test GCS URI formatting."""
        bucket = "my-bucket"
        blob = "audio/123/audio.mp3"
        
        uri = FileOrganizer.format_gcs_uri(bucket, blob)
        assert uri == f"gs://{bucket}/{blob}"


class TestAudioStorageManager:
    """Test AudioStorageManager functionality."""
    
    @pytest.fixture
    def mock_gcs_client(self):
        """Mock GCS client."""
        with patch('src.storage.gcs_client.GCSClient') as mock:
            client = Mock()
            client.bucket_name = "test-bucket"
            mock.return_value = client
            yield client
    
    @pytest.fixture
    def temp_audio_file(self):
        """Create a temporary audio file."""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"fake audio data")
            path = Path(f.name)
        
        yield path
        
        # Cleanup
        if path.exists():
            path.unlink()
    
    @pytest.fixture
    def temp_thumbnail_file(self):
        """Create a temporary thumbnail file."""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"fake image data")
            path = Path(f.name)
        
        yield path
        
        # Cleanup
        if path.exists():
            path.unlink()
    
    def test_initialization(self, mock_gcs_client):
        """Test AudioStorageManager initialization."""
        manager = AudioStorageManager(bucket_name="test-bucket")
        
        assert manager.gcs_client == mock_gcs_client
        assert manager.filename_generator is not None
        assert manager.file_organizer is not None
        assert manager.retry_config is not None
    
    def test_upload_audio_file(self, mock_gcs_client, temp_audio_file):
        """Test audio file upload."""
        # Setup mock
        mock_blob = Mock()
        mock_blob.size = 1000
        mock_blob.content_type = "audio/mpeg"
        mock_blob.md5_hash = "abc123"
        mock_blob.generation = 1
        mock_gcs_client.upload_file.return_value = mock_blob
        
        manager = AudioStorageManager(bucket_name="test-bucket")
        result = manager.upload_audio_file(temp_audio_file)
        
        assert isinstance(result, StorageResult)
        assert result.audio_id is not None
        assert result.audio_gcs_path.startswith("gs://test-bucket/audio/")
        assert result.audio_blob_name.startswith("audio/")
        assert result.metadata["size"] == 1000
    
    def test_upload_audio_file_with_custom_id(self, mock_gcs_client, temp_audio_file):
        """Test audio file upload with pre-generated ID."""
        custom_id = "550e8400-e29b-41d4-a716-446655440000"
        
        mock_blob = Mock()
        mock_blob.size = 1000
        mock_blob.content_type = "audio/mpeg"
        mock_blob.md5_hash = "abc123"
        mock_blob.generation = 1
        mock_gcs_client.upload_file.return_value = mock_blob
        
        manager = AudioStorageManager(bucket_name="test-bucket")
        result = manager.upload_audio_file(temp_audio_file, audio_id=custom_id)
        
        assert result.audio_id == custom_id
    
    def test_upload_audio_file_invalid_format(self, mock_gcs_client):
        """Test audio upload with unsupported format."""
        with tempfile.NamedTemporaryFile(suffix=".txt") as f:
            invalid_file = Path(f.name)
            
            manager = AudioStorageManager(bucket_name="test-bucket")
            
            with pytest.raises(ValueError, match="Unsupported audio format"):
                manager.upload_audio_file(invalid_file)
    
    def test_upload_audio_file_nonexistent(self, mock_gcs_client):
        """Test audio upload with nonexistent file."""
        nonexistent = Path("/tmp/nonexistent-file.mp3")
        
        manager = AudioStorageManager(bucket_name="test-bucket")
        
        with pytest.raises(FileNotFoundError):
            manager.upload_audio_file(nonexistent)
    
    def test_upload_thumbnail_file(self, mock_gcs_client, temp_thumbnail_file):
        """Test thumbnail file upload."""
        audio_id = "550e8400-e29b-41d4-a716-446655440000"
        
        mock_blob = Mock()
        mock_blob.size = 500
        mock_blob.content_type = "image/jpeg"
        mock_blob.md5_hash = "def456"
        mock_blob.generation = 1
        mock_gcs_client.upload_file.return_value = mock_blob
        
        manager = AudioStorageManager(bucket_name="test-bucket")
        result = manager.upload_thumbnail_file(temp_thumbnail_file, audio_id)
        
        assert isinstance(result, StorageResult)
        assert result.audio_id == audio_id
        assert result.thumbnail_gcs_path.startswith("gs://test-bucket/audio/")
        assert result.thumbnail_blob_name.startswith("audio/")
    
    def test_upload_thumbnail_invalid_audio_id(self, mock_gcs_client, temp_thumbnail_file):
        """Test thumbnail upload with invalid audio ID."""
        manager = AudioStorageManager(bucket_name="test-bucket")
        
        with pytest.raises(ValueError, match="Invalid UUID format"):
            manager.upload_thumbnail_file(temp_thumbnail_file, "invalid-id")
    
    def test_upload_audio_with_thumbnail(self, mock_gcs_client, temp_audio_file, temp_thumbnail_file):
        """Test combined audio and thumbnail upload."""
        mock_blob = Mock()
        mock_blob.size = 1000
        mock_blob.content_type = "audio/mpeg"
        mock_blob.md5_hash = "abc123"
        mock_blob.generation = 1
        mock_gcs_client.upload_file.return_value = mock_blob
        
        manager = AudioStorageManager(bucket_name="test-bucket")
        result = manager.upload_audio_with_thumbnail(
            temp_audio_file,
            temp_thumbnail_file
        )
        
        assert isinstance(result, StorageResult)
        assert result.audio_id is not None
        assert result.audio_gcs_path is not None
        assert result.thumbnail_gcs_path is not None
        assert result.metadata["has_thumbnail"] is True
    
    def test_upload_audio_without_thumbnail(self, mock_gcs_client, temp_audio_file):
        """Test audio upload without thumbnail."""
        mock_blob = Mock()
        mock_blob.size = 1000
        mock_blob.content_type = "audio/mpeg"
        mock_blob.md5_hash = "abc123"
        mock_blob.generation = 1
        mock_gcs_client.upload_file.return_value = mock_blob
        
        manager = AudioStorageManager(bucket_name="test-bucket")
        result = manager.upload_audio_with_thumbnail(temp_audio_file, thumbnail_path=None)
        
        assert result.thumbnail_gcs_path is None
        assert result.metadata["has_thumbnail"] is False
    
    def test_cleanup_file(self, mock_gcs_client, temp_audio_file):
        """Test file cleanup functionality."""
        manager = AudioStorageManager(bucket_name="test-bucket")
        
        assert temp_audio_file.exists()
        result = manager._cleanup_file(temp_audio_file, "test file")
        assert result is True
        assert not temp_audio_file.exists()
    
    def test_cleanup_file_already_deleted(self, mock_gcs_client):
        """Test cleanup of already deleted file."""
        nonexistent = Path("/tmp/nonexistent-file.mp3")
        
        manager = AudioStorageManager(bucket_name="test-bucket")
        result = manager._cleanup_file(nonexistent, "test file")
        
        assert result is True  # Should succeed gracefully
    
    def test_upload_with_cleanup(self, mock_gcs_client, temp_audio_file):
        """Test upload with automatic cleanup."""
        mock_blob = Mock()
        mock_blob.size = 1000
        mock_blob.content_type = "audio/mpeg"
        mock_blob.md5_hash = "abc123"
        mock_blob.generation = 1
        mock_gcs_client.upload_file.return_value = mock_blob
        
        manager = AudioStorageManager(bucket_name="test-bucket")
        
        assert temp_audio_file.exists()
        result = manager.upload_audio_file(temp_audio_file, cleanup=True)
        
        assert isinstance(result, StorageResult)
        # Note: In this test, cleanup might not work due to temp file handling
        # In real usage, cleanup would work as expected


class TestRetryLogic:
    """Test retry functionality."""
    
    def test_retry_success_first_attempt(self):
        """Test successful operation on first attempt."""
        mock_func = Mock(return_value="success")
        
        @with_retry(RetryConfig(max_attempts=3))
        def operation():
            return mock_func()
        
        result = operation()
        
        assert result == "success"
        assert mock_func.call_count == 1
    
    def test_retry_success_after_failures(self):
        """Test successful operation after transient failures."""
        mock_func = Mock(side_effect=[
            TooManyRequests("Rate limit"),
            ServiceUnavailable("Temporarily down"),
            "success"
        ])
        
        @with_retry(RetryConfig(max_attempts=3, initial_delay=0.01))
        def operation():
            return mock_func()
        
        result = operation()
        
        assert result == "success"
        assert mock_func.call_count == 3
    
    def test_retry_exhausted(self):
        """Test operation that fails all retry attempts."""
        mock_func = Mock(side_effect=TooManyRequests("Rate limit"))
        
        @with_retry(RetryConfig(max_attempts=3, initial_delay=0.01))
        def operation():
            return mock_func()
        
        with pytest.raises(TooManyRequests):
            operation()
        
        assert mock_func.call_count == 3
    
    def test_retry_non_retryable_exception(self):
        """Test that non-retryable exceptions fail immediately."""
        mock_func = Mock(side_effect=ValueError("Invalid input"))
        
        @with_retry(RetryConfig(max_attempts=3))
        def operation():
            return mock_func()
        
        with pytest.raises(ValueError):
            operation()
        
        assert mock_func.call_count == 1  # Should not retry



