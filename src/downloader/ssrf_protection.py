"""
SSRF (Server-Side Request Forgery) protection for URL downloads.

Provides comprehensive protection against SSRF attacks by:
- Blocking private IP ranges (RFC 1918)
- Blocking localhost and loopback addresses
- Blocking link-local and multicast addresses
- Blocking cloud metadata endpoints
- DNS resolution validation
"""

import ipaddress
import logging
import socket
from typing import Set, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class SSRFProtectionError(ValueError):
    """Exception raised when SSRF protection blocks a URL."""
    pass


# Private IP ranges (RFC 1918)
PRIVATE_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),          # Class A private
    ipaddress.ip_network("172.16.0.0/12"),       # Class B private
    ipaddress.ip_network("192.168.0.0/16"),      # Class C private
]

# Loopback addresses
LOOPBACK_RANGES = [
    ipaddress.ip_network("127.0.0.0/8"),         # IPv4 loopback
    ipaddress.ip_network("::1/128"),             # IPv6 loopback
]

# Link-local addresses
LINK_LOCAL_RANGES = [
    ipaddress.ip_network("169.254.0.0/16"),      # IPv4 link-local
    ipaddress.ip_network("fe80::/10"),           # IPv6 link-local
]

# Multicast addresses
MULTICAST_RANGES = [
    ipaddress.ip_network("224.0.0.0/4"),         # IPv4 multicast
    ipaddress.ip_network("ff00::/8"),            # IPv6 multicast
]

# Reserved/special addresses
RESERVED_RANGES = [
    ipaddress.ip_network("0.0.0.0/8"),           # Current network
    ipaddress.ip_network("100.64.0.0/10"),       # Shared address space
    ipaddress.ip_network("198.18.0.0/15"),       # Benchmark testing
    ipaddress.ip_network("240.0.0.0/4"),         # Reserved
]

# Cloud metadata endpoints (common cloud providers)
CLOUD_METADATA_HOSTS = {
    "169.254.169.254",      # AWS, GCP, Azure metadata
    "metadata.google.internal",  # GCP
    "metadata",             # Generic
}

# All blocked ranges combined
BLOCKED_IP_RANGES = (
    PRIVATE_IP_RANGES +
    LOOPBACK_RANGES +
    LINK_LOCAL_RANGES +
    MULTICAST_RANGES +
    RESERVED_RANGES
)


class SSRFProtector:
    """
    SSRF protection validator.
    
    Validates URLs and IP addresses to prevent Server-Side Request Forgery attacks.
    """
    
    @staticmethod
    def is_private_ip(ip_str: str) -> bool:
        """
        Check if IP address is in a private range.
        
        Args:
            ip_str: IP address as string
        
        Returns:
            True if IP is private, False otherwise
        """
        try:
            ip = ipaddress.ip_address(ip_str)
            
            # Check against all blocked ranges
            for ip_range in BLOCKED_IP_RANGES:
                if ip in ip_range:
                    logger.debug(f"IP {ip_str} is in blocked range {ip_range}")
                    return True
            
            return False
            
        except ValueError:
            # Not a valid IP address
            return False
    
    @staticmethod
    def is_cloud_metadata_endpoint(hostname: str) -> bool:
        """
        Check if hostname is a known cloud metadata endpoint.
        
        Args:
            hostname: Hostname to check
        
        Returns:
            True if hostname is a cloud metadata endpoint
        """
        return hostname.lower() in CLOUD_METADATA_HOSTS
    
    @staticmethod
    def resolve_hostname(hostname: str, timeout: int = 5) -> Set[str]:
        """
        Resolve hostname to IP addresses.
        
        Args:
            hostname: Hostname to resolve
            timeout: DNS resolution timeout
        
        Returns:
            Set of resolved IP addresses
        
        Raises:
            socket.gaierror: If DNS resolution fails
        """
        try:
            # Set socket timeout for DNS resolution
            socket.setdefaulttimeout(timeout)
            
            # Resolve hostname
            addr_info = socket.getaddrinfo(
                hostname,
                None,
                socket.AF_UNSPEC,  # IPv4 or IPv6
                socket.SOCK_STREAM
            )
            
            # Extract unique IP addresses
            ip_addresses = set()
            for family, socktype, proto, canonname, sockaddr in addr_info:
                ip = sockaddr[0]
                ip_addresses.add(ip)
            
            logger.debug(f"Resolved {hostname} to: {ip_addresses}")
            return ip_addresses
            
        except socket.gaierror as e:
            logger.warning(f"Failed to resolve hostname {hostname}: {e}")
            raise
        finally:
            socket.setdefaulttimeout(None)
    
    @staticmethod
    def validate_url(url: str, check_dns: bool = True) -> None:
        """
        Validate URL for SSRF protection.
        
        Args:
            url: URL to validate
            check_dns: Whether to perform DNS resolution check
        
        Raises:
            SSRFProtectionError: If URL is blocked by SSRF protection
        """
        parsed = urlparse(url)
        hostname = parsed.hostname
        
        if not hostname:
            raise SSRFProtectionError("URL must have a hostname")
        
        # Check for cloud metadata endpoints
        if SSRFProtector.is_cloud_metadata_endpoint(hostname):
            raise SSRFProtectionError(
                f"Access to cloud metadata endpoint '{hostname}' is blocked"
            )
        
        # Check if hostname is an IP address
        try:
            # Try to parse as IP address
            ip = ipaddress.ip_address(hostname)
            
            # Check if it's a private IP
            if SSRFProtector.is_private_ip(hostname):
                raise SSRFProtectionError(
                    f"Access to private IP address {hostname} is blocked. "
                    f"Private IPs, localhost, and internal networks are not allowed."
                )
            
            logger.debug(f"IP address {hostname} is public - allowed")
            
        except ValueError:
            # Not an IP address, it's a hostname
            # Perform DNS resolution check if enabled
            if check_dns:
                try:
                    resolved_ips = SSRFProtector.resolve_hostname(hostname)
                    
                    # Check each resolved IP
                    for ip_str in resolved_ips:
                        if SSRFProtector.is_private_ip(ip_str):
                            raise SSRFProtectionError(
                                f"Hostname '{hostname}' resolves to private IP {ip_str}. "
                                f"Access to private IP addresses is blocked."
                            )
                    
                    logger.debug(f"Hostname {hostname} resolves to public IPs: {resolved_ips}")
                    
                except socket.gaierror:
                    # DNS resolution failed - allow it to proceed
                    # The actual download will fail with a proper error
                    logger.warning(f"Could not resolve hostname: {hostname}")
    
    @staticmethod
    def validate_ip_address(ip_str: str) -> None:
        """
        Validate that an IP address is not private/restricted.
        
        Args:
            ip_str: IP address as string
        
        Raises:
            SSRFProtectionError: If IP is private or restricted
        """
        if SSRFProtector.is_private_ip(ip_str):
            raise SSRFProtectionError(
                f"Access to private IP address {ip_str} is blocked"
            )


def validate_ssrf(url: str, check_dns: bool = True) -> None:
    """
    Validate URL for SSRF protection.
    
    Convenience function for SSRF validation.
    
    Args:
        url: URL to validate
        check_dns: Whether to perform DNS resolution check
    
    Raises:
        SSRFProtectionError: If URL is blocked
    
    Example:
        >>> from src.downloader.ssrf_protection import validate_ssrf
        >>> validate_ssrf("https://example.com/audio.mp3")  # OK
        >>> validate_ssrf("http://192.168.1.1/audio.mp3")  # Raises SSRFProtectionError
    """
    SSRFProtector.validate_url(url, check_dns=check_dns)


def is_private_ip(ip_or_hostname: str) -> bool:
    """
    Check if IP address or hostname is private.
    
    Args:
        ip_or_hostname: IP address or hostname to check
    
    Returns:
        True if private, False otherwise
    """
    # First check if it's directly an IP
    if SSRFProtector.is_private_ip(ip_or_hostname):
        return True
    
    # Try to resolve as hostname
    try:
        resolved_ips = SSRFProtector.resolve_hostname(ip_or_hostname)
        return any(SSRFProtector.is_private_ip(ip) for ip in resolved_ips)
    except socket.gaierror:
        # Can't resolve - assume not private
        return False

