"""
MCP Tools for Loist Music Library Server.

This module provides MCP tool implementations for audio processing and query workflows.
"""

# Task 7: Audio processing tools
from .process_audio import process_audio_complete, ProcessAudioError

# Task 8: Query/retrieval tools
from .query_tools import get_audio_metadata, search_library, delete_audio
from .query_schemas import (
    QueryException,
    DeleteAudioInput,
    DeleteAudioOutput,
)

# Update/edit tools
from .update_tools import update_metadata
from .update_schemas import (
    UpdateMetadataInput,
    UpdateMetadataOutput,
    UpdateMetadataError,
    UpdateErrorCode,
    TrackMetadataUpdate,
)

# Download/conversion tools
from .download_tool import download_audio

__all__ = [
    # Task 7
    "process_audio_complete",
    "ProcessAudioError",
    # Task 8
    "get_audio_metadata",
    "search_library",
    "delete_audio",
    "QueryException",
    "DeleteAudioInput",
    "DeleteAudioOutput",
    # Update tools
    "update_metadata",
    "UpdateMetadataInput",
    "UpdateMetadataOutput",
    "UpdateMetadataError",
    "UpdateErrorCode",
    "TrackMetadataUpdate",
    # Download tools
    "download_audio",
]
