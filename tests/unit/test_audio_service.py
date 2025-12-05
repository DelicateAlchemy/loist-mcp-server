"""
Unit tests for the audio_service layer.

These tests mock the database and GCS dependencies to test the service's
business logic in isolation.
"""

import pytest
from unittest.mock import patch, ANY

from src.services import audio_service
from src.exceptions import ResourceNotFoundError, DatabaseOperationError

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
        "duration_seconds": 431.0,
        "channels": 2,
        "sample_rate": 44100,
        "bitrate": 320000,
        "format": "MP3",
        "thumbnail_gcs_path": "gs://bucket/art.jpg",
        "audio_gcs_path": "gs://bucket/audio.mp3",
    }

@pytest.fixture
def mock_db_search_response():
    """Mock search response from the database."""
    return {
        'tracks': [
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "artist": "The Beatles", "title": "Hey Jude", "album": "Hey Jude",
                "duration_seconds": 431.0, "format": "MP3", "rank": 0.95,
                "thumbnail_gcs_path": "gs://bucket/art.jpg",
            }
        ],
        'total_count': 1,
    }

# ============================================================================
# get_audio_metadata Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.audio_service.get_audio_metadata_by_id')
async def test_get_audio_metadata_success(mock_get_by_id, mock_db_metadata):
    """Test successful metadata retrieval in the service."""
    mock_get_by_id.return_value = mock_db_metadata
    
    result = await audio_service.get_audio_metadata("any_id")
    
    mock_get_by_id.assert_called_once_with("any_id")
    assert result["audio_id"] == "any_id"
    assert result["metadata"].product.artist == "The Beatles"
    assert result["resources"].thumbnail_url is not None

@pytest.mark.asyncio
@patch('src.services.audio_service.get_audio_metadata_by_id')
async def test_get_audio_metadata_not_found(mock_get_by_id):
    """Test that ResourceNotFoundError is raised for a missing track."""
    mock_get_by_id.return_value = None
    
    with pytest.raises(ResourceNotFoundError):
        await audio_service.get_audio_metadata("not_found_id")
    
    mock_get_by_id.assert_called_once_with("not_found_id")

@pytest.mark.asyncio
@patch('src.services.audio_service.get_audio_metadata_by_id')
async def test_get_audio_metadata_db_error(mock_get_by_id):
    """Test that DatabaseOperationError is propagated."""
    mock_get_by_id.side_effect = DatabaseOperationError("Connection failed")
    
    with pytest.raises(DatabaseOperationError):
        await audio_service.get_audio_metadata("any_id")

# ============================================================================
# search_audio_library Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.audio_service.filter_audio_tracks_combined')
@patch('src.services.audio_service.get_xmp_field_facets')
async def test_search_audio_library_success(mock_get_facets, mock_db_call, mock_db_search_response):
    """Test successful search in the service."""
    mock_db_call.return_value = mock_db_search_response
    mock_get_facets.return_value = {}
    
    result = await audio_service.search_audio_library("test", 20, 0)
    
    mock_db_call.assert_called_once()
    assert len(result["results"]) == 1
    assert result["total"] == 1
    assert result["results"][0].metadata.product.artist == "The Beatles"

@pytest.mark.asyncio
@patch('src.services.audio_service.filter_audio_tracks_combined')
async def test_search_audio_library_db_error(mock_db_call):
    """Test that DatabaseOperationError is propagated from search."""
    mock_db_call.side_effect = DatabaseOperationError("Search failed")
    
    with pytest.raises(DatabaseOperationError):
        await audio_service.search_audio_library("test", 20, 0)

# ============================================================================
# delete_audio_track_and_files Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.audio_service.delete_audio_track')
@patch('src.services.audio_service.GCSClient')
async def test_delete_audio_success(mock_gcs_client, mock_delete_db):
    """Test successful deletion of track and GCS files."""
    mock_delete_db.return_value = {"audio_gcs_path": "gs://bucket/audio.mp3", "thumbnail_gcs_path": "gs://bucket/art.jpg"}
    mock_gcs_instance = mock_gcs_client.return_value
    
    result = await audio_service.delete_audio_track_and_files("any_id")
    
    assert result is True
    mock_delete_db.assert_called_once_with("any_id")
    assert mock_gcs_instance.delete_file.call_count == 2
    mock_gcs_instance.delete_file.assert_any_call("audio.mp3")
    mock_gcs_instance.delete_file.assert_any_call("art.jpg")

@pytest.mark.asyncio
@patch('src.services.audio_service.delete_audio_track')
async def test_delete_audio_not_found(mock_delete_db):
    """Test that ResourceNotFoundError is raised when deleting a missing track."""
    mock_delete_db.side_effect = ResourceNotFoundError("Not found")
    
    with pytest.raises(ResourceNotFoundError):
        await audio_service.delete_audio_track_and_files("not_found_id")

@pytest.mark.asyncio
@patch('src.services.audio_service.delete_audio_track')
async def test_delete_audio_db_error(mock_delete_db):
    """Test that DatabaseOperationError is propagated on delete."""
    mock_delete_db.side_effect = DatabaseOperationError("Delete failed")
    
    with pytest.raises(DatabaseOperationError):
        await audio_service.delete_audio_track_and_files("any_id")
