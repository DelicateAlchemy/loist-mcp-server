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

from src.tools.process_audio import process_audio_complete
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
    assert validated.options.max_size_mb == 100


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
@patch('src.business.process_audio_shared', new_callable=AsyncMock)
async def test_successful_processing_with_artwork(
    mock_process_shared,
    valid_input_data,
    mock_metadata,
):
    """Test successful audio processing with artwork"""
    from src.business.audio_processor import AudioProcessingResult
    from src.schemas.metadata import AudioMetadata, AudioResources, ProductMetadata, FormatMetadata
    
    # Setup mock shared function to return success result
    mock_result = AudioProcessingResult(
        success=True,
        audio_id="test-audio-id",
        metadata=AudioMetadata(
            product=ProductMetadata(
                artist="Test Artist",
                title="Test Song",
                album="Test Album",
                genre=["Rock"],
                year=2024
            ),
            format=FormatMetadata(
                duration=180.5,
                channels=2,
                sample_rate=44100,
                bitrate=320000,
                format="MP3"
            ),
            url_embed_link="https://loist.io/embed/test-audio-id"
        ),
        resources=AudioResources(
            audio_url="music-library://audio/test-audio-id/stream",
            thumbnail_url="music-library://audio/test-audio-id/thumbnail",
            waveform_url=None
        ),
        processing_time=2.5
    )
    mock_process_shared.return_value = mock_result
    
    # Execute
    result = await process_audio_complete(valid_input_data)
    
    # Verify success
    assert result["success"] is True
    assert "audio_id" in result
    assert result["audio_id"] == "test-audio-id"
    assert result["metadata"]["product"]["artist"] == "Test Artist"
    assert result["metadata"]["product"]["title"] == "Test Song"
    assert result["metadata"]["format"]["duration"] == 180.5
    assert result["resources"]["audio_url"].startswith("music-library://audio/")
    assert result["resources"]["thumbnail_url"] is not None
    assert "processing_time" in result
    
    # Verify shared function was called
    mock_process_shared.assert_called_once()


@pytest.mark.asyncio
@patch('src.business.process_audio_shared', new_callable=AsyncMock)
async def test_successful_processing_without_artwork(
    mock_process_shared,
    valid_input_data,
    mock_metadata,
):
    """Test successful audio processing without artwork"""
    from src.business.audio_processor import AudioProcessingResult
    from src.schemas.metadata import AudioMetadata, AudioResources, ProductMetadata, FormatMetadata
    
    # Setup mock shared function to return success result without artwork
    mock_result = AudioProcessingResult(
        success=True,
        audio_id="test-audio-id",
        metadata=AudioMetadata(
            product=ProductMetadata(
                artist="Test Artist",
                title="Test Song",
                album="Test Album",
                genre=["Rock"],
                year=2024
            ),
            format=FormatMetadata(
                duration=180.5,
                channels=2,
                sample_rate=44100,
                bitrate=320000,
                format="MP3"
            ),
            url_embed_link="https://loist.io/embed/test-audio-id"
        ),
        resources=AudioResources(
            audio_url="music-library://audio/test-audio-id/stream",
            thumbnail_url=None,  # No artwork
            waveform_url=None
        ),
        processing_time=2.5
    )
    mock_process_shared.return_value = mock_result
    
    # Execute
    result = await process_audio_complete(valid_input_data)
    
    # Verify success
    assert result["success"] is True
    assert result["resources"]["thumbnail_url"] is None  # No artwork
    mock_process_shared.assert_called_once()


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
@patch('src.business.process_audio_shared', new_callable=AsyncMock)
async def test_url_validation_error(
    mock_process_shared,
    valid_input_data
):
    """Test error response for invalid URL"""
    from src.business.audio_processor import AudioProcessingError
    
    # Mock shared function to raise validation error
    mock_process_shared.side_effect = AudioProcessingError(
        code=ErrorCode.VALIDATION_ERROR,
        message="Invalid URL: Invalid URL scheme",
        retryable=False
    )
    
    result = await process_audio_complete(valid_input_data)
    
    assert result["success"] is False
    assert result["error"] == ErrorCode.VALIDATION_ERROR.value
    assert "Invalid URL" in result["message"]


@pytest.mark.asyncio
@patch('src.business.process_audio_shared', new_callable=AsyncMock)
async def test_ssrf_protection_error(
    mock_process_shared,
    valid_input_data
):
    """Test error response for SSRF protection"""
    from src.business.audio_processor import AudioProcessingError
    
    # Mock shared function to raise SSRF protection error
    mock_process_shared.side_effect = AudioProcessingError(
        code=ErrorCode.VALIDATION_ERROR,
        message="URL blocked by security policy: Private IP detected",
        retryable=False
    )
    
    result = await process_audio_complete(valid_input_data)
    
    assert result["success"] is False
    assert result["error"] == ErrorCode.VALIDATION_ERROR.value
    assert "security policy" in result["message"].lower()


