"""
Metadata mapping utilities for FFmpeg audio conversion.

Provides functions to map database metadata fields to FFmpeg -metadata arguments
with proper format-specific handling and UTF-8 encoding.
"""

import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


def map_metadata_to_ffmpeg_args(
    metadata: Dict[str, Any],
    target_format: str,
    artwork_path: Optional[Path] = None
) -> List[str]:
    """
    Map database metadata to FFmpeg -metadata arguments.

    Handles format-specific metadata requirements:
    - MP3: ID3v2.3 + ID3v1 tags
    - WAV: RIFF INFO + BWF bext chunks
    - FLAC/OGG: Vorbis comments
    - AAC/M4A: iTunes atoms

    Args:
        metadata: Dictionary of track metadata from database
        target_format: Target format (mp3, wav, flac, aac, ogg)
        artwork_path: Optional path to artwork file for embedding

    Returns:
        List of FFmpeg arguments (e.g., ['-metadata', 'title=Song Title', ...])

    Raises:
        ValueError: If required metadata is missing or format is invalid
    """
    # Metadata is required unless we only have artwork
    if not metadata and not artwork_path:
        raise ValueError("Metadata dictionary or artwork path is required")

    # Title is required only if we have metadata
    if metadata and not metadata.get('title'):
        raise ValueError("Title is required for metadata embedding")

    target_format = target_format.lower()
    args = []

    # Map standard metadata fields to FFmpeg keys (only if metadata provided)
    metadata_mappings = {}
    if metadata:
        metadata_mappings = {
            'title': metadata.get('title', ''),
            'artist': metadata.get('artist', ''),
            'album': metadata.get('album', ''),
            'genre': metadata.get('genre', ''),
            'date': str(metadata.get('year', '')) if metadata.get('year') else '',
            'composer': metadata.get('composer', ''),
            'publisher': metadata.get('publisher', ''),
            'ISRC': metadata.get('isrc', ''),
        }

        # Format track number (handle track/total format)
        track_number = metadata.get('track_number')
        if track_number:
            # If we have total tracks, format as "track/total", otherwise just "track"
            total_tracks = metadata.get('total_tracks')
            if total_tracks and total_tracks > 0:
                metadata_mappings['track'] = f"{track_number}/{total_tracks}"
            else:
                metadata_mappings['track'] = str(track_number)

        # Format-specific metadata handling
        if target_format == 'mp3':
            # MP3: Add album_artist for ID3 tags
            album_artist = metadata.get('album_artist')
            if album_artist:
                metadata_mappings['album_artist'] = album_artist

    # Add metadata arguments, filtering out empty values
    for key, value in metadata_mappings.items():
        if value:  # Only add non-empty metadata
            # Ensure UTF-8 encoding and escape special characters
            safe_value = _escape_metadata_value(str(value))
            args.extend(['-metadata', f'{key}={safe_value}'])

    # Add artwork embedding if supported and artwork exists
    if artwork_path and artwork_path.exists():
        artwork_args = _get_artwork_ffmpeg_args(target_format, artwork_path)
        args.extend(artwork_args)

    # Format-specific flags
    format_flags = _get_format_specific_flags(target_format)
    args.extend(format_flags)

    return args


def _escape_metadata_value(value: str) -> str:
    """
    Escape special characters in metadata values for FFmpeg.

    FFmpeg expects UTF-8 encoded strings. We need to ensure:
    - Proper UTF-8 encoding
    - Escape quotes and special characters that might break FFmpeg parsing

    Args:
        value: Raw metadata value

    Returns:
        Escaped and UTF-8 safe value
    """
    if not value:
        return value

    # FFmpeg handles UTF-8 well, but we need to be careful with quotes and backslashes
    # Replace backslashes first, then quotes
    escaped = value.replace('\\', '\\\\')  # Escape backslashes
    escaped = escaped.replace('"', '\\"')  # Escape quotes
    escaped = escaped.replace("'", "\\'")  # Escape single quotes

    # Ensure UTF-8 encoding (FFmpeg expects UTF-8)
    try:
        # Validate UTF-8 encoding
        escaped.encode('utf-8')
        return escaped
    except UnicodeEncodeError:
        # Fallback: replace problematic characters
        logger.warning(f"UTF-8 encoding issue with metadata value, sanitizing: {value}")
        return escaped.encode('utf-8', errors='replace').decode('utf-8')


