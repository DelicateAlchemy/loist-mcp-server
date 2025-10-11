"""
Comprehensive tests for MCP resource handlers.

Tests cover:
- Audio stream resource with signed URLs
- Metadata resource with JSON responses
- Thumbnail resource with caching
- Signed URL cache functionality
- Error handling for all scenarios
- URI parsing and validation
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import time

from src.resources.audio_stream import (
    get_audio_stream_resource,
    parse_gcs_path,
    get_content_headers_for_audio,
)
from src.resources.metadata import get_metadata_resource
from src.resources.thumbnail import (
    get_thumbnail_resource,
    get_content_headers_for_thumbnail,
)
from src.resources.cache import SignedURLCache
from src.exceptions import ResourceNotFoundError, ValidationError


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_audio_metadata():
    """Mock database metadata for audio track"""
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "artist": "The Beatles",
        "title": "Hey Jude",
        "album": "Hey Jude",
        "genre": "Rock",
        "year": 1968,
        "duration": 431.0,
        "channels": 2,
        "sample_rate": 44100,
        "bitrate": 320000,
        "format": "MP3",
        "audio_path": "gs://music-library/audio/550e8400/audio.mp3",
        "thumbnail_path": "gs://music-library/audio/550e8400/artwork.jpg",
        "status": "COMPLETED"
    }


# ============================================================================
# Signed URL Cache Tests
# ============================================================================

def test_cache_initialization():
    """Test cache initializes with correct defaults"""
    cache = SignedURLCache()
    assert cache.default_ttl == 810  # 13.5 minutes
    assert len(cache.cache) == 0
    assert cache.hits == 0
    assert cache.misses == 0


def test_cache_hit():
    """Test cache hit scenario"""
    cache = SignedURLCache()
    
    with patch('src.resources.cache.generate_signed_url') as mock_gen_url:
        mock_gen_url.return_value = "https://storage.googleapis.com/bucket/file?sig=abc"
        
        # First call - cache miss
        url1 = cache.get("gs://bucket/file")
        assert cache.misses == 1
        assert cache.hits == 0
        
        # Second call - cache hit
        url2 = cache.get("gs://bucket/file")
        assert cache.misses == 1
        assert cache.hits == 1
        assert url1 == url2
        
        # Should only call generate_signed_url once
        assert mock_gen_url.call_count == 1


def test_cache_expiration():
    """Test that cache entries expire"""
    cache = SignedURLCache(default_ttl=1)  # 1 second TTL
    
    with patch('src.resources.cache.generate_signed_url') as mock_gen_url:
        mock_gen_url.return_value = "https://storage.googleapis.com/bucket/file?sig=abc"
        
        # First call
        url1 = cache.get("gs://bucket/file", url_expiration_minutes=1)
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Second call - should regenerate (expired)
        url2 = cache.get("gs://bucket/file", url_expiration_minutes=1)
        
        assert cache.misses == 2  # Both were misses
        assert mock_gen_url.call_count == 2


def test_cache_invalidate():
    """Test manual cache invalidation"""
    cache = SignedURLCache()
    
    with patch('src.resources.cache.generate_signed_url') as mock_gen_url:
        mock_gen_url.return_value = "https://storage.googleapis.com/bucket/file?sig=abc"
        
        # Add to cache
        cache.get("gs://bucket/file")
        assert len(cache.cache) == 1
        
        # Invalidate
        result = cache.invalidate("gs://bucket/file")
        assert result is True
        assert len(cache.cache) == 0
        
        # Invalidate non-existent
        result = cache.invalidate("gs://bucket/nonexistent")
        assert result is False


def test_cache_clear():
    """Test clearing entire cache"""
    cache = SignedURLCache()
    
    with patch('src.resources.cache.generate_signed_url') as mock_gen_url:
        mock_gen_url.return_value = "https://storage.googleapis.com/bucket/file?sig=abc"
        
        # Add multiple entries
        cache.get("gs://bucket/file1")
        cache.get("gs://bucket/file2")
        cache.get("gs://bucket/file3")
        assert len(cache.cache) == 3
        
        # Clear all
        cache.clear()
        assert len(cache.cache) == 0


def test_cache_stats():
    """Test cache statistics tracking"""
    cache = SignedURLCache()
    
    with patch('src.resources.cache.generate_signed_url') as mock_gen_url:
        mock_gen_url.return_value = "https://storage.googleapis.com/bucket/file?sig=abc"
        
        # Generate some traffic
        cache.get("gs://bucket/file1")  # Miss
        cache.get("gs://bucket/file1")  # Hit
        cache.get("gs://bucket/file2")  # Miss
        cache.get("gs://bucket/file1")  # Hit
        
        stats = cache.get_stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 2
        assert stats["total_requests"] == 4
        assert stats["hit_rate_percent"] == 50.0
        assert stats["size"] == 2


# ============================================================================
# Audio Stream Resource Tests
# ============================================================================

def test_parse_gcs_path_valid():
    """Test parsing valid GCS paths"""
    bucket, blob = parse_gcs_path("gs://my-bucket/path/to/file.mp3")
    assert bucket == "my-bucket"
    assert blob == "path/to/file.mp3"


def test_parse_gcs_path_invalid():
    """Test invalid GCS paths raise errors"""
    with pytest.raises(ValueError, match="Invalid GCS path"):
        parse_gcs_path("https://example.com/file.mp3")
    
    with pytest.raises(ValueError, match="Invalid GCS path format"):
        parse_gcs_path("gs://bucket-only")


@pytest.mark.asyncio
@patch('src.resources.audio_stream.get_audio_metadata_by_id')
@patch('src.resources.audio_stream.get_cache')
async def test_audio_stream_success(mock_get_cache, mock_get_metadata, mock_audio_metadata):
    """Test successful audio stream resource retrieval"""
    mock_get_metadata.return_value = mock_audio_metadata
    
    # Mock cache
    mock_cache = Mock()
    mock_cache.get.return_value = "https://storage.googleapis.com/signed-url"
    mock_get_cache.return_value = mock_cache
    
    uri = "music-library://audio/550e8400-e29b-41d4-a716-446655440000/stream"
    response = await get_audio_stream_resource(uri)
    
    assert response["uri"] == "https://storage.googleapis.com/signed-url"
    assert response["mimeType"] == "audio/mpeg"  # MP3
    assert mock_cache.get.called


@pytest.mark.asyncio
@patch('src.resources.audio_stream.get_audio_metadata_by_id')
async def test_audio_stream_not_found(mock_get_metadata):
    """Test audio stream resource with non-existent audioId"""
    mock_get_metadata.return_value = None
    
    uri = "music-library://audio/00000000-0000-0000-0000-000000000000/stream"
    
    with pytest.raises(ResourceNotFoundError):
        await get_audio_stream_resource(uri)


@pytest.mark.asyncio
async def test_audio_stream_invalid_uri():
    """Test audio stream resource with invalid URI format"""
    uri = "invalid://uri/format"
    
    with pytest.raises(ValidationError, match="Invalid URI format"):
        await get_audio_stream_resource(uri)


def test_audio_headers():
    """Test audio streaming headers"""
    headers = get_content_headers_for_audio("MP3", support_ranges=True)
    
    assert headers["Content-Type"] == "audio/mpeg"
    assert headers["Accept-Ranges"] == "bytes"
    assert "Access-Control-Allow-Origin" in headers


# ============================================================================
# Metadata Resource Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.resources.metadata.get_audio_metadata_by_id')
async def test_metadata_resource_success(mock_get_metadata, mock_audio_metadata):
    """Test successful metadata resource retrieval"""
    mock_get_metadata.return_value = mock_audio_metadata
    
    uri = "music-library://audio/550e8400-e29b-41d4-a716-446655440000/metadata"
    response = await get_metadata_resource(uri)
    
    assert response["mimeType"] == "application/json"
    assert response["text"] is not None
    assert "The Beatles" in response["text"]
    assert "Hey Jude" in response["text"]


@pytest.mark.asyncio
@patch('src.resources.metadata.get_audio_metadata_by_id')
async def test_metadata_resource_not_found(mock_get_metadata):
    """Test metadata resource with non-existent audioId"""
    mock_get_metadata.return_value = None
    
    uri = "music-library://audio/00000000-0000-0000-0000-000000000000/metadata"
    
    with pytest.raises(ResourceNotFoundError):
        await get_metadata_resource(uri)


@pytest.mark.asyncio
async def test_metadata_resource_invalid_uri():
    """Test metadata resource with invalid URI format"""
    uri = "invalid://uri/format"
    
    with pytest.raises(ValidationError):
        await get_metadata_resource(uri)


# ============================================================================
# Thumbnail Resource Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.resources.thumbnail.get_audio_metadata_by_id')
@patch('src.resources.thumbnail.get_cache')
async def test_thumbnail_resource_success(mock_get_cache, mock_get_metadata, mock_audio_metadata):
    """Test successful thumbnail resource retrieval"""
    mock_get_metadata.return_value = mock_audio_metadata
    
    # Mock cache
    mock_cache = Mock()
    mock_cache.get.return_value = "https://storage.googleapis.com/thumbnail-signed-url"
    mock_get_cache.return_value = mock_cache
    
    uri = "music-library://audio/550e8400-e29b-41d4-a716-446655440000/thumbnail"
    response = await get_thumbnail_resource(uri)
    
    assert response["uri"] == "https://storage.googleapis.com/thumbnail-signed-url"
    assert response["mimeType"] == "image/jpeg"
    assert mock_cache.get.called


@pytest.mark.asyncio
@patch('src.resources.thumbnail.get_audio_metadata_by_id')
async def test_thumbnail_resource_no_thumbnail(mock_get_metadata, mock_audio_metadata):
    """Test thumbnail resource when audio has no thumbnail"""
    mock_audio_metadata["thumbnail_path"] = None
    mock_get_metadata.return_value = mock_audio_metadata
    
    uri = "music-library://audio/550e8400-e29b-41d4-a716-446655440000/thumbnail"
    
    with pytest.raises(ResourceNotFoundError, match="Thumbnail not available"):
        await get_thumbnail_resource(uri)


@pytest.mark.asyncio
@patch('src.resources.thumbnail.get_audio_metadata_by_id')
async def test_thumbnail_resource_not_found(mock_get_metadata):
    """Test thumbnail resource with non-existent audioId"""
    mock_get_metadata.return_value = None
    
    uri = "music-library://audio/00000000-0000-0000-0000-000000000000/thumbnail"
    
    with pytest.raises(ResourceNotFoundError):
        await get_thumbnail_resource(uri)


def test_thumbnail_headers():
    """Test thumbnail image headers"""
    headers = get_content_headers_for_thumbnail()
    
    assert headers["Content-Type"] == "image/jpeg"
    assert "Cache-Control" in headers
    assert "Access-Control-Allow-Origin" in headers


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.resources.audio_stream.get_audio_metadata_by_id')
@patch('src.resources.metadata.get_audio_metadata_by_id')
@patch('src.resources.thumbnail.get_audio_metadata_by_id')
@patch('src.resources.audio_stream.get_cache')
@patch('src.resources.thumbnail.get_cache')
async def test_all_resources_for_track(
    mock_thumb_cache,
    mock_audio_cache,
    mock_thumb_metadata,
    mock_meta_metadata,
    mock_audio_metadata,
    mock_audio_metadata
):
    """Test accessing all resources for a single track"""
    # Setup mocks
    mock_audio_metadata.return_value = mock_audio_metadata
    mock_meta_metadata.return_value = mock_audio_metadata
    mock_thumb_metadata.return_value = mock_audio_metadata
    
    mock_cache = Mock()
    mock_cache.get.return_value = "https://storage.googleapis.com/signed-url"
    mock_audio_cache.return_value = mock_cache
    mock_thumb_cache.return_value = mock_cache
    
    audio_id = "550e8400-e29b-41d4-a716-446655440000"
    
    # Test audio stream
    audio_response = await get_audio_stream_resource(
        f"music-library://audio/{audio_id}/stream"
    )
    assert audio_response["mimeType"] == "audio/mpeg"
    
    # Test metadata
    metadata_response = await get_metadata_resource(
        f"music-library://audio/{audio_id}/metadata"
    )
    assert metadata_response["mimeType"] == "application/json"
    
    # Test thumbnail
    thumbnail_response = await get_thumbnail_resource(
        f"music-library://audio/{audio_id}/thumbnail"
    )
    assert thumbnail_response["mimeType"] == "image/jpeg"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

