"""
Service layer for party-related business logic.

This service centralizes operations for retrieving, creating, and searching
parties (writers, publishers, artists, labels), separating business logic
from the transport layer (MCP/HTTP).
"""

import logging
from typing import Dict, Any, List

from src.repositories import get_party_repository
from src.exceptions import (
    DatabaseOperationError,
    ResourceNotFoundError,
)

logger = logging.getLogger(__name__)


async def get_party(party_id: str) -> Dict[str, Any]:
    """
    Retrieve a party by ID.

    Args:
        party_id: The UUID of the party.

    Returns:
        A dictionary containing the party information with involvement data.

    Raises:
        ResourceNotFoundError: If the party is not found.
        DatabaseOperationError: If a database error occurs.
    """
    logger.debug(f"Service: Fetching party: {party_id}")
    party = get_party_repository().get_by_id(party_id)

    if not party:
        logger.warning(f"Service: Party not found: {party_id}")
        raise ResourceNotFoundError(f"Party with ID '{party_id}' was not found")

    return party


async def create_party(party_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new party.

    Args:
        party_data: Dictionary containing party fields:
            - name: str (required) - Display name
            - party_type: str (optional, default 'person') - 'person' or 'organization'
            - legal_name: str (optional) - Legal/contract name
            - ipi_cae_number: str (optional) - CAE/IPI number
            - isni: str (optional) - ISNI identifier
            - society_affiliation: str (optional) - PRO affiliation
            - email: str (optional) - Contact email
            - notes: str (optional) - Freeform notes

    Returns:
        A dictionary containing the created party information.

    Raises:
        DatabaseOperationError: If the creation fails.
    """
    logger.debug(f"Service: Creating party: {party_data.get('name', 'unknown')}")
    
    try:
        result = get_party_repository().create(party_data)
        logger.info(f"Service: Created party {result.get('id')}")
        return result
    except Exception as e:
        logger.error(f"Service: Failed to create party: {e}")
        raise DatabaseOperationError(f"Failed to create party: {str(e)}")


async def search_parties(query: str, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
    """
    Search parties by name.

    Args:
        query: The search query string.
        limit: The maximum number of results to return (1-100).
        offset: The number of results to skip.

    Returns:
        A dictionary containing search results and pagination info.

    Raises:
        DatabaseOperationError: If the search fails.
    """
    logger.debug(f"Service: Searching parties for '{query}' with limit={limit}, offset={offset}")

    try:
        results = get_party_repository().search(query, limit=limit, offset=offset)
        
        return {
            "results": results,
            "total": len(results),  # Note: search_parties doesn't return total count
            "limit": limit,
            "offset": offset,
            "has_more": len(results) == limit,  # Estimate based on result count
        }
    except Exception as e:
        logger.error(f"Service: Failed to search parties: {e}")
        raise DatabaseOperationError(f"Failed to search parties: {str(e)}")

