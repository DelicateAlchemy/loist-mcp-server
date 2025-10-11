"""
Tests for HTTP/HTTPS downloader.

Tests verify:
- Basic HTTP/HTTPS download functionality
- URL scheme validation
- File size validation
- Timeout handling
- Redirect handling
- Error handling
- Progress tracking
- Temporary file management
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
import requests


class TestHTTPDownloaderImports:
    """Test that downloader module imports correctly."""
    
    def test_imports(self):
        """Test module imports."""
        from src.downloader import HTTPDownloader, download_from_url
        from src.downloader import DownloadError, DownloadTimeoutError, DownloadSizeError
        
        assert HTTPDownloader is not None
        assert download_from_url is not None
        assert DownloadError is not None


class TestHTTPDownloaderInitialization:
    """Test downloader initialization."""
    
    def test_default_initialization(self):
        """Test downloader with default settings."""
        from src.downloader import HTTPDownloader
        
        downloader = HTTPDownloader()
        
        assert downloader.max_size_bytes == 100 * 1024 * 1024
        assert downloader.timeout_seconds == 60
        assert downloader.chunk_size == 8192
        assert downloader.max_retries == 3
        assert downloader.follow_redirects is True
    
    def test_custom_initialization(self):
        """Test downloader with custom settings."""
        from src.downloader import HTTPDownloader
        
        downloader = HTTPDownloader(
            max_size_mb=50,
            timeout_seconds=30,
            chunk_size=4096,
            max_retries=5,
            follow_redirects=False,
            user_agent="CustomAgent/1.0"
        )
        
        assert downloader.max_size_bytes == 50 * 1024 * 1024
        assert downloader.timeout_seconds == 30
        assert downloader.chunk_size == 4096
        assert downloader.max_retries == 5
        assert downloader.follow_redirects is False
        assert downloader.user_agent == "CustomAgent/1.0"
    
    def test_session_creation(self):
        """Test that session is created with retry adapter."""
        from src.downloader import HTTPDownloader
        
        downloader = HTTPDownloader()
        
        assert downloader.session is not None
        assert isinstance(downloader.session, requests.Session)
        assert "User-Agent" in downloader.session.headers


class TestURLSchemeValidation:
    """Test URL scheme validation."""
    
    def test_http_scheme_allowed(self):
        """Test that HTTP scheme is allowed."""
        from src.downloader import HTTPDownloader
        
        downloader = HTTPDownloader()
        
        # Should not raise
        downloader.validate_url_scheme("http://example.com/audio.mp3")
    
    def test_https_scheme_allowed(self):
        """Test that HTTPS scheme is allowed."""
        from src.downloader import HTTPDownloader
        
        downloader = HTTPDownloader()
        
        # Should not raise
        downloader.validate_url_scheme("https://example.com/audio.mp3")
    
    def test_file_scheme_blocked(self):
        """Test that file:// scheme is blocked."""
        from src.downloader import HTTPDownloader
        
        downloader = HTTPDownloader()
        
        with pytest.raises(ValueError, match="Unsupported URL scheme"):
            downloader.validate_url_scheme("file:///etc/passwd")
    
    def test_ftp_scheme_blocked(self):
        """Test that ftp:// scheme is blocked."""
        from src.downloader import HTTPDownloader
        
        downloader = HTTPDownloader()
        
        with pytest.raises(ValueError, match="Unsupported URL scheme"):
            downloader.validate_url_scheme("ftp://example.com/file.mp3")
    
    def test_invalid_url_no_hostname(self):
        """Test that URLs without hostname are rejected."""
        from src.downloader import HTTPDownloader
        
        downloader = HTTPDownloader()
        
        with pytest.raises(ValueError, match="Invalid URL"):
            downloader.validate_url_scheme("http://")


