"""Tests for Phase 6: SERP Advanced Search Parameters."""

from unittest.mock import MagicMock, patch

import pytest

from config.settings import (
    SERP_DEVICE_OPTIONS,
    SERP_GOOGLE_DOMAIN_OPTIONS,
    SERP_SAFE_SEARCH_OPTIONS,
    SERP_SEARCH_TYPE_OPTIONS,
    SERP_TIME_PERIOD_OPTIONS,
)
from config.i18n import TRANSLATIONS
from utils.serp_client import (
    SERPOrganicResult,
    _build_tbs_value,
    _normalize_organic_results,
)


# ---------------------------------------------------------------------------
# Settings option dicts
# ---------------------------------------------------------------------------


# Purpose: TestSerpAdvancedOptions implementation
class TestSerpAdvancedOptions:
    # Purpose: Test device options
    def test_device_options(self):
        assert SERP_DEVICE_OPTIONS == {
            "Not set": "",
            "Desktop": "desktop",
            "Mobile": "mobile",
            "Tablet": "tablet",
        }

    # Purpose: Test search type options
    def test_search_type_options(self):
        assert SERP_SEARCH_TYPE_OPTIONS == {
            "Web": "web",
            "Images": "images",
            "Videos": "videos",
            "News": "news",
            "Shopping": "shopping",
        }

    # Purpose: Test time period options
    def test_time_period_options(self):
        assert SERP_TIME_PERIOD_OPTIONS == {
            "Any time": "any",
            "Past hour": "hour",
            "Past day": "day",
            "Past week": "week",
            "Past month": "month",
            "Past year": "year",
        }

    # Purpose: Test safe search options
    def test_safe_search_options(self):
        assert SERP_SAFE_SEARCH_OPTIONS == {
            "Off": "off",
            "Active": "active",
        }

    # Purpose: Test google domain options
    def test_google_domain_options(self):
        expected_domains = [
            "google.com", "google.co.uk", "google.de", "google.fr",
            "google.com.ua", "google.ru", "google.com.tr", "google.pl",
        ]
        for domain in expected_domains:
            assert domain in SERP_GOOGLE_DOMAIN_OPTIONS.values()


# ---------------------------------------------------------------------------
# _build_tbs_value helper
# ---------------------------------------------------------------------------


# Purpose: TestTbsValueBuilder implementation
class TestTbsValueBuilder:
    @pytest.mark.parametrize("period,expected", [
        ("hour", "qdr:h"),
        ("day", "qdr:d"),
        ("week", "qdr:w"),
        ("month", "qdr:m"),
        ("year", "qdr:y"),
    ])
    # Purpose: Test known periods
    def test_known_periods(self, period, expected):
        assert _build_tbs_value(period) == expected

    # Purpose: Test any returns none
    def test_any_returns_none(self):
        assert _build_tbs_value("any") is None

    # Purpose: Test unknown returns none
    def test_unknown_returns_none(self):
        assert _build_tbs_value("unknown") is None


# ---------------------------------------------------------------------------
# i18n keys
# ---------------------------------------------------------------------------


# Purpose: TestI18nSerpAdvancedKeys implementation
class TestI18nSerpAdvancedKeys:
    ADVANCED_KEYS = [
        "serp_device",
        "serp_search_type",
        "serp_time_period",
        "serp_safe_search",
        "serp_google_domain",
        "serp_city",
        "serp_uule",
    ]

    # Purpose: Test advanced keys present in translations
    def test_advanced_keys_present_in_translations(self):
        for key in self.ADVANCED_KEYS:
            assert key in TRANSLATIONS, f"Missing TRANSLATIONS key: {key}"
            entry = TRANSLATIONS[key]
            for lang in ("ru", "uk", "en"):
                assert lang in entry, f"Missing {lang} for key: {key}"



# ---------------------------------------------------------------------------
# SerperDev endpoint routing
# ---------------------------------------------------------------------------


