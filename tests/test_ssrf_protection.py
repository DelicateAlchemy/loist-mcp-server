"""
Tests for SSRF (Server-Side Request Forgery) protection.

Tests verify:
- Private IP range detection
- Localhost blocking
- Link-local address blocking
- Multicast address blocking
- Cloud metadata endpoint blocking
- DNS resolution validation
"""

import pytest
from unittest.mock import patch, Mock
import socket

from src.downloader.ssrf_protection import (
    SSRFProtector,
    SSRFProtectionError,
    validate_ssrf,
    is_private_ip,
    PRIVATE_IP_RANGES,
    LOOPBACK_RANGES,
    CLOUD_METADATA_HOSTS,
)


class TestPrivateIPDetection:
    """Test private IP address detection."""
    
    def test_class_a_private_ip(self):
        """Test Class A private IP (10.0.0.0/8)."""
        assert SSRFProtector.is_private_ip("10.0.0.1") is True
        assert SSRFProtector.is_private_ip("10.255.255.255") is True
    
    def test_class_b_private_ip(self):
        """Test Class B private IP (172.16.0.0/12)."""
        assert SSRFProtector.is_private_ip("172.16.0.1") is True
        assert SSRFProtector.is_private_ip("172.31.255.255") is True
    
    def test_class_c_private_ip(self):
        """Test Class C private IP (192.168.0.0/16)."""
        assert SSRFProtector.is_private_ip("192.168.0.1") is True
        assert SSRFProtector.is_private_ip("192.168.255.255") is True
    
    def test_loopback_ipv4(self):
        """Test IPv4 loopback (127.0.0.0/8)."""
        assert SSRFProtector.is_private_ip("127.0.0.1") is True
        assert SSRFProtector.is_private_ip("127.0.0.2") is True
        assert SSRFProtector.is_private_ip("127.255.255.255") is True
    
    def test_loopback_ipv6(self):
        """Test IPv6 loopback (::1)."""
        assert SSRFProtector.is_private_ip("::1") is True
    
    def test_link_local_ipv4(self):
        """Test IPv4 link-local (169.254.0.0/16)."""
        assert SSRFProtector.is_private_ip("169.254.0.1") is True
        assert SSRFProtector.is_private_ip("169.254.169.254") is True  # Cloud metadata
    
    def test_link_local_ipv6(self):
        """Test IPv6 link-local (fe80::/10)."""
        assert SSRFProtector.is_private_ip("fe80::1") is True
    
    def test_multicast_ipv4(self):
        """Test IPv4 multicast (224.0.0.0/4)."""
        assert SSRFProtector.is_private_ip("224.0.0.1") is True
        assert SSRFProtector.is_private_ip("239.255.255.255") is True
    
    def test_multicast_ipv6(self):
        """Test IPv6 multicast (ff00::/8)."""
        assert SSRFProtector.is_private_ip("ff00::1") is True
    
    def test_public_ip_allowed(self):
        """Test public IP addresses are allowed."""
        assert SSRFProtector.is_private_ip("8.8.8.8") is False  # Google DNS
        assert SSRFProtector.is_private_ip("1.1.1.1") is False  # Cloudflare DNS
        assert SSRFProtector.is_private_ip("93.184.216.34") is False  # example.com
    
    def test_invalid_ip_returns_false(self):
        """Test invalid IP addresses return False."""
        assert SSRFProtector.is_private_ip("not-an-ip") is False
        assert SSRFProtector.is_private_ip("999.999.999.999") is False


class TestCloudMetadataDetection:
    """Test cloud metadata endpoint detection."""
    
    def test_aws_metadata_endpoint(self):
        """Test AWS metadata endpoint is detected."""
        assert SSRFProtector.is_cloud_metadata_endpoint("169.254.169.254") is True
    
    def test_gcp_metadata_endpoint(self):
        """Test GCP metadata endpoint is detected."""
        assert SSRFProtector.is_cloud_metadata_endpoint("metadata.google.internal") is True
        assert SSRFProtector.is_cloud_metadata_endpoint("METADATA.GOOGLE.INTERNAL") is True
    
    def test_generic_metadata_endpoint(self):
        """Test generic metadata endpoint is detected."""
        assert SSRFProtector.is_cloud_metadata_endpoint("metadata") is True
    
    def test_normal_domain_not_metadata(self):
        """Test normal domains are not detected as metadata."""
        assert SSRFProtector.is_cloud_metadata_endpoint("example.com") is False
        assert SSRFProtector.is_cloud_metadata_endpoint("api.example.com") is False


class TestDNSResolution:
    """Test DNS resolution for SSRF protection."""
    
    @patch('socket.getaddrinfo')
    def test_resolve_hostname(self, mock_getaddrinfo):
        """Test hostname resolution."""
        # Mock DNS response
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 0)),
        ]
        
        ips = SSRFProtector.resolve_hostname("example.com")
        
        assert "93.184.216.34" in ips
        mock_getaddrinfo.assert_called_once()
    
    @patch('socket.getaddrinfo')
    def test_resolve_hostname_multiple_ips(self, mock_getaddrinfo):
        """Test hostname with multiple IP addresses."""
        # Mock DNS response with multiple IPs
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.35', 0)),
        ]
        
        ips = SSRFProtector.resolve_hostname("example.com")
        
        assert len(ips) == 2
        assert "93.184.216.34" in ips
        assert "93.184.216.35" in ips
    
    @patch('socket.getaddrinfo')
    def test_resolve_hostname_timeout(self, mock_getaddrinfo):
        """Test DNS resolution timeout handling."""
        mock_getaddrinfo.side_effect = socket.gaierror("Timeout")
        
        with pytest.raises(socket.gaierror):
            SSRFProtector.resolve_hostname("slow-dns.example.com")


class TestSSRFURLValidation:
    """Test complete SSRF URL validation."""
    
    def test_public_url_allowed(self):
        """Test public URLs are allowed."""
        # Should not raise
        SSRFProtector.validate_url("https://example.com/audio.mp3", check_dns=False)
    
    def test_private_ip_blocked(self):
        """Test private IP addresses are blocked."""
        private_ips = [
            "http://10.0.0.1/audio.mp3",
            "http://172.16.0.1/audio.mp3",
            "http://192.168.1.1/audio.mp3",
        ]
        
        for url in private_ips:
            with pytest.raises(SSRFProtectionError, match="private IP"):
                SSRFProtector.validate_url(url, check_dns=False)
    
    def test_localhost_blocked(self):
        """Test localhost is blocked."""
        localhost_urls = [
            "http://127.0.0.1/audio.mp3",
            "http://127.0.0.2/audio.mp3",
            "http://[::1]/audio.mp3",
        ]
        
        for url in localhost_urls:
            with pytest.raises(SSRFProtectionError, match="private IP"):
                SSRFProtector.validate_url(url, check_dns=False)
    
    def test_link_local_blocked(self):
        """Test link-local addresses are blocked."""
        with pytest.raises(SSRFProtectionError, match="private IP"):
            SSRFProtector.validate_url("http://169.254.169.254/metadata", check_dns=False)
    
    def test_cloud_metadata_endpoint_blocked(self):
        """Test cloud metadata endpoints are blocked."""
        metadata_urls = [
            "http://169.254.169.254/latest/meta-data/",
            "http://metadata.google.internal/computeMetadata/v1/",
            "http://metadata/",
        ]
        
        for url in metadata_urls:
            with pytest.raises(SSRFProtectionError, match="metadata endpoint"):
                SSRFProtector.validate_url(url, check_dns=False)
    
    @patch('socket.getaddrinfo')
    def test_hostname_resolving_to_private_ip_blocked(self, mock_getaddrinfo):
        """Test hostname that resolves to private IP is blocked."""
        # Mock DNS to return private IP
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('192.168.1.1', 0)),
        ]
        
        with pytest.raises(SSRFProtectionError, match="resolves to private IP"):
            SSRFProtector.validate_url("http://internal.example.com/audio.mp3", check_dns=True)
    
    @patch('socket.getaddrinfo')
    def test_hostname_resolving_to_public_ip_allowed(self, mock_getaddrinfo):
        """Test hostname resolving to public IP is allowed."""
        # Mock DNS to return public IP
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 0)),
        ]
        
        # Should not raise
        SSRFProtector.validate_url("https://example.com/audio.mp3", check_dns=True)
    
    @patch('socket.getaddrinfo')
    def test_dns_resolution_failure_allowed(self, mock_getaddrinfo):
        """Test DNS resolution failure doesn't block download."""
        # Mock DNS failure
        mock_getaddrinfo.side_effect = socket.gaierror("Name resolution failed")
        
        # Should not raise (allows download to fail naturally)
        SSRFProtector.validate_url("https://nonexistent.example.com/audio.mp3", check_dns=True)
    
    def test_validation_without_dns_check(self):
        """Test validation can skip DNS resolution."""
        # Should validate just the IP/hostname without DNS
        SSRFProtector.validate_url("https://example.com/audio.mp3", check_dns=False)


