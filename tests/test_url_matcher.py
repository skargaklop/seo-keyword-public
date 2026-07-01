"""Tests for utils/url_matcher.py — pure URL/domain matching with comprehensive TLD support."""

# MODULE_CONTRACT: tests/test_url_matcher
# Purpose: Verify URL normalization, domain extraction, and match classification helpers.
# Rationale: Links URL matcher tests to their GRACE module for verification traceability.
# Dependencies: utils.url_matcher.
# Exports: pytest tests.
# LINKS: knowledge-graph.xml#MOD-009
# MODULE_MAP: tests/test_url_matcher.py
# Public Functions: pytest test functions.
# Private Helpers: none.
# Key Semantic Blocks: none.
# Critical Flows: normalize URL inputs -> extract domains -> classify source/result matches.
# Verification: verification-plan.xml#V-09-URL-MATCHER
# CHANGE_SUMMARY: Added GRACE module contract linking this test file to MOD-009.

from utils.url_matcher import (
    normalize_match_url,
    extract_match_domain,
    classify_url_match,
    build_source_url_targets,
)


# ---------------------------------------------------------------------------
# normalize_match_url
# ---------------------------------------------------------------------------

# Purpose: TestNormalizeMatchUrl implementation
class TestNormalizeMatchUrl:
    # Purpose: Test empty input
    def test_empty_input(self):
        assert normalize_match_url("") == ""

    # Purpose: Test whitespace input
    def test_whitespace_input(self):
        assert normalize_match_url("  ") == ""

    # Purpose: Test adds scheme
    def test_adds_scheme(self):
        result = normalize_match_url("example.com")
        assert result.startswith("https://")

    # Purpose: Test preserves scheme
    def test_preserves_scheme(self):
        result = normalize_match_url("http://example.com")
        assert result.startswith("http://")

    # Purpose: Test lowercase
    def test_lowercase(self):
        result = normalize_match_url("HTTPS://EXAMPLE.COM/Path")
        assert result == "https://example.com/Path"

    # Purpose: Test strips www
    def test_strips_www(self):
        result = normalize_match_url("https://www.example.com/page")
        assert "www." not in result
        assert result == "https://example.com/page"

    # Purpose: Test trailing slash removed
    def test_trailing_slash_removed(self):
        result = normalize_match_url("https://example.com/")
        assert result == "https://example.com"

    # Purpose: Test path trailing slash removed
    def test_path_trailing_slash_removed(self):
        result = normalize_match_url("https://example.com/path/")
        assert result == "https://example.com/path"

    # Purpose: Test query params removed
    def test_query_params_removed(self):
        result = normalize_match_url("https://example.com/page?foo=bar")
        assert "?" not in result
        assert result == "https://example.com/page"

    # Purpose: Test fragment removed
    def test_fragment_removed(self):
        result = normalize_match_url("https://example.com/page#section")
        assert "#" not in result
        assert result == "https://example.com/page"

    # Purpose: Test bare domain normalized
    def test_bare_domain_normalized(self):
        result = normalize_match_url("example.com")
        assert result == "https://example.com"

    # Purpose: Test bare domain with path
    def test_bare_domain_with_path(self):
        result = normalize_match_url("example.com/path/to/page")
        assert result == "https://example.com/path/to/page"


# ---------------------------------------------------------------------------
# extract_match_domain
# ---------------------------------------------------------------------------

# Purpose: TestExtractMatchDomain implementation
class TestExtractMatchDomain:
    # Purpose: Test empty input
    def test_empty_input(self):
        assert extract_match_domain("") == ""

    # Purpose: Test simple domain
    def test_simple_domain(self):
        assert extract_match_domain("https://example.com/path") == "example.com"

    # Purpose: Test subdomain
    def test_subdomain(self):
        assert extract_match_domain("https://shop.example.com") == "example.com"

    # Purpose: Test www stripped
    def test_www_stripped(self):
        assert extract_match_domain("https://www.example.com") == "example.com"

    # Purpose: Test ua two level tld
    def test_ua_two_level_tld(self):
        assert extract_match_domain("https://rozetka.com.ua") == "rozetka.com.ua"

    # Purpose: Test ua two level tld subdomain
    def test_ua_two_level_tld_subdomain(self):
        assert extract_match_domain("https://shop.rozetka.com.ua") == "rozetka.com.ua"

    # Purpose: Test org ua
    def test_org_ua(self):
        assert extract_match_domain("https://example.org.ua") == "example.org.ua"

    # Purpose: Test net ua
    def test_net_ua(self):
        assert extract_match_domain("https://example.net.ua") == "example.net.ua"

    # Purpose: Test ru 2LD behavior under the Public Suffix List.
    # NOTE: com.ru/net.ru/org.ru/pp.ru are classified as PSL *private* domains. With
    # include_psl_private_domains=True (the configured setting), they are treated as
    # suffixes, so example.com.ru -> example.com.ru (registrable), NOT com.ru. This
    # diverges from browser cookie scope but matches SEO/registrant expectations for
    # RU/UA domains and is the behavior the user explicitly requested.
    def test_ru_private_2ld_treated_as_suffixes(self):
        assert extract_match_domain("https://example.com.ru") == "example.com.ru"
        assert extract_match_domain("https://example.net.ru") == "example.net.ru"
        assert extract_match_domain("https://example.org.ru") == "example.org.ru"
        assert extract_match_domain("https://example.pp.ru") == "example.pp.ru"

    # Purpose: Test co uk
    def test_co_uk(self):
        assert extract_match_domain("https://amazon.co.uk") == "amazon.co.uk"

    # Purpose: Test co uk subdomain
    def test_co_uk_subdomain(self):
        assert extract_match_domain("https://shop.amazon.co.uk") == "amazon.co.uk"

    # Purpose: Test org uk
    def test_org_uk(self):
        assert extract_match_domain("https://example.org.uk") == "example.org.uk"

    # Purpose: Test co jp
    def test_co_jp(self):
        assert extract_match_domain("https://example.co.jp") == "example.co.jp"

    # Purpose: Test com au
    def test_com_au(self):
        assert extract_match_domain("https://example.com.au") == "example.com.au"

    # Purpose: Test ip address rejected
    # IP addresses should return the original value, not extract a domain.
    def test_ip_address_rejected(self):
        result = extract_match_domain("https://192.168.1.1")
        assert "192.168.1.1" in result

    # Purpose: Test punycode domain
    # Punycode domains should work with standard extraction.
    def test_punycode_domain(self):
        result = extract_match_domain("https://xn--e1afmkfd.xn--p1ai")
        assert "xn--e1afmkfd.xn--p1ai" == result

    # Purpose: Test bare domain
    def test_bare_domain(self):
        assert extract_match_domain("example.com") == "example.com"

    # Purpose: Test single part returns as is
    def test_single_part_returns_as_is(self):
        assert extract_match_domain("localhost") == "localhost"


# ---------------------------------------------------------------------------
# classify_url_match
# ---------------------------------------------------------------------------