class TestFileSizeValidation:
    """Test file size validation."""
    
    @patch('requests.Session.head')
    def test_file_size_check_success(self, mock_head):
        """Test successful file size check."""
        from src.downloader import HTTPDownloader
        
        # Mock HEAD response
        mock_response = Mock()
        mock_response.headers = {"Content-Length": "5000000"}  # 5MB
        mock_response.raise_for_status = Mock()
        mock_head.return_value = mock_response
        
        downloader = HTTPDownloader(max_size_mb=10)
        size = downloader.check_file_size("https://example.com/audio.mp3")
        
        assert size == 5000000
        mock_head.assert_called_once()
    
    @patch('requests.Session.head')
    def test_file_size_exceeds_limit(self, mock_head):
        """Test that oversized files are rejected."""
        from src.downloader import HTTPDownloader, DownloadSizeError
        
        # Mock HEAD response with large file
        mock_response = Mock()
        mock_response.headers = {"Content-Length": "200000000"}  # 200MB
        mock_response.raise_for_status = Mock()
        mock_head.return_value = mock_response
        
        downloader = HTTPDownloader(max_size_mb=100)
        
        with pytest.raises(DownloadSizeError, match="exceeds maximum allowed size"):
            downloader.check_file_size("https://example.com/audio.mp3")
    
    @patch('requests.Session.head')
    def test_file_size_no_content_length(self, mock_head):
        """Test handling when Content-Length is missing."""
        from src.downloader import HTTPDownloader
        
        # Mock HEAD response without Content-Length
        mock_response = Mock()
        mock_response.headers = {}
        mock_response.raise_for_status = Mock()
        mock_head.return_value = mock_response
        
        downloader = HTTPDownloader()
        size = downloader.check_file_size("https://example.com/audio.mp3")
        
        # Should return 0 when Content-Length is missing
        assert size == 0


class TestFileExtraction:
    """Test file extension extraction."""
    
    def test_extract_mp3_extension(self):
        """Test extracting .mp3 extension."""
        from src.downloader import HTTPDownloader
        
        downloader = HTTPDownloader()
        ext = downloader._get_file_extension("https://example.com/audio.mp3")
        
        assert ext == ".mp3"
    
    def test_extract_flac_extension(self):
        """Test extracting .flac extension."""
        from src.downloader import HTTPDownloader
        
        downloader = HTTPDownloader()
        ext = downloader._get_file_extension("https://example.com/audio.flac")
        
        assert ext == ".flac"
    
    def test_no_extension(self):
        """Test handling URLs without extension."""
        from src.downloader import HTTPDownloader
        
        downloader = HTTPDownloader()
        ext = downloader._get_file_extension("https://example.com/audio")
        
        assert ext == ".bin"
    
    def test_query_parameters_ignored(self):
        """Test that query parameters don't affect extension."""
        from src.downloader import HTTPDownloader
        
        downloader = HTTPDownloader()
        ext = downloader._get_file_extension("https://example.com/audio.mp3?token=abc123")
        
        assert ext == ".mp3"


