from __future__ import annotations

# MODULE_CONTRACT: tests/test_request_cache
# Purpose: Verify request-cache keying, storage, migration, expiration, and serialization behavior.
# Rationale: Links request-cache tests to the GRACE cache module.
# Dependencies: pandas, utils.request_cache.
# Exports: pytest tests.
# LINKS: knowledge-graph.xml#MOD-014
# MODULE_MAP: tests/test_request_cache.py
# Public Functions: pytest test functions.
# Private Helpers: CacheEnvelope, RequestEnvelope.
# Key Semantic Blocks: none.
# Critical Flows: normalize request params -> build cache keys -> set/get cache records -> validate persistence.
# Verification: verification-plan.xml#V-10-HISTORY-CACHE
# CHANGE_SUMMARY: Added GRACE module contract linking this test file to MOD-014.

import json
from dataclasses import dataclass
from typing import TypedDict

import pandas as pd

from utils.request_cache import (
    RequestCache,
    build_cache_key,
    build_settings_hash,
    build_trends_cache_key,
)


# Purpose: CacheEnvelope implementation
# Purpose: CacheEnvelope implementation
@dataclass
class CacheEnvelope:
    title: str
    metrics: dict[str, int]


# Purpose: RequestEnvelope implementation
class RequestEnvelope(TypedDict):
    keywords: list[str]
    geo: str
    nested: dict[str, str]


# Purpose: Test build cache key omits secrets and is order stable
def test_build_cache_key_omits_secrets_and_is_order_stable() -> None:
    params_a = {
        "keywords": ["Coffee", "Tea"],
        "nested": {
            "geo": "UA",
            "api_key": "secret-a",
            "token": "token-a",
        },
        "source_urls": ["https://example.com/a", "https://example.com/b"],
    }
    params_b = {
        "source_urls": ["https://example.com/b", "https://example.com/a"],
        "keywords": ["tea", "coffee"],
        "nested": {
            "geo": "ua",
            "api_key": "secret-b",
            "token": "token-b",
        },
    }

    settings_hash = build_settings_hash({"seo_math": {"analyze_bm25f": True}})

    key_a = build_cache_key("serp", "google_ads", params_a, settings_hash)
    key_b = build_cache_key("serp", "google_ads", params_b, settings_hash)

    assert key_a == key_b
    assert len(key_a) == 64


# Purpose: Test build cache key handles dataclass and typed dict params
def test_build_cache_key_handles_dataclass_and_typed_dict_params() -> None:
    params: RequestEnvelope = {
        "keywords": ["coffee", "tea"],
        "geo": "UA",
        "nested": {"mode": "fast"},
    }
    envelope = CacheEnvelope(title="Example", metrics={"hits": 3, "misses": 1})

    key = build_cache_key(
        "math",
        "local",
        {
            "request": params,
            "envelope": envelope,
        },
    )

    assert len(key) == 64
    assert key == build_cache_key(
        "math",
        "local",
        {
            "envelope": CacheEnvelope(title="Example", metrics={"hits": 3, "misses": 1}),
            "request": {
                "geo": "ua",
                "keywords": ["tea", "coffee"],
                "nested": {"mode": "fast"},
            },
        },
    )


# Purpose: Test request cache serializes dataframe and persists hit count
def test_request_cache_serializes_dataframe_and_persists_hit_count(
    tmp_path, monkeypatch
) -> None:
    history_file = tmp_path / "history.json"
    monkeypatch.setattr("utils.request_cache.HISTORY_FILE", history_file)

    cache = RequestCache(enabled=True)
    params = {"keywords": ["coffee"], "location_id": "2840"}
    cache_key = build_cache_key("ads", "google_ads", params)
    frame = pd.DataFrame(
        [
            {"Keyword": "coffee", "Avg Monthly Searches": 100},
            {"Keyword": "tea", "Avg Monthly Searches": 80},
        ]
    )

    assert cache.set("ads", cache_key, params, frame, provider="google_ads")

    first = cache.get(cache_key)
    assert first is not None
    assert first["result"]["type"] == "dataframe"
    assert first["result"]["payload"]["columns"] == ["Keyword", "Avg Monthly Searches"]
    assert first["cache_hit_count"] == 1

    second = cache.get(cache_key)
    assert second is not None
    assert second["cache_hit_count"] == 2

    stored = json.loads(history_file.read_text(encoding="utf-8"))
    cache_records = [r for r in stored["records"] if r.get("record_type") == "cache"]
    assert len(cache_records) == 1
    assert cache_records[0]["cache_hit_count"] == 2
    assert cache_records[0]["result"]["type"] == "dataframe"


