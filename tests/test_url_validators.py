"""
Tests for URL validation.

Tests verify:
- URL scheme validation
- Hostname validation
- Dangerous scheme detection
- URL normalization
- Error handling
"""

import pytest
from src.downloader.validators import (
    URLSchemeValidator,
    URLValidationError,
    validate_url,
    ALLOWED_SCHEMES,
    BLOCKED_SCHEMES,
)


class TestURLSchemeValidation:
    """Test URL scheme validation."""
    
    def test_http_scheme_allowed(self):
        """Test that HTTP scheme is allowed."""
        url = "http://example.com/audio.mp3"
        is_valid, msg = URLSchemeValidator.validate_scheme(url)
        assert is_valid is True
    
    def test_https_scheme_allowed(self):
        """Test that HTTPS scheme is allowed."""
        url = "https://example.com/audio.mp3"
        is_valid, msg = URLSchemeValidator.validate_scheme(url)
        assert is_valid is True
    
    def test_file_scheme_blocked(self):
        """Test that file:// scheme is blocked."""
        with pytest.raises(URLValidationError, match="Blocked URL scheme"):
            URLSchemeValidator.validate_scheme("file:///etc/passwd")
    
    def test_ftp_scheme_blocked(self):
        """Test that ftp:// scheme is blocked."""
        with pytest.raises(URLValidationError, match="Blocked URL scheme"):
            URLSchemeValidator.validate_scheme("ftp://example.com/file.mp3")
    
    def test_data_scheme_blocked(self):
        """Test that data: scheme is blocked."""
        with pytest.raises(URLValidationError, match="Blocked URL scheme"):
            URLSchemeValidator.validate_scheme("data:text/plain;base64,SGVsbG8=")
    
    def test_javascript_scheme_blocked(self):
        """Test that javascript: scheme is blocked."""
        with pytest.raises(URLValidationError, match="Blocked URL scheme"):
            URLSchemeValidator.validate_scheme("javascript:alert('xss')")
    
    def test_ws_scheme_blocked(self):
        """Test that ws:// scheme is blocked."""
        with pytest.raises(URLValidationError, match="Unsupported URL scheme"):
            URLSchemeValidator.validate_scheme("ws://example.com/socket")
    
    def test_unknown_scheme_rejected(self):
        """Test that unknown schemes are rejected."""
        with pytest.raises(URLValidationError, match="Unsupported URL scheme"):
            URLSchemeValidator.validate_scheme("custom://example.com/file")
    
    def test_missing_scheme_rejected(self):
        """Test that URLs without scheme are rejected."""
        with pytest.raises(URLValidationError, match="must include a scheme"):
            URLSchemeValidator.validate_scheme("example.com/audio.mp3")
    
    def test_empty_url_rejected(self):
        """Test that empty URLs are rejected."""
        with pytest.raises(URLValidationError, match="non-empty string"):
            URLSchemeValidator.validate_scheme("")
    
    def test_none_url_rejected(self):
        """Test that None is rejected."""
        with pytest.raises(URLValidationError, match="non-empty string"):
            URLSchemeValidator.validate_scheme(None)
    
    def test_missing_hostname_rejected(self):
        """Test that URLs without hostname are rejected."""
        with pytest.raises(URLValidationError, match="missing hostname"):
            URLSchemeValidator.validate_scheme("https://")


class TestHostnameValidation:
    """Test hostname validation."""
    
    def test_valid_domain_name(self):
        """Test valid domain name."""
        url = "https://example.com/audio.mp3"
        is_valid, msg = URLSchemeValidator.validate_hostname(url)
        assert is_valid is True
    
    def test_subdomain_allowed(self):
        """Test subdomain is allowed."""
        url = "https://cdn.example.com/audio.mp3"
        is_valid, msg = URLSchemeValidator.validate_hostname(url)
        assert is_valid is True
    
    def test_port_number_allowed(self):
        """Test port number in hostname."""
        url = "https://example.com:8080/audio.mp3"
        is_valid, msg = URLSchemeValidator.validate_hostname(url)
        assert is_valid is True
    
    def test_localhost_allowed_with_warning(self):
        """Test localhost is allowed but logged."""
        url = "http://localhost/audio.mp3"
        # Should not raise, but logs warning
        is_valid, msg = URLSchemeValidator.validate_hostname(url)
        assert is_valid is True
    
    def test_127_0_0_1_allowed_with_warning(self):
        """Test 127.0.0.1 is allowed but logged."""
        url = "http://127.0.0.1/audio.mp3"
        # Should not raise, but logs warning
        is_valid, msg = URLSchemeValidator.validate_hostname(url)
        assert is_valid is True
    
    def test_invalid_hostname_format(self):
        """Test invalid hostname format is rejected."""
        url = "https://invalid_hostname/audio.mp3"
        with pytest.raises(URLValidationError, match="Invalid hostname format"):
            URLSchemeValidator.validate_hostname(url)
    
    def test_hostname_with_invalid_characters(self):
        """Test hostname with invalid characters."""
        url = 'https://exam<ple>.com/audio.mp3'
        with pytest.raises(URLValidationError, match="invalid characters"):
            URLSchemeValidator.validate_hostname(url)
    
    def test_missing_hostname(self):
        """Test missing hostname."""
        url = "https:///audio.mp3"
        with pytest.raises(URLValidationError, match="Hostname is required"):
            URLSchemeValidator.validate_hostname(url)


