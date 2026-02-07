"""
Service layer for work-related business logic.

This service centralizes operations for retrieving, creating, searching, and managing
works (compositions), separating business logic from the transport layer (MCP/HTTP).
"""

import logging
from typing import Dict, Any, List

from src.repositories import get_work_repository
from src.exceptions import (
    DatabaseOperationError,
    ResourceNotFoundError,
)

logger = logging.getLogger(__name__)


async def get_work(work_id: str) -> Dict[str, Any]:
    """
    Retrieve a work by ID with all relations.

    Args:
        work_id: The UUID of the work.

    Returns:
        A dictionary containing the work information with writers, publishers,
        alternative titles, recordings, and warnings.

    Raises:
        ResourceNotFoundError: If the work is not found.
        DatabaseOperationError: If a database error occurs.
    """
    logger.debug(f"Service: Fetching work: {work_id}")
    work = get_work_repository().get_by_id(work_id)

    if not work:
        logger.warning(f"Service: Work not found: {work_id}")
        raise ResourceNotFoundError(f"Work with ID '{work_id}' was not found")

    return work


async def create_work(work_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new work.

    Args:
        work_data: Dictionary containing work fields:
            - title: str (required) - Canonical title
            - iswc: str (optional) - International Standard Musical Work Code
            - language: str (optional) - ISO 639-1 language code
            - status: str (optional, default 'draft') - Workflow status
            - notes: str (optional) - Freeform notes

    Returns:
        A dictionary containing the created work information.

    Raises:
        DatabaseOperationError: If the creation fails.
    """
    logger.debug(f"Service: Creating work: {work_data.get('title', 'unknown')}")
    
    try:
        result = get_work_repository().create(work_data)
        logger.info(f"Service: Created work {result.get('id')}")
        return result
    except Exception as e:
        logger.error(f"Service: Failed to create work: {e}")
        raise DatabaseOperationError(f"Failed to create work: {str(e)}")


async def search_works(query: str, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
    """
    Search works by title.

    Args:
        query: The search query string.
        limit: The maximum number of results to return (1-100).
        offset: The number of results to skip.

    Returns:
        A dictionary containing search results and pagination info.

    Raises:
        DatabaseOperationError: If the search fails.
    """
    logger.debug(f"Service: Searching works for '{query}' with limit={limit}, offset={offset}")

    try:
        results = get_work_repository().search(query, limit=limit, offset=offset)
        
        return {
            "results": results,
            "total": len(results),  # Note: search_works doesn't return total count
            "limit": limit,
            "offset": offset,
            "has_more": len(results) == limit,  # Estimate based on result count
        }
    except Exception as e:
        logger.error(f"Service: Failed to search works: {e}")
        raise DatabaseOperationError(f"Failed to search works: {str(e)}")


async def update_work_writers(work_id: str, writers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Update writers for a work (batch replace operation).

    This replaces all existing writers with the provided list. Each writer dict should contain:
        - party_id: str (required) - UUID of the party
        - split_percentage: float (optional) - Percentage (0-200 or None)
        - split_status: str (required) - 'proposed', 'confirmed', 'disputed', or 'unknown'
        - notes: str (optional) - Negotiation notes

    Args:
        work_id: The UUID of the work.
        writers: List of writer dictionaries.

    Returns:
        A dictionary with:
            - replaced_count: Number of writers replaced
            - work_id: The work ID

    Raises:
        ResourceNotFoundError: If the work is not found.
        DatabaseOperationError: If the update fails.
    """
    logger.debug(f"Service: Updating writers for work {work_id} ({len(writers)} writers)")

    try:
        result = get_work_repository().replace_writers(work_id, writers)
        logger.info(f"Service: Updated {result.get('replaced_count', 0)} writers for work {work_id}")
        return result
    except ResourceNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Service: Failed to update writers for work {work_id}: {e}")
        raise DatabaseOperationError(f"Failed to update writers: {str(e)}")


async def update_work_publishers(work_id: str, publishers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Update publishers for a work (batch replace operation).

    This replaces all existing publishers with the provided list. Each publisher dict should contain:
        - party_id: str (required) - UUID of the party
        - split_percentage: float (optional) - Percentage (0-200 or None)
        - split_status: str (required) - 'proposed', 'confirmed', 'disputed', or 'unknown'
        - notes: str (optional) - Negotiation notes

    Args:
        work_id: The UUID of the work.
        publishers: List of publisher dictionaries.

    Returns:
        A dictionary with:
            - replaced_count: Number of publishers replaced
            - work_id: The work ID

    Raises:
        ResourceNotFoundError: If the work is not found.
        DatabaseOperationError: If the update fails.
    """
    logger.debug(f"Service: Updating publishers for work {work_id} ({len(publishers)} publishers)")

    try:
        result = get_work_repository().replace_publishers(work_id, publishers)
        logger.info(f"Service: Updated {result.get('replaced_count', 0)} publishers for work {work_id}")
        return result
    except ResourceNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Service: Failed to update publishers for work {work_id}: {e}")
        raise DatabaseOperationError(f"Failed to update publishers: {str(e)}")

