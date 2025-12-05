"""
Tests for MCP resource handlers.

This file tests the wrapper logic of the MCP resource handlers, ensuring they
correctly call the streaming_service and format the MCP response.
"""

import pytest
from unittest.mock import patch, AsyncMock

from src.resources.audio_stream import get_audio_stream_resource, get_content_headers_for_audio
from src.resources.thumbnail import get_thumbnail_resource, get_content_headers_for_thumbnail
from src.exceptions import ResourceNotFoundError, ValidationError

# ============================================================================
# Audio Stream Resource Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.resources.audio_stream.streaming_service', new_callable=AsyncMock)
async def test_audio_stream_success(mock_streaming_service):
    """Test successful wrapping of the streaming_service for audio streams."""
    mock_streaming_service.get_audio_stream_details.return_value = {
        "signed_url": "http://signed-url/audio.mp3",
        "mime_type": "audio/mpeg",
    }
    
    uri = "music-library://audio/550e8400-e29b-41d4-a716-446655440000/stream"
    response = await get_audio_stream_resource(uri)
    
    mock_streaming_service.get_audio_stream_details.assert_called_once_with("550e8400-e29b-41d4-a716-446655440000")
    assert response["uri"] == "http://signed-url/audio.mp3"
    assert response["mimeType"] == "audio/mpeg"

@pytest.mark.asyncio
@patch('src.resources.audio_stream.streaming_service', new_callable=AsyncMock)
async def test_audio_stream_not_found(mock_streaming_service):
    """Test that the resource wrapper propagates ResourceNotFoundError."""
    mock_streaming_service.get_audio_stream_details.side_effect = ResourceNotFoundError("Not found")
    
    with pytest.raises(ResourceNotFoundError):
        await get_audio_stream_resource("music-library://audio/not-found-id/stream")

@pytest.mark.asyncio
async def test_audio_stream_invalid_uri():
    """Test that the resource wrapper raises ValidationError for bad URIs."""
    with pytest.raises(ValidationError):
        await get_audio_stream_resource("invalid-uri")

# ============================================================================
# Thumbnail Resource Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.resources.thumbnail.streaming_service', new_callable=AsyncMock)
async def test_thumbnail_resource_success(mock_streaming_service):
    """Test successful wrapping of the streaming_service for thumbnails."""
    mock_streaming_service.get_thumbnail_details.return_value = {
        "signed_url": "http://signed-url/art.jpg",
        "mime_type": "image/jpeg",
    }
    
    uri = "music-library://audio/550e8400-e29b-41d4-a716-446655440000/thumbnail"
    response = await get_thumbnail_resource(uri)
    
    mock_streaming_service.get_thumbnail_details.assert_called_once_with("550e8400-e29b-41d4-a716-446655440000")
    assert response["uri"] == "http://signed-url/art.jpg"
    assert response["mimeType"] == "image/jpeg"

@pytest.mark.asyncio
@patch('src.resources.thumbnail.streaming_service', new_callable=AsyncMock)
async def test_thumbnail_resource_not_found(mock_streaming_service):
    """Test that the thumbnail wrapper propagates ResourceNotFoundError."""
    mock_streaming_service.get_thumbnail_details.side_effect = ResourceNotFoundError("Not found")
    
    with pytest.raises(ResourceNotFoundError):
        await get_thumbnail_resource("music-library://audio/not-found-id/thumbnail")

# ============================================================================
# Header Util Tests (Keeping them here for now)
# ============================================================================

def test_audio_headers():
    """Test audio streaming headers utility function."""
    headers = get_content_headers_for_audio("MP3", support_ranges=True)
    assert headers["Content-Type"] == "audio/mpeg"
    assert headers["Accept-Ranges"] == "bytes"

def test_thumbnail_headers():
    """Test thumbnail image headers utility function."""
    headers = get_content_headers_for_thumbnail()
    assert headers["Content-Type"] == "image/jpeg"
    assert "Cache-Control" in headers