class TestConvenienceFunctions:
    """Test convenience wrapper functions."""
    
    def test_validate_ssrf_function(self):
        """Test validate_ssrf convenience function."""
        # Should not raise for public URL
        validate_ssrf("https://example.com/audio.mp3", check_dns=False)
    
    def test_validate_ssrf_blocks_private(self):
        """Test validate_ssrf blocks private IPs."""
        with pytest.raises(SSRFProtectionError):
            validate_ssrf("http://192.168.1.1/audio.mp3", check_dns=False)
    
    def test_is_private_ip_function(self):
        """Test is_private_ip convenience function."""
        assert is_private_ip("192.168.1.1") is True
        assert is_private_ip("8.8.8.8") is False
    
    @patch('socket.getaddrinfo')
    def test_is_private_ip_with_hostname(self, mock_getaddrinfo):
        """Test is_private_ip with hostname resolution."""
        # Mock DNS to return private IP
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('192.168.1.1', 0)),
        ]
        
        assert is_private_ip("internal.example.com") is True


class TestIntegrationWithDownloader:
    """Test integration with HTTPDownloader."""
    
    @patch('requests.Session.head')
    @patch('requests.Session.get')
    def test_downloader_blocks_private_ip(self, mock_get, mock_head):
        """Test downloader blocks private IP addresses."""
        from src.downloader import HTTPDownloader
        
        downloader = HTTPDownloader()
        
        with pytest.raises(SSRFProtectionError, match="private IP"):
            downloader.download("http://192.168.1.1/audio.mp3")
    
    @patch('requests.Session.head')
    @patch('requests.Session.get')
    def test_downloader_blocks_localhost(self, mock_get, mock_head):
        """Test downloader blocks localhost."""
        from src.downloader import HTTPDownloader
        
        downloader = HTTPDownloader()
        
        with pytest.raises(SSRFProtectionError, match="private IP"):
            downloader.download("http://127.0.0.1/audio.mp3")
    
    @patch('requests.Session.head')
    @patch('requests.Session.get')
    def test_downloader_blocks_metadata_endpoint(self, mock_get, mock_head):
        """Test downloader blocks cloud metadata endpoints."""
        from src.downloader import HTTPDownloader
        
        downloader = HTTPDownloader()
        
        with pytest.raises(SSRFProtectionError, match="metadata endpoint"):
            downloader.download("http://169.254.169.254/latest/meta-data/")