# Purpose: Test force refresh bypasses cache and overwrites record
def test_force_refresh_bypasses_cache_and_overwrites_record(
    tmp_path, monkeypatch
) -> None:
    history_file = tmp_path / "history.json"
    monkeypatch.setattr("utils.request_cache.HISTORY_FILE", history_file)

    cache = RequestCache(enabled=True)
    params = {"keywords": ["coffee"], "region": "ua"}
    cache_key = build_cache_key("trends", "google_trends", params)

    assert cache.set("trends", cache_key, params, {"version": 1}, provider="google_trends")
    assert cache.get(cache_key, force_refresh=True) is None

    assert cache.set("trends", cache_key, params, {"version": 2}, provider="google_trends")
    cached = cache.get(cache_key)

    assert cached is not None
    assert cached["result"]["payload"] == {"version": 2}

    stored = json.loads(history_file.read_text(encoding="utf-8"))
    cache_records = [r for r in stored["records"] if r.get("record_type") == "cache"]
    assert len(cache_records) == 1
    assert cache_records[0]["result"]["payload"] == {"version": 2}


# Purpose: Test build trends cache key is provider and batch specific
def test_build_trends_cache_key_is_provider_and_batch_specific() -> None:
    params = {
        "keywords": ["Seo", "marketing", "seo"],
        "timeframe": "today 12-m",
        "geo": "UA",
        "category": 0,
        "property": "",
        "language": "en-US",
        "timezone": 0,
        "batch_composition": ["marketing", "seo"],
        "provider_version": "phase13-v1",
        "schema_version": 3,
        "api_key": "secret-a",
    }

    key_a = build_trends_cache_key(
        provider="dataforseo_trends",
        endpoint_mode="trends.interestByTime",
        params=params,
    )
    key_b = build_trends_cache_key(
        provider="serpapi_trends",
        endpoint_mode="trends.interestByTime",
        params=params,
    )
    key_c = build_trends_cache_key(
        provider="dataforseo_trends",
        endpoint_mode="trends.relatedQueries",
        params=params,
    )

    assert key_a
    assert key_a != key_b
    assert key_a != key_c
    assert len(key_a) == 64


# Purpose: Test trends cache round trip preserves metadata
def test_trends_cache_round_trip_preserves_metadata(tmp_path, monkeypatch) -> None:
    from utils.google_trends_client import GoogleTrendsRequest, GoogleTrendsResult

    history_file = tmp_path / "history.json"
    monkeypatch.setattr("utils.request_cache.HISTORY_FILE", history_file)

    cache = RequestCache(enabled=True)
    request = GoogleTrendsRequest(keywords=["seo"], geo="UA")
    result = GoogleTrendsResult(
        request=request,
        provider="serpapi_trends",
        provider_metadata={
            "provider": "serpapi_trends",
            "provider_version": "phase13-v1",
        },
        data_confidence="high",
    )

    cache_key = build_trends_cache_key(
        provider="serpapi_trends",
        endpoint_mode="trends.interestByTime",
        params={
            "keywords": request.keywords,
            "timeframe": request.timeframe,
            "geo": request.geo,
            "category": request.category,
            "property": request.gprop,
            "language": request.hl,
            "timezone": request.tz,
            "batch_composition": request.keywords,
            "provider_version": "phase13-v1",
        },
    )

    assert cache.set(
        "trends",
        cache_key,
        request.to_dict(),
        result,
        provider="serpapi_trends",
        keywords=request.keywords,
        ttl_hours=4,
    )

    cached = cache.get(cache_key)
    assert cached is not None
    assert cached["result"]["payload"]["provider_metadata"]["provider"] == "serpapi_trends"
    assert cached["result"]["payload"]["data_confidence"] == "high"
    assert cached["provider_metadata"]["provider_version"] == "phase13-v1"
    assert cached["data_confidence"] == "high"