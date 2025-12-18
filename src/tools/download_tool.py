"""
Download tool for Loist Music Library MCP Server.

Provides download_audio MCP tool for downloading audio tracks in specified formats
with on-the-fly conversion and metadata embedding.
"""

import logging
import os
import uuid
from typing import Dict, Any, Optional
from pathlib import Path
import tempfile
import time

from .schemas import (
    AudioMetadata,
    AudioResources,
)
from src.config import get_safe_temp_dir
from src.exceptions import ValidationError, ResourceNotFoundError
from src.error_utils import handle_tool_error
from src.storage import generate_signed_url, parse_gcs_path, download_audio_file
from src.converter import (
    convert_audio,
    ConversionError,
    ConversionTimeoutError,
    validate_format,
    validate_preset,
    get_default_preset,
    get_mime_type,
    get_file_extension,
    get_supported_artwork_formats,
)

# Import database operations
from database import get_audio_metadata_by_id

logger = logging.getLogger(__name__)


def download_audio(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Download audio track in specified format with conversion.

    This tool downloads an audio track, converts it to the requested format
    with metadata embedding, and returns a temporary download URL.

    Args:
        input_data: Dictionary containing:
            - audio_id: UUID of the audio track (required)
            - format: Target format (mp3, wav, flac, aac, ogg) (required)
            - preset: Quality preset (optional, defaults to 'high')

    Returns:
        Dictionary containing:
            - success: Boolean indicating success
            - download_url: Temporary signed URL for download
            - format: Target format used
            - quality: Quality description (e.g., "320kbps")
            - original_format: Source format
            - file_size: File size in bytes
            - filename: Generated filename
            - expires_in: URL expiration time in seconds
            - error: Error message if failed

    Raises:
        ValidationError: If input parameters are invalid
        ResourceNotFoundError: If audio track is not found
        ConversionError: If audio conversion fails
    """
    try:
        logger.info(f"Download audio request: {input_data}")

        # Extract and validate parameters
        audio_id = input_data.get("audio_id")
        if not audio_id:
            raise ValidationError("audio_id is required")

        # Validate UUID format
        try:
            uuid.UUID(audio_id)
        except ValueError:
            raise ValidationError(f"Invalid audio_id format: {audio_id}")

        target_format = input_data.get("format")
        if not target_format:
            raise ValidationError("format is required")

        target_format = target_format.lower()
        if not validate_format(target_format):
            from src.converter import SUPPORTED_FORMATS
            raise ValidationError(
                f"Unsupported format '{target_format}'. Supported: {list(SUPPORTED_FORMATS)}"
            )

        preset = input_data.get("preset")
        if preset:
            preset = preset.lower()
            if not validate_preset(target_format, preset):
                from src.converter.presets import FORMAT_PRESETS
                valid_presets = list(FORMAT_PRESETS[target_format].keys())
                raise ValidationError(
                    f"Invalid preset '{preset}' for format '{target_format}'. Valid: {valid_presets}"
                )
        else:
            preset = get_default_preset(target_format)

        # Get track metadata from database
        metadata = get_audio_metadata_by_id(audio_id)
        if not metadata:
            raise ResourceNotFoundError(f"Audio track not found: {audio_id}")

        # Get GCS audio path
        audio_gcs_path = metadata.get("audio_gcs_path")
        if not audio_gcs_path:
            raise ResourceNotFoundError(f"Audio file path not found for track: {audio_id}")

        # Check if track is completed
        if metadata.get("status") != "COMPLETED":
            raise ValidationError(f"Track {audio_id} is not ready for download (status: {metadata.get('status')})")

        # Get source format from path extension
        source_ext = Path(audio_gcs_path).suffix.lower().lstrip(".")
        source_format = _normalize_format(source_ext)

        # Short-circuit check: if same format and default preset, return direct URL
        if source_format == target_format and preset == get_default_preset(target_format):
            logger.info(f"Short-circuit: returning direct URL for {audio_id}")
            try:
                bucket_name, blob_name = parse_gcs_path(audio_gcs_path)
                signed_url = generate_signed_url(blob_name, expiration_minutes=15)

                return {
                    "success": True,
                    "download_url": signed_url,
                    "format": target_format,
                    "quality": "original",
                    "original_format": source_format,
                    "file_size": metadata.get("file_size_bytes"),
                    "filename": _generate_download_filename(metadata, target_format),
                    "expires_in": 15 * 60,  # 15 minutes
                }
            except Exception as e:
                logger.warning(f"Short-circuit failed, falling back to conversion: {e}")

        # Perform conversion with metadata embedding
        logger.info(f"Converting {audio_id} from {source_format} to {target_format} (preset: {preset})")

        # Create temp directory
        temp_dir = tempfile.mkdtemp(prefix="mcp_download_", dir=get_safe_temp_dir())
        logger.debug(f"Created temp directory for download tool: {temp_dir}")
        source_path = None
        output_path = None
        artwork_path = None

        try:
            # Parse GCS path and download source
            bucket_name, blob_name = parse_gcs_path(audio_gcs_path)
            source_filename = f"source_{audio_id}{Path(audio_gcs_path).suffix}"
            source_path = Path(temp_dir) / source_filename

            logger.debug(f"Downloading source from GCS: {blob_name}")
            download_audio_file(
                blob_name=blob_name,
                destination_path=source_path,
                timeout=120,
            )

            # Prepare output path
            output_ext = get_file_extension(target_format)
            output_filename = f"converted_{audio_id}{output_ext}"
            output_path = Path(temp_dir) / output_filename

            # Prepare metadata for embedding
            metadata_for_embedding = {
                'title': metadata.get('title'),
                'artist': metadata.get('artist'),
                'album': metadata.get('album'),
                'album_artist': metadata.get('album_artist'),
                'genre': metadata.get('genre'),
                'year': metadata.get('year'),
                'track_number': metadata.get('track_number'),
                'composer': metadata.get('composer'),
                'publisher': metadata.get('publisher'),
                'isrc': metadata.get('isrc'),
            }
            # Filter out None values
            metadata_for_embedding = {k: v for k, v in metadata_for_embedding.items() if v is not None}

            # Prepare artwork if available and format supports it
            artwork_gcs_path = metadata.get('thumbnail_gcs_path') or metadata.get('artwork_gcs_path')
            if artwork_gcs_path and get_supported_artwork_formats(target_format):
                try:
                    artwork_filename = f"artwork_{audio_id}{Path(artwork_gcs_path).suffix}"
                    artwork_path = Path(temp_dir) / artwork_filename

                    logger.debug(f"Downloading artwork from GCS: {artwork_gcs_path}")
                    artwork_bucket, artwork_blob = parse_gcs_path(artwork_gcs_path)
                    download_audio_file(
                        blob_name=artwork_blob,
                        destination_path=artwork_path,
                        timeout=60,
                    )
                    logger.debug(f"Downloaded artwork to: {artwork_path}")
                except Exception as e:
                    logger.warning(f"Failed to download artwork {artwork_gcs_path}: {e}")
                    artwork_path = None

            # Convert audio
            conversion_result = convert_audio(
                source_path=source_path,
                output_path=output_path,
                target_format=target_format,
                preset_name=preset,
                timeout_seconds=300,
                metadata=metadata_for_embedding if metadata_for_embedding else None,
                artwork_path=artwork_path,
            )

            if not conversion_result.success:
                raise ConversionError(conversion_result.error_message or "Conversion failed")

            # Upload converted file to GCS temp location
            temp_blob_name = f"temp/downloads/{audio_id}_{int(time.time())}_{target_format}{output_ext}"

            # Import here to avoid circular imports
            from src.storage import upload_audio_file
            upload_audio_file(
                source_path=output_path,
                destination_blob_name=temp_blob_name,
                metadata={"content-type": get_mime_type(target_format)},
            )

            # Generate signed URL for the converted file
            signed_url = generate_signed_url(temp_blob_name, expiration_minutes=15)

            # Generate quality description
            from src.converter.presets import get_preset_config
            preset_config = get_preset_config(target_format, preset)
            quality_desc = preset_config.estimated_bitrate
            if quality_desc:
                quality_desc = f"{quality_desc}kbps"
            elif preset_config.sample_rate:
                quality_desc = f"{preset_config.sample_rate}Hz"
            else:
                quality_desc = preset

            # Return successful response
            result = {
                "success": True,
                "audio_id": audio_id,
                "download_url": signed_url,
                "format": target_format,
                "quality": quality_desc,
                "original_format": source_format,
                "file_size": conversion_result.output_size_bytes,
                "filename": _generate_download_filename(metadata, target_format),
                "expires_in": 15 * 60,  # 15 minutes
            }

            logger.info(f"Download prepared: {result['filename']} ({result['file_size']} bytes)")
            return result

        finally:
            # Cleanup temp files synchronously
            # Note: This blocks response until cleanup completes
            # For production, consider async cleanup or background tasks
            try:
                if source_path and source_path.exists():
                    source_path.unlink()
                    logger.debug(f"Cleaned up source file: {source_path}")
                if output_path and output_path.exists():
                    output_path.unlink()
                    logger.debug(f"Cleaned up output file: {output_path}")
                if artwork_path and artwork_path.exists():
                    artwork_path.unlink()
                    logger.debug(f"Cleaned up artwork file: {artwork_path}")
                if temp_dir and Path(temp_dir).exists():
                    Path(temp_dir).rmdir()
                    logger.debug(f"Cleaned up temp directory: {temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp files: {e}")

    except ValidationError as e:
        logger.warning(f"Validation error in download_audio: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_code": "VALIDATION_ERROR"
        }
    except ResourceNotFoundError as e:
        logger.warning(f"Resource not found in download_audio: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_code": "TRACK_NOT_FOUND"
        }
    except ConversionTimeoutError as e:
        logger.error(f"Conversion timeout in download_audio: {e}")
        return {
            "success": False,
            "error": "Conversion timed out",
            "error_code": "CONVERSION_TIMEOUT"
        }
    except ConversionError as e:
        logger.error(f"Conversion error in download_audio: {e}")
        return {
            "success": False,
            "error": f"Conversion failed: {str(e)}",
            "error_code": "CONVERSION_FAILED"
        }
    except Exception as e:
        error_response = handle_tool_error(e, "download_audio")
        logger.error(f"Unexpected error in download_audio: {error_response}")
        return error_response


def _normalize_format(extension: str) -> str:
    """
    Normalize file extension to standard format name.

    Args:
        extension: File extension (without dot)

    Returns:
        Normalized format name
    """
    extension = extension.lower()
    format_map = {
        "mp3": "mp3",
        "wav": "wav",
        "wave": "wav",
        "flac": "flac",
        "m4a": "aac",
        "aac": "aac",
        "ogg": "ogg",
        "oga": "ogg",
        "opus": "ogg",
    }
    return format_map.get(extension, extension)


def _sanitize_filename_component(component: str, max_length: int = 100) -> Optional[str]:
    """
    Sanitize a filename component by removing unsafe characters and limiting length.

    Args:
        component: The filename component to sanitize
        max_length: Maximum allowed length (default 100)

    Returns:
        Sanitized component string, or None if empty/invalid
    """
    if not component:
        return None

    # Convert to string and strip whitespace
    component = str(component).strip()

    if not component:
        return None

    # Replace unsafe characters with underscores
    unsafe_chars = '<>:"/\\|?*'
    for char in unsafe_chars:
        component = component.replace(char, '_')

    # Limit length
    if len(component) > max_length:
        component = component[:max_length].rstrip()

    # Final check - if empty after processing, return None
    return component if component else None


def _generate_download_filename(metadata: Dict[str, Any], target_format: str) -> str:
    """
    Generate a safe filename for download from track metadata.

    Priority order:
    1. original_filename (if stored during ingestion) - stem + target extension
    2. title/artist metadata (fallback)

    Args:
        metadata: Track metadata dictionary
        target_format: Target format for extension

    Returns:
        Safe filename string
    """
    if metadata is None:
        logger.error("Metadata is None in _generate_download_filename")
        return "Unknown_Unknown_Artist.unknown"

    # Determine target extension
    ext = target_format if target_format != 'aac' else 'm4a'

    # Priority 1: Original filename (if available)
    original_filename = metadata.get('original_filename')
    if original_filename:
        logger.debug(f"Using original_filename for download: {original_filename}")
        try:
            from pathlib import Path
            # Extract stem (filename without extension) and sanitize
            stem = Path(original_filename).stem
            sanitized_stem = _sanitize_filename_component(stem)
            if sanitized_stem:
                filename = f"{sanitized_stem}.{ext}"
                logger.debug(f"Generated filename from original: {filename}")
                return filename
            else:
                logger.debug("Original filename stem was empty after sanitization, falling back to metadata")
        except Exception as e:
            logger.warning(f"Error processing original_filename '{original_filename}': {e}, falling back to metadata")

    # Priority 2: Fallback to title/artist metadata
    logger.debug(f"Filename generation metadata keys: {list(metadata.keys())}")
    logger.debug(f"Raw title: {repr(metadata.get('title'))}, artist: {repr(metadata.get('artist'))}")
    title = _sanitize_filename_component(metadata.get('title')) or 'Unknown'
    artist = _sanitize_filename_component(metadata.get('artist'), max_length=50) or 'Unknown Artist'
    logger.debug(f"Processed title: {repr(title)}, artist: {repr(artist)}")

    # Combine and add extension
    filename = f"{title} - {artist}.{ext}"
    logger.debug(f"Generated fallback filename: {filename}")
    return filename
