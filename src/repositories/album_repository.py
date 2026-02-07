"""
Album Repository Abstraction Layer

Provides clean data access interface for albums, decoupling
business logic from database implementation details.
"""

import logging
import os
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod

from database.operations import (
    create_album,
    get_album_by_id,
    update_album,
    delete_album,
    search_albums,
    add_track_to_album,
    remove_track_from_album,
    reorder_album_tracks,
)

logger = logging.getLogger(__name__)


class AlbumRepositoryInterface(ABC):
    """Abstract interface for album data operations."""

    @abstractmethod
    def create(self, album_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new album."""
        pass

    @abstractmethod
    def get_by_id(self, album_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve album by ID with tracks."""
        pass

    @abstractmethod
    def update(self, album_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update album metadata."""
        pass

    @abstractmethod
    def delete(self, album_id: str) -> bool:
        """Delete an album."""
        pass

    @abstractmethod
    def search(
        self, query: str, limit: int = 20, offset: int = 0, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search albums by name."""
        pass

    @abstractmethod
    def add_track(
        self,
        album_id: str,
        audio_track_id: str,
        position: Optional[int] = None,
        disc_number: int = 1,
    ) -> Dict[str, Any]:
        """Add a track to an album."""
        pass

    @abstractmethod
    def remove_track(self, album_id: str, audio_track_id: str) -> bool:
        """Remove a track from an album."""
        pass

    @abstractmethod
    def reorder_tracks(self, album_id: str, track_order: List[str]) -> Dict[str, Any]:
        """Reorder tracks in an album."""
        pass


class PostgresAlbumRepository(AlbumRepositoryInterface):
    """PostgreSQL implementation of album repository."""

    def create(self, album_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new album."""
        try:
            result = create_album(album_data)
            logger.debug(f"Created album: {result.get('id', 'unknown')}")
            return result
        except Exception as e:
            logger.error(f"Failed to create album: {e}")
            raise

    def get_by_id(self, album_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve album by ID with tracks."""
        try:
            result = get_album_by_id(album_id)
            if result:
                logger.debug(f"Retrieved album: {album_id}")
            else:
                logger.debug(f"No album found: {album_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to retrieve album {album_id}: {e}")
            raise

    def update(self, album_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update album metadata."""
        try:
            result = update_album(album_id, update_data)
            logger.debug(f"Updated album: {album_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to update album {album_id}: {e}")
            raise

    def delete(self, album_id: str) -> bool:
        """Delete an album."""
        try:
            result = delete_album(album_id)
            logger.debug(f"Deleted album: {album_id} (success={result})")
            return result
        except Exception as e:
            logger.error(f"Failed to delete album {album_id}: {e}")
            raise

    def search(
        self, query: str, limit: int = 20, offset: int = 0, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search albums by name."""
        try:
            result = search_albums(query, limit=limit, offset=offset, status=status)
            logger.debug(f"Search '{query}' returned {len(result)} albums")
            return result
        except Exception as e:
            logger.error(f"Failed to search albums for query '{query}': {e}")
            raise

    def add_track(
        self,
        album_id: str,
        audio_track_id: str,
        position: Optional[int] = None,
        disc_number: int = 1,
    ) -> Dict[str, Any]:
        """Add a track to an album."""
        try:
            result = add_track_to_album(album_id, audio_track_id, position, disc_number)
            logger.debug(f"Added track {audio_track_id} to album {album_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to add track {audio_track_id} to album {album_id}: {e}")
            raise

    def remove_track(self, album_id: str, audio_track_id: str) -> bool:
        """Remove a track from an album."""
        try:
            result = remove_track_from_album(album_id, audio_track_id)
            logger.debug(f"Removed track {audio_track_id} from album {album_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to remove track {audio_track_id} from album {album_id}: {e}")
            raise

    def reorder_tracks(self, album_id: str, track_order: List[str]) -> Dict[str, Any]:
        """Reorder tracks in an album."""
        try:
            result = reorder_album_tracks(album_id, track_order)
            logger.debug(f"Reordered {len(track_order)} tracks in album {album_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to reorder tracks in album {album_id}: {e}")
            raise


# Global repository instance
_album_repository: Optional[AlbumRepositoryInterface] = None


def get_album_repository() -> AlbumRepositoryInterface:
    """Get the global album repository instance."""
    global _album_repository
    if _album_repository is None:
        if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("TEST_MODE") == "true":
            try:
                from tests.conftest import MockAlbumRepository

                _album_repository = MockAlbumRepository()
                logger.info("Mock album repository initialized for testing")
            except ImportError:
                _album_repository = PostgresAlbumRepository()
                logger.warning("Test fixtures not available, using real repository")
        else:
            _album_repository = PostgresAlbumRepository()
            logger.info("Album repository initialized")
    return _album_repository


def set_album_repository(repository: AlbumRepositoryInterface) -> None:
    """Set the global album repository instance (for testing)."""
    global _album_repository
    _album_repository = repository
    logger.info("Album repository instance set")
