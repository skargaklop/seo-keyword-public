from __future__ import annotations

from dataclasses import is_dataclass



def test_build_trends_provider_capabilities_matches_expected_shape() -> None:
    from utils.google_trends_client import _build_trends_provider_capabilities

    capabilities = _build_trends_provider_capabilities(
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
        cache_ttl_seconds=86400,
        notes=["Browser CSV-download automation via cloakbrowser."],
    )

    assert is_dataclass(capabilities)
    assert capabilities.provider == "browser_scraper_trends"
    assert capabilities.supports_time_series is True
    assert capabilities.supports_related_queries is False
    assert capabilities.max_keywords_per_request == 5
    assert capabilities.notes == ["Browser CSV-download automation via cloakbrowser."]


def test_build_trends_result_defaults_to_empty_collections() -> None:
    from utils.google_trends_client import (
        GoogleTrendsDataConfidence,
        GoogleTrendsRequest,
        _build_trends_result,
    )

    request = GoogleTrendsRequest(keywords=["seo"], geo="UA")
    result = _build_trends_result(
        request=request,
        provider="browser_scraper_trends",
        provider_metadata={"provider": "browser_scraper_trends", "status": "empty"},
        cache_metadata={"cache_hit": False},
        data_confidence=GoogleTrendsDataConfidence.LOW.value,
        warnings=["Downloaded CSV contains no data rows for 'seo'"],
        failures=[],
        integrity_warnings=["Downloaded CSV contains no data rows for 'seo'"],
    )

    assert result.provider == "browser_scraper_trends"
    assert result.interest_over_time == []
    assert result.related_queries_top == []
    assert result.related_topics_top == []
    assert result.region_rows == []
    assert result.data_confidence == GoogleTrendsDataConfidence.LOW.value
    assert result.provider_metadata["status"] == "empty"
    assert result.cache_metadata == {"cache_hit": False}


def test_restore_trends_result_payload_keeps_typed_items() -> None:
    from utils.google_trends_client import (
        GoogleTrendsFailure,
        GoogleTrendsInterestPoint,
        GoogleTrendsRegionRow,
        _restore_trends_result_payload,
    )

    payload = {
        "request": {
            "keywords": ["seo"],
            "geo": "UA",
            "timeframe": "today 12-m",
        },
        "provider": "serpapi_trends",
        "interest_over_time": [
            {"time": "2025-06-01", "formatted_time": "2025-06-01", "values": {"seo": 45}},
        ],
        "region_rows": [
            {"region": "Kyiv", "value": 80, "keyword": "seo", "source_batches": [0]},
        ],
        "failures": [
            {
                "kind": "empty_data",
                "message": "No rows",
                "retryable": False,
                "source": "serpapi_trends",
            }
        ],
    }

    result = _restore_trends_result_payload(payload)

    assert result is not None
    assert isinstance(result.interest_over_time[0], GoogleTrendsInterestPoint)
    assert isinstance(result.region_rows[0], GoogleTrendsRegionRow)
    assert isinstance(result.failures[0], GoogleTrendsFailure)
    assert result.provider == "serpapi_trends"
    assert result.request.keywords == ["seo"]


def test_close_resource_quietly_ignores_close_errors() -> None:
    from utils.browser_scraper import _close_resource_quietly

    class ClosingResource:
        def __init__(self) -> None:
            self.closed = 0

        def close(self) -> None:
            self.closed += 1

    class BrokenResource:
        def __init__(self) -> None:
            self.closed = 0

        def close(self) -> None:
            self.closed += 1
            raise RuntimeError("boom")

    good = ClosingResource()
    broken = BrokenResource()

    _close_resource_quietly(good)
    _close_resource_quietly(broken)

    assert good.closed == 1
    assert broken.closed == 1