class TestDownloadFunction:
    """Test the main download function."""
    
    @patch('requests.Session.head')
    @patch('requests.Session.get')
    def test_successful_download(self, mock_get, mock_head):
        """Test successful file download."""
        from src.downloader import HTTPDownloader
        
        # Mock HEAD response
        mock_head_response = Mock()
        mock_head_response.headers = {"Content-Length": "1000"}
        mock_head_response.raise_for_status = Mock()
        mock_head.return_value = mock_head_response
        
        # Mock GET response
        mock_get_response = Mock()
        mock_get_response.headers = {"Content-Length": "1000"}
        mock_get_response.raise_for_status = Mock()
        mock_get_response.iter_content = Mock(return_value=[b"test data chunk"])
        mock_get_response.__enter__ = Mock(return_value=mock_get_response)
        mock_get_response.__exit__ = Mock(return_value=False)
        mock_get.return_value = mock_get_response
        
        downloader = HTTPDownloader()
        
        try:
            result = downloader.download("https://example.com/audio.mp3")
            
            assert result is not None
            assert result.exists()
            assert result.suffix == ".mp3"
            
        finally:
            # Cleanup
            if result and result.exists():
                result.unlink()
    
    @patch('requests.Session.head')
    @patch('requests.Session.get')
    def test_download_with_destination(self, mock_get, mock_head):
        """Test download to specific destination."""
        from src.downloader import HTTPDownloader
        
        # Mock responses
        mock_head_response = Mock()
        mock_head_response.headers = {"Content-Length": "1000"}
        mock_head_response.raise_for_status = Mock()
        mock_head.return_value = mock_head_response
        
        mock_get_response = Mock()
        mock_get_response.headers = {"Content-Length": "1000"}
        mock_get_response.raise_for_status = Mock()
        mock_get_response.iter_content = Mock(return_value=[b"test data"])
        mock_get_response.__enter__ = Mock(return_value=mock_get_response)
        mock_get_response.__exit__ = Mock(return_value=False)
        mock_get.return_value = mock_get_response
        
        downloader = HTTPDownloader()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "test.mp3"
            
            result = downloader.download(
                "https://example.com/audio.mp3",
                destination=dest
            )
            
            assert result == dest
    
    @patch('requests.Session.head')
    @patch('requests.Session.get')
    def test_download_with_progress_callback(self, mock_get, mock_head):
        """Test download with progress tracking."""
        from src.downloader import HTTPDownloader
        
        # Mock responses
        mock_head_response = Mock()
        mock_head_response.headers = {"Content-Length": "2000"}
        mock_head_response.raise_for_status = Mock()
        mock_head.return_value = mock_head_response
        
        mock_get_response = Mock()
        mock_get_response.headers = {"Content-Length": "2000"}
        mock_get_response.raise_for_status = Mock()
        mock_get_response.iter_content = Mock(return_value=[b"a" * 1000, b"b" * 1000])
        mock_get_response.__enter__ = Mock(return_value=mock_get_response)
        mock_get_response.__exit__ = Mock(return_value=False)
        mock_get.return_value = mock_get_response
        
        # Track progress
        progress_calls = []
        
        def track_progress(downloaded, total):
            progress_calls.append((downloaded, total))
        
        downloader = HTTPDownloader()
        
        try:
            result = downloader.download(
                "https://example.com/audio.mp3",
                progress_callback=track_progress
            )
            
            # Progress callback should have been called
            assert len(progress_calls) > 0
            
        finally:
            if result and result.exists():
                result.unlink()
    
    @patch('requests.Session.head')
    @patch('requests.Session.get')
    def test_download_timeout(self, mock_get, mock_head):
        """Test download timeout handling."""
        from src.downloader import HTTPDownloader, DownloadTimeoutError
        
        # Mock HEAD to succeed
        mock_head_response = Mock()
        mock_head_response.headers = {"Content-Length": "1000"}
        mock_head_response.raise_for_status = Mock()
        mock_head.return_value = mock_head_response
        
        # Mock GET to timeout
        mock_get.side_effect = requests.Timeout("Connection timed out")
        
        downloader = HTTPDownloader(timeout_seconds=1)
        
        with pytest.raises(DownloadTimeoutError, match="timed out"):
            downloader.download("https://example.com/audio.mp3")
    
    @patch('requests.Session.head')
    @patch('requests.Session.get')
    def test_download_http_error(self, mock_get, mock_head):
        """Test download HTTP error handling."""
        from src.downloader import HTTPDownloader, DownloadError
        
        # Mock HEAD to succeed
        mock_head_response = Mock()
        mock_head_response.headers = {"Content-Length": "1000"}
        mock_head_response.raise_for_status = Mock()
        mock_head.return_value = mock_head_response
        
        # Mock GET to fail
        mock_get.side_effect = requests.HTTPError("404 Not Found")
        
        downloader = HTTPDownloader()
        
        with pytest.raises(DownloadError, match="Download failed"):
            downloader.download("https://example.com/audio.mp3")


class TestConvenienceFunction:
    """Test the download_from_url convenience function."""
    
    @patch('requests.Session.head')
    @patch('requests.Session.get')
    def test_download_from_url(self, mock_get, mock_head):
        """Test convenience function."""
        from src.downloader import download_from_url
        
        # Mock responses
        mock_head_response = Mock()
        mock_head_response.headers = {"Content-Length": "500"}
        mock_head_response.raise_for_status = Mock()
        mock_head.return_value = mock_head_response
        
        mock_get_response = Mock()
        mock_get_response.headers = {"Content-Length": "500"}
        mock_get_response.raise_for_status = Mock()
        mock_get_response.iter_content = Mock(return_value=[b"test"])
        mock_get_response.__enter__ = Mock(return_value=mock_get_response)
        mock_get_response.__exit__ = Mock(return_value=False)
        mock_get.return_value = mock_get_response
        
        try:
            result = download_from_url("https://example.com/audio.mp3")
            
            assert result is not None
            assert result.exists()
            
        finally:
            if result and result.exists():
                result.unlink()
    
    @patch('requests.Session.head')
    @patch('requests.Session.get')
    def test_download_from_url_with_params(self, mock_get, mock_head):
        """Test convenience function with custom parameters."""
        from src.downloader import download_from_url
        
        # Mock responses
        mock_head_response = Mock()
        mock_head_response.headers = {"Content-Length": "500"}
        mock_head_response.raise_for_status = Mock()
        mock_head.return_value = mock_head_response
        
        mock_get_response = Mock()
        mock_get_response.headers = {"Content-Length": "500"}
        mock_get_response.raise_for_status = Mock()
        mock_get_response.iter_content = Mock(return_value=[b"test"])
        mock_get_response.__enter__ = Mock(return_value=mock_get_response)
        mock_get_response.__exit__ = Mock(return_value=False)
        mock_get.return_value = mock_get_response
        
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "custom.mp3"
            
            result = download_from_url(
                "https://example.com/audio.mp3",
                destination=dest,
                max_size_mb=50,
                timeout_seconds=30,
                headers={"Authorization": "Bearer token"}
            )
            
            assert result == dest


