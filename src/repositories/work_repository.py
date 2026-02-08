"""
Work Repository Abstraction Layer

Provides clean data access interface for works (compositions), decoupling
business logic from database implementation details.
"""

import logging
import os
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod

from database.operations import (
    create_work,
    get_work_by_id,
    search_works,
    replace_work_writers,
    replace_work_publishers,
    calculate_split_warnings,
)

logger = logging.getLogger(__name__)


class WorkRepositoryInterface(ABC):
    """Abstract interface for work data operations."""

    @abstractmethod
    def create(self, work_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new work."""
        pass

    @abstractmethod
    def get_by_id(self, work_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve work by ID with all relations."""
        pass

    @abstractmethod
    def search(self, query: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """Search works by title."""
        pass

    @abstractmethod
    def replace_writers(self, work_id: str, writers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Replace all writers for a work (batch operation)."""
        pass

    @abstractmethod
    def replace_publishers(self, work_id: str, publishers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Replace all publishers for a work (batch operation)."""
        pass

    @abstractmethod
    def calculate_warnings(self, work_id: str) -> List[str]:
        """Calculate split validation warnings for a work."""
        pass


class PostgresWorkRepository(WorkRepositoryInterface):
    """PostgreSQL implementation of work repository."""

    def create(self, work_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new work."""
        try:
            result = create_work(work_data)
            logger.debug(f"Created work: {result.get('id', 'unknown')}")
            return result
        except Exception as e:
            logger.error(f"Failed to create work: {e}")
            raise

    def get_by_id(self, work_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve work by ID with all relations."""
        try:
            result = get_work_by_id(work_id)
            if result:
                logger.debug(f"Retrieved work: {work_id}")
            else:
                logger.debug(f"No work found: {work_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to retrieve work {work_id}: {e}")
            raise

    def search(self, query: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """Search works by title."""
        try:
            result = search_works(query, limit=limit, offset=offset)
            logger.debug(f"Search '{query}' returned {len(result)} works")
            return result
        except Exception as e:
            logger.error(f"Failed to search works for query '{query}': {e}")
            raise

    def replace_writers(self, work_id: str, writers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Replace all writers for a work (batch operation)."""
        try:
            result = replace_work_writers(work_id, writers)
            logger.debug(f"Replaced {result.get('replaced_count', 0)} writers for work {work_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to replace writers for work {work_id}: {e}")
            raise

    def replace_publishers(self, work_id: str, publishers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Replace all publishers for a work (batch operation)."""
        try:
            result = replace_work_publishers(work_id, publishers)
            logger.debug(f"Replaced {result.get('replaced_count', 0)} publishers for work {work_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to replace publishers for work {work_id}: {e}")
            raise

    def calculate_warnings(self, work_id: str) -> List[str]:
        """Calculate split validation warnings for a work."""
        try:
            result = calculate_split_warnings(work_id)
            logger.debug(f"Calculated {len(result)} warnings for work {work_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to calculate warnings for work {work_id}: {e}")
            raise


# Global repository instance
_work_repository: Optional[WorkRepositoryInterface] = None


def get_work_repository() -> WorkRepositoryInterface:
    """Get the global work repository instance."""
    global _work_repository
    if _work_repository is None:
        # Check if we're in test mode (environment variable or explicit override)
        if os.getenv('PYTEST_CURRENT_TEST') or os.getenv('TEST_MODE') == 'true':
            # Import mock repository only when needed to avoid circular imports
            try:
                from tests.conftest import MockWorkRepository
                _work_repository = MockWorkRepository()
                logger.info("✅ Mock work repository initialized for testing")
            except ImportError:
                # Fallback to real repository if test fixtures not available
                _work_repository = PostgresWorkRepository()
                logger.warning("Test fixtures not available, using real repository")
        else:
            _work_repository = PostgresWorkRepository()
            logger.info("✅ Work repository initialized")
    return _work_repository


def set_work_repository(repository: WorkRepositoryInterface) -> None:
    """Set the global work repository instance (for testing)."""
    global _work_repository
    _work_repository = repository
    logger.info("✅ Work repository instance set")