# Purpose: TestClassifyUrlMatch implementation
class TestClassifyUrlMatch:
    # Purpose: Test empty result url
    def test_empty_result_url(self):
        result = classify_url_match("", ["https://example.com"])
        assert result["match_type"] == "none"

    # Purpose: Test empty source urls
    def test_empty_source_urls(self):
        result = classify_url_match("https://example.com", [])
        assert result["match_type"] == "none"

    # Purpose: Test full url match
    def test_full_url_match(self):
        result = classify_url_match(
            "https://example.com/page",
            ["https://example.com/page"],
        )
        assert result["match_type"] == "full_url"
        assert result["matched_target"] == "https://example.com/page"

    # Purpose: Test full url match scheme insensitive
    def test_full_url_match_scheme_insensitive(self):
        result = classify_url_match(
            "http://example.com/page",
            ["https://example.com/page"],
        )
        # Different schemes should not match as full_url
        assert result["match_type"] != "full_url"

    # Purpose: Test full url match trailing slash
    def test_full_url_match_trailing_slash(self):
        result = classify_url_match(
            "https://example.com/page/",
            ["https://example.com/page"],
        )
        assert result["match_type"] == "full_url"

    # Purpose: Test full url match hostname case insensitive
    # Hostname is case-insensitive; path is case-sensitive in HTTP.
    def test_full_url_match_hostname_case_insensitive(self):
        result = classify_url_match(
            "https://EXAMPLE.COM/page",
            ["https://example.com/page"],
        )
        assert result["match_type"] == "full_url"

    # Purpose: Test full url match with query
    def test_full_url_match_with_query(self):
        result = classify_url_match(
            "https://example.com/page?foo=bar",
            ["https://example.com/page"],
        )
        assert result["match_type"] == "full_url"

    # Purpose: Test domain match
    def test_domain_match(self):
        result = classify_url_match(
            "https://example.com/other-page",
            ["https://example.com/page"],
        )
        assert result["match_type"] == "domain"
        assert result["matched_domain"] == "example.com"

    # Purpose: Test domain match subdomain
    def test_domain_match_subdomain(self):
        result = classify_url_match(
            "https://shop.example.com/page",
            ["https://example.com"],
        )
        assert result["match_type"] == "domain"

    # Purpose: Test no match
    def test_no_match(self):
        result = classify_url_match(
            "https://other.com/page",
            ["https://example.com"],
        )
        assert result["match_type"] == "none"

    # Purpose: Test malicious lookalike rejected
    def test_malicious_lookalike_rejected(self):
        result = classify_url_match(
            "https://example.com.evil.com/page",
            ["https://example.com"],
        )
        assert result["match_type"] == "none"

    # Purpose: Test two level tld domain match
    def test_two_level_tld_domain_match(self):
        result = classify_url_match(
            "https://rozetka.com.ua/some-product",
            ["https://rozetka.com.ua"],
        )
        assert result["match_type"] == "domain"

    # Purpose: Test two level tld no match
    def test_two_level_tld_no_match(self):
        result = classify_url_match(
            "https://other.com.ua/page",
            ["https://rozetka.com.ua"],
        )
        assert result["match_type"] == "none"

    # Purpose: Test uk domain match
    def test_uk_domain_match(self):
        result = classify_url_match(
            "https://amazon.co.uk/product",
            ["https://amazon.co.uk"],
        )
        assert result["match_type"] == "domain"

    # Purpose: Test www stripped before match
    def test_www_stripped_before_match(self):
        result = classify_url_match(
            "https://www.example.com/page",
            ["https://example.com"],
        )
        assert result["match_type"] == "domain"


# ---------------------------------------------------------------------------
# build_source_url_targets
# ---------------------------------------------------------------------------

# Purpose: TestBuildSourceUrlTargets implementation
class TestBuildSourceUrlTargets:
    # Purpose: Test empty input
    def test_empty_input(self):
        assert build_source_url_targets([]) == []

    # Purpose: Test single url
    def test_single_url(self):
        targets = build_source_url_targets(["https://example.com"])
        assert len(targets) == 1
        assert targets[0]["original"] == "https://example.com"
        assert targets[0]["normalized_url"] == "https://example.com"
        assert targets[0]["domain"] == "example.com"

    # Purpose: Test deduplication
    def test_deduplication(self):
        targets = build_source_url_targets([
            "https://example.com",
            "https://example.com/",
        ])
        assert len(targets) == 1

    # Purpose: Test multiple urls
    def test_multiple_urls(self):
        targets = build_source_url_targets([
            "https://example.com",
            "https://other.com",
        ])
        assert len(targets) == 2
        domains = {t["domain"] for t in targets}
        assert domains == {"example.com", "other.com"}

    # Purpose: Test two level tld domain
    def test_two_level_tld_domain(self):
        targets = build_source_url_targets(["https://rozetka.com.ua"])
        assert targets[0]["domain"] == "rozetka.com.ua"

    # Purpose: Test normalization applied
    def test_normalization_applied(self):
        targets = build_source_url_targets(["https://WWW.EXAMPLE.COM/"])
        assert targets[0]["normalized_url"] == "https://example.com"
        assert targets[0]["domain"] == "example.com"
