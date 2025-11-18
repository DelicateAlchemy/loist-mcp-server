"""
Audio metadata extraction for Loist Music Library MCP Server.

This module provides extraction of:
- ID3 tags (artist, title, album, genre, year)
- Technical specifications (duration, channels, sample rate, bitrate)
- Embedded artwork/album covers
- Format validation and detection
"""

from .extractor import (
    MetadataExtractor,
    MetadataQualityAssessment,
    extract_metadata,
    extract_metadata_with_fallback,
    extract_id3_tags,
    extract_artwork,
    assess_metadata_quality,
    parse_filename_metadata,
    MetadataExtractionError,
    MetadataQualityError,
)

from .format_validator import (
    FormatValidator,
    FormatValidationError,
    validate_audio_format,
)

__all__ = [
    "MetadataExtractor",
    "MetadataQualityAssessment",
    "extract_metadata",
    "extract_metadata_with_fallback",
    "extract_id3_tags",
    "extract_artwork",
    "assess_metadata_quality",
    "parse_filename_metadata",
    "MetadataExtractionError",
    "MetadataQualityError",
    "FormatValidator",
    "FormatValidationError",
    "validate_audio_format",
]

