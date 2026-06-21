# MODULE_CONTRACT: utils/url_safety
# Purpose: Shared URL safety helpers for validation and scraping.
# Rationale: Keep the module boundary explicit for GRACE adoption and review.
# Dependencies: ipaddress, socket, urllib.parse
# Exports: URLSafetyError, BLOCKED_HOSTNAMES, BLOCKED_IPS, ALLOWED_SCHEMES, resolve_hostname_ips, validate_safe_url_with_ips, validate_safe_url
# LINKS: requirements.xml#UC-001, development-plan.xml#MOD-001
# MODULE_MAP: utils/url_safety.py
# Public Functions: exported callables and classes defined in this module
# Private Helpers: internal helpers and private methods defined in this module
# Key Semantic Blocks: main workflow paths and state transitions in this module
# Critical Flows: preserve existing runtime behavior and integrations
# Verification: python -m py_compile, python -m ruff check ., python -m pytest -q
# CHANGE_SUMMARY: Added file-local module metadata and declaration contracts.

import ipaddress
import socket
from urllib.parse import ParseResult, urlparse

# CLASS_CONTRACT: URLSafetyError
# Purpose: Signal blocked or unresolved URLs before network fetching.
# LINKS: requirements.xml#UC-001
class URLSafetyError(ValueError):
    pass

BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
}
BLOCKED_IPS = {
    "0.0.0.0",
    "169.254.169.254",
}
ALLOWED_SCHEMES = {"http", "https"}
# FUNCTION_CONTRACT: resolve_hostname_ips
# Purpose: Implement the resolve hostname ips helper for this module.
# Input: hostname (str)
# Output: list[str]
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def resolve_hostname_ips(hostname: str) -> list[str]:
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
# FUNCTION_CONTRACT: _is_blocked_ip
# Purpose: Implement the  is blocked ip helper for this module.
# Input: ip_value (str)
# Output: bool
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
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
# FUNCTION_CONTRACT: validate_safe_url_with_ips
# Purpose: Implement the validate safe url with ips helper for this module.
# Input: url (str), resolve_dns (bool = True)
# Output: tuple[ParseResult, list[str]]
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def validate_safe_url_with_ips(
    url: str,
    resolve_dns: bool = True,
) -> tuple[ParseResult, list[str]]:
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
# FUNCTION_CONTRACT: validate_safe_url
# Purpose: Implement the validate safe url helper for this module.
# Input: url (str), resolve_dns (bool = True)
# Output: ParseResult
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def validate_safe_url(url: str, resolve_dns: bool = True) -> ParseResult:
    parsed, _ = validate_safe_url_with_ips(url, resolve_dns=resolve_dns)
    return parsed