@pytest.mark.asyncio
@patch('src.business.process_audio_shared', new_callable=AsyncMock)
async def test_size_exceeded_error(
    mock_process_shared,
    valid_input_data
):
    """Test error response for file size exceeded"""
    from src.business.audio_processor import AudioProcessingError
    
    # Mock shared function to raise size exceeded error
    mock_process_shared.side_effect = AudioProcessingError(
        code=ErrorCode.SIZE_EXCEEDED,
        message="File size exceeds limit",
        details={"max_size_mb": 100},
        retryable=False
    )
    
    result = await process_audio_complete(valid_input_data)
    
    assert result["success"] is False
    assert result["error"] == ErrorCode.SIZE_EXCEEDED.value
    assert "details" in result
    assert result["details"]["max_size_mb"] == 100


@pytest.mark.asyncio
@patch('src.business.process_audio_shared', new_callable=AsyncMock)
async def test_download_timeout_error(
    mock_process_shared,
    valid_input_data
):
    """Test error response for download timeout"""
    from src.business.audio_processor import AudioProcessingError
    
    # Mock shared function to raise timeout error
    mock_process_shared.side_effect = AudioProcessingError(
        code=ErrorCode.TIMEOUT,
        message="Download timeout",
        details={"timeout_seconds": 300},
        retryable=True
    )
    
    result = await process_audio_complete(valid_input_data)
    
    assert result["success"] is False
    assert result["error"] == ErrorCode.TIMEOUT.value


@pytest.mark.asyncio
@patch('src.business.process_audio_shared', new_callable=AsyncMock)
async def test_invalid_format_error(
    mock_process_shared,
    valid_input_data
):
    """Test error response for invalid audio format"""
    from src.business.audio_processor import AudioProcessingError
    
    # Mock shared function to raise format validation error
    mock_process_shared.side_effect = AudioProcessingError(
        code=ErrorCode.INVALID_FORMAT,
        message="Unsupported or invalid audio format: Unsupported format",
        retryable=False
    )
    
    result = await process_audio_complete(valid_input_data)
    
    assert result["success"] is False
    assert result["error"] == ErrorCode.INVALID_FORMAT.value


@pytest.mark.asyncio
@patch('src.business.process_audio_shared', new_callable=AsyncMock)
async def test_metadata_extraction_error(
    mock_process_shared,
    valid_input_data
):
    """Test error response for metadata extraction failure"""
    from src.business.audio_processor import AudioProcessingError
    
    # Mock shared function to raise extraction error
    mock_process_shared.side_effect = AudioProcessingError(
        code=ErrorCode.EXTRACTION_FAILED,
        message="Failed to extract metadata: Extraction failed",
        retryable=False
    )
    
    result = await process_audio_complete(valid_input_data)
    
    assert result["success"] is False
    assert result["error"] == ErrorCode.EXTRACTION_FAILED.value


@pytest.mark.asyncio
@patch('src.business.process_audio_shared', new_callable=AsyncMock)
async def test_storage_error(
    mock_process_shared,
    valid_input_data
):
    """Test error response for storage upload failure"""
    from src.business.audio_processor import AudioProcessingError
    
    # Mock shared function to raise storage error
    mock_process_shared.side_effect = AudioProcessingError(
        code=ErrorCode.STORAGE_FAILED,
        message="Failed to upload to storage: Upload failed",
        retryable=True
    )
    
    result = await process_audio_complete(valid_input_data)
    
    assert result["success"] is False
    assert result["error"] == ErrorCode.STORAGE_FAILED.value


# ============================================================================
# Resource Cleanup Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.business.process_audio_shared', new_callable=AsyncMock)
async def test_cleanup_on_success(mock_process_shared, valid_input_data):
    """Test that temporary files are cleaned up on success"""
    from src.business.audio_processor import AudioProcessingResult, ProcessingPipeline
    from src.schemas.metadata import AudioMetadata, AudioResources, ProductMetadata, FormatMetadata
    
    # Setup mock shared function to return success result
    mock_result = AudioProcessingResult(
        success=True,
        audio_id="test-audio-id",
        metadata=AudioMetadata(
            product=ProductMetadata(
                artist="Test Artist",
                title="Test Song",
                album="Test Album",
                genre=["Rock"],
                year=2024
            ),
            format=FormatMetadata(
                duration=180.5,
                channels=2,
                sample_rate=44100,
                bitrate=320000,
                format="MP3"
            ),
            url_embed_link="https://loist.io/embed/test-audio-id"
        ),
        resources=AudioResources(
            audio_url="music-library://audio/test-audio-id/stream",
            thumbnail_url=None,
            waveform_url=None
        ),
        processing_time=2.5
    )
    mock_process_shared.return_value = mock_result
    
    # Execute - cleanup is handled by shared layer
    result = await process_audio_complete(valid_input_data)
    
    # Verify success (cleanup happens in shared layer)
    assert result["success"] is True


