"""
URL validation utilities for secure downloading.

Provides comprehensive URL validation including:
- Scheme validation (HTTP/HTTPS only)
- Hostname validation
- Dangerous scheme detection
- URL normalization
"""

import logging
import re
from typing import Tuple
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)


# Allowed URL schemes
ALLOWED_SCHEMES = {"http", "https"}

# Dangerous/blocked URL schemes
BLOCKED_SCHEMES = {
    "file",      # Local file system access
    "ftp",       # FTP protocol
    "ftps",      # Secure FTP
    "gopher",    # Gopher protocol
    "data",      # Data URLs (can be large)
    "javascript",# JavaScript execution
    "vbscript",  # VBScript execution
    "about",     # Browser internal
    "chrome",    # Browser internal
    "jar",       # Java archives
    "ws",        # WebSocket (not for downloads)
    "wss",       # Secure WebSocket
    "ssh",       # SSH protocol
    "telnet",    # Telnet protocol
    "ldap",      # LDAP protocol
    "dict",      # Dictionary protocol
}


class URLValidationError(ValueError):
    """Exception raised when URL validation fails."""
    pass


class URLSchemeValidator:
    """
    Comprehensive URL scheme validator.
    
    Validates URLs to ensure only safe protocols are used for downloads.
    Prevents security issues like local file access and protocol smuggling.
    """
    
    @staticmethod
    def validate_scheme(url: str) -> Tuple[bool, str]:
        """
        Validate URL scheme.
        
        Args:
            url: URL to validate
        
        Returns:
            Tuple of (is_valid, error_message)
        
        Raises:
            URLValidationError: If URL scheme is invalid or dangerous
        """
        if not url or not isinstance(url, str):
            raise URLValidationError("URL must be a non-empty string")
        
        # Parse URL
        try:
            parsed = urlparse(url.strip())
        except Exception as e:
            raise URLValidationError(f"Invalid URL format: {e}")
        
        # Check for scheme
        if not parsed.scheme:
            raise URLValidationError(
                "URL must include a scheme (e.g., https://example.com)"
            )
        
        scheme = parsed.scheme.lower()
        
        # Check for blocked schemes
        if scheme in BLOCKED_SCHEMES:
            raise URLValidationError(
                f"Blocked URL scheme '{scheme}'. This scheme is not allowed for security reasons."
            )
        
        # Check for allowed schemes
        if scheme not in ALLOWED_SCHEMES:
            raise URLValidationError(
                f"Unsupported URL scheme '{scheme}'. Only HTTP and HTTPS are allowed."
            )
        
        # Validate hostname exists
        if not parsed.netloc:
            raise URLValidationError(
                f"Invalid URL: missing hostname. URL must be in format: {scheme}://hostname/path"
            )
        
        logger.debug(f"URL scheme validated: {scheme}://{parsed.netloc}")
        return True, ""
    
    @staticmethod
    def validate_hostname(url: str) -> Tuple[bool, str]:
        """
        Validate hostname format.
        
        Args:
            url: URL to validate
        
        Returns:
            Tuple of (is_valid, error_message)
        
        Raises:
            URLValidationError: If hostname is invalid
        """
        parsed = urlparse(url)
        hostname = parsed.netloc.split(':')[0]  # Remove port if present
        
        if not hostname:
            raise URLValidationError("Hostname is required")
        
        # Check for localhost variations
        localhost_patterns = [
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
            "::1",
            "[::1]",
        ]
        
        if hostname.lower() in localhost_patterns:
            logger.warning(f"Localhost URL detected: {hostname}")
            # Don't block localhost in development, but log it
        
        # Validate hostname format (basic check)
        # Hostname should contain at least one dot (for FQDN) or be localhost
        if "." not in hostname and hostname.lower() not in ["localhost"]:
            raise URLValidationError(
                f"Invalid hostname format: {hostname}. Use fully qualified domain name."
            )
        
        # Check for invalid characters
        if re.search(r'[<>"\s]', hostname):
            raise URLValidationError(
                f"Hostname contains invalid characters: {hostname}"
            )
        
        logger.debug(f"Hostname validated: {hostname}")
        return True, ""
    
    @staticmethod
    def normalize_url(url: str) -> str:
        """
        Normalize URL for consistent processing.
        
        Args:
            url: URL to normalize
        
        Returns:
            Normalized URL
        """
        # Strip whitespace
        url = url.strip()
        
        # Parse and rebuild URL
        parsed = urlparse(url)
        
        # Normalize scheme to lowercase
        scheme = parsed.scheme.lower() if parsed.scheme else ""
        
        # Normalize hostname to lowercase
        netloc = parsed.netloc.lower() if parsed.netloc else ""
        
        # Remove default ports
        if netloc.endswith(":80") and scheme == "http":
            netloc = netloc[:-3]
        elif netloc.endswith(":443") and scheme == "https":
            netloc = netloc[:-4]
        
        # Rebuild URL
        normalized = urlunparse((
            scheme,
            netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment
        ))
        
        return normalized
    
    @staticmethod
    def validate(url: str, normalize: bool = True) -> str:
        """
        Perform complete URL validation.
        
        Args:
            url: URL to validate
            normalize: Whether to normalize URL
        
        Returns:
            Validated (and optionally normalized) URL
        
        Raises:
            URLValidationError: If validation fails
        """
        # Normalize if requested
        if normalize:
            url = URLSchemeValidator.normalize_url(url)
        
        # Validate scheme
        URLSchemeValidator.validate_scheme(url)
        
        # Validate hostname
        URLSchemeValidator.validate_hostname(url)
        
        logger.info(f"URL validated: {url}")
        return url


def validate_url(url: str, normalize: bool = True) -> str:
    """
    Validate URL for downloading.
    
    Convenience function that performs complete URL validation.
    
    Args:
        url: URL to validate
        normalize: Whether to normalize URL
    
    Returns:
        Validated URL
    
    Raises:
        URLValidationError: If validation fails
    
    Example:
        >>> from src.downloader.validators import validate_url
        >>> url = validate_url("https://example.com/audio.mp3")
        >>> print(url)
        https://example.com/audio.mp3
    """
    return URLSchemeValidator.validate(url, normalize=normalize)

