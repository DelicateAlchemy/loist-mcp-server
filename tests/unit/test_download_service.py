"""
Unit tests for the download_service layer.

Mocks dependencies like the database, GCS, and converter to test the
service's business logic for preparing audio downloads.
"""

import pytest
from unittest.mock import patch, ANY, MagicMock

from src.services import download_service
from src.exceptions import ResourceNotFoundError
from src.converter import ConversionError

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db_metadata():
    """Mock database metadata for a track."""
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "title": "Test Title",
        "artist": "Test Artist",
        "audio_gcs_path": "gs://bucket/audio.mp3",
        "thumbnail_gcs_path": "gs://bucket/art.jpg",
    }

# ============================================================================
# Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.download_service.get_audio_metadata_by_id')
@patch('src.services.download_service.generate_signed_url')
async def test_prepare_download_redirect_case(mock_gen_url, mock_get_meta, mock_db_metadata):
    """Test the redirect case when target format matches source."""
    mock_get_meta.return_value = mock_db_metadata
    mock_gen_url.return_value = "http://redirect-url"
    
    action, data = await download_service.prepare_audio_download(
        "any_id", "mp3", "high"
    )
    
    mock_get_meta.assert_called_once_with("any_id")
    mock_gen_url.assert_called_once()
    assert action == "redirect"
    assert data["url"] == "http://redirect-url"

@pytest.mark.asyncio
@patch('src.services.download_service.get_audio_metadata_by_id')
@patch('src.services.download_service.download_audio_file')
@patch('src.services.download_service.convert_audio')
@patch('tempfile.mkdtemp')
async def test_prepare_download_stream_case(mock_mkdtemp, mock_convert, mock_download, mock_get_meta, mock_db_metadata):
    """Test the stream case when format conversion is needed."""
    mock_get_meta.return_value = mock_db_metadata
    mock_mkdtemp.return_value = "/tmp/testdir"
    
    # Mock the conversion result
    mock_conversion_result = MagicMock()
    mock_conversion_result.success = True
    mock_conversion_result.processing_time_seconds = 5.0
    mock_convert.return_value = mock_conversion_result

    # Mock the output file path stat
    with patch('pathlib.Path.stat') as mock_stat:
        mock_stat.return_value.st_size = 12345

        action, data = await download_service.prepare_audio_download(
            "any_id", "wav", "high"
        )
    
    mock_download.assert_called()
    mock_convert.assert_called_once()
    assert action == "stream"
    assert data["mime_type"] == "audio/wav"
    assert data["file_size"] == 12345
    assert data["download_filename"] == "Test Title - Test Artist.wav"

@pytest.mark.asyncio
@patch('src.services.download_service.get_audio_metadata_by_id')
async def test_prepare_download_not_found(mock_get_meta):
    """Test that ResourceNotFoundError is raised for a missing track."""
    mock_get_meta.return_value = None
    with pytest.raises(ResourceNotFoundError):
        await download_service.prepare_audio_download("not_found_id", "mp3")

@pytest.mark.asyncio
@patch('src.services.download_service.get_audio_metadata_by_id')
@patch('src.services.download_service.download_audio_file')
@patch('src.services.download_service.convert_audio')
@patch('tempfile.mkdtemp')
async def test_prepare_download_conversion_fails(mock_mkdtemp, mock_convert, mock_download, mock_get_meta, mock_db_metadata):
    """Test that ConversionError is propagated."""
    mock_get_meta.return_value = mock_db_metadata
    mock_mkdtemp.return_value = "/tmp/testdir"
    
    mock_conversion_result = MagicMock()
    mock_conversion_result.success = False
    mock_conversion_result.error_message = "ffmpeg error"
    mock_convert.return_value = mock_conversion_result

    with pytest.raises(ConversionError):
        await download_service.prepare_audio_download("any_id", "wav")

@pytest.mark.asyncio
@patch('src.services.download_service.Path')
async def test_cleanup_temp_directory(MockPath):
    """Test the cleanup utility function."""
    mock_dir = MagicMock()
    mock_file = MagicMock()
    mock_dir.iterdir.return_value = [mock_file]
    MockPath.return_value = mock_dir

    await download_service.cleanup_temp_directory("/tmp/testdir")

    mock_dir.iterdir.assert_called_once()
    mock_file.unlink.assert_called_once()
    mock_dir.rmdir.assert_called_once()