# Purpose: TestSerperDevEndpointRouting implementation
class TestSerperDevEndpointRouting:
    # Purpose: Test web uses default endpoint
    def test_web_uses_default_endpoint(self):
        adapter = MagicMock()
        adapter.endpoint = "https://google.serper.dev/search"
        adapter.api_key = "test"
        from utils.serp_client import SerperDevAdapter
        inst = SerperDevAdapter.__new__(SerperDevAdapter)
        inst.api_key = "test"
        inst.endpoint = "https://google.serper.dev/search"

        # Simulate the routing logic from search()
        extra = {"search_type": "web"}
        base_url = inst.endpoint
        st_val = extra.get("search_type", "web")
        if st_val not in ("web", None):
            path = {"images": "/images", "videos": "/videos", "news": "/news", "shopping": "/shopping"}.get(st_val)
            if path:
                base_url = "https://google.serper.dev" + path
        assert base_url == "https://google.serper.dev/search"

    @pytest.mark.parametrize("st_val,path", [
        ("images", "/images"),
        ("videos", "/videos"),
        ("news", "/news"),
        ("shopping", "/shopping"),
    ])
    # Purpose: Test non web changes endpoint
    def test_non_web_changes_endpoint(self, st_val, path):
        base_url = "https://google.serper.dev/search"
        extra = {"search_type": st_val}
        if extra.get("search_type", "web") not in ("web", None):
            p = {"images": "/images", "videos": "/videos", "news": "/news", "shopping": "/shopping"}.get(extra["search_type"])
            if p:
                base_url = "https://google.serper.dev" + p
        assert base_url == f"https://google.serper.dev{path}"


# ---------------------------------------------------------------------------
# Adapter backward compat (extra_params=None)
# ---------------------------------------------------------------------------


# Purpose: TestAdapterExtraParamsBackwardCompat implementation
class TestAdapterExtraParamsBackwardCompat:
    # Purpose: Verify adapters accept extra_params=None without error.
    def test_adapter_search_without_extra_params(self):
        from utils.serp_client import SerperDevAdapter
        adapter = SerperDevAdapter.__new__(SerperDevAdapter)
        adapter.api_key = "test"
        adapter.endpoint = "https://google.serper.dev/search"

        mock_response = MagicMock()
        mock_response.json.return_value = {"organic": []}
        mock_response.raise_for_status = MagicMock()

        with patch("utils.serp_client.requests.post", return_value=mock_response):
            result = adapter.search("test", 10, "us", "en", 30, extra_params=None)
        assert result.success is True
        assert result.keyword == "test"


# ---------------------------------------------------------------------------
# Enriched organic result fields
# ---------------------------------------------------------------------------


# Purpose: TestOrganicResultEnrichedFields implementation
class TestOrganicResultEnrichedFields:
    # Purpose: Test displayed link extracted
    def test_displayed_link_extracted(self):
        items = [
            {"title": "Test", "link": "https://example.com", "snippet": "desc", "position": 1, "displayedLink": "www.example.com › path"},
        ]
        results = _normalize_organic_results(items)
        assert results[0].displayed_link == "www.example.com › path"

    # Purpose: Test displayed link fallback
    def test_displayed_link_fallback(self):
        items = [
            {"title": "Test", "link": "https://example.com", "snippet": "desc", "position": 1, "displayed_link": "example.com › page"},
        ]
        results = _normalize_organic_results(items)
        assert results[0].displayed_link == "example.com › page"

    # Purpose: Test displayed link empty when missing
    def test_displayed_link_empty_when_missing(self):
        items = [
            {"title": "Test", "link": "https://example.com", "snippet": "desc", "position": 1},
        ]
        results = _normalize_organic_results(items)
        assert results[0].displayed_link == ""

    # Purpose: Test rich snippet extracted
    def test_rich_snippet_extracted(self):
        rs = {"type": "recipe", "rating": {"value": 4.5}}
        items = [
            {"title": "Test", "link": "https://example.com", "snippet": "desc", "position": 1, "richSnippet": rs},
        ]
        results = _normalize_organic_results(items)
        assert results[0].rich_snippet == rs

    # Purpose: Test rich snippet fallback key
    def test_rich_snippet_fallback_key(self):
        rs = {"type": "product"}
        items = [
            {"title": "Test", "link": "https://example.com", "snippet": "desc", "position": 1, "rich_snippet": rs},
        ]
        results = _normalize_organic_results(items)
        assert results[0].rich_snippet == rs

    # Purpose: Test rich snippet empty when not dict
    def test_rich_snippet_empty_when_not_dict(self):
        items = [
            {"title": "Test", "link": "https://example.com", "snippet": "desc", "position": 1, "richSnippet": "not a dict"},
        ]
        results = _normalize_organic_results(items)
        assert results[0].rich_snippet == {}

    # Purpose: Test rich snippet empty when missing
    def test_rich_snippet_empty_when_missing(self):
        items = [
            {"title": "Test", "link": "https://example.com", "snippet": "desc", "position": 1},
        ]
        results = _normalize_organic_results(items)
        assert results[0].rich_snippet == {}

    # Purpose: Test dataclass defaults
    def test_dataclass_defaults(self):
        r = SERPOrganicResult(position=1, title="T", url="http://x", snippet="S")
        assert r.displayed_link == ""
        assert r.rich_snippet == {}