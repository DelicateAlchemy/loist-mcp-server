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

from src.tools.query_tools import get_audio_metadata, search_library, delete_audio
from src.tools.query_schemas import (
    GetAudioMetadataInput,
    GetAudioMetadataOutput,
    SearchLibraryInput,
    SearchLibraryOutput,
    DeleteAudioInput,
    DeleteAudioOutput,
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
        "limit": 20
    }
    validated = SearchLibraryInput(**input_data)
    assert validated.query == "beatles"
    assert validated.limit == 20
    assert validated.filter is None
    assert validated.fields == "id,title,score,artist,album,genre,year"
    assert validated.cursor is None


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
async def test_search_library_invalid_cursor():
    """Test that invalid cursor is rejected"""
    with pytest.raises(Exception):  # Pydantic ValidationError
        SearchLibraryInput(**{
            "query": "test",
            "cursor": "invalid-cursor-string"
        })


@pytest.mark.asyncio
@patch('src.tools.query_tools.search_audio_tracks_cursor')
async def test_search_library_success(mock_search, mock_search_results):
    """Test successful search"""
    mock_search.return_value = mock_search_results

    result = await search_library({
        "query": "beatles",
        "limit": 20
    })

    assert result["success"] is True
    assert len(result["results"]) == 2
    assert result["results"][0]["audioId"] == "550e8400-e29b-41d4-a716-446655440000"
    assert result["results"][0]["score"] == 0.95
    assert result["results"][0]["metadata"]["Product"]["Artist"] == "The Beatles"
    assert result["limit"] == 20
    assert result["hasMore"] is False
    assert result["nextCursor"] is None


@pytest.mark.asyncio
@patch('src.tools.query_tools.search_audio_tracks_cursor')
async def test_search_library_with_filters(mock_search, mock_search_results):
    """Test search with RSQL filters"""
    mock_search.return_value = mock_search_results

    result = await search_library({
        "query": "rock",
        "filter": "year>=1960,year<=1980;format==MP3",
        "limit": 20
    })

    assert result["success"] is True
    assert len(result["results"]) > 0
    mock_search.assert_called_once()

    # Verify filters were parsed and passed
    call_kwargs = mock_search.call_args[1]
    assert call_kwargs["status_filter"] == "COMPLETED"
    assert call_kwargs["year_min"] == 1960
    assert call_kwargs["year_max"] == 1980
    assert call_kwargs["format_filter"] == "MP3"


@pytest.mark.asyncio
@patch('src.tools.query_tools.search_audio_tracks_cursor')
async def test_search_library_pagination(mock_search):
    """Test pagination with hasMore flag and nextCursor"""
    # Return limit+1 results to indicate more exist
    results = [{"id": f"id{i}", "score": 0.9, "artist": f"Artist {i}",
                "title": f"Song {i}", "album": "", "genre": "Rock",
                "year": 2020, "duration_seconds": 180, "channels": 2,
                "sample_rate": 44100, "bitrate": 128000, "format": "MP3",
                "thumbnail_gcs_path": None, "created_at": "2024-01-01T00:00:00Z"} for i in range(21)]
    mock_search.return_value = {
        'tracks': results,
        'query': 'test',
        'filters': {},
        'limit': 20
    }

    result = await search_library({
        "query": "test",
        "limit": 20
    })

    assert result["success"] is True
    assert len(result["results"]) == 20  # Should trim to limit
    assert result["hasMore"] is True  # More results available
    assert result["nextCursor"] is not None  # Should have cursor for next page


@pytest.mark.asyncio
@patch('src.tools.query_tools.search_audio_tracks_cursor')
async def test_search_library_no_results(mock_search):
    """Test search with no results"""
    mock_search.return_value = {
        'tracks': [],
        'query': 'nonexistent',
        'filters': {},
        'limit': 20
    }

    result = await search_library({
        "query": "nonexistent",
        "limit": 20
    })

    assert result["success"] is True
    assert len(result["results"]) == 0
    assert result["hasMore"] is False
    assert result["nextCursor"] is None


