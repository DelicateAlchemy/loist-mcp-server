"""
Database module for Loist Music Library MCP Server.

Provides connection pooling, query utilities, and database management
for PostgreSQL interactions.
"""

from .pool import (
    DatabasePool,
    get_connection_pool,
    get_connection,
    close_pool,
)
from .operations import (
    save_audio_metadata,
    save_audio_metadata_batch,
    get_audio_metadata_by_id,
    get_audio_metadata_by_ids,
    get_all_audio_metadata,
    search_audio_tracks,
    search_audio_tracks_advanced,
    filter_audio_tracks_xmp,
    filter_audio_tracks_combined,
    get_xmp_field_facets,
    filter_audio_tracks_cursor_xmp,
    encode_cursor,
    decode_cursor,
    update_processing_status,
    update_processing_status_batch,
    mark_as_failed,
    mark_as_completed,
    mark_as_processing,
)
from .utils import check_database_availability

__all__ = [
    "DatabasePool",
    "get_connection_pool",
    "get_connection",
    "close_pool",
    "save_audio_metadata",
    "save_audio_metadata_batch",
    "get_audio_metadata_by_id",
    "get_audio_metadata_by_ids",
    "get_all_audio_metadata",
    "search_audio_tracks",
    "search_audio_tracks_advanced",
    "filter_audio_tracks_xmp",
    "filter_audio_tracks_combined",
    "get_xmp_field_facets",
    "filter_audio_tracks_cursor_xmp",
    "encode_cursor",
    "decode_cursor",
    "update_processing_status",
    "update_processing_status_batch",
    "mark_as_failed",
    "mark_as_completed",
    "mark_as_processing",
]

