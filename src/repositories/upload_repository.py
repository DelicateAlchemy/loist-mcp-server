"""
Upload Repository Abstraction Layer

Provides clean data access interface for browser upload tracking records
(LOI-45), decoupling business logic from database implementation details.
"""

import logging
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

from database.operations import (
    create_upload,
    get_upload_by_id,
    update_upload_status,
)

logger = logging.getLogger(__name__)


class UploadRepositoryInterface(ABC):
    """Abstract interface for upload tracking operations."""

    @abstractmethod
    def create(self, upload_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new upload record."""
        pass

    @abstractmethod
    def get_by_id(self, upload_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve upload record by ID."""
        pass

    @abstractmethod
    def update_status(
        self,
        upload_id: str,
        status: str,
        audio_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update an upload's processing status."""
        pass


class PostgresUploadRepository(UploadRepositoryInterface):
    """PostgreSQL implementation of upload repository."""

    def create(self, upload_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new upload record."""
        try:
            result = create_upload(upload_data)
            logger.debug(f"Created upload record: {result.get('id', 'unknown')}")
            return result
        except Exception as e:
            logger.error(f"Failed to create upload record: {e}")
            raise

    def get_by_id(self, upload_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve upload record by ID."""
        try:
            result = get_upload_by_id(upload_id)
            if result:
                logger.debug(f"Retrieved upload: {upload_id}")
            else:
                logger.debug(f"No upload found: {upload_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to retrieve upload {upload_id}: {e}")
            raise

    def update_status(
        self,
        upload_id: str,
        status: str,
        audio_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update an upload's processing status."""
        try:
            result = update_upload_status(
                upload_id, status, audio_id=audio_id, error_message=error_message
            )
            logger.debug(f"Upload {upload_id} status -> {status}")
            return result
        except Exception as e:
            logger.error(f"Failed to update upload {upload_id}: {e}")
            raise


# Global repository instance
_upload_repository: Optional[UploadRepositoryInterface] = None


def get_upload_repository() -> UploadRepositoryInterface:
    """Get the global upload repository instance."""
    global _upload_repository
    if _upload_repository is None:
        _upload_repository = PostgresUploadRepository()
        logger.info("✅ Upload repository initialized")
    return _upload_repository


def set_upload_repository(repository: UploadRepositoryInterface) -> None:
    """Set the global upload repository instance (for testing)."""
    global _upload_repository
    _upload_repository = repository
    logger.info("✅ Upload repository instance set")
