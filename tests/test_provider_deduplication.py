from __future__ import annotations

# MODULE_CONTRACT: tests/test_provider_deduplication
# Purpose: Verify deduplication helpers preserve cache-key, cache-lookup, and fallback behavior.
# Rationale: Locks the branch equivalence needed for the GRACE clone refactor.
# Dependencies: pandas, pytest, utils.google_ads_client, utils.llm_handler, utils.request_cache.
# Exports: pytest tests.
# LINKS: requirements.xml#UC-001
# MODULE_MAP: tests/test_provider_deduplication.py
# Public Functions: pytest test functions.
# Private Helpers: _ToDictOnly, _ModelDumpOnly, _AsDictOnly, _SlotsItemOnly.
# Key Semantic Blocks: none.
# Critical Flows: normalize ads request params -> reconstruct cached payloads -> serialize request-cache values -> persist fallback results.
# Verification: tmp/jscpd-grace-20260619/jscpd-report.json
# CHANGE_SUMMARY: Added regression coverage for cache-key normalization, recursive value coercion, and fallback cache persistence.

from dataclasses import dataclass

import pandas as pd
import pytest

import utils.google_ads_client as google_ads_client_module
import utils.llm_handler as llm_handler_module
from utils.google_ads_client import GoogleAdsHandler
from utils.llm_handler import LLMHandler
from utils.request_cache import _canonicalize_for_key, _jsonable_value, _sanitize_params


@dataclass
class _Stamped:
    title: str
    created_at: str


class _ToDictOnly:
    def to_dict(self) -> dict[str, object]:
        return {"Title": "Hello", "Nested": {"Value": "World"}}


class _ModelDumpOnly:
    def model_dump(self) -> dict[str, object]:
        return {"Title": "Hello", "Nested": {"Value": "World"}}


class _AsDictOnly:
    def _asdict(self) -> dict[str, object]:
        return {"Title": "Hello", "Nested": {"Value": "World"}}


class _SlotsItemOnly:
    __slots__ = ("value",)

    def __init__(self, value: object) -> None:
        self.value = value

    def item(self) -> object:
        return self.value


def test_google_ads_request_params_are_normalized_by_operation() -> None:
    handler = GoogleAdsHandler.__new__(GoogleAdsHandler)
    handler.location_id = "2804"
    handler.language_id = ["1036", "1031"]
    handler.target_currency_code = "uah"

    metrics_params = handler._build_ads_request_params(
        "historical_metrics",
        [" Tea ", "coffee", ""],
    )
    ideas_params = handler._build_ads_request_params(
        "keyword_ideas",
        [" Tea ", "coffee"],
        page_url=" https://example.com/stretch-film ",
    )

    assert metrics_params == {
        "operation": "historical_metrics",
        "keywords": ["coffee", "tea"],
        "location_id": "2804",
        "language_id": "1031,1036",
        "currency_code": "UAH",
    }
    assert ideas_params == {
        "operation": "keyword_ideas",
        "keywords": ["coffee", "tea"],
        "page_url": "https://example.com/stretch-film",
        "location_id": "2804",
        "language_id": "1031,1036",
        "currency_code": "UAH",
    }


@pytest.mark.parametrize(
    "cached_result, expected",
    [
        (
            {
                "result": {
                    "payload": {
                        "columns": ["Keyword", "Avg Monthly Searches"],
                        "data": [{"Keyword": "coffee", "Avg Monthly Searches": 100}],
                    }
                }
            },
            pd.DataFrame([{"Keyword": "coffee", "Avg Monthly Searches": 100}]),
        ),
        (
            {"result": {"payload": [{"Keyword": "tea", "Avg Monthly Searches": 80}]}},
            pd.DataFrame([{"Keyword": "tea", "Avg Monthly Searches": 80}]),
        ),
        (
            {"result": {"payload": "raw-payload"}},
            "raw-payload",
        ),
        (
            {"result": {}},
            None,
        ),
    ],
)
def test_google_ads_cached_payload_helper_preserves_payload_shape(
    monkeypatch: pytest.MonkeyPatch,
    cached_result: dict[str, object],
    expected: object,
) -> None:
    handler = GoogleAdsHandler.__new__(GoogleAdsHandler)

    monkeypatch.setattr(
        google_ads_client_module.request_cache,
        "get",
        lambda cache_key, force_refresh=False: cached_result,
    )

    result = handler._get_cached_ads_dataframe("cache-key", force_refresh=False)

    if isinstance(expected, pd.DataFrame):
        assert isinstance(result, pd.DataFrame)
        pd.testing.assert_frame_equal(result.reset_index(drop=True), expected)
    else:
        assert result == expected


@pytest.mark.parametrize(
    "value, expected_json, expected_key",
    [
        (
            _Stamped(title="Hello", created_at="2026-06-19T10:00:00"),
            {"title": "Hello", "created_at": "2026-06-19T10:00:00"},
            {"created_at": "2026-06-19t10:00:00", "title": "hello"},
        ),
        (
            _ToDictOnly(),
            {"Title": "Hello", "Nested": {"Value": "World"}},
            {"Nested": {"Value": "world"}, "Title": "hello"},
        ),
        (
            _ModelDumpOnly(),
            {"Title": "Hello", "Nested": {"Value": "World"}},
            {"Nested": {"Value": "world"}, "Title": "hello"},
        ),
        (
            _AsDictOnly(),
            {"Title": "Hello", "Nested": {"Value": "World"}},
            {"Nested": {"Value": "world"}, "Title": "hello"},
        ),
        (
            _SlotsItemOnly("MiXeD"),
            "MiXeD",
            "mixed",
        ),
    ],
)
def test_request_cache_recursive_value_coercion_branches(
    value: object,
    expected_json: object,
    expected_key: object,
) -> None:
    assert _jsonable_value(value) == expected_json
    assert _canonicalize_for_key(value) == expected_key


def test_request_cache_sanitize_params_removes_secrets_and_preserves_nested_values() -> None:
    sanitized = _sanitize_params(
        {
            "api_key": "secret",
            "payload": _ToDictOnly(),
            "nested": {
                "token": "secret-token",
                "summary": _Stamped(title="Hello", created_at="2026-06-19T10:00:00"),
            },
        }
    )

    assert "api_key" not in sanitized
    assert "token" not in sanitized["nested"]
    assert sanitized["payload"] == {"Title": "hello", "Nested": {"Value": "world"}}
    assert sanitized["nested"]["summary"] == {
        "title": "hello",
        "created_at": "2026-06-19t10:00:00",
    }


def test_llm_fallback_cache_helper_persists_non_none_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        llm_handler_module.request_cache,
        "set",
        lambda **kwargs: captured_calls.append(kwargs) or True,
    )

    handler = LLMHandler.__new__(LLMHandler)
    fallback_result = ["alpha", "beta"]
    returned = handler._cache_fallback_result(
        kind="llm_extract",
        cache_key="cache-key",
        request_params={"text_hash": "abc"},
        result=fallback_result,
        provider="openai",
    )
    empty_return = handler._cache_fallback_result(
        kind="llm_extract",
        cache_key="cache-key",
        request_params={"text_hash": "abc"},
        result=None,
        provider="openai",
    )

    assert returned == fallback_result
    assert empty_return is None
    assert captured_calls == [
        {
            "kind": "llm_extract",
            "cache_key": "cache-key",
            "request_params": {"text_hash": "abc"},
            "result": fallback_result,
            "provider": "openai",
        }
    ]
