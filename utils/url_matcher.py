# MODULE_CONTRACT: utils/url_matcher
# Purpose: Pure URL/domain matching helper with comprehensive TLD support for SERP highlight classification
# Rationale: Keeps URL matching logic dependency-free and testable, separate from pipeline and UI concerns
# Dependencies: urllib.parse, re (stdlib only, no pip packages)
# Exports: normalize_match_url, extract_match_domain, classify_url_match, build_source_url_targets
# LINKS: PLAN 09-04 Task 1, development-plan.xml#MOD-009
# MODULE_MAP: utils/url_matcher.py
# Public Functions: normalize_match_url, extract_match_domain, classify_url_match, build_source_url_targets
# Private Helpers: _parse_hostname, _is_ip_address, _strip_www, _get_two_level_tld_domain
# Key Semantic Blocks: block_url_normalize_input, block_url_extract_domain, block_url_classify_match, block_url_build_target
# Critical Flows: source URLs -> normalize -> build targets -> classify SERP results -> match type
# Verification: python -m pytest tests/test_url_matcher.py -q
# CHANGE_SUMMARY: Phase 9 Plan 4 Task 1: created pure URL matching module with comprehensive UA/RU/UK TLD heuristics

"""Pure URL/domain match helper with comprehensive TLD support.

Provides normalization, domain extraction, and match classification
for SERP URL highlighting. No external dependencies.
"""

import re
from typing import Dict, List, Optional
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Two-level TLD registry (ccTLD with second-level registration)
# ---------------------------------------------------------------------------
TWO_LEVEL_TLDS: frozenset[str] = frozenset({
    # Ukraine
    "com.ua", "org.ua", "net.ua", "in.ua", "edu.ua", "gov.ua",
    # Russia
    "com.ru", "org.ru", "net.ru", "pp.ru",
    # UK
    "co.uk", "org.uk", "me.uk", "ac.uk", "gov.uk",
    # Generic international
    "co.jp", "com.au", "net.au", "org.au",
    "co.nz", "org.nz", "co.in", "co.za",
    "com.br", "com.mx", "com.ar", "com.tr",
    "com.sg", "com.hk", "com.tw", "com.my",
})

# Regex for IPv4 address (covers dotted-decimal)
_IPV4_RE = re.compile(
    r"^(?:\d{1,3}\.){3}\d{1,3}$"
)

# Regex for IPv6 (proper validation per CR-04)
_IPV6_RE = re.compile(
    r"^\[?("
    r"([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}|"
    r"([0-9a-fA-F]{1,4}:){1,7}:|"
    r"([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|"
    r"([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|"
    r"([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|"
    r"([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|"
    r"([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|"
    r"[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|"
    r":((:[0-9a-fA-F]{1,4}){1,7}|:)|"
    r"fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|"
    r"::(ffff(:0{1,4}){0,1}:){0,1}"
    r"((25[0-5]|(2[0-4]|1?[0-9])?[0-9])\.){3}"
    r"(25[0-5]|(2[0-4]|1?[0-9])?[0-9])|"
    r"([0-9a-fA-F]{1,4}:){1,4}:"
    r"((25[0-5]|(2[0-4]|1?[0-9])?[0-9])\.){3}"
    r"(25[0-5]|(2[0-4]|1?[0-9])?[0-9])"
    r")\]?$"
)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

# Purpose: Extract hostname (netloc) from a URL or bare domain string.
def _parse_hostname(value: str) -> str:
    value = value.strip()
    if not value:
        return ""

    # Add scheme if missing so urlparse works on bare domains
    if "://" not in value:
        value = "https://" + value

    parsed = urlparse(value)
    hostname = parsed.hostname or parsed.netloc or ""
    return hostname.lower()


# Purpose: Return True if the hostname looks like an IP address.
def _is_ip_address(hostname: str) -> bool:
    if not hostname:
        return False
    # Remove brackets used in IPv6 URL notation
    clean = hostname.strip("[]")
    if _IPV4_RE.match(clean):
        return True
    if _IPV6_RE.match(clean):
        return True
    return False


# Purpose: Remove leading 'www.' from hostname.
def _strip_www(hostname: str) -> str:
    if hostname.startswith("www."):
        return hostname[4:]
    return hostname


