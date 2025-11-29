"""
Query/retrieval tools for Loist Music Library MCP Server.

Implements get_audio_metadata and search_library MCP tools for
retrieving and searching processed audio tracks.

Follows best practices from research:
- Input validation with Pydantic
- Proper error handling for not found scenarios
- Performance optimization for database queries
- Response caching ready (implement at infrastructure level)
"""

import logging
from typing import Dict, Any, List
import time

from .query_schemas import (
    GetAudioMetadataInput,
    GetAudioMetadataOutput,
    SearchLibraryInput,
    SearchLibraryOutput,
    SearchResult,
    QueryException,
    QueryErrorCode,
    TimeFilters,
)
from .schemas import (
    ProductMetadata,
    FormatMetadata,
    AudioMetadata,
    AudioResources,
)

# Import database operations
from database import (
    get_audio_metadata_by_id,
    search_audio_tracks_advanced,
    filter_audio_tracks_xmp,
    filter_audio_tracks_combined,
    get_xmp_field_facets,
    filter_audio_tracks_cursor_xmp,
    encode_cursor,
    decode_cursor,
)
from src.exceptions import (
    DatabaseOperationError,
    ResourceNotFoundError,
    ValidationError,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions
# ============================================================================

def format_metadata_response(db_metadata: Dict[str, Any]) -> AudioMetadata:
    """
    Format database metadata into API response structure.
    
    Converts database field names to API contract field names.
    
    Args:
        db_metadata: Raw metadata dict from database
        
    Returns:
        AudioMetadata: Formatted metadata following API contract
    """
    # Generate embed URL
    audio_id = db_metadata.get("id")
    embed_url = f"https://loist.io/embed/{audio_id}"
    
    # Format product metadata
    product = ProductMetadata(
        Artist=db_metadata.get("artist", ""),
        Title=db_metadata.get("title", "Untitled"),
        Album=db_metadata.get("album", ""),
        MBID=None,  # MVP: null
        Genre=[db_metadata.get("genre")] if db_metadata.get("genre") else [],
        Year=db_metadata.get("year")
    )
    
    # Format technical metadata
    # Handle both "duration" and "duration_seconds" field names for compatibility
    duration = db_metadata.get("duration") or db_metadata.get("duration_seconds", 0.0)
    format_metadata = FormatMetadata(
        Duration=duration,
        Channels=db_metadata.get("channels", 2),
        SampleRate=db_metadata.get("sample_rate", 44100),
        Bitrate=db_metadata.get("bitrate", 0),
        Format=db_metadata.get("format", "")
    )
    
    # Combine into complete metadata
    return AudioMetadata(
        Product=product,
        Format=format_metadata,
        urlEmbedLink=embed_url
    )


def format_resources(audio_id: str, has_thumbnail: bool = False) -> AudioResources:
    """
    Generate resource URIs for an audio track.
    
    Args:
        audio_id: UUID of the audio track
        has_thumbnail: Whether thumbnail is available
        
    Returns:
        AudioResources: Resource URIs
    """
    return AudioResources(
        audio=f"music-library://audio/{audio_id}/stream",
        thumbnail=f"music-library://audio/{audio_id}/thumbnail" if has_thumbnail else None,
        waveform=None  # MVP: null
    )


# ============================================================================
# Main Tool Functions
# ============================================================================

async def get_audio_metadata(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Retrieve metadata for a previously processed audio track.
    
    This is a read-only operation that fetches metadata from the database.
    
    Args:
        input_data: Dictionary containing audioId
        
    Returns:
        Dictionary with success status and metadata, or error response
        
    Raises:
        QueryException: For not found or database errors
        
    Example:
        >>> result = await get_audio_metadata({"audioId": "550e8400-..."})
        >>> print(result["metadata"]["Product"]["Title"])
        "Hey Jude"
    """
    logger.info("Retrieving audio metadata")
    
    try:
        # Validate input
        try:
            validated_input = GetAudioMetadataInput(**input_data)
        except Exception as e:
            logger.error(f"Input validation failed: {e}")
            raise QueryException(
                error_code=QueryErrorCode.INVALID_QUERY,
                message=f"Invalid input: {str(e)}",
                details={"validation_errors": str(e)}
            )
        
        audio_id = validated_input.audioId
        logger.debug(f"Fetching metadata for audio ID: {audio_id}")
        
        # Fetch from database
        try:
            db_metadata = get_audio_metadata_by_id(audio_id)
        except ResourceNotFoundError as e:
            logger.warning(f"Audio track not found: {audio_id}")
            raise QueryException(
                error_code=QueryErrorCode.RESOURCE_NOT_FOUND,
                message=f"Audio track with ID '{audio_id}' was not found",
                details={"audioId": audio_id}
            )
        except DatabaseOperationError as e:
            logger.error(f"Database error retrieving metadata: {e}")
            raise QueryException(
                error_code=QueryErrorCode.DATABASE_ERROR,
                message=f"Failed to retrieve metadata: {str(e)}",
                details={"audioId": audio_id}
            )
        
        # Check if result exists (database returns None for not found)
        if not db_metadata:
            logger.warning(f"Audio track not found: {audio_id}")
            raise QueryException(
                error_code=QueryErrorCode.RESOURCE_NOT_FOUND,
                message=f"Audio track with ID '{audio_id}' was not found",
                details={"audioId": audio_id}
            )
        
        logger.info(f"Successfully retrieved metadata for {audio_id}")
        
        # Format response
        formatted_metadata = format_metadata_response(db_metadata)
        resources = format_resources(
            audio_id,
            has_thumbnail=bool(db_metadata.get("thumbnail_path"))
        )
        
        # Build response using Pydantic for validation
        response = GetAudioMetadataOutput(
            success=True,
            audioId=audio_id,
            metadata=formatted_metadata,
            resources=resources
        )
        
        return response.model_dump()
        
    except QueryException as e:
        # Known query error
        logger.error(f"Query error: {e.message}")
        error_response = e.to_error_response()
        return error_response.model_dump()
        
    except Exception as e:
        # Unexpected error
        logger.exception(f"Unexpected error retrieving metadata: {e}")
        error_response = QueryException(
            error_code=QueryErrorCode.DATABASE_ERROR,
            message=f"Unexpected error: {str(e)}",
            details={"exception_type": type(e).__name__}
        ).to_error_response()
        return error_response.model_dump()


async def search_library(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Search across all processed audio in the library.
    
    Performs full-text search with optional filters for:
    - Genre, year, duration, format
    - Artist, album (partial match)
    
    Supports pagination and sorting.
    
    Args:
        input_data: Dictionary containing query, filters, pagination, and sort options
        
    Returns:
        Dictionary with success status and search results, or error response
        
    Example:
        >>> result = await search_library({
        ...     "query": "beatles",
        ...     "filters": {"genre": ["Rock"], "year": {"min": 1960, "max": 1970"}},
        ...     "limit": 20
        ... })
        >>> print(len(result["results"]))
        15
    """
    logger.info("Searching audio library")
    start_time = time.time()
    
    try:
        # Validate input
        try:
            validated_input = SearchLibraryInput(**input_data)
        except Exception as e:
            logger.error(f"Input validation failed: {e}")
            raise QueryException(
                error_code=QueryErrorCode.INVALID_QUERY,
                message=f"Invalid search input: {str(e)}",
                details={"validation_errors": str(e)}
            )
        
        query = validated_input.query
        filters = validated_input.filters
        limit = validated_input.limit
        offset = validated_input.offset
        sort_by = validated_input.sortBy
        sort_order = validated_input.sortOrder

        logger.debug(f"Searching for: '{query}' with limit={limit}, offset={offset}")

        # Extract XMP filters and time filters from the filters dict
        xmp_filters = {}
        if filters:
            xmp_filters = {
                'composer_filter': filters.get('composer'),
                'publisher_filter': filters.get('publisher'),
                'record_label_filter': filters.get('record_label'),
                'isrc_filter': filters.get('isrc'),
                'year_min': filters.get('year', {}).get('min') if filters.get('year') else None,
                'year_max': filters.get('year', {}).get('max') if filters.get('year') else None,
                'format_filter': filters.get('format', [None])[0] if filters.get('format') else None,
                # Time-based filters
                'time_period': filters.get('time', {}).get('period') if filters.get('time') else None,
                'date_from': filters.get('time', {}).get('dateFrom') if filters.get('time') else None,
                'date_to': filters.get('time', {}).get('dateTo') if filters.get('time') else None,
                'timezone': filters.get('time', {}).get('timezone', 'UTC') if filters.get('time') else 'UTC',
            }

        # Use combined filtering function that supports both full-text search and XMP filters
        try:
            search_response = filter_audio_tracks_combined(
                query=query,
                limit=limit + 1,  # Fetch one extra to check if more results exist
                offset=offset,
                min_rank=0.01,  # Minimum relevance threshold
                **xmp_filters
            )
        except DatabaseOperationError as e:
            logger.error(f"Database error during search: {e}")
            raise QueryException(
                error_code=QueryErrorCode.DATABASE_ERROR,
                message=f"Search failed: {str(e)}",
                details={"query": query}
            )
        except Exception as e:
            logger.error(f"Unexpected error during search: {e}")
            raise QueryException(
                error_code=QueryErrorCode.DATABASE_ERROR,
                message=f"Unexpected search error: {str(e)}",
                details={"query": query, "exception_type": type(e).__name__}
            )

        # Extract tracks from response
        search_results = search_response.get('tracks', [])
        total_matches = search_response.get('total_count', 0)

        # Check if more results exist (pagination)
        has_more = len(search_results) > limit
        if has_more:
            search_results = search_results[:limit]  # Remove the extra result

        logger.info(f"Found {len(search_results)} results for '{query}' (total matches: {total_matches})")

        # Format results
        formatted_results = []
        for result in search_results:
            try:
                # Get metadata from result
                # Note: database returns "duration_seconds" and "thumbnail_gcs_path"
                # Handle None values with defaults
                duration_seconds = result.get("duration_seconds") or 0.0
                db_metadata = {
                    "id": result.get("id"),
                    "artist": result.get("artist", ""),
                    "title": result.get("title", "Untitled"),
                    "album": result.get("album", ""),
                    "genre": result.get("genre"),
                    "year": result.get("year"),
                    "duration": duration_seconds,  # Map duration_seconds to duration
                    "duration_seconds": duration_seconds,  # Keep both for compatibility
                    "channels": result.get("channels", 2),
                    "sample_rate": result.get("sample_rate", 44100),
                    "bitrate": result.get("bitrate", 0),
                    "format": result.get("format", ""),
                    "thumbnail_path": result.get("thumbnail_gcs_path"),  # Map thumbnail_gcs_path to thumbnail_path
                    "thumbnail_gcs_path": result.get("thumbnail_gcs_path"),  # Keep both for compatibility
                    "composer": result.get("composer"),
                    "publisher": result.get("publisher"),
                    "record_label": result.get("record_label"),
                    "isrc": result.get("isrc")
                }

                # Format metadata
                formatted_metadata = format_metadata_response(db_metadata)

                # Get relevance score (database returns as "rank")
                score = float(result.get("rank", 0.0))

                # Create search result
                search_result = SearchResult(
                    audioId=result.get("id"),
                    metadata=formatted_metadata,
                    score=score
                )

                formatted_results.append(search_result)

            except Exception as e:
                logger.warning(f"Error formatting search result: {e}")
                continue  # Skip this result and continue with others

        # Get facets for XMP fields to support faceted search
        try:
            facets_data = get_xmp_field_facets(
                composer_limit=20,
                publisher_limit=20,
                record_label_limit=20,
                min_count=1
            )

            # Convert to Pydantic format
            facets = SearchFacets(
                composers=[
                    FacetData(name=facet['name'], count=facet['count'])
                    for facet in facets_data.get('composers', [])
                ],
                publishers=[
                    FacetData(name=facet['name'], count=facet['count'])
                    for facet in facets_data.get('publishers', [])
                ],
                record_labels=[
                    FacetData(name=facet['name'], count=facet['count'])
                    for facet in facets_data.get('record_labels', [])
                ]
            )
        except Exception as e:
            logger.warning(f"Failed to retrieve facets: {e}")
            facets = None

        # Build response
        response = SearchLibraryOutput(
            success=True,
            results=formatted_results,
            total=total_matches,
            limit=limit,
            offset=offset,
            hasMore=has_more,
            facets=facets
        )
        
        search_time = time.time() - start_time
        logger.info(f"Search completed in {search_time:.3f}s: {len(formatted_results)} results")
        
        return response.model_dump()
        
    except QueryException as e:
        # Known query error
        logger.error(f"Query error: {e.message}")
        error_response = e.to_error_response()
        return error_response.model_dump()
        
    except Exception as e:
        # Unexpected error
        logger.exception(f"Unexpected error during search: {e}")
        error_response = QueryException(
            error_code=QueryErrorCode.DATABASE_ERROR,
            message=f"Unexpected error: {str(e)}",
            details={"exception_type": type(e).__name__}
        ).to_error_response()
        return error_response.model_dump()


# ============================================================================
# Synchronous Wrappers (if needed)
# ============================================================================

def get_audio_metadata_sync(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synchronous wrapper for get_audio_metadata.
    
    FastMCP supports async tools, but this is available if needed.
    """
    import asyncio
    return asyncio.run(get_audio_metadata(input_data))


def search_library_sync(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synchronous wrapper for search_library.
    
    FastMCP supports async tools, but this is available if needed.
    """
    import asyncio
    return asyncio.run(search_library(input_data))

