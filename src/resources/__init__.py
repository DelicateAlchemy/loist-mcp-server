"""
MCP Resources for Loist Music Library Server.

This module provides MCP resource handlers for accessing:
- Audio streams (with range request support)
- Metadata
- Thumbnails

Follows best practices from research:
- Signed URL caching
- Range request support for seeking
- Proper Content-Type and CORS headers
- Efficient streaming
"""

from .audio_stream import get_audio_stream_resource
from .metadata import get_metadata_resource
from .thumbnail import get_thumbnail_resource
from .cache import SignedURLCache

__all__ = [
    "get_audio_stream_resource",
    "get_metadata_resource",
    "get_thumbnail_resource",
    "SignedURLCache",
]

