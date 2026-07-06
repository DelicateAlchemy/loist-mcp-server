"""
Integration tests for the v1 REST API endpoints.

These tests use an HTTP client to make real requests to the application,
but they mock the service layer to isolate the HTTP layer (routing,
request/response handling, headers, error envelope) from the business logic.
"""

import pytest
import httpx
from unittest.mock import patch, AsyncMock

pytestmark = pytest.mark.requires_db

# Models for creating mock service responses
from src.schemas.metadata import AudioMetadata, AudioResources, ProductMetadata, FormatMetadata

# The application instance to test
from src.server import mcp

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
async def client():
    """Async HTTP client for testing the Starlette app."""
    transport = httpx.ASGITransport(app=mcp.http_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

@pytest.fixture
def mock_service_metadata_response():
    """Mock response from audio_service.get_audio_metadata."""
    return {
        "audio_id": "550e8400-e29b-41d4-a716-446655440000",
        "metadata": AudioMetadata(
            product=ProductMetadata(artist="The Beatles", title="Hey Jude"),
            format=FormatMetadata(duration=431.0, format="MP3"),
            url_embed_link="http://test/embed/some-id"
        ),
        "resources": AudioResources(audio_url="...", thumbnail_url="..."),
    }

# ============================================================================
# /api/v1/tracks/{audioId} Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.http_api.audio_service', new_callable=AsyncMock)
async def test_get_track_success(mock_audio_service, client, mock_service_metadata_response):
    """Test GET /api/v1/tracks/{audioId} success case."""
    mock_audio_service.get_audio_metadata.return_value = mock_service_metadata_response

    response = await client.get("/api/v1/tracks/550e8400-e29b-41d4-a716-446655440000")

    assert response.status_code == 200
    json_data = response.json()
    assert json_data["success"] is True
    assert json_data["metadata"]["product"]["artist"] == "The Beatles"
    assert "etag" in response.headers
    assert "cache-control" in response.headers

@pytest.mark.asyncio
@patch('src.http_api.audio_service', new_callable=AsyncMock)
async def test_get_track_not_found(mock_audio_service, client):
    """Test GET /api/v1/tracks/{audioId} for a track that doesn't exist."""
    from src.exceptions import ResourceNotFoundError
    mock_audio_service.get_audio_metadata.side_effect = ResourceNotFoundError("Not found")

    response = await client.get("/api/v1/tracks/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    json_data = response.json()
    assert json_data["success"] is False
    assert json_data["error"] == "TRACK_NOT_FOUND"
    assert "message" in json_data

@pytest.mark.asyncio
async def test_get_track_invalid_uuid_error_envelope(client):
    """Invalid UUIDs return 400 with the standard error envelope."""
    response = await client.get("/api/v1/tracks/not-a-uuid")

    assert response.status_code == 400
    json_data = response.json()
    assert json_data["success"] is False
    assert json_data["error"] == "VALIDATION_ERROR"
    assert "message" in json_data

@pytest.mark.asyncio
async def test_unversioned_api_paths_are_gone(client):
    """The pre-v1 /api/* paths were removed in the v1 cutover (LOI-38)."""
    response = await client.get("/api/tracks/550e8400-e29b-41d4-a716-446655440000")
    assert response.status_code == 404

# ============================================================================
# /api/v1/search Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.http_api.audio_service', new_callable=AsyncMock)
async def test_search_success(mock_audio_service, client):
    """Test GET /api/v1/search success case."""
    mock_audio_service.search_audio_library.return_value = {
        "results": [], "total": 0, "limit": 20, "offset": 0, "has_more": False, "facets": None
    }

    response = await client.get("/api/v1/search?q=test")

    assert response.status_code == 200
    json_data = response.json()
    assert json_data["success"] is True
    assert "x-total-count" in response.headers
    assert response.headers["x-total-count"] == "0"

@pytest.mark.asyncio
async def test_search_missing_query_error_envelope(client):
    """Missing q parameter returns 400 with the standard error envelope."""
    response = await client.get("/api/v1/search")

    assert response.status_code == 400
    json_data = response.json()
    assert json_data["success"] is False
    assert json_data["error"] == "INVALID_QUERY"
    assert "message" in json_data

# ============================================================================
# /api/v1/tracks/{audioId}/stream Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.http_api.streaming_service', new_callable=AsyncMock)
async def test_get_stream_redirect(mock_streaming_service, client):
    """Test GET /api/v1/tracks/{audioId}/stream redirects correctly."""
    mock_streaming_service.get_audio_stream_details.return_value = {
        "signed_url": "http://signed-url/audio.mp3"
    }

    response = await client.get(
        "/api/v1/tracks/550e8400-e29b-41d4-a716-446655440000/stream",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "http://signed-url/audio.mp3"

# ============================================================================
# /api/v1/tracks/{audioId}/thumbnail Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.http_api.streaming_service', new_callable=AsyncMock)
async def test_get_thumbnail_redirect(mock_streaming_service, client):
    """Test GET /api/v1/tracks/{audioId}/thumbnail redirects correctly."""
    mock_streaming_service.get_thumbnail_details.return_value = {
        "signed_url": "http://signed-url/art.jpg"
    }

    response = await client.get(
        "/api/v1/tracks/550e8400-e29b-41d4-a716-446655440000/thumbnail",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "http://signed-url/art.jpg"

# ============================================================================
# /api/v1/tracks/{audioId} DELETE Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.http_api.audio_service', new_callable=AsyncMock)
async def test_delete_track_success(mock_audio_service, client):
    """Test DELETE /api/v1/tracks/{audioId} success case."""
    mock_audio_service.delete_audio_track_and_files.return_value = True

    response = await client.delete("/api/v1/tracks/550e8400-e29b-41d4-a716-446655440000")

    assert response.status_code == 204

@pytest.mark.asyncio
@patch('src.http_api.audio_service', new_callable=AsyncMock)
async def test_delete_track_not_found(mock_audio_service, client):
    """Test DELETE /api/v1/tracks/{audioId} for a non-existent track."""
    from src.exceptions import ResourceNotFoundError
    mock_audio_service.delete_audio_track_and_files.side_effect = ResourceNotFoundError("Not found")

    response = await client.delete("/api/v1/tracks/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    json_data = response.json()
    assert json_data["success"] is False
    assert json_data["error"] == "TRACK_NOT_FOUND"
