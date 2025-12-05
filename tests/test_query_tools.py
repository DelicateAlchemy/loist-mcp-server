"""
Tests for the query tools (get_audio_metadata, search_library, delete_audio).

These tests validate the tool layer's logic, which involves:
- Input validation using Pydantic schemas.
- Calling the appropriate service layer function.
- Formatting the service's response into the correct MCP tool format.
- Handling exceptions from the service layer and converting them to MCP error responses.
"""

import pytest
from unittest.mock import patch, AsyncMock

# Models for creating mock service responses
from src.schemas.metadata import AudioMetadata, AudioResources, ProductMetadata, FormatMetadata
from src.tools.query_schemas import SearchResult, SearchFacets, QueryErrorCode, GetAudioMetadataInput, SearchLibraryInput, DeleteAudioInput

# Functions to test
from src.tools.query_tools import get_audio_metadata, search_library, delete_audio

# Exceptions to test handling for
from src.exceptions import ResourceNotFoundError, DatabaseOperationError

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_service_metadata_response():
    """Provides a mock response from audio_service.get_audio_metadata."""
    return {
        "audio_id": "550e8400-e29b-41d4-a716-446655440000",
        "metadata": AudioMetadata(
            product=ProductMetadata(artist="The Beatles", title="Hey Jude", album="Hey Jude"),
            format=FormatMetadata(duration=431.0, format="MP3"),
            url_embed_link="http://loist.io/embed/some-id"
        ),
        "resources": AudioResources(
            audio_url="music-library://audio/some-id/stream",
            thumbnail_url="music-library://audio/some-id/thumbnail"
        ),
    }

@pytest.fixture
def mock_service_search_response():
    """Provides a mock response from audio_service.search_audio_library."""
    metadata = AudioMetadata(
        product=ProductMetadata(artist="The Beatles", title="Hey Jude"),
        format=FormatMetadata(duration=431.0, format="MP3"),
        url_embed_link="http://loist.io/embed/some-id"
    )
    return {
        "results": [SearchResult(audio_id="some-id", metadata=metadata, score=0.9)],
        "total": 1,
        "limit": 20,
        "offset": 0,
        "has_more": False,
        "facets": None,
    }

# ============================================================================
# get_audio_metadata Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_audio_metadata_input_validation():
    """Test Pydantic input validation for get_audio_metadata."""
    # Valid
    GetAudioMetadataInput(audio_id="550e8400-e29b-41d4-a716-446655440000")
    # Invalid
    with pytest.raises(Exception):
        GetAudioMetadataInput(audio_id="not-a-uuid")

@pytest.mark.asyncio
@patch('src.tools.query_tools.audio_service', new_callable=AsyncMock)
async def test_get_audio_metadata_success(mock_audio_service, mock_service_metadata_response):
    """Test successful wrapping of the audio_service."""
    mock_audio_service.get_audio_metadata.return_value = mock_service_metadata_response
    
    result = await get_audio_metadata({"audio_id": "550e8400-e29b-41d4-a716-446655440000"})
    
    mock_audio_service.get_audio_metadata.assert_called_once_with("550e8400-e29b-41d4-a716-446655440000")
    assert result["success"] is True
    assert result["audio_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert result["metadata"]["product"]["artist"] == "The Beatles"

@pytest.mark.asyncio
@patch('src.tools.query_tools.audio_service', new_callable=AsyncMock)
async def test_get_audio_metadata_not_found(mock_audio_service):
    """Test handling of ResourceNotFoundError from the service."""
    mock_audio_service.get_audio_metadata.side_effect = ResourceNotFoundError("Track not found")
    
    with pytest.raises(Exception) as excinfo:
        await get_audio_metadata({"audio_id": "not-found-id"})
    
    assert excinfo.value.error_code == QueryErrorCode.RESOURCE_NOT_FOUND

@pytest.mark.asyncio
@patch('src.tools.query_tools.audio_service', new_callable=AsyncMock)
async def test_get_audio_metadata_db_error(mock_audio_service):
    """Test handling of DatabaseOperationError from the service."""
    mock_audio_service.get_audio_metadata.side_effect = DatabaseOperationError("DB connection failed")

    with pytest.raises(Exception) as excinfo:
        await get_audio_metadata({"audio_id": "any-id"})

    assert excinfo.value.error_code == QueryErrorCode.DATABASE_ERROR

# ============================================================================
# search_library Tests
# ============================================================================

@pytest.mark.asyncio
async def test_search_library_input_validation():
    """Test Pydantic input validation for search_library."""
    SearchLibraryInput(query="test")
    with pytest.raises(Exception):
        SearchLibraryInput(query="a" * 501) # Too long
    with pytest.raises(Exception):
        SearchLibraryInput(query="test", limit=200) # limit too high

@pytest.mark.asyncio
@patch('src.tools.query_tools.audio_service', new_callable=AsyncMock)
async def test_search_library_success(mock_audio_service, mock_service_search_response):
    """Test successful wrapping of the search service."""
    mock_audio_service.search_audio_library.return_value = mock_service_search_response
    
    result = await search_library({"query": "beatles", "limit": 20, "offset": 0})
    
    mock_audio_service.search_audio_library.assert_called_once_with(query="beatles", limit=20, offset=0, filters=None)
    assert result["success"] is True
    assert len(result["results"]) == 1
    assert result["total"] == 1
    assert result["results"][0]["metadata"]["product"]["artist"] == "The Beatles"

@pytest.mark.asyncio
@patch('src.tools.query_tools.audio_service', new_callable=AsyncMock)
async def test_search_library_db_error(mock_audio_service):
    """Test handling of DatabaseOperationError from the search service."""
    mock_audio_service.search_audio_library.side_effect = DatabaseOperationError("Search failed")
    
    with pytest.raises(Exception) as excinfo:
        await search_library({"query": "test"})
    
    assert excinfo.value.error_code == QueryErrorCode.DATABASE_ERROR

# ============================================================================
# delete_audio Tests
# ============================================================================

@pytest.mark.asyncio
async def test_delete_audio_input_validation():
    """Test Pydantic input validation for delete_audio."""
    DeleteAudioInput(audio_id="550e8400-e29b-41d4-a716-446655440000")
    with pytest.raises(Exception):
        DeleteAudioInput(audio_id="not-a-uuid")

@pytest.mark.asyncio
@patch('src.tools.query_tools.audio_service', new_callable=AsyncMock)
async def test_delete_audio_success(mock_audio_service):
    """Test successful wrapping of the delete service."""
    mock_audio_service.delete_audio_track_and_files.return_value = True
    
    result = await delete_audio({"audio_id": "550e8400-e29b-41d4-a716-446655440000"})
    
    mock_audio_service.delete_audio_track_and_files.assert_called_once_with("550e8400-e29b-41d4-a716-446655440000")
    assert result["success"] is True
    assert result["deleted"] is True

@pytest.mark.asyncio
@patch('src.tools.query_tools.audio_service', new_callable=AsyncMock)
async def test_delete_audio_not_found(mock_audio_service):
    """Test handling of ResourceNotFoundError on delete."""
    mock_audio_service.delete_audio_track_and_files.side_effect = ResourceNotFoundError("Not found")

    with pytest.raises(Exception) as excinfo:
        await delete_audio({"audio_id": "not-found-id"})

    assert excinfo.value.error_code == QueryErrorCode.RESOURCE_NOT_FOUND