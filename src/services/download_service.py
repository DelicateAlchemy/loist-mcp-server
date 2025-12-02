"""
Service layer for audio download and conversion logic.

This service encapsulates the business logic for handling audio download
requests, including format conversion, metadata embedding, and streaming preparation.
"""

import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, AsyncGenerator

from src.converter import (
    convert_audio,
    ConversionError,
    ConversionTimeoutError,
    SUPPORTED_FORMATS,
    get_preset_config,
    get_mime_type,
    get_file_extension,
    validate_format,
    validate_preset,
    get_default_preset,
    get_supported_artwork_formats,
)
from src.storage import download_audio_file, generate_signed_url, parse_gcs_path
from database import get_audio_metadata_by_id
from src.exceptions import ResourceNotFoundError

logger = logging.getLogger(__name__)


def _normalize_format(extension: str) -> str:
    extension = extension.lower()
    format_map = {"mp3": "mp3", "wav": "wav", "wave": "wav", "flac": "flac", "m4a": "aac", "aac": "aac", "ogg": "ogg", "oga": "ogg", "opus": "ogg"}
    return format_map.get(extension, extension)


def _generate_download_filename(metadata: Dict[str, Any], target_format: str) -> str:
    title = metadata.get("title") or "Unknown"
    artist = metadata.get("artist") or "Unknown Artist"
    
    def sanitize(s: str) -> str:
        s = re.sub(r'[<>:"/\\|?*]', '', s)
        s = s.strip('. ')
        return s[:100]
    
    title = sanitize(title)
    artist = sanitize(artist)
    extension = get_file_extension(target_format)
    return f"{title} - {artist}{extension}"


async def prepare_audio_download(audio_id: str, target_format: str, preset: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
    """
    Prepares an audio file for download, converting it if necessary.

    Returns a tuple indicating the action to take ('redirect' or 'stream') and
    the necessary data for the web layer to construct the response.
    """
    metadata = get_audio_metadata_by_id(audio_id)
    if not metadata:
        raise ResourceNotFoundError(f"Track not found: {audio_id}")

    audio_gcs_path = metadata.get("audio_gcs_path")
    if not audio_gcs_path:
        raise ResourceNotFoundError(f"Audio file path not found for track: {audio_id}")

    source_ext = Path(audio_gcs_path).suffix.lower().lstrip(".")
    source_format = _normalize_format(source_ext)
    
    if not preset:
        preset = get_default_preset(target_format)

    # If no conversion is needed, redirect to a signed URL
    if source_format == target_format and preset == get_default_preset(target_format):
        logger.info(f"Service: Redirecting to original file for {audio_id}")
        _, blob_name = parse_gcs_path(audio_gcs_path)
        signed_url = generate_signed_url(blob_name, expiration_minutes=15)
        return "redirect", {"url": signed_url}

    # Conversion is needed
    logger.info(f"Service: Converting {audio_id} from {source_format} to {target_format} (preset: {preset})")

    temp_dir = tempfile.mkdtemp(prefix="loist_download_")
    source_path = Path(temp_dir) / f"source_{audio_id}{Path(audio_gcs_path).suffix}"
    output_ext = get_file_extension(target_format)
    output_path = Path(temp_dir) / f"converted_{audio_id}{output_ext}"
    artwork_path = None

    try:
        # Download source file
        _, blob_name = parse_gcs_path(audio_gcs_path)
        download_audio_file(blob_name=blob_name, destination_path=source_path, timeout=120)

        # Download artwork if available
        artwork_gcs_path = metadata.get('thumbnail_gcs_path')
        if artwork_gcs_path and get_supported_artwork_formats(target_format):
            try:
                artwork_path = Path(temp_dir) / f"artwork_{audio_id}{Path(artwork_gcs_path).suffix}"
                _, artwork_blob = parse_gcs_path(artwork_gcs_path)
                download_audio_file(blob_name=artwork_blob, destination_path=artwork_path, timeout=60)
            except Exception as e:
                logger.warning(f"Failed to download artwork {artwork_gcs_path}: {e}")
                artwork_path = None
        
        # Prepare metadata for embedding
        metadata_for_embedding = {k: v for k, v in metadata.items() if v is not None and k in [
            'title', 'artist', 'album', 'album_artist', 'genre', 'year', 'track_number', 'composer', 'publisher', 'isrc'
        ]}

        # Convert audio
        conversion_result = convert_audio(
            source_path=source_path,
            output_path=output_path,
            target_format=target_format,
            preset_name=preset,
            timeout_seconds=300,
            metadata=metadata_for_embedding,
            artwork_path=artwork_path,
        )
        if not conversion_result.success:
            raise ConversionError(conversion_result.error_message or "Conversion failed")

        download_filename = _generate_download_filename(metadata, target_format)
        mime_type = get_mime_type(target_format)
        file_size = output_path.stat().st_size

        return "stream", {
            "output_path": output_path,
            "mime_type": mime_type,
            "file_size": file_size,
            "download_filename": download_filename,
            "temp_dir": temp_dir,
            "conversion_time": conversion_result.processing_time_seconds,
        }

    except Exception:
        # Cleanup on error before re-raising
        try:
            if source_path and source_path.exists(): source_path.unlink()
            if output_path and output_path.exists(): output_path.unlink()
            if artwork_path and artwork_path.exists(): artwork_path.unlink()
            if temp_dir and Path(temp_dir).exists(): Path(temp_dir).rmdir()
        except Exception as cleanup_error:
            logger.warning(f"Cleanup on error failed: {cleanup_error}")
        raise

async def cleanup_temp_directory(temp_dir: str):
    """Safely cleans up a temporary directory and its contents."""
    try:
        if temp_dir and Path(temp_dir).exists():
            for p in Path(temp_dir).iterdir():
                p.unlink()
            Path(temp_dir).rmdir()
            logger.debug(f"Cleaned up temp dir: {temp_dir}")
    except Exception as e:
        logger.warning(f"Failed to cleanup temp files: {e}")
