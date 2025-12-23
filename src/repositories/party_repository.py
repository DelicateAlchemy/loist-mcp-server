"""
Party Repository Abstraction Layer

Provides clean data access interface for parties (writers, publishers, artists, labels),
decoupling business logic from database implementation details.
"""

import logging
import os
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod

from database.operations import (
    create_party,
    get_party_by_id,
    search_parties,
)

logger = logging.getLogger(__name__)


class PartyRepositoryInterface(ABC):
    """Abstract interface for party data operations."""

    @abstractmethod
    def create(self, party_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new party."""
        pass

    @abstractmethod
    def get_by_id(self, party_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve party by ID."""
        pass

    @abstractmethod
    def search(self, query: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """Search parties by name."""
        pass


class PostgresPartyRepository(PartyRepositoryInterface):
    """PostgreSQL implementation of party repository."""

    def create(self, party_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new party."""
        try:
            result = create_party(party_data)
            logger.debug(f"Created party: {result.get('id', 'unknown')}")
            return result
        except Exception as e:
            logger.error(f"Failed to create party: {e}")
            raise

    def get_by_id(self, party_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve party by ID."""
        try:
            result = get_party_by_id(party_id)
            if result:
                logger.debug(f"Retrieved party: {party_id}")
            else:
                logger.debug(f"No party found: {party_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to retrieve party {party_id}: {e}")
            raise

    def search(self, query: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """Search parties by name."""
        try:
            result = search_parties(query, limit=limit, offset=offset)
            logger.debug(f"Search '{query}' returned {len(result)} parties")
            return result
        except Exception as e:
            logger.error(f"Failed to search parties for query '{query}': {e}")
            raise


# Global repository instance
_party_repository: Optional[PartyRepositoryInterface] = None


def get_party_repository() -> PartyRepositoryInterface:
    """Get the global party repository instance."""
    global _party_repository
    if _party_repository is None:
        # Check if we're in test mode (environment variable or explicit override)
        if os.getenv('PYTEST_CURRENT_TEST') or os.getenv('TEST_MODE') == 'true':
            # Import mock repository only when needed to avoid circular imports
            try:
                from tests.conftest import MockPartyRepository
                _party_repository = MockPartyRepository()
                logger.info("✅ Mock party repository initialized for testing")
            except ImportError:
                # Fallback to real repository if test fixtures not available
                _party_repository = PostgresPartyRepository()
                logger.warning("Test fixtures not available, using real repository")
        else:
            _party_repository = PostgresPartyRepository()
            logger.info("✅ Party repository initialized")
    return _party_repository


def set_party_repository(repository: PartyRepositoryInterface) -> None:
    """Set the global party repository instance (for testing)."""
    global _party_repository
    _party_repository = repository
    logger.info("✅ Party repository instance set")

