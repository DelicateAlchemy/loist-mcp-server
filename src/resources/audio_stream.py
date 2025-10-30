"""
Audio stream resource handler for MCP.

Implements audio streaming with:
- HTTP Range request support for seeking
- GCS signed URL integration
- Efficient streaming with proper headers
- CORS support for cross-origin access

Follows best practices from research:
- 206 Partial Content for range requests
- Accept-Ranges header
- Content-Type for audio formats
- Redirect to signed GCS URLs
"""

import logging
from typing import Dict, Any, Optional
import re

from database import get_audio_metadata_by_id
from src.exceptions import ResourceNotFoundError, ValidationError
from .cache import get_cache

logger = logging.getLogger(__name__)


# Audio format MIME types
AUDIO_MIME_TYPES = {
    "MP3": "audio/mpeg",
    "FLAC": "audio/flac",
    "M4A": "audio/mp4",
    "OGG": "audio/ogg",
    "WAV": "audio/wav",
    "AAC": "audio/aac",
    "OPUS": "audio/opus",
}


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
    if not gcs_path or not gcs_path.startswith("gs://"):
        raise ValueError(f"Invalid GCS path: {gcs_path}")
    
    path_without_prefix = gcs_path[5:]  # Remove "gs://"
    parts = path_without_prefix.split("/", 1)
    
    if len(parts) != 2:
        raise ValueError(f"Invalid GCS path format: {gcs_path}")
    
    return parts[0], parts[1]


async def get_audio_stream_resource(uri: str) -> Dict[str, Any]:
    """
    MCP resource handler for audio streams.
    
    Handles requests for audio streaming with support for:
    - HTTP Range requests (for seeking)
    - Signed GCS URLs (cached)
    - Proper Content-Type headers
    - CORS headers
    
    URI Format: music-library://audio/{audioId}/stream
    
    Args:
        uri: Resource URI
        
    Returns:
        dict: MCP resource response with redirect to signed URL
        
    Example:
        >>> response = await get_audio_stream_resource("music-library://audio/550e8400-.../stream")
        >>> print(response["mimeType"])
        "audio/mpeg"
    """
    logger.info(f"Audio stream resource requested: {uri}")
    
    try:
        # Parse URI to extract audioId
        # Format: music-library://audio/{audioId}/stream
        match = re.match(r"music-library://audio/([0-9a-fA-F-]+)/stream", uri)
        
        if not match:
            logger.error(f"Invalid audio stream URI format: {uri}")
            raise ValidationError(f"Invalid URI format: {uri}")
        
        audio_id = match.group(1)
        logger.debug(f"Requesting audio stream for ID: {audio_id}")
        
        # Get metadata from database
        try:
            metadata = get_audio_metadata_by_id(audio_id)
        except Exception as e:
            logger.error(f"Database error fetching metadata: {e}")
            raise
        
        if not metadata:
            logger.warning(f"Audio track not found: {audio_id}")
            raise ResourceNotFoundError(f"Audio track {audio_id} not found")
        
        # Get GCS audio path
        audio_path = metadata.get("audio_path")
        if not audio_path:
            logger.error(f"No audio_path in metadata for {audio_id}")
            raise ResourceNotFoundError(f"Audio file path not found for {audio_id}")
        
        # Get audio format for Content-Type
        audio_format = metadata.get("format", "MP3").upper()
        mime_type = AUDIO_MIME_TYPES.get(audio_format, "audio/mpeg")
        
        # Generate signed URL with caching
        cache = get_cache()
        try:
            signed_url = cache.get(
                gcs_path=audio_path,
                url_expiration_minutes=15
            )
        except Exception as e:
            logger.error(f"Failed to generate signed URL: {e}")
            raise
        
        logger.info(f"Generated signed URL for {audio_id} (format: {audio_format})")
        
        # Return MCP resource response
        # MCP resources can return content directly or provide a URI
        # For audio streams, we provide the signed GCS URL
        return {
            "uri": signed_url,
            "mimeType": mime_type,
            "text": None,  # Not applicable for binary audio
            "blob": None,  # Could stream blob directly, but signed URL is more efficient
        }
        
    except ResourceNotFoundError as e:
        logger.error(f"Resource not found: {e}")
        # MCP resources return None or raise exception for not found
        raise
        
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise
        
    except Exception as e:
        logger.exception(f"Unexpected error in audio stream resource: {e}")
        raise


def get_content_headers_for_audio(
    audio_format: str,
    support_ranges: bool = True
) -> Dict[str, str]:
    """
    Generate appropriate HTTP headers for audio streaming.
    
    Follows best practices from research:
    - Accept-Ranges for seeking support
    - Content-Type for proper MIME type
    - CORS headers for cross-origin access
    
    Args:
        audio_format: Audio format (e.g., "MP3", "FLAC")
        support_ranges: Whether to advertise range request support
        
    Returns:
        dict: HTTP headers for audio response
    """
    mime_type = AUDIO_MIME_TYPES.get(audio_format.upper(), "audio/mpeg")
    
    headers = {
        "Content-Type": mime_type,
        "Cache-Control": "public, max-age=3600",  # 1 hour cache
        "Access-Control-Allow-Origin": "*",  # CORS for audio streaming
        "Access-Control-Expose-Headers": "Content-Length, Content-Range, Accept-Ranges",
    }
    
    if support_ranges:
        headers["Accept-Ranges"] = "bytes"
    
    return headers
