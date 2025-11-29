"""
Audio format converter module for Loist Music Library MCP Server.

Provides on-the-fly audio format conversion using FFmpeg with
quality presets for common use cases.

Supported formats:
- MP3 (lossy, 128-320 kbps)
- WAV (lossless, various sample rates)
- FLAC (lossless compressed)
- AAC (lossy, 192-256 kbps)
- OGG Vorbis (lossy VBR)
"""

from .presets import (
    SUPPORTED_FORMATS,
    FORMAT_PRESETS,
    FORMAT_MIME_TYPES,
    FORMAT_EXTENSIONS,
    get_preset_config,
    get_default_preset,
    validate_format,
    validate_preset,
)
from .ffmpeg_converter import (
    convert_audio,
    ConversionError,
    ConversionTimeoutError,
    ConversionResult,
)

__all__ = [
    # Presets
    "SUPPORTED_FORMATS",
    "FORMAT_PRESETS",
    "FORMAT_MIME_TYPES",
    "FORMAT_EXTENSIONS",
    "get_preset_config",
    "get_default_preset",
    "validate_format",
    "validate_preset",
    # Converter
    "convert_audio",
    "ConversionError",
    "ConversionTimeoutError",
    "ConversionResult",
]

