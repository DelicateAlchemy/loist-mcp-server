"""
Unit tests for the album_service layer.

These tests mock the repository to test the service's business logic in isolation.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.services import album_service
from src.exceptions import ResourceNotFoundError, DatabaseOperationError

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_album():
    """Mock album data with tracks."""
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "My Album",
        "description": "Test album",
        "status": "project",
        "cover_art_gcs_path": None,
        "owner_id": None,
        "tracks": [],
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }

@pytest.fixture
def mock_album_list():
    """Mock list of albums from search."""
    return [
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "First Album",
            "status": "project",
            "track_count": 5,
        },
        {
            "id": "660e8400-e29b-41d4-a716-446655440001",
            "name": "First EP",
            "status": "draft",
            "track_count": 3,
        },
    ]

@pytest.fixture
def mock_album_track():
    """Mock album track record."""
    return {
        "id": "track-link-1",
        "album_id": "550e8400-e29b-41d4-a716-446655440000",
        "audio_track_id": "audio-1",
        "position": 1,
        "disc_number": 1,
        "added_at": "2024-01-01T00:00:00Z",
    }

# ============================================================================
# get_album Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.album_service.get_album_repository')
async def test_get_album_success(mock_get_repo, mock_album):
    """Test successful album retrieval in the service."""
    mock_repo = MagicMock()
    mock_repo.get_by_id.return_value = mock_album
    mock_get_repo.return_value = mock_repo

    result = await album_service.get_album("any_id")

    mock_repo.get_by_id.assert_called_once_with("any_id")
    assert result["id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert result["name"] == "My Album"
    assert "tracks" in result

@pytest.mark.asyncio
@patch('src.services.album_service.get_album_repository')
async def test_get_album_not_found(mock_get_repo):
    """Test that ResourceNotFoundError is raised for a missing album."""
    mock_repo = MagicMock()
    mock_repo.get_by_id.return_value = None
    mock_get_repo.return_value = mock_repo

    with pytest.raises(ResourceNotFoundError):
        await album_service.get_album("not_found_id")

    mock_repo.get_by_id.assert_called_once_with("not_found_id")

@pytest.mark.asyncio
@patch('src.services.album_service.get_album_repository')
async def test_get_album_db_error(mock_get_repo):
    """Test that DatabaseOperationError is propagated."""
    mock_repo = MagicMock()
    mock_repo.get_by_id.side_effect = DatabaseOperationError("Connection failed")
    mock_get_repo.return_value = mock_repo

    with pytest.raises(DatabaseOperationError):
        await album_service.get_album("any_id")

# ============================================================================
# create_album Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.album_service.get_album_repository')
async def test_create_album_success(mock_get_repo, mock_album):
    """Test successful album creation in the service."""
    mock_repo = MagicMock()
    mock_repo.create.return_value = mock_album
    mock_get_repo.return_value = mock_repo

    album_data = {"name": "My Album", "status": "project"}

    result = await album_service.create_album(album_data)

    mock_repo.create.assert_called_once_with(album_data)
    assert result["id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert result["name"] == "My Album"

@pytest.mark.asyncio
@patch('src.services.album_service.get_album_repository')
async def test_create_album_db_error(mock_get_repo):
    """Test that DatabaseOperationError is raised on creation failure."""
    mock_repo = MagicMock()
    mock_repo.create.side_effect = Exception("Database error")
    mock_get_repo.return_value = mock_repo

    with pytest.raises(DatabaseOperationError):
        await album_service.create_album({"name": "Fail Album"})

# ============================================================================
# update_album Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.album_service.get_album_repository')
async def test_update_album_success(mock_get_repo, mock_album):
    """Test successful album update in the service."""
    updated = {**mock_album, "name": "Updated Album"}
    mock_repo = MagicMock()
    mock_repo.update.return_value = updated
    mock_get_repo.return_value = mock_repo

    result = await album_service.update_album("album-1", {"name": "Updated Album"})

    mock_repo.update.assert_called_once_with("album-1", {"name": "Updated Album"})
    assert result["name"] == "Updated Album"

@pytest.mark.asyncio
@patch('src.services.album_service.get_album_repository')
async def test_update_album_not_found(mock_get_repo):
    """Test that ResourceNotFoundError is propagated from update."""
    mock_repo = MagicMock()
    mock_repo.update.side_effect = ResourceNotFoundError("Album not found")
    mock_get_repo.return_value = mock_repo

    with pytest.raises(ResourceNotFoundError):
        await album_service.update_album("missing-id", {"name": "X"})

@pytest.mark.asyncio
@patch('src.services.album_service.get_album_repository')
async def test_update_album_db_error(mock_get_repo):
    """Test that DatabaseOperationError is raised on update failure."""
    mock_repo = MagicMock()
    mock_repo.update.side_effect = Exception("Database error")
    mock_get_repo.return_value = mock_repo

    with pytest.raises(DatabaseOperationError):
        await album_service.update_album("album-1", {"name": "X"})

# ============================================================================
# delete_album Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.album_service.get_album_repository')
async def test_delete_album_success(mock_get_repo):
    """Test successful album deletion."""
    mock_repo = MagicMock()
    mock_repo.delete.return_value = True
    mock_get_repo.return_value = mock_repo

    result = await album_service.delete_album("album-1")

    mock_repo.delete.assert_called_once_with("album-1")
    assert result is True

@pytest.mark.asyncio
@patch('src.services.album_service.get_album_repository')
async def test_delete_album_not_found(mock_get_repo):
    """Test that ResourceNotFoundError is raised when album not found."""
    mock_repo = MagicMock()
    mock_repo.delete.return_value = False
    mock_get_repo.return_value = mock_repo

    with pytest.raises(ResourceNotFoundError):
        await album_service.delete_album("missing-id")

@pytest.mark.asyncio
@patch('src.services.album_service.get_album_repository')
async def test_delete_album_db_error(mock_get_repo):
    """Test that DatabaseOperationError is raised on deletion failure."""
    mock_repo = MagicMock()
    mock_repo.delete.side_effect = Exception("Database error")
    mock_get_repo.return_value = mock_repo

    with pytest.raises(DatabaseOperationError):
        await album_service.delete_album("album-1")

# ============================================================================
# search_albums Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.album_service.get_album_repository')
async def test_search_albums_success(mock_get_repo, mock_album_list):
    """Test successful album search in the service."""
    mock_repo = MagicMock()
    mock_repo.search.return_value = mock_album_list
    mock_get_repo.return_value = mock_repo

    result = await album_service.search_albums("First", limit=20, offset=0)

    mock_repo.search.assert_called_once_with("First", limit=20, offset=0, status=None)
    assert len(result["results"]) == 2
    assert result["total"] == 2
    assert result["limit"] == 20
    assert result["offset"] == 0
    assert result["has_more"] is False

@pytest.mark.asyncio
@patch('src.services.album_service.get_album_repository')
async def test_search_albums_with_status_filter(mock_get_repo, mock_album_list):
    """Test album search with status filter."""
    mock_repo = MagicMock()
    mock_repo.search.return_value = [mock_album_list[0]]
    mock_get_repo.return_value = mock_repo

    result = await album_service.search_albums("First", limit=20, offset=0, status="project")

    mock_repo.search.assert_called_once_with("First", limit=20, offset=0, status="project")
    assert len(result["results"]) == 1

@pytest.mark.asyncio
@patch('src.services.album_service.get_album_repository')
async def test_search_albums_has_more(mock_get_repo):
    """Test search with has_more flag when results equal limit."""
    mock_repo = MagicMock()
    mock_repo.search.return_value = [{"id": f"id-{i}"} for i in range(20)]
    mock_get_repo.return_value = mock_repo

    result = await album_service.search_albums("test", limit=20, offset=0)

    assert result["has_more"] is True

@pytest.mark.asyncio
@patch('src.services.album_service.get_album_repository')
async def test_search_albums_db_error(mock_get_repo):
    """Test that DatabaseOperationError is propagated from search."""
    mock_repo = MagicMock()
    mock_repo.search.side_effect = Exception("Search failed")
    mock_get_repo.return_value = mock_repo

    with pytest.raises(DatabaseOperationError):
        await album_service.search_albums("test", limit=20, offset=0)

# ============================================================================
# add_track_to_album Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.album_service.get_album_repository')
async def test_add_track_to_album_success(mock_get_repo, mock_album_track):
    """Test successful track addition to album."""
    mock_repo = MagicMock()
    mock_repo.add_track.return_value = mock_album_track
    mock_get_repo.return_value = mock_repo

    result = await album_service.add_track_to_album("album-1", "audio-1", position=1, disc_number=1)

    mock_repo.add_track.assert_called_once_with("album-1", "audio-1", 1, 1)
    assert result["audio_track_id"] == "audio-1"
    assert result["position"] == 1

@pytest.mark.asyncio
@patch('src.services.album_service.get_album_repository')
async def test_add_track_to_album_auto_position(mock_get_repo, mock_album_track):
    """Test track addition with auto-assigned position."""
    mock_repo = MagicMock()
    mock_repo.add_track.return_value = mock_album_track
    mock_get_repo.return_value = mock_repo

    result = await album_service.add_track_to_album("album-1", "audio-1")

    mock_repo.add_track.assert_called_once_with("album-1", "audio-1", None, 1)

@pytest.mark.asyncio
@patch('src.services.album_service.get_album_repository')
async def test_add_track_to_album_db_error(mock_get_repo):
    """Test that DatabaseOperationError is raised on add track failure."""
    mock_repo = MagicMock()
    mock_repo.add_track.side_effect = Exception("Integrity error")
    mock_get_repo.return_value = mock_repo

    with pytest.raises(DatabaseOperationError):
        await album_service.add_track_to_album("album-1", "audio-1")

# ============================================================================
# remove_track_from_album Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.album_service.get_album_repository')
async def test_remove_track_from_album_success(mock_get_repo):
    """Test successful track removal from album."""
    mock_repo = MagicMock()
    mock_repo.remove_track.return_value = True
    mock_get_repo.return_value = mock_repo

    result = await album_service.remove_track_from_album("album-1", "audio-1")

    mock_repo.remove_track.assert_called_once_with("album-1", "audio-1")
    assert result is True

@pytest.mark.asyncio
@patch('src.services.album_service.get_album_repository')
async def test_remove_track_from_album_db_error(mock_get_repo):
    """Test that DatabaseOperationError is raised on remove track failure."""
    mock_repo = MagicMock()
    mock_repo.remove_track.side_effect = Exception("Database error")
    mock_get_repo.return_value = mock_repo

    with pytest.raises(DatabaseOperationError):
        await album_service.remove_track_from_album("album-1", "audio-1")

# ============================================================================
# reorder_album_tracks Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.album_service.get_album_repository')
async def test_reorder_album_tracks_success(mock_get_repo):
    """Test successful track reordering in album."""
    mock_repo = MagicMock()
    mock_repo.reorder_tracks.return_value = {"updated_count": 3}
    mock_get_repo.return_value = mock_repo

    track_order = ["track-3", "track-1", "track-2"]
    result = await album_service.reorder_album_tracks("album-1", track_order)

    mock_repo.reorder_tracks.assert_called_once_with("album-1", track_order)
    assert result["updated_count"] == 3

@pytest.mark.asyncio
@patch('src.services.album_service.get_album_repository')
async def test_reorder_album_tracks_db_error(mock_get_repo):
    """Test that DatabaseOperationError is raised on reorder failure."""
    mock_repo = MagicMock()
    mock_repo.reorder_tracks.side_effect = Exception("Database error")
    mock_get_repo.return_value = mock_repo

    with pytest.raises(DatabaseOperationError):
        await album_service.reorder_album_tracks("album-1", ["track-1"])
