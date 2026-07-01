"""Google Trends client with commercial API adapter support."""

# MODULE_CONTRACT: utils/google_trends_client
# Purpose: Google Trends client with commercial API adapter support
# Rationale: Commercial API adapters provide reliable keyword interest data without reverse engineering
# Dependencies: typing, dataclasses, datetime, json, time, hashlib, requests, config.settings, utils.logger
# Exports: GoogleTrendsClient, GoogleTrendsRequest, GoogleTrendsResult, GoogleTrendsError, GoogleTrendsFailure, GoogleTrendsInterestPoint, GoogleTrendsRelatedItem, GoogleTrendsRegionRow, create_google_trends_client
# LINKS: requirements.xml#UC-010, .planning/phases/10-bm25f-history-cache-google-trends/10-CONTEXT.md, verification-plan.xml#V-MOD-010, knowledge-graph.xml#MOD-015, verification-plan.xml#V-17-SEMRUSH-NO-TRENDS
# MODULE_MAP: utils/google_trends_client.py
# Public Functions: create_google_trends_client, GoogleTrendsClient.get_trends
# Private Helpers: _normalize_text, _normalize_keywords, _canonical_json, _first_numeric, _safe_round_value, _strip_anti_xssi, _parse_timeline, _parse_related, _parse_region, _merge_interest_points, _calculate_averages, _dedupe_related, _dedupe_regions, _extract_widgets
# Key Semantic Blocks: block_trends_request_validation, block_trends_batch_processing, block_explore_api_call, block_trends_widget_extraction, block_trends_timeline_parsing, block_related_queries_parsing, block_trends_region_parsing, block_trends_result_deduplication
# Critical Flows: Request validation → commercial API adapter → widget extraction → timeline/related/region parsing → deduplication → result aggregation
# Verification: verification-plan.xml#V-MOD-010
# CHANGE_SUMMARY: Phase 16 - Removed stale direct/local adapters, kept commercial API adapters only

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Protocol

import requests
from requests.auth import HTTPBasicAuth
from config.settings import load_config, RETRY_CONFIG
import config.settings as settings
from utils.request_cache import build_trends_cache_key, request_cache
from utils.logger import logger

GOOGLE_TRENDS_EXPLORE_URL = "https://trends.google.com/trends/api/explore"
DATAFORSEO_BASE_URL = "https://api.dataforseo.com/v3"
DATAFORSEO_GOOGLE_TRENDS_EXPLORE_LIVE_URL = (
    f"{DATAFORSEO_BASE_URL}/keywords_data/google_trends/explore/live"
)
ANTI_XSSI_PREFIXES = (")]}\'", ")]}'\n", ")]}'\r\n")
MAX_BATCH_SIZE = 5
DEFAULT_PROVIDER_NAME = "browser_scraper_trends"
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_BATCH_DELAY_SECONDS = 2.0
DEFAULT_MAX_RETRIES = int(RETRY_CONFIG.get("max_attempts", 4))
DEFAULT_RETRY_BACKOFF = float(RETRY_CONFIG.get("backoff_factor", 1.5))
MODULE_VERSION = "phase10-google-trends-v1"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)
DATAFORSEO_LOCATION_NAME_MAP = {
    "UA": "Ukraine",
    "US": "United States",
    "GB": "United Kingdom",
    "UK": "United Kingdom",
    "DE": "Germany",
    "PL": "Poland",
    "RU": "Russia",
    "CA": "Canada",
    "AU": "Australia",
    "IN": "India",
    "FR": "France",
    "IT": "Italy",
    "ES": "Spain",
    "NL": "Netherlands",
    "BR": "Brazil",
    "TR": "Turkey",
    "KZ": "Kazakhstan",
}
DATAFORSEO_TIME_RANGE_MAP = {
    "today 12-m": "past_12_months",
    "today 5-y": "past_5_years",
    "today 1-m": "past_30_days",
    "today 7-d": "past_7_days",
    "today 1-d": "past_day",
    "now 1-h": "past_hour",
    "now 4-h": "past_4_hours",
}
DATAFORSEO_ITEM_TYPES = {
    "interest_over_time": "google_trends_interest_over_time",
    "interest_by_region": "google_trends_interest_by_region",
    "related_queries": "google_trends_related_queries",
    "related_topics": "google_trends_related_topics",
}
_GENERIC_SCRAPE_WARNING = "Generic web scrape; data quality not guaranteed."
_SECRET_DETAIL_TOKENS = frozenset({
    "api", "apikey", "api_key", "auth", "authorization", "bearer",
    "clientsecret", "client_secret", "credential", "credentials",
    "key", "password", "privatekey", "private_key", "refresh",
    "secret", "session", "token",
})


