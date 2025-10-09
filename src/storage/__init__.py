"""
Google Cloud Storage integration for Loist Music Library MCP Server.

This module provides utilities for managing audio file storage in GCS,
including signed URL generation, file uploads, and lifecycle management.
"""

from .gcs_client import (
    create_gcs_client,
    generate_signed_url,
    upload_audio_file,
    delete_file,
    list_audio_files,
    get_file_metadata,
)

__all__ = [
    "create_gcs_client",
    "generate_signed_url",
    "upload_audio_file",
    "delete_file",
    "list_audio_files",
    "get_file_metadata",
]