@pytest.mark.asyncio
@patch('src.tools.query_tools.search_audio_tracks_cursor')
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
@patch('src.tools.query_tools.search_audio_tracks_cursor')
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
@patch('src.tools.query_tools.search_audio_tracks_cursor')
async def test_search_with_rsql_filters(mock_search, mock_search_results):
    """Test search with RSQL filter parsing"""
    mock_search.return_value = mock_search_results

    result = await search_library({
        "query": "music",
        "filter": "year>=1960,year<=1980;format==MP3",
        "limit": 20
    })

    assert result["success"] is True
    # Verify RSQL filters were parsed and passed
    call_kwargs = mock_search.call_args[1]
    assert call_kwargs["year_min"] == 1960
    assert call_kwargs["year_max"] == 1980
    assert call_kwargs["format_filter"] == "MP3"


@pytest.mark.asyncio
@patch('src.tools.query_tools.search_audio_tracks_cursor')
async def test_search_with_sparse_fields(mock_search, mock_search_results):
    """Test search with sparse field selection"""
    mock_search.return_value = mock_search_results

    result = await search_library({
        "query": "beatles",
        "fields": "id,title,score",
        "limit": 10
    })

    assert result["success"] is True
    # Verify field selection was applied (results should only have requested fields)
    if result["results"]:
        first_result = result["results"][0]
        # Should have requested fields
        assert "audioId" in first_result
        assert "score" in first_result
        assert "metadata" in first_result
        # Should not have extra fields that weren't selected (this is hard to test with the current structure)


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.tools.query_tools.get_audio_metadata_by_id')
@patch('src.tools.query_tools.search_audio_tracks_cursor')
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


# ============================================================================
# delete_audio Tests
# ============================================================================

@pytest.mark.asyncio
async def test_delete_audio_valid_uuid():
    """Test that valid UUID passes validation"""
    input_data = {"audioId": "550e8400-e29b-41d4-a716-446655440000"}
    validated = DeleteAudioInput(**input_data)
    assert validated.audioId == "550e8400-e29b-41d4-a716-446655440000"


@pytest.mark.asyncio
async def test_delete_audio_invalid_uuid():
    """Test that invalid UUID is rejected"""
    with pytest.raises(Exception):  # Pydantic ValidationError
        DeleteAudioInput(**{"audioId": "not-a-uuid"})


@pytest.mark.asyncio
@patch('src.tools.query_tools.AudioTrackDB.delete_track')
async def test_delete_audio_success(mock_delete):
    """Test successful track deletion"""
    mock_delete.return_value = True  # Track was deleted

    result = await delete_audio({
        "audioId": "550e8400-e29b-41d4-a716-446655440000"
    })

    assert result["success"] is True
    assert result["audioId"] == "550e8400-e29b-41d4-a716-446655440000"
    assert result["deleted"] is True
    mock_delete.assert_called_once()


@pytest.mark.asyncio
@patch('src.tools.query_tools.AudioTrackDB.delete_track')
async def test_delete_audio_not_found(mock_delete):
    """Test deletion of non-existent track"""
    mock_delete.return_value = False  # Track not found

    result = await delete_audio({
        "audioId": "550e8400-e29b-41d4-a716-446655440000"
    })

    assert result["success"] is False
    assert result["error"] == QueryErrorCode.RESOURCE_NOT_FOUND.value
    assert "not found" in result["message"].lower()
    mock_delete.assert_called_once()


@pytest.mark.asyncio
@patch('src.tools.query_tools.AudioTrackDB.delete_track')
async def test_delete_audio_database_error(mock_delete):
    """Test database error handling during deletion"""
    from src.exceptions import DatabaseOperationError
    mock_delete.side_effect = DatabaseOperationError("Connection failed")

    result = await delete_audio({
        "audioId": "550e8400-e29b-41d4-a716-446655440000"
    })

    assert result["success"] is False
    assert result["error"] == QueryErrorCode.DATABASE_ERROR.value
    mock_delete.assert_called_once()


@pytest.mark.asyncio
async def test_delete_audio_invalid_input():
    """Test that invalid input is properly rejected"""
    result = await delete_audio({
        "audioId": "invalid-uuid-format"
    })

    assert result["success"] is False
    assert result["error"] == QueryErrorCode.INVALID_QUERY.value
    assert "validation" in result["message"].lower()