class TestURLNormalization:
    """Test URL normalization."""
    
    def test_normalize_scheme_to_lowercase(self):
        """Test scheme is normalized to lowercase."""
        url = "HTTP://EXAMPLE.COM/audio.mp3"
        normalized = URLSchemeValidator.normalize_url(url)
        assert normalized.startswith("http://")
    
    def test_normalize_hostname_to_lowercase(self):
        """Test hostname is normalized to lowercase."""
        url = "https://EXAMPLE.COM/audio.mp3"
        normalized = URLSchemeValidator.normalize_url(url)
        assert "EXAMPLE.COM" not in normalized
        assert "example.com" in normalized
    
    def test_remove_default_http_port(self):
        """Test default HTTP port is removed."""
        url = "http://example.com:80/audio.mp3"
        normalized = URLSchemeValidator.normalize_url(url)
        assert ":80" not in normalized
        assert "example.com/audio.mp3" in normalized
    
    def test_remove_default_https_port(self):
        """Test default HTTPS port is removed."""
        url = "https://example.com:443/audio.mp3"
        normalized = URLSchemeValidator.normalize_url(url)
        assert ":443" not in normalized
        assert "example.com/audio.mp3" in normalized
    
    def test_keep_non_default_port(self):
        """Test non-default ports are kept."""
        url = "https://example.com:8080/audio.mp3"
        normalized = URLSchemeValidator.normalize_url(url)
        assert ":8080" in normalized
    
    def test_strip_whitespace(self):
        """Test whitespace is stripped."""
        url = "  https://example.com/audio.mp3  "
        normalized = URLSchemeValidator.normalize_url(url)
        assert not normalized.startswith(" ")
        assert not normalized.endswith(" ")
    
    def test_preserve_path_and_query(self):
        """Test path and query parameters are preserved."""
        url = "https://example.com/path/to/audio.mp3?token=abc&format=mp3"
        normalized = URLSchemeValidator.normalize_url(url)
        assert "/path/to/audio.mp3" in normalized
        assert "token=abc" in normalized
        assert "format=mp3" in normalized


class TestCompleteValidation:
    """Test complete URL validation."""
    
    def test_validate_valid_http_url(self):
        """Test validation of valid HTTP URL."""
        url = "http://example.com/audio.mp3"
        validated = URLSchemeValidator.validate(url)
        assert validated == url
    
    def test_validate_valid_https_url(self):
        """Test validation of valid HTTPS URL."""
        url = "https://example.com/audio.mp3"
        validated = URLSchemeValidator.validate(url)
        assert validated == url
    
    def test_validate_normalizes_url(self):
        """Test validation normalizes URL."""
        url = "HTTPS://EXAMPLE.COM:443/audio.mp3"
        validated = URLSchemeValidator.validate(url, normalize=True)
        assert validated == "https://example.com/audio.mp3"
    
    def test_validate_without_normalization(self):
        """Test validation can skip normalization."""
        url = "HTTPS://EXAMPLE.COM/audio.mp3"
        validated = URLSchemeValidator.validate(url, normalize=False)
        # Should still pass validation even without normalization
        assert "HTTPS" in validated
    
    def test_validate_rejects_invalid_scheme(self):
        """Test validation rejects invalid schemes."""
        with pytest.raises(URLValidationError):
            URLSchemeValidator.validate("ftp://example.com/file.mp3")
    
    def test_validate_rejects_invalid_hostname(self):
        """Test validation rejects invalid hostnames."""
        with pytest.raises(URLValidationError):
            URLSchemeValidator.validate("https://invalid_host/file.mp3")


class TestConvenienceFunction:
    """Test convenience validation function."""
    
    def test_validate_url_function(self):
        """Test validate_url convenience function."""
        url = "https://example.com/audio.mp3"
        validated = validate_url(url)
        assert validated == url
    
    def test_validate_url_normalizes(self):
        """Test validate_url normalizes by default."""
        url = "HTTPS://EXAMPLE.COM:443/audio.mp3"
        validated = validate_url(url)
        assert validated == "https://example.com/audio.mp3"
    
    def test_validate_url_rejects_dangerous_schemes(self):
        """Test validate_url rejects dangerous schemes."""
        dangerous_urls = [
            "file:///etc/passwd",
            "ftp://example.com/file.mp3",
            "javascript:alert('xss')",
            "data:text/plain,hello",
        ]
        
        for url in dangerous_urls:
            with pytest.raises(URLValidationError):
                validate_url(url)


