"""
Service layer for album-related business logic.

This service centralizes operations for retrieving, creating, searching, and managing
albums, separating business logic from the transport layer (MCP/HTTP).
"""

import logging
from typing import Dict, Any, List, Optional

from src.repositories import get_album_repository
from src.exceptions import (
    DatabaseOperationError,
    ResourceNotFoundError,
)

logger = logging.getLogger(__name__)


async def get_album(album_id: str) -> Dict[str, Any]:
    """
    Retrieve an album by ID with all tracks.

    Args:
        album_id: The UUID of the album.

    Returns:
        A dictionary containing album information with tracks.

    Raises:
        ResourceNotFoundError: If the album is not found.
        DatabaseOperationError: If a database error occurs.
    """
    logger.debug(f"Service: Fetching album: {album_id}")
    album = get_album_repository().get_by_id(album_id)

    if not album:
        logger.warning(f"Service: Album not found: {album_id}")
        raise ResourceNotFoundError(f"Album with ID '{album_id}' was not found")

    return album


async def create_album(album_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new album.

    Args:
        album_data: Dictionary containing album fields:
            - name: str (required)
            - description: str (optional)
            - status: str (optional, default 'project')
            - cover_art_gcs_path: str (optional)
            - owner_id: str (optional)

    Returns:
        A dictionary containing the created album information.

    Raises:
        DatabaseOperationError: If the creation fails.
    """
    logger.debug(f"Service: Creating album: {album_data.get('name', 'unknown')}")

    try:
        result = get_album_repository().create(album_data)
        logger.info(f"Service: Created album {result.get('id')}")
        return result
    except Exception as e:
        logger.error(f"Service: Failed to create album: {e}")
        raise DatabaseOperationError(f"Failed to create album: {str(e)}")


async def update_album(album_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update album metadata.

    Args:
        album_id: The UUID of the album.
        update_data: Dictionary of fields to update.

    Returns:
        A dictionary containing the updated album information.

    Raises:
        ResourceNotFoundError: If the album is not found.
        DatabaseOperationError: If the update fails.
    """
    logger.debug(f"Service: Updating album {album_id}")

    try:
        result = get_album_repository().update(album_id, update_data)
        logger.info(f"Service: Updated album {album_id}")
        return result
    except ResourceNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Service: Failed to update album {album_id}: {e}")
        raise DatabaseOperationError(f"Failed to update album: {str(e)}")


async def delete_album(album_id: str) -> bool:
    """
    Delete an album.

    Args:
        album_id: The UUID of the album.

    Returns:
        True if the album was deleted.

    Raises:
        ResourceNotFoundError: If the album is not found.
        DatabaseOperationError: If the deletion fails.
    """
    logger.debug(f"Service: Deleting album {album_id}")

    try:
        result = get_album_repository().delete(album_id)
        if not result:
            raise ResourceNotFoundError(f"Album with ID '{album_id}' was not found")
        logger.info(f"Service: Deleted album {album_id}")
        return result
    except ResourceNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Service: Failed to delete album {album_id}: {e}")
        raise DatabaseOperationError(f"Failed to delete album: {str(e)}")


async def search_albums(
    query: str, limit: int = 20, offset: int = 0, status: Optional[str] = None
) -> Dict[str, Any]:
    """
    Search albums by name.

    Args:
        query: The search query string.
        limit: The maximum number of results to return.
        offset: The number of results to skip.
        status: Optional status filter.

    Returns:
        A dictionary containing search results and pagination info.

    Raises:
        DatabaseOperationError: If the search fails.
    """
    logger.debug(
        f"Service: Searching albums for '{query}' with limit={limit}, offset={offset}"
    )

    try:
        results = get_album_repository().search(
            query, limit=limit, offset=offset, status=status
        )

        return {
            "results": results,
            "total": len(results),
            "limit": limit,
            "offset": offset,
            "has_more": len(results) == limit,
        }
    except Exception as e:
        logger.error(f"Service: Failed to search albums: {e}")
        raise DatabaseOperationError(f"Failed to search albums: {str(e)}")


async def add_track_to_album(
    album_id: str,
    audio_track_id: str,
    position: Optional[int] = None,
    disc_number: int = 1,
) -> Dict[str, Any]:
    """
    Add a track to an album.

    Args:
        album_id: The UUID of the album.
        audio_track_id: The UUID of the audio track.
        position: Track position (auto-assigned if None).
        disc_number: Disc number (default 1).

    Returns:
        A dictionary with the created album_track record.

    Raises:
        DatabaseOperationError: If the operation fails.
    """
    logger.debug(f"Service: Adding track {audio_track_id} to album {album_id}")

    try:
        result = get_album_repository().add_track(
            album_id, audio_track_id, position, disc_number
        )
        logger.info(f"Service: Added track {audio_track_id} to album {album_id}")
        return result
    except Exception as e:
        logger.error(
            f"Service: Failed to add track {audio_track_id} to album {album_id}: {e}"
        )
        raise DatabaseOperationError(f"Failed to add track to album: {str(e)}")


async def remove_track_from_album(album_id: str, audio_track_id: str) -> bool:
    """
    Remove a track from an album.

    Args:
        album_id: The UUID of the album.
        audio_track_id: The UUID of the audio track.

    Returns:
        True if the track was removed.

    Raises:
        DatabaseOperationError: If the operation fails.
    """
    logger.debug(f"Service: Removing track {audio_track_id} from album {album_id}")

    try:
        result = get_album_repository().remove_track(album_id, audio_track_id)
        logger.info(f"Service: Removed track {audio_track_id} from album {album_id}")
        return result
    except Exception as e:
        logger.error(
            f"Service: Failed to remove track {audio_track_id} from album {album_id}: {e}"
        )
        raise DatabaseOperationError(f"Failed to remove track from album: {str(e)}")


async def reorder_album_tracks(
    album_id: str, track_order: List[str]
) -> Dict[str, Any]:
    """
    Reorder tracks in an album.

    Args:
        album_id: The UUID of the album.
        track_order: Ordered list of audio_track_ids.

    Returns:
        A dictionary with reorder result.

    Raises:
        DatabaseOperationError: If the operation fails.
    """
    logger.debug(f"Service: Reordering {len(track_order)} tracks in album {album_id}")

    try:
        result = get_album_repository().reorder_tracks(album_id, track_order)
        logger.info(f"Service: Reordered tracks in album {album_id}")
        return result
    except Exception as e:
        logger.error(f"Service: Failed to reorder tracks in album {album_id}: {e}")
        raise DatabaseOperationError(f"Failed to reorder album tracks: {str(e)}")
