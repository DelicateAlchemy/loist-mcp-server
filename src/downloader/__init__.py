"""
HTTP/HTTPS Audio Downloader for Loist Music Library MCP Server.

This module provides secure audio file downloading from URLs with:
- HTTP/HTTPS protocol support
- URL scheme validation
- SSRF protection
- File size validation
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

from .validators import (
    URLSchemeValidator,
    URLValidationError,
    validate_url,
)

from .ssrf_protection import (
    SSRFProtector,
    SSRFProtectionError,
    validate_ssrf,
    is_private_ip,
)

__all__ = [
    "HTTPDownloader",
    "download_from_url",
    "DownloadError",
    "DownloadTimeoutError",
    "DownloadSizeError",
    "URLSchemeValidator",
    "URLValidationError",
    "validate_url",
    "SSRFProtector",
    "SSRFProtectionError",
    "validate_ssrf",
    "is_private_ip",
]

