# MODULE_CONTRACT: utils/browser_scraper_trends
# Purpose: Google Trends provider adapter wrapping BrowserScraper (cloakbrowser + playwright)
# Rationale: Browser-based fallback for Google Trends when direct API fails or JS-heavy pages need rendering
# LINKS: requirements.xml#UC-010, utils/google_trends_client.py, utils/browser_scraper.py
# Dependencies: utils.google_trends_client, utils.browser_scraper
# Exports: BrowserScraperTrendsAdapter
# MODULE_MAP: utils/browser_scraper_trends.py
# Public Functions: is_available, get_trends, close
# Private Helpers: _normalize_widget_text, _extract_related_row_value, _is_rising_related_value, _parse_rendered_trends_html
# Key Semantic Blocks: block_browser_scraper_trends_adapter, block_browser_scraper_trends_fetch, block_browser_scraper_trends_rendered_html
# Critical Flows: adapter bridges BrowserScraper CSV-download output into GoogleTrendsResult and recovers rendered HTML related/geo widgets when present
# Verification: V-SUITE
# CHANGE_SUMMARY: Phase 16 - Fix adapter to use correct GoogleTrendsInterestPoint fields (time, formatted_time, values dict), handle blocked/429 with BLOCKED confidence and rate_limit failure, handle empty CSV with LOW confidence and empty_data failure. Phase 17 - Fan out multi-keyword requests sequentially, merge per-keyword CSV timelines, and degrade gracefully on partial failures. Phase 18 - Parse rendered Trends HTML for related queries and geo rows while keeping CSV timeline as primary when present.

from __future__ import annotations

import random
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from bs4 import BeautifulSoup

from utils.browser_scraper import _parse_trends_structural_html

from utils.google_trends_client import (
    GoogleTrendsClient,
    GoogleTrendsDataConfidence,
    GoogleTrendsFailure,
    GoogleTrendsInterestPoint,
    GoogleTrendsRequest,
    GoogleTrendsRelatedItem,
    GoogleTrendsRegionRow,
    GoogleTrendsResult,
    MAX_BATCH_SIZE,
    _build_provider_failure_result,
    _build_trends_provider_capabilities,
    _build_trends_result,
    register_trends_provider,
)


# FUNCTION_CONTRACT: _build_terminal_trends_result
# Purpose: Build a terminal GoogleTrendsResult with explicit status and confidence
# Input: request (GoogleTrendsRequest), provider (str), status (str), confidence (str), warnings (List[str]), failures (List[GoogleTrendsFailure]), provider_metadata (Dict[str, object]), cache_metadata (Dict[str, object])
# Output: GoogleTrendsResult
# Side Effects: none
# Business Rules: Preserve the supplied warnings, failures, and metadata while stamping the terminal status
# Failure Modes: none
# LINKS: utils/browser_scraper_trends.py
# GRACE: function _build_terminal_trends_result declaration
def _build_terminal_trends_result(
    *,
    request: GoogleTrendsRequest,
    provider: str,
    status: str,
    confidence: str,
    warnings: List[str],
    failures: List[GoogleTrendsFailure],
    provider_metadata: Dict[str, object],
    cache_metadata: Dict[str, object],
) -> GoogleTrendsResult:
    return _build_trends_result(
        request=request,
        provider=provider,
        warnings=warnings,
        failures=failures,
        provider_metadata={**provider_metadata, "status": status},
        cache_metadata=cache_metadata,
        data_confidence=confidence,
        integrity_warnings=list(warnings),
    )


# FUNCTION_CONTRACT: _normalize_widget_text
# Purpose: Normalize rendered Trends widget text into a single trimmed space-separated string
# Input: value (str)
# Output: str
# Side Effects: none
# Business Rules: Collapses repeated whitespace without altering visible tokens
# Failure Modes: none
# LINKS: utils/browser_scraper_trends.py
def _normalize_widget_text(value: str) -> str:
    return " ".join((value or "").split()).strip()


