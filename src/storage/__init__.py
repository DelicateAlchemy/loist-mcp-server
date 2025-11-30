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
    download_audio_file,
    delete_file,
    list_audio_files,
    get_file_metadata,
)
from .waveform_storage import (
    upload_waveform_svg,
    get_waveform_signed_url,
    get_waveform_gcs_path,
)


def parse_gcs_path(gcs_path: str) -> tuple[str, str]:
    """
    Parse GCS path into bucket and blob name.

    Args:
        gcs_path: Full GCS path (gs://bucket/path/to/file)

    Returns:
        tuple: (bucket_name, blob_name)

    Raises:
        ValueError: If path format is invalid
    """
    if not gcs_path.startswith('gs://'):
        raise ValueError(f"Invalid GCS path format: {gcs_path}")

    path_without_scheme = gcs_path[5:]  # Remove 'gs://'
    first_slash_index = path_without_scheme.find('/')

    if first_slash_index == -1:
        raise ValueError(f"Invalid GCS path format: {gcs_path}")

    bucket_name = path_without_scheme[:first_slash_index]
    blob_name = path_without_scheme[first_slash_index + 1:]

    if not bucket_name:
        raise ValueError(f"Invalid GCS path format: {gcs_path}")

    return bucket_name, blob_name

__all__ = [
    "GCSClient",
    "create_gcs_client",
    "generate_signed_url",
    "upload_audio_file",
    "download_audio_file",
    "delete_file",
    "list_audio_files",
    "get_file_metadata",
    "upload_waveform_svg",
    "get_waveform_signed_url",
    "get_waveform_gcs_path",
    "parse_gcs_path",
]

