"""
Audio format conversion presets for FFmpeg.

Defines quality presets for each supported audio format with
corresponding FFmpeg command-line arguments.

Presets follow industry standards:
- MP3: 320kbps for high quality distribution
- WAV: 48kHz/24-bit for broadcast standards
- FLAC: Level 8 compression for best file size
- AAC: 256kbps for Apple-compatible high quality
- OGG: Quality 8 (~256kbps VBR) for open source high quality
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass


@dataclass(frozen=True)
class PresetConfig:
    """Configuration for a quality preset."""
    name: str
    description: str
    ffmpeg_args: Tuple[str, ...]
    estimated_bitrate: Optional[int] = None  # kbps, None for lossless
    sample_rate: Optional[int] = None  # Hz, None to preserve source
    bit_depth: Optional[int] = None  # bits, for lossless formats


# Supported output formats
SUPPORTED_FORMATS = frozenset(["mp3", "wav", "flac", "aac", "ogg"])

# MIME types for each format
FORMAT_MIME_TYPES: Dict[str, str] = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "flac": "audio/flac",
    "aac": "audio/aac",
    "m4a": "audio/mp4",  # AAC in M4A container
    "ogg": "audio/ogg",
}

# File extensions for each format
FORMAT_EXTENSIONS: Dict[str, str] = {
    "mp3": ".mp3",
    "wav": ".wav",
    "flac": ".flac",
    "aac": ".m4a",  # AAC typically uses M4A container
    "ogg": ".ogg",
}

# Quality presets per format
FORMAT_PRESETS: Dict[str, Dict[str, PresetConfig]] = {
    "mp3": {
        "high": PresetConfig(
            name="high",
            description="Highest quality MP3 (320 kbps CBR)",
            ffmpeg_args=("-vn", "-codec:a", "libmp3lame", "-b:a", "320k"),
            estimated_bitrate=320,
        ),
        "standard": PresetConfig(
            name="standard",
            description="Good quality MP3 (192 kbps CBR)",
            ffmpeg_args=("-vn", "-codec:a", "libmp3lame", "-b:a", "192k"),
            estimated_bitrate=192,
        ),
        "compact": PresetConfig(
            name="compact",
            description="Smaller file size MP3 (128 kbps CBR)",
            ffmpeg_args=("-vn", "-codec:a", "libmp3lame", "-b:a", "128k"),
            estimated_bitrate=128,
        ),
    },
    "wav": {
        "broadcast": PresetConfig(
            name="broadcast",
            description="Broadcast standard (48 kHz, 24-bit)",
            ffmpeg_args=("-vn", "-acodec", "pcm_s24le", "-ar", "48000"),
            sample_rate=48000,
            bit_depth=24,
        ),
        "cd": PresetConfig(
            name="cd",
            description="CD quality (44.1 kHz, 16-bit)",
            ffmpeg_args=("-vn", "-acodec", "pcm_s16le", "-ar", "44100"),
            sample_rate=44100,
            bit_depth=16,
        ),
        "high": PresetConfig(
            name="high",
            description="Studio quality (96 kHz, 24-bit)",
            ffmpeg_args=("-vn", "-acodec", "pcm_s24le", "-ar", "96000"),
            sample_rate=96000,
            bit_depth=24,
        ),
    },
    "flac": {
        "high": PresetConfig(
            name="high",
            description="Best compression (level 8)",
            ffmpeg_args=("-vn", "-codec:a", "flac", "-compression_level", "8"),
        ),
        "fast": PresetConfig(
            name="fast",
            description="Fastest encoding (level 0)",
            ffmpeg_args=("-vn", "-codec:a", "flac", "-compression_level", "0"),
        ),
    },
    "aac": {
        "high": PresetConfig(
            name="high",
            description="High quality AAC (256 kbps)",
            ffmpeg_args=("-vn", "-codec:a", "aac", "-b:a", "256k"),
            estimated_bitrate=256,
        ),
        "standard": PresetConfig(
            name="standard",
            description="Standard quality AAC (192 kbps)",
            ffmpeg_args=("-vn", "-codec:a", "aac", "-b:a", "192k"),
            estimated_bitrate=192,
        ),
    },
    "ogg": {
        "high": PresetConfig(
            name="high",
            description="High quality Vorbis (Q8, ~256 kbps VBR)",
            ffmpeg_args=("-vn", "-codec:a", "libvorbis", "-qscale:a", "8"),
            estimated_bitrate=256,
        ),
        "standard": PresetConfig(
            name="standard",
            description="Standard quality Vorbis (Q5, ~160 kbps VBR)",
            ffmpeg_args=("-vn", "-codec:a", "libvorbis", "-qscale:a", "5"),
            estimated_bitrate=160,
        ),
    },
}

# Default preset per format
DEFAULT_PRESETS: Dict[str, str] = {
    "mp3": "high",
    "wav": "broadcast",
    "flac": "high",
    "aac": "high",
    "ogg": "high",
}


def validate_format(format_name: str) -> bool:
    """
    Check if a format is supported.
    
    Args:
        format_name: Format name to validate (case-insensitive)
        
    Returns:
        True if format is supported
    """
    return format_name.lower() in SUPPORTED_FORMATS


def validate_preset(format_name: str, preset_name: str) -> bool:
    """
    Check if a preset is valid for a given format.
    
    Args:
        format_name: Format name (case-insensitive)
        preset_name: Preset name to validate
        
    Returns:
        True if preset is valid for the format
    """
    format_lower = format_name.lower()
    if format_lower not in FORMAT_PRESETS:
        return False
    return preset_name.lower() in FORMAT_PRESETS[format_lower]


def get_default_preset(format_name: str) -> str:
    """
    Get the default preset name for a format.
    
    Args:
        format_name: Format name (case-insensitive)
        
    Returns:
        Default preset name for the format
        
    Raises:
        ValueError: If format is not supported
    """
    format_lower = format_name.lower()
    if format_lower not in DEFAULT_PRESETS:
        raise ValueError(f"Unsupported format: {format_name}")
    return DEFAULT_PRESETS[format_lower]


def get_preset_config(format_name: str, preset_name: Optional[str] = None) -> PresetConfig:
    """
    Get the preset configuration for a format and preset.
    
    Args:
        format_name: Format name (case-insensitive)
        preset_name: Preset name (optional, uses default if not provided)
        
    Returns:
        PresetConfig for the format/preset combination
        
    Raises:
        ValueError: If format or preset is invalid
    """
    format_lower = format_name.lower()
    
    if format_lower not in FORMAT_PRESETS:
        raise ValueError(f"Unsupported format: {format_name}")
    
    # Use default preset if not specified
    if preset_name is None:
        preset_name = DEFAULT_PRESETS[format_lower]
    
    preset_lower = preset_name.lower()
    
    if preset_lower not in FORMAT_PRESETS[format_lower]:
        valid_presets = list(FORMAT_PRESETS[format_lower].keys())
        raise ValueError(
            f"Invalid preset '{preset_name}' for format '{format_name}'. "
            f"Valid presets: {valid_presets}"
        )
    
    return FORMAT_PRESETS[format_lower][preset_lower]


def get_available_presets(format_name: str) -> List[str]:
    """
    Get list of available presets for a format.
    
    Args:
        format_name: Format name (case-insensitive)
        
    Returns:
        List of preset names
        
    Raises:
        ValueError: If format is not supported
    """
    format_lower = format_name.lower()
    
    if format_lower not in FORMAT_PRESETS:
        raise ValueError(f"Unsupported format: {format_name}")
    
    return list(FORMAT_PRESETS[format_lower].keys())


def get_mime_type(format_name: str) -> str:
    """
    Get MIME type for a format.
    
    Args:
        format_name: Format name (case-insensitive)
        
    Returns:
        MIME type string
        
    Raises:
        ValueError: If format is not supported
    """
    format_lower = format_name.lower()
    
    if format_lower not in FORMAT_MIME_TYPES:
        raise ValueError(f"Unsupported format: {format_name}")
    
    return FORMAT_MIME_TYPES[format_lower]


def get_file_extension(format_name: str) -> str:
    """
    Get file extension for a format (including leading dot).
    
    Args:
        format_name: Format name (case-insensitive)
        
    Returns:
        File extension (e.g., ".mp3")
        
    Raises:
        ValueError: If format is not supported
    """
    format_lower = format_name.lower()
    
    if format_lower not in FORMAT_EXTENSIONS:
        raise ValueError(f"Unsupported format: {format_name}")
    
    return FORMAT_EXTENSIONS[format_lower]