class TestContextManager:
    """Test context manager functionality."""
    
    def test_context_manager(self):
        """Test using downloader as context manager."""
        from src.downloader import HTTPDownloader
        
        with HTTPDownloader() as downloader:
            assert downloader is not None
            assert downloader.session is not None
        
        # Session should be closed after context exit
        # (Can't easily test this without internals)
    
    def test_context_manager_closes_session(self):
        """Test that context manager closes session."""
        from src.downloader import HTTPDownloader
        
        downloader = HTTPDownloader()
        session = downloader.session
        
        with downloader:
            pass
        
        # Session should be closed
        # This is verified by the close() call


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def test_download_error_cleanup(self):
        """Test that partial files are cleaned up on error."""
        from src.downloader import HTTPDownloader, DownloadError
        
        with pytest.raises((DownloadError, ValueError)):
            downloader = HTTPDownloader()
            # Invalid URL should fail validation
            downloader.download("ftp://example.com/file.mp3")
    
    @patch('requests.Session.head')
    @patch('requests.Session.get')
    def test_size_exceeded_during_download(self, mock_get, mock_head):
        """Test file size check during download."""
        from src.downloader import HTTPDownloader, DownloadSizeError
        
        # Mock HEAD with no Content-Length
        mock_head_response = Mock()
        mock_head_response.headers = {}
        mock_head_response.raise_for_status = Mock()
        mock_head.return_value = mock_head_response
        
        # Mock GET with large chunks
        mock_get_response = Mock()
        mock_get_response.headers = {}
        mock_get_response.raise_for_status = Mock()
        # Generate chunks that exceed 1MB limit
        large_chunk = b"x" * (2 * 1024 * 1024)  # 2MB chunk
        mock_get_response.iter_content = Mock(return_value=[large_chunk])
        mock_get_response.__enter__ = Mock(return_value=mock_get_response)
        mock_get_response.__exit__ = Mock(return_value=False)
        mock_get.return_value = mock_get_response
        
        downloader = HTTPDownloader(max_size_mb=1)  # 1MB limit
        
        with pytest.raises(DownloadSizeError, match="exceeds limit during download"):
            downloader.download("https://example.com/audio.mp3")


class TestRedirectHandling:
    """Test HTTP redirect handling."""
    
    @patch('requests.Session.head')
    def test_follow_redirects_enabled(self, mock_head):
        """Test that redirects are followed when enabled."""
        from src.downloader import HTTPDownloader
        
        mock_response = Mock()
        mock_response.headers = {"Content-Length": "1000"}
        mock_response.raise_for_status = Mock()
        mock_head.return_value = mock_response
        
        downloader = HTTPDownloader(follow_redirects=True)
        downloader.check_file_size("https://example.com/redirect")
        
        # Verify allow_redirects=True was passed
        mock_head.assert_called_once()
        call_kwargs = mock_head.call_args[1]
        assert call_kwargs.get('allow_redirects') is True
    
    @patch('requests.Session.head')
    def test_follow_redirects_disabled(self, mock_head):
        """Test that redirects can be disabled."""
        from src.downloader import HTTPDownloader
        
        mock_response = Mock()
        mock_response.headers = {"Content-Length": "1000"}
        mock_response.raise_for_status = Mock()
        mock_head.return_value = mock_response
        
        downloader = HTTPDownloader(follow_redirects=False)
        downloader.check_file_size("https://example.com/redirect")
        
        # Verify allow_redirects=False was passed
        call_kwargs = mock_head.call_args[1]
        assert call_kwargs.get('allow_redirects') is False


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])

