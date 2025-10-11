"""
Thumbnail resource handler for MCP.

Provides thumbnail/album artwork access via signed GCS URLs
with caching and proper Content-Type headers.
"""

import logging
from typing import Dict, Any
import re

from database import get_audio_metadata_by_id
from src.exceptions import ResourceNotFoundError, ValidationError
from .cache import get_cache

logger = logging.getLogger(__name__)


async def get_thumbnail_resource(uri: str) -> Dict[str, Any]:
    """
    MCP resource handler for audio thumbnails/artwork.
    
    Returns signed URL to thumbnail image in GCS.
    
    URI Format: music-library://audio/{audioId}/thumbnail
    
    Args:
        uri: Resource URI
        
    Returns:
        dict: MCP resource response with signed URL to thumbnail
        
    Raises:
        ResourceNotFoundError: If audio or thumbnail not found
        ValidationError: If URI format is invalid
        
    Example:
        >>> response = await get_thumbnail_resource("music-library://audio/550e8400-.../thumbnail")
        >>> print(response["mimeType"])
        "image/jpeg"
    """
    logger.info(f"Thumbnail resource requested: {uri}")
    
    try:
        # Parse URI to extract audioId
        # Format: music-library://audio/{audioId}/thumbnail
        match = re.match(r"music-library://audio/([0-9a-f-]+)/thumbnail", uri)
        
        if not match:
            logger.error(f"Invalid thumbnail URI format: {uri}")
            raise ValidationError(f"Invalid URI format: {uri}")
        
        audio_id = match.group(1)
        logger.debug(f"Requesting thumbnail for ID: {audio_id}")
        
        # Get metadata from database
        try:
            metadata = get_audio_metadata_by_id(audio_id)
        except Exception as e:
            logger.error(f"Database error fetching metadata: {e}")
            raise
        
        if not metadata:
            logger.warning(f"Audio track not found: {audio_id}")
            raise ResourceNotFoundError(f"Audio track {audio_id} not found")
        
        # Check if thumbnail exists
        thumbnail_path = metadata.get("thumbnail_path")
        if not thumbnail_path:
            logger.warning(f"No thumbnail available for {audio_id}")
            raise ResourceNotFoundError(f"Thumbnail not available for audio {audio_id}")
        
        if not thumbnail_path.startswith("gs://"):
            logger.error(f"Invalid thumbnail path format: {thumbnail_path}")
            raise ValidationError(f"Invalid thumbnail path: {thumbnail_path}")
        
        # Generate signed URL with caching
        cache = get_cache()
        try:
            signed_url = cache.get(
                gcs_path=thumbnail_path,
                url_expiration_minutes=15
            )
        except Exception as e:
            logger.error(f"Failed to generate signed URL for thumbnail: {e}")
            raise
        
        logger.info(f"Generated signed URL for thumbnail {audio_id}")
        
        # Determine MIME type (default to JPEG for thumbnails)
        # Could parse from thumbnail_path extension if needed
        mime_type = "image/jpeg"
        
        # Return MCP resource response
        return {
            "uri": signed_url,
            "mimeType": mime_type,
            "text": None,
            "blob": None,
        }
        
    except ResourceNotFoundError as e:
        logger.error(f"Resource not found: {e}")
        raise
        
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise
        
    except Exception as e:
        logger.exception(f"Unexpected error in thumbnail resource: {e}")
        raise


def get_content_headers_for_thumbnail() -> Dict[str, str]:
    """
    Generate appropriate HTTP headers for thumbnail images.
    
    Returns:
        dict: HTTP headers for thumbnail response
    """
    return {
        "Content-Type": "image/jpeg",
        "Cache-Control": "public, max-age=86400",  # 24 hour cache (thumbnails don't change)
        "Access-Control-Allow-Origin": "*",  # CORS for images
        "Access-Control-Expose-Headers": "Content-Length, Content-Type",
    }

