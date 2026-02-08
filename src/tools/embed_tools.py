"""
Tools for generating embed URLs and configurations.
"""
import logging
from typing import Optional

from src.config import config
from src.exceptions import ValidationError
from database import get_audio_metadata_by_id

# Import PlayerConfig schemas for embed URL responses
from src.tools.schemas import (
    PlayerConfig,
    PlayerConfigUrls,
    PlayerConfigMetadata,
)

logger = logging.getLogger(__name__)


async def get_waveform_context(audio_id: str) -> dict:
    """
    Get waveform context for audio track (used by waveform embed endpoints).
    """
    try:
        from database.operations import get_waveform_metadata
        from src.storage.waveform_storage import get_waveform_signed_url

        metadata = get_waveform_metadata(audio_id)

        if metadata and metadata.get('waveform_gcs_path'):
            try:
                waveform_url = get_waveform_signed_url(audio_id)
                logger.debug(f"Waveform URL generated for audio_id: {audio_id}")
                return {
                    'waveform_url': waveform_url,
                    'waveform_available': True,
                    'waveform_generated_at': metadata.get('waveform_generated_at')
                }
            except Exception as e:
                logger.warning(f"Failed to generate waveform signed URL for {audio_id}: {e}")
    except Exception as e:
        logger.warning(f"Error retrieving waveform context for {audio_id}: {e}")

    return {
        'waveform_url': None,
        'waveform_available': False,
        'waveform_generated_at': None
    }


async def get_embed_url_logic(audio_id: str, template: str = "standard", device: Optional[str] = None) -> dict:
    """
    Logic for generating embed URL for audio track.
    """
    try:
        metadata = get_audio_metadata_by_id(audio_id)
        if not metadata:
            return {
                "success": False,
                "error": "RESOURCE_NOT_FOUND",
                "message": f"Audio track with ID '{audio_id}' was not found",
                "audio_id": audio_id
            }

        base_url = f"{config.embed_base_url}/embed/{audio_id}"
        embed_url = base_url
        if template == "waveform":
            embed_url = f"{base_url}/waveform"
            if device == "mobile":
                embed_url = f"{base_url}/waveform/mobile"
            elif device == "desktop":
                embed_url = f"{base_url}/waveform/desktop"

        waveform_available = False
        waveform_svg_url = None
        if template == "waveform":
            waveform_context = await get_waveform_context(audio_id)
            waveform_available = waveform_context.get("waveform_available", False)
            if waveform_available:
                from src.storage.waveform_storage import get_waveform_signed_url
                waveform_svg_url = get_waveform_signed_url(audio_id)
        
        artwork_url = None
        thumbnail_path = metadata.get("thumbnail_gcs_path")
        if thumbnail_path:
            from src.services.streaming_service import get_cache
            cache = get_cache()
            artwork_url = cache.get(thumbnail_path, url_expiration_minutes=15)

        mode = "waveform" if template == "waveform" else "simple"

        player_config = PlayerConfig(
            audio_id=audio_id,
            mode=mode,
            device=device or "auto",
            context="embed",
            waveform_available=waveform_available,
            urls=PlayerConfigUrls(
                embed=embed_url,
                waveform=f"{base_url}/waveform" if template == "waveform" else None,
                artwork=artwork_url,
                waveform_svg=waveform_svg_url
            ),
            metadata=PlayerConfigMetadata(
                title=metadata.get("title", "Untitled"),
                artist=metadata.get("artist", "Unknown Artist"),
                album=metadata.get("album"),
                duration_seconds=metadata.get("duration", 0)
            )
        )

        return {
            "success": True,
            **player_config.model_dump()
        }

    except ValidationError as e:
        return {
            "success": False, "error": "VALIDATION_ERROR",
            "message": f"Invalid audio ID format: {str(e)}", "audio_id": audio_id
        }
    except Exception as e:
        logger.error(f"Error generating embed URL for {audio_id}: {e}")
        return {
            "success": False, "error": "INTERNAL_ERROR",
            "message": "Failed to generate embed URL", "audio_id": audio_id
        }

