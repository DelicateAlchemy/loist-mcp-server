"""
Playlist Repository Abstraction Layer

Provides clean data access interface for playlists, decoupling
business logic from database implementation details.
"""

import logging
import os
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod

from database.operations import (
    create_playlist,
    get_playlist_by_id,
    update_playlist,
    delete_playlist,
    search_playlists,
    add_track_to_playlist,
    remove_track_from_playlist,
    reorder_playlist_tracks,
    add_playlist_collaborator,
    remove_playlist_collaborator,
)

logger = logging.getLogger(__name__)


class PlaylistRepositoryInterface(ABC):
    """Abstract interface for playlist data operations."""

    @abstractmethod
    def create(self, playlist_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new playlist."""
        pass

    @abstractmethod
    def get_by_id(self, playlist_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve playlist by ID with tracks and collaborators."""
        pass

    @abstractmethod
    def update(self, playlist_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update playlist metadata."""
        pass

    @abstractmethod
    def delete(self, playlist_id: str) -> bool:
        """Delete a playlist."""
        pass

    @abstractmethod
    def search(self, query: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """Search playlists by name."""
        pass

    @abstractmethod
    def add_track(
        self,
        playlist_id: str,
        audio_track_id: str,
        position: Optional[int] = None,
        added_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a track to a playlist."""
        pass

    @abstractmethod
    def remove_track(self, playlist_id: str, audio_track_id: str) -> bool:
        """Remove a track from a playlist."""
        pass

    @abstractmethod
    def reorder_tracks(self, playlist_id: str, track_order: List[str]) -> Dict[str, Any]:
        """Reorder tracks in a playlist."""
        pass

    @abstractmethod
    def add_collaborator(self, playlist_id: str, user_id: str, role: str = "viewer") -> Dict[str, Any]:
        """Add or update a collaborator on a playlist."""
        pass

    @abstractmethod
    def remove_collaborator(self, playlist_id: str, user_id: str) -> bool:
        """Remove a collaborator from a playlist."""
        pass


class PostgresPlaylistRepository(PlaylistRepositoryInterface):
    """PostgreSQL implementation of playlist repository."""

    def create(self, playlist_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new playlist."""
        try:
            result = create_playlist(playlist_data)
            logger.debug(f"Created playlist: {result.get('id', 'unknown')}")
            return result
        except Exception as e:
            logger.error(f"Failed to create playlist: {e}")
            raise

    def get_by_id(self, playlist_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve playlist by ID with tracks and collaborators."""
        try:
            result = get_playlist_by_id(playlist_id)
            if result:
                logger.debug(f"Retrieved playlist: {playlist_id}")
            else:
                logger.debug(f"No playlist found: {playlist_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to retrieve playlist {playlist_id}: {e}")
            raise

    def update(self, playlist_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update playlist metadata."""
        try:
            result = update_playlist(playlist_id, update_data)
            logger.debug(f"Updated playlist: {playlist_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to update playlist {playlist_id}: {e}")
            raise

    def delete(self, playlist_id: str) -> bool:
        """Delete a playlist."""
        try:
            result = delete_playlist(playlist_id)
            logger.debug(f"Deleted playlist: {playlist_id} (success={result})")
            return result
        except Exception as e:
            logger.error(f"Failed to delete playlist {playlist_id}: {e}")
            raise

    def search(self, query: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """Search playlists by name."""
        try:
            result = search_playlists(query, limit=limit, offset=offset)
            logger.debug(f"Search '{query}' returned {len(result)} playlists")
            return result
        except Exception as e:
            logger.error(f"Failed to search playlists for query '{query}': {e}")
            raise

    def add_track(
        self,
        playlist_id: str,
        audio_track_id: str,
        position: Optional[int] = None,
        added_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a track to a playlist."""
        try:
            result = add_track_to_playlist(playlist_id, audio_track_id, position, added_by)
            logger.debug(f"Added track {audio_track_id} to playlist {playlist_id}")
            return result
        except Exception as e:
            logger.error(
                f"Failed to add track {audio_track_id} to playlist {playlist_id}: {e}"
            )
            raise

    def remove_track(self, playlist_id: str, audio_track_id: str) -> bool:
        """Remove a track from a playlist."""
        try:
            result = remove_track_from_playlist(playlist_id, audio_track_id)
            logger.debug(f"Removed track {audio_track_id} from playlist {playlist_id}")
            return result
        except Exception as e:
            logger.error(
                f"Failed to remove track {audio_track_id} from playlist {playlist_id}: {e}"
            )
            raise

    def reorder_tracks(self, playlist_id: str, track_order: List[str]) -> Dict[str, Any]:
        """Reorder tracks in a playlist."""
        try:
            result = reorder_playlist_tracks(playlist_id, track_order)
            logger.debug(f"Reordered {len(track_order)} tracks in playlist {playlist_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to reorder tracks in playlist {playlist_id}: {e}")
            raise

    def add_collaborator(
        self, playlist_id: str, user_id: str, role: str = "viewer"
    ) -> Dict[str, Any]:
        """Add or update a collaborator on a playlist."""
        try:
            result = add_playlist_collaborator(playlist_id, user_id, role)
            logger.debug(f"Added collaborator {user_id} to playlist {playlist_id} as {role}")
            return result
        except Exception as e:
            logger.error(
                f"Failed to add collaborator {user_id} to playlist {playlist_id}: {e}"
            )
            raise

    def remove_collaborator(self, playlist_id: str, user_id: str) -> bool:
        """Remove a collaborator from a playlist."""
        try:
            result = remove_playlist_collaborator(playlist_id, user_id)
            logger.debug(f"Removed collaborator {user_id} from playlist {playlist_id}")
            return result
        except Exception as e:
            logger.error(
                f"Failed to remove collaborator {user_id} from playlist {playlist_id}: {e}"
            )
            raise


# Global repository instance
_playlist_repository: Optional[PlaylistRepositoryInterface] = None


def get_playlist_repository() -> PlaylistRepositoryInterface:
    """Get the global playlist repository instance."""
    global _playlist_repository
    if _playlist_repository is None:
        if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("TEST_MODE") == "true":
            try:
                from tests.conftest import MockPlaylistRepository

                _playlist_repository = MockPlaylistRepository()
                logger.info("Mock playlist repository initialized for testing")
            except ImportError:
                _playlist_repository = PostgresPlaylistRepository()
                logger.warning("Test fixtures not available, using real repository")
        else:
            _playlist_repository = PostgresPlaylistRepository()
            logger.info("Playlist repository initialized")
    return _playlist_repository


def set_playlist_repository(repository: PlaylistRepositoryInterface) -> None:
    """Set the global playlist repository instance (for testing)."""
    global _playlist_repository
    _playlist_repository = repository
    logger.info("Playlist repository instance set")
