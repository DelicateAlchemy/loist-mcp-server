"""
Service layer for streaming-related business logic.

This service handles the logic for generating signed URLs for audio streams
and thumbnails, including caching to improve performance.
"""

import logging
import time
from typing import Dict, Any, Optional
from threading import Lock

from src.storage import generate_signed_url, parse_gcs_path
from database import get_audio_metadata_by_id
from src.exceptions import ResourceNotFoundError

logger = logging.getLogger(__name__)


# ============================================================================
# Signed URL Cache
# ============================================================================

class _SignedURLCache:
    """In-memory cache for GCS signed URLs."""

    def __init__(self, default_ttl: int = 810):  # 13.5 minutes
        self.default_ttl = default_ttl
        self.cache: Dict[str, str] = {}
        self.expiry: Dict[str, float] = {}
        self.lock = Lock()
        self.hits = 0
        self.misses = 0
        logger.info(f"Signed URL cache initialized with TTL={default_ttl}s")

    def get(self, gcs_path: str, url_expiration_minutes: int = 15) -> str:
        """Get a signed URL from cache or generate a new one."""
        with self.lock:
            current_time = time.time()
            if gcs_path in self.cache and self.expiry.get(gcs_path, 0) > current_time:
                self.hits += 1
                logger.debug(f"Cache HIT for {gcs_path}")
                return self.cache[gcs_path]

            self.misses += 1
            logger.debug(f"Cache MISS for {gcs_path}")
            
            bucket_name, blob_name = parse_gcs_path(gcs_path)
            
            signed_url = generate_signed_url(
                bucket_name=bucket_name,
                blob_name=blob_name,
                expiration_minutes=url_expiration_minutes
            )
            
            cache_ttl = url_expiration_minutes * 60 * 0.9
            self.cache[gcs_path] = signed_url
            self.expiry[gcs_path] = current_time + cache_ttl
            
            logger.info(f"Generated and cached signed URL for {gcs_path}")
            return signed_url

_cache: Optional[_SignedURLCache] = None

def get_cache() -> _SignedURLCache:
    global _cache
    if _cache is None:
        _cache = _SignedURLCache()
    return _cache


# ============================================================================
# Constants
# ============================================================================

AUDIO_MIME_TYPES = {
    "MP3": "audio/mpeg",
    "FLAC": "audio/flac",
    "M4A": "audio/mp4",
    "OGG": "audio/ogg",
    "WAV": "audio/wav",
    "AAC": "audio/aac",
    "OPUS": "audio/opus",
}


# ============================================================================
# Public Service Functions
# ============================================================================

async def get_audio_stream_details(audio_id: str) -> Dict[str, Any]:
    """
    Get details required for streaming an audio track.

    Args:
        audio_id: The UUID of the audio track.

    Returns:
        A dictionary with the signed URL and MIME type.

    Raises:
        ResourceNotFoundError: If the audio track or its path is not found.
    """
    logger.debug(f"Service: Getting audio stream details for {audio_id}")
    metadata = get_audio_metadata_by_id(audio_id)
    if not metadata:
        raise ResourceNotFoundError(f"Audio track {audio_id} not found")

    audio_path = metadata.get("audio_gcs_path") or metadata.get("audio_path") # Support both legacy and new schema
    if not audio_path:
        raise ResourceNotFoundError(f"Audio file path not found for {audio_id}")

    audio_format = metadata.get("format", "MP3").upper()
    mime_type = AUDIO_MIME_TYPES.get(audio_format, "audio/mpeg")

    cache = get_cache()
    signed_url = cache.get(gcs_path=audio_path, url_expiration_minutes=15)

    return {"signed_url": signed_url, "mime_type": mime_type}


async def get_thumbnail_details(audio_id: str) -> Dict[str, Any]:
    """
    Get details for serving a thumbnail image.

    Args:
        audio_id: The UUID of the audio track.

    Returns:
        A dictionary with the signed URL and MIME type.

    Raises:
        ResourceNotFoundError: If the thumbnail is not found.
    """
    logger.debug(f"Service: Getting thumbnail details for {audio_id}")
    metadata = get_audio_metadata_by_id(audio_id)
    if not metadata:
        raise ResourceNotFoundError(f"Audio track {audio_id} not found")

    thumbnail_path = metadata.get("thumbnail_gcs_path") or metadata.get("thumbnail_path")
    if not thumbnail_path:
        raise ResourceNotFoundError(f"Thumbnail not available for audio {audio_id}")

    cache = get_cache()
    signed_url = cache.get(gcs_path=thumbnail_path, url_expiration_minutes=15)
    
    # Simple assumption for now, could be improved by checking file extension
    mime_type = "image/jpeg"

    return {"signed_url": signed_url, "mime_type": mime_type}
