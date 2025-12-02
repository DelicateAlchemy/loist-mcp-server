"""
Audio stream resource handler for MCP.

This module acts as a thin wrapper around the streaming service, adapting
its functionality to the MCP resource protocol.
"""

import logging
from typing import Dict, Any
import re

from src.services import streaming_service
from src.exceptions import ResourceNotFoundError, ValidationError

logger = logging.getLogger(__name__)

async def get_audio_stream_resource(uri: str) -> Dict[str, Any]:
    """
    MCP resource handler for audio streams.
    
    URI Format: music-library://audio/{audioId}/stream
    """
    logger.info(f"Audio stream resource requested: {uri}")
    
    try:
        match = re.match(r"music-library://audio/([0-9a-f-]+)/stream", uri)
        if not match:
            raise ValidationError(f"Invalid URI format: {uri}")
        
        audio_id = match.group(1)
        
        details = await streaming_service.get_audio_stream_details(audio_id)
        
        return {
            "uri": details["signed_url"],
            "mimeType": details["mime_type"],
            "text": None,
            "blob": None,
        }
        
    except (ResourceNotFoundError, ValidationError) as e:
        logger.error(f"Error handling audio stream resource: {e}")
        raise  # Re-raise for the MCP framework to handle
    except Exception as e:
        logger.exception(f"Unexpected error in audio stream resource: {e}")
        raise