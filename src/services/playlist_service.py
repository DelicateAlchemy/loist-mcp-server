"""
Service layer for playlist-related business logic.

This service centralizes operations for retrieving, creating, searching, and managing
playlists, separating business logic from the transport layer (MCP/HTTP).
"""

import logging
from typing import Dict, Any, List, Optional

from src.repositories import get_playlist_repository
from src.exceptions import (
    DatabaseOperationError,
    ResourceNotFoundError,
)

logger = logging.getLogger(__name__)


async def get_playlist(playlist_id: str) -> Dict[str, Any]:
    """
    Retrieve a playlist by ID with tracks and collaborators.

    Args:
        playlist_id: The UUID of the playlist.

    Returns:
        A dictionary containing playlist information with tracks and collaborators.

    Raises:
        ResourceNotFoundError: If the playlist is not found.
        DatabaseOperationError: If a database error occurs.
    """
    logger.debug(f"Service: Fetching playlist: {playlist_id}")
    playlist = get_playlist_repository().get_by_id(playlist_id)

    if not playlist:
        logger.warning(f"Service: Playlist not found: {playlist_id}")
        raise ResourceNotFoundError(f"Playlist with ID '{playlist_id}' was not found")

    return playlist


async def create_playlist(playlist_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new playlist.

    Args:
        playlist_data: Dictionary containing playlist fields:
            - name: str (required)
            - description: str (optional)
            - is_public: bool (optional, default False)
            - owner_id: str (optional)

    Returns:
        A dictionary containing the created playlist information.

    Raises:
        DatabaseOperationError: If the creation fails.
    """
    logger.debug(f"Service: Creating playlist: {playlist_data.get('name', 'unknown')}")

    try:
        result = get_playlist_repository().create(playlist_data)
        logger.info(f"Service: Created playlist {result.get('id')}")
        return result
    except Exception as e:
        logger.error(f"Service: Failed to create playlist: {e}")
        raise DatabaseOperationError(f"Failed to create playlist: {str(e)}")


async def update_playlist(playlist_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update playlist metadata.

    Args:
        playlist_id: The UUID of the playlist.
        update_data: Dictionary of fields to update.

    Returns:
        A dictionary containing the updated playlist information.

    Raises:
        ResourceNotFoundError: If the playlist is not found.
        DatabaseOperationError: If the update fails.
    """
    logger.debug(f"Service: Updating playlist {playlist_id}")

    try:
        result = get_playlist_repository().update(playlist_id, update_data)
        logger.info(f"Service: Updated playlist {playlist_id}")
        return result
    except ResourceNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Service: Failed to update playlist {playlist_id}: {e}")
        raise DatabaseOperationError(f"Failed to update playlist: {str(e)}")


async def delete_playlist(playlist_id: str) -> bool:
    """
    Delete a playlist.

    Args:
        playlist_id: The UUID of the playlist.

    Returns:
        True if the playlist was deleted.

    Raises:
        ResourceNotFoundError: If the playlist is not found.
        DatabaseOperationError: If the deletion fails.
    """
    logger.debug(f"Service: Deleting playlist {playlist_id}")

    try:
        result = get_playlist_repository().delete(playlist_id)
        if not result:
            raise ResourceNotFoundError(
                f"Playlist with ID '{playlist_id}' was not found"
            )
        logger.info(f"Service: Deleted playlist {playlist_id}")
        return result
    except ResourceNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Service: Failed to delete playlist {playlist_id}: {e}")
        raise DatabaseOperationError(f"Failed to delete playlist: {str(e)}")


async def search_playlists(
    query: str, limit: int = 20, offset: int = 0
) -> Dict[str, Any]:
    """
    Search playlists by name.

    Args:
        query: The search query string.
        limit: The maximum number of results to return.
        offset: The number of results to skip.

    Returns:
        A dictionary containing search results and pagination info.

    Raises:
        DatabaseOperationError: If the search fails.
    """
    logger.debug(
        f"Service: Searching playlists for '{query}' with limit={limit}, offset={offset}"
    )

    try:
        results = get_playlist_repository().search(query, limit=limit, offset=offset)

        return {
            "results": results,
            "total": len(results),
            "limit": limit,
            "offset": offset,
            "has_more": len(results) == limit,
        }
    except Exception as e:
        logger.error(f"Service: Failed to search playlists: {e}")
        raise DatabaseOperationError(f"Failed to search playlists: {str(e)}")


async def add_track_to_playlist(
    playlist_id: str,
    audio_track_id: str,
    position: Optional[int] = None,
    added_by: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Add a track to a playlist.

    Args:
        playlist_id: The UUID of the playlist.
        audio_track_id: The UUID of the audio track.
        position: Track position (auto-assigned if None).
        added_by: UUID of user adding the track (optional).

    Returns:
        A dictionary with the created playlist_track record.

    Raises:
        DatabaseOperationError: If the operation fails.
    """
    logger.debug(f"Service: Adding track {audio_track_id} to playlist {playlist_id}")

    try:
        result = get_playlist_repository().add_track(
            playlist_id, audio_track_id, position, added_by
        )
        logger.info(f"Service: Added track {audio_track_id} to playlist {playlist_id}")
        return result
    except Exception as e:
        logger.error(
            f"Service: Failed to add track {audio_track_id} to playlist {playlist_id}: {e}"
        )
        raise DatabaseOperationError(f"Failed to add track to playlist: {str(e)}")


async def remove_track_from_playlist(playlist_id: str, audio_track_id: str) -> bool:
    """
    Remove a track from a playlist.

    Args:
        playlist_id: The UUID of the playlist.
        audio_track_id: The UUID of the audio track.

    Returns:
        True if the track was removed.

    Raises:
        DatabaseOperationError: If the operation fails.
    """
    logger.debug(f"Service: Removing track {audio_track_id} from playlist {playlist_id}")

    try:
        result = get_playlist_repository().remove_track(playlist_id, audio_track_id)
        logger.info(
            f"Service: Removed track {audio_track_id} from playlist {playlist_id}"
        )
        return result
    except Exception as e:
        logger.error(
            f"Service: Failed to remove track {audio_track_id} "
            f"from playlist {playlist_id}: {e}"
        )
        raise DatabaseOperationError(f"Failed to remove track from playlist: {str(e)}")


async def reorder_playlist_tracks(
    playlist_id: str, track_order: List[str]
) -> Dict[str, Any]:
    """
    Reorder tracks in a playlist.

    Args:
        playlist_id: The UUID of the playlist.
        track_order: Ordered list of audio_track_ids.

    Returns:
        A dictionary with reorder result.

    Raises:
        DatabaseOperationError: If the operation fails.
    """
    logger.debug(
        f"Service: Reordering {len(track_order)} tracks in playlist {playlist_id}"
    )

    try:
        result = get_playlist_repository().reorder_tracks(playlist_id, track_order)
        logger.info(f"Service: Reordered tracks in playlist {playlist_id}")
        return result
    except Exception as e:
        logger.error(
            f"Service: Failed to reorder tracks in playlist {playlist_id}: {e}"
        )
        raise DatabaseOperationError(f"Failed to reorder playlist tracks: {str(e)}")


async def add_collaborator(
    playlist_id: str, user_id: str, role: str = "viewer"
) -> Dict[str, Any]:
    """
    Add or update a collaborator on a playlist.

    Args:
        playlist_id: The UUID of the playlist.
        user_id: The UUID of the collaborator.
        role: Collaboration role (viewer, editor, admin).

    Returns:
        A dictionary with the collaborator record.

    Raises:
        DatabaseOperationError: If the operation fails.
    """
    logger.debug(
        f"Service: Adding collaborator {user_id} to playlist {playlist_id} as {role}"
    )

    try:
        result = get_playlist_repository().add_collaborator(playlist_id, user_id, role)
        logger.info(
            f"Service: Added collaborator {user_id} to playlist {playlist_id}"
        )
        return result
    except Exception as e:
        logger.error(
            f"Service: Failed to add collaborator {user_id} "
            f"to playlist {playlist_id}: {e}"
        )
        raise DatabaseOperationError(f"Failed to add collaborator: {str(e)}")


async def remove_collaborator(playlist_id: str, user_id: str) -> bool:
    """
    Remove a collaborator from a playlist.

    Args:
        playlist_id: The UUID of the playlist.
        user_id: The UUID of the collaborator to remove.

    Returns:
        True if the collaborator was removed.

    Raises:
        DatabaseOperationError: If the operation fails.
    """
    logger.debug(
        f"Service: Removing collaborator {user_id} from playlist {playlist_id}"
    )

    try:
        result = get_playlist_repository().remove_collaborator(playlist_id, user_id)
        logger.info(
            f"Service: Removed collaborator {user_id} from playlist {playlist_id}"
        )
        return result
    except Exception as e:
        logger.error(
            f"Service: Failed to remove collaborator {user_id} "
            f"from playlist {playlist_id}: {e}"
        )
        raise DatabaseOperationError(f"Failed to remove collaborator: {str(e)}")