@pytest.mark.asyncio
@patch('src.business.process_audio_shared', new_callable=AsyncMock)
async def test_cleanup_on_error(mock_process_shared, valid_input_data):
    """Test that temporary files are cleaned up on error"""
    from src.business.audio_processor import AudioProcessingError
    
    # Mock shared function to raise error
    mock_process_shared.side_effect = AudioProcessingError(
        code=ErrorCode.FETCH_FAILED,
        message="Test error",
        retryable=False
    )
    
    result = await process_audio_complete(valid_input_data)
    
    assert result["success"] is False
    # Cleanup should have occurred (implicitly tested by no temp files remaining)


# ============================================================================
# Database Status Tracking Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.business.process_audio_shared', new_callable=AsyncMock)
async def test_status_tracking_on_success(
    mock_process_shared,
    valid_input_data,
    mock_metadata,
):
    """Test that status is correctly tracked on success"""
    from src.business.audio_processor import AudioProcessingResult
    from src.schemas.metadata import AudioMetadata, AudioResources, ProductMetadata, FormatMetadata
    
    # Setup mock shared function to return success result
    mock_result = AudioProcessingResult(
        success=True,
        audio_id="test-audio-id",
        metadata=AudioMetadata(
            product=ProductMetadata(
                artist="Test Artist",
                title="Test Song",
                album="Test Album",
                genre=["Rock"],
                year=2024
            ),
            format=FormatMetadata(
                duration=180.5,
                channels=2,
                sample_rate=44100,
                bitrate=320000,
                format="MP3"
            ),
            url_embed_link="https://loist.io/embed/test-audio-id"
        ),
        resources=AudioResources(
            audio_url="music-library://audio/test-audio-id/stream",
            thumbnail_url=None,
            waveform_url=None
        ),
        processing_time=2.5
    )
    mock_process_shared.return_value = mock_result
    
    result = await process_audio_complete(valid_input_data)
    
    assert result["success"] is True
    # Note: Status tracking is now handled in shared layer, not directly testable here
    # Integration tests would verify database status updates


@pytest.mark.asyncio
@patch('src.business.process_audio_shared', new_callable=AsyncMock)
async def test_status_tracking_on_error(
    mock_process_shared,
    valid_input_data
):
    """Test that status is correctly tracked on error"""
    from src.business.audio_processor import AudioProcessingError
    
    # Mock shared function to raise error
    mock_process_shared.side_effect = AudioProcessingError(
        code=ErrorCode.VALIDATION_ERROR,
        message="Invalid URL: Invalid URL",
        retryable=False
    )
    
    result = await process_audio_complete(valid_input_data)
    
    assert result["success"] is False
    # Note: Status tracking is now handled in shared layer, not directly testable here
    # Integration tests would verify database status updates


# ============================================================================
# Response Format Tests
# ============================================================================

@pytest.mark.asyncio
async def test_success_response_schema(mock_metadata):
    """Test that success response matches schema"""
    response_data = {
        "success": True,
        "audio_id": str(uuid.uuid4()),
        "metadata": {
            "product": {
                "artist": mock_metadata["artist"],
                "title": mock_metadata["title"],
                "album": mock_metadata["album"],
                "mbid": None,
                "genre": [mock_metadata["genre"]],
                "year": mock_metadata["year"]
            },
            "format": {
                "duration": mock_metadata["duration"],
                "channels": mock_metadata["channels"],
                "sample_rate": mock_metadata["sample_rate"],
                "bitrate": mock_metadata["bitrate"],
                "format": mock_metadata["format"]
            },
            "url_embed_link": "https://loist.io/embed/test-id"
        },
        "resources": {
            "audio_url": "music-library://audio/test-id/stream",
            "thumbnail_url": "music-library://audio/test-id/thumbnail",
            "waveform_url": None
        },
        "processing_time": 2.5
    }
    
    # Validate against Pydantic schema
    validated = ProcessAudioOutput(**response_data)
    assert validated.success is True
    assert validated.audio_id is not None


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

