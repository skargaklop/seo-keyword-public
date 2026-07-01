# MODULE_CONTRACT: utils/domain
# Purpose: Registrable-domain (eTLD+1) extraction backed by the Public Suffix List via tldextract
# Rationale: A single source of truth for "what is the registrable domain of this host/URL", replacing
#   the prior hardcoded TWO_LEVEL_TLDS heuristic that collapsed *.kiev.ua sites into the "kiev.ua" zone
#   and mishandled other multi-label suffixes. PSL is the only correct model; label-counting is not.
# Dependencies: tldextract (Public Suffix List), urllib.parse (stdlib)
# Exports: registrable_domain
# LINKS: development-plan.xml#MOD-009, utils/url_matcher.py#extract_match_domain, utils/crawler.py#_registrable_domain
# MODULE_MAP: utils/domain.py
# Public Functions: registrable_domain
# Private Helpers: _parse_hostname, _is_ip_address, _normalize_host_input
# Key Semantic Blocks: block_domain_tldextract_instance, block_domain_registrable_lookup
# Critical Flows: host/URL input -> normalize -> tldextract PSL snapshot lookup -> eTLD+1 or empty
# Verification: python -m pytest tests/test_domain.py -q
# CHANGE_SUMMARY: Created tldextract-backed registrable_domain as the shared eTLD+1 source of truth.

"""Registrable-domain extraction backed by the Public Suffix List.

Exposes ``registrable_domain`` — the single source of truth for resolving the
registrable (eTLD+1) domain of any host or URL, using tldextract's bundled
Public Suffix List snapshot with no network access.

This replaces the former hardcoded two-level-TLD heuristics in url_matcher.py
and crawler.py, which could not represent real public-suffix rules and collapsed
multi-label-suffix hosts (e.g. ``*.kiev.ua``) into the bare zone.
"""

import re
from functools import lru_cache
from typing import Optional
from urllib.parse import urlparse

import tldextract


# ---------------------------------------------------------------------------
# SEMANTIC_BLOCK: block_domain_tldextract_instance
# A snapshot-only extractor: suffix_list_urls=() disables all network fetches so
# resolution is fully offline (essential for a desktop app and for deterministic
# tests). cache_dir=None skips on-disk cache writes; the bundled PSL snapshot is
# authoritative. The instance is created once and reused.
#
# include_psl_private_domains=True: the PSL "private domains" section lists
# corporate/cloud suffixes (e.g. com.ru, net.ru, org.ru, pp.ru registered by
# MSK-IX, plus s3.amazonaws.com, herokuapp.com, etc.). With this on, those are
# treated as suffixes, so example.com.ru is registrable as "example.com.ru"
# rather than collapsing to "com.ru". This diverges from browser cookie scope
# (which uses only the public section) but matches how SEO/registrants think
# about RU/UA domains, and is the behavior the user explicitly requested.
# ---------------------------------------------------------------------------

_TLD_EXTRACT = tldextract.TLDExtract(
    suffix_list_urls=(),
    cache_dir=None,
    include_psl_private_domains=True,
)


# ---------------------------------------------------------------------------
# SEMANTIC_BLOCK: block_domain_registrable_lookup
# Helpers + public registrable_domain. IP addresses and single-label hosts pass
# through; public suffixes with no registrable label yield "".
# ---------------------------------------------------------------------------

_IPV4_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")


def _is_ip_address(hostname: str) -> bool:
    """True for a dotted-decimal IPv4 or a bracketed/bare IPv6 host."""
    if not hostname:
        return False
    h = hostname.strip().strip("[]")
    if _IPV4_RE.match(h):
        return True
    # Bare IPv6 (contains ':' and only hex/colon/dot chars) — conservative match.
    if ":" in h and re.match(r"^[0-9a-fA-F:.]+$", h):
        return True
    return False


def _normalize_host_input(value: str) -> str:
    """Reduce a raw URL/host string to a bare hostname (lowercased), or '' for garbage."""
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    # Add a scheme so urlparse reliably isolates the host for bare-domain inputs.
    candidate = text if "://" in text else f"https://{text}"
    parsed = urlparse(candidate)
    host = (parsed.hostname or parsed.netloc or "").lower()
    # urlparse leaves a trailing port on netloc; hostname already strips it. Prefer hostname.
    return host


@lru_cache(maxsize=4096)
def _registrable_domain_cached(host: str) -> str:
    """Cached lookup for a normalized hostname. Never raises; returns '' on any failure."""
    if not host:
        return ""
    if _is_ip_address(host):
        return host  # IP addresses have no registrable domain — pass through.
    try:
        extraction = _TLD_EXTRACT(host)
    except Exception:
        return ""
    registered = extraction.top_domain_under_public_suffix
    return registered or ""


# FUNCTION_CONTRACT: registrable_domain
# Purpose: Resolve the registrable (eTLD+1) domain of a URL or host string using the Public Suffix List
# Input: value (str | None) — full URL or bare hostname/domain (scheme optional)
# Output: str — the registrable domain (e.g. 'mobile.kiev.ua', 'rozetka.com.ua', 'example.com'),
#   the IP literal for IP inputs, or '' for empty input / bare public suffix / unresolvable hosts
# Side Effects: None externally observable; uses an in-memory LRU cache and the bundled offline PSL snapshot
# Business Rules: Offline-only (never performs network I/O); never raises; subdomains stripped; a public
#   suffix on its own (e.g. 'kiev.ua') returns '' because it is a zone, not a registrable domain
# Failure Modes: Empty input, single-label hosts, and unparseable values return '' without raising
# LINKS: development-plan.xml#MOD-009, utils/url_matcher.py#extract_match_domain, utils/crawler.py#_registrable_domain
def registrable_domain(value: Optional[str]) -> str:
    host = _normalize_host_input(value)
    if not host:
        return ""
    return _registrable_domain_cached(host)
