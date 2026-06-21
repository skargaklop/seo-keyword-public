# MODULE_CONTRACT: tests/test_google_trends_client
# Purpose: Verify Google Trends client normalization, failure handling, and pipeline integration contracts.
# Rationale: Links Trends tests to direct client, pipeline, and browser-Trends verification modules.
# Dependencies: unittest.mock, utils.google_trends_client.
# Exports: pytest tests.
# LINKS: knowledge-graph.xml#MOD-015, knowledge-graph.xml#MOD-002, knowledge-graph.xml#MOD-016
# MODULE_MAP: tests/test_google_trends_client.py
# Public Functions: pytest test functions.
# Private Helpers: _response.
# Key Semantic Blocks: none.
# Critical Flows: mock Trends HTTP responses -> normalize Trends result objects -> assert controlled failures.
# Verification: verification-plan.xml#V-10-TRENDS-CLIENT, verification-plan.xml#V-10-PIPELINE, verification-plan.xml#V-12-BROWSER-TRENDS-PARSER
# CHANGE_SUMMARY: Added GRACE module contract linking this test file to MOD-015, MOD-002, and MOD-016.

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock

from utils.google_trends_client import (
    ANTI_XSSI_PREFIXES,
    GoogleTrendsClient,
    GoogleTrendsDataConfidence,
    GoogleTrendsFailure,
    GoogleTrendsInterestPoint,
    GoogleTrendsRequest,
    GoogleTrendsResult,
    _restore_trends_result_from_payload,
    _GENERIC_SCRAPE_WARNING,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "google_trends"


# Purpose:  response implementation
def _response(payload=None, *, status_code=200, text=None):
    response = MagicMock()
    response.status_code = status_code
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    if text is None:
        body = json.dumps(payload or {})
        response.text = f"{ANTI_XSSI_PREFIXES[1]}{body}"
    else:
        response.text = text
    return response


# Purpose:  load fixture json implementation
def _load_fixture_json(name: str):
    with open(FIXTURE_DIR / name, "r", encoding="utf-8") as handle:
        return json.load(handle)


# Purpose:  load fixture text implementation
def _load_fixture_text(name: str) -> str:
    with open(FIXTURE_DIR / name, "r", encoding="utf-8") as handle:
        return handle.read()


# Purpose: Test request normalizes keywords and limits batch size
def test_request_normalizes_keywords_and_limits_batch_size():
    request = GoogleTrendsRequest(
        keywords=["  SEO  ", "seo", "Marketing", "", "marketing"],
        batch_size=9,
        geo="ua",
        anchor_keyword=" anchor ",
    )

    assert request.keywords == ["SEO", "Marketing"]
    assert request.batch_size == 5
    assert request.geo == "UA"
    assert request.anchor_keyword == "anchor"


# Purpose: Test cache key is stable for reordered keywords
def test_cache_key_is_stable_for_reordered_keywords():
    request_a = GoogleTrendsRequest(keywords=["seo", "marketing"], geo="UA", timeframe="today 12-m")
    request_b = GoogleTrendsRequest(keywords=["marketing", "seo"], geo="UA", timeframe="today 12-m")

    assert GoogleTrendsClient._build_cache_key(request_a) == GoogleTrendsClient._build_cache_key(request_b)


# Purpose: Test strip anti xssi removes prefix
def test_strip_anti_xssi_removes_prefix():
    from utils.google_trends_client import _strip_anti_xssi

    assert _strip_anti_xssi(f"{ANTI_XSSI_PREFIXES[1]}{{\"ok\":true}}") == '{"ok":true}'




# Purpose: Test request and result to dict are serializable
def test_request_and_result_to_dict_are_serializable():
    request = GoogleTrendsRequest(keywords=["seo"], geo="UA")
    result = GoogleTrendsResult(request=request)

    assert request.to_dict()["keywords"] == ["seo"]
    assert result.to_dict()["provider"] == "browser_scraper_trends"










# Purpose: Test provider capabilities and confidence
def test_provider_capabilities_and_confidence():
    from utils.google_trends_client import (
        GoogleTrendsProviderCapabilities,
        GoogleTrendsDataConfidence,
    )
    caps = GoogleTrendsProviderCapabilities(
        provider="test_provider",
        supports_time_series=True,
        supports_related_queries=True,
        supports_related_topics=True,
        supports_geo_breakdown=True,
        supports_trending_now=False,
        supports_autocomplete=False,
        supports_topic_ids=False,
        supports_historical_depth="years",
        max_keywords_per_request=5,
        cache_ttl_seconds=3600,
        notes=["Test note"],
    )
    assert caps.provider == "test_provider"
    assert caps.supports_time_series is True
    assert caps.max_keywords_per_request == 5
    
    assert GoogleTrendsDataConfidence.HIGH == "high"
    assert GoogleTrendsDataConfidence.MEDIUM == "medium"
    assert GoogleTrendsDataConfidence.LOW == "low"
    assert GoogleTrendsDataConfidence.BLOCKED == "blocked"
    assert GoogleTrendsDataConfidence.DEGRADED == "degraded"
    assert GoogleTrendsDataConfidence.UNKNOWN == "unknown"


# Purpose: Test extended google trends result
def test_extended_google_trends_result():
    from utils.google_trends_client import GoogleTrendsResult, GoogleTrendsRequest
    req = GoogleTrendsRequest(keywords=["seo"])
    res = GoogleTrendsResult(request=req)
    assert res.data_confidence == "unknown"
    assert res.integrity_warnings == []


# Purpose: Test provider registry
def test_provider_registry():
    from utils.google_trends_client import (
        TRENDS_PROVIDER_REGISTRY,
        TRENDS_PROVIDER_OPTIONS,
        register_trends_provider,
        GoogleTrendsProviderCapabilities,
    )
    
    # Purpose: DummyAdapter implementation
    class DummyAdapter:
        provider_name = "dummy_trends"
        capabilities = GoogleTrendsProviderCapabilities(
            provider="dummy_trends",
            supports_time_series=False,
            supports_related_queries=False,
            supports_related_topics=False,
            supports_geo_breakdown=False,
            supports_trending_now=False,
            supports_autocomplete=False,
            supports_topic_ids=False,
            supports_historical_depth="none",
            max_keywords_per_request=1,
            cache_ttl_seconds=60,
            notes=[],
        )
        # Purpose: is available implementation
        def is_available(self) -> bool:
            return True
        # Purpose: get trends implementation
        def get_trends(self, request) -> any:
            return None

    register_trends_provider("dummy_trends", DummyAdapter())
    assert "dummy_trends" in TRENDS_PROVIDER_REGISTRY
    assert "dummy_trends" in TRENDS_PROVIDER_OPTIONS


# Purpose: Test trends orchestrator falls back to next available provider
def test_trends_orchestrator_falls_back_to_next_available_provider(monkeypatch):
    from utils.google_trends_client import (
        GoogleTrendsProviderCapabilities,
        GoogleTrendsResult,
        TRENDS_PROVIDER_REGISTRY,
        TrendsOrchestrator,
    )

    calls: list[tuple[str, str]] = []

    # Purpose:  UnavailableAdapter implementation
    class _UnavailableAdapter:
        provider_name = "dataforseo_trends"
        capabilities = GoogleTrendsProviderCapabilities(
            provider="dataforseo_trends",
            supports_time_series=True,
            supports_related_queries=True,
            supports_related_topics=True,
            supports_geo_breakdown=True,
            supports_trending_now=False,
            supports_autocomplete=False,
            supports_topic_ids=False,
            supports_historical_depth="years",
            max_keywords_per_request=5,
            cache_ttl_seconds=3600,
            notes=[],
        )

        # Purpose: is available implementation
        def is_available(self) -> bool:
            calls.append(("check", self.provider_name))
            return False

        # Purpose: get trends implementation
        def get_trends(self, request):  # pragma: no cover - should not run
            raise AssertionError("unavailable provider should not run")

    # Purpose:  AvailableAdapter implementation
    class _AvailableAdapter:
        provider_name = "serpapi_trends"
        capabilities = GoogleTrendsProviderCapabilities(
            provider="serpapi_trends",
            supports_time_series=True,
            supports_related_queries=True,
            supports_related_topics=True,
            supports_geo_breakdown=True,
            supports_trending_now=False,
            supports_autocomplete=False,
            supports_topic_ids=False,
            supports_historical_depth="years",
            max_keywords_per_request=5,
            cache_ttl_seconds=3600,
            notes=[],
        )

        # Purpose: is available implementation
        def is_available(self) -> bool:
            calls.append(("check", self.provider_name))
            return True

        # Purpose: get trends implementation
        def get_trends(self, request):
            calls.append(("run", self.provider_name))
            return GoogleTrendsResult(
                request=request,
                provider=self.provider_name,
                data_confidence="high",
                provider_metadata={
                    "provider": self.provider_name,
                    "provider_version": "phase13-v1",
                    "endpoint_mode": "trends.interestByTime",
                },
            )

    # Purpose:  FakeCache implementation
    class _FakeCache:
        # Purpose: get implementation
        def get(self, cache_key, force_refresh=False):
            return None

        # Purpose: set implementation
        def set(self, **kwargs):
            return True

    monkeypatch.setitem(TRENDS_PROVIDER_REGISTRY, "dataforseo_trends", _UnavailableAdapter())
    monkeypatch.setitem(TRENDS_PROVIDER_REGISTRY, "serpapi_trends", _AvailableAdapter())
    monkeypatch.setattr("utils.google_trends_client.request_cache", _FakeCache())

    orchestrator = TrendsOrchestrator(
        settings={
            "google_trends": {
                "provider": "dataforseo_trends",
                "provider_order": ["dataforseo_trends", "serpapi_trends"],
            }
        }
    )
    result = orchestrator.run_trends(["seo"], force_refresh=False)

    assert result.provider == "serpapi_trends"
    assert result.provider_metadata["provider"] == "serpapi_trends"
    assert result.provider_metadata["provider_version"] == "phase13-v1"
    assert calls == [
        ("check", "dataforseo_trends"),
        ("check", "serpapi_trends"),
        ("run", "serpapi_trends"),
    ]


# Purpose: Test serpapi trends adapter registration and availability
def test_serpapi_trends_adapter_registration_and_availability(monkeypatch):
    from utils.google_trends_client import TRENDS_PROVIDER_REGISTRY

    monkeypatch.delenv("SERPAPI_KEY", raising=False)

    assert "serpapi_trends" in TRENDS_PROVIDER_REGISTRY
    assert TRENDS_PROVIDER_REGISTRY["serpapi_trends"].provider_name == "serpapi_trends"
    assert TRENDS_PROVIDER_REGISTRY["serpapi_trends"].is_available() is False


# Purpose: Test serpapi trends timeseries fixture normalizes interest points
def test_serpapi_trends_timeseries_fixture_normalizes_interest_points(monkeypatch):
    monkeypatch.setenv("SERPAPI_KEY", "test-serpapi-key")

    from utils.google_trends_client import GoogleTrendsClient, GoogleTrendsRequest

    client = GoogleTrendsClient(provider_name="serpapi_trends")
    assert client.active_adapter is not None
    client.active_adapter.session.get = Mock(
        return_value=_response(_load_fixture_json("serpapi_timeseries_success.json"))
    )

    request = GoogleTrendsRequest(keywords=["seo"], include_related=True, include_region=True)
    result = client.get_trends(request)

    assert result.provider == "serpapi_trends"
    assert result.provider_metadata["provider"] == "serpapi_trends"
    assert "TIMESERIES" in result.provider_metadata["data_type"]
    assert result.provider_metadata["search_metadata"]["status"] == "Success"
    assert result.has_data()
    assert result.data_confidence == "high"
    assert result.interest_over_time[0].values["seo"] == 75
    assert result.related_queries_top[0].label == "what is seo"
    assert result.related_topics_top[0].label == "Search engine optimization"
    assert result.region_rows[0].region == "California"


# Purpose: Test serpapi trends error status returns typed failure
def test_serpapi_trends_error_status_returns_typed_failure(monkeypatch):
    monkeypatch.setenv("SERPAPI_KEY", "test-serpapi-key")

    from utils.google_trends_client import GoogleTrendsClient, GoogleTrendsRequest

    client = GoogleTrendsClient(provider_name="serpapi_trends")
    assert client.active_adapter is not None
    client.active_adapter.session.get = Mock(
        return_value=_response(_load_fixture_json("serpapi_error_status.json"))
    )

    request = GoogleTrendsRequest(keywords=["seo"], include_related=False, include_region=False)
    result = client.get_trends(request)

    assert result.data_confidence == "blocked"
    assert result.failures[0].kind == "provider_task_error"


# Purpose: Test serpapi trends rate limit returns quota failure
def test_serpapi_trends_rate_limit_returns_quota_failure(monkeypatch):
    monkeypatch.setenv("SERPAPI_KEY", "test-serpapi-key")

    from utils.google_trends_client import GoogleTrendsClient, GoogleTrendsRequest

    client = GoogleTrendsClient(provider_name="serpapi_trends")
    assert client.active_adapter is not None
    client.active_adapter.session.get = Mock(
        return_value=_response(_load_fixture_json("serpapi_rate_limit.json"), status_code=429)
    )

    request = GoogleTrendsRequest(keywords=["seo"], include_related=False, include_region=False)
    result = client.get_trends(request)

    assert result.data_confidence == "blocked"
    assert result.failures[0].kind == "provider_quota"


# Purpose: Test scrapebadger web adapter registration and availability
def test_scrapebadger_web_adapter_registration_and_availability(monkeypatch):
    from utils.google_trends_client import TRENDS_PROVIDER_REGISTRY

    monkeypatch.delenv("SCRAPEBADGER_KEY", raising=False)

    assert "scrapebadger_web" in TRENDS_PROVIDER_REGISTRY
    assert TRENDS_PROVIDER_REGISTRY["scrapebadger_web"].provider_name == "scrapebadger_web"
    assert TRENDS_PROVIDER_REGISTRY["scrapebadger_web"].is_available() is False


# Purpose: Test scrapebadger web parseable fixture returns low confidence
def test_scrapebadger_web_parseable_fixture_returns_low_confidence(monkeypatch):
    monkeypatch.setenv("SCRAPEBADGER_KEY", "test-scrapebadger-key")

    from utils.google_trends_client import GoogleTrendsClient, GoogleTrendsRequest

    client = GoogleTrendsClient(provider_name="scrapebadger_web")
    assert client.active_adapter is not None
    client.active_adapter.session.post = Mock(
        return_value=_response(_load_fixture_json("scrapebadger_parseable.json"))
    )

    request = GoogleTrendsRequest(keywords=["seo"], include_related=True, include_region=True)
    result = client.get_trends(request)

    assert result.provider == "scrapebadger_web"
    assert result.has_data()
    assert result.data_confidence == "low"
    assert any("generic web scrape" in warning.lower() for warning in result.integrity_warnings)


# Purpose: Test scrapebadger web unparseable fixture is not structured
def test_scrapebadger_web_unparseable_fixture_is_not_structured(monkeypatch):
    monkeypatch.setenv("SCRAPEBADGER_KEY", "test-scrapebadger-key")

    from utils.google_trends_client import GoogleTrendsClient, GoogleTrendsRequest

    client = GoogleTrendsClient(provider_name="scrapebadger_web")
    assert client.active_adapter is not None
    client.active_adapter.session.post = Mock(
        return_value=_response(_load_fixture_json("scrapebadger_unparseable.json"))
    )

    request = GoogleTrendsRequest(keywords=["seo"], include_related=False, include_region=False)
    result = client.get_trends(request)

    assert result.data_confidence == "low"
    assert any("generic web scrape" in warning.lower() for warning in result.integrity_warnings)


# Purpose: Test scrapebadger web error fixture returns unsupported mode
def test_scrapebadger_web_error_fixture_returns_unsupported_mode(monkeypatch):
    monkeypatch.setenv("SCRAPEBADGER_KEY", "test-scrapebadger-key")

    from utils.google_trends_client import GoogleTrendsClient, GoogleTrendsRequest

    client = GoogleTrendsClient(provider_name="scrapebadger_web")
    assert client.active_adapter is not None
    client.active_adapter.session.post = Mock(
        return_value=_response(_load_fixture_json("scrapebadger_error.json"), status_code=500)
    )

    request = GoogleTrendsRequest(keywords=["seo"], include_related=False, include_region=False)
    result = client.get_trends(request)

    assert result.data_confidence == "blocked"
    assert result.failures[0].kind == "unsupported_mode"
















# Purpose: Test google trends client has no google search or browser automation references
def test_google_trends_client_has_no_google_search_or_browser_automation_references():
    source = (Path(__file__).parent.parent / "utils" / "google_trends_client.py").read_text(
        encoding="utf-8"
    ).lower()

    assert "scrape_google_search" not in source
    assert "google_search" not in source
    assert "playwright" not in source
    assert "selenium" not in source
    assert "puppeteer" not in source












# Purpose: Test dataforseo adapter registration and capabilities
def test_dataforseo_adapter_registration_and_capabilities():
    from utils.google_trends_client import TRENDS_PROVIDER_REGISTRY, DataForSeoGoogleTrendsAdapter
    assert "dataforseo_trends" in TRENDS_PROVIDER_REGISTRY
    adapter = TRENDS_PROVIDER_REGISTRY["dataforseo_trends"]
    assert isinstance(adapter, DataForSeoGoogleTrendsAdapter)
    assert adapter.capabilities.supports_time_series is True
    assert adapter.capabilities.supports_historical_depth == "years"


# Purpose: Test dataforseo adapter availability respects credentials
def test_dataforseo_adapter_availability_respects_credentials(monkeypatch):
    from utils.google_trends_client import DataForSeoGoogleTrendsAdapter

    monkeypatch.delenv("DATAFORSEO_LOGIN", raising=False)
    monkeypatch.delenv("DATAFORSEO_PASSWORD", raising=False)
    assert DataForSeoGoogleTrendsAdapter().is_available() is False

    monkeypatch.setenv("DATAFORSEO_LOGIN", "test_login")
    monkeypatch.setenv("DATAFORSEO_PASSWORD", "test_pass")
    assert DataForSeoGoogleTrendsAdapter().is_available() is True


# Purpose: Test dataforseo adapter success flow
def test_dataforseo_adapter_success_flow(monkeypatch):
    from utils.google_trends_client import GoogleTrendsClient, GoogleTrendsRequest

    monkeypatch.setenv("DATAFORSEO_LOGIN", "test_login")
    monkeypatch.setenv("DATAFORSEO_PASSWORD", "test_pass")

    client = GoogleTrendsClient(provider_name="dataforseo_trends")
    adapter = client.active_adapter
    adapter.session.post = Mock(return_value=_response(_load_fixture_json("dataforseo_live_success.json")))

    request = GoogleTrendsRequest(keywords=["seo"], geo="UA", include_related=True, include_region=True)
    result = client.get_trends(request)

    assert result.has_data()
    assert result.data_confidence == "high"
    assert len(result.interest_over_time) == 2
    assert result.interest_over_time[0].values["seo"] == 75
    assert result.related_queries_top[0].label == "seo tools"
    assert result.related_queries_rising[0].label == "ai seo"
    assert result.related_topics_top[0].label == "Search engine optimization"
    assert result.region_rows[0].region == "Kyiv"
    assert result.region_rows[0].value == 100
    assert result.provider_metadata["provider"] == "dataforseo_trends"
    assert result.provider_metadata["endpoint"] == "explore/live"
    assert result.provider_metadata["status_code"] == 20000


# Purpose: Test dataforseo adapter body error returns typed failure
def test_dataforseo_adapter_body_error_returns_typed_failure(monkeypatch):
    from utils.google_trends_client import GoogleTrendsClient, GoogleTrendsRequest

    monkeypatch.setenv("DATAFORSEO_LOGIN", "test_login")
    monkeypatch.setenv("DATAFORSEO_PASSWORD", "test_pass")

    client = GoogleTrendsClient(provider_name="dataforseo_trends")
    adapter = client.active_adapter
    adapter.session.post = Mock(return_value=_response(_load_fixture_json("dataforseo_body_error.json")))

    request = GoogleTrendsRequest(keywords=["seo"], include_related=False, include_region=False)
    result = client.get_trends(request)

    assert not result.has_data()
    assert result.data_confidence == "blocked"
    assert result.failures[0].kind == "provider_task_error"


# Purpose: Test dataforseo adapter unauthorized error
def test_dataforseo_adapter_unauthorized_error(monkeypatch):
    from utils.google_trends_client import GoogleTrendsClient, GoogleTrendsRequest

    monkeypatch.setenv("DATAFORSEO_LOGIN", "test_login")
    monkeypatch.setenv("DATAFORSEO_PASSWORD", "test_pass")

    client = GoogleTrendsClient(provider_name="dataforseo_trends")
    adapter = client.active_adapter
    adapter.session.post = Mock(return_value=_response(_load_fixture_json("dataforseo_auth_error.json"), status_code=401))

    request = GoogleTrendsRequest(keywords=["seo"], include_related=False, include_region=False)
    result = client.get_trends(request)

    assert not result.has_data()
    assert result.data_confidence == "blocked"
    assert result.failures[0].kind == "provider_auth"


# Purpose: Test dataforseo adapter rate limited error
def test_dataforseo_adapter_rate_limited_error(monkeypatch):
    from utils.google_trends_client import GoogleTrendsClient, GoogleTrendsRequest

    monkeypatch.setenv("DATAFORSEO_LOGIN", "test_login")
    monkeypatch.setenv("DATAFORSEO_PASSWORD", "test_pass")

    client = GoogleTrendsClient(provider_name="dataforseo_trends")
    adapter = client.active_adapter
    adapter.session.post = Mock(return_value=_response(_load_fixture_json("dataforseo_rate_limit.json"), status_code=429))

    request = GoogleTrendsRequest(keywords=["seo"], include_related=False, include_region=False)
    result = client.get_trends(request)

    assert not result.has_data()
    assert result.data_confidence == "blocked"
    assert result.failures[0].kind == "provider_quota"


# Purpose: Test dataforseo adapter partial data sets medium confidence
def test_dataforseo_adapter_partial_data_sets_medium_confidence(monkeypatch):
    from utils.google_trends_client import GoogleTrendsClient, GoogleTrendsRequest

    monkeypatch.setenv("DATAFORSEO_LOGIN", "test_login")
    monkeypatch.setenv("DATAFORSEO_PASSWORD", "test_pass")

    client = GoogleTrendsClient(provider_name="dataforseo_trends")
    adapter = client.active_adapter
    adapter.session.post = Mock(return_value=_response(_load_fixture_json("dataforseo_partial_data.json")))

    request = GoogleTrendsRequest(keywords=["seo"], include_related=True, include_region=True)
    result = client.get_trends(request)

    assert result.has_data()
    assert result.data_confidence == "medium"
    assert result.integrity_warnings










# Purpose: Test google trends client has no forbidden auth imports or service account env refs
def test_google_trends_client_has_no_forbidden_auth_imports_or_service_account_env_refs():
    source = (Path(__file__).parent.parent / "utils" / "google_trends_client.py").read_text(
        encoding="utf-8"
    ).lower()

    forbidden_fragments = [
        "google-auth",
        "oauthlib",
        "cryptography",
        "jwt",
        "service_account",
        "google_trends_alpha_service_account_json",
    ]

    assert all(fragment not in source for fragment in forbidden_fragments)


# --- WARNING-008: Tests for _restore_trends_result_from_payload edge cases ---


# Purpose: Empty dict returns None because GoogleTrendsRequest requires keywords.
def test_restore_trends_result_from_empty_dict():
    result = _restore_trends_result_from_payload({})
    assert result is None


# Purpose: Non-dict input should return None.
def test_restore_trends_result_returns_none_for_non_dict():
    assert _restore_trends_result_from_payload("not a dict") is None
    assert _restore_trends_result_from_payload(42) is None
    assert _restore_trends_result_from_payload(None) is None
    assert _restore_trends_result_from_payload([]) is None


# Purpose: Partial payload with only required fields should restore without error.
def test_restore_trends_result_with_missing_optional_fields():
    payload = {
        "request": {"keywords": ["seo"]},
    }
    result = _restore_trends_result_from_payload(payload)
    assert result is not None
    assert isinstance(result.request, GoogleTrendsRequest)
    assert result.request.keywords == ["seo"]
    assert result.interest_over_time == []
    assert result.related_queries_top == []
    assert result.warnings == []
    assert result.failures == []


# Purpose: Nested items that are not dicts/dataclass should be filtered out gracefully.
def test_restore_trends_result_with_nested_type_mismatch():
    payload = {
        "request": {"keywords": ["seo"]},
        "interest_over_time": ["not_a_dict", 42, None],
        "related_queries_top": [True, "bad"],
        "region_rows": [123],
        "failures": ["not_a_failure_dict"],
    }
    result = _restore_trends_result_from_payload(payload)
    assert result is not None
    # All malformed items should be filtered out
    assert result.interest_over_time == []
    assert result.related_queries_top == []
    assert result.region_rows == []
    assert result.failures == []


# Purpose: Properly structured nested items should be reconstructed as dataclass instances.
def test_restore_trends_result_with_valid_nested_dataclass_items():
    payload = {
        "request": {"keywords": ["seo"]},
        "interest_over_time": [
            {
                "time": "2025-01",
                "formatted_time": "Jan 2025",
                "values": {"seo": 75},
                "source_batches": [1],
            }
        ],
        "averages": {"seo": 75.0},
    }
    result = _restore_trends_result_from_payload(payload)
    assert result is not None
    assert len(result.interest_over_time) == 1
    assert result.interest_over_time[0].time == "2025-01"
    assert result.interest_over_time[0].values == {"seo": 75}
    assert result.averages == {"seo": 75.0}


# Purpose: data_confidence as a non-string (e.g. int) should still work via str() conversion.
def test_restore_trends_result_with_confidence_type_mismatch():
    payload = {
        "request": {"keywords": ["seo"]},
        "data_confidence": 42,
    }
    result = _restore_trends_result_from_payload(payload)
    assert result is not None
    assert result.data_confidence == "42"


# --- WARNING-002: Verify _GENERIC_SCRAPE_WARNING constant ---


# Purpose: The _GENERIC_SCRAPE_WARNING constant should match the expected string.
def test_generic_scrape_warning_constant_matches_string():
    assert _GENERIC_SCRAPE_WARNING == "Generic web scrape; data quality not guaranteed."


# ---------------------------------------------------------------------------
# PLAN 15-02: Google Trends provider/options tests
# ---------------------------------------------------------------------------


# Purpose: Cache keys must differentiate requests with different timeframes.
def test_trends_cache_key_differs_by_timeframe():
    from utils.request_cache import build_trends_cache_key

    key_12m = build_trends_cache_key(
        provider="serpapi_trends",
        endpoint_mode="trends.interestByTime",
        params={"keywords": ["seo"], "geo": "US", "timeframe": "today 12-m", "category": 0},
    )
    key_3m = build_trends_cache_key(
        provider="serpapi_trends",
        endpoint_mode="trends.interestByTime",
        params={"keywords": ["seo"], "geo": "US", "timeframe": "today 3-m", "category": 0},
    )
    assert key_12m != key_3m, "Different timeframes must produce different cache keys"


# Purpose: Cache keys must differentiate same keywords across different providers.
def test_trends_cache_key_differs_by_provider():
    from utils.request_cache import build_trends_cache_key

    params = {"keywords": ["seo"], "geo": "US", "timeframe": "today 12-m"}
    key_direct = build_trends_cache_key(provider="google_trends_direct", endpoint_mode="trends.interestByTime", params=params)
    key_serpapi = build_trends_cache_key(provider="serpapi_trends", endpoint_mode="trends.interestByTime", params=params)
    assert key_direct != key_serpapi, "Different providers must produce different cache keys"


# Purpose: Cache keys must include category and gprop (property).
def test_trends_cache_key_differs_by_category_and_property():
    from utils.request_cache import build_trends_cache_key

    base_params = {"keywords": ["seo"], "geo": "US", "timeframe": "today 12-m", "category": 0, "gprop": ""}
    cat_params = {**base_params, "category": 5}
    prop_params = {**base_params, "gprop": "images"}

    key_base = build_trends_cache_key(provider="serpapi_trends", endpoint_mode="trends.interestByTime", params=base_params)
    key_cat = build_trends_cache_key(provider="serpapi_trends", endpoint_mode="trends.interestByTime", params=cat_params)
    key_prop = build_trends_cache_key(provider="serpapi_trends", endpoint_mode="trends.interestByTime", params=prop_params)

    assert key_base != key_cat, "Different category must produce different cache key"
    assert key_base != key_prop, "Different gprop must produce different cache key"


# Purpose: GoogleTrendsRequest normalizes category to int and gprop to stripped string.
def test_trends_request_normalizes_category_and_gprop():
    request = GoogleTrendsRequest(
        keywords=["seo"],
        geo="US",
        timeframe="today 12-m",
        category=5,
        gprop="Images",
    )
    assert request.category == 5
    assert request.gprop == "Images"


# Purpose: Valid fixture payload can be restored as GoogleTrendsResult without error.
def test_trends_request_valid_payload_fixture_is_accepted():
    from utils.google_trends_client import _restore_trends_result_from_payload

    payload = {
        "request": {
            "keywords": ["seo", "marketing"],
            "geo": "US",
            "timeframe": "today 12-m",
            "category": 5,
            "gprop": "images",
        },
        "provider": "serpapi_trends",
        "data_confidence": "high",
        "interest_over_time": [
            {
                "time": "2025-01",
                "formatted_time": "Jan 2025",
                "values": {"seo": 75, "marketing": 60},
                "source_batches": [1],
            }
        ],
        "related_queries_top": [],
        "related_queries_rising": [],
        "related_topics_top": [],
        "related_topics_rising": [],
        "region_rows": [],
        "averages": {"seo": 75.0, "marketing": 60.0},
        "failures": [],
        "warnings": [],
        "integrity_warnings": [],
        "provider_metadata": {"provider": "serpapi_trends"},
    }
    result = _restore_trends_result_from_payload(payload)
    assert result is not None
    assert result.request.keywords == ["seo", "marketing"]
    assert result.request.category == 5
    assert result.request.gprop == "images"


# Purpose: TrendsOrchestrator passes provider and request options to adapter via settings.
def test_trends_orchestrator_passes_provider_and_options(monkeypatch):
    from utils.google_trends_client import TrendsOrchestrator

    captured_requests = []

    # Purpose:  FakeAdapter implementation
    class _FakeAdapter:
        provider_name = "serpapi_trends"

        # Purpose: is available implementation
        def is_available(self):
            return True

        # Purpose: get trends implementation
        def get_trends(self, request):
            captured_requests.append(request)
            return GoogleTrendsResult(request=request, provider="serpapi_trends", data_confidence="high")

    monkeypatch.setattr(
        "utils.google_trends_client.TRENDS_PROVIDER_REGISTRY",
        {"serpapi_trends": _FakeAdapter()},
    )

    mock_cache = type("C", (), {"get": lambda *a, **kw: None, "set": lambda self, *a, **kw: True})()

    orchestrator = TrendsOrchestrator(
        settings={
            "google_trends": {
                "provider": "serpapi_trends",
                "provider_order": ["serpapi_trends"],
                "default_timeframe": "today 3-m",
                "default_category": 5,
            }
        },
        cache=mock_cache,
    )
    result = orchestrator.run_trends(
        ["seo"],
        force_refresh=False,
    )

    assert result is not None
    assert len(captured_requests) == 1
    assert captured_requests[0].timeframe == "today 3-m"
    assert captured_requests[0].category == 5


# Purpose: TrendsOrchestrator must ignore stale degraded cache entries and refetch live data.
def test_trends_orchestrator_skips_stale_degraded_cache_entries(monkeypatch):
    from utils.google_trends_client import TrendsOrchestrator

    captured_requests = []
    cached_request = GoogleTrendsRequest(keywords=["seo"], geo="US", timeframe="today 3-m")
    cached_result = GoogleTrendsResult(
        request=cached_request,
        provider="serpapi_trends",
        interest_over_time=[
            GoogleTrendsInterestPoint(
                time="2025-06-01",
                formatted_time="2025-06-01",
                values={"seo": 10},
            )
        ],
        failures=[
            GoogleTrendsFailure(
                kind="rate_limit",
                message="Google returned 429/block page",
                retryable=False,
                source="browser_scraper_trends",
            )
        ],
        data_confidence=GoogleTrendsDataConfidence.DEGRADED.value,
        provider_metadata={"provider": "browser_scraper_trends", "status": "blocked"},
    )

    class _FakeAdapter:
        provider_name = "serpapi_trends"

        def is_available(self):
            return True

        def get_trends(self, request):
            captured_requests.append(request)
            return GoogleTrendsResult(
                request=request,
                provider="serpapi_trends",
                interest_over_time=[
                    GoogleTrendsInterestPoint(
                        time="2025-06-01",
                        formatted_time="2025-06-01",
                        values={"seo": 42},
                    )
                ],
                data_confidence=GoogleTrendsDataConfidence.HIGH.value,
                provider_metadata={"provider": "serpapi_trends"},
            )

    class _FakeCache:
        def __init__(self):
            self.set_calls = []

        def get(self, cache_key, force_refresh=False):
            return {"result": {"payload": cached_result.to_dict()}, "cache_hit_count": 3}

        def set(self, **kwargs):
            self.set_calls.append(kwargs)
            return True

    fake_cache = _FakeCache()
    monkeypatch.setattr(
        "utils.google_trends_client.TRENDS_PROVIDER_REGISTRY",
        {"serpapi_trends": _FakeAdapter()},
    )

    orchestrator = TrendsOrchestrator(
        settings={
            "google_trends": {
                "provider": "serpapi_trends",
                "provider_order": ["serpapi_trends"],
                "default_timeframe": "today 3-m",
            }
        },
        cache=fake_cache,
    )

    result = orchestrator.run_trends(["seo"], force_refresh=False)

    assert len(captured_requests) == 1
    assert result.interest_over_time[0].values["seo"] == 42
    assert result.data_confidence == GoogleTrendsDataConfidence.HIGH.value
    assert len(fake_cache.set_calls) == 1


# Purpose: TrendsOrchestrator should not cache degraded live browser results.
def test_trends_orchestrator_does_not_cache_degraded_live_results(monkeypatch):
    from utils.google_trends_client import TrendsOrchestrator

    class _FakeAdapter:
        provider_name = "serpapi_trends"

        def is_available(self):
            return True

        def get_trends(self, request):
            return GoogleTrendsResult(
                request=request,
                provider="serpapi_trends",
                interest_over_time=[
                    GoogleTrendsInterestPoint(
                        time="2025-06-01",
                        formatted_time="2025-06-01",
                        values={"seo": 10},
                    )
                ],
                failures=[
                    GoogleTrendsFailure(
                        kind="rate_limit",
                        message="Google returned 429/block page",
                        retryable=False,
                        source="browser_scraper_trends",
                    )
                ],
                data_confidence=GoogleTrendsDataConfidence.DEGRADED.value,
                provider_metadata={"provider": "serpapi_trends", "status": "partial"},
            )

    class _FakeCache:
        def __init__(self):
            self.set_calls = []

        def get(self, cache_key, force_refresh=False):
            return None

        def set(self, **kwargs):
            self.set_calls.append(kwargs)
            return True

    fake_cache = _FakeCache()
    monkeypatch.setattr(
        "utils.google_trends_client.TRENDS_PROVIDER_REGISTRY",
        {"serpapi_trends": _FakeAdapter()},
    )

    orchestrator = TrendsOrchestrator(
        settings={
            "google_trends": {
                "provider": "serpapi_trends",
                "provider_order": ["serpapi_trends"],
            }
        },
        cache=fake_cache,
    )

    result = orchestrator.run_trends(["seo"], force_refresh=False)

    assert result.data_confidence == GoogleTrendsDataConfidence.DEGRADED.value
    assert len(fake_cache.set_calls) == 0


# Purpose: GoogleTrendsClient returns blocked result for empty keyword list.
def test_trends_client_returns_blocked_for_empty_keywords():
    from utils.google_trends_client import GoogleTrendsClient, GoogleTrendsRequest
    try:
        request = GoogleTrendsRequest(keywords=[])
        client = GoogleTrendsClient(batch_delay_seconds=0, max_retries=1)
        result = client.get_trends(request)
        assert result.data_confidence == "blocked"
    except ValueError:
        pass  # ValueError is also acceptable for empty keywords


# Purpose: GoogleTrendsClient rejects requests exceeding max_keywords_per_request.
def test_trends_client_rejects_keywords_longer_than_max():
    from utils.google_trends_client import GoogleTrendsClient, GoogleTrendsRequest
    request = GoogleTrendsRequest(
        keywords=["kw1", "kw2", "kw3", "kw4", "kw5", "kw6", "kw7", "kw8", "kw9", "kw10"],
        geo="US",
        max_keywords_per_request=9,
    )
    client = GoogleTrendsClient(batch_delay_seconds=0, max_retries=1)
    result = client.get_trends(request)
    assert not result.has_data()
    assert any(f.kind in ("too_many_keywords", "max_keywords_exceeded") for f in result.failures)


# Purpose: GoogleTrendsClient honors configured local browser keyword caps above five.
def test_browser_trends_client_allows_configured_ten_keyword_run(monkeypatch):
    from utils.google_trends_client import (
        GoogleTrendsClient,
        GoogleTrendsDataConfidence,
        GoogleTrendsProviderCapabilities,
        GoogleTrendsRequest,
        GoogleTrendsResult,
        TRENDS_PROVIDER_REGISTRY,
    )

    class _TenKeywordAdapter:
        provider_name = "browser_scraper_trends"
        capabilities = GoogleTrendsProviderCapabilities(
            provider="browser_scraper_trends",
            supports_time_series=True,
            supports_related_queries=False,
            supports_related_topics=False,
            supports_geo_breakdown=False,
            supports_trending_now=False,
            supports_autocomplete=False,
            supports_topic_ids=False,
            supports_historical_depth="months",
            max_keywords_per_request=5,
            cache_ttl_seconds=3600,
            notes=[],
        )

        def get_trends(self, request):
            return GoogleTrendsResult(
                request=request,
                provider=self.provider_name,
                data_confidence=GoogleTrendsDataConfidence.MEDIUM.value,
            )

    monkeypatch.setitem(TRENDS_PROVIDER_REGISTRY, "browser_scraper_trends", _TenKeywordAdapter())
    request = GoogleTrendsRequest(
        keywords=[f"kw{i}" for i in range(10)],
        geo="US",
        max_keywords_per_request=10,
    )
    result = GoogleTrendsClient(provider_name="browser_scraper_trends").get_trends(request)

    assert result.provider == "browser_scraper_trends"
    assert result.failures == []


# Purpose: Trends cache identity changes when the configured keyword cap changes.
def test_trends_batch_composition_includes_max_keywords_per_request():
    from utils.google_trends_client import GoogleTrendsRequest, _trends_batch_composition

    request = GoogleTrendsRequest(
        keywords=["kw1", "kw2"],
        geo="US",
        max_keywords_per_request=10,
    )

    assert _trends_batch_composition(request)["max_keywords_per_request"] == 10
    assert request.to_dict()["max_keywords_per_request"] == 10
