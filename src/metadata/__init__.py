"""
Audio metadata extraction for Loist Music Library MCP Server.

This module provides extraction of:
- ID3 tags (artist, title, album, genre, year)
- BWF (Broadcast Wave Format) metadata from professional WAV files
- XMP metadata from WAV files with embedded XMP
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
from .xmp_extractor import (
    XMPExtractor,
    XMPExtractionError,
    extract_xmp_metadata,
    enhance_metadata_with_xmp,
    is_xmp_available,
    should_attempt_xmp_extraction,
)
from .bwf_extractor import (
    BWFExtractor,
    BWFExtractionError,
    extract_bwf_metadata,
    enhance_metadata_with_bwf,
    is_bwf_available,
    should_attempt_bwf_extraction,
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
    "XMPExtractor",
    "XMPExtractionError",
    "extract_xmp_metadata",
    "enhance_metadata_with_xmp",
    "is_xmp_available",
    "should_attempt_xmp_extraction",
    "BWFExtractor",
    "BWFExtractionError",
    "extract_bwf_metadata",
    "enhance_metadata_with_bwf",
    "is_bwf_available",
    "should_attempt_bwf_extraction",
]