# Purpose: Strip secret-bearing fields from failure details before caching.
def _sanitize_details_for_cache(details: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(details, dict):
        return details
    sanitized: Dict[str, Any] = {}
    for key, value in details.items():
        key_lower = str(key).lower().replace("-", "_").replace(".", "_")
        tokens = set(re.split(r"[^a-zA-Z0-9]+", key_lower))
        if tokens & _SECRET_DETAIL_TOKENS:
            sanitized[key] = "[REDACTED]"
            continue
        if isinstance(value, dict):
            sanitized[key] = _sanitize_details_for_cache(value)
        elif isinstance(value, (list, tuple)):
            sanitized[key] = [
                _sanitize_details_for_cache(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            sanitized[key] = value
    return sanitized


# Purpose: GoogleTrendsProviderCapabilities implementation
# Purpose: GoogleTrendsProviderCapabilities implementation
@dataclass
class GoogleTrendsProviderCapabilities:
    provider: str
    supports_time_series: bool
    supports_related_queries: bool
    supports_related_topics: bool
    supports_geo_breakdown: bool
    supports_trending_now: bool
    supports_autocomplete: bool
    supports_topic_ids: bool
    supports_historical_depth: str
    max_keywords_per_request: int
    cache_ttl_seconds: int
    notes: List[str]


# Purpose: GoogleTrendsDataConfidence implementation
class GoogleTrendsDataConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    BLOCKED = "blocked"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


# Purpose: GoogleTrendsProviderAdapter implementation
class GoogleTrendsProviderAdapter(Protocol):
    provider_name: str
    capabilities: GoogleTrendsProviderCapabilities

    # Purpose: is available implementation
    def is_available(self) -> bool:
        ...

    # Purpose: get trends implementation
    def get_trends(self, request: GoogleTrendsRequest) -> GoogleTrendsResult:
        ...


def _build_trends_provider_capabilities(
    *,
    provider: str,
    supports_time_series: bool,
    supports_related_queries: bool,
    supports_related_topics: bool,
    supports_geo_breakdown: bool,
    supports_trending_now: bool,
    supports_autocomplete: bool,
    supports_topic_ids: bool,
    supports_historical_depth: str,
    max_keywords_per_request: int,
    cache_ttl_seconds: int,
    notes: List[str],
) -> GoogleTrendsProviderCapabilities:
    return GoogleTrendsProviderCapabilities(
        provider=provider,
        supports_time_series=supports_time_series,
        supports_related_queries=supports_related_queries,
        supports_related_topics=supports_related_topics,
        supports_geo_breakdown=supports_geo_breakdown,
        supports_trending_now=supports_trending_now,
        supports_autocomplete=supports_autocomplete,
        supports_topic_ids=supports_topic_ids,
        supports_historical_depth=supports_historical_depth,
        max_keywords_per_request=max_keywords_per_request,
        cache_ttl_seconds=cache_ttl_seconds,
        notes=list(notes),
    )


def _coerce_trends_request_payload(payload: Any) -> GoogleTrendsRequest:
    if isinstance(payload, GoogleTrendsRequest):
        return payload
    if not isinstance(payload, dict):
        raise TypeError("request payload must be a dict or GoogleTrendsRequest")
    return GoogleTrendsRequest(**payload)


def _coerce_trends_items(payload: Any, item_type: type) -> List[Any]:
    if not isinstance(payload, list):
        return []
    items: List[Any] = []
    for item in payload:
        if isinstance(item, item_type):
            items.append(item)
        elif isinstance(item, dict):
            items.append(item_type(**item))
    return items


def _build_trends_result(
    *,
    request: GoogleTrendsRequest,
    provider: str,
    interest_over_time: Optional[List[GoogleTrendsInterestPoint]] = None,
    averages: Optional[Dict[str, float]] = None,
    related_queries_top: Optional[List[GoogleTrendsRelatedItem]] = None,
    related_queries_rising: Optional[List[GoogleTrendsRelatedItem]] = None,
    related_topics_top: Optional[List[GoogleTrendsRelatedItem]] = None,
    related_topics_rising: Optional[List[GoogleTrendsRelatedItem]] = None,
    region_rows: Optional[List[GoogleTrendsRegionRow]] = None,
    warnings: Optional[List[str]] = None,
    failures: Optional[List[GoogleTrendsFailure]] = None,
    provider_metadata: Optional[Dict[str, Any]] = None,
    cache_metadata: Optional[Dict[str, Any]] = None,
    data_confidence: str = GoogleTrendsDataConfidence.UNKNOWN.value,
    integrity_warnings: Optional[List[str]] = None,
) -> GoogleTrendsResult:
    return GoogleTrendsResult(
        request=request,
        provider=provider,
        interest_over_time=list(interest_over_time or []),
        averages=dict(averages or {}),
        related_queries_top=list(related_queries_top or []),
        related_queries_rising=list(related_queries_rising or []),
        related_topics_top=list(related_topics_top or []),
        related_topics_rising=list(related_topics_rising or []),
        region_rows=list(region_rows or []),
        warnings=list(warnings or []),
        failures=list(failures or []),
        provider_metadata=dict(provider_metadata or {}),
        cache_metadata=dict(cache_metadata or {}),
        data_confidence=data_confidence,
        integrity_warnings=list(integrity_warnings or []),
    )


TRENDS_PROVIDER_REGISTRY: Dict[str, GoogleTrendsProviderAdapter] = {}
TRENDS_PROVIDER_OPTIONS: List[str] = []


# Purpose: register trends provider implementation
def register_trends_provider(name: str, adapter: GoogleTrendsProviderAdapter) -> None:
    TRENDS_PROVIDER_REGISTRY[name] = adapter
    if name not in TRENDS_PROVIDER_OPTIONS:
        TRENDS_PROVIDER_OPTIONS.append(name)


# Purpose:  normalize text implementation
def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


# Purpose:  normalize keywords implementation
def _normalize_keywords(keywords: Sequence[str]) -> List[str]:
    seen: set[str] = set()
    normalized: List[str] = []
    for keyword in keywords or []:
        cleaned = _normalize_text(keyword)
        if not cleaned:
            continue
        dedupe_key = cleaned.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized.append(cleaned)
    return normalized


# Purpose:  canonical json implementation
def _canonical_json(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


# Purpose:  first numeric implementation
def _first_numeric(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value))
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return int(round(float(text)))
        except ValueError:
            return None
    if isinstance(value, (list, tuple)):
        for item in value:
            numeric = _first_numeric(item)
            if numeric is not None:
                return numeric
    return None


# Purpose:  safe round value implementation
def _safe_round_value(value: float) -> int:
    return max(0, min(100, int(round(value))))


# Purpose:  strip anti xssi implementation
def _strip_anti_xssi(text: str) -> str:
    raw = text or ""
    for prefix in ANTI_XSSI_PREFIXES:
        if raw.startswith(prefix):
            return raw[len(prefix) :].lstrip()
    return raw.lstrip()


# Purpose:  google trends settings implementation
def _google_trends_settings() -> Dict[str, Any]:
    cfg = getattr(settings, "GOOGLE_TRENDS_CONFIG", {})
    return cfg if isinstance(cfg, dict) else {}


# Purpose:  google trends setting value implementation
def _google_trends_setting_value(name: str, default: Any = None) -> Any:
    return _google_trends_settings().get(name, default)


# Purpose:  configured trends max keywords implementation
def _configured_trends_max_keywords(default: int) -> int:
    try:
        value = _google_trends_setting_value("max_keywords_per_request", default)
        return max(1, int(value))
    except (TypeError, ValueError):
        return max(1, int(default))


# Purpose:  looks like url implementation
def _looks_like_url(value: str) -> bool:
    if not value:
        return False
    text = str(value).strip()
    if not text:
        return False
    if re.match(r"^(https?://|www\.)", text, re.IGNORECASE):
        return True
    return re.match(r"^[a-zA-Z0-9-]+\.[a-zA-Z]{2,}", text) is not None


# Purpose:  trends request from settings implementation
def _trends_request_from_settings(
    keywords: List[str],
    trends_config: Optional[Dict[str, Any]] = None,
) -> GoogleTrendsRequest:
    values = dict(trends_config or {})
    return GoogleTrendsRequest(
        keywords=keywords,
        geo=str(values.get("default_geo", values.get("geo", "UA")) or "UA"),
        timeframe=str(
            values.get("default_timeframe", values.get("timeframe", "today 12-m"))
            or "today 12-m"
        ),
        category=int(values.get("default_category", values.get("category", 0)) or 0),
        gprop=str(values.get("default_property", values.get("gprop", "")) or ""),
        hl=str(values.get("default_language", values.get("hl", "en-US")) or "en-US"),
        tz=int(values.get("default_timezone", values.get("tz", 0)) or 0),
        batch_size=int(values.get("batch_size", 5) or 5),
        max_keywords_per_request=int(
            values.get(
                "max_keywords_per_request",
                _configured_trends_max_keywords(MAX_BATCH_SIZE),
            )
            or MAX_BATCH_SIZE
        ),
        anchor_keyword=values.get("anchor_keyword") or None,
        include_interest_over_time=bool(
            values.get("include_interest_over_time", True)
        ),
        include_related=bool(values.get("include_related", True)),
        include_region=bool(values.get("include_region", False)),
    )


# Purpose:  trends endpoint mode implementation
def _trends_endpoint_mode(request: GoogleTrendsRequest) -> str:
    modes: List[str] = []
    if request.include_interest_over_time:
        modes.append("interestByTime")
    if request.include_related:
        modes.append("relatedQueries+relatedTopics")
    if request.include_region:
        modes.append("interestByRegion")
    if not modes:
        modes.append("disabled")
    return "trends." + "+".join(modes)


# Purpose:  trends batch composition implementation
def _trends_batch_composition(request: GoogleTrendsRequest) -> Dict[str, Any]:
    return {
        "keywords": list(request.keywords),
        "batch_size": request.batch_size,
        "max_keywords_per_request": request.max_keywords_per_request,
        "anchor_keyword": request.anchor_keyword,
    }


# Purpose:  trends provider version implementation
def _trends_provider_version(provider_name: str, adapter: GoogleTrendsProviderAdapter) -> str:
    version = getattr(adapter, "provider_version", "")
    if version:
        return str(version)
    return {
        "dataforseo_trends": "dataforseo_trends_v1",
        "serpapi_trends": "serpapi_trends_v1",
        "scrapebadger_web": "scrapebadger_web_v1",
    }.get(provider_name, "unknown")


# Purpose:  trends cache ttl hours implementation
def _trends_cache_ttl_hours(provider_name: str, adapter: GoogleTrendsProviderAdapter) -> int:
    trends_cfg = _google_trends_settings()
    base_ttl = int(trends_cfg.get("cache_ttl_hours", 24) or 24)
    return base_ttl


# Purpose:  restore trends result from payload implementation
def _restore_trends_result_from_payload(payload: Any) -> Optional[GoogleTrendsResult]:
    return _restore_trends_result_payload(payload)


# Purpose:  restore typed trends result payload implementation
def _restore_trends_result_payload(payload: Any) -> Optional[GoogleTrendsResult]:
    if isinstance(payload, GoogleTrendsResult):
        return payload
    if not isinstance(payload, dict):
        return None

    try:
        request = _coerce_trends_request_payload(payload.get("request") or {})
        return _build_trends_result(
            request=request,
            provider=str(payload.get("provider", DEFAULT_PROVIDER_NAME)),
            interest_over_time=_coerce_trends_items(
                payload.get("interest_over_time", []), GoogleTrendsInterestPoint
            ),
            averages=dict(payload.get("averages", {}) or {}),
            related_queries_top=_coerce_trends_items(
                payload.get("related_queries_top", []), GoogleTrendsRelatedItem
            ),
            related_queries_rising=_coerce_trends_items(
                payload.get("related_queries_rising", []), GoogleTrendsRelatedItem
            ),
            related_topics_top=_coerce_trends_items(
                payload.get("related_topics_top", []), GoogleTrendsRelatedItem
            ),
            related_topics_rising=_coerce_trends_items(
                payload.get("related_topics_rising", []), GoogleTrendsRelatedItem
            ),
            region_rows=_coerce_trends_items(payload.get("region_rows", []), GoogleTrendsRegionRow),
            warnings=list(payload.get("warnings", []) or []),
            failures=_coerce_trends_items(payload.get("failures", []), GoogleTrendsFailure),
            provider_metadata=dict(payload.get("provider_metadata", {}) or {}),
            cache_metadata=dict(payload.get("cache_metadata", {}) or {}),
            data_confidence=str(
                payload.get("data_confidence", GoogleTrendsDataConfidence.UNKNOWN.value)
            ),
            integrity_warnings=list(payload.get("integrity_warnings", []) or []),
        )
    except Exception as exc:
        logger.warning(f"Failed to restore cached Google Trends result: {exc}")
        return None


# Purpose:  parse json text implementation
def _parse_json_text(text: str) -> Dict[str, Any]:
    payload = json.loads(_strip_anti_xssi(text or ""))
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    return payload


# Purpose:  build provider failure result implementation
def _build_provider_failure_result(
    request: GoogleTrendsRequest,
    provider_name: str,
    failure: GoogleTrendsFailure,
    *,
    data_confidence: str = GoogleTrendsDataConfidence.BLOCKED.value,
    provider_metadata: Optional[Dict[str, Any]] = None,
    integrity_warning: Optional[str] = None,
) -> GoogleTrendsResult:
    result = _build_trends_result(
        request=request,
        provider=provider_name,
        data_confidence=data_confidence,
        provider_metadata=provider_metadata or {"provider": provider_name},
    )
    result.failures.append(failure)
    result.integrity_warnings.append(failure.message)
    if integrity_warning:
        result.integrity_warnings.append(integrity_warning)
    return result


# Purpose: Determine whether a Trends result is safe to cache and replay.
def _is_cacheable_trends_result(result: GoogleTrendsResult) -> bool:
    if not result.has_data():
        return False
    confidence = str(getattr(result, "data_confidence", "") or "").lower()
    if confidence in {
        GoogleTrendsDataConfidence.BLOCKED.value,
        GoogleTrendsDataConfidence.DEGRADED.value,
    }:
        return False
    return not any(failure.kind == "rate_limit" for failure in result.failures)


# Purpose:  dataforseo location params implementation
def _dataforseo_location_params(geo: str) -> Dict[str, Any]:
    normalized = _normalize_text(geo)
    if not normalized:
        return {}
    if normalized.isdigit():
        return {"location_code": int(normalized)}
    mapped_name = DATAFORSEO_LOCATION_NAME_MAP.get(normalized.upper(), normalized)
    return {"location_name": mapped_name}


# Purpose:  dataforseo time window params implementation
def _dataforseo_time_window_params(timeframe: str) -> Dict[str, Any]:
    normalized = _normalize_text(timeframe).lower()
    if not normalized:
        return {}

    mapped_range = DATAFORSEO_TIME_RANGE_MAP.get(normalized)
    if mapped_range:
        return {"time_range": mapped_range}

    date_values = re.findall(r"\d{4}-\d{2}-\d{2}", normalized)
    if len(date_values) >= 2:
        return {"date_from": date_values[0], "date_to": date_values[1]}

    if "12-m" in normalized:
        return {"time_range": "past_12_months"}
    if "5-y" in normalized:
        return {"time_range": "past_5_years"}
    if "1-m" in normalized:
        return {"time_range": "past_30_days"}
    if "7-d" in normalized:
        return {"time_range": "past_7_days"}
    return {"time_range": "past_12_months"}


# Purpose:  dataforseo item types implementation
def _dataforseo_item_types(request: GoogleTrendsRequest) -> List[str]:
    item_types: List[str] = []
    if request.include_interest_over_time:
        item_types.append(DATAFORSEO_ITEM_TYPES["interest_over_time"])
    if request.include_region:
        item_types.append(DATAFORSEO_ITEM_TYPES["interest_by_region"])
    if request.include_related:
        item_types.extend(
            [
                DATAFORSEO_ITEM_TYPES["related_queries"],
                DATAFORSEO_ITEM_TYPES["related_topics"],
            ]
        )
    return item_types or [DATAFORSEO_ITEM_TYPES["interest_over_time"]]


# Purpose:  estimate alpha time window implementation
def _estimate_alpha_time_window(timeframe: str) -> Dict[str, Any]:
    normalized = _normalize_text(timeframe).lower()
    now = datetime.now(timezone.utc)
    delta = timedelta(days=365)
    label = "year"
    if "5-y" in normalized:
        delta = timedelta(days=365 * 5)
        label = "5-years"
    elif "1-m" in normalized:
        delta = timedelta(days=30)
        label = "month"
    elif "7-d" in normalized:
        delta = timedelta(days=7)
        label = "week"
    elif "1-d" in normalized:
        delta = timedelta(days=1)
        label = "day"
    elif "1-h" in normalized or "4-h" in normalized:
        hours = 1 if "1-h" in normalized else 4
        delta = timedelta(hours=hours)
        label = "hours"
    start = now - delta
    if delta >= timedelta(days=365 * 4):
        points = 5 * 12
    elif delta >= timedelta(days=365):
        points = 12
    elif delta >= timedelta(days=30):
        points = 30
    elif delta >= timedelta(days=7):
        points = 7
    elif delta >= timedelta(days=1):
        points = 24
    else:
        points = max(1, int(delta.total_seconds() // 3600) or 1)
    return {
        "startTime": start.isoformat().replace("+00:00", "Z"),
        "endTime": now.isoformat().replace("+00:00", "Z"),
        "estimated_points": points,
        "window_label": label,
    }




# Purpose: GoogleTrendsFailure implementation
# Purpose: GoogleTrendsFailure implementation
@dataclass
class GoogleTrendsFailure:
    kind: str
    message: str
    retryable: bool = False
    status_code: Optional[int] = None
    source: str = ""
    batch_index: Optional[int] = None
    source_keywords: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    # Purpose: to dict implementation
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Purpose: GoogleTrendsError implementation
class GoogleTrendsError(RuntimeError):
    # Purpose:   init   implementation
    def __init__(self, failure: GoogleTrendsFailure):
        super().__init__(failure.message)
        self.failure = failure

    # Purpose: retryable implementation
    # Purpose: retryable implementation
    @property
    def retryable(self) -> bool:
        return self.failure.retryable

    # Purpose:   str   implementation
    def __str__(self) -> str:
        return f"[{self.failure.kind}] {self.failure.message}"


# Purpose: GoogleTrendsRequest implementation
# Purpose: GoogleTrendsRequest implementation
@dataclass
class GoogleTrendsRequest:
    keywords: List[str]
    geo: str = "UA"
    timeframe: str = "today 12-m"
    category: int = 0
    gprop: str = ""
    hl: str = "en-US"
    tz: int = 0
    batch_size: int = MAX_BATCH_SIZE
    max_keywords_per_request: int = MAX_BATCH_SIZE
    anchor_keyword: Optional[str] = None
    include_interest_over_time: bool = True
    include_related: bool = True
    include_region: bool = False

    # Purpose:   post init   implementation
    def __post_init__(self) -> None:
        self.keywords = _normalize_keywords(self.keywords)
        if not self.keywords:
            raise ValueError("keywords must contain at least one keyword")

        self.geo = _normalize_text(self.geo).upper()
        if self.geo and len(self.geo) != 2:
            raise ValueError(f"Invalid geo code: {self.geo}")

        self.timeframe = _normalize_text(self.timeframe)
        if not self.timeframe:
            raise ValueError("timeframe must not be empty")

        self.gprop = _normalize_text(self.gprop)
        self.hl = _normalize_text(self.hl) or "en-US"

        try:
            self.batch_size = int(self.batch_size)
        except (TypeError, ValueError):
            raise ValueError("batch_size must be an integer")
        self.batch_size = max(1, min(self.batch_size, MAX_BATCH_SIZE))

        try:
            self.max_keywords_per_request = int(self.max_keywords_per_request)
        except (TypeError, ValueError):
            raise ValueError("max_keywords_per_request must be an integer")
        self.max_keywords_per_request = max(1, self.max_keywords_per_request)

        if self.anchor_keyword is not None:
            anchor = _normalize_text(self.anchor_keyword)
            self.anchor_keyword = anchor or None

    # Purpose: to dict implementation
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Purpose: GoogleTrendsInterestPoint implementation
# Purpose: GoogleTrendsInterestPoint implementation
@dataclass
class GoogleTrendsInterestPoint:
    time: str
    formatted_time: str
    values: Dict[str, Optional[int]]
    source_batches: List[int] = field(default_factory=list)

    # Purpose: to dict implementation
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Purpose: GoogleTrendsRelatedItem implementation
# Purpose: GoogleTrendsRelatedItem implementation
@dataclass
class GoogleTrendsRelatedItem:
    label: str
    value: Any
    rank_type: str
    item_type: str
    topic_type: str = ""
    source_keywords: List[str] = field(default_factory=list)
    source_batches: List[int] = field(default_factory=list)

    # Purpose: to dict implementation
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Purpose: GoogleTrendsRegionRow implementation
# Purpose: GoogleTrendsRegionRow implementation
@dataclass
class GoogleTrendsRegionRow:
    region: str
    value: Optional[int]
    keyword: str = ""
    source_batches: List[int] = field(default_factory=list)

    # Purpose: to dict implementation
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Purpose: GoogleTrendsResult implementation
# Purpose: GoogleTrendsResult implementation
@dataclass
class GoogleTrendsResult:
    request: GoogleTrendsRequest
    provider: str = DEFAULT_PROVIDER_NAME
    interest_over_time: List[GoogleTrendsInterestPoint] = field(default_factory=list)
    averages: Dict[str, float] = field(default_factory=dict)
    related_queries_top: List[GoogleTrendsRelatedItem] = field(default_factory=list)
    related_queries_rising: List[GoogleTrendsRelatedItem] = field(default_factory=list)
    related_topics_top: List[GoogleTrendsRelatedItem] = field(default_factory=list)
    related_topics_rising: List[GoogleTrendsRelatedItem] = field(default_factory=list)
    region_rows: List[GoogleTrendsRegionRow] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    failures: List[GoogleTrendsFailure] = field(default_factory=list)
    provider_metadata: Dict[str, Any] = field(default_factory=dict)
    cache_metadata: Dict[str, Any] = field(default_factory=dict)
    data_confidence: str = GoogleTrendsDataConfidence.UNKNOWN.value
    integrity_warnings: List[str] = field(default_factory=list)

    # Purpose: has data implementation
    def has_data(self) -> bool:
        return any(
            (
                self.interest_over_time,
                self.related_queries_top,
                self.related_queries_rising,
                self.related_topics_top,
                self.related_topics_rising,
                self.region_rows,
            )
        )

    # Purpose: to dict implementation
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
# Purpose: GoogleTrendsClient implementation
class GoogleTrendsClient:
    # FUNCTION_CONTRACT: GoogleTrendsClient.__init__
    # Purpose: Initialize Google Trends HTTP client with configurable retry and timeout settings
    # Input: timeout_seconds (int), batch_delay_seconds (float), max_retries (int), retry_backoff (float), user_agent (str)
    # Output: None (constructor)
    # Side Effects: Creates requests.Session, loads runtime config from settings
    # Business Rules: Uses exponential backoff for retries; respects config/google_trends settings
    # Failure Modes: Settings load errors are silently ignored (fallback to defaults)
    # LINKS: requirements.xml#UC-010
    # SEMANTIC_BLOCK: block_trends_request_validation
    def __init__(
        self,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        batch_delay_seconds: float = DEFAULT_BATCH_DELAY_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_backoff: float = DEFAULT_RETRY_BACKOFF,
        user_agent: str = DEFAULT_USER_AGENT,
        provider_name: Optional[str] = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.batch_delay_seconds = batch_delay_seconds
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.user_agent = user_agent
        self.provider_name = provider_name or DEFAULT_PROVIDER_NAME
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self.cache_ttl_hours = 24
        self._load_runtime_config()

        adapter = TRENDS_PROVIDER_REGISTRY.get(self.provider_name)
        if adapter is not None:
            try:
                adapter = type(adapter)(self)
            except Exception:
                pass
        self.active_adapter = adapter

    # Purpose: Close the underlying HTTP session and adapter session to release connections.
    def close(self) -> None:
        try:
            self.session.close()
        except Exception:
            pass
        if self.active_adapter is not None and hasattr(self.active_adapter, "session"):
            try:
                self.active_adapter.session.close()
            except Exception:
                pass

    # Purpose:   enter   implementation
    def __enter__(self) -> "GoogleTrendsClient":
        return self

    # Purpose:   exit   implementation
    def __exit__(self, *exc: Any) -> None:
        self.close()

    # Purpose:  load runtime config implementation
    def _load_runtime_config(self) -> None:
        try:
            cfg = load_config()
        except Exception:
            return

        trends_cfg = cfg.get("google_trends", {}) if isinstance(cfg, dict) else {}
        retry_cfg = cfg.get("retry", {}) if isinstance(cfg, dict) else {}
        if isinstance(trends_cfg, dict):
            self.timeout_seconds = int(trends_cfg.get("timeout_seconds", self.timeout_seconds))
            self.batch_delay_seconds = float(
                trends_cfg.get("batch_delay_seconds", self.batch_delay_seconds)
            )
            self.cache_ttl_hours = int(trends_cfg.get("cache_ttl_hours", self.cache_ttl_hours))
            if not self.provider_name or self.provider_name == "google_trends_direct":
                self.provider_name = trends_cfg.get("provider", self.provider_name or "google_trends_direct")
        if isinstance(retry_cfg, dict):
            self.max_retries = int(retry_cfg.get("max_attempts", self.max_retries))
            self.retry_backoff = float(retry_cfg.get("backoff_factor", self.retry_backoff))

    # Purpose:  build cache key implementation
    # Purpose:  build cache key implementation
    @staticmethod
    def _build_cache_key(request: GoogleTrendsRequest) -> str:
        payload = {
            "anchor_keyword": request.anchor_keyword,
            "batch_size": request.batch_size,
            "category": request.category,
            "geo": request.geo,
            "gprop": request.gprop,
            "hl": request.hl,
            "include_interest_over_time": request.include_interest_over_time,
            "include_related": request.include_related,
            "include_region": request.include_region,
            "keywords": sorted(request.keywords, key=lambda value: value.lower()),
            "max_keywords_per_request": request.max_keywords_per_request,
            "timeframe": request.timeframe,
            "tz": request.tz,
            "version": MODULE_VERSION,
        }
        digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
        return digest

    # Purpose:  extract widgets implementation
    @staticmethod
    def _extract_widgets(explore_payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        widgets: Dict[str, Dict[str, Any]] = {}
        for widget in explore_payload.get("widgets", []) or []:
            if not isinstance(widget, dict):
                continue
            widget_id = _normalize_text(widget.get("id"))
            token = _normalize_text(widget.get("token"))
            request = widget.get("request")
            if not widget_id or not token or request is None:
                continue
            widget_id_lower = widget_id.lower()
            if "timeseries" in widget_id_lower:
                widgets["interest_over_time"] = {"id": widget_id, "token": token, "request": request}
            elif "related_quer" in widget_id_lower:
                widgets["related_queries"] = {"id": widget_id, "token": token, "request": request}
            elif "related_topic" in widget_id_lower:
                widgets["related_topics"] = {"id": widget_id, "token": token, "request": request}
            elif "geo" in widget_id_lower:
                widgets["region"] = {"id": widget_id, "token": token, "request": request}
        return widgets

    # Purpose:  parse timeline implementation
    @staticmethod
    def _parse_timeline(
        payload: Dict[str, Any],
        batch_keywords: Sequence[str],
        batch_index: int,
    ) -> List[GoogleTrendsInterestPoint]:
        timeline = payload.get("default", {}).get("timelineData", []) or []
        points: List[GoogleTrendsInterestPoint] = []
        for entry in timeline:
            if not isinstance(entry, dict):
                continue
            time_key = _normalize_text(entry.get("time"))
            formatted_time = _normalize_text(
                entry.get("formattedTime") or entry.get("formattedAxisTime") or time_key
            )
            values = entry.get("value", []) or []
            row_values: Dict[str, Optional[int]] = {}
            for index, keyword in enumerate(batch_keywords):
                row_values[keyword] = _first_numeric(values[index]) if index < len(values) else None
            points.append(
                GoogleTrendsInterestPoint(
                    time=time_key,
                    formatted_time=formatted_time,
                    values=row_values,
                    source_batches=[batch_index],
                )
            )
        return points

    # Purpose:  parse related implementation
    # Purpose:  parse related implementation
    @staticmethod
    def _parse_related(
        payload: Dict[str, Any],
        batch_keywords: Sequence[str],
        batch_index: int,
        widget_type: str,
    ) -> tuple[List[GoogleTrendsRelatedItem], List[GoogleTrendsRelatedItem]]:
        top_items: List[GoogleTrendsRelatedItem] = []
        rising_items: List[GoogleTrendsRelatedItem] = []
        ranked_lists = payload.get("default", {}).get("rankedList", []) or []
        for ranked_list in ranked_lists:
            if not isinstance(ranked_list, dict):
                continue
            rank_type = _normalize_text(ranked_list.get("formattedRankType")).lower()
            ranked_keyword_items = ranked_list.get("rankedKeyword", []) or []
            for item in ranked_keyword_items:
                if not isinstance(item, dict):
                    continue
                if widget_type == "related_topics":
                    topic = item.get("topic", {}) or {}
                    label = _normalize_text(topic.get("title") or topic.get("name") or item.get("title"))
                    topic_type = _normalize_text(topic.get("type"))
                    value = item.get("value")
                    related_item = GoogleTrendsRelatedItem(
                        label=label,
                        value=value,
                        rank_type=rank_type or "top",
                        item_type="topic",
                        topic_type=topic_type,
                        source_keywords=list(batch_keywords),
                        source_batches=[batch_index],
                    )
                else:
                    label = _normalize_text(item.get("query") or item.get("title") or item.get("text"))
                    value = item.get("value")
                    related_item = GoogleTrendsRelatedItem(
                        label=label,
                        value=value,
                        rank_type=rank_type or "top",
                        item_type="query",
                        source_keywords=list(batch_keywords),
                        source_batches=[batch_index],
                    )

                if not label:
                    continue

                if "rising" in rank_type or "breakout" in rank_type:
                    rising_items.append(related_item)
                else:
                    top_items.append(related_item)
        return top_items, rising_items

    # Purpose:  parse region implementation
    # Purpose:  parse region implementation
    @staticmethod
    def _parse_region(
        payload: Dict[str, Any],
        keyword: str,
        batch_index: int,
    ) -> List[GoogleTrendsRegionRow]:
        rows: List[GoogleTrendsRegionRow] = []
        geo_map = payload.get("default", {}).get("geoMapData", []) or []
        for item in geo_map:
            if not isinstance(item, dict):
                continue
            region = _normalize_text(item.get("geoName") or item.get("geo") or item.get("name"))
            if not region:
                continue
            value = _first_numeric(item.get("value"))
            rows.append(
                GoogleTrendsRegionRow(
                    region=region,
                    value=value,
                    keyword=keyword,
                    source_batches=[batch_index],
                )
            )
        return rows

    # Purpose:  merge interest points implementation
    # Purpose:  merge interest points implementation
    @staticmethod
    def _merge_interest_points(points: List[GoogleTrendsInterestPoint]) -> List[GoogleTrendsInterestPoint]:
        merged: Dict[tuple[str, str], GoogleTrendsInterestPoint] = {}
        for point in points:
            key = (point.time, point.formatted_time)
            existing = merged.get(key)
            if existing is None:
                merged[key] = GoogleTrendsInterestPoint(
                    time=point.time,
                    formatted_time=point.formatted_time,
                    values=dict(point.values),
                    source_batches=list(point.source_batches),
                )
                continue
            for keyword, value in point.values.items():
                if value is not None:
                    existing.values[keyword] = value
            for batch_index in point.source_batches:
                if batch_index not in existing.source_batches:
                    existing.source_batches.append(batch_index)
        return list(merged.values())

    # Purpose:  calculate averages implementation
    # Purpose:  calculate averages implementation
    @staticmethod
    def _calculate_averages(points: List[GoogleTrendsInterestPoint]) -> Dict[str, float]:
        totals: Dict[str, List[int]] = {}
        for point in points:
            for keyword, value in point.values.items():
                if value is None:
                    continue
                totals.setdefault(keyword, []).append(int(value))
        return {
            keyword: (sum(values) / len(values) if values else 0.0)
            for keyword, values in totals.items()
        }

    # Purpose:  dedupe related implementation
    # Purpose:  dedupe related implementation
    @staticmethod
    def _dedupe_related(items: List[GoogleTrendsRelatedItem]) -> List[GoogleTrendsRelatedItem]:
        seen: set[tuple[Any, ...]] = set()
        deduped: List[GoogleTrendsRelatedItem] = []
        for item in items:
            key = (
                item.item_type,
                item.rank_type,
                item.label.lower(),
                str(item.value),
                item.topic_type.lower(),
                tuple(item.source_keywords),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    # Purpose:  dedupe regions implementation
    # Purpose:  dedupe regions implementation
    @staticmethod
    def _dedupe_regions(items: List[GoogleTrendsRegionRow]) -> List[GoogleTrendsRegionRow]:
        seen: set[tuple[Any, ...]] = set()
        deduped: List[GoogleTrendsRegionRow] = []
        for item in items:
            key = (item.keyword.lower(), item.region.lower(), item.value)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped
    # Purpose: get trends implementation
    # Purpose: get trends implementation
    def get_trends(self, request: GoogleTrendsRequest) -> GoogleTrendsResult:
        caps = getattr(self.active_adapter, "capabilities", None) if self.active_adapter else None
        adapter_max = (
            getattr(caps, "max_keywords_per_request", MAX_BATCH_SIZE) if caps else MAX_BATCH_SIZE
        )
        if self.provider_name == DEFAULT_PROVIDER_NAME:
            adapter_max = int(
                getattr(
                    request,
                    "max_keywords_per_request",
                    _configured_trends_max_keywords(adapter_max),
                )
                or adapter_max
            )
        if not request.anchor_keyword and len(request.keywords) > adapter_max:
            return _build_trends_result(
                request=request,
                provider=self.provider_name,
                provider_metadata={"provider": self.provider_name},
                cache_metadata={},
                data_confidence=GoogleTrendsDataConfidence.BLOCKED.value,
                failures=[
                    GoogleTrendsFailure(
                        kind="too_many_keywords",
                        message=f"Provider {self.provider_name} supports max {adapter_max} keywords without anchor",
                        retryable=False,
                        source=self.provider_name,
                        details={"max_keywords": adapter_max, "requested": len(request.keywords)},
                    )
                ],
            )

        if not self.active_adapter:
            return _build_trends_result(
                request=request,
                provider=self.provider_name,
                provider_metadata={"provider": self.provider_name},
                cache_metadata={},
                data_confidence=GoogleTrendsDataConfidence.BLOCKED.value,
                failures=[
                    GoogleTrendsFailure(
                        kind="provider_unavailable",
                        message=f"No adapter registered for provider: {self.provider_name}",
                        retryable=False,
                        source=self.provider_name,
                    )
                ],
            )

        result = self.active_adapter.get_trends(request)
        result.provider = self.provider_name
        return result


class _SessionBackedTrendsAdapter(GoogleTrendsProviderAdapter):
    client: Optional[GoogleTrendsClient]

    def __init__(self, client: Optional[GoogleTrendsClient] = None) -> None:
        self.client = client
        self.session = requests.Session()

    def close(self) -> None:
        try:
            self.session.close()
        except Exception:
            pass

    @property
    def active_client(self) -> GoogleTrendsClient:
        if self.client is None:
            self.client = GoogleTrendsClient(provider_name="google_trends_direct")
        return self.client


# Purpose: SerpApiTrendsAdapter implementation
class SerpApiTrendsAdapter(_SessionBackedTrendsAdapter):
    provider_name: str = "serpapi_trends"

    # Purpose:   init   implementation
    def __init__(self, client: Optional[GoogleTrendsClient] = None) -> None:
        super().__init__(client)
        self.capabilities = _build_trends_provider_capabilities(
            provider=self.provider_name,
            supports_time_series=True,
            supports_related_queries=True,
            supports_related_topics=True,
            supports_geo_breakdown=True,
            supports_trending_now=True,
            supports_autocomplete=False,
            supports_topic_ids=False,
            supports_historical_depth="years",
            max_keywords_per_request=5,
            cache_ttl_seconds=86400,
            notes=["Production provider. Requires SERPAPI_KEY."],
        )

    # Purpose: is available implementation
    def is_available(self) -> bool:
        return bool(os.environ.get("SERPAPI_KEY", "").strip())

    # Purpose:  requested data types implementation
    # Purpose:  requested data types implementation
    @staticmethod
    def _requested_data_types(request: GoogleTrendsRequest) -> List[str]:
        data_types: List[str] = []
        if request.include_interest_over_time:
            data_types.append("TIMESERIES")
        if request.include_region:
            data_types.append("GEO_MAP")
        if request.include_related:
            data_types.extend(["RELATED_QUERIES", "RELATED_TOPICS"])
        return data_types[:4]

    # Purpose:  build params implementation
    # Purpose:  build params implementation
    @staticmethod
    def _build_params(request: GoogleTrendsRequest, data_type: str) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "engine": "google_trends",
            "data_type": data_type,
            "q": "|".join(request.keywords),
            "geo": request.geo,
            "category": request.category,
        }
        if request.gprop:
            params["gprop"] = request.gprop
        if request.timeframe:
            params["time_range"] = request.timeframe
        return params

    # Purpose:  parse timeseries implementation
    # Purpose:  parse timeseries implementation
    @staticmethod
    def _parse_timeseries(
        payload: Dict[str, Any],
        request: GoogleTrendsRequest,
    ) -> List[GoogleTrendsInterestPoint]:
        timeline = payload.get("interest_over_time", {}).get("timeline_data", []) or []
        points: List[GoogleTrendsInterestPoint] = []
        keywords = list(request.keywords)
        for entry in timeline:
            if not isinstance(entry, dict):
                continue
            values = entry.get("values", []) or []
            row_values: Dict[str, Optional[int]] = {}
            for index, keyword in enumerate(keywords):
                value = None
                if index < len(values) and isinstance(values[index], dict):
                    value = values[index].get("extracted_value", values[index].get("value"))
                elif index < len(values):
                    value = values[index]
                row_values[keyword] = _first_numeric(value)
            points.append(
                GoogleTrendsInterestPoint(
                    time=str(entry.get("timestamp") or entry.get("time") or ""),
                    formatted_time=_normalize_text(
                        entry.get("date")
                        or entry.get("formattedTime")
                        or entry.get("formatted_axis_time")
                        or entry.get("timestamp")
                    ),
                    values=row_values,
                )
            )
        return points

    # Purpose:  parse related items implementation
    # Purpose:  parse related items implementation
    @staticmethod
    def _build_related_item_from_section_item(
        item: Dict[str, Any],
        request: GoogleTrendsRequest,
        *,
        rank_type: str,
        use_topics: bool,
    ) -> Optional[GoogleTrendsRelatedItem]:
        if use_topics:
            topic = item.get("topic") or {}
            label = _normalize_text(topic.get("title") or topic.get("name") or item.get("topic_title"))
            topic_type = _normalize_text(topic.get("type") or item.get("topic_type"))
            if not label:
                return None
            return GoogleTrendsRelatedItem(
                label=label,
                value=item.get("value"),
                rank_type=rank_type,
                item_type="topic",
                topic_type=topic_type,
                source_keywords=list(request.keywords),
            )

        label = _normalize_text(item.get("query") or item.get("title") or item.get("text"))
        if not label:
            return None
        return GoogleTrendsRelatedItem(
            label=label,
            value=item.get("value"),
            rank_type=rank_type,
            item_type="query",
            source_keywords=list(request.keywords),
        )

    @staticmethod
    def _parse_related_items(
        payload: Dict[str, Any],
        request: GoogleTrendsRequest,
        *,
        use_topics: bool,
    ) -> tuple[List[GoogleTrendsRelatedItem], List[GoogleTrendsRelatedItem]]:
        section = payload.get("related_topics" if use_topics else "related_queries", {}) or {}
        top_items: List[GoogleTrendsRelatedItem] = []
        rising_items: List[GoogleTrendsRelatedItem] = []
        for item in section.get("top", []) or []:
            if not isinstance(item, dict):
                continue
            related = SerpApiTrendsAdapter._build_related_item_from_section_item(
                item,
                request,
                rank_type="top",
                use_topics=use_topics,
            )
            if related is not None:
                top_items.append(related)
        for item in section.get("rising", []) or []:
            if not isinstance(item, dict):
                continue
            related = SerpApiTrendsAdapter._build_related_item_from_section_item(
                item,
                request,
                rank_type="rising",
                use_topics=use_topics,
            )
            if related is not None:
                rising_items.append(related)
        return top_items, rising_items

    # Purpose:  parse regions implementation
    # Purpose:  parse regions implementation
    @staticmethod
    def _parse_regions(
        payload: Dict[str, Any],
        request: GoogleTrendsRequest,
    ) -> List[GoogleTrendsRegionRow]:
        rows: List[GoogleTrendsRegionRow] = []
        for item in payload.get("interest_by_region", {}).get("geo_map_data", []) or []:
            if not isinstance(item, dict):
                continue
            region = _normalize_text(item.get("geo_name") or item.get("geoName") or item.get("geo") or item.get("name"))
            if not region:
                continue
            rows.append(
                GoogleTrendsRegionRow(
                    region=region,
                    value=_first_numeric(item.get("value")),
                    keyword=", ".join(request.keywords),
                )
            )
        return rows

    # Purpose: get trends implementation
    def get_trends(self, request: GoogleTrendsRequest) -> GoogleTrendsResult:
        if not self.is_available():
            return _build_provider_failure_result(
                request,
                self.provider_name,
                GoogleTrendsFailure(
                    kind="provider_unavailable",
                    message="SERPAPI_KEY is not configured",
                    source="serpapi",
                ),
                provider_metadata={"provider": self.provider_name, "endpoint": "search.json"},
            )

        requested_data_types = self._requested_data_types(request)
        skipped_data_types = []
        if len(requested_data_types) > 4:
            skipped_data_types = requested_data_types[4:]
            requested_data_types = requested_data_types[:4]

        result = GoogleTrendsResult(
            request=request,
            provider=self.provider_name,
            provider_metadata={
                "provider": self.provider_name,
                "endpoint": "search.json?engine=google_trends",
                "requested_data_types": list(requested_data_types),
                "completed_data_types": [],
                "failed_data_types": [],
                "search_metadata": {},
                "search_ids": [],
            },
            data_confidence=GoogleTrendsDataConfidence.HIGH.value,
        )
        if skipped_data_types:
            warning = f"Skipped SerpApi data types due to fanout cap: {', '.join(skipped_data_types)}"
            result.integrity_warnings.append(warning)
            result.warnings.append(warning)

        all_interest_points: List[GoogleTrendsInterestPoint] = []
        all_related_queries_top: List[GoogleTrendsRelatedItem] = []
        all_related_queries_rising: List[GoogleTrendsRelatedItem] = []
        all_related_topics_top: List[GoogleTrendsRelatedItem] = []
        all_related_topics_rising: List[GoogleTrendsRelatedItem] = []
        all_region_rows: List[GoogleTrendsRegionRow] = []
        search_metadata_by_type: Dict[str, Dict[str, Any]] = {}
        data_types_with_data: List[str] = []

        for data_type in requested_data_types:
            params = self._build_params(request, data_type)
            try:
                headers = {"Authorization": f"Bearer {os.environ.get('SERPAPI_KEY', '')}"}
                response = self.session.get(
                    "https://serpapi.com/search.json",
                    params=params,
                    headers=headers,
                    timeout=self.active_client.timeout_seconds,
                )
            except requests.Timeout as exc:
                failure = GoogleTrendsFailure(
                    kind="provider_task_error",
                    message="SerpApi request timed out",
                    retryable=True,
                    source="serpapi",
                    details={"error": str(exc), "data_type": data_type},
                )
                result.failures.append(failure)
                result.data_confidence = GoogleTrendsDataConfidence.BLOCKED.value
                result.provider_metadata["failed_data_types"].append(data_type)
                continue
            except requests.RequestException as exc:
                failure = GoogleTrendsFailure(
                    kind="provider_task_error",
                    message="SerpApi request failed",
                    retryable=True,
                    source="serpapi",
                    details={"error": str(exc), "data_type": data_type},
                )
                result.failures.append(failure)
                result.data_confidence = GoogleTrendsDataConfidence.BLOCKED.value
                result.provider_metadata["failed_data_types"].append(data_type)
                continue

            if response.status_code == 429:
                failure = GoogleTrendsFailure(
                    kind="provider_quota",
                    message="SerpApi rate limit reached",
                    retryable=True,
                    status_code=429,
                    source="serpapi",
                    details={"data_type": data_type},
                )
                result.failures.append(failure)
                result.data_confidence = GoogleTrendsDataConfidence.BLOCKED.value
                result.provider_metadata["failed_data_types"].append(data_type)
                break

            if response.status_code in {401, 403}:
                failure = GoogleTrendsFailure(
                    kind="provider_auth",
                    message="SerpApi authentication failed",
                    status_code=response.status_code,
                    source="serpapi",
                    details={"data_type": data_type},
                )
                result.failures.append(failure)
                result.data_confidence = GoogleTrendsDataConfidence.BLOCKED.value
                result.provider_metadata["failed_data_types"].append(data_type)
                break

            if response.status_code >= 400:
                failure = GoogleTrendsFailure(
                    kind="provider_task_error",
                    message="SerpApi returned an HTTP error",
                    retryable=response.status_code >= 500,
                    status_code=response.status_code,
                    source="serpapi",
                    details={"data_type": data_type, "status_code": response.status_code},
                )
                result.failures.append(failure)
                result.provider_metadata["failed_data_types"].append(data_type)
                result.data_confidence = GoogleTrendsDataConfidence.BLOCKED.value
                continue

            try:
                payload = response.json()
            except ValueError as exc:
                failure = GoogleTrendsFailure(
                    kind="provider_task_error",
                    message="SerpApi returned malformed JSON",
                    status_code=response.status_code,
                    source="serpapi",
                    details={"error": str(exc), "data_type": data_type},
                )
                result.failures.append(failure)
                result.provider_metadata["failed_data_types"].append(data_type)
                result.data_confidence = GoogleTrendsDataConfidence.BLOCKED.value
                continue

            if not isinstance(payload, dict):
                failure = GoogleTrendsFailure(
                    kind="provider_task_error",
                    message="SerpApi returned an unexpected payload",
                    status_code=response.status_code,
                    source="serpapi",
                    details={"data_type": data_type},
                )
                result.failures.append(failure)
                result.provider_metadata["failed_data_types"].append(data_type)
                result.data_confidence = GoogleTrendsDataConfidence.BLOCKED.value
                continue

            search_metadata = payload.get("search_metadata", {}) or {}
            status = _normalize_text(search_metadata.get("status"))
            search_metadata_by_type[data_type] = search_metadata if isinstance(search_metadata, dict) else {}
            search_id = _normalize_text(search_metadata.get("id"))
            if search_id:
                result.provider_metadata["search_ids"].append(search_id)
            if status:
                result.provider_metadata["search_metadata"] = search_metadata

            if status == "Error":
                sanitized_details = _sanitize_details_for_cache(
                    {"data_type": data_type, "search_metadata": search_metadata, "body": payload}
                )
                failure = GoogleTrendsFailure(
                    kind="provider_task_error",
                    message=_normalize_text(payload.get("error") or search_metadata.get("error")) or "SerpApi task failed",
                    status_code=response.status_code,
                    source="serpapi",
                    details=sanitized_details,
                )
                result.failures.append(failure)
                result.provider_metadata["failed_data_types"].append(data_type)
                result.data_confidence = GoogleTrendsDataConfidence.BLOCKED.value
                continue

            if status in {"Queued", "Processing"}:
                result.data_confidence = GoogleTrendsDataConfidence.MEDIUM.value

            if data_type == "TIMESERIES":
                batch_interest = self._parse_timeseries(payload, request)
                if batch_interest:
                    all_interest_points.extend(batch_interest)
                    data_types_with_data.append(data_type)
            elif data_type == "RELATED_QUERIES":
                batch_top, batch_rising = self._parse_related_items(payload, request, use_topics=False)
                if batch_top or batch_rising:
                    all_related_queries_top.extend(batch_top)
                    all_related_queries_rising.extend(batch_rising)
                    data_types_with_data.append(data_type)
            elif data_type == "RELATED_TOPICS":
                batch_top, batch_rising = self._parse_related_items(payload, request, use_topics=True)
                if batch_top or batch_rising:
                    all_related_topics_top.extend(batch_top)
                    all_related_topics_rising.extend(batch_rising)
                    data_types_with_data.append(data_type)
            elif data_type == "GEO_MAP":
                batch_regions = self._parse_regions(payload, request)
                if batch_regions:
                    all_region_rows.extend(batch_regions)
                    data_types_with_data.append(data_type)

            result.provider_metadata["completed_data_types"].append(data_type)

        result.interest_over_time = GoogleTrendsClient._merge_interest_points(all_interest_points)
        result.interest_over_time = sorted(
            result.interest_over_time, key=lambda point: (point.time or "", point.formatted_time or "")
        )
        result.averages = GoogleTrendsClient._calculate_averages(result.interest_over_time)
        result.related_queries_top = GoogleTrendsClient._dedupe_related(all_related_queries_top)
        result.related_queries_rising = GoogleTrendsClient._dedupe_related(all_related_queries_rising)
        result.related_topics_top = GoogleTrendsClient._dedupe_related(all_related_topics_top)
        result.related_topics_rising = GoogleTrendsClient._dedupe_related(all_related_topics_rising)
        result.region_rows = GoogleTrendsClient._dedupe_regions(all_region_rows)

        if not result.has_data():
            if result.failures:
                if result.data_confidence != GoogleTrendsDataConfidence.BLOCKED.value:
                    result.data_confidence = GoogleTrendsDataConfidence.BLOCKED.value
            else:
                result.failures.append(
                    GoogleTrendsFailure(
                        kind="provider_task_error",
                        message="SerpApi returned no usable Google Trends data",
                        source="serpapi",
                    )
                )
                result.data_confidence = GoogleTrendsDataConfidence.BLOCKED.value

        elif len(data_types_with_data) < len(requested_data_types):
            if result.data_confidence != GoogleTrendsDataConfidence.BLOCKED.value:
                result.data_confidence = GoogleTrendsDataConfidence.MEDIUM.value

        if result.failures and result.data_confidence == GoogleTrendsDataConfidence.HIGH.value:
            result.data_confidence = GoogleTrendsDataConfidence.MEDIUM.value

        result.provider_metadata["data_type"] = (
            requested_data_types[0] if len(requested_data_types) == 1 else list(requested_data_types)
        )
        result.provider_metadata["search_metadata_by_data_type"] = search_metadata_by_type
        return result


# Purpose: ScrapeBadgerWebTrendsAdapter implementation
class ScrapeBadgerWebTrendsAdapter(_SessionBackedTrendsAdapter):
    provider_name: str = "scrapebadger_web"

    # Purpose:   init   implementation
    def __init__(self, client: Optional[GoogleTrendsClient] = None) -> None:
        super().__init__(client)
        self.capabilities = _build_trends_provider_capabilities(
            provider=self.provider_name,
            supports_time_series=False,
            supports_related_queries=False,
            supports_related_topics=False,
            supports_geo_breakdown=False,
            supports_trending_now=False,
            supports_autocomplete=False,
            supports_topic_ids=False,
            supports_historical_depth="none",
            max_keywords_per_request=5,
            cache_ttl_seconds=86400,
            notes=[
                "Generic web scrape fallback/diagnostic. Not a structured Google Trends API.",
            ],
        )

    # Purpose: is available implementation
    def is_available(self) -> bool:
        return bool(os.environ.get("SCRAPEBADGER_KEY", "").strip())

    # Purpose:  build trends url implementation
    # Purpose:  build trends url implementation
    @staticmethod
    def _build_trends_url(request: GoogleTrendsRequest) -> str:
        params = {
            "q": "|".join(request.keywords),
            "geo": request.geo,
            "date": request.timeframe,
        }
        return requests.Request(
            "GET",
            GOOGLE_TRENDS_EXPLORE_URL.replace("/api/explore", "/explore"),
            params=params,
        ).prepare().url

    # Purpose:  parse content payload implementation
    # Purpose:  parse content payload implementation
    @staticmethod
    def _parse_content_payload(content: str) -> Optional[Dict[str, Any]]:
        try:
            payload = _parse_json_text(content)
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    # Purpose: get trends implementation
    def get_trends(self, request: GoogleTrendsRequest) -> GoogleTrendsResult:
        if not self.is_available():
            return _build_provider_failure_result(
                request,
                self.provider_name,
                GoogleTrendsFailure(
                    kind="provider_unavailable",
                    message="ScrapeBadger web scrape fallback is not enabled",
                    source="scrapebadger",
                ),
                provider_metadata={"provider": self.provider_name, "endpoint": "web/scrape"},
            )

        api_key = os.environ.get("SCRAPEBADGER_KEY", "")
        target_url = self._build_trends_url(request)
        try:
            response = self.session.post(
                "https://scrapebadger.com/v1/web/scrape",
                headers={"x-api-key": api_key, "Content-Type": "application/json"},
                json={"url": target_url, "format": "json"},
                timeout=self.active_client.timeout_seconds,
            )
        except requests.RequestException as exc:
            return _build_provider_failure_result(
                request,
                self.provider_name,
                GoogleTrendsFailure(
                    kind="unsupported_mode",
                    message="ScrapeBadger request failed",
                    source="scrapebadger",
                    retryable=True,
                    details={"error": str(exc)},
                ),
                provider_metadata={"provider": self.provider_name, "endpoint": "web/scrape", "url": target_url},
            )

        if response.status_code != 200:
            return _build_provider_failure_result(
                request,
                self.provider_name,
                GoogleTrendsFailure(
                    kind="unsupported_mode",
                    message="ScrapeBadger returned an error response",
                    status_code=response.status_code,
                    source="scrapebadger",
                    details={"url": target_url},
                ),
                provider_metadata={"provider": self.provider_name, "endpoint": "web/scrape", "url": target_url},
            )

        try:
            body = response.json()
        except ValueError:
            return _build_provider_failure_result(
                request,
                self.provider_name,
                GoogleTrendsFailure(
                    kind="unsupported_mode",
                    message="ScrapeBadger returned malformed JSON",
                    source="scrapebadger",
                ),
                provider_metadata={"provider": self.provider_name, "endpoint": "web/scrape", "url": target_url},
            )

        if not isinstance(body, dict):
            return _build_provider_failure_result(
                request,
                self.provider_name,
                GoogleTrendsFailure(
                    kind="unsupported_mode",
                    message="ScrapeBadger returned an unexpected payload",
                    source="scrapebadger",
                ),
                provider_metadata={"provider": self.provider_name, "endpoint": "web/scrape", "url": target_url},
            )

        content = _normalize_text(body.get("content"))
        if not content:
            return _build_provider_failure_result(
                request,
                self.provider_name,
                GoogleTrendsFailure(
                    kind="unsupported_mode",
                    message="ScrapeBadger returned empty content",
                    source="scrapebadger",
                ),
                provider_metadata={"provider": self.provider_name, "endpoint": "web/scrape", "url": target_url},
            )

        payload = self._parse_content_payload(content)
        provider_metadata = {
            "provider": self.provider_name,
            "endpoint": "web/scrape",
            "url": target_url,
            "format": _normalize_text(body.get("format") or "json"),
            "parse_mode": "json" if payload is not None else "html",
        }

        if payload is None:
            result = GoogleTrendsResult(
                request=request,
                provider=self.provider_name,
                provider_metadata=provider_metadata,
                data_confidence=GoogleTrendsDataConfidence.LOW.value,
            )
            result.integrity_warnings.append(_GENERIC_SCRAPE_WARNING)
            result.warnings.append(_GENERIC_SCRAPE_WARNING)
            return result

        interest_points: List[GoogleTrendsInterestPoint] = []
        related_queries_top: List[GoogleTrendsRelatedItem] = []
        related_queries_rising: List[GoogleTrendsRelatedItem] = []
        related_topics_top: List[GoogleTrendsRelatedItem] = []
        related_topics_rising: List[GoogleTrendsRelatedItem] = []
        region_rows: List[GoogleTrendsRegionRow] = []

        if request.include_interest_over_time:
            interest_points = GoogleTrendsClient._parse_timeline(payload, request.keywords, 1)
        if request.include_related:
            related_queries_top, related_queries_rising = GoogleTrendsClient._parse_related(
                payload, request.keywords, 1, "related_queries"
            )
            related_topics_top, related_topics_rising = GoogleTrendsClient._parse_related(
                payload, request.keywords, 1, "related_topics"
            )
        if request.include_region:
            region_rows = GoogleTrendsClient._parse_region(payload, ", ".join(request.keywords), 1)

        result = GoogleTrendsResult(
            request=request,
            provider=self.provider_name,
            interest_over_time=GoogleTrendsClient._merge_interest_points(interest_points),
            averages={},
            related_queries_top=GoogleTrendsClient._dedupe_related(related_queries_top),
            related_queries_rising=GoogleTrendsClient._dedupe_related(related_queries_rising),
            related_topics_top=GoogleTrendsClient._dedupe_related(related_topics_top),
            related_topics_rising=GoogleTrendsClient._dedupe_related(related_topics_rising),
            region_rows=GoogleTrendsClient._dedupe_regions(region_rows),
            provider_metadata=provider_metadata,
            data_confidence=GoogleTrendsDataConfidence.LOW.value,
        )
        result.averages = GoogleTrendsClient._calculate_averages(result.interest_over_time)

        # Always append the generic scrape warning exactly once (ScrapeBadger is always
        # an unstructured scrape regardless of whether widgets/data were found).
        result.integrity_warnings.append(_GENERIC_SCRAPE_WARNING)
        result.warnings.append(_GENERIC_SCRAPE_WARNING)

        return result




# Purpose: DataForSeoGoogleTrendsAdapter implementation
class DataForSeoGoogleTrendsAdapter(_SessionBackedTrendsAdapter):
    provider_name: str = "dataforseo_trends"

    # Purpose:   init   implementation
    def __init__(self, client: Optional[GoogleTrendsClient] = None) -> None:
        super().__init__(client)
        self.capabilities = _build_trends_provider_capabilities(
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
            cache_ttl_seconds=86400,
            notes=["Commercial Basic-auth provider with live Google Trends explore support."],
        )

    # Purpose: is available implementation
    def is_available(self) -> bool:
        return bool(os.environ.get("DATAFORSEO_LOGIN") and os.environ.get("DATAFORSEO_PASSWORD"))

    # Purpose:  build request payload implementation
    def _build_request_payload(self, request: GoogleTrendsRequest) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "keywords": request.keywords[:MAX_BATCH_SIZE],
            "language_code": _normalize_text(request.hl).split("-")[0] or "en",
            "type": "interest",
            "category_code": request.category,
            "item_types": _dataforseo_item_types(request),
            "tag": GoogleTrendsClient._build_cache_key(request),
        }
        payload.update(_dataforseo_location_params(request.geo))
        payload.update(_dataforseo_time_window_params(request.timeframe))
        return payload

    # Purpose:  new failure implementation
    # Purpose:  new failure implementation
    @staticmethod
    def _new_failure(
        *,
        kind: str,
        message: str,
        status_code: Optional[int] = None,
        retryable: bool = False,
        details: Optional[Dict[str, Any]] = None,
    ) -> GoogleTrendsFailure:
        return GoogleTrendsFailure(
            kind=kind,
            message=message,
            retryable=retryable,
            status_code=status_code,
            source="dataforseo_trends",
            details=details or {},
        )

    # Purpose:  provider failure result implementation
    # Purpose:  provider failure result implementation
    @staticmethod
    def _provider_failure_result(
        request: GoogleTrendsRequest,
        failure: GoogleTrendsFailure,
        *,
        status_code: Optional[int] = None,
        status_message: Optional[str] = None,
    ) -> GoogleTrendsResult:
        result = GoogleTrendsResult(
            request=request,
            provider=DataForSeoGoogleTrendsAdapter.provider_name,
            data_confidence=(
                GoogleTrendsDataConfidence.BLOCKED.value
                if failure.kind in {"provider_quota", "provider_auth", "provider_task_error"}
                else GoogleTrendsDataConfidence.DEGRADED.value
            ),
            provider_metadata={
                "provider": DataForSeoGoogleTrendsAdapter.provider_name,
                "endpoint": "explore/live",
                "status_code": status_code,
                "status_message": status_message or failure.message,
                "items_count": 0,
            },
        )
        result.failures.append(failure)
        result.integrity_warnings.append(failure.message)
        return result

    # Purpose:  coerce items implementation
    # Purpose:  coerce items implementation
    @staticmethod
    def _coerce_items(value: Any) -> List[Dict[str, Any]]:
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        return []

    # Purpose:  build related item implementation
    # Purpose:  build related item implementation
    @staticmethod
    def _build_related_item(
        item: Dict[str, Any],
        *,
        rank_type: str,
        item_type: str,
        keyword: str,
    ) -> Optional[GoogleTrendsRelatedItem]:
        label = _normalize_text(
            item.get("query")
            or item.get("title")
            or item.get("text")
            or item.get("keyword")
            or item.get("name")
        )
        if not label:
            return None
        topic_type = _normalize_text(item.get("type") or item.get("topic_type"))
        return GoogleTrendsRelatedItem(
            label=label,
            value=item.get("value"),
            rank_type=rank_type,
            item_type=item_type,
            topic_type=topic_type,
            source_keywords=[keyword] if keyword else [],
        )

    # Purpose:  normalize result item implementation
    def _normalize_result_item(
        self,
        result_item: Dict[str, Any],
        *,
        request: GoogleTrendsRequest,
    ) -> tuple[
        List[GoogleTrendsInterestPoint],
        List[GoogleTrendsRelatedItem],
        List[GoogleTrendsRelatedItem],
        List[GoogleTrendsRelatedItem],
        List[GoogleTrendsRelatedItem],
        List[GoogleTrendsRegionRow],
        List[str],
    ]:
        interest_points: List[GoogleTrendsInterestPoint] = []
        related_queries_top: List[GoogleTrendsRelatedItem] = []
        related_queries_rising: List[GoogleTrendsRelatedItem] = []
        related_topics_top: List[GoogleTrendsRelatedItem] = []
        related_topics_rising: List[GoogleTrendsRelatedItem] = []
        region_rows: List[GoogleTrendsRegionRow] = []
        warnings: List[str] = []

        item_type = _normalize_text(result_item.get("type"))
        if not item_type:
            warnings.append("DataForSEO result item missing type.")
            return (
                interest_points,
                related_queries_top,
                related_queries_rising,
                related_topics_top,
                related_topics_rising,
                region_rows,
                warnings,
            )

        if item_type == DATAFORSEO_ITEM_TYPES["interest_over_time"]:
            for keyword_item in self._coerce_items(result_item.get("items")):
                keyword = _normalize_text(keyword_item.get("keyword") or request.keywords[0])
                if not keyword:
                    continue
                for entry in self._coerce_items(keyword_item.get("data")):
                    time_key = _normalize_text(
                        entry.get("date")
                        or entry.get("time")
                        or entry.get("formattedTime")
                        or entry.get("formatted_axis_time")
                    )
                    if not time_key:
                        continue
                    value = _first_numeric(entry.get("value"))
                    interest_points.append(
                        GoogleTrendsInterestPoint(
                            time=time_key,
                            formatted_time=_normalize_text(
                                entry.get("formattedTime")
                                or entry.get("formattedAxisTime")
                                or entry.get("date")
                                or time_key
                            ),
                            values={keyword: value},
                        )
                    )
        elif item_type == DATAFORSEO_ITEM_TYPES["related_queries"]:
            for keyword_item in self._coerce_items(result_item.get("items")):
                keyword = _normalize_text(keyword_item.get("keyword") or request.keywords[0])
                for entry in self._coerce_items(keyword_item.get("data")):
                    related = self._build_related_item(
                        entry, rank_type="top", item_type="query", keyword=keyword
                    )
                    if related:
                        related_queries_top.append(related)
                for entry in self._coerce_items(keyword_item.get("rising_data")):
                    related = self._build_related_item(
                        entry, rank_type="rising", item_type="query", keyword=keyword
                    )
                    if related:
                        related_queries_rising.append(related)
        elif item_type == DATAFORSEO_ITEM_TYPES["related_topics"]:
            for keyword_item in self._coerce_items(result_item.get("items")):
                keyword = _normalize_text(keyword_item.get("keyword") or request.keywords[0])
                for entry in self._coerce_items(keyword_item.get("data")):
                    related = self._build_related_item(
                        entry, rank_type="top", item_type="topic", keyword=keyword
                    )
                    if related:
                        related_topics_top.append(related)
                for entry in self._coerce_items(keyword_item.get("rising_data")):
                    related = self._build_related_item(
                        entry, rank_type="rising", item_type="topic", keyword=keyword
                    )
                    if related:
                        related_topics_rising.append(related)
        elif item_type == DATAFORSEO_ITEM_TYPES["interest_by_region"]:
            for keyword_item in self._coerce_items(result_item.get("items")):
                keyword = _normalize_text(keyword_item.get("keyword") or request.keywords[0])
                for entry in self._coerce_items(keyword_item.get("data")):
                    region = _normalize_text(
                        entry.get("geo_name")
                        or entry.get("geoName")
                        or entry.get("location_name")
                        or entry.get("geo")
                        or entry.get("name")
                    )
                    if not region:
                        continue
                    region_rows.append(
                        GoogleTrendsRegionRow(
                            region=region,
                            value=_first_numeric(entry.get("value")),
                            keyword=keyword,
                        )
                    )
        else:
            warnings.append(f"Unsupported DataForSEO item type: {item_type}")

        return (
            interest_points,
            related_queries_top,
            related_queries_rising,
            related_topics_top,
            related_topics_rising,
            region_rows,
            warnings,
        )

    # Purpose: get trends implementation
    def get_trends(self, request: GoogleTrendsRequest) -> GoogleTrendsResult:
        if not self.is_available():
            return self._provider_failure_result(
                request,
                self._new_failure(
                    kind="provider_unavailable",
                    message="DataForSEO credentials are not configured",
                ),
            )

        if len(request.keywords) > MAX_BATCH_SIZE:
            return self._provider_failure_result(
                request,
                self._new_failure(
                    kind="unsupported_mode",
                    message="DataForSEO Google Trends supports up to 5 keywords per request",
                    details={"max_keywords_per_request": MAX_BATCH_SIZE},
                ),
            )

        payload = self._build_request_payload(request)
        auth = HTTPBasicAuth(
            os.environ.get("DATAFORSEO_LOGIN", ""),
            os.environ.get("DATAFORSEO_PASSWORD", ""),
        )

        try:
            response = self.session.post(
                DATAFORSEO_GOOGLE_TRENDS_EXPLORE_LIVE_URL,
                json=payload,
                auth=auth,
                timeout=30,
            )
        except requests.Timeout as exc:
            failure = self._new_failure(
                kind="provider_task_error",
                message="DataForSEO Google Trends request timed out",
                retryable=True,
                details={"error": str(exc)},
            )
            return self._provider_failure_result(request, failure)
        except requests.RequestException as exc:
            failure = self._new_failure(
                kind="provider_task_error",
                message="DataForSEO Google Trends request failed",
                retryable=True,
                details={"error": str(exc)},
            )
            return self._provider_failure_result(request, failure)

        if response.status_code == 429:
            failure = self._new_failure(
                kind="provider_quota",
                message="DataForSEO Google Trends rate limit reached",
                status_code=429,
                retryable=True,
            )
            return self._provider_failure_result(request, failure, status_code=429)

        if response.status_code in {401, 403}:
            failure = self._new_failure(
                kind="provider_auth",
                message="DataForSEO authentication failed",
                status_code=response.status_code,
            )
            return self._provider_failure_result(
                request,
                failure,
                status_code=response.status_code,
                status_message=getattr(response, "reason", None) or "Authentication failed",
            )

        try:
            body = response.json()
        except ValueError as exc:
            failure = self._new_failure(
                kind="provider_task_error",
                message="DataForSEO returned malformed JSON",
                status_code=getattr(response, "status_code", None),
                details={"error": str(exc)},
            )
            return self._provider_failure_result(
                request,
                failure,
                status_code=getattr(response, "status_code", None),
            )

        if not isinstance(body, dict):
            failure = self._new_failure(
                kind="provider_task_error",
                message="DataForSEO returned an unexpected payload",
                status_code=getattr(response, "status_code", None),
            )
            return self._provider_failure_result(request, failure)

        body_status_code = _first_numeric(body.get("status_code"))
        body_status_message = _normalize_text(body.get("status_message"))
        tasks = body.get("tasks") or []

        if body_status_code is not None and body_status_code != 20000:
            # Extract only non-sensitive fields to avoid persisting credentials
            safe_details: Dict[str, Any] = {
                "status_code": body_status_code,
                "status_message": body_status_message,
            }
            # Extract task_id from first task if available, without the full body
            first_task = tasks[0] if isinstance(tasks, list) and tasks else None
            if isinstance(first_task, dict):
                safe_details["task_id"] = first_task.get("id")
            failure = self._new_failure(
                kind="provider_task_error",
                message=body_status_message or "DataForSEO returned a task-level error",
                status_code=body_status_code,
                retryable=body_status_code in {40005, 50000},
                details=safe_details,
            )
            return self._provider_failure_result(
                request,
                failure,
                status_code=body_status_code,
                status_message=body_status_message,
            )

        if not isinstance(tasks, list) or not tasks:
            failure = self._new_failure(
                kind="provider_task_error",
                message="DataForSEO response did not include tasks",
                status_code=body_status_code,
            )
            return self._provider_failure_result(
                request,
                failure,
                status_code=body_status_code,
                status_message=body_status_message or "No tasks returned",
            )

        interest_points: List[GoogleTrendsInterestPoint] = []
        related_queries_top: List[GoogleTrendsRelatedItem] = []
        related_queries_rising: List[GoogleTrendsRelatedItem] = []
        related_topics_top: List[GoogleTrendsRelatedItem] = []
        related_topics_rising: List[GoogleTrendsRelatedItem] = []
        region_rows: List[GoogleTrendsRegionRow] = []
        warnings: List[str] = []
        task_ids: List[str] = []
        task_status_codes: List[int] = []
        task_status_messages: List[str] = []
        task_failure: Optional[GoogleTrendsFailure] = None

        for task in tasks:
            if not isinstance(task, dict):
                warnings.append("Encountered a non-dict DataForSEO task entry.")
                continue

            task_id = _normalize_text(task.get("id"))
            if task_id:
                task_ids.append(task_id)

            task_status_code = _first_numeric(task.get("status_code"))
            if task_status_code is not None:
                task_status_codes.append(task_status_code)
            task_status_message = _normalize_text(task.get("status_message"))
            if task_status_message:
                task_status_messages.append(task_status_message)

            if task_status_code is not None and task_status_code != 20000:
                task_failure = self._new_failure(
                    kind="provider_task_error",
                    message=task_status_message or "DataForSEO task returned an error",
                    status_code=task_status_code,
                    retryable=task_status_code in {40005, 50000},
                    details={"task": task},
                )
                continue

            result_items = task.get("result") or []
            if not isinstance(result_items, list):
                warnings.append("DataForSEO task result is not a list.")
                continue

            for result_item in result_items:
                if not isinstance(result_item, dict):
                    warnings.append("Encountered a non-dict DataForSEO result item.")
                    continue
                (
                    batch_interest_points,
                    batch_related_queries_top,
                    batch_related_queries_rising,
                    batch_related_topics_top,
                    batch_related_topics_rising,
                    batch_region_rows,
                    item_warnings,
                ) = self._normalize_result_item(result_item, request=request)
                interest_points.extend(batch_interest_points)
                related_queries_top.extend(batch_related_queries_top)
                related_queries_rising.extend(batch_related_queries_rising)
                related_topics_top.extend(batch_related_topics_top)
                related_topics_rising.extend(batch_related_topics_rising)
                region_rows.extend(batch_region_rows)
                warnings.extend(item_warnings)

        merged_interest = GoogleTrendsClient._merge_interest_points(interest_points)
        merged_interest = sorted(
            merged_interest, key=lambda point: (point.time or "", point.formatted_time or "")
        )
        averages = GoogleTrendsClient._calculate_averages(merged_interest)
        region_rows = GoogleTrendsClient._dedupe_regions(region_rows)
        related_queries_top = GoogleTrendsClient._dedupe_related(related_queries_top)
        related_queries_rising = GoogleTrendsClient._dedupe_related(related_queries_rising)
        related_topics_top = GoogleTrendsClient._dedupe_related(related_topics_top)
        related_topics_rising = GoogleTrendsClient._dedupe_related(related_topics_rising)

        provider_metadata: Dict[str, Any] = {
            "provider": self.provider_name,
            "endpoint": "explore/live",
            "status_code": body_status_code
            if body_status_code is not None
            else (task_status_codes[0] if task_status_codes else getattr(response, "status_code", None)),
            "status_message": body_status_message
            or (task_status_messages[0] if task_status_messages else getattr(response, "reason", "") or ""),
            "items_count": sum(
                len(collection)
                for collection in (
                    merged_interest,
                    related_queries_top,
                    related_queries_rising,
                    related_topics_top,
                    related_topics_rising,
                    region_rows,
                )
            ),
        }
        if task_ids:
            provider_metadata["task_id"] = task_ids[0] if len(task_ids) == 1 else task_ids

        result = GoogleTrendsResult(
            request=request,
            provider=self.provider_name,
            interest_over_time=merged_interest,
            averages=averages,
            related_queries_top=related_queries_top,
            related_queries_rising=related_queries_rising,
            related_topics_top=related_topics_top,
            related_topics_rising=related_topics_rising,
            region_rows=region_rows,
            warnings=warnings,
            provider_metadata=provider_metadata,
            data_confidence=GoogleTrendsDataConfidence.HIGH.value,
        )

        if task_failure is not None:
            result.failures.append(task_failure)
            result.integrity_warnings.append(task_failure.message)
            if result.has_data():
                result.data_confidence = GoogleTrendsDataConfidence.MEDIUM.value
            else:
                result.data_confidence = (
                    GoogleTrendsDataConfidence.BLOCKED.value
                    if task_failure.kind in {"provider_quota", "provider_auth"}
                    else GoogleTrendsDataConfidence.DEGRADED.value
                )

        if warnings:
            result.integrity_warnings.extend(warnings)
            if result.data_confidence == GoogleTrendsDataConfidence.HIGH.value:
                result.data_confidence = GoogleTrendsDataConfidence.MEDIUM.value

        if request.include_interest_over_time and result.interest_over_time:
            if all(
                value in (None, 0)
                for point in result.interest_over_time
                for value in point.values.values()
            ):
                zero_warning = "Suspicious all-zero time series detected in DataForSEO response."
                result.data_confidence = GoogleTrendsDataConfidence.DEGRADED.value
                result.integrity_warnings.append(zero_warning)
                result.warnings.append(zero_warning)

        if not result.has_data():
            result.failures.append(
                self._new_failure(
                    kind="provider_task_error",
                    message="DataForSEO returned no usable Google Trends data",
                    status_code=provider_metadata.get("status_code"),
                )
            )
            result.data_confidence = GoogleTrendsDataConfidence.BLOCKED.value
            result.integrity_warnings.append("DataForSEO returned no usable Google Trends data.")

        return result




register_trends_provider("serpapi_trends", SerpApiTrendsAdapter())
register_trends_provider("scrapebadger_web", ScrapeBadgerWebTrendsAdapter())
register_trends_provider("dataforseo_trends", DataForSeoGoogleTrendsAdapter())


# Purpose: TrendsOrchestrator implementation
class TrendsOrchestrator:
    # Purpose:   init   implementation
    def __init__(
        self,
        settings: Optional[Dict[str, Any]] = None,
        cache: Any = request_cache,
    ) -> None:
        self.settings = settings or {}
        self.cache = cache

    # Purpose:  settings section implementation
    def _settings_section(self, settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        candidate = settings if settings is not None else self.settings
        if isinstance(candidate, dict):
            if isinstance(candidate.get("google_trends"), dict):
                return dict(candidate.get("google_trends", {}) or {})
            return dict(candidate)
        return _google_trends_settings()

    # Purpose:  provider order implementation
    # Purpose:  provider order implementation
    @staticmethod
    def _provider_order(settings_section: Dict[str, Any], provider: Optional[str]) -> List[str]:
        order: List[str] = []
        resolved = str(provider or settings_section.get("provider") or DEFAULT_PROVIDER_NAME)
        for name in [resolved, *list(settings_section.get("provider_order", []) or []), *TRENDS_PROVIDER_OPTIONS]:
            candidate = str(name).strip()
            if candidate and candidate not in order:
                order.append(candidate)
        return order

    # Purpose:  is provider allowed implementation
    # Purpose:  is provider allowed implementation
    @staticmethod
    def _is_provider_allowed(provider_name: str, settings_section: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        return True, None

    # Purpose:  cache metadata implementation
    # Purpose:  cache metadata implementation
    @staticmethod
    def _cache_metadata(cache_key: str, cache_hit: bool, cache_hit_count: Optional[int] = None) -> Dict[str, Any]:
        payload = {"cache_key": cache_key, "cache_hit": cache_hit}
        if cache_hit_count is not None:
            payload["cache_hit_count"] = cache_hit_count
        return payload

    # Purpose: run trends implementation
    def run_trends(
        self,
        keywords: List[str],
        provider: Optional[str] = None,
        force_refresh: bool = False,
        settings: Optional[Dict[str, Any]] = None,
    ) -> GoogleTrendsResult:
        settings_section = self._settings_section(settings)
        filtered_keywords = [str(keyword).strip() for keyword in keywords if str(keyword or "").strip()]
        filtered_keywords = [keyword for keyword in filtered_keywords if not _looks_like_url(keyword)]
        if not filtered_keywords:
            raise ValueError("keywords must contain at least one non-URL keyword")

        request = _trends_request_from_settings(filtered_keywords, settings_section)
        endpoint_mode = _trends_endpoint_mode(request)
        provider_order = self._provider_order(settings_section, provider)
        attempts: List[Dict[str, Any]] = []
        selected_provider = str(provider or settings_section.get("provider") or DEFAULT_PROVIDER_NAME)
        last_failure: Optional[GoogleTrendsFailure] = None

        for provider_name in provider_order:
            allowed, skip_reason = self._is_provider_allowed(provider_name, settings_section)
            if not allowed:
                attempts.append(
                    {
                        "provider": provider_name,
                        "status": "skipped",
                        "reason": skip_reason,
                    }
                )
                logger.info(
                    f"Skipping Trends provider {provider_name}: {skip_reason}"
                )
                continue

            client = GoogleTrendsClient(provider_name=provider_name)
            try:
                adapter = client.active_adapter
                if adapter is None:
                    attempts.append(
                        {
                            "provider": provider_name,
                            "status": "unavailable",
                            "reason": "provider not registered",
                        }
                    )
                    logger.info(f"Trends provider {provider_name} is not registered")
                    continue

                try:
                    available = bool(adapter.is_available())
                except Exception as exc:
                    available = False
                    skip_reason = f"availability check failed: {exc}"
                else:
                    skip_reason = "provider unavailable"
                if not available:
                    attempts.append(
                        {
                            "provider": provider_name,
                            "status": "unavailable",
                            "reason": skip_reason,
                        }
                    )
                    logger.info(f"Trends provider {provider_name} unavailable: {skip_reason}")
                    continue

                provider_version = _trends_provider_version(provider_name, adapter)
                cache_key = build_trends_cache_key(
                    provider=provider_name,
                    endpoint_mode=endpoint_mode,
                    params={
                        **request.to_dict(),
                        "normalized_keywords": request.keywords,
                        "batch_composition": _trends_batch_composition(request),
                        "provider_version": provider_version,
                    },
                )
                cache_ttl_hours = _trends_cache_ttl_hours(provider_name, adapter)

                if not force_refresh and self.cache is not None:
                    cached = self.cache.get(cache_key, force_refresh=False)
                    if cached is not None:
                        result = _restore_trends_result_from_payload(
                            cached.get("result", {}).get("payload")
                        )
                        if result is not None and _is_cacheable_trends_result(result):
                            result.provider = provider_name
                            result.provider_metadata = dict(result.provider_metadata or {})
                            result.provider_metadata.setdefault("provider", provider_name)
                            result.provider_metadata.setdefault("provider_version", provider_version)
                            result.provider_metadata.setdefault("endpoint_mode", endpoint_mode)
                            result.provider_metadata.setdefault("attempted_providers", attempts + [
                                {"provider": provider_name, "status": "cache_hit"}
                            ])
                            result.cache_metadata.update(
                                self._cache_metadata(
                                    cache_key,
                                    True,
                                    cached.get("cache_hit_count", 0),
                                )
                            )
                            logger.info(
                                f"Trends cache hit for provider {provider_name} key={cache_key[:8]}"
                            )
                            return result
                        if result is not None:
                            logger.info(
                                "Skipping stale non-cacheable Trends cache entry "
                                f"for provider {provider_name} key={cache_key[:8]}"
                            )

                try:
                    result = client.get_trends(request)
                except Exception as exc:
                    failure = GoogleTrendsFailure(
                        kind="provider_task_error",
                        message=str(exc),
                        retryable=False,
                        source=provider_name,
                    )
                    attempts.append(
                        {
                            "provider": provider_name,
                            "status": "error",
                            "reason": failure.message,
                        }
                    )
                    last_failure = failure
                    logger.info(f"Trends provider {provider_name} failed: {failure.message}")
                    continue

                result.provider = provider_name
                result.provider_metadata = dict(result.provider_metadata or {})
                result.provider_metadata.setdefault("provider", provider_name)
                result.provider_metadata.setdefault("provider_version", provider_version)
                result.provider_metadata.setdefault("endpoint_mode", endpoint_mode)
                result.provider_metadata["attempted_providers"] = attempts + [
                    {
                        "provider": provider_name,
                        "status": "selected",
                        "reason": "returned data" if result.has_data() else "no usable data",
                    }
                ]
                result.cache_metadata.update(self._cache_metadata(cache_key, False))

                if self.cache is not None and _is_cacheable_trends_result(result):
                    self.cache.set(
                        kind="trends",
                        cache_key=cache_key,
                        request_params={
                            **request.to_dict(),
                            "normalized_keywords": request.keywords,
                            "batch_composition": _trends_batch_composition(request),
                            "provider_version": provider_version,
                            "endpoint_mode": endpoint_mode,
                            "schema_version": 2,
                        },
                        result=result,
                        provider=provider_name,
                        keywords=request.keywords,
                        ttl_hours=cache_ttl_hours,
                    )

                if result.has_data() or not result.failures:
                    return result

                if result.failures:
                    last_failure = result.failures[-1]
                    attempts.append(
                        {
                            "provider": provider_name,
                            "status": "failed",
                            "reason": last_failure.message,
                        }
                    )
                    logger.info(
                        f"Trends provider {provider_name} returned no usable data: {last_failure.message}"
                    )
            finally:
                client.close()

        final_failure = last_failure or GoogleTrendsFailure(
            kind="provider_unavailable",
            message="No Google Trends provider was available",
            retryable=False,
            source=selected_provider,
        )
        return GoogleTrendsResult(
            request=request,
            provider=selected_provider,
            failures=[final_failure],
            provider_metadata={
                "provider": selected_provider,
                "attempted_providers": attempts,
                "provider_order": provider_order,
                "reason": final_failure.message,
            },
            cache_metadata={"cache_hit": False},
            data_confidence=GoogleTrendsDataConfidence.BLOCKED.value,
            integrity_warnings=[final_failure.message],
        )


# FUNCTION_CONTRACT: create_google_trends_client
# Purpose: Factory function to create Google Trends client with default configuration or registry lookup
# Input: provider_name (str, optional)
# Output: GoogleTrendsClient instance
# Side Effects: None (pure factory)
# Business Rules: Loads configuration from settings.yaml; uses default timeout/retry/backoff values
# Failure Modes: None (factory always succeeds)
# LINKS: requirements.xml#UC-010
# SEMANTIC_BLOCK: block_trends_result_deduplication
def create_google_trends_client(provider_name: Optional[str] = None) -> GoogleTrendsClient:
    if not provider_name:
        try:
            cfg = load_config()
            trends_cfg = cfg.get("google_trends", {}) if isinstance(cfg, dict) else {}
            provider_name = trends_cfg.get("provider", "google_trends_direct")
        except Exception:
            provider_name = "google_trends_direct"
    return GoogleTrendsClient(provider_name=provider_name)


__all__ = [
    "ANTI_XSSI_PREFIXES",
    "DEFAULT_PROVIDER_NAME",
    "GoogleTrendsClient",
    "GoogleTrendsError",
    "GoogleTrendsFailure",
    "GoogleTrendsInterestPoint",
    "DataForSeoGoogleTrendsAdapter",
    "GoogleTrendsRelatedItem",
    "GoogleTrendsRegionRow",
    "GoogleTrendsRequest",
    "GoogleTrendsResult",
    "ScrapeBadgerWebTrendsAdapter",
    "SerpApiTrendsAdapter",
    "TrendsOrchestrator",
    "create_google_trends_client",
    "GoogleTrendsProviderCapabilities",
    "GoogleTrendsDataConfidence",
    "GoogleTrendsProviderAdapter",
    "TRENDS_PROVIDER_REGISTRY",
    "TRENDS_PROVIDER_OPTIONS",
    "register_trends_provider",
]
