"""
Shared URL safety helpers for validation and scraping.
"""

import ipaddress
import socket
from urllib.parse import ParseResult, urlparse


class URLSafetyError(ValueError):
    """Raised when a URL is not safe to fetch."""


BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
}
BLOCKED_IPS = {
    "0.0.0.0",
    "169.254.169.254",
}
ALLOWED_SCHEMES = {"http", "https"}


def resolve_hostname_ips(hostname: str) -> list[str]:
    """Resolve a hostname into unique IP addresses."""
    try:
        parsed_ip = ipaddress.ip_address(hostname)
        return [str(parsed_ip)]
    except ValueError:
        pass

    try:
        address_info = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise URLSafetyError(f"Host resolution failed: {hostname}") from exc

    ips: list[str] = []
    for _, _, _, _, sockaddr in address_info:
        ip = sockaddr[0]
        if ip not in ips:
            ips.append(ip)

    if not ips:
        raise URLSafetyError(f"Host resolution failed: {hostname}")

    return ips


def _is_blocked_ip(ip_value: str) -> bool:
    ip_obj = ipaddress.ip_address(ip_value)
    return bool(
        ip_value in BLOCKED_IPS
        or ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
        or getattr(ip_obj, "is_site_local", False)
    )


def validate_safe_url_with_ips(
    url: str,
    resolve_dns: bool = True,
) -> tuple[ParseResult, list[str]]:
    """Validate that a URL is safe to fetch and optionally return resolved safe IPs."""
    if not url:
        raise URLSafetyError("Empty URL")

    parsed = urlparse(str(url).strip())
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise URLSafetyError(
            f"Unsupported URL scheme: {parsed.scheme or 'missing'}. Only http and https are allowed."
        )

    if not parsed.netloc or not parsed.hostname:
        raise URLSafetyError("Invalid URL format")

    hostname = parsed.hostname.lower()
    if hostname in BLOCKED_HOSTNAMES:
        raise URLSafetyError(f"Requests to internal hosts are not allowed: {hostname}")

    resolved_ips: list[str] = []
    if resolve_dns:
        resolved_ips = resolve_hostname_ips(hostname)
        for resolved_ip in resolved_ips:
            if _is_blocked_ip(resolved_ip):
                raise URLSafetyError(
                    f"Requests to private or internal addresses are not allowed: {hostname}"
                )
    else:
        try:
            literal_ip = ipaddress.ip_address(hostname)
        except ValueError:
            literal_ip = None
        if literal_ip is not None and _is_blocked_ip(str(literal_ip)):
            raise URLSafetyError(
                f"Requests to private or internal addresses are not allowed: {hostname}"
            )

    return parsed, resolved_ips


def validate_safe_url(url: str, resolve_dns: bool = True) -> ParseResult:
    """Validate that a URL is safe to fetch."""
    parsed, _ = validate_safe_url_with_ips(url, resolve_dns=resolve_dns)
    return parsed
