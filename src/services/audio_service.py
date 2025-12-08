"""
Service layer for audio-related business logic.

This service centralizes operations for retrieving, searching, and managing
audio track data, separating business logic from the transport layer (MCP/HTTP).
"""

import logging
from typing import Dict, Any, List, Optional

from src.schemas.metadata import (
    AudioMetadata,
    AudioResources,
    ProductMetadata,
    FormatMetadata,
)
from database import (
    get_audio_metadata_by_id,
    filter_audio_tracks_combined,
    get_xmp_field_facets,
    delete_audio_track,
)
from src.exceptions import (
    DatabaseOperationError,
    ResourceNotFoundError,
)
from src.storage.gcs_client import GCSClient
from src.tools.query_schemas import SearchResult, SearchFacets, FacetData

logger = logging.getLogger(__name__)

# ============================================================================
# Constants
# ============================================================================

# Database-imposed maximum limit for queries (used for pagination boundary handling)
DATABASE_MAX_LIMIT = 100

# ============================================================================
# Private Helper Functions
# ============================================================================

def _format_metadata_response(db_metadata: Dict[str, Any]) -> AudioMetadata:
    """
    Format database metadata into the AudioMetadata Pydantic model.
    """
    audio_id = db_metadata.get("id")
    embed_url = f"https://loist.io/embed/{audio_id}"

    product = ProductMetadata(
        artist=db_metadata.get("artist") or "",
        title=db_metadata.get("title") or "Untitled",
        album=db_metadata.get("album") or "",
        mbid=None,  # MVP: null
        genre=[db_metadata.get("genre")] if db_metadata.get("genre") else [],
        year=db_metadata.get("year"),
    )

    duration = db_metadata.get("duration") or db_metadata.get("duration_seconds", 0.0)
    format_meta = FormatMetadata(
        duration=duration,
        channels=db_metadata.get("channels", 2),
        sample_rate=db_metadata.get("sample_rate", 44100),
        bitrate=db_metadata.get("bitrate", 0),
        format=db_metadata.get("format", ""),
    )

    return AudioMetadata(
        product=product,
        format=format_meta,
        url_embed_link=embed_url,
    )


def _format_resources(audio_id: str, has_thumbnail: bool = False) -> AudioResources:
    """
    Generate resource URIs for an audio track.
    """
    return AudioResources(
        audio_url=f"music-library://audio/{audio_id}/stream",
        thumbnail_url=f"music-library://audio/{audio_id}/thumbnail" if has_thumbnail else None,
        waveform_url=None,  # MVP: null
    )


# ============================================================================
# Public Service Functions
# ============================================================================

async def get_audio_metadata(audio_id: str) -> Dict[str, Any]:
    """
    Retrieve and format metadata for a single audio track.

    Args:
        audio_id: The UUID of the audio track.

    Returns:
        A dictionary containing the formatted metadata and resources.

    Raises:
        ResourceNotFoundError: If the audio track is not found.
        DatabaseOperationError: If a database error occurs.
    """
    logger.debug(f"Service: Fetching metadata for audio ID: {audio_id}")
    db_metadata = get_audio_metadata_by_id(audio_id)

    if not db_metadata:
        logger.warning(f"Service: Audio track not found: {audio_id}")
        raise ResourceNotFoundError(f"Audio track with ID '{audio_id}' was not found")

    if db_metadata.get("album") is None:
        db_metadata["album"] = ""

    formatted_metadata = _format_metadata_response(db_metadata)
    resources = _format_resources(
        audio_id, has_thumbnail=bool(db_metadata.get("thumbnail_gcs_path"))
    )

    return {
        "audio_id": audio_id,
        "metadata": formatted_metadata,
        "resources": resources,
    }


