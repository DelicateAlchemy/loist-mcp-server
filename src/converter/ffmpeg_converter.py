"""
FFmpeg-based audio format converter.

Provides audio format conversion using FFmpeg subprocess calls,
following the same pattern established in the waveform generator.

Features:
- Multiple output format support (MP3, WAV, FLAC, AAC, OGG)
- Quality presets per format
- Timeout handling for long conversions
- Comprehensive error handling
- Temp file management
"""

import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any

from .presets import (
    get_preset_config,
    get_file_extension,
    validate_format,
    validate_preset,
    PresetConfig,
)
from .metadata_mapper import (
    map_metadata_to_ffmpeg_args,
)

logger = logging.getLogger(__name__)


class ConversionError(Exception):
    """Base exception for audio conversion errors."""
    pass


class ConversionTimeoutError(ConversionError):
    """Exception raised when FFmpeg conversion times out."""
    pass


@dataclass
class ConversionResult:
    """Result of an audio conversion operation."""
    success: bool
    output_path: Path
    source_path: Path
    target_format: str
    preset_name: str
    processing_time_seconds: float
    output_size_bytes: int
    error_message: Optional[str] = None


def convert_audio(
    source_path: Path,
    output_path: Path,
    target_format: str,
    preset_name: Optional[str] = None,
    timeout_seconds: int = 300,
    overwrite: bool = True,
    metadata: Optional[Dict[str, Any]] = None,
    artwork_path: Optional[Path] = None,
) -> ConversionResult:
    """
    Convert audio file to target format using FFmpeg.

    Uses subprocess to call FFmpeg with appropriate codec and quality
    settings based on the selected preset. Supports metadata embedding
    and artwork embedding for supported formats.

    Args:
        source_path: Path to source audio file
        output_path: Path for converted output file
        target_format: Target format (mp3, wav, flac, aac, ogg)
        preset_name: Quality preset (optional, uses format default)
        timeout_seconds: Maximum time for conversion (default: 300s / 5 min)
        overwrite: Whether to overwrite existing output file
        metadata: Optional dictionary of metadata to embed (title, artist, album, etc.)
        artwork_path: Optional path to artwork image file for embedding

    Returns:
        ConversionResult with success status and details

    Raises:
        ConversionError: If conversion fails
        ConversionTimeoutError: If conversion exceeds timeout
        ValueError: If format or preset is invalid
        FileNotFoundError: If source file doesn't exist

    Example:
        >>> result = convert_audio(
        ...     source_path=Path("/tmp/audio.wav"),
        ...     output_path=Path("/tmp/audio.mp3"),
        ...     target_format="mp3",
        ...     preset_name="high",
        ...     metadata={"title": "Song Title", "artist": "Artist Name"},
        ...     artwork_path=Path("/tmp/cover.jpg")
        ... )
        >>> print(f"Converted in {result.processing_time_seconds}s")
    """
    start_time = time.time()
    
    # Validate source file
    source_path = Path(source_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")
    
    # Validate format
    target_format_lower = target_format.lower()
    if not validate_format(target_format_lower):
        raise ValueError(f"Unsupported format: {target_format}")
    
    # Get preset configuration
    try:
        preset_config = get_preset_config(target_format_lower, preset_name)
    except ValueError as e:
        raise ValueError(str(e))
    
    # Ensure output path has correct extension
    output_path = Path(output_path)
    expected_ext = get_file_extension(target_format_lower)
    if output_path.suffix.lower() != expected_ext.lower():
        output_path = output_path.with_suffix(expected_ext)
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Build FFmpeg command
    cmd = _build_ffmpeg_command(
        source_path=source_path,
        output_path=output_path,
        preset_config=preset_config,
        overwrite=overwrite,
        target_format=target_format_lower,
        metadata=metadata,
        artwork_path=artwork_path,
    )

    metadata_info = " with metadata" if metadata else ""
    artwork_info = " with artwork" if artwork_path else ""
    logger.info(
        f"Converting {source_path.name} to {target_format_lower} "
        f"(preset: {preset_config.name}){metadata_info}{artwork_info}"
    )
    logger.debug(f"FFmpeg command: {' '.join(cmd)}")
    
    try:
        # Run FFmpeg
        result = subprocess.run(
            cmd,
            capture_output=True,
            check=True,
            timeout=timeout_seconds,
        )
        
        processing_time = time.time() - start_time
        output_size = output_path.stat().st_size if output_path.exists() else 0
        
        logger.info(
            f"Conversion completed in {processing_time:.2f}s, "
            f"output size: {output_size / 1024 / 1024:.2f}MB"
        )
        
        return ConversionResult(
            success=True,
            output_path=output_path,
            source_path=source_path,
            target_format=target_format_lower,
            preset_name=preset_config.name,
            processing_time_seconds=round(processing_time, 2),
            output_size_bytes=output_size,
        )
        
    except subprocess.TimeoutExpired:
        processing_time = time.time() - start_time
        error_msg = f"FFmpeg conversion timed out after {timeout_seconds}s"
        logger.error(error_msg)
        
        # Clean up partial output file
        if output_path.exists():
            try:
                output_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to clean up partial output: {e}")
        
        raise ConversionTimeoutError(error_msg)
        
    except subprocess.CalledProcessError as e:
        processing_time = time.time() - start_time
        stderr = e.stderr.decode() if e.stderr else "Unknown error"
        error_msg = f"FFmpeg conversion failed: {stderr}"
        logger.error(error_msg)
        
        # Clean up partial output file
        if output_path.exists():
            try:
                output_path.unlink()
            except Exception as cleanup_error:
                logger.warning(f"Failed to clean up partial output: {cleanup_error}")
        
        raise ConversionError(error_msg)
        
    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = f"Unexpected error during conversion: {e}"
        logger.exception(error_msg)
        
        # Clean up partial output file
        if output_path.exists():
            try:
                output_path.unlink()
            except Exception as cleanup_error:
                logger.warning(f"Failed to clean up partial output: {cleanup_error}")
        
        raise ConversionError(error_msg)


def _build_ffmpeg_command(
    source_path: Path,
    output_path: Path,
    preset_config: PresetConfig,
    overwrite: bool = True,
    target_format: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    artwork_path: Optional[Path] = None,
) -> list:
    """
    Build FFmpeg command with appropriate arguments.

    Args:
        source_path: Input file path
        output_path: Output file path
        preset_config: Preset configuration with codec settings
        overwrite: Whether to overwrite existing files
        target_format: Target format for metadata/artwork handling
        metadata: Optional metadata dictionary to embed
        artwork_path: Optional artwork file path to embed

    Returns:
        List of command arguments for subprocess
    """
    cmd = ["ffmpeg"]

    # Overwrite flag (before input)
    if overwrite:
        cmd.append("-y")
    else:
        cmd.append("-n")

    # Input file
    cmd.extend(["-i", str(source_path)])

    # Preset-specific encoding arguments
    cmd.extend(preset_config.ffmpeg_args)

    # Add metadata and/or artwork arguments if provided
    if metadata or artwork_path:
        try:
            # Pass empty dict if no metadata but we have artwork
            metadata_to_pass = metadata or {}
            metadata_args = map_metadata_to_ffmpeg_args(metadata_to_pass, target_format, artwork_path)
            cmd.extend(metadata_args)
        except Exception as e:
            logger.warning(f"Failed to map metadata/artwork for FFmpeg command: {e}")
            # Continue without metadata/artwork rather than failing

    # Output file
    cmd.append(str(output_path))

    return cmd


def probe_audio_format(file_path: Path) -> dict:
    """
    Probe audio file to get format information using ffprobe.
    
    Args:
        file_path: Path to audio file
        
    Returns:
        Dictionary with format info (format_name, duration, bit_rate, etc.)
        
    Raises:
        ConversionError: If probing fails
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(file_path),
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            check=True,
            timeout=30,
        )
        
        import json
        data = json.loads(result.stdout.decode())
        
        # Extract relevant info
        format_info = data.get("format", {})
        streams = data.get("streams", [])
        
        # Find audio stream
        audio_stream = None
        for stream in streams:
            if stream.get("codec_type") == "audio":
                audio_stream = stream
                break
        
        return {
            "format_name": format_info.get("format_name"),
            "duration": float(format_info.get("duration", 0)),
            "bit_rate": int(format_info.get("bit_rate", 0)),
            "size": int(format_info.get("size", 0)),
            "codec_name": audio_stream.get("codec_name") if audio_stream else None,
            "sample_rate": int(audio_stream.get("sample_rate", 0)) if audio_stream else 0,
            "channels": audio_stream.get("channels", 0) if audio_stream else 0,
        }
        
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if e.stderr else "Unknown error"
        raise ConversionError(f"Failed to probe audio file: {stderr}")
    except Exception as e:
        raise ConversionError(f"Failed to probe audio file: {e}")


def get_source_format_extension(file_path: Path) -> str:
    """
    Get the source file format based on extension.
    
    Args:
        file_path: Path to audio file
        
    Returns:
        Format name (lowercase, e.g., "mp3", "wav")
    """
    ext = file_path.suffix.lower()
    
    # Map common extensions to format names
    extension_map = {
        ".mp3": "mp3",
        ".wav": "wav",
        ".flac": "flac",
        ".m4a": "aac",
        ".aac": "aac",
        ".ogg": "ogg",
        ".oga": "ogg",
        ".opus": "ogg",
    }
    
    return extension_map.get(ext, ext.lstrip("."))

