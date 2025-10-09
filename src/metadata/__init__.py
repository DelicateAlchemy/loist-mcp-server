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
    extract_metadata,
    extract_id3_tags,
    MetadataExtractionError,
)

__all__ = [
    "MetadataExtractor",
    "extract_metadata",
    "extract_id3_tags",
    "MetadataExtractionError",
]

