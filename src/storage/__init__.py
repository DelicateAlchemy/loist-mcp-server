"""
Google Cloud Storage integration for Loist Music Library MCP Server.

This module provides utilities for managing audio file storage in GCS,
including signed URL generation, file uploads, and lifecycle management.
"""

from .gcs_client import (
    GCSClient,
    create_gcs_client,
    generate_signed_url,
    upload_audio_file,
    delete_file,
    list_audio_files,
    get_file_metadata,
)
from .waveform_storage import (
    upload_waveform_svg,
    get_waveform_signed_url,
    get_waveform_gcs_path,
)

__all__ = [
    "GCSClient",
    "create_gcs_client",
    "generate_signed_url",
    "upload_audio_file",
    "delete_file",
    "list_audio_files",
    "get_file_metadata",
    "upload_waveform_svg",
    "get_waveform_signed_url",
    "get_waveform_gcs_path",
]