# FUNCTION_CONTRACT: _extract_related_row_value
# Purpose: Extract the value token from a rendered related-query row
# Input: item (Any), label (str)
# Output: str
# Side Effects: none
# Business Rules: Prefer explicit value nodes, otherwise derive from row text before control tokens
# Failure Modes: Returns empty string when no value can be recovered
# LINKS: utils/browser_scraper_trends.py, tmp/tsk.html
def _extract_related_row_value(item, label: str) -> str:
    value_node = item.select_one(".progress-value")
    if value_node is not None:
        direct_value = _normalize_widget_text(value_node.get_text(" ", strip=True))
        if direct_value:
            return direct_value

    row_text = _normalize_widget_text(item.get_text(" ", strip=True))
    if not row_text or not label:
        return ""

    label_index = row_text.find(label)
    tail = row_text[label_index + len(label) :] if label_index >= 0 else row_text
    tail = re.sub(r"^\s*\d+\s*\|\s*", "", tail)
    tail = re.split(r"\s+(?:more_vert|timeline|add|share|embed|search|edit)\b", tail, maxsplit=1)[0]
    tail = re.sub(r"^\s*[\|\-–—]\s*", "", tail)
    return _normalize_widget_text(tail)


# FUNCTION_CONTRACT: _is_rising_related_value
# Purpose: Detect whether a related-query value denotes a rising or breakout entry
# Input: value_text (str)
# Output: bool
# Side Effects: none
# Business Rules: Treat localized breakout labels and percentage increases as rising
# Failure Modes: Returns False on empty or unrecognized values
# LINKS: utils/browser_scraper_trends.py, tmp/tsk.html
def _is_rising_related_value(value_text: str) -> bool:
    normalized = _normalize_widget_text(value_text).casefold()
    if not normalized:
        return False
    breakout_markers = {
        "прорив",
        "breakout",
        "прорыв",
        "прорывной",
        "всплеск",
        "рост",
        "злет",
        "зріст",
    }
    if normalized in breakout_markers:
        return True
    return bool(re.search(r"\+\s*\d", normalized)) or "%" in normalized


# FUNCTION_CONTRACT: _parse_rendered_trends_html
# Purpose: Parse rendered Google Trends HTML into related-query and geo rows
# Input: html (str), keyword (str)
# Output: Dict[str, List[object]]
# Side Effects: none
# Business Rules: Parse rendered HTML structurally while preserving CSV as the primary time-series source; only emit geo/related rows when the row shape and semantics are clear
# Failure Modes: Returns empty collections when widgets are absent or malformed
# LINKS: utils/browser_scraper_trends.py, tmp/tsk.html
def _parse_rendered_trends_html(html: str, keyword: str = "") -> Dict[str, List[object]]:
    soup = BeautifulSoup(html or "", "html.parser")
    related_queries_top: List[GoogleTrendsRelatedItem] = []
    related_queries_rising: List[GoogleTrendsRelatedItem] = []
    region_rows: List[GoogleTrendsRegionRow] = []

    for container, kind in _iter_structural_widget_containers(soup):
        for label, value_text in _extract_structural_widget_rows(container):
            if kind == "geo":
                try:
                    region_rows.append(
                        GoogleTrendsRegionRow(region=label, value=int(value_text), keyword=keyword)
                    )
                except (TypeError, ValueError):
                    continue
            elif kind == "related":
                if not _is_rising_related_value(value_text) and not re.search(r"\d", value_text):
                    continue
                rank_type = "rising" if _is_rising_related_value(value_text) else "top"
                related = GoogleTrendsRelatedItem(
                    label=label,
                    value=value_text,
                    rank_type=rank_type,
                    item_type="related_queries",
                    source_keywords=[keyword] if keyword else [],
                )
                if related.rank_type == "rising":
                    related_queries_rising.append(related)
                else:
                    related_queries_top.append(related)

    return {
        "related_queries_top": related_queries_top,
        "related_queries_rising": related_queries_rising,
        "region_rows": region_rows,
    }


def _iter_structural_widget_containers(soup: BeautifulSoup):
    for container in soup.find_all(["trends-widget", "section", "div", "ul", "ol"]):
        kind = _classify_widget_container(container)
        if kind:
            yield container, kind


def _classify_widget_container(container) -> str:
    class_names = " ".join(container.get("class", [])).lower() if container.get("class") else ""
    role = str(container.get("role", "")).lower()
    text = _normalize_widget_text(container.get_text(" ", strip=True)).casefold()
    if (
        container.name == "trends-widget"
        or "geo" in class_names
        or "map" in class_names
        or "geo" in text
        or "map" in text
        or role in {"region", "img"}
    ):
        return "geo"
    if (
        "related" in class_names
        or "query" in class_names
        or "topic" in class_names
        or "related" in text
        or "query" in text
        or "topic" in text
        or role in {"feed", "list"}
    ):
        return "related"
    return ""


