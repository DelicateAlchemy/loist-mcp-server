"""
Thumbnail resource handler for MCP.

This module acts as a thin wrapper around the streaming service, adapting
its functionality to the MCP resource protocol for thumbnails.
"""

import logging
from typing import Dict, Any
import re

from src.services import streaming_service
from src.exceptions import ResourceNotFoundError, ValidationError

logger = logging.getLogger(__name__)


async def get_thumbnail_resource(uri: str) -> Dict[str, Any]:
    """
    MCP resource handler for audio thumbnails/artwork.
    
    URI Format: music-library://audio/{audioId}/thumbnail
    """
    logger.info(f"Thumbnail resource requested: {uri}")
    
    try:
        match = re.match(r"music-library://audio/([0-9a-f-]+)/thumbnail", uri)
        if not match:
            raise ValidationError(f"Invalid URI format: {uri}")
        
        audio_id = match.group(1)
        
        details = await streaming_service.get_thumbnail_details(audio_id)
        
        return {
            "uri": details["signed_url"],
            "mimeType": details["mime_type"],
            "text": None,
            "blob": None,
        }
        
    except (ResourceNotFoundError, ValidationError) as e:
        logger.error(f"Error handling thumbnail resource: {e}")
        raise  # Re-raise for the MCP framework to handle
    except Exception as e:
        logger.exception(f"Unexpected error in thumbnail resource: {e}")
        raise