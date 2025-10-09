"""
HTTP/HTTPS downloader implementation with security and error handling.

Provides secure downloading of audio files from URLs with:
- Protocol validation (HTTP/HTTPS only)
- File size limits
- Streaming downloads for large files
- Timeout handling
- Redirect support
- Custom headers
"""

import logging
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .validators import URLSchemeValidator, URLValidationError

logger = logging.getLogger(__name__)


class DownloadError(Exception):
    """Base exception for download errors."""
    pass


class DownloadTimeoutError(DownloadError):
    """Exception raised when download times out."""
    pass


class DownloadSizeError(DownloadError):
    """Exception raised when file size exceeds limit."""
    pass


class HTTPDownloader:
    """
    HTTP/HTTPS file downloader with security and validation.
    
    Features:
    - HTTP/HTTPS protocol support
    - Streaming downloads for large files
    - File size validation
    - Timeout handling
    - Redirect support
    - Custom headers
    - Progress tracking
    """
    
    def __init__(
        self,
        max_size_mb: int = 100,
        timeout_seconds: int = 60,
        chunk_size: int = 8192,
        max_retries: int = 3,
        follow_redirects: bool = True,
        user_agent: Optional[str] = None,
    ):
        """
        Initialize HTTP downloader.
        
        Args:
            max_size_mb: Maximum file size in megabytes
            timeout_seconds: Download timeout in seconds
            chunk_size: Download chunk size in bytes
            max_retries: Maximum retry attempts for failed downloads
            follow_redirects: Whether to follow HTTP redirects
            user_agent: Custom User-Agent header
        """
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.timeout_seconds = timeout_seconds
        self.chunk_size = chunk_size
        self.max_retries = max_retries
        self.follow_redirects = follow_redirects
        self.user_agent = user_agent or "Loist-MCP-Server/0.1.0"
        
        # Create session with retry logic
        self.session = self._create_session()
        
        logger.info(
            f"Initialized HTTP downloader: max_size={max_size_mb}MB, "
            f"timeout={timeout_seconds}s, retries={max_retries}"
        )
    
    def _create_session(self) -> requests.Session:
        """
        Create requests session with retry configuration.
        
        Returns:
            Configured requests.Session
        """
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,  # 1s, 2s, 4s backoff
            status_forcelist=[429, 500, 502, 503, 504],  # Retry on these status codes
            allowed_methods=["HEAD", "GET"],
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set default headers
        session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "audio/*,*/*",
        })
        
        return session
    
    def validate_url_scheme(self, url: str) -> str:
        """
        Validate that URL uses allowed scheme (HTTP/HTTPS).
        
        Args:
            url: URL to validate
        
        Returns:
            Validated (and normalized) URL
        
        Raises:
            URLValidationError: If URL scheme is not allowed
        """
        # Use comprehensive validator
        return URLSchemeValidator.validate(url, normalize=True)
    
    def check_file_size(self, url: str, headers: Optional[Dict[str, str]] = None) -> int:
        """
        Check file size using HEAD request.
        
        Args:
            url: URL to check
            headers: Optional custom headers
        
        Returns:
            File size in bytes (0 if unknown)
        
        Raises:
            DownloadSizeError: If file size exceeds limit
            DownloadError: If HEAD request fails
        """
        try:
            response = self.session.head(
                url,
                headers=headers,
                timeout=10,
                allow_redirects=self.follow_redirects
            )
            response.raise_for_status()
            
            content_length = response.headers.get("Content-Length")
            
            if not content_length:
                logger.warning(f"Content-Length header not present for {url}")
                return 0
            
            file_size = int(content_length)
            
            if file_size > self.max_size_bytes:
                raise DownloadSizeError(
                    f"File size ({file_size / 1024 / 1024:.2f}MB) exceeds "
                    f"maximum allowed size ({self.max_size_bytes / 1024 / 1024}MB)"
                )
            
            logger.info(f"File size check passed: {file_size / 1024 / 1024:.2f}MB")
            return file_size
            
        except requests.RequestException as e:
            raise DownloadError(f"Failed to check file size: {e}")
    
    def download(
        self,
        url: str,
        destination: Optional[Path | str] = None,
        headers: Optional[Dict[str, str]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Path:
        """
        Download file from URL.
        
        Args:
            url: URL to download from
            destination: Destination path (uses temp file if None)
            headers: Optional custom headers
            progress_callback: Optional callback(bytes_downloaded, total_bytes)
        
        Returns:
            Path to downloaded file
        
        Raises:
            ValueError: If URL is invalid
            DownloadSizeError: If file size exceeds limit
            DownloadTimeoutError: If download times out
            DownloadError: If download fails
        """
        # Validate and normalize URL
        url = self.validate_url_scheme(url)
        
        # Check file size
        try:
            total_size = self.check_file_size(url, headers)
        except DownloadError as e:
            logger.warning(f"Could not check file size: {e}")
            total_size = 0
        
        # Create destination path
        if destination:
            dest_path = Path(destination)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            # Use temporary file
            temp_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=self._get_file_extension(url)
            )
            dest_path = Path(temp_file.name)
            temp_file.close()
        
        logger.info(f"Downloading from {url} to {dest_path}")
        
        try:
            # Download file with streaming
            with self.session.get(
                url,
                headers=headers,
                stream=True,
                timeout=self.timeout_seconds,
                allow_redirects=self.follow_redirects
            ) as response:
                response.raise_for_status()
                
                # Double-check content length if not checked before
                if total_size == 0:
                    content_length = response.headers.get("Content-Length")
                    if content_length:
                        total_size = int(content_length)
                        if total_size > self.max_size_bytes:
                            raise DownloadSizeError(
                                f"File size ({total_size / 1024 / 1024:.2f}MB) exceeds "
                                f"maximum allowed size ({self.max_size_bytes / 1024 / 1024}MB)"
                            )
                
                # Download in chunks
                bytes_downloaded = 0
                with open(dest_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=self.chunk_size):
                        if chunk:  # Filter out keep-alive chunks
                            f.write(chunk)
                            bytes_downloaded += len(chunk)
                            
                            # Check size during download
                            if bytes_downloaded > self.max_size_bytes:
                                dest_path.unlink()  # Delete partial file
                                raise DownloadSizeError(
                                    f"Downloaded size exceeds limit during download"
                                )
                            
                            # Progress callback
                            if progress_callback:
                                progress_callback(bytes_downloaded, total_size)
                
                logger.info(
                    f"Download complete: {bytes_downloaded / 1024 / 1024:.2f}MB saved to {dest_path}"
                )
                return dest_path
                
        except requests.Timeout as e:
            # Clean up partial file
            if dest_path.exists():
                dest_path.unlink()
            raise DownloadTimeoutError(f"Download timed out after {self.timeout_seconds}s: {e}")
            
        except requests.RequestException as e:
            # Clean up partial file
            if dest_path.exists():
                dest_path.unlink()
            raise DownloadError(f"Download failed: {e}")
            
        except Exception as e:
            # Clean up partial file on any error
            if dest_path.exists():
                dest_path.unlink()
            raise DownloadError(f"Unexpected error during download: {e}")
    
    def _get_file_extension(self, url: str) -> str:
        """
        Extract file extension from URL.
        
        Args:
            url: URL to extract extension from
        
        Returns:
            File extension (e.g., ".mp3") or empty string
        """
        parsed = urlparse(url)
        path = Path(parsed.path)
        
        # Get extension, default to empty string
        ext = path.suffix
        
        # Common audio extensions
        if ext.lower() in [".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma"]:
            return ext
        
        # Default to .bin for unknown
        return ".bin"
    
    def close(self) -> None:
        """Close the HTTP session."""
        if self.session:
            self.session.close()
            logger.debug("HTTP session closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False


# Convenience function for simple downloads
def download_from_url(
    url: str,
    destination: Optional[Path | str] = None,
    max_size_mb: int = 100,
    timeout_seconds: int = 60,
    headers: Optional[Dict[str, str]] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> Path:
    """
    Download a file from a URL.
    
    Convenience function that creates a downloader and downloads a single file.
    
    Args:
        url: URL to download from
        destination: Destination path (temp file if None)
        max_size_mb: Maximum file size in MB
        timeout_seconds: Download timeout in seconds
        headers: Optional custom headers
        progress_callback: Optional progress callback function
    
    Returns:
        Path to downloaded file
    
    Raises:
        ValueError: If URL is invalid
        DownloadSizeError: If file size exceeds limit
        DownloadTimeoutError: If download times out
        DownloadError: If download fails
    
    Example:
        >>> from src.downloader import download_from_url
        >>> file_path = download_from_url(
        ...     "https://example.com/audio.mp3",
        ...     max_size_mb=50
        ... )
        >>> print(f"Downloaded to: {file_path}")
    """
    with HTTPDownloader(
        max_size_mb=max_size_mb,
        timeout_seconds=timeout_seconds
    ) as downloader:
        return downloader.download(
            url=url,
            destination=destination,
            headers=headers,
            progress_callback=progress_callback
        )

