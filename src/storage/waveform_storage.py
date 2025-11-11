"""
Waveform storage integration for Loist Music Library MCP Server.

Provides functionality for uploading SVG waveform files to Google Cloud Storage
and generating signed URLs for waveform access.

Features:
- SVG file upload with proper content-type
- Content-hash based file naming for cache invalidation
- Signed URL generation for secure access
- Integration with existing GCS client patterns
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any
from google.cloud import storage

from .gcs_client import create_gcs_client, GCSClient

logger = logging.getLogger(__name__)


def upload_waveform_svg(
    svg_path: Path,
    audio_id: str,
    content_hash: str,
    bucket_name: Optional[str] = None,
) -> str:
    """
    Upload SVG waveform file to Google Cloud Storage.

    Stores the waveform with a content-hash based filename for cache invalidation.
    The file structure is: waveforms/{audio_id}/{content_hash[:8]}.svg

    Args:
        svg_path: Local path to the SVG file
        audio_id: UUID of the audio track
        content_hash: SHA-256 hash of the source audio file
        bucket_name: GCS bucket name (optional, uses default if not provided)

    Returns:
        Full GCS path (gs://bucket/path) to the uploaded waveform

    Raises:
        FileNotFoundError: If SVG file doesn't exist
        Exception: If upload fails
    """
    if not svg_path.exists():
        raise FileNotFoundError(f"SVG file not found: {svg_path}")

    # Create client
    client = create_gcs_client(bucket_name=bucket_name)

    # Generate blob name with content hash for cache invalidation
    # Format: waveforms/{audio_id}/{content_hash_prefix}.svg
    content_hash_prefix = content_hash[:8]  # First 8 chars of hash
    blob_name = f"waveforms/{audio_id}/{content_hash_prefix}.svg"

    logger.info(f"Uploading waveform SVG to gs://{client.bucket_name}/{blob_name}")

    # Upload with proper content type
    blob = client.upload_file(
        source_path=svg_path,
        destination_blob_name=blob_name,
        content_type="image/svg+xml",  # Proper MIME type for SVG
        metadata={
            "audio_id": audio_id,
            "content_hash": content_hash,
            "file_type": "waveform_svg",
        }
    )

    gcs_path = f"gs://{client.bucket_name}/{blob_name}"
    logger.info(f"Successfully uploaded waveform SVG: {gcs_path}")

    return gcs_path


def get_waveform_signed_url(
    audio_id: str,
    bucket_name: Optional[str] = None,
    expiration_minutes: int = 60,
) -> Optional[str]:
    """
    Generate a signed URL for waveform access.

    Queries the database to get the waveform GCS path, then generates
    a signed URL for temporary access.

    Args:
        audio_id: UUID of the audio track
        bucket_name: GCS bucket name (optional, uses default if not provided)
        expiration_minutes: URL expiration time in minutes (default: 60)

    Returns:
        Signed URL string, or None if no waveform exists

    Raises:
        Exception: If signed URL generation fails
    """
    # Import here to avoid circular dependency
    from database.operations import get_waveform_metadata

    try:
        # Get waveform metadata from database
        metadata = get_waveform_metadata(audio_id)
        if not metadata or not metadata.get('waveform_gcs_path'):
            logger.debug(f"No waveform found for audio_id: {audio_id}")
            return None

        gcs_path = metadata['waveform_gcs_path']

        # Extract blob name from gs:// URL
        if not gcs_path.startswith('gs://'):
            logger.error(f"Invalid GCS path format: {gcs_path}")
            return None

        # Parse gs://bucket/path -> path
        path_part = gcs_path[5:]  # Remove 'gs://'
        slash_index = path_part.find('/')
        if slash_index == -1:
            logger.error(f"Invalid GCS path format: {gcs_path}")
            return None

        blob_name = path_part[slash_index + 1:]  # Everything after bucket/

        # Create GCS client and generate signed URL
        client = create_gcs_client(bucket_name=bucket_name)
        signed_url = client.generate_signed_url(
            blob_name=blob_name,
            expiration_minutes=expiration_minutes,
            method="GET",
            content_type="image/svg+xml",
        )

        logger.debug(f"Generated signed URL for waveform: {audio_id}")
        return signed_url

    except Exception as e:
        logger.error(f"Failed to generate waveform signed URL for {audio_id}: {e}")
        raise


def get_waveform_gcs_path(audio_id: str) -> Optional[str]:
    """
    Get the GCS path for a waveform file.

    Args:
        audio_id: UUID of the audio track

    Returns:
        GCS path string (gs://bucket/path), or None if no waveform exists
    """
    # Import here to avoid circular dependency
    from database.operations import get_waveform_metadata

    try:
        metadata = get_waveform_metadata(audio_id)
        return metadata.get('waveform_gcs_path') if metadata else None
    except Exception as e:
        logger.error(f"Failed to get waveform GCS path for {audio_id}: {e}")
        return None