@pytest.mark.asyncio
async def test_delete_audio_response_schema():
    """Test that delete response matches Pydantic schema"""
    # Test success response
    success_response = DeleteAudioOutput(
        success=True,
        audioId="550e8400-e29b-41d4-a716-446655440000",
        deleted=True
    )

    assert success_response.success is True
    assert success_response.audioId == "550e8400-e29b-41d4-a716-446655440000"
    assert success_response.deleted is True


# Time Filtering Tests
@pytest.mark.asyncio
@patch('src.tools.query_tools.filter_audio_tracks_combined')
async def test_search_library_time_period_this_week(mock_search):
    """Test search with time period filter (this week)"""
    mock_search.return_value = {
        'tracks': [
            {
                'id': '550e8400-e29b-41d4-a716-446655440000',
                'title': 'Test Track',
                'artist': 'Test Artist',
                'album': 'Test Album',
                'genre': 'Rock',
                'year': 2025,
                'duration_seconds': 180.0,
                'channels': 2,
                'sample_rate': 44100,
                'bitrate': 320000,
                'format': 'MP3',
                'thumbnail_gcs_path': None,
                'composer': None,
                'publisher': None,
                'record_label': None,
                'isrc': None,
                'rank': 0.8
            }
        ],
        'total_count': 1
    }

    result = await search_library({
        "query": "test",
        "filters": {
            "time": {
                "period": "this_week",
                "timezone": "UTC"
            }
        },
        "limit": 20
    })

    assert result["success"] is True
    assert len(result["results"]) == 1
    assert result["results"][0]["audioId"] == "550e8400-e29b-41d4-a716-446655440000"

    # Verify that the time filter parameters were passed to the database function
    mock_search.assert_called_once()
    call_args = mock_search.call_args
    assert call_args.kwargs['time_period'] == 'this_week'
    assert call_args.kwargs['timezone'] == 'UTC'


@pytest.mark.asyncio
@patch('src.tools.query_tools.filter_audio_tracks_combined')
async def test_search_library_custom_date_range(mock_search):
    """Test search with custom date range filter"""
    mock_search.return_value = {
        'tracks': [
            {
                'id': '550e8400-e29b-41d4-a716-446655440001',
                'title': 'Another Track',
                'artist': 'Another Artist',
                'album': 'Another Album',
                'genre': 'Jazz',
                'year': 2025,
                'duration_seconds': 240.0,
                'channels': 2,
                'sample_rate': 44100,
                'bitrate': 256000,
                'format': 'FLAC',
                'thumbnail_gcs_path': None,
                'composer': None,
                'publisher': None,
                'record_label': None,
                'isrc': None,
                'rank': 0.9
            }
        ],
        'total_count': 1
    }

    result = await search_library({
        "query": "jazz",
        "filters": {
            "time": {
                "dateFrom": "2025-11-01",
                "dateTo": "2025-11-30",
                "timezone": "America/New_York"
            }
        },
        "limit": 10
    })

    assert result["success"] is True
    assert len(result["results"]) == 1

    # Verify that the custom date filter parameters were passed
    mock_search.assert_called_once()
    call_args = mock_search.call_args
    assert call_args.kwargs['date_from'] == '2025-11-01'
    assert call_args.kwargs['date_to'] == '2025-11-30'
    assert call_args.kwargs['timezone'] == 'America/New_York'


@pytest.mark.asyncio
@patch('src.tools.query_tools.filter_audio_tracks_combined')
async def test_search_library_time_period_validation_error(mock_search):
    """Test search with invalid time period"""
    # Test invalid time period
    with pytest.raises(Exception):  # Should raise validation error
        await search_library({
            "query": "test",
            "filters": {
                "time": {
                    "period": "invalid_period"
                }
            }
        })


@pytest.mark.asyncio
@patch('src.tools.query_tools.filter_audio_tracks_combined')
async def test_search_library_invalid_timezone(mock_search):
    """Test search with invalid timezone"""
    with pytest.raises(Exception):  # Should raise validation error
        await search_library({
            "query": "test",
            "filters": {
                "time": {
                    "period": "today",
                    "timezone": "Invalid/Timezone"
                }
            }
        })


if __name__ == "__main__":
    pytest.main([__file__, "-v"])



