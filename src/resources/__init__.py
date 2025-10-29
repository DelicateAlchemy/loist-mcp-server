"""
MCP Resources for Music Library Server.

This module provides MCP resources for serving audio streams and thumbnails.
Resources are registered with the FastMCP server to enable streaming access
to audio files and artwork.
"""

from .audio_stream import serve_audio_stream, get_audio_stream_info
from .thumbnail import serve_thumbnail, get_thumbnail_info

__all__ = [
    'serve_audio_stream',
    'get_audio_stream_info', 
    'serve_thumbnail',
    'get_thumbnail_info'
]
