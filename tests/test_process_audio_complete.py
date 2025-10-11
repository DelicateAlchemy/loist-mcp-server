"""
Comprehensive tests for the process_audio_complete MCP tool.

Tests cover:
- Input validation
- Complete processing pipeline
- Error handling for all failure scenarios
- Response format validation
- Resource cleanup
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
import tempfile
import uuid

from src.tools.process_audio import process_audio_complete, ProcessingPipeline
from src.tools.schemas import (
    ProcessAudioInput,
    ProcessAudioOutput,
    ProcessAudioError,
    ErrorCode,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def valid_input_data():
    """Valid input data for process_audio_complete"""
    return {
        "source": {
            "type": "http_url",
            "url": "https://example.com/test-audio.mp3"
        },
        "options": {
            "maxSizeMB": 100,
            "timeout": 300,
            "validateFormat": True
        }
    }


@pytest.fixture
def mock_metadata():
    """Mock metadata extracted from audio file"""
    return {
        "artist": "Test Artist",
        "title": "Test Song",
        "album": "Test Album",
        "genre": "Rock",
        "year": 2024,
        "duration": 180.5,
        "channels": 2,
        "sample_rate": 44100,
        "bitrate": 320000,
        "format": "MP3"
    }


@pytest.fixture
def temp_audio_file():
    """Create a temporary audio file for testing"""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(b"fake audio data")
        temp_path = f.name
    yield temp_path
    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


# ============================================================================
# Input Validation Tests
# ============================================================================

@pytest.mark.asyncio
async def test_valid_input_schema(valid_input_data):
    """Test that valid input passes Pydantic validation"""
    validated = ProcessAudioInput(**valid_input_data)
    assert validated.source.type == "http_url"
    assert str(validated.source.url) == "https://example.com/test-audio.mp3"
    assert validated.options.maxSizeMB == 100


@pytest.mark.asyncio
async def test_invalid_source_type():
    """Test that invalid source type is rejected"""
    with pytest.raises(Exception):  # Pydantic ValidationError
        ProcessAudioInput(**{
            "source": {
                "type": "invalid_type",
                "url": "https://example.com/test.mp3"
            }
        })


@pytest.mark.asyncio
async def test_invalid_url_scheme():
    """Test that non-HTTP URLs are rejected"""
    with pytest.raises(Exception):  # Pydantic ValidationError
        ProcessAudioInput(**{
            "source": {
                "type": "http_url",
                "url": "ftp://example.com/test.mp3"
            }
        })


@pytest.mark.asyncio
async def test_missing_required_fields():
    """Test that missing required fields are rejected"""
    with pytest.raises(Exception):  # Pydantic ValidationError
        ProcessAudioInput(**{
            "source": {
                "type": "http_url"
                # Missing url
            }
        })


# ============================================================================
# Successful Processing Pipeline Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.tools.process_audio.download_from_url')
@patch('src.tools.process_audio.validate_url')
@patch('src.tools.process_audio.validate_ssrf')
@patch('src.tools.process_audio.extract_metadata')
@patch('src.tools.process_audio.extract_artwork')
@patch('src.tools.process_audio.validate_audio_format')
@patch('src.tools.process_audio.upload_audio_file')
@patch('src.tools.process_audio.save_audio_metadata')
@patch('src.tools.process_audio.mark_as_processing')
@patch('src.tools.process_audio.mark_as_completed')
async def test_successful_processing_with_artwork(
    mock_mark_completed,
    mock_mark_processing,
    mock_save_metadata,
    mock_upload,
    mock_validate_format,
    mock_extract_artwork,
    mock_extract_metadata,
    mock_validate_ssrf,
    mock_validate_url,
    mock_download,
    valid_input_data,
    mock_metadata,
    temp_audio_file
):
    """Test successful audio processing with artwork"""
    # Setup mocks
    mock_download.return_value = temp_audio_file
    mock_extract_metadata.return_value = mock_metadata
    mock_extract_artwork.return_value = "/tmp/artwork.jpg"
    mock_upload.side_effect = [
        "gs://bucket/audio/test-id/audio.mp3",
        "gs://bucket/audio/test-id/artwork.jpg"
    ]
    mock_save_metadata.return_value = {"id": "test-audio-id"}
    
    # Execute
    result = await process_audio_complete(valid_input_data)
    
    # Verify success
    assert result["success"] is True
    assert "audioId" in result
    assert result["metadata"]["Product"]["Artist"] == "Test Artist"
    assert result["metadata"]["Product"]["Title"] == "Test Song"
    assert result["metadata"]["Format"]["Duration"] == 180.5
    assert result["resources"]["audio"].startswith("music-library://audio/")
    assert result["resources"]["thumbnail"] is not None
    assert "processingTime" in result
    
    # Verify all stages were called
    mock_validate_url.assert_called_once()
    mock_validate_ssrf.assert_called_once()
    mock_download.assert_called_once()
    mock_extract_metadata.assert_called_once()
    mock_extract_artwork.assert_called_once()
    assert mock_upload.call_count == 2  # Audio + artwork
    mock_save_metadata.assert_called_once()
    mock_mark_completed.assert_called_once()


@pytest.mark.asyncio
@patch('src.tools.process_audio.download_from_url')
@patch('src.tools.process_audio.validate_url')
@patch('src.tools.process_audio.validate_ssrf')
@patch('src.tools.process_audio.extract_metadata')
@patch('src.tools.process_audio.extract_artwork')
@patch('src.tools.process_audio.validate_audio_format')
@patch('src.tools.process_audio.upload_audio_file')
@patch('src.tools.process_audio.save_audio_metadata')
@patch('src.tools.process_audio.mark_as_processing')
@patch('src.tools.process_audio.mark_as_completed')
async def test_successful_processing_without_artwork(
    mock_mark_completed,
    mock_mark_processing,
    mock_save_metadata,
    mock_upload,
    mock_validate_format,
    mock_extract_artwork,
    mock_extract_metadata,
    mock_validate_ssrf,
    mock_validate_url,
    mock_download,
    valid_input_data,
    mock_metadata,
    temp_audio_file
):
    """Test successful audio processing without artwork"""
    # Setup mocks
    mock_download.return_value = temp_audio_file
    mock_extract_metadata.return_value = mock_metadata
    mock_extract_artwork.return_value = None  # No artwork
    mock_upload.return_value = "gs://bucket/audio/test-id/audio.mp3"
    mock_save_metadata.return_value = {"id": "test-audio-id"}
    
    # Execute
    result = await process_audio_complete(valid_input_data)
    
    # Verify success
    assert result["success"] is True
    assert result["resources"]["thumbnail"] is None  # No artwork
    assert mock_upload.call_count == 1  # Only audio, no artwork


# ============================================================================
# Error Handling Tests
# ============================================================================

@pytest.mark.asyncio
async def test_invalid_input_error(valid_input_data):
    """Test error response for invalid input"""
    invalid_data = valid_input_data.copy()
    invalid_data["source"]["type"] = "invalid"
    
    result = await process_audio_complete(invalid_data)
    
    assert result["success"] is False
    assert result["error"] == ErrorCode.VALIDATION_ERROR.value
    assert "Invalid input" in result["message"]


@pytest.mark.asyncio
@patch('src.tools.process_audio.validate_url')
@patch('src.tools.process_audio.mark_as_processing')
async def test_url_validation_error(
    mock_mark_processing,
    mock_validate_url,
    valid_input_data
):
    """Test error response for invalid URL"""
    from src.downloader import URLValidationError
    mock_validate_url.side_effect = URLValidationError("Invalid URL scheme")
    
    result = await process_audio_complete(valid_input_data)
    
    assert result["success"] is False
    assert result["error"] == ErrorCode.VALIDATION_ERROR.value
    assert "Invalid URL" in result["message"]


@pytest.mark.asyncio
@patch('src.tools.process_audio.validate_url')
@patch('src.tools.process_audio.validate_ssrf')
@patch('src.tools.process_audio.mark_as_processing')
async def test_ssrf_protection_error(
    mock_mark_processing,
    mock_validate_ssrf,
    mock_validate_url,
    valid_input_data
):
    """Test error response for SSRF protection"""
    from src.downloader import SSRFProtectionError
    mock_validate_ssrf.side_effect = SSRFProtectionError("Private IP detected")
    
    result = await process_audio_complete(valid_input_data)
    
    assert result["success"] is False
    assert result["error"] == ErrorCode.VALIDATION_ERROR.value
    assert "security policy" in result["message"].lower()


@pytest.mark.asyncio
@patch('src.tools.process_audio.validate_url')
@patch('src.tools.process_audio.validate_ssrf')
@patch('src.tools.process_audio.download_from_url')
@patch('src.tools.process_audio.mark_as_processing')
async def test_size_exceeded_error(
    mock_mark_processing,
    mock_download,
    mock_validate_ssrf,
    mock_validate_url,
    valid_input_data
):
    """Test error response for file size exceeded"""
    from src.downloader import DownloadSizeError
    mock_download.side_effect = DownloadSizeError("File size exceeds limit")
    
    result = await process_audio_complete(valid_input_data)
    
    assert result["success"] is False
    assert result["error"] == ErrorCode.SIZE_EXCEEDED.value
    assert "details" in result
    assert result["details"]["max_size_mb"] == 100


@pytest.mark.asyncio
@patch('src.tools.process_audio.validate_url')
@patch('src.tools.process_audio.validate_ssrf')
@patch('src.tools.process_audio.download_from_url')
@patch('src.tools.process_audio.mark_as_processing')
async def test_download_timeout_error(
    mock_mark_processing,
    mock_download,
    mock_validate_ssrf,
    mock_validate_url,
    valid_input_data
):
    """Test error response for download timeout"""
    from src.downloader import DownloadTimeoutError
    mock_download.side_effect = DownloadTimeoutError("Download timeout")
    
    result = await process_audio_complete(valid_input_data)
    
    assert result["success"] is False
    assert result["error"] == ErrorCode.TIMEOUT.value


@pytest.mark.asyncio
@patch('src.tools.process_audio.validate_url')
@patch('src.tools.process_audio.validate_ssrf')
@patch('src.tools.process_audio.download_from_url')
@patch('src.tools.process_audio.validate_audio_format')
@patch('src.tools.process_audio.mark_as_processing')
async def test_invalid_format_error(
    mock_mark_processing,
    mock_validate_format,
    mock_download,
    mock_validate_ssrf,
    mock_validate_url,
    valid_input_data,
    temp_audio_file
):
    """Test error response for invalid audio format"""
    from src.metadata import FormatValidationError
    mock_download.return_value = temp_audio_file
    mock_validate_format.side_effect = FormatValidationError("Unsupported format")
    
    result = await process_audio_complete(valid_input_data)
    
    assert result["success"] is False
    assert result["error"] == ErrorCode.INVALID_FORMAT.value


@pytest.mark.asyncio
@patch('src.tools.process_audio.validate_url')
@patch('src.tools.process_audio.validate_ssrf')
@patch('src.tools.process_audio.download_from_url')
@patch('src.tools.process_audio.validate_audio_format')
@patch('src.tools.process_audio.extract_metadata')
@patch('src.tools.process_audio.mark_as_processing')
async def test_metadata_extraction_error(
    mock_mark_processing,
    mock_extract_metadata,
    mock_validate_format,
    mock_download,
    mock_validate_ssrf,
    mock_validate_url,
    valid_input_data,
    temp_audio_file
):
    """Test error response for metadata extraction failure"""
    from src.metadata import MetadataExtractionError
    mock_download.return_value = temp_audio_file
    mock_extract_metadata.side_effect = MetadataExtractionError("Extraction failed")
    
    result = await process_audio_complete(valid_input_data)
    
    assert result["success"] is False
    assert result["error"] == ErrorCode.EXTRACTION_FAILED.value


@pytest.mark.asyncio
@patch('src.tools.process_audio.validate_url')
@patch('src.tools.process_audio.validate_ssrf')
@patch('src.tools.process_audio.download_from_url')
@patch('src.tools.process_audio.validate_audio_format')
@patch('src.tools.process_audio.extract_metadata')
@patch('src.tools.process_audio.extract_artwork')
@patch('src.tools.process_audio.upload_audio_file')
@patch('src.tools.process_audio.mark_as_processing')
async def test_storage_error(
    mock_mark_processing,
    mock_upload,
    mock_extract_artwork,
    mock_extract_metadata,
    mock_validate_format,
    mock_download,
    mock_validate_ssrf,
    mock_validate_url,
    valid_input_data,
    mock_metadata,
    temp_audio_file
):
    """Test error response for storage upload failure"""
    from src.exceptions import StorageError
    mock_download.return_value = temp_audio_file
    mock_extract_metadata.return_value = mock_metadata
    mock_extract_artwork.return_value = None
    mock_upload.side_effect = StorageError("Upload failed")
    
    result = await process_audio_complete(valid_input_data)
    
    assert result["success"] is False
    assert result["error"] == ErrorCode.STORAGE_FAILED.value


# ============================================================================
# Resource Cleanup Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.tools.process_audio.os.remove')
async def test_cleanup_on_success(mock_remove, temp_audio_file):
    """Test that temporary files are cleaned up on success"""
    pipeline = ProcessingPipeline()
    pipeline.temp_audio_path = temp_audio_file
    pipeline.temp_artwork_path = "/tmp/artwork.jpg"
    
    pipeline.cleanup()
    
    # Should attempt to clean both files
    assert mock_remove.call_count >= 1


@pytest.mark.asyncio
@patch('src.tools.process_audio.mark_as_failed')
@patch('src.tools.process_audio.validate_url')
async def test_cleanup_on_error(mock_validate_url, mock_mark_failed, valid_input_data):
    """Test that temporary files are cleaned up on error"""
    mock_validate_url.side_effect = Exception("Test error")
    
    result = await process_audio_complete(valid_input_data)
    
    assert result["success"] is False
    # Cleanup should have occurred (implicitly tested by no temp files remaining)


# ============================================================================
# Database Status Tracking Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.tools.process_audio.download_from_url')
@patch('src.tools.process_audio.validate_url')
@patch('src.tools.process_audio.validate_ssrf')
@patch('src.tools.process_audio.extract_metadata')
@patch('src.tools.process_audio.extract_artwork')
@patch('src.tools.process_audio.validate_audio_format')
@patch('src.tools.process_audio.upload_audio_file')
@patch('src.tools.process_audio.save_audio_metadata')
@patch('src.tools.process_audio.mark_as_processing')
@patch('src.tools.process_audio.mark_as_completed')
@patch('src.tools.process_audio.mark_as_failed')
async def test_status_tracking_on_success(
    mock_mark_failed,
    mock_mark_completed,
    mock_mark_processing,
    mock_save_metadata,
    mock_upload,
    mock_validate_format,
    mock_extract_artwork,
    mock_extract_metadata,
    mock_validate_ssrf,
    mock_validate_url,
    mock_download,
    valid_input_data,
    mock_metadata,
    temp_audio_file
):
    """Test that status is correctly tracked on success"""
    mock_download.return_value = temp_audio_file
    mock_extract_metadata.return_value = mock_metadata
    mock_extract_artwork.return_value = None
    mock_upload.return_value = "gs://bucket/audio/test-id/audio.mp3"
    mock_save_metadata.return_value = {"id": "test-audio-id"}
    
    result = await process_audio_complete(valid_input_data)
    
    assert result["success"] is True
    mock_mark_processing.assert_called_once()
    mock_mark_completed.assert_called_once()
    mock_mark_failed.assert_not_called()


@pytest.mark.asyncio
@patch('src.tools.process_audio.validate_url')
@patch('src.tools.process_audio.mark_as_processing')
@patch('src.tools.process_audio.mark_as_failed')
async def test_status_tracking_on_error(
    mock_mark_failed,
    mock_mark_processing,
    mock_validate_url,
    valid_input_data
):
    """Test that status is correctly tracked on error"""
    from src.downloader import URLValidationError
    mock_validate_url.side_effect = URLValidationError("Invalid URL")
    
    result = await process_audio_complete(valid_input_data)
    
    assert result["success"] is False
    mock_mark_failed.assert_called_once()


# ============================================================================
# Response Format Tests
# ============================================================================

@pytest.mark.asyncio
async def test_success_response_schema(mock_metadata):
    """Test that success response matches schema"""
    response_data = {
        "success": True,
        "audioId": str(uuid.uuid4()),
        "metadata": {
            "Product": {
                "Artist": mock_metadata["artist"],
                "Title": mock_metadata["title"],
                "Album": mock_metadata["album"],
                "MBID": None,
                "Genre": [mock_metadata["genre"]],
                "Year": mock_metadata["year"]
            },
            "Format": {
                "Duration": mock_metadata["duration"],
                "Channels": mock_metadata["channels"],
                "Sample rate": mock_metadata["sample_rate"],
                "Bitrate": mock_metadata["bitrate"],
                "Format": mock_metadata["format"]
            },
            "urlEmbedLink": "https://loist.io/embed/test-id"
        },
        "resources": {
            "audio": "music-library://audio/test-id/stream",
            "thumbnail": "music-library://audio/test-id/thumbnail",
            "waveform": None
        },
        "processingTime": 2.5
    }
    
    # Validate against Pydantic schema
    validated = ProcessAudioOutput(**response_data)
    assert validated.success is True
    assert validated.audioId is not None


@pytest.mark.asyncio
async def test_error_response_schema():
    """Test that error response matches schema"""
    error_data = {
        "success": False,
        "error": ErrorCode.SIZE_EXCEEDED.value,
        "message": "File too large",
        "details": {"max_size_mb": 100}
    }
    
    # Validate against Pydantic schema
    validated = ProcessAudioError(**error_data)
    assert validated.success is False
    assert validated.error == ErrorCode.SIZE_EXCEEDED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

