"""
Metadata resource handler for MCP.

Provides metadata access via MCP resources with proper
Content-Type headers and caching.
"""

import logging
from typing import Dict, Any
import re
import json

from database import get_audio_metadata_by_id
from src.exceptions import ResourceNotFoundError, ValidationError

logger = logging.getLogger(__name__)


async def get_metadata_resource(uri: str) -> Dict[str, Any]:
    """
    MCP resource handler for audio metadata.
    
    Returns complete metadata as JSON.
    
    URI Format: music-library://audio/{audioId}/metadata
    
    Args:
        uri: Resource URI
        
    Returns:
        dict: MCP resource response with JSON metadata
        
    Example:
        >>> response = await get_metadata_resource("music-library://audio/550e8400-.../metadata")
        >>> print(response["mimeType"])
        "application/json"
    """
    logger.info(f"Metadata resource requested: {uri}")
    
    try:
        # Parse URI to extract audioId
        # Format: music-library://audio/{audioId}/metadata
        match = re.match(r"music-library://audio/([0-9a-fA-F-]+)/metadata", uri)
        
        if not match:
            logger.error(f"Invalid metadata URI format: {uri}")
            raise ValidationError(f"Invalid URI format: {uri}")
        
        audio_id = match.group(1)
        logger.debug(f"Requesting metadata for ID: {audio_id}")
        
        # Get metadata from database
        try:
            metadata = get_audio_metadata_by_id(audio_id)
        except Exception as e:
            logger.error(f"Database error fetching metadata: {e}")
            raise
        
        if not metadata:
            logger.warning(f"Audio track not found: {audio_id}")
            raise ResourceNotFoundError(f"Audio track {audio_id} not found")
        
        # Format metadata for response
        response_data = {
            "id": metadata.get("id"),
            "Product": {
                "Artist": metadata.get("artist", ""),
                "Title": metadata.get("title", "Untitled"),
                "Album": metadata.get("album", ""),
                "MBID": None,  # MVP: null
                "Genre": [metadata.get("genre")] if metadata.get("genre") else [],
                "Year": metadata.get("year")
            },
            "Format": {
                "Duration": metadata.get("duration", 0.0),
                "Channels": metadata.get("channels", 2),
                "SampleRate": metadata.get("sample_rate", 44100),
                "Bitrate": metadata.get("bitrate", 0),
                "Format": metadata.get("format", "")
            },
            "urlEmbedLink": f"http://localhost:8080/embed/{audio_id}",
            "resources": {
                "audio": f"music-library://audio/{audio_id}/stream",
                "thumbnail": f"music-library://audio/{audio_id}/thumbnail" if metadata.get("thumbnail_path") else None,
                "waveform": None
            }
        }
        
        logger.info(f"Returning metadata for {audio_id}")
        
        # Return MCP resource response
        return {
            "uri": uri,
            "mimeType": "application/json",
            "text": json.dumps(response_data, indent=2),
            "blob": None,
        }
        
    except ResourceNotFoundError as e:
        logger.error(f"Resource not found: {e}")
        raise
        
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise
        
    except Exception as e:
        logger.exception(f"Unexpected error in metadata resource: {e}")
        raise
