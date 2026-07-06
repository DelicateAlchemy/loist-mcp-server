"""
Unit tests for the streaming_service layer.

Tests the logic for generating signed URLs for streams and thumbnails,
including the underlying caching mechanism.
"""

import pytest
from unittest.mock import patch, ANY

from src.services import streaming_service
from src.exceptions import ResourceNotFoundError

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db_metadata():
    """Mock database metadata for a track with audio and thumbnail."""
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "format": "MP3",
        "audio_gcs_path": "gs://bucket/audio.mp3",
        "thumbnail_gcs_path": "gs://bucket/art.jpg",
    }

@pytest.fixture
def mock_db_metadata_no_thumb():
    """Mock database metadata for a track without a thumbnail."""
    return {
        "id": "550e8400-e29b-41d4-a716-446655440001",
        "format": "WAV",
        "audio_gcs_path": "gs://bucket/audio.wav",
        "thumbnail_gcs_path": None,
    }

# ============================================================================
# Cache Tests (moved from test_resources.py)
# ============================================================================

def test_cache_initialization():
    """Test that the cache initializes correctly."""
    # We test the internal class, not the global get_cache() singleton
    cache = streaming_service._SignedURLCache()
    assert cache.default_ttl > 0
    assert len(cache.cache) == 0

@patch('src.services.streaming_service.generate_signed_url')
def test_cache_hit_and_miss(mock_generate_url):
    """Test cache hit and miss logic."""
    mock_generate_url.return_value = "http://signed-url"
    cache = streaming_service._SignedURLCache()
    
    # First call is a miss
    url1 = cache.get("gs://bucket/file")
    assert mock_generate_url.call_count == 1
    assert cache.misses == 1
    assert cache.hits == 0
    assert url1 == "http://signed-url"
    
    # Second call is a hit
    url2 = cache.get("gs://bucket/file")
    assert mock_generate_url.call_count == 1 # Not called again
    assert cache.misses == 1
    assert cache.hits == 1
    assert url2 == url1

@patch('src.services.streaming_service.generate_signed_url')
def test_cache_expiration(mock_generate_url):
    """Test that cache entries expire correctly (deterministic mocked clock)."""
    mock_generate_url.return_value = "http://signed-url"
    cache = streaming_service._SignedURLCache(default_ttl=100)

    with patch('src.services.streaming_service.time.time') as mock_time:
        # Entry cached at t=1000 with TTL 100 -> expires at t=1100
        mock_time.return_value = 1000.0
        cache.get("gs://bucket/file")
        assert mock_generate_url.call_count == 1

        # Just before expiry: still served from cache
        mock_time.return_value = 1099.0
        cache.get("gs://bucket/file")
        assert mock_generate_url.call_count == 1

        # After expiry: regenerated
        mock_time.return_value = 1101.0
        cache.get("gs://bucket/file")
        assert mock_generate_url.call_count == 2 # Called again after expiration

# ============================================================================
# get_audio_stream_details Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.streaming_service.get_audio_metadata_by_id')
@patch('src.services.streaming_service.get_cache')
async def test_get_audio_stream_details_success(mock_get_cache, mock_get_metadata, mock_db_metadata):
    """Test successful retrieval of audio stream details."""
    mock_get_metadata.return_value = mock_db_metadata
    mock_cache_instance = mock_get_cache.return_value
    mock_cache_instance.get.return_value = "http://signed-url/audio.mp3"
    
    result = await streaming_service.get_audio_stream_details("any_id")
    
    mock_get_metadata.assert_called_once_with("any_id")
    mock_cache_instance.get.assert_called_once_with(gcs_path="gs://bucket/audio.mp3", url_expiration_minutes=15)
    assert result["signed_url"] == "http://signed-url/audio.mp3"
    assert result["mime_type"] == "audio/mpeg"

@pytest.mark.asyncio
@patch('src.services.streaming_service.get_audio_metadata_by_id')
async def test_get_audio_stream_details_not_found(mock_get_metadata):
    """Test ResourceNotFoundError when track is missing."""
    mock_get_metadata.return_value = None
    with pytest.raises(ResourceNotFoundError):
        await streaming_service.get_audio_stream_details("not_found_id")

@pytest.mark.asyncio
@patch('src.services.streaming_service.get_audio_metadata_by_id')
async def test_get_audio_stream_details_no_path(mock_get_metadata):
    """Test ResourceNotFoundError when audio path is missing."""
    mock_get_metadata.return_value = {"id": "id", "audio_gcs_path": None}
    with pytest.raises(ResourceNotFoundError):
        await streaming_service.get_audio_stream_details("id_no_path")

# ============================================================================
# get_thumbnail_details Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.streaming_service.get_audio_metadata_by_id')
@patch('src.services.streaming_service.get_cache')
async def test_get_thumbnail_details_success(mock_get_cache, mock_get_metadata, mock_db_metadata):
    """Test successful retrieval of thumbnail details."""
    mock_get_metadata.return_value = mock_db_metadata
    mock_cache_instance = mock_get_cache.return_value
    mock_cache_instance.get.return_value = "http://signed-url/art.jpg"
    
    result = await streaming_service.get_thumbnail_details("any_id")
    
    mock_get_metadata.assert_called_once_with("any_id")
    mock_cache_instance.get.assert_called_once_with(gcs_path="gs://bucket/art.jpg", url_expiration_minutes=15)
    assert result["signed_url"] == "http://signed-url/art.jpg"
    assert result["mime_type"] == "image/jpeg"

@pytest.mark.asyncio
@patch('src.services.streaming_service.get_audio_metadata_by_id')
async def test_get_thumbnail_details_not_found(mock_get_metadata, mock_db_metadata_no_thumb):
    """Test ResourceNotFoundError when thumbnail is missing."""
    mock_get_metadata.return_value = mock_db_metadata_no_thumb
    with pytest.raises(ResourceNotFoundError):
        await streaming_service.get_thumbnail_details("id_no_thumb")