async def search_audio_library(
    query: str,
    limit: int,
    offset: int,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Search the audio library with optional filters.

    Args:
        query: The search query string.
        limit: The maximum number of results to return.
        offset: The number of results to skip.
        filters: A dictionary of filters to apply.

    Returns:
        A dictionary containing search results, total count, and pagination info.

    Raises:
        DatabaseOperationError: If the search fails.
    """
    logger.debug(f"Service: Searching for '{query}' with limit={limit}, offset={offset}")

    xmp_filters = {}
    if filters:
        xmp_filters = {
            'composer_filter': filters.get('composer'),
            'publisher_filter': filters.get('publisher'),
            'record_label_filter': filters.get('record_label'),
            'isrc_filter': filters.get('isrc'),
            'year_min': filters.get('year', {}).get('min'),
            'year_max': filters.get('year', {}).get('max'),
            'format_filter': filters.get('format', [None])[0] if filters.get('format') else None,
            'time_period': filters.get('time', {}).get('period'),
            'date_from': filters.get('time', {}).get('date_from'),
            'date_to': filters.get('time', {}).get('date_to'),
            'timezone': filters.get('time', {}).get('timezone', 'UTC'),
        }

    # Pagination boundary handling:
    # - For limit < DATABASE_MAX_LIMIT: use +1 approach (fetch extra to determine has_more)
    # - For limit = DATABASE_MAX_LIMIT: use total_count approach (avoid exceeding DB limit)
    if limit < DATABASE_MAX_LIMIT:
        actual_limit = limit + 1
        use_count_for_has_more = False
    else:
        actual_limit = limit  # Don't exceed database max
        use_count_for_has_more = True
        logger.debug(f"Using count-based has_more (limit={limit} at database max)")

    search_response = filter_audio_tracks_combined(
        query=query,
        limit=actual_limit,
        offset=offset,
        min_rank=0.01,
        **xmp_filters,
    )

    search_results = search_response.get('tracks', [])
    total_matches = search_response.get('total_count', 0)

    if use_count_for_has_more:
        # At database limit: use total_count to determine has_more
        has_more = (offset + limit) < total_matches
    else:
        # Standard case: use +1 fetch approach
        has_more = len(search_results) > limit
        if has_more:
            search_results = search_results[:limit]

    formatted_results = []
    for result in search_results:
        db_metadata = {**result, "duration": result.get("duration_seconds", 0.0)}
        formatted_metadata = _format_metadata_response(db_metadata)
        score = float(result.get("rank", 0.0))
        formatted_results.append(
            SearchResult(
                audio_id=result.get("id"), metadata=formatted_metadata, score=score
            )
        )

    try:
        facets_data = get_xmp_field_facets(composer_limit=20, publisher_limit=20, record_label_limit=20, min_count=1)
        facets = SearchFacets(
            composers=[FacetData(**f) for f in facets_data.get('composers', [])],
            publishers=[FacetData(**f) for f in facets_data.get('publishers', [])],
            record_labels=[FacetData(**f) for f in facets_data.get('record_labels', [])],
        )
    except Exception as e:
        logger.warning(f"Failed to retrieve facets: {e}")
        facets = None

    return {
        "results": formatted_results,
        "total": total_matches,
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
        "facets": facets,
    }


async def delete_audio_track_and_files(audio_id: str) -> bool:
    """
    Delete an audio track from the database and its associated GCS files.

    Args:
        audio_id: The UUID of the audio track to delete.

    Returns:
        True if the database deletion was successful, False otherwise.

    Raises:
        ResourceNotFoundError: If the track is not found in the database.
        DatabaseOperationError: If the database deletion fails.
    """
    logger.debug(f"Service: Deleting audio track: {audio_id}")
    deleted_track = delete_audio_track(audio_id)

    gcs_paths = [
        path for key, path in deleted_track.items()
        if key.endswith("_gcs_path") and path
    ]

    if gcs_paths:
        try:
            gcs_client = GCSClient()
            for gcs_path in gcs_paths:
                try:
                    blob_name = gcs_path.split("/", 3)[-1]
                    gcs_client.delete_file(blob_name)
                    logger.info(f"Service: Deleted GCS file: {gcs_path}")
                except Exception as e:
                    logger.warning(f"Service: Failed to delete GCS file {gcs_path}: {e}")
        except Exception as e:
            logger.warning(f"Service: Failed to initialize GCS client for cleanup: {e}")

    return True