def _get_artwork_ffmpeg_args(target_format: str, artwork_path: Path) -> List[str]:
    """
    Get FFmpeg arguments for embedding artwork.

    Args:
        target_format: Target audio format
        artwork_path: Path to artwork image file

    Returns:
        List of FFmpeg arguments for artwork embedding
    """
    args = []

    # Add artwork input
    args.extend(['-i', str(artwork_path)])

    # Format-specific artwork handling
    if target_format == 'mp3':
        # MP3: Map video stream as attached picture
        args.extend([
            '-map', '0:a',  # Audio from first input
            '-map', '1:v',  # Video from second input (artwork)
            '-codec:v', 'mjpeg',  # Encode artwork as JPEG
            '-metadata:s:v', 'title=Cover',
            '-metadata:s:v', 'comment=Cover (front)',
        ])
    elif target_format in ['aac', 'm4a']:
        # AAC/M4A: iTunes-style cover art
        args.extend([
            '-map', '0:a',  # Audio from first input
            '-map', '1:v',  # Video from second input (artwork)
            '-codec:v', 'mjpeg',  # Encode artwork as JPEG
            '-disposition:v', 'attached_pic',  # Mark as attached picture
        ])
    elif target_format == 'flac':
        # FLAC: PICTURE block
        args.extend([
            '-map', '0:a',  # Audio from first input
            '-map', '1:v',  # Video from second input (artwork)
            '-codec:v', 'mjpeg',  # Encode artwork as JPEG
            '-disposition:v', 'attached_pic',  # Mark as attached picture
        ])
    elif target_format == 'ogg':
        # OGG: METADATA_BLOCK_PICTURE (player support varies)
        args.extend([
            '-map', '0:a',  # Audio from first input
            '-map', '1:v',  # Video from second input (artwork)
            '-codec:v', 'mjpeg',  # Encode artwork as JPEG
            '-disposition:v', 'attached_pic',  # Mark as attached picture
        ])
    else:
        # WAV doesn't support embedded artwork, skip it
        logger.info(f"Artwork embedding not supported for format: {target_format}")
        return []

    return args


def _get_format_specific_flags(target_format: str) -> List[str]:
    """
    Get format-specific FFmpeg flags for proper metadata handling.

    Args:
        target_format: Target audio format

    Returns:
        List of FFmpeg flags
    """
    flags = []

    if target_format == 'mp3':
        # MP3: Force ID3v2.3 for better compatibility, also write ID3v1
        flags.extend(['-id3v2_version', '3', '-write_id3v1', '1'])
    elif target_format == 'wav':
        # WAV: Enable BWF bext chunk writing for professional audio
        flags.extend(['-write_bext', '1'])
    elif target_format in ['aac', 'm4a']:
        # AAC: Use iPod/MP4 container format
        flags.extend(['-f', 'ipod'])
    # FLAC and OGG use default metadata handling

    return flags


def get_supported_artwork_formats(target_format: str) -> bool:
    """
    Check if a format supports artwork embedding.

    Args:
        target_format: Audio format to check

    Returns:
        True if format supports embedded artwork
    """
    return target_format.lower() in ['mp3', 'aac', 'm4a', 'flac', 'ogg']


def validate_metadata_for_format(metadata: Dict[str, Any], target_format: str) -> List[str]:
    """
    Validate metadata for a specific format and return warnings.

    Args:
        metadata: Metadata dictionary
        target_format: Target format

    Returns:
        List of warning messages (empty if no issues)
    """
    warnings = []

    # Check required fields
    if not metadata.get('title'):
        warnings.append("Missing title - this is required")

    # Format-specific validations
    target_format = target_format.lower()

    if target_format == 'mp3':
        # MP3 specific checks
        if not metadata.get('artist') and not metadata.get('album_artist'):
            warnings.append("MP3: Consider adding artist or album_artist for better compatibility")

    elif target_format == 'wav':
        # WAV specific checks
        if not metadata.get('artist'):
            warnings.append("WAV: Artist recommended for RIFF INFO chunk")

    return warnings
