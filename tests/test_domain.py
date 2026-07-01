"""Tests for utils/domain.py — registrable-domain extraction backed by the Public Suffix List."""

# MODULE_CONTRACT: tests/test_domain
# Purpose: Verify registrable_domain() resolves the registrable (eTLD+1) domain for any host/URL
#   using the Public Suffix List (via tldextract), with no network access and graceful fallbacks
#   for IP addresses, bare hosts, and empty input.
# Rationale: Locks the correct behavior that the old hardcoded TWO_LEVEL_TLDS heuristic got wrong
#   (e.g. *.kiev.ua collapsing to the "kiev.ua" zone, subdomains like www.rozetka.com.ua -> com.ua).
# Dependencies: utils.domain (tldextract-backed).
# Exports: pytest test functions.
# LINKS: knowledge-graph.xml#MOD-009
# MODULE_MAP: tests/test_domain.py
# Public Functions: pytest test functions.
# Private Helpers: none.
# Key Semantic Blocks: none.
# Critical Flows: URL/host input -> tldextract PSL lookup -> registrable domain or empty string.
# Verification: verification-plan.xml#V-09-URL-MATCHER
# CHANGE_SUMMARY: RED phase — failing tests written before registrable_domain exists.

import pytest

from utils.domain import registrable_domain


# ---------------------------------------------------------------------------
# registrable_domain — multi-label public suffixes (the core regression)
# ---------------------------------------------------------------------------


class TestRegistrableDomain:
    # Purpose: *.kiev.ua sites must keep their distinct registrable names, NOT collapse to the
    # "kiev.ua" zone. This is the exact bug that surfaced in SERP domains.
    @pytest.mark.parametrize("url,expected", [
        ("https://www.mobile.kiev.ua/catalog", "mobile.kiev.ua"),
        ("https://mobile.kiev.ua", "mobile.kiev.ua"),
        ("https://fixit.kiev.ua/services", "fixit.kiev.ua"),
        ("https://sub.site.kiev.ua", "site.kiev.ua"),
    ])
    def test_kiev_ua_sites_keep_registrable_name(self, url: str, expected: str) -> None:
        assert registrable_domain(url) == expected

    # Purpose: a public suffix on its own (the zone, no registrable label) yields empty —
    # "kiev.ua" is a zone, never a domain.
    @pytest.mark.parametrize("url", [
        "https://kiev.ua",
        "kiev.ua",
    ])
    def test_public_suffix_alone_is_empty(self, url: str) -> None:
        assert registrable_domain(url) == ""

    # Purpose: known multi-label suffixes that the old hardcoded list happened to cover must
    # still resolve correctly after the migration.
    @pytest.mark.parametrize("url,expected", [
        ("https://www.rozetka.com.ua", "rozetka.com.ua"),
        ("https://rozetka.com.ua", "rozetka.com.ua"),
        ("https://shop.amazon.co.uk", "amazon.co.uk"),
    ])
    def test_listed_multi_label_suffixes(self, url: str, expected: str) -> None:
        assert registrable_domain(url) == expected

    # Purpose: PSL *private* domains (com.ru/net.ru/org.ru/pp.ru — MSK-IX registry) are treated
    # as suffixes because include_psl_private_domains=True. So a site under them keeps its
    # registrable label rather than collapsing to the two-label suffix. This diverges from
    # browser cookie scope (public-only) but matches SEO/registrant expectations.
    @pytest.mark.parametrize("url,expected", [
        ("https://example.com.ru", "example.com.ru"),
        ("https://www.example.com.ru", "example.com.ru"),
        ("https://example.net.ru", "example.net.ru"),
        ("https://example.org.ru", "example.org.ru"),
        ("https://example.pp.ru", "example.pp.ru"),
        ("https://shop.example.pp.ru", "example.pp.ru"),
    ])
    def test_psl_private_domains_treated_as_suffixes(self, url: str, expected: str) -> None:
        assert registrable_domain(url) == expected

    # Purpose: standard single-label suffixes resolve to the last two labels.
    @pytest.mark.parametrize("url,expected", [
        ("https://example.com", "example.com"),
        ("https://www.example.com/path", "example.com"),
        ("https://maps.google.com", "google.com"),
        ("https://sub.sub.example.org/page?q=1", "example.org"),
    ])
    def test_standard_suffixes(self, url: str, expected: str) -> None:
        assert registrable_domain(url) == expected

    # Purpose: www and other subdomains are stripped from the registrable domain.
    def test_strips_subdomains(self) -> None:
        assert registrable_domain("https://www.blog.example.com") == "example.com"
        assert registrable_domain("https://api.v2.service.example.com") == "example.com"

    # Purpose: bare domain strings (no scheme) are accepted.
    def test_bare_domain_without_scheme(self) -> None:
        assert registrable_domain("mobile.kiev.ua") == "mobile.kiev.ua"
        assert registrable_domain("www.example.com") == "example.com"

    # Purpose: IP addresses are passed through unchanged (no registrable domain exists).
    @pytest.mark.parametrize("url", [
        "https://192.168.1.1/path",
        "http://10.0.0.1",
        "https://[::1]/",  # IPv6 loopback
    ])
    def test_ip_addresses_passthrough(self, url: str) -> None:
        result = registrable_domain(url)
        assert result and ("192.168.1.1" in result or "10.0.0.1" in result or "::1" in result or result == url)

    # Purpose: single-label hosts (localhost / no dot) return the host or empty — never raise.
    @pytest.mark.parametrize("url", ["localhost", "intranet", "https://intranet/"])
    def test_single_label_host_no_crash(self, url: str) -> None:
        result = registrable_domain(url)
        assert isinstance(result, str)

    # Purpose: empty / whitespace input never raises and returns "".
    @pytest.mark.parametrize("url", ["", "   ", None])
    def test_empty_input(self, url) -> None:
        assert registrable_domain(url) == ""

    # Purpose: the function never raises on garbage input — robustness contract.
    @pytest.mark.parametrize("url", ["not a url", "://broken", "ftp://example.com", "example."])
    def test_never_raises_on_garbage(self, url: str) -> None:
        assert isinstance(registrable_domain(url), str)

    # Purpose: idempotent — feeding the output back in returns the same domain.
    def test_idempotent(self) -> None:
        d = registrable_domain("https://www.mobile.kiev.ua/catalog")
        assert registrable_domain(d) == d

    # Purpose: the extractor must NOT touch the network (desktop app, offline-capable).
    def test_no_network_dependency(self, monkeypatch) -> None:
        def _no_network(*args, **kwargs):
            raise AssertionError("registrable_domain must not perform network I/O")
        import urllib.request
        monkeypatch.setattr(urllib.request, "urlopen", _no_network)
        # Should resolve purely from the bundled PSL snapshot.
        assert registrable_domain("https://www.mobile.kiev.ua") == "mobile.kiev.ua"
