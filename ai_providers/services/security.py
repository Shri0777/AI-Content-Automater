"""
Security utilities for AI provider integrations.

Provides SSRF protection and destination validation for custom API endpoints.
"""
import ipaddress
import logging
import socket
import urllib.parse
from typing import Tuple

logger = logging.getLogger(__name__)

# Cloud metadata and internal service domains/hostnames to block
BLOCKED_HOSTNAMES = {
    'localhost',
    'metadata.google.internal',
    'metadata.internal',
    'instance-data',
}

# Explicitly blocked IP networks for SSRF prevention
BLOCKED_NETWORKS = [
    ipaddress.ip_network('127.0.0.0/8'),      # Loopback
    ipaddress.ip_network('10.0.0.0/8'),       # Private class A
    ipaddress.ip_network('172.16.0.0/12'),    # Private class B
    ipaddress.ip_network('192.168.0.0/16'),   # Private class C
    ipaddress.ip_network('169.254.0.0/16'),   # Link-local / Cloud metadata (AWS, GCP, Azure)
    ipaddress.ip_network('0.0.0.0/8'),        # Current network
    ipaddress.ip_network('100.64.0.0/10'),    # Shared address space / Carrier NAT
    ipaddress.ip_network('198.18.0.0/15'),    # Benchmark network
    ipaddress.ip_network('224.0.0.0/4'),      # Multicast
    ipaddress.ip_network('240.0.0.0/4'),      # Reserved
    ipaddress.ip_network('255.255.255.255/32'), # Broadcast
    ipaddress.ip_network('::1/128'),          # IPv6 loopback
    ipaddress.ip_network('fc00::/7'),         # IPv6 unique local
    ipaddress.ip_network('fe80::/10'),        # IPv6 link-local
]


def validate_safe_endpoint(url: str, allow_http: bool = False) -> Tuple[bool, str]:
    """
    Validate an outbound AI provider API endpoint to prevent SSRF vulnerabilities.
    
    Checks:
    - URL structure and scheme (https required unless allow_http=True)
    - Absence of embedded userinfo/credentials
    - Hostname presence and resolution
    - Rejection of loopback, private, link-local, multicast, and cloud metadata addresses
    
    Args:
        url: The endpoint URL to validate
        allow_http: Whether http scheme is permitted (defaults to False)
        
    Returns:
        Tuple of (is_safe: bool, reason: str)
    """
    if not url or not isinstance(url, str):
        return False, "Endpoint URL cannot be empty"
    
    url = url.strip()
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception as e:
        return False, f"Malformed URL: {e}"
    
    # 1. Validate Scheme
    allowed_schemes = ('https',) if not allow_http else ('https', 'http')
    if parsed.scheme.lower() not in allowed_schemes:
        return False, f"Unsupported scheme '{parsed.scheme}'. Only HTTPS is permitted for security."
    
    # 2. Check for embedded credentials
    if parsed.username or parsed.password:
        return False, "Embedded credentials in endpoint URLs are forbidden."
    
    # 3. Check hostname
    hostname = parsed.hostname
    if not hostname:
        return False, "Endpoint URL must include a valid hostname."
    
    hostname_lower = hostname.lower()
    
    # Block forbidden hostnames
    if hostname_lower in BLOCKED_HOSTNAMES or hostname_lower.endswith('.local') or hostname_lower.endswith('.internal'):
        return False, f"Destination hostname '{hostname}' is blocked for security reasons."
    
    # 4. Resolve hostname and validate IP addresses
    try:
        # Get address info for both IPv4 and IPv6
        addr_info = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == 'https' else 80))
    except socket.gaierror:
        return False, f"Could not resolve hostname '{hostname}'."
    except Exception as e:
        return False, f"DNS resolution error for '{hostname}': {e}"
    
    if not addr_info:
        return False, f"Could not resolve any address for hostname '{hostname}'."
    
    for family, socktype, proto, canonname, sockaddr in addr_info:
        ip_str = sockaddr[0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            return False, f"Invalid resolved IP address: {ip_str}"
        
        # Check standard properties
        if ip_obj.is_loopback:
            return False, f"Endpoint resolves to loopback address: {ip_str}"
        if ip_obj.is_private:
            return False, f"Endpoint resolves to private network address: {ip_str}"
        if ip_obj.is_link_local:
            return False, f"Endpoint resolves to link-local / cloud metadata address: {ip_str}"
        if ip_obj.is_multicast:
            return False, f"Endpoint resolves to multicast address: {ip_str}"
        if ip_obj.is_reserved:
            return False, f"Endpoint resolves to reserved address: {ip_str}"
        if ip_obj.is_unspecified:
            return False, f"Endpoint resolves to unspecified address: {ip_str}"
        
        # Check against explicit blocked network definitions
        for net in BLOCKED_NETWORKS:
            if ip_obj in net:
                return False, f"Endpoint resolves to prohibited network address: {ip_str}"
    
    return True, ""