def _extract_structural_widget_rows(container) -> List[tuple[str, str]]:
    rows: List[tuple[str, str]] = []
    for item in container.select("div.item, li, tr"):
        label_node = item.select_one(".label-text, .label, [role='heading'], [aria-label]")
        value_node = item.select_one(".progress-value, .value, [role='img'], [data-value]")
        label = _normalize_widget_text(label_node.get_text(" ", strip=True) if label_node else "")
        value_text = _normalize_widget_text(value_node.get_text(" ", strip=True) if value_node else "")
        if not label or not value_text:
            text = _normalize_widget_text(item.get_text(" ", strip=True))
            parts = [part for part in re.split(r"\s{2,}|(?:\s[|•]\s)|(?:\s+-\s+)", text) if part.strip()]
            if len(parts) >= 2:
                label, value_text = parts[0], parts[-1]
        if label and value_text:
            rows.append((label, value_text))
    return rows


# CLASS_CONTRACT: BrowserScraperTrendsAdapter
# Purpose: Adapter wrapping BrowserScraper for Google Trends via browser automation
# LINKS: requirements.xml#UC-010, utils/browser_scraper.py
# SEMANTIC_BLOCK: block_browser_scraper_trends_adapter
# GRACE: class BrowserScraperTrendsAdapter declaration
class BrowserScraperTrendsAdapter:
    provider_name: str = "browser_scraper_trends"

    # FUNCTION_CONTRACT: BrowserScraperTrendsAdapter.__init__
    # Purpose: Initialize the browser scraper trends adapter
    # Input: client (unused, kept for protocol compatibility)
    # Output: None (constructor)
    # Side Effects: Creates capabilities descriptor
    # Business Rules: Browser automation via cloakbrowser, requires pip install
    # Failure Modes: none
    # LINKS: requirements.xml#UC-010
    def __init__(self, client: object = None) -> None:
        self.client = client
        try:
            from config.settings import GOOGLE_TRENDS_CONFIG

            configured_max = int(
                GOOGLE_TRENDS_CONFIG.get("max_keywords_per_request", MAX_BATCH_SIZE)
                or MAX_BATCH_SIZE
            )
        except (TypeError, ValueError, ImportError):
            configured_max = MAX_BATCH_SIZE
        self.capabilities = _build_trends_provider_capabilities(
            provider=self.provider_name,
            supports_time_series=True,
            supports_related_queries=True,
            supports_related_topics=False,
            supports_geo_breakdown=True,
            supports_trending_now=False,
            supports_autocomplete=False,
            supports_topic_ids=False,
            supports_historical_depth="months",
            max_keywords_per_request=max(1, configured_max),
            cache_ttl_seconds=86400,
            notes=[
                "Browser CSV-download automation via cloakbrowser.",
                "Sequential multi-keyword fan-out with per-keyword CSV downloads.",
                "Rendered HTML parsing recovers related queries and geo rows when available.",
            ],
        )

    # FUNCTION_CONTRACT: BrowserScraperTrendsAdapter.close
    # Purpose: No-op - BrowserScraper manages its own browser lifecycle
    # Input: none
    # Output: none
    # Side Effects: none
    # Business Rules: BrowserScraper handles browser cleanup internally
    # Failure Modes: none
    # LINKS: requirements.xml#UC-010
    def close(self) -> None:
        pass

    # FUNCTION_CONTRACT: BrowserScraperTrendsAdapter.is_available
    # Purpose: Check if BrowserScraper with cloakbrowser is installed and usable
    # Input: none
    # Output: bool
    # Side Effects: Imports and instantiates BrowserScraper to check dependencies
    # Business Rules: Returns True only if cloakbrowser is available
    # Failure Modes: Returns False on any import or instantiation error
    # LINKS: requirements.xml#UC-010
    def is_available(self) -> bool:
        try:
            from utils.browser_scraper import BrowserScraper, BrowserScraperConfig

            scraper = BrowserScraper(BrowserScraperConfig())
            return scraper.is_available()
        except Exception:
            return False

    # FUNCTION_CONTRACT: BrowserScraperTrendsAdapter.get_trends
    # Purpose: Fetch Google Trends data via browser CSV download automation
    # Input: request (GoogleTrendsRequest)
    # Output: GoogleTrendsResult
    # Side Effects: Launches browser, navigates to Google Trends, downloads CSV
    # Business Rules: CSV download is primary - MEDIUM confidence on success, BLOCKED on 429, LOW on empty. Multi-keyword requests fan out sequentially up to the provider cap and merge by (time, formatted_time). Preserve rendered HTML in the scrape payload so downstream code can recover structural timeline/widget fallbacks. No related queries/topics/regions from CSV.
    # Failure Modes: Returns BLOCKED result on 429/block, LOW result on empty CSV, failure result on errors
    # LINKS: requirements.xml#UC-010, utils/browser_scraper.py
    # SEMANTIC_BLOCK: block_browser_scraper_trends_fetch
    def get_trends(self, request: GoogleTrendsRequest) -> GoogleTrendsResult:
        from utils.browser_scraper import BrowserScraper, BrowserScraperConfig
        from config.settings import GOOGLE_TRENDS_CONFIG, load_config as _load_trends_config

        if not self.is_available():
            return _build_provider_failure_result(
                request,
                self.provider_name,
                GoogleTrendsFailure(
                    kind="provider_unavailable",
                    message="BrowserScraper (cloakbrowser) is not installed or unavailable",
                    retryable=False,
                    source=self.provider_name,
                ),
            )

        _trends_cfg = _load_trends_config().get("google_trends", {})
        configured_max = getattr(request, "max_keywords_per_request", None) or _trends_cfg.get(
            "max_keywords_per_request",
            getattr(self.capabilities, "max_keywords_per_request", MAX_BATCH_SIZE),
        )
        try:
            max_keywords = max(1, int(configured_max or 1))
        except (TypeError, ValueError):
            max_keywords = max(
                1,
                int(
                    getattr(self.capabilities, "max_keywords_per_request", MAX_BATCH_SIZE)
                    or MAX_BATCH_SIZE
                ),
            )
        self.capabilities.max_keywords_per_request = max_keywords
        if len(request.keywords) > max_keywords:
            return _build_provider_failure_result(
                request,
                self.provider_name,
                GoogleTrendsFailure(
                    kind="too_many_keywords",
                    message=(
                        "browser_scraper_trends supports up to "
                        f"{max_keywords} keywords per request (received {len(request.keywords)})"
                    ),
                    retryable=False,
                    source=self.provider_name,
                    details={"max_keywords_per_request": max_keywords},
                ),
            )

        scraper = BrowserScraper(BrowserScraperConfig.from_settings())
        browser_locale = str(
            _trends_cfg.get("locale")
            or (request.hl if "-" in request.hl else f"{request.hl}-{request.geo}")
            or "uk-UA"
        )
        params = {
            "geo": request.geo,
            "timeframe": request.timeframe,
            "category": request.category,
            "gprop": request.gprop,
            "hl": request.hl,
            "tz": request.tz,
            "locale": browser_locale,
            "timezone": str(_trends_cfg.get("timezone") or "Europe/Kyiv"),
            "manual_start_wait": _trends_cfg.get(
                "manual_start_wait",
                GOOGLE_TRENDS_CONFIG.get("manual_start_wait", 0),
            ),
            "min_delay": _trends_cfg.get(
                "min_delay",
                GOOGLE_TRENDS_CONFIG.get("min_delay", 60),
            ),
            "max_delay": _trends_cfg.get(
                "max_delay",
                GOOGLE_TRENDS_CONFIG.get("max_delay", 60),
            ),
            "state_file": _trends_cfg.get("state_file", "trends_state.json"),
            "headless": _trends_cfg.get("headless", False),
        }

        failures: List[GoogleTrendsFailure] = []
        warnings: List[str] = []
        interest_points: List[GoogleTrendsInterestPoint] = []
        related_queries_top: List[GoogleTrendsRelatedItem] = []
        related_queries_rising: List[GoogleTrendsRelatedItem] = []
        region_rows: List[GoogleTrendsRegionRow] = []
        successful_keywords: List[str] = []
        failed_keywords: List[str] = []

        min_delay = int(params.get("min_delay", GOOGLE_TRENDS_CONFIG.get("min_delay", 60)) or 0)
        max_delay = int(params.get("max_delay", GOOGLE_TRENDS_CONFIG.get("max_delay", 60)) or 0)
        if min_delay > max_delay:
            min_delay, max_delay = max_delay, min_delay

        for index, keyword in enumerate(request.keywords):
            params_for_keyword: Dict[str, object] = dict(params)
            params_for_keyword["keywords"] = [keyword]

            try:
                scrape_result = scraper.scrape_google_trends([keyword], params_for_keyword)
            except Exception as exc:
                failed_keywords.append(keyword)
                failure = GoogleTrendsFailure(
                    kind="provider_task_error",
                    message=f"BrowserScraper raised for '{keyword}': {exc}",
                    retryable=False,
                    source=self.provider_name,
                    batch_index=index,
                    source_keywords=[keyword],
                )
                failures.append(failure)
                warnings.append(failure.message)
            else:
                if not scrape_result.success:
                    status = str((scrape_result.metadata or {}).get("status", "")).lower()
                    is_blocked = (
                        "blocked" in status
                        or any("429" in err or "block" in err.lower() for err in scrape_result.errors)
                    )
                    failure = GoogleTrendsFailure(
                        kind="rate_limit" if is_blocked else "provider_task_error",
                        message=(
                            "Google returned 429/block page"
                            if is_blocked
                            else ("; ".join(scrape_result.errors) or "BrowserScraper returned no data")
                        ),
                        retryable=False,
                        source=self.provider_name,
                        batch_index=index,
                        source_keywords=[keyword],
                    )
                    if is_blocked:
                        failure.details["status"] = status or "blocked"
                    failures.append(failure)
                    failed_keywords.append(keyword)
                    warnings.append(failure.message)
                else:
                    extracted = scrape_result.extracted_data or scrape_result.parsed_content or {}
                    keyword_points: List[GoogleTrendsInterestPoint] = []
                    for pt in extracted.get("timeline", []):
                        time_str = pt.get("time", "")
                        formatted_time_str = pt.get("formatted_time", "")
                        value = pt.get("value")
                        if value is not None and time_str:
                            keyword_points.append(
                                GoogleTrendsInterestPoint(
                                    time=str(time_str),
                                    formatted_time=str(formatted_time_str),
                                    values={keyword: int(value)},
                                    source_batches=[index],
                                )
                            )

                    rendered_html = extracted.get("html")
                    rendered_data = {
                        "related_queries_top": [],
                        "related_queries_rising": [],
                        "region_rows": [],
                    }
                    if isinstance(rendered_html, str) and rendered_html.strip():
                        rendered_data = _parse_rendered_trends_html(rendered_html, keyword=keyword)
                        related_queries_top.extend(rendered_data["related_queries_top"])
                        related_queries_rising.extend(rendered_data["related_queries_rising"])
                        region_rows.extend(rendered_data["region_rows"])
                        if not keyword_points:
                            fallback_rows = _parse_trends_structural_html(rendered_html)
                            keyword_points = [
                                GoogleTrendsInterestPoint(
                                    time=row["time"],
                                    formatted_time=row["formatted_time"],
                                    values={keyword: int(row["value"])} if keyword else {},
                                    source_batches=[index],
                                )
                                for row in fallback_rows
                            ]
                    has_rendered_data = bool(
                        rendered_data["related_queries_top"]
                        or rendered_data["related_queries_rising"]
                        or rendered_data["region_rows"]
                    )

                    if keyword_points or has_rendered_data:
                        successful_keywords.append(keyword)
                        interest_points.extend(keyword_points)
                    else:
                        failed_keywords.append(keyword)
                        failure = GoogleTrendsFailure(
                            kind="empty_data",
                            message=f"Downloaded CSV contains no data rows for '{keyword}'",
                            retryable=False,
                            source=self.provider_name,
                            batch_index=index,
                            source_keywords=[keyword],
                        )
                        failures.append(failure)
                        warnings.append(failure.message)

            if index < len(request.keywords) - 1:
                delay = random.randint(min_delay, max_delay)
                time.sleep(delay)

        now = datetime.now(timezone.utc)
        cache_metadata = {
            "ttl_hours": 24,
            "fetched_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=24)).isoformat(),
        }
        provider_metadata = {
            "provider": self.provider_name,
            "engine": "cloakbrowser",
            "mode": "csv_download",
            "geo": request.geo,
            "timeframe": request.timeframe,
            "keywords": list(request.keywords),
            "successful_keywords": successful_keywords,
            "failed_keywords": failed_keywords,
            "fetched_at": now.isoformat(),
        }

        has_any_data = bool(interest_points or related_queries_top or related_queries_rising or region_rows)

        if not has_any_data:
            if failures and all(f.kind == "empty_data" for f in failures):
                return _build_terminal_trends_result(
                    request=request,
                    provider=self.provider_name,
                    status="empty",
                    confidence=GoogleTrendsDataConfidence.LOW.value,
                    warnings=warnings,
                    failures=failures,
                    provider_metadata=provider_metadata,
                    cache_metadata=cache_metadata,
                )

            if failures and any(f.kind == "rate_limit" for f in failures):
                return _build_terminal_trends_result(
                    request=request,
                    provider=self.provider_name,
                    status="blocked",
                    confidence=GoogleTrendsDataConfidence.BLOCKED.value,
                    warnings=warnings,
                    failures=failures,
                    provider_metadata=provider_metadata,
                    cache_metadata=cache_metadata,
                )

            return _build_provider_failure_result(
                request,
                self.provider_name,
                failures[0]
                if failures
                else GoogleTrendsFailure(
                    kind="provider_task_error",
                    message="BrowserScraper returned no data",
                    retryable=False,
                    source=self.provider_name,
                ),
                provider_metadata={**provider_metadata, "status": "failed"},
            )

        merged_points = GoogleTrendsClient._merge_interest_points(interest_points)
        merged_points.sort(key=lambda point: (point.time or "", point.formatted_time or ""))
        averages = GoogleTrendsClient._calculate_averages(merged_points)
        related_queries_top = GoogleTrendsClient._dedupe_related(related_queries_top)
        related_queries_rising = GoogleTrendsClient._dedupe_related(related_queries_rising)
        region_rows = GoogleTrendsClient._dedupe_regions(region_rows)

        if failures:
            # Distinguish benign empty_data failures from genuine degradation
            only_empty_data = all(f.kind == "empty_data" for f in failures)
            if only_empty_data:
                # All failures are empty_data — benign low-volume keywords; use MEDIUM
                data_conf = GoogleTrendsDataConfidence.MEDIUM.value
                integrity_warnings = [
                    f"No Google Trends data for {len(failures)} of {len(request.keywords)} "
                    f"keyword(s): {', '.join(failed_keywords)}"
                ]
            else:
                # At least one non-empty_data failure — genuine degradation
                non_benign_kinds = {f.kind for f in failures if f.kind != "empty_data"}
                data_conf = GoogleTrendsDataConfidence.DEGRADED.value
                integrity_warnings = [
                    f"Partial Google Trends data: {len(successful_keywords)} of "
                    f"{len(request.keywords)} keywords succeeded; {len(failures)} failed "
                    f"(kinds: {', '.join(sorted(non_benign_kinds))})"
                ]

            return _build_trends_result(
                request=request,
                provider=self.provider_name,
                interest_over_time=merged_points,
                averages=averages,
                related_queries_top=related_queries_top,
                related_queries_rising=related_queries_rising,
                region_rows=region_rows,
                warnings=warnings or [
                    f"Partial Google Trends data: {len(successful_keywords)} of {len(request.keywords)} keywords succeeded"
                ],
                failures=failures,
                provider_metadata={**provider_metadata, "status": "partial"},
                cache_metadata=cache_metadata,
                data_confidence=data_conf,
                integrity_warnings=integrity_warnings,
            )

        return _build_trends_result(
            request=request,
            provider=self.provider_name,
            interest_over_time=merged_points,
            averages=averages,
            related_queries_top=related_queries_top,
            related_queries_rising=related_queries_rising,
            region_rows=region_rows,
            warnings=[],
            failures=[],
            provider_metadata=provider_metadata,
            cache_metadata=cache_metadata,
            data_confidence=GoogleTrendsDataConfidence.MEDIUM.value,
        )


register_trends_provider("browser_scraper_trends", BrowserScraperTrendsAdapter())
