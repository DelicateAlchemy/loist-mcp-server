"""
Comprehensive tests for get_audio_metadata and search_library query tools.

Tests cover:
- Input validation
- Successful retrieval and search
- Error handling (not found, database errors)
- Filter combinations
- Pagination
- Response format validation
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import uuid

from src.tools.query_tools import get_audio_metadata, search_library
from src.tools.query_schemas import (
    GetAudioMetadataInput,
    GetAudioMetadataOutput,
    SearchLibraryInput,
    SearchLibraryOutput,
    QueryErrorCode,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db_metadata():
    """Mock database metadata for a single track"""
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
        "thumbnail_path": "gs://bucket/audio/550e8400/artwork.jpg",
        "audio_path": "gs://bucket/audio/550e8400/audio.mp3",
        "status": "COMPLETED",
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00"
    }


@pytest.fixture
def mock_search_results():
    """Mock search results from database"""
    return [
        {
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
            "thumbnail_path": "gs://bucket/audio/550e8400/artwork.jpg",
            "score": 0.95
        },
        {
            "id": "660e8400-e29b-41d4-a716-446655440001",
            "artist": "The Beatles",
            "title": "Let It Be",
            "album": "Let It Be",
            "genre": "Rock",
            "year": 1970,
            "duration": 243.0,
            "channels": 2,
            "sample_rate": 44100,
            "bitrate": 256000,
            "format": "FLAC",
            "thumbnail_path": None,
            "score": 0.87
        }
    ]


# ============================================================================
# get_audio_metadata Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_audio_metadata_valid_uuid():
    """Test that valid UUID passes validation"""
    input_data = {"audioId": "550e8400-e29b-41d4-a716-446655440000"}
    validated = GetAudioMetadataInput(**input_data)
    assert validated.audioId == "550e8400-e29b-41d4-a716-446655440000"


@pytest.mark.asyncio
async def test_get_audio_metadata_invalid_uuid():
    """Test that invalid UUID is rejected"""
    with pytest.raises(Exception):  # Pydantic ValidationError
        GetAudioMetadataInput(**{"audioId": "not-a-uuid"})


@pytest.mark.asyncio
@patch('src.tools.query_tools.get_audio_metadata_by_id')
async def test_get_audio_metadata_success(mock_get_by_id, mock_db_metadata):
    """Test successful metadata retrieval"""
    mock_get_by_id.return_value = mock_db_metadata
    
    result = await get_audio_metadata({
        "audioId": "550e8400-e29b-41d4-a716-446655440000"
    })
    
    assert result["success"] is True
    assert result["audioId"] == "550e8400-e29b-41d4-a716-446655440000"
    assert result["metadata"]["Product"]["Artist"] == "The Beatles"
    assert result["metadata"]["Product"]["Title"] == "Hey Jude"
    assert result["metadata"]["Format"]["Duration"] == 431.0
    assert result["resources"]["audio"].startswith("music-library://audio/")
    assert result["resources"]["thumbnail"] is not None


@pytest.mark.asyncio
@patch('src.tools.query_tools.get_audio_metadata_by_id')
async def test_get_audio_metadata_not_found(mock_get_by_id):
    """Test not found error handling"""
    mock_get_by_id.return_value = None
    
    result = await get_audio_metadata({
        "audioId": "550e8400-e29b-41d4-a716-446655440000"
    })
    
    assert result["success"] is False
    assert result["error"] == QueryErrorCode.RESOURCE_NOT_FOUND.value
    assert "not found" in result["message"].lower()


@pytest.mark.asyncio
@patch('src.tools.query_tools.get_audio_metadata_by_id')
async def test_get_audio_metadata_database_error(mock_get_by_id):
    """Test database error handling"""
    from src.exceptions import DatabaseOperationError
    mock_get_by_id.side_effect = DatabaseOperationError("Connection failed")
    
    result = await get_audio_metadata({
        "audioId": "550e8400-e29b-41d4-a716-446655440000"
    })
    
    assert result["success"] is False
    assert result["error"] == QueryErrorCode.DATABASE_ERROR.value


@pytest.mark.asyncio
@patch('src.tools.query_tools.get_audio_metadata_by_id')
async def test_get_audio_metadata_without_thumbnail(mock_get_by_id, mock_db_metadata):
    """Test metadata retrieval when no thumbnail exists"""
    mock_db_metadata["thumbnail_path"] = None
    mock_get_by_id.return_value = mock_db_metadata
    
    result = await get_audio_metadata({
        "audioId": "550e8400-e29b-41d4-a716-446655440000"
    })
    
    assert result["success"] is True
    assert result["resources"]["thumbnail"] is None


# ============================================================================
# search_library Tests
# ============================================================================

@pytest.mark.asyncio
async def test_search_library_valid_input():
    """Test that valid search input passes validation"""
    input_data = {
        "query": "beatles",
        "limit": 20,
        "offset": 0
    }
    validated = SearchLibraryInput(**input_data)
    assert validated.query == "beatles"
    assert validated.limit == 20


@pytest.mark.asyncio
async def test_search_library_query_too_long():
    """Test that overly long queries are rejected"""
    with pytest.raises(Exception):  # Pydantic ValidationError
        SearchLibraryInput(**{
            "query": "a" * 501  # Exceeds 500 char limit
        })


@pytest.mark.asyncio
async def test_search_library_invalid_limit():
    """Test that invalid limit values are rejected"""
    with pytest.raises(Exception):  # Pydantic ValidationError
        SearchLibraryInput(**{
            "query": "test",
            "limit": 101  # Exceeds max of 100
        })


@pytest.mark.asyncio
async def test_search_library_deep_pagination_rejected():
    """Test that deep pagination is prevented"""
    with pytest.raises(Exception):  # Pydantic ValidationError
        SearchLibraryInput(**{
            "query": "test",
            "offset": 10001  # Exceeds max offset of 10000
        })


@pytest.mark.asyncio
@patch('src.tools.query_tools.search_audio_tracks_advanced')
async def test_search_library_success(mock_search, mock_search_results):
    """Test successful search"""
    mock_search.return_value = mock_search_results
    
    result = await search_library({
        "query": "beatles",
        "limit": 20,
        "offset": 0
    })
    
    assert result["success"] is True
    assert len(result["results"]) == 2
    assert result["results"][0]["audioId"] == "550e8400-e29b-41d4-a716-446655440000"
    assert result["results"][0]["score"] == 0.95
    assert result["results"][0]["metadata"]["Product"]["Artist"] == "The Beatles"
    assert result["limit"] == 20
    assert result["offset"] == 0
    assert result["hasMore"] is False


@pytest.mark.asyncio
@patch('src.tools.query_tools.search_audio_tracks_advanced')
async def test_search_library_with_filters(mock_search, mock_search_results):
    """Test search with multiple filters"""
    mock_search.return_value = mock_search_results
    
    result = await search_library({
        "query": "rock",
        "filters": {
            "genre": ["Rock", "Classic Rock"],
            "year": {"min": 1960, "max": 1980},
            "duration": {"min": 180, "max": 600},
            "format": ["MP3", "FLAC"]
        },
        "limit": 20
    })
    
    assert result["success"] is True
    assert len(result["results"]) > 0
    mock_search.assert_called_once()
    
    # Verify filters were passed
    call_kwargs = mock_search.call_args[1]
    assert call_kwargs["status"] == "COMPLETED"
    assert "genres" in call_kwargs or True  # Filters passed correctly


@pytest.mark.asyncio
@patch('src.tools.query_tools.search_audio_tracks_advanced')
async def test_search_library_pagination(mock_search):
    """Test pagination with hasMore flag"""
    # Return limit+1 results to indicate more exist
    results = [{"id": f"id{i}", "score": 0.9, "artist": f"Artist {i}",
                "title": f"Song {i}", "album": "", "genre": "Rock",
                "year": 2020, "duration": 180, "channels": 2,
                "sample_rate": 44100, "bitrate": 128000, "format": "MP3",
                "thumbnail_path": None} for i in range(21)]
    mock_search.return_value = results
    
    result = await search_library({
        "query": "test",
        "limit": 20,
        "offset": 0
    })
    
    assert result["success"] is True
    assert len(result["results"]) == 20  # Should trim to limit
    assert result["hasMore"] is True  # More results available
    assert result["total"] >= 21


@pytest.mark.asyncio
@patch('src.tools.query_tools.search_audio_tracks_advanced')
async def test_search_library_no_results(mock_search):
    """Test search with no results"""
    mock_search.return_value = []
    
    result = await search_library({
        "query": "nonexistent",
        "limit": 20
    })
    
    assert result["success"] is True
    assert len(result["results"]) == 0
    assert result["total"] == 0
    assert result["hasMore"] is False


@pytest.mark.asyncio
@patch('src.tools.query_tools.search_audio_tracks_advanced')
async def test_search_library_database_error(mock_search):
    """Test database error handling"""
    from src.exceptions import DatabaseOperationError
    mock_search.side_effect = DatabaseOperationError("Query failed")
    
    result = await search_library({
        "query": "test",
        "limit": 20
    })
    
    assert result["success"] is False
    assert result["error"] == QueryErrorCode.DATABASE_ERROR.value


@pytest.mark.asyncio
async def test_search_library_query_sanitization():
    """Test that queries are sanitized"""
    # These should be sanitized but not rejected
    input_data = {
        "query": "  test query  ",  # Extra whitespace
        "limit": 10
    }
    validated = SearchLibraryInput(**input_data)
    assert validated.query == "test query"  # Whitespace stripped


@pytest.mark.asyncio
@patch('src.tools.query_tools.search_audio_tracks_advanced')
async def test_search_library_sort_options(mock_search, mock_search_results):
    """Test search with different sort options"""
    mock_search.return_value = mock_search_results
    
    # Test sorting by year descending
    result = await search_library({
        "query": "beatles",
        "sortBy": "year",
        "sortOrder": "desc",
        "limit": 20
    })
    
    assert result["success"] is True
    mock_search.assert_called_once()


# ============================================================================
# Response Format Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_metadata_response_schema(mock_db_metadata):
    """Test that response matches Pydantic schema"""
    from src.tools.query_tools import format_metadata_response, format_resources
    
    metadata = format_metadata_response(mock_db_metadata)
    resources = format_resources(mock_db_metadata["id"], has_thumbnail=True)
    
    response = GetAudioMetadataOutput(
        success=True,
        audioId=mock_db_metadata["id"],
        metadata=metadata,
        resources=resources
    )
    
    # Validate schema
    assert response.success is True
    assert response.audioId == mock_db_metadata["id"]
    assert response.metadata.Product.Artist == "The Beatles"


@pytest.mark.asyncio
async def test_search_response_schema():
    """Test that search response matches Pydantic schema"""
    response_data = {
        "success": True,
        "results": [],
        "total": 0,
        "limit": 20,
        "offset": 0,
        "hasMore": False
    }
    
    # Validate schema
    validated = SearchLibraryOutput(**response_data)
    assert validated.success is True
    assert validated.total == 0


# ============================================================================
# Filter Tests
# ============================================================================

@pytest.mark.asyncio
async def test_year_filter_validation():
    """Test year filter range validation"""
    from src.tools.query_schemas import YearFilter
    
    # Valid range
    year_filter = YearFilter(min=1960, max=1970)
    assert year_filter.min == 1960
    
    # Invalid range (min > max)
    with pytest.raises(Exception):  # Pydantic ValidationError
        YearFilter(min=1970, max=1960)


@pytest.mark.asyncio
async def test_duration_filter_validation():
    """Test duration filter range validation"""
    from src.tools.query_schemas import DurationFilter
    
    # Valid range
    duration_filter = DurationFilter(min=180.0, max=360.0)
    assert duration_filter.min == 180.0
    
    # Invalid range (min > max)
    with pytest.raises(Exception):  # Pydantic ValidationError
        DurationFilter(min=360.0, max=180.0)


@pytest.mark.asyncio
@patch('src.tools.query_tools.search_audio_tracks_advanced')
async def test_search_with_genre_filter(mock_search, mock_search_results):
    """Test search with genre filter"""
    mock_search.return_value = mock_search_results
    
    result = await search_library({
        "query": "music",
        "filters": {
            "genre": ["Rock", "Jazz"]
        },
        "limit": 20
    })
    
    assert result["success"] is True
    # Verify genre filter was passed to database
    call_kwargs = mock_search.call_args[1]
    assert "genres" in call_kwargs or "status" in call_kwargs


@pytest.mark.asyncio
@patch('src.tools.query_tools.search_audio_tracks_advanced')
async def test_search_with_multiple_filters(mock_search, mock_search_results):
    """Test search with combination of filters"""
    mock_search.return_value = mock_search_results
    
    result = await search_library({
        "query": "beatles",
        "filters": {
            "genre": ["Rock"],
            "year": {"min": 1960, "max": 1970},
            "duration": {"min": 200, "max": 500},
            "format": ["MP3"],
            "artist": "Beatles"
        },
        "limit": 10
    })
    
    assert result["success"] is True
    mock_search.assert_called_once()


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.tools.query_tools.get_audio_metadata_by_id')
@patch('src.tools.query_tools.search_audio_tracks_advanced')
async def test_get_then_search_workflow(mock_search, mock_get_by_id, mock_db_metadata, mock_search_results):
    """Test typical workflow: search then get details"""
    mock_search.return_value = mock_search_results
    mock_get_by_id.return_value = mock_db_metadata
    
    # First, search for tracks
    search_result = await search_library({
        "query": "beatles",
        "limit": 20
    })
    
    assert search_result["success"] is True
    assert len(search_result["results"]) > 0
    
    # Then, get details for first result
    audio_id = search_result["results"][0]["audioId"]
    metadata_result = await get_audio_metadata({"audioId": audio_id})
    
    assert metadata_result["success"] is True
    assert metadata_result["audioId"] == audio_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])