class TestAllowedSchemes:
    """Test allowed schemes configuration."""
    
    def test_allowed_schemes_contains_http(self):
        """Test HTTP is in allowed schemes."""
        assert "http" in ALLOWED_SCHEMES
    
    def test_allowed_schemes_contains_https(self):
        """Test HTTPS is in allowed schemes."""
        assert "https" in ALLOWED_SCHEMES
    
    def test_allowed_schemes_count(self):
        """Test only HTTP and HTTPS are allowed."""
        assert len(ALLOWED_SCHEMES) == 2


class TestBlockedSchemes:
    """Test blocked schemes configuration."""
    
    def test_blocked_schemes_contains_file(self):
        """Test file:// is blocked."""
        assert "file" in BLOCKED_SCHEMES
    
    def test_blocked_schemes_contains_ftp(self):
        """Test ftp:// is blocked."""
        assert "ftp" in BLOCKED_SCHEMES
    
    def test_blocked_schemes_contains_javascript(self):
        """Test javascript: is blocked."""
        assert "javascript" in BLOCKED_SCHEMES
    
    def test_blocked_schemes_contains_data(self):
        """Test data: is blocked."""
        assert "data" in BLOCKED_SCHEMES
    
    def test_no_overlap_allowed_blocked(self):
        """Test no overlap between allowed and blocked schemes."""
        overlap = ALLOWED_SCHEMES & BLOCKED_SCHEMES
        assert len(overlap) == 0, f"Overlap found: {overlap}"


class TestEdgeCases:
    """Test edge cases and security scenarios."""
    
    def test_case_insensitive_scheme(self):
        """Test scheme validation is case-insensitive."""
        urls = [
            "HTTP://example.com/audio.mp3",
            "Http://example.com/audio.mp3",
            "HTTPS://example.com/audio.mp3",
            "Https://example.com/audio.mp3",
        ]
        
        for url in urls:
            # Should not raise
            URLSchemeValidator.validate_scheme(url)
    
    def test_url_with_credentials_allowed(self):
        """Test URL with credentials in netloc."""
        url = "https://user:pass@example.com/audio.mp3"
        # Should validate successfully
        validated = URLSchemeValidator.validate(url)
        assert "example.com" in validated
    
    def test_url_with_fragment(self):
        """Test URL with fragment."""
        url = "https://example.com/audio.mp3#section"
        validated = URLSchemeValidator.validate(url)
        assert "#section" in validated
    
    def test_ipv4_hostname_allowed(self):
        """Test IPv4 address as hostname."""
        url = "https://192.168.1.1/audio.mp3"
        # Should validate (SSRF protection is separate)
        validated = URLSchemeValidator.validate(url)
        assert "192.168.1.1" in validated
    
    def test_ipv6_hostname_allowed(self):
        """Test IPv6 address as hostname."""
        url = "https://[2001:db8::1]/audio.mp3"
        validated = URLSchemeValidator.validate(url)
        assert "2001:db8::1" in validated


class TestErrorMessages:
    """Test error messages are helpful."""
    
    def test_blocked_scheme_error_message(self):
        """Test error message for blocked scheme."""
        try:
            URLSchemeValidator.validate_scheme("file:///etc/passwd")
            pytest.fail("Should have raised URLValidationError")
        except URLValidationError as e:
            assert "Blocked URL scheme 'file'" in str(e)
            assert "security reasons" in str(e)
    
    def test_unsupported_scheme_error_message(self):
        """Test error message for unsupported scheme."""
        try:
            URLSchemeValidator.validate_scheme("custom://example.com")
            pytest.fail("Should have raised URLValidationError")
        except URLValidationError as e:
            assert "Unsupported URL scheme 'custom'" in str(e)
            assert "HTTP and HTTPS" in str(e)
    
    def test_missing_hostname_error_message(self):
        """Test error message for missing hostname."""
        try:
            URLSchemeValidator.validate_scheme("https://")
            pytest.fail("Should have raised URLValidationError")
        except URLValidationError as e:
            assert "missing hostname" in str(e)
            assert "https://hostname/path" in str(e)


class TestIntegrationWithDownloader:
    """Test integration with HTTPDownloader."""
    
    def test_downloader_uses_validator(self):
        """Test that HTTPDownloader uses the validator."""
        from src.downloader import HTTPDownloader
        
        downloader = HTTPDownloader()
        
        # Should use the enhanced validator
        validated = downloader.validate_url_scheme("HTTPS://EXAMPLE.COM/audio.mp3")
        assert validated == "https://example.com/audio.mp3"
    
    def test_downloader_rejects_dangerous_schemes(self):
        """Test downloader rejects dangerous schemes."""
        from src.downloader import HTTPDownloader
        
        downloader = HTTPDownloader()
        
        with pytest.raises(URLValidationError):
            downloader.validate_url_scheme("file:///etc/passwd")
    
    def test_downloader_normalizes_urls(self):
        """Test downloader normalizes URLs."""
        from src.downloader import HTTPDownloader
        
        downloader = HTTPDownloader()
        
        validated = downloader.validate_url_scheme("HTTPS://EXAMPLE.COM:443/audio.mp3")
        assert validated == "https://example.com/audio.mp3"


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])

