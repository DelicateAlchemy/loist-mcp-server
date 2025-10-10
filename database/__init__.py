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
)

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
]

