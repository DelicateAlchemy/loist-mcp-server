"""
HTTP/HTTPS Audio Downloader for Loist Music Library MCP Server.

This module provides secure audio file downloading from URLs with:
- HTTP/HTTPS protocol support
- File size validation
- SSRF protection
- Timeout and retry logic
- Progress tracking
"""

from .http_downloader import (
    HTTPDownloader,
    download_from_url,
    DownloadError,
    DownloadTimeoutError,
    DownloadSizeError,
)

__all__ = [
    "HTTPDownloader",
    "download_from_url",
    "DownloadError",
    "DownloadTimeoutError",
    "DownloadSizeError",
]

