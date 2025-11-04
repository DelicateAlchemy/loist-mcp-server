"""
Audio Repository Abstraction Layer

Provides clean data access interface for audio tracks, decoupling
business logic from database implementation details.

Author: Task Master AI
Created: $(date)
"""

import logging
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod

from database.operations import (
    save_audio_metadata,
    save_audio_metadata_batch,
    get_audio_metadata_by_id,
    get_audio_metadata_by_ids,
    get_all_audio_metadata,
    search_audio_tracks,
    search_audio_tracks_advanced,
    update_processing_status,
    mark_as_processing,
    mark_as_completed,
    mark_as_failed,
)

logger = logging.getLogger(__name__)


class AudioRepositoryInterface(ABC):
    """Abstract interface for audio data operations."""

    @abstractmethod
    def save_metadata(self, metadata: Dict[str, Any], audio_gcs_path: str,
                     thumbnail_gcs_path: Optional[str] = None, track_id: Optional[str] = None) -> Dict[str, Any]:
        """Save single audio metadata record."""
        pass

    @abstractmethod
    def save_metadata_batch(self, metadata_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Save multiple audio metadata records."""
        pass

    @abstractmethod
    def get_metadata_by_id(self, track_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve metadata by track ID."""
        pass

    @abstractmethod
    def get_metadata_by_ids(self, track_ids: List[str]) -> Dict[str, Any]:
        """Retrieve metadata for multiple track IDs."""
        pass

    @abstractmethod
    def get_all_metadata(self, limit: int = 20, offset: int = 0,
                        status_filter: Optional[str] = None, order_by: str = "created_at",
                        order_direction: str = "DESC") -> Dict[str, Any]:
        """Get paginated metadata list."""
        pass

    @abstractmethod
    def search_tracks(self, query: str, limit: int = 20, offset: int = 0,
                     min_rank: float = 0.0) -> List[Dict[str, Any]]:
        """Search tracks using full-text search."""
        pass

    @abstractmethod
    def search_tracks_advanced(self, query: str, limit: int = 20, offset: int = 0,
                             status_filter: Optional[str] = None, year_min: Optional[int] = None,
                             year_max: Optional[int] = None, format_filter: Optional[str] = None,
                             min_rank: float = 0.0, rank_normalization: int = 1) -> Dict[str, Any]:
        """Advanced search with filters."""
        pass

    @abstractmethod
    def update_status(self, track_id: str, status: str,
                     error_message: Optional[str] = None, increment_retry: bool = False) -> Dict[str, Any]:
        """Update processing status."""
        pass

    @abstractmethod
    def mark_processing(self, track_id: str) -> Dict[str, Any]:
        """Mark track as processing."""
        pass

    @abstractmethod
    def mark_completed(self, track_id: str) -> Dict[str, Any]:
        """Mark track as completed."""
        pass

    @abstractmethod
    def mark_failed(self, track_id: str, error_message: str, increment_retry: bool = True) -> Dict[str, Any]:
        """Mark track as failed."""
        pass


class PostgresAudioRepository(AudioRepositoryInterface):
    """PostgreSQL implementation of audio repository."""

    def save_metadata(self, metadata: Dict[str, Any], audio_gcs_path: str,
                     thumbnail_gcs_path: Optional[str] = None, track_id: Optional[str] = None) -> Dict[str, Any]:
        """Save single audio metadata record."""
        try:
            result = save_audio_metadata(
                metadata=metadata,
                audio_gcs_path=audio_gcs_path,
                thumbnail_gcs_path=thumbnail_gcs_path,
                track_id=track_id
            )
            logger.debug(f"Saved metadata for track {result.get('id', 'unknown')}")
            return result
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")
            raise

    def save_metadata_batch(self, metadata_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Save multiple audio metadata records."""
        try:
            result = save_audio_metadata_batch(metadata_list)
            logger.debug(f"Batch saved {result.get('inserted_count', 0)} tracks")
            return result
        except Exception as e:
            logger.error(f"Failed to batch save metadata: {e}")
            raise

    def get_metadata_by_id(self, track_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve metadata by track ID."""
        try:
            result = get_audio_metadata_by_id(track_id)
            if result:
                logger.debug(f"Retrieved metadata for track {track_id}")
            else:
                logger.debug(f"No metadata found for track {track_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to retrieve metadata for track {track_id}: {e}")
            raise

    def get_metadata_by_ids(self, track_ids: List[str]) -> Dict[str, Any]:
        """Retrieve metadata for multiple track IDs."""
        try:
            result = get_audio_metadata_by_ids(track_ids)
            logger.debug(f"Retrieved metadata for {len(track_ids)} tracks")
            return result
        except Exception as e:
            logger.error(f"Failed to retrieve metadata for track IDs {track_ids}: {e}")
            raise

    def get_all_metadata(self, limit: int = 20, offset: int = 0,
                        status_filter: Optional[str] = None, order_by: str = "created_at",
                        order_direction: str = "DESC") -> Dict[str, Any]:
        """Get paginated metadata list."""
        try:
            result = get_all_audio_metadata(
                limit=limit,
                offset=offset,
                status_filter=status_filter,
                order_by=order_by,
                order_direction=order_direction
            )
            logger.debug(f"Retrieved {len(result.get('tracks', []))} tracks (limit={limit}, offset={offset})")
            return result
        except Exception as e:
            logger.error(f"Failed to retrieve metadata list: {e}")
            raise

    def search_tracks(self, query: str, limit: int = 20, offset: int = 0,
                     min_rank: float = 0.0) -> List[Dict[str, Any]]:
        """Search tracks using full-text search."""
        try:
            result = search_audio_tracks(
                query=query,
                limit=limit,
                offset=offset,
                min_rank=min_rank
            )
            logger.debug(f"Search '{query}' returned {len(result)} results")
            return result
        except Exception as e:
            logger.error(f"Failed to search tracks for query '{query}': {e}")
            raise

    def search_tracks_advanced(self, query: str, limit: int = 20, offset: int = 0,
                             status_filter: Optional[str] = None, year_min: Optional[int] = None,
                             year_max: Optional[int] = None, format_filter: Optional[str] = None,
                             min_rank: float = 0.0, rank_normalization: int = 1) -> Dict[str, Any]:
        """Advanced search with filters."""
        try:
            result = search_audio_tracks_advanced(
                query=query,
                limit=limit,
                offset=offset,
                status_filter=status_filter,
                year_min=year_min,
                year_max=year_max,
                format_filter=format_filter,
                min_rank=min_rank,
                rank_normalization=rank_normalization
            )
            logger.debug(f"Advanced search '{query}' returned {result.get('total_matches', 0)} matches")
            return result
        except Exception as e:
            logger.error(f"Failed to perform advanced search for query '{query}': {e}")
            raise

    def update_status(self, track_id: str, status: str,
                     error_message: Optional[str] = None, increment_retry: bool = False) -> Dict[str, Any]:
        """Update processing status."""
        try:
            result = update_processing_status(
                track_id=track_id,
                status=status,
                error_message=error_message,
                increment_retry=increment_retry
            )
            logger.debug(f"Updated status for track {track_id} to {status}")
            return result
        except Exception as e:
            logger.error(f"Failed to update status for track {track_id}: {e}")
            raise

    def mark_processing(self, track_id: str) -> Dict[str, Any]:
        """Mark track as processing."""
        try:
            result = mark_as_processing(track_id)
            logger.debug(f"Marked track {track_id} as processing")
            return result
        except Exception as e:
            logger.error(f"Failed to mark track {track_id} as processing: {e}")
            raise

    def mark_completed(self, track_id: str) -> Dict[str, Any]:
        """Mark track as completed."""
        try:
            result = mark_as_completed(track_id)
            logger.debug(f"Marked track {track_id} as completed")
            return result
        except Exception as e:
            logger.error(f"Failed to mark track {track_id} as completed: {e}")
            raise

    def mark_failed(self, track_id: str, error_message: str, increment_retry: bool = True) -> Dict[str, Any]:
        """Mark track as failed."""
        try:
            result = mark_as_failed(track_id, error_message, increment_retry)
            logger.debug(f"Marked track {track_id} as failed")
            return result
        except Exception as e:
            logger.error(f"Failed to mark track {track_id} as failed: {e}")
            raise


# Global repository instance
_audio_repository: Optional[AudioRepositoryInterface] = None


def get_audio_repository() -> AudioRepositoryInterface:
    """Get the global audio repository instance."""
    global _audio_repository
    if _audio_repository is None:
        _audio_repository = PostgresAudioRepository()
        logger.info("✅ Audio repository initialized")
    return _audio_repository


def set_audio_repository(repository: AudioRepositoryInterface) -> None:
    """Set the global audio repository instance (for testing)."""
    global _audio_repository
    _audio_repository = repository
    logger.info("✅ Audio repository instance set")


# Convenience functions for backward compatibility
def save_metadata(*args, **kwargs) -> Dict[str, Any]:
    """Convenience function for saving metadata."""
    return get_audio_repository().save_metadata(*args, **kwargs)

def save_metadata_batch(*args, **kwargs) -> Dict[str, Any]:
    """Convenience function for batch saving metadata."""
    return get_audio_repository().save_metadata_batch(*args, **kwargs)

def get_metadata_by_id(*args, **kwargs) -> Optional[Dict[str, Any]]:
    """Convenience function for getting metadata by ID."""
    return get_audio_repository().get_metadata_by_id(*args, **kwargs)

def search_tracks(*args, **kwargs) -> List[Dict[str, Any]]:
    """Convenience function for searching tracks."""
    return get_audio_repository().search_tracks(*args, **kwargs)

def update_track_status(*args, **kwargs) -> Dict[str, Any]:
    """Convenience function for updating track status."""
    return get_audio_repository().update_status(*args, **kwargs)
