# MODULE_CONTRACT: utils/url_matcher
# Purpose: Pure URL/domain matching helper with registrable-domain extraction for SERP highlight classification
# Rationale: Keeps URL matching logic testable, separate from pipeline and UI concerns
# Dependencies: urllib.parse, re (stdlib); tldextract (via utils.domain) for Public Suffix List resolution
# Exports: normalize_match_url, extract_match_domain, classify_url_match, build_source_url_targets
# LINKS: PLAN 09-04 Task 1, development-plan.xml#MOD-009, utils/domain.py#registrable_domain
# MODULE_MAP: utils/url_matcher.py
# Public Functions: normalize_match_url, extract_match_domain, classify_url_match, build_source_url_targets
# Private Helpers: _parse_hostname, _is_ip_address, _strip_www
# Key Semantic Blocks: block_url_normalize_input, block_url_extract_domain, block_url_classify_match, block_url_build_target
# Critical Flows: source URLs -> normalize -> build targets -> classify SERP results -> match type
# Verification: python -m pytest tests/test_url_matcher.py -q
# CHANGE_SUMMARY: extract_match_domain now delegates registrable-domain resolution to utils.domain (PSL-backed),
#   replacing the hardcoded TWO_LEVEL_TLDS heuristic that collapsed *.kiev.ua sites into the "kiev.ua" zone.

"""Pure URL/domain match helper with registrable-domain extraction.

Provides normalization, domain extraction, and match classification
for SERP URL highlighting. Registrable-domain resolution delegates to
``utils.domain`` (Public Suffix List via tldextract).
"""

import re
from typing import Dict, List, Optional
from urllib.parse import urlparse

from utils.domain import registrable_domain


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
# Purpose: Extract the registrable domain (eTLD+1) from a URL or host string
# Input: value (str) - URL or domain string
# Output: str - registrable domain (e.g., 'rozetka.com.ua', 'mobile.kiev.ua', 'example.com'),
#   the input for IP addresses, the bare host for single-label hosts, or '' for empty input
# Side Effects: (none externally; delegates to utils.domain's cached offline PSL lookup)
# Business Rules: Delegates to utils.domain.registrable_domain (Public Suffix List via tldextract)
#   for all multi-label suffix resolution, including multi-label zones like kiev.ua. Preserves the
#   documented IP-passthrough and single-label-host-passthrough contracts of the prior heuristic.
# Failure Modes: Returns the original input for IP addresses; '' for empty input; never raises
# LINKS: PLAN 09-04 Task 1, utils/domain.py#registrable_domain
def extract_match_domain(value: str) -> str:
    if not value or not str(value).strip():
        return ""
    hostname = _parse_hostname(value)
    if not hostname:
        return value.strip()

    # Reject IP addresses — pass the original input through (documented contract).
    if _is_ip_address(hostname):
        return value.strip()

    # Delegate multi-label / public-suffix resolution to the PSL-backed helper.
    registered = registrable_domain(hostname)
    if registered:
        return registered

    # Single-label host (e.g. 'localhost') or an unresolvable value: return the bare host.
    return _strip_www(hostname)


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