"""
Unit tests for the playlist_service layer.

These tests mock the repository to test the service's business logic in isolation.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.services import playlist_service
from src.exceptions import ResourceNotFoundError, DatabaseOperationError

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_playlist():
    """Mock playlist data with tracks and collaborators."""
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "My Playlist",
        "description": "Test playlist",
        "is_public": False,
        "owner_id": None,
        "tracks": [],
        "collaborators": [],
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }

@pytest.fixture
def mock_playlist_list():
    """Mock list of playlists from search."""
    return [
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "Favorites",
            "is_public": True,
            "track_count": 10,
        },
        {
            "id": "660e8400-e29b-41d4-a716-446655440001",
            "name": "Favs 2024",
            "is_public": False,
            "track_count": 5,
        },
    ]

@pytest.fixture
def mock_playlist_track():
    """Mock playlist track record."""
    return {
        "id": "track-link-1",
        "playlist_id": "550e8400-e29b-41d4-a716-446655440000",
        "audio_track_id": "audio-1",
        "position": 1,
        "added_by": None,
        "added_at": "2024-01-01T00:00:00Z",
    }

@pytest.fixture
def mock_collaborator():
    """Mock collaborator record."""
    return {
        "id": "collab-1",
        "playlist_id": "550e8400-e29b-41d4-a716-446655440000",
        "user_id": "user-1",
        "role": "editor",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }

# ============================================================================
# get_playlist Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.playlist_service.get_playlist_repository')
async def test_get_playlist_success(mock_get_repo, mock_playlist):
    """Test successful playlist retrieval in the service."""
    mock_repo = MagicMock()
    mock_repo.get_by_id.return_value = mock_playlist
    mock_get_repo.return_value = mock_repo

    result = await playlist_service.get_playlist("any_id")

    mock_repo.get_by_id.assert_called_once_with("any_id")
    assert result["id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert result["name"] == "My Playlist"
    assert "tracks" in result
    assert "collaborators" in result

@pytest.mark.asyncio
@patch('src.services.playlist_service.get_playlist_repository')
async def test_get_playlist_not_found(mock_get_repo):
    """Test that ResourceNotFoundError is raised for a missing playlist."""
    mock_repo = MagicMock()
    mock_repo.get_by_id.return_value = None
    mock_get_repo.return_value = mock_repo

    with pytest.raises(ResourceNotFoundError):
        await playlist_service.get_playlist("not_found_id")

    mock_repo.get_by_id.assert_called_once_with("not_found_id")

@pytest.mark.asyncio
@patch('src.services.playlist_service.get_playlist_repository')
async def test_get_playlist_db_error(mock_get_repo):
    """Test that DatabaseOperationError is propagated."""
    mock_repo = MagicMock()
    mock_repo.get_by_id.side_effect = DatabaseOperationError("Connection failed")
    mock_get_repo.return_value = mock_repo

    with pytest.raises(DatabaseOperationError):
        await playlist_service.get_playlist("any_id")

# ============================================================================
# create_playlist Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.playlist_service.get_playlist_repository')
async def test_create_playlist_success(mock_get_repo, mock_playlist):
    """Test successful playlist creation in the service."""
    mock_repo = MagicMock()
    mock_repo.create.return_value = mock_playlist
    mock_get_repo.return_value = mock_repo

    playlist_data = {"name": "My Playlist", "is_public": False}

    result = await playlist_service.create_playlist(playlist_data)

    mock_repo.create.assert_called_once_with(playlist_data)
    assert result["id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert result["name"] == "My Playlist"

@pytest.mark.asyncio
@patch('src.services.playlist_service.get_playlist_repository')
async def test_create_playlist_db_error(mock_get_repo):
    """Test that DatabaseOperationError is raised on creation failure."""
    mock_repo = MagicMock()
    mock_repo.create.side_effect = Exception("Database error")
    mock_get_repo.return_value = mock_repo

    with pytest.raises(DatabaseOperationError):
        await playlist_service.create_playlist({"name": "Fail Playlist"})

# ============================================================================
# update_playlist Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.playlist_service.get_playlist_repository')
async def test_update_playlist_success(mock_get_repo, mock_playlist):
    """Test successful playlist update in the service."""
    updated = {**mock_playlist, "name": "Updated Playlist"}
    mock_repo = MagicMock()
    mock_repo.update.return_value = updated
    mock_get_repo.return_value = mock_repo

    result = await playlist_service.update_playlist("playlist-1", {"name": "Updated Playlist"})

    mock_repo.update.assert_called_once_with("playlist-1", {"name": "Updated Playlist"})
    assert result["name"] == "Updated Playlist"

@pytest.mark.asyncio
@patch('src.services.playlist_service.get_playlist_repository')
async def test_update_playlist_not_found(mock_get_repo):
    """Test that ResourceNotFoundError is propagated from update."""
    mock_repo = MagicMock()
    mock_repo.update.side_effect = ResourceNotFoundError("Playlist not found")
    mock_get_repo.return_value = mock_repo

    with pytest.raises(ResourceNotFoundError):
        await playlist_service.update_playlist("missing-id", {"name": "X"})

@pytest.mark.asyncio
@patch('src.services.playlist_service.get_playlist_repository')
async def test_update_playlist_db_error(mock_get_repo):
    """Test that DatabaseOperationError is raised on update failure."""
    mock_repo = MagicMock()
    mock_repo.update.side_effect = Exception("Database error")
    mock_get_repo.return_value = mock_repo

    with pytest.raises(DatabaseOperationError):
        await playlist_service.update_playlist("playlist-1", {"name": "X"})

# ============================================================================
# delete_playlist Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.playlist_service.get_playlist_repository')
async def test_delete_playlist_success(mock_get_repo):
    """Test successful playlist deletion."""
    mock_repo = MagicMock()
    mock_repo.delete.return_value = True
    mock_get_repo.return_value = mock_repo

    result = await playlist_service.delete_playlist("playlist-1")

    mock_repo.delete.assert_called_once_with("playlist-1")
    assert result is True

@pytest.mark.asyncio
@patch('src.services.playlist_service.get_playlist_repository')
async def test_delete_playlist_not_found(mock_get_repo):
    """Test that ResourceNotFoundError is raised when playlist not found."""
    mock_repo = MagicMock()
    mock_repo.delete.return_value = False
    mock_get_repo.return_value = mock_repo

    with pytest.raises(ResourceNotFoundError):
        await playlist_service.delete_playlist("missing-id")

@pytest.mark.asyncio
@patch('src.services.playlist_service.get_playlist_repository')
async def test_delete_playlist_db_error(mock_get_repo):
    """Test that DatabaseOperationError is raised on deletion failure."""
    mock_repo = MagicMock()
    mock_repo.delete.side_effect = Exception("Database error")
    mock_get_repo.return_value = mock_repo

    with pytest.raises(DatabaseOperationError):
        await playlist_service.delete_playlist("playlist-1")

# ============================================================================
# search_playlists Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.playlist_service.get_playlist_repository')
async def test_search_playlists_success(mock_get_repo, mock_playlist_list):
    """Test successful playlist search in the service."""
    mock_repo = MagicMock()
    mock_repo.search.return_value = mock_playlist_list
    mock_get_repo.return_value = mock_repo

    result = await playlist_service.search_playlists("Fav", limit=20, offset=0)

    mock_repo.search.assert_called_once_with("Fav", limit=20, offset=0)
    assert len(result["results"]) == 2
    assert result["total"] == 2
    assert result["limit"] == 20
    assert result["offset"] == 0
    assert result["has_more"] is False

@pytest.mark.asyncio
@patch('src.services.playlist_service.get_playlist_repository')
async def test_search_playlists_has_more(mock_get_repo):
    """Test search with has_more flag when results equal limit."""
    mock_repo = MagicMock()
    mock_repo.search.return_value = [{"id": f"id-{i}"} for i in range(20)]
    mock_get_repo.return_value = mock_repo

    result = await playlist_service.search_playlists("test", limit=20, offset=0)

    assert result["has_more"] is True

@pytest.mark.asyncio
@patch('src.services.playlist_service.get_playlist_repository')
async def test_search_playlists_db_error(mock_get_repo):
    """Test that DatabaseOperationError is propagated from search."""
    mock_repo = MagicMock()
    mock_repo.search.side_effect = Exception("Search failed")
    mock_get_repo.return_value = mock_repo

    with pytest.raises(DatabaseOperationError):
        await playlist_service.search_playlists("test", limit=20, offset=0)

# ============================================================================
# add_track_to_playlist Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.playlist_service.get_playlist_repository')
async def test_add_track_to_playlist_success(mock_get_repo, mock_playlist_track):
    """Test successful track addition to playlist."""
    mock_repo = MagicMock()
    mock_repo.add_track.return_value = mock_playlist_track
    mock_get_repo.return_value = mock_repo

    result = await playlist_service.add_track_to_playlist(
        "playlist-1", "audio-1", position=1, added_by="user-1"
    )

    mock_repo.add_track.assert_called_once_with("playlist-1", "audio-1", 1, "user-1")
    assert result["audio_track_id"] == "audio-1"
    assert result["position"] == 1

@pytest.mark.asyncio
@patch('src.services.playlist_service.get_playlist_repository')
async def test_add_track_to_playlist_auto_position(mock_get_repo, mock_playlist_track):
    """Test track addition with auto-assigned position."""
    mock_repo = MagicMock()
    mock_repo.add_track.return_value = mock_playlist_track
    mock_get_repo.return_value = mock_repo

    await playlist_service.add_track_to_playlist("playlist-1", "audio-1")

    mock_repo.add_track.assert_called_once_with("playlist-1", "audio-1", None, None)

@pytest.mark.asyncio
@patch('src.services.playlist_service.get_playlist_repository')
async def test_add_track_to_playlist_db_error(mock_get_repo):
    """Test that DatabaseOperationError is raised on add track failure."""
    mock_repo = MagicMock()
    mock_repo.add_track.side_effect = Exception("Integrity error")
    mock_get_repo.return_value = mock_repo

    with pytest.raises(DatabaseOperationError):
        await playlist_service.add_track_to_playlist("playlist-1", "audio-1")

# ============================================================================
# remove_track_from_playlist Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.playlist_service.get_playlist_repository')
async def test_remove_track_from_playlist_success(mock_get_repo):
    """Test successful track removal from playlist."""
    mock_repo = MagicMock()
    mock_repo.remove_track.return_value = True
    mock_get_repo.return_value = mock_repo

    result = await playlist_service.remove_track_from_playlist("playlist-1", "audio-1")

    mock_repo.remove_track.assert_called_once_with("playlist-1", "audio-1")
    assert result is True

@pytest.mark.asyncio
@patch('src.services.playlist_service.get_playlist_repository')
async def test_remove_track_from_playlist_db_error(mock_get_repo):
    """Test that DatabaseOperationError is raised on remove track failure."""
    mock_repo = MagicMock()
    mock_repo.remove_track.side_effect = Exception("Database error")
    mock_get_repo.return_value = mock_repo

    with pytest.raises(DatabaseOperationError):
        await playlist_service.remove_track_from_playlist("playlist-1", "audio-1")

# ============================================================================
# reorder_playlist_tracks Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.playlist_service.get_playlist_repository')
async def test_reorder_playlist_tracks_success(mock_get_repo):
    """Test successful track reordering in playlist."""
    mock_repo = MagicMock()
    mock_repo.reorder_tracks.return_value = {"updated_count": 3}
    mock_get_repo.return_value = mock_repo

    track_order = ["track-3", "track-1", "track-2"]
    result = await playlist_service.reorder_playlist_tracks("playlist-1", track_order)

    mock_repo.reorder_tracks.assert_called_once_with("playlist-1", track_order)
    assert result["updated_count"] == 3

@pytest.mark.asyncio
@patch('src.services.playlist_service.get_playlist_repository')
async def test_reorder_playlist_tracks_db_error(mock_get_repo):
    """Test that DatabaseOperationError is raised on reorder failure."""
    mock_repo = MagicMock()
    mock_repo.reorder_tracks.side_effect = Exception("Database error")
    mock_get_repo.return_value = mock_repo

    with pytest.raises(DatabaseOperationError):
        await playlist_service.reorder_playlist_tracks("playlist-1", ["track-1"])

# ============================================================================
# add_collaborator Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.playlist_service.get_playlist_repository')
async def test_add_collaborator_success(mock_get_repo, mock_collaborator):
    """Test successful collaborator addition."""
    mock_repo = MagicMock()
    mock_repo.add_collaborator.return_value = mock_collaborator
    mock_get_repo.return_value = mock_repo

    result = await playlist_service.add_collaborator("playlist-1", "user-1", "editor")

    mock_repo.add_collaborator.assert_called_once_with("playlist-1", "user-1", "editor")
    assert result["user_id"] == "user-1"
    assert result["role"] == "editor"

@pytest.mark.asyncio
@patch('src.services.playlist_service.get_playlist_repository')
async def test_add_collaborator_default_role(mock_get_repo, mock_collaborator):
    """Test collaborator addition with default viewer role."""
    viewer_collab = {**mock_collaborator, "role": "viewer"}
    mock_repo = MagicMock()
    mock_repo.add_collaborator.return_value = viewer_collab
    mock_get_repo.return_value = mock_repo

    result = await playlist_service.add_collaborator("playlist-1", "user-1")

    mock_repo.add_collaborator.assert_called_once_with("playlist-1", "user-1", "viewer")
    assert result["role"] == "viewer"

@pytest.mark.asyncio
@patch('src.services.playlist_service.get_playlist_repository')
async def test_add_collaborator_db_error(mock_get_repo):
    """Test that DatabaseOperationError is raised on collaborator add failure."""
    mock_repo = MagicMock()
    mock_repo.add_collaborator.side_effect = Exception("Database error")
    mock_get_repo.return_value = mock_repo

    with pytest.raises(DatabaseOperationError):
        await playlist_service.add_collaborator("playlist-1", "user-1", "editor")

# ============================================================================
# remove_collaborator Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.playlist_service.get_playlist_repository')
async def test_remove_collaborator_success(mock_get_repo):
    """Test successful collaborator removal."""
    mock_repo = MagicMock()
    mock_repo.remove_collaborator.return_value = True
    mock_get_repo.return_value = mock_repo

    result = await playlist_service.remove_collaborator("playlist-1", "user-1")

    mock_repo.remove_collaborator.assert_called_once_with("playlist-1", "user-1")
    assert result is True

@pytest.mark.asyncio
@patch('src.services.playlist_service.get_playlist_repository')
async def test_remove_collaborator_db_error(mock_get_repo):
    """Test that DatabaseOperationError is raised on collaborator removal failure."""
    mock_repo = MagicMock()
    mock_repo.remove_collaborator.side_effect = Exception("Database error")
    mock_get_repo.return_value = mock_repo

    with pytest.raises(DatabaseOperationError):
        await playlist_service.remove_collaborator("playlist-1", "user-1")