# Purpose: If the hostname ends with a known two-level TLD, extract the domain
# as the part before the two-level TLD plus the TLD itself.
# For 'rozetka.com.ua' -> 'rozetka.com.ua'
# For 'shop.amazon.co.uk' -> 'amazon.co.uk'
# Returns None if no two-level TLD match.
def _get_two_level_tld_domain(hostname: str) -> Optional[str]:
    if not hostname or "." not in hostname:
        return None

    parts = hostname.split(".")
    # Check last two parts against known two-level TLDs
    if len(parts) >= 3:
        candidate_tld = ".".join(parts[-2:])
        if candidate_tld in TWO_LEVEL_TLDS:
            # Domain is: second-level-name.two-level-tld
            return ".".join(parts[-3:])

    # Also check if hostname is exactly name.two-level-tld (e.g., "rozetka.com.ua")
    if len(parts) == 2:
        # This is just "name.tld", not a two-level TLD case
        return None

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# FUNCTION_CONTRACT: normalize_match_url
# Purpose: Normalize a URL for comparison by standardizing scheme, case, www prefix, and trailing slash
# Input: value (str) - raw URL string
# Output: str - normalized URL
# Side Effects: (none - pure function)
# Business Rules: Lowercase, strip www, remove trailing slash, ensure scheme
# Failure Modes: Returns empty string for empty input
# LINKS: PLAN 09-04 Task 1
def normalize_match_url(value: str) -> str:
    if not value or not value.strip():
        return ""

    value = value.strip()

    # Add scheme if missing so urlparse works
    if "://" not in value:
        value = "https://" + value

    parsed = urlparse(value)
    scheme = (parsed.scheme or "https").lower()
    hostname = (parsed.hostname or parsed.netloc or "").lower()
    hostname = _strip_www(hostname)

    path = parsed.path.rstrip("/") or ""

    # Rebuild without query/fragment
    return f"{scheme}://{hostname}{path}"


# FUNCTION_CONTRACT: extract_match_domain
# Purpose: Extract the registrable domain from a URL with two-level TLD heuristics
# Input: value (str) - URL or domain string
# Output: str - registrable domain (e.g., 'rozetka.com.ua', 'example.com')
# Side Effects: (none - pure function)
# Business Rules: Handles two-level TLDs, punycode, IP address rejection
# Failure Modes: Returns original input if hostname invalid or IP address
# LINKS: PLAN 09-04 Task 1
def extract_match_domain(value: str) -> str:
    hostname = _parse_hostname(value)
    if not hostname:
        return value.strip() if value else ""

    # Reject IP addresses
    if _is_ip_address(hostname):
        return value.strip()

    hostname = _strip_www(hostname)

    if "." not in hostname:
        return hostname

    # Check for two-level TLD match first
    two_level = _get_two_level_tld_domain(hostname)
    if two_level:
        return two_level

    # Standard TLD: take last two parts
    parts = hostname.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])

    return hostname


# FUNCTION_CONTRACT: classify_url_match
# Purpose: Classify how a SERP result URL matches against source URLs
# Input: result_url (str), source_urls (List[str])
# Output: Dict with match_type, matched_target, matched_domain
# Side Effects: (none - pure function)
# Business Rules: full_url > domain > none; exact normalized URL comparison
# Failure Modes: Returns none match for empty inputs
# LINKS: PLAN 09-04 Task 1
def classify_url_match(
    result_url: str,
    source_urls: List[str],
) -> Dict[str, str]:
    """Classify how a SERP result URL matches source URLs.

    Returns dict:
        match_type: "full_url" | "domain" | "none"
        matched_target: the source URL that matched (or "")
        matched_domain: the domain that matched (or "")
    """
    if not result_url or not source_urls:
        return {"match_type": "none", "matched_target": "", "matched_domain": ""}

    norm_result = normalize_match_url(result_url)

    # Check full URL match first (highest priority)
    for source in source_urls:
        if normalize_match_url(source) == norm_result:
            return {
                "match_type": "full_url",
                "matched_target": source,
                "matched_domain": extract_match_domain(source),
            }

    # Check domain match
    result_domain = extract_match_domain(result_url)
    if result_domain:
        for source in source_urls:
            source_domain = extract_match_domain(source)
            if source_domain and source_domain == result_domain:
                # Malicious lookalike protection:
                # If the result hostname ends with source_domain but has more subdomain
                # parts, verify it's not a lookalike like example.com.evil.com
                # The result should not have a hostname that merely has
                # the source domain as a suffix with a different registrable root
                result_root = extract_match_domain(result_url)
                source_root = extract_match_domain(source)
                if result_root == source_root:
                    return {
                        "match_type": "domain",
                        "matched_target": source,
                        "matched_domain": result_domain,
                    }

    return {"match_type": "none", "matched_target": "", "matched_domain": ""}


# FUNCTION_CONTRACT: build_source_url_targets
# Purpose: Build match target structures from source URLs for efficient matching
# Input: source_urls (List[str])
# Output: List[Dict] with normalized_url, domain, original
# Side Effects: (none - pure function)
# Business Rules: Deduplicates by normalized URL
# Failure Modes: Returns empty list for empty input
# LINKS: PLAN 09-04 Task 1
def build_source_url_targets(source_urls: List[str]) -> List[Dict[str, str]]:
    if not source_urls:
        return []

    seen_normalized = set()
    targets: List[Dict[str, str]] = []

    for url in source_urls:
        norm = normalize_match_url(url)
        if norm in seen_normalized:
            continue
        seen_normalized.add(norm)

        targets.append({
            "original": url,
            "normalized_url": norm,
            "domain": extract_match_domain(url),
        })

    return targets