class TestEdgeCases:
    """Test edge cases and special scenarios."""
    
    def test_ipv6_localhost(self):
        """Test IPv6 localhost is blocked."""
        assert SSRFProtector.is_private_ip("::1") is True
    
    def test_ipv6_link_local(self):
        """Test IPv6 link-local is blocked."""
        assert SSRFProtector.is_private_ip("fe80::1") is True
    
    def test_reserved_ranges(self):
        """Test reserved IP ranges are blocked."""
        assert SSRFProtector.is_private_ip("0.0.0.0") is True
        assert SSRFProtector.is_private_ip("240.0.0.1") is True
    
    def test_shared_address_space(self):
        """Test shared address space is blocked."""
        assert SSRFProtector.is_private_ip("100.64.0.1") is True
    
    def test_public_ips_allowed(self):
        """Test various public IPs are allowed."""
        public_ips = [
            "8.8.8.8",          # Google DNS
            "1.1.1.1",          # Cloudflare DNS
            "93.184.216.34",    # example.com
            "13.107.42.14",     # microsoft.com
        ]
        
        for ip in public_ips:
            assert SSRFProtector.is_private_ip(ip) is False


class TestURLValidation:
    """Test complete URL validation."""
    
    def test_validate_url_with_public_ip(self):
        """Test URL with public IP is allowed."""
        # Should not raise
        SSRFProtector.validate_url("https://8.8.8.8/audio.mp3", check_dns=False)
    
    def test_validate_url_with_private_ip_blocked(self):
        """Test URL with private IP is blocked."""
        with pytest.raises(SSRFProtectionError):
            SSRFProtector.validate_url("https://192.168.1.1/audio.mp3", check_dns=False)
    
    def test_validate_url_no_hostname(self):
        """Test URL without hostname raises error."""
        with pytest.raises(SSRFProtectionError, match="must have a hostname"):
            SSRFProtector.validate_url("https:///audio.mp3", check_dns=False)
    
    @patch('socket.getaddrinfo')
    def test_validate_url_with_dns_check(self, mock_getaddrinfo):
        """Test URL validation with DNS resolution."""
        # Mock public IP
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 0)),
        ]
        
        # Should not raise
        SSRFProtector.validate_url("https://example.com/audio.mp3", check_dns=True)


class TestIPRangeConfiguration:
    """Test IP range configuration."""
    
    def test_private_ip_ranges_exist(self):
        """Test private IP ranges are configured."""
        assert len(PRIVATE_IP_RANGES) >= 3
        assert any("10.0.0.0" in str(r) for r in PRIVATE_IP_RANGES)
        assert any("172.16.0.0" in str(r) for r in PRIVATE_IP_RANGES)
        assert any("192.168.0.0" in str(r) for r in PRIVATE_IP_RANGES)
    
    def test_loopback_ranges_exist(self):
        """Test loopback ranges are configured."""
        assert len(LOOPBACK_RANGES) >= 2
        assert any("127.0.0.0" in str(r) for r in LOOPBACK_RANGES)
    
    def test_cloud_metadata_hosts_exist(self):
        """Test cloud metadata hosts are configured."""
        assert "169.254.169.254" in CLOUD_METADATA_HOSTS
        assert "metadata.google.internal" in CLOUD_METADATA_HOSTS


class TestErrorMessages:
    """Test error messages are helpful."""
    
    def test_private_ip_error_message(self):
        """Test error message for private IP."""
        try:
            SSRFProtector.validate_url("http://192.168.1.1/audio.mp3", check_dns=False)
            pytest.fail("Should have raised SSRFProtectionError")
        except SSRFProtectionError as e:
            assert "private IP" in str(e).lower()
            assert "192.168.1.1" in str(e)
    
    def test_metadata_endpoint_error_message(self):
        """Test error message for metadata endpoint."""
        try:
            SSRFProtector.validate_url("http://metadata.google.internal/", check_dns=False)
            pytest.fail("Should have raised SSRFProtectionError")
        except SSRFProtectionError as e:
            assert "metadata endpoint" in str(e).lower()
    
    @patch('socket.getaddrinfo')
    def test_dns_resolution_private_ip_error(self, mock_getaddrinfo):
        """Test error message when hostname resolves to private IP."""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('192.168.1.1', 0)),
        ]
        
        try:
            SSRFProtector.validate_url("http://internal.local/audio.mp3", check_dns=True)
            pytest.fail("Should have raised SSRFProtectionError")
        except SSRFProtectionError as e:
            assert "resolves to private IP" in str(e)
            assert "192.168.1.1" in str(e)


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])

