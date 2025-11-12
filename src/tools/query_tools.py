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
    DeleteAudioInput,
    DeleteAudioOutput,
    DeleteException,
)
from .search_filter_parser import (
    parse_rsql_filter,
    encode_cursor,
    decode_cursor,
    parse_field_selection,
    apply_field_selection,
    RSQLParseError,
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
    search_audio_tracks_cursor,
)
from database.utils import AudioTrackDB
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
    from config import config
    audio_id = db_metadata.get("id")
    embed_url = f"{config.embed_base_url}/embed/{audio_id}"
    
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
    format_metadata = FormatMetadata(
        Duration=db_metadata.get("duration_seconds", 0.0),
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
            has_thumbnail=bool(db_metadata.get("thumbnail_gcs_path"))
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
    
    Performs full-text search with RSQL filters and cursor-based pagination.
    Supports sparse field selection for optimized responses.
    
    Args:
        input_data: Dictionary containing query, filter, fields, cursor, limit, and sort options
        
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
        filter_str = validated_input.filter
        fields_str = validated_input.fields
        limit = validated_input.limit
        cursor = validated_input.cursor
        sort_by = validated_input.sortBy
        sort_order = validated_input.sortOrder

        logger.debug(f"Searching for: '{query}' with filter='{filter_str}', cursor='{cursor}', limit={limit}")
        
        # Parse RSQL filter string
        try:
            parsed_filters = parse_rsql_filter(filter_str) if filter_str else {}
        except RSQLParseError as e:
            logger.error(f"RSQL parsing failed: {e}")
            raise QueryException(
                error_code=QueryErrorCode.INVALID_FILTER,
                message=f"Invalid filter syntax: {str(e)}",
                details={"filter": filter_str}
            )

        # Parse field selection
        requested_fields = parse_field_selection(fields_str) if fields_str else None

        # Decode cursor if provided
        cursor_data = None
        if cursor:
            try:
                cursor_score, cursor_created_at, cursor_id = decode_cursor(cursor)
                cursor_data = (cursor_score, cursor_created_at, cursor_id)
            except Exception as e:
                logger.error(f"Cursor decoding failed: {e}")
                raise QueryException(
                    error_code=QueryErrorCode.PAGINATION_ERROR,
                    message=f"Invalid cursor format: {str(e)}",
                    details={"cursor": cursor}
                )

        # Build database filter parameters from parsed RSQL filters
        filter_params = {}

        # Always filter for completed tracks only
        filter_params["status_filter"] = "COMPLETED"

        # Map parsed RSQL filters to database parameters
        if "year_min" in parsed_filters:
            filter_params["year_min"] = parsed_filters["year_min"]
        if "year_max" in parsed_filters:
            filter_params["year_max"] = parsed_filters["year_max"]
        if "format_filter" in parsed_filters:
            filter_params["format_filter"] = parsed_filters["format_filter"]
        
        # Determine sort field mapping
        sort_field_map = {
            "relevance": "score",  # Default from search
            "title": "title",
            "artist": "artist",
            "year": "year",
            "duration": "duration",
            "created_at": "created_at"
        }
        
        db_sort_field = sort_field_map.get(sort_by.value, "score")
        db_sort_order = sort_order.value  # "asc" or "desc"
        
        # Execute search query with cursor-based pagination
        try:
            search_results = search_audio_tracks_cursor(
                query=query,
                limit=limit + 1,  # Fetch one extra to check if more results exist
                cursor_data=cursor_data,
                min_rank=0.01,  # Minimum relevance threshold
                **filter_params
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
        
        # Extract tracks from search result
        tracks = search_results.get('tracks', [])
        has_more = len(tracks) > limit

        # Trim to requested limit
        if has_more:
            tracks = tracks[:limit]

        logger.info(f"Found {len(tracks)} results for '{query}' (has_more: {has_more})")

        # Format results
        formatted_results = []
        next_cursor = None

        for i, result in enumerate(tracks):
            try:
                # Get metadata from result
                db_metadata = {
                    "id": result.get("id"),
                    "artist": result.get("artist", ""),
                    "title": result.get("title", "Untitled"),
                    "album": result.get("album", ""),
                    "genre": result.get("genre"),
                    "year": result.get("year"),
                    "duration_seconds": result.get("duration_seconds", 0.0),
                    "channels": result.get("channels", 2),
                    "sample_rate": result.get("sample_rate", 44100),
                    "bitrate": result.get("bitrate", 0),
                    "format": result.get("format", ""),
                    "thumbnail_gcs_path": result.get("thumbnail_gcs_path")
                }

                # Format metadata
                formatted_metadata = format_metadata_response(db_metadata)

                # Get relevance score
                score = float(result.get("rank", 0.0))

                # Create search result
                search_result = SearchResult(
                    audioId=result.get("id"),
                    metadata=formatted_metadata,
                    score=score
                )

                # Apply field selection if requested
                if requested_fields:
                    result_dict = search_result.model_dump()
                    filtered_result = apply_field_selection(result_dict, requested_fields)
                    # Reconstruct SearchResult from filtered data
                    search_result = SearchResult(**filtered_result)

                formatted_results.append(search_result)

                # Generate next cursor from last result
                if i == len(tracks) - 1 and has_more:
                    next_cursor = encode_cursor(
                        score=score,
                        created_at=result.get("created_at", ""),
                        track_id=result.get("id")
                    )

            except Exception as e:
                logger.warning(f"Error formatting search result: {e}")
                continue  # Skip this result and continue with others

        # Build response
        response = SearchLibraryOutput(
            success=True,
            results=formatted_results,
            limit=limit,
            hasMore=has_more,
            nextCursor=next_cursor
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


async def delete_audio(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Delete a previously processed audio track.

    This is a destructive operation that permanently removes an audio track
    from the database. GCS files are left in place for lifecycle management.

    Args:
        input_data: Dictionary containing audioId and optional userId for future auth

    Returns:
        Dictionary with success status and deletion confirmation, or error response

    Raises:
        DeleteException: For not found or database errors

    Example:
        >>> result = await delete_audio({"audioId": "550e8400-..."})
        >>> print(result["deleted"])
        True
    """
    logger.info("Deleting audio track")

    try:
        # Validate input
        try:
            validated_input = DeleteAudioInput(**input_data)
        except Exception as e:
            logger.error(f"Input validation failed: {e}")
            raise DeleteException(
                error_code=QueryErrorCode.INVALID_QUERY,
                message=f"Invalid input: {str(e)}",
                details={"validation_errors": str(e)}
            )

        audio_id = validated_input.audioId
        logger.debug(f"Deleting audio track: {audio_id}")

        # TODO: Add user authorization check when auth is implemented
        # if validated_input.userId:
        #     # Verify user owns the track or has delete permissions
        #     pass

        # Delete from database
        try:
            from uuid import UUID
            track_id = UUID(audio_id)
            deleted = AudioTrackDB.delete_track(track_id)
        except DatabaseOperationError as e:
            logger.error(f"Database error deleting track: {e}")
            raise DeleteException(
                error_code=QueryErrorCode.DATABASE_ERROR,
                message=f"Failed to delete track: {str(e)}",
                details={"audioId": audio_id}
            )
        except Exception as e:
            logger.error(f"Unexpected error during deletion: {e}")
            raise DeleteException(
                error_code=QueryErrorCode.DELETE_FAILED,
                message=f"Unexpected error deleting track: {str(e)}",
                details={"audioId": audio_id, "exception_type": type(e).__name__}
            )

        # Log deletion result
        if deleted:
            logger.info(f"Successfully deleted track: {audio_id}")
        else:
            logger.warning(f"Track not found for deletion: {audio_id}")
            raise DeleteException(
                error_code=QueryErrorCode.RESOURCE_NOT_FOUND,
                message=f"Audio track with ID '{audio_id}' was not found",
                details={"audioId": audio_id}
            )

        # Build success response using Pydantic for validation
        response = DeleteAudioOutput(
            success=True,
            audioId=audio_id,
            deleted=deleted
        )

        return response.model_dump()

    except DeleteException as e:
        # Known delete error
        logger.error(f"Delete error: {e.message}")
        error_response = e.to_error_response()
        return error_response.model_dump()

    except Exception as e:
        # Unexpected error
        logger.exception(f"Unexpected error deleting track: {e}")
        error_response = DeleteException(
            error_code=QueryErrorCode.DELETE_FAILED,
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


def delete_audio_sync(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synchronous wrapper for delete_audio.

    FastMCP supports async tools, but this is available if needed.
    """
    import asyncio
    return asyncio.run(delete_audio(input_data))

