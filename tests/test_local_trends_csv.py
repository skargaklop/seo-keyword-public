# TDD tests for CSV-download-based Google Trends extraction
# Reference: .planning/phases/16-local-cloakbrowser-trends-csv/16-01-PLAN.md Task 1

from __future__ import annotations

import logging
import sys
import types
import tempfile
from pathlib import Path
from unittest.mock import call, patch

import pytest

from utils.google_trends_client import (
    GoogleTrendsDataConfidence,
    GoogleTrendsRequest,
)
from utils.browser_scraper import BrowserScrapeResult, BrowserScraper, BrowserScraperConfig
from utils.browser_scraper_trends import BrowserScraperTrendsAdapter

# ---- New helpers (not yet implemented — TDD) ----

try:
    from utils.browser_scraper import _parse_trends_csv
except ImportError:
    _parse_trends_csv = None

try:
    from utils.browser_scraper import _detect_trends_block
except ImportError:
    _detect_trends_block = None

try:
    from utils.browser_scraper import _validate_trends_keyword
except ImportError:
    _validate_trends_keyword = None

try:
    from utils.browser_scraper import _load_session_state
except ImportError:
    _load_session_state = None

try:
    from utils.browser_scraper import _save_session_state
except ImportError:
    _save_session_state = None


# ---- CSV Fixtures (derived from real Google Trends single-keyword CSV) ----

STANDARD_CSV = """\
Ключове слово: test keyword

Interest over time
День,test keyword
2025-06-01 – 2025-06-07,45
2025-06-08 – 2025-06-14,52
2025-06-15 – 2025-06-21,38
"""

HEADER_ONLY_CSV = """\
Ключове слово: test keyword

Interest over time
День,test keyword
"""

MISSING_COLUMNS_CSV = """\
Ключове слово: test keyword

Interest over time
"""

BOM_CSV = """\
﻿Ключове слово: test keyword

Interest over time
День,test keyword
2025-06-01 – 2025-06-07,45
"""

SINGLE_DATE_CSV = """\
Ключове слово: test keyword

Interest over time
День,test keyword
2025-06-01,45
2025-06-02,52
"""

# --- Real-world captured CSVs from live Google Trends downloads ----------------
# These reproduce the ACTUAL failure: Google Trends "today 12-m" returns WEEKLY
# buckets whose header first cell is the localized "Week" word (UA: Тиждень,
# RU: Неделя, EN: Week), NOT "День"/"Day". The original parser only matched
# День/Day/Ден, so weekly/monthly CSVs parsed to ZERO points (empty_data).

# Captured from a live download (hl=uk, geo=UA, today 12-m) — weekly granularity.
WEEKLY_UA_CSV = """\
Категорія: Усі категорії

Тиждень,ноутбук: (Україна)
2025-06-08,65
2025-06-15,64
2025-06-22,67
2025-06-29,66
"""

# Weekly granularity, Russian locale.
WEEKLY_RU_CSV = """\
Категория: Все категории

Неделя,ноутбук: (Украина)
2025-06-08,65
2025-06-15,64
"""

# Weekly granularity, English locale.
WEEKLY_EN_CSV = """\
Category: All categories

Week,ноутбук: (Ukraine)
2025-06-08,65
2025-06-15,64
"""

# Monthly granularity, Ukrainian locale (e.g. "now 5-y" groups by month).
MONTHLY_UA_CSV = """\
Категорія: Усі категорії

Місяць,ноутбук: (Україна)
2025-01,65
2025-02,64
"""

# With "<1%" low-volume value (Google uses the literal "<1%" string).
LOW_VOLUME_CSV = """\
Тиждень,редкий запрос: (Україна)
2025-06-08,<1%
2025-06-15,3
"""




class _FakeDownload:
    def __init__(self, csv_content: str) -> None:
        self.csv_content = csv_content

    def save_as(self, path: str) -> None:
        Path(path).write_text(self.csv_content, encoding="utf-8")


class _FakeDownloadContext:
    def __init__(self, page: "_FakeTrendsPage") -> None:
        self.page = page

    def __enter__(self) -> "_FakeDownloadContext":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    @property
    def value(self) -> _FakeDownload:
        return self.page._pending_download


class _FakeDownloadItem:
    def __init__(self, page: "_FakeTrendsPage", csv_content: str) -> None:
        self.page = page
        self.csv_content = csv_content

    def is_visible(self) -> bool:
        return True

    def click(self) -> None:
        self.page._pending_download = _FakeDownload(self.csv_content)


class _FakeTextLocator:
    def __init__(self, should_succeed: bool) -> None:
        self.should_succeed = should_succeed

    @property
    def first(self) -> "_FakeTextLocator":
        return self

    def wait_for(self, timeout: int) -> None:
        if not self.should_succeed:
            raise RuntimeError("text not found")

    def count(self) -> int:
        return 1 if self.should_succeed else 0

    # GRACE: function click declaration.
    def click(self, timeout: int = 0) -> None:
        if not self.should_succeed:
            raise RuntimeError("text not found")


class _FakeBodyLocator:
    def __init__(self, body_text: str) -> None:
        self.body_text = body_text

    def inner_text(self, timeout: int) -> str:
        return self.body_text


class _FakeDownloadLocator:
    def __init__(self, page: "_FakeTrendsPage", csv_content: str) -> None:
        self.page = page
        self.csv_content = csv_content

    def count(self) -> int:
        return 1

    def nth(self, index: int) -> _FakeDownloadItem:
        return _FakeDownloadItem(self.page, self.csv_content)

    @property
    def first(self) -> "_FakeDownloadLocator":
        return self

    def wait_for(self, timeout: int) -> None:
        return None


class _FakeTrendsPage:
    def __init__(self, body_text: str, csv_content: str, responses: list[object]) -> None:
        self.body_text = body_text
        self.csv_content = csv_content
        self.responses = responses
        self._pending_download = None
        self._response_handler = None
        self.url = ""

    def on(self, event: str, callback) -> None:
        if event == "response":
            self._response_handler = callback

    # GRACE: function goto declaration.
    def goto(self, url: str, wait_until: str, timeout: int) -> None:
        self.url = url
        for response in self.responses:
            if self._response_handler is not None:
                self._response_handler(response)

    def wait_for_timeout(self, timeout: int) -> None:
        return None

    # GRACE: function get_by_text declaration.
    def get_by_text(self, text: str, exact: bool = False):
        if text == "Interest over time":
            return _FakeTextLocator(True)
        return _FakeTextLocator(False)

    # GRACE: function locator declaration.
    def locator(self, selector: str):
        if selector == "body":
            return _FakeBodyLocator(self.body_text)
        if "Download" in selector or "Завантажити" in selector or "Скачать" in selector:
            return _FakeDownloadLocator(self, self.csv_content)
        return _FakeTextLocator(False)

    def expect_download(self, timeout: int) -> _FakeDownloadContext:
        return _FakeDownloadContext(self)

    def close(self) -> None:
        return None


class _FakeTrendsContext:
    def __init__(self, page: _FakeTrendsPage) -> None:
        self.page = page

    def new_page(self) -> _FakeTrendsPage:
        return self.page


class _FakeTrendsBrowser:
    def __init__(self, page: _FakeTrendsPage) -> None:
        self.page = page

    def new_context(self, **kwargs) -> _FakeTrendsContext:
        return _FakeTrendsContext(self.page)

    def close(self) -> None:
        return None


class _FakeResponse:
    def __init__(self, status: int, resource_type: str) -> None:
        self.status = status
        self.request = types.SimpleNamespace(resource_type=resource_type)


# GRACE: function _install_fake_cloakbrowser declaration.
def _install_fake_cloakbrowser(monkeypatch, page: _FakeTrendsPage) -> None:
    fake_module = types.ModuleType("cloakbrowser")
    fake_module.launch = lambda **kwargs: _FakeTrendsBrowser(page)
    monkeypatch.setitem(sys.modules, "cloakbrowser", fake_module)




# GRACE: class TestCSVParsing declaration.
class TestCSVParsing:


    @pytest.mark.skipif(_parse_trends_csv is None, reason="Implementation not yet available")
    def test_parse_standard_csv_returns_list(self) -> None:
        result = _parse_trends_csv(STANDARD_CSV)
        assert isinstance(result, list)

    @pytest.mark.skipif(_parse_trends_csv is None, reason="Implementation not yet available")
    def test_parse_standard_csv_has_correct_row_count(self) -> None:
        result = _parse_trends_csv(STANDARD_CSV)
        assert len(result) == 3

    @pytest.mark.skipif(_parse_trends_csv is None, reason="Implementation not yet available")
    def test_parse_standard_csv_has_expected_keys(self) -> None:
        result = _parse_trends_csv(STANDARD_CSV)
        for row in result:
            assert "time" in row, f"Missing 'time' key in {row}"
            assert "formatted_time" in row, f"Missing 'formatted_time' key in {row}"
            assert "value" in row, f"Missing 'value' key in {row}"

    @pytest.mark.skipif(_parse_trends_csv is None, reason="Implementation not yet available")
    def test_parse_standard_csv_values(self) -> None:
        result = _parse_trends_csv(STANDARD_CSV)
        assert result[0]["formatted_time"] == "2025-06-01 – 2025-06-07"
        assert result[0]["value"] == 45
        assert result[1]["formatted_time"] == "2025-06-08 – 2025-06-14"
        assert result[1]["value"] == 52
        assert result[2]["formatted_time"] == "2025-06-15 – 2025-06-21"
        assert result[2]["value"] == 38

    @pytest.mark.skipif(_parse_trends_csv is None, reason="Implementation not yet available")
    def test_parse_standard_csv_time_present(self) -> None:
        result = _parse_trends_csv(STANDARD_CSV)
        for row in result:
            assert row["time"], f"Empty 'time' in {row}"


    @pytest.mark.skipif(_parse_trends_csv is None, reason="Implementation not yet available")
    def test_parse_header_only_csv_returns_empty_list(self) -> None:
        result = _parse_trends_csv(HEADER_ONLY_CSV)
        assert isinstance(result, list)
        assert len(result) == 0


    @pytest.mark.skipif(_parse_trends_csv is None, reason="Implementation not yet available")
    def test_parse_missing_data_columns_returns_empty_list(self) -> None:
        result = _parse_trends_csv(MISSING_COLUMNS_CSV)
        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.skipif(_parse_trends_csv is None, reason="Implementation not yet available")
    def test_parse_missing_data_columns_logs_warning(self, caplog) -> None:
        from utils.logger import logger as _proj_logger
        _old_handlers = list(_proj_logger.main_logger.handlers)
        try:
            _proj_logger.main_logger.addHandler(caplog.handler)
            _proj_logger.main_logger.setLevel(logging.WARNING)
            _parse_trends_csv(MISSING_COLUMNS_CSV)
            warning_messages = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
            assert len(warning_messages) > 0, "Expected at least one warning log"
        finally:
            _proj_logger.main_logger.handlers = _old_handlers


    @pytest.mark.skipif(_parse_trends_csv is None, reason="Implementation not yet available")
    def test_parse_csv_with_bom_returns_correct_count(self) -> None:
        result = _parse_trends_csv(BOM_CSV)
        assert len(result) == 1

    @pytest.mark.skipif(_parse_trends_csv is None, reason="Implementation not yet available")
    def test_parse_csv_with_bom_values(self) -> None:
        result = _parse_trends_csv(BOM_CSV)
        assert result[0]["value"] == 45


    @pytest.mark.skipif(_parse_trends_csv is None, reason="Implementation not yet available")
    def test_parse_single_date_column_returns_list(self) -> None:
        result = _parse_trends_csv(SINGLE_DATE_CSV)
        assert isinstance(result, list)

    @pytest.mark.skipif(_parse_trends_csv is None, reason="Implementation not yet available")
    def test_parse_single_date_column_count(self) -> None:
        result = _parse_trends_csv(SINGLE_DATE_CSV)
        assert len(result) == 2

    @pytest.mark.skipif(_parse_trends_csv is None, reason="Implementation not yet available")
    def test_parse_single_date_column_values(self) -> None:
        result = _parse_trends_csv(SINGLE_DATE_CSV)
        assert result[0]["formatted_time"] == "2025-06-01"
        assert result[0]["value"] == 45
        assert result[1]["formatted_time"] == "2025-06-02"
        assert result[1]["value"] == 52




# GRACE: class TestCSVGranularityHeaders declaration.
class TestCSVGranularityHeaders:

    @pytest.mark.skipif(_parse_trends_csv is None, reason="Implementation not yet available")
    def test_weekly_uk_header_is_parsed(self) -> None:
        result = _parse_trends_csv(WEEKLY_UA_CSV)
        assert len(result) == 4, f"Expected 4 weekly points, got {len(result)}"
        assert result[0]["formatted_time"] == "2025-06-08"
        assert result[0]["value"] == 65

    @pytest.mark.skipif(_parse_trends_csv is None, reason="Implementation not yet available")
    def test_weekly_ru_header_is_parsed(self) -> None:
        result = _parse_trends_csv(WEEKLY_RU_CSV)
        assert len(result) == 2, f"Expected 2 weekly points, got {len(result)}"
        assert result[0]["formatted_time"] == "2025-06-08"
        assert result[0]["value"] == 65

    @pytest.mark.skipif(_parse_trends_csv is None, reason="Implementation not yet available")
    def test_weekly_en_header_is_parsed(self) -> None:
        result = _parse_trends_csv(WEEKLY_EN_CSV)
        assert len(result) == 2, f"Expected 2 weekly points, got {len(result)}"
        assert result[0]["formatted_time"] == "2025-06-08"

    @pytest.mark.skipif(_parse_trends_csv is None, reason="Implementation not yet available")
    def test_monthly_uk_header_is_parsed(self) -> None:
        result = _parse_trends_csv(MONTHLY_UA_CSV)
        assert len(result) == 2, f"Expected 2 monthly points, got {len(result)}"
        assert result[0]["formatted_time"] == "2025-01"
        assert result[0]["value"] == 65

    @pytest.mark.skipif(_parse_trends_csv is None, reason="Implementation not yet available")
    def test_low_volume_lt_one_percent_is_normalized(self) -> None:
        result = _parse_trends_csv(LOW_VOLUME_CSV)
        assert len(result) == 2
        assert result[0]["value"] == 0  # "<1%" -> 0
        assert result[1]["value"] == 3

    @pytest.mark.skipif(_parse_trends_csv is None, reason="Implementation not yet available")
    def test_daily_header_still_parsed_after_fix(self) -> None:
        result = _parse_trends_csv(SINGLE_DATE_CSV)
        assert len(result) == 2




class TestBlockDetection:

    @pytest.mark.skipif(_detect_trends_block is None, reason="Implementation not yet available")
    def test_body_contains_too_many_requests(self) -> None:
        assert _detect_trends_block("Error: too many requests from your IP") is True

    @pytest.mark.skipif(_detect_trends_block is None, reason="Implementation not yet available")
    def test_body_contains_unusual_traffic(self) -> None:
        assert _detect_trends_block("We have detected unusual traffic from your network") is True

    @pytest.mark.skipif(_detect_trends_block is None, reason="Implementation not yet available")
    def test_body_contains_429(self) -> None:
        assert _detect_trends_block("HTTP Error 429: Too Many Requests") is True

    @pytest.mark.skipif(_detect_trends_block is None, reason="Implementation not yet available")
    def test_body_contains_automated_queries(self) -> None:
        assert _detect_trends_block("Our systems have detected automated queries from your computer") is True

    @pytest.mark.skipif(_detect_trends_block is None, reason="Implementation not yet available")
    def test_body_contains_detected_phrase(self) -> None:
        assert _detect_trends_block("our systems have detected unusual traffic patterns") is True

    @pytest.mark.skipif(_detect_trends_block is None, reason="Implementation not yet available")
    def test_normal_page_body_returns_false(self) -> None:
        body = "Interest over time\nDay,keyword\n2025-06-01,45"
        assert _detect_trends_block(body) is False

    @pytest.mark.skipif(_detect_trends_block is None, reason="Implementation not yet available")
    def test_empty_body_returns_false(self) -> None:
        assert _detect_trends_block("") is False

    @pytest.mark.skipif(_detect_trends_block is None, reason="Implementation not yet available")
    def test_case_insensitive_detection(self) -> None:
        assert _detect_trends_block("TOO MANY REQUESTS") is True




class TestSingleKeywordValidation:

    @pytest.mark.skipif(_validate_trends_keyword is None, reason="Implementation not yet available")
    def test_single_keyword_no_error(self) -> None:
        _validate_trends_keyword("test keyword")  # Should not raise

    @pytest.mark.skipif(_validate_trends_keyword is None, reason="Implementation not yet available")
    def test_keyword_with_comma_raises_value_error(self) -> None:
        with pytest.raises(ValueError) as excinfo:
            _validate_trends_keyword("test, keyword")
        assert "one-keyword" in str(excinfo.value).lower()

    @pytest.mark.skipif(_validate_trends_keyword is None, reason="Implementation not yet available")
    def test_empty_keyword_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            _validate_trends_keyword("")

    @pytest.mark.skipif(_validate_trends_keyword is None, reason="Implementation not yet available")
    def test_whitespace_only_keyword_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            _validate_trends_keyword("   ")




class TestGoogleTrendsResultConstruction:

    # GRACE: function _make_adapter declaration.
    def _make_adapter(self) -> BrowserScraperTrendsAdapter:
        return BrowserScraperTrendsAdapter()

    # ---- Successful CSV extraction ----

    @pytest.mark.skipif(
        not hasattr(BrowserScraperTrendsAdapter, 'get_trends'),
        reason="Adapter not available",
    )
    # GRACE: function test_successful_csv_returns_medium_confidence declaration.
    def test_successful_csv_returns_medium_confidence(self) -> None:
        adapter = self._make_adapter()
        request = GoogleTrendsRequest(keywords=["test keyword"])

        mock_result = BrowserScrapeResult(
            source="cloakbrowser",
            success=True,
            extracted_data={
                "timeline": [
                    {"time": "1748736000", "formatted_time": "2025-06-01", "value": 45},
                    {"time": "1749340800", "formatted_time": "2025-06-08", "value": 52},
                ],
            },
        )

        with patch.object(adapter, 'is_available', return_value=True):
            with patch('utils.browser_scraper.BrowserScraper') as MockScraper:
                mock_scraper_instance = MockScraper.return_value
                mock_scraper_instance.scrape_google_trends.return_value = mock_result

                result = adapter.get_trends(request)

        assert result.data_confidence == GoogleTrendsDataConfidence.MEDIUM.value

    @pytest.mark.skipif(
        not hasattr(BrowserScraperTrendsAdapter, 'get_trends'),
        reason="Adapter not available",
    )
    # GRACE: function test_successful_csv_has_correct_interest_point_fields declaration.
    def test_successful_csv_has_correct_interest_point_fields(self) -> None:
        adapter = self._make_adapter()
        request = GoogleTrendsRequest(keywords=["test keyword"])

        mock_result = BrowserScrapeResult(
            source="cloakbrowser",
            success=True,
            extracted_data={
                "timeline": [
                    {"time": "1748736000", "formatted_time": "2025-06-01", "value": 45},
                ],
            },
        )

        with patch.object(adapter, 'is_available', return_value=True):
            with patch('utils.browser_scraper.BrowserScraper') as MockScraper:
                mock_scraper_instance = MockScraper.return_value
                mock_scraper_instance.scrape_google_trends.return_value = mock_result

                result = adapter.get_trends(request)

        assert len(result.interest_over_time) == 1
        point = result.interest_over_time[0]
        # Correct field names for GoogleTrendsInterestPoint
        assert point.time == "1748736000"
        assert point.formatted_time == "2025-06-01"
        # values must be a dict, not a flat keyword/value attribute
        assert isinstance(point.values, dict)
        assert "test keyword" in point.values
        assert point.values["test keyword"] == 45

    @pytest.mark.skipif(
        not hasattr(BrowserScraperTrendsAdapter, 'get_trends'),
        reason="Adapter not available",
    )
    # GRACE: function test_successful_csv_has_no_failures declaration.
    def test_successful_csv_has_no_failures(self) -> None:
        adapter = self._make_adapter()
        request = GoogleTrendsRequest(keywords=["test keyword"])

        mock_result = BrowserScrapeResult(
            source="cloakbrowser",
            success=True,
            extracted_data={
                "timeline": [
                    {"time": "1748736000", "formatted_time": "2025-06-01", "value": 45},
                ],
            },
        )

        with patch.object(adapter, 'is_available', return_value=True):
            with patch('utils.browser_scraper.BrowserScraper') as MockScraper:
                mock_scraper_instance = MockScraper.return_value
                mock_scraper_instance.scrape_google_trends.return_value = mock_result

                result = adapter.get_trends(request)

        assert len(result.failures) == 0

    # ---- Blocked / 429 ----

    @pytest.mark.skipif(
        not hasattr(BrowserScraperTrendsAdapter, 'get_trends'),
        reason="Adapter not available",
    )
    # GRACE: function test_blocked_429_returns_blocked_confidence declaration.
    def test_blocked_429_returns_blocked_confidence(self) -> None:
        adapter = self._make_adapter()
        request = GoogleTrendsRequest(keywords=["test keyword"])

        with patch.object(adapter, 'is_available', return_value=True):
            with patch('utils.browser_scraper.BrowserScraper') as MockScraper:
                mock_scraper_instance = MockScraper.return_value
                mock_scraper_instance.scrape_google_trends.return_value = BrowserScrapeResult(
                    source="cloakbrowser",
                    success=False,
                    errors=["Google returned 429/block page"],
                )

                result = adapter.get_trends(request)

        assert result.data_confidence == GoogleTrendsDataConfidence.BLOCKED.value

    @pytest.mark.skipif(
        not hasattr(BrowserScraperTrendsAdapter, 'get_trends'),
        reason="Adapter not available",
    )
    # GRACE: function test_blocked_429_has_rate_limit_failure declaration.
    def test_blocked_429_has_rate_limit_failure(self) -> None:
        adapter = self._make_adapter()
        request = GoogleTrendsRequest(keywords=["test keyword"])

        with patch.object(adapter, 'is_available', return_value=True):
            with patch('utils.browser_scraper.BrowserScraper') as MockScraper:
                mock_scraper_instance = MockScraper.return_value
                mock_scraper_instance.scrape_google_trends.return_value = BrowserScrapeResult(
                    source="cloakbrowser",
                    success=False,
                    errors=["Google returned 429/block page"],
                )

                result = adapter.get_trends(request)

        assert len(result.failures) > 0
        rate_limit_failures = [f for f in result.failures if f.kind == "rate_limit"]
        assert len(rate_limit_failures) > 0, (
            f"Expected a failure with kind='rate_limit', got kinds: "
            f"{[f.kind for f in result.failures]}"
        )

    @pytest.mark.skipif(
        not hasattr(BrowserScraperTrendsAdapter, 'get_trends'),
        reason="Adapter not available",
    )
    # GRACE: function test_blocked_429_is_not_retryable declaration.
    def test_blocked_429_is_not_retryable(self) -> None:
        adapter = self._make_adapter()
        request = GoogleTrendsRequest(keywords=["test keyword"])

        with patch.object(adapter, 'is_available', return_value=True):
            with patch('utils.browser_scraper.BrowserScraper') as MockScraper:
                mock_scraper_instance = MockScraper.return_value
                mock_scraper_instance.scrape_google_trends.return_value = BrowserScrapeResult(
                    source="cloakbrowser",
                    success=False,
                    errors=["Google returned 429/block page"],
                )

                result = adapter.get_trends(request)

        for failure in result.failures:
            if failure.kind == "rate_limit":
                assert failure.retryable is False

    # ---- Empty CSV ----

    @pytest.mark.skipif(
        not hasattr(BrowserScraperTrendsAdapter, 'get_trends'),
        reason="Adapter not available",
    )
    # GRACE: function test_empty_csv_returns_low_confidence declaration.
    def test_empty_csv_returns_low_confidence(self) -> None:
        adapter = self._make_adapter()
        request = GoogleTrendsRequest(keywords=["test keyword"])

        mock_result = BrowserScrapeResult(
            source="cloakbrowser",
            success=True,
            extracted_data={"timeline": []},
        )

        with patch.object(adapter, 'is_available', return_value=True):
            with patch('utils.browser_scraper.BrowserScraper') as MockScraper:
                mock_scraper_instance = MockScraper.return_value
                mock_scraper_instance.scrape_google_trends.return_value = mock_result

                result = adapter.get_trends(request)

        assert result.data_confidence == GoogleTrendsDataConfidence.LOW.value

    @pytest.mark.skipif(
        not hasattr(BrowserScraperTrendsAdapter, 'get_trends'),
        reason="Adapter not available",
    )
    # GRACE: function test_empty_csv_has_empty_data_failure declaration.
    def test_empty_csv_has_empty_data_failure(self) -> None:
        adapter = self._make_adapter()
        request = GoogleTrendsRequest(keywords=["test keyword"])

        mock_result = BrowserScrapeResult(
            source="cloakbrowser",
            success=True,
            extracted_data={"timeline": []},
        )

        with patch.object(adapter, 'is_available', return_value=True):
            with patch('utils.browser_scraper.BrowserScraper') as MockScraper:
                mock_scraper_instance = MockScraper.return_value
                mock_scraper_instance.scrape_google_trends.return_value = mock_result

                result = adapter.get_trends(request)

        assert len(result.failures) > 0
        empty_data_failures = [f for f in result.failures if f.kind == "empty_data"]
        assert len(empty_data_failures) > 0, (
            f"Expected a failure with kind='empty_data', got kinds: "
            f"{[f.kind for f in result.failures]}"
        )

    @pytest.mark.skipif(
        not hasattr(BrowserScraperTrendsAdapter, 'get_trends'),
        reason="Adapter not available",
    )
    # GRACE: function test_empty_csv_has_no_interest_points declaration.
    def test_empty_csv_has_no_interest_points(self) -> None:
        adapter = self._make_adapter()
        request = GoogleTrendsRequest(keywords=["test keyword"])

        mock_result = BrowserScrapeResult(
            source="cloakbrowser",
            success=True,
            extracted_data={"timeline": []},
        )

        with patch.object(adapter, 'is_available', return_value=True):
            with patch('utils.browser_scraper.BrowserScraper') as MockScraper:
                mock_scraper_instance = MockScraper.return_value
                mock_scraper_instance.scrape_google_trends.return_value = mock_result

                result = adapter.get_trends(request)

        assert len(result.interest_over_time) == 0

    @pytest.mark.skipif(
        not hasattr(BrowserScraperTrendsAdapter, 'get_trends'),
        reason="Adapter not available",
    )
    # GRACE: function test_adapter_caps_support_multi_keyword_requests declaration.
    def test_adapter_caps_support_multi_keyword_requests(self) -> None:
        adapter = self._make_adapter()
        assert adapter.capabilities.max_keywords_per_request == 10

    @pytest.mark.skipif(
        not hasattr(BrowserScraperTrendsAdapter, 'get_trends'),
        reason="Adapter not available",
    )
    # GRACE: function test_multiple_keywords_are_processed_sequentially_and_merged declaration.
    def test_multiple_keywords_are_processed_sequentially_and_merged(self) -> None:
        adapter = self._make_adapter()
        request = GoogleTrendsRequest(keywords=["alpha", "beta"])

        alpha_result = BrowserScrapeResult(
            source="cloakbrowser",
            success=True,
            extracted_data={
                "timeline": [
                    {"time": "1748736000", "formatted_time": "2025-06-01", "value": 10},
                    {"time": "1749340800", "formatted_time": "2025-06-08", "value": 30},
                ],
            },
        )
        beta_result = BrowserScrapeResult(
            source="cloakbrowser",
            success=True,
            extracted_data={
                "timeline": [
                    {"time": "1748736000", "formatted_time": "2025-06-01", "value": 20},
                    {"time": "1749340800", "formatted_time": "2025-06-08", "value": 40},
                ],
            },
        )

        with patch.object(adapter, 'is_available', return_value=True):
            with patch('config.settings.load_config', return_value={
                "google_trends": {
                    "manual_start_wait": 0,
                    "min_delay": 0,
                    "max_delay": 0,
                    "state_file": "trends_state.json",
                    "headless": False,
                }
            }):
                with patch('utils.browser_scraper_trends.time.sleep') as sleep_mock:
                    with patch('utils.browser_scraper.BrowserScraper') as MockScraper:
                        mock_scraper_instance = MockScraper.return_value
                        mock_scraper_instance.scrape_google_trends.side_effect = [
                            alpha_result,
                            beta_result,
                        ]

                        result = adapter.get_trends(request)

        assert mock_scraper_instance.scrape_google_trends.call_count == 2
        assert mock_scraper_instance.scrape_google_trends.call_args_list == [
            call(["alpha"], {
                "geo": "UA",
                "timeframe": "today 12-m",
                "category": 0,
                "gprop": "",
                "hl": "en-US",
                "tz": 0,
                "locale": "en-US",
                "timezone": "Europe/Kyiv",
                "manual_start_wait": 0,
                "min_delay": 0,
                "max_delay": 0,
                "state_file": "trends_state.json",
                "headless": False,
                "keywords": ["alpha"],
            }),
            call(["beta"], {
                "geo": "UA",
                "timeframe": "today 12-m",
                "category": 0,
                "gprop": "",
                "hl": "en-US",
                "tz": 0,
                "locale": "en-US",
                "timezone": "Europe/Kyiv",
                "manual_start_wait": 0,
                "min_delay": 0,
                "max_delay": 0,
                "state_file": "trends_state.json",
                "headless": False,
                "keywords": ["beta"],
            }),
        ]
        assert sleep_mock.call_count == 1
        assert result.data_confidence == GoogleTrendsDataConfidence.MEDIUM.value
        assert result.failures == []
        assert len(result.interest_over_time) == 2
        first_point = result.interest_over_time[0]
        second_point = result.interest_over_time[1]
        assert first_point.values == {"alpha": 10, "beta": 20}
        assert second_point.values == {"alpha": 30, "beta": 40}
        assert result.averages == {"alpha": 20.0, "beta": 30.0}

    @pytest.mark.skipif(
        not hasattr(BrowserScraperTrendsAdapter, 'get_trends'),
        reason="Adapter not available",
    )
    # GRACE: function test_partial_multi_keyword_failures_return_degraded_confidence declaration.
    def test_partial_multi_keyword_failures_return_degraded_confidence(self) -> None:
        adapter = self._make_adapter()
        request = GoogleTrendsRequest(keywords=["alpha", "beta"])

        alpha_result = BrowserScrapeResult(
            source="cloakbrowser",
            success=True,
            extracted_data={
                "timeline": [
                    {"time": "1748736000", "formatted_time": "2025-06-01", "value": 10},
                ],
            },
        )
        beta_result = BrowserScrapeResult(
            source="cloakbrowser",
            success=False,
            errors=["Google returned 429/block page"],
            metadata={"status": "blocked"},
        )

        with patch.object(adapter, 'is_available', return_value=True):
            with patch('config.settings.load_config', return_value={
                "google_trends": {
                    "manual_start_wait": 0,
                    "min_delay": 0,
                    "max_delay": 0,
                    "state_file": "trends_state.json",
                    "headless": False,
                }
            }):
                with patch('utils.browser_scraper_trends.time.sleep') as sleep_mock:
                    with patch('utils.browser_scraper.BrowserScraper') as MockScraper:
                        mock_scraper_instance = MockScraper.return_value
                        mock_scraper_instance.scrape_google_trends.side_effect = [
                            alpha_result,
                            beta_result,
                        ]

                        result = adapter.get_trends(request)

        assert sleep_mock.call_count == 1
        assert result.data_confidence == GoogleTrendsDataConfidence.DEGRADED.value
        assert len(result.interest_over_time) == 1
        assert result.interest_over_time[0].values == {"alpha": 10}
        assert len(result.failures) == 1
        assert result.failures[0].kind == "rate_limit"
        assert result.provider_metadata["status"] == "partial"
        assert result.integrity_warnings

    @pytest.mark.skipif(
        not hasattr(BrowserScraperTrendsAdapter, 'get_trends'),
        reason="Adapter not available",
    )
    # GRACE: function test_partial_batch_with_only_empty_data_failures_returns_medium declaration.
    def test_partial_batch_with_only_empty_data_failures_returns_medium(self) -> None:
        adapter = self._make_adapter()
        request = GoogleTrendsRequest(keywords=["alpha", "page rank"])

        alpha_result = BrowserScrapeResult(
            source="cloakbrowser",
            success=True,
            extracted_data={
                "timeline": [
                    {"time": "1748736000", "formatted_time": "2025-06-01", "value": 10},
                    {"time": "1749340800", "formatted_time": "2025-06-08", "value": 30},
                ],
            },
        )
        # Benign: valid CSV download but zero data rows (genuinely low UA volume).
        page_rank_result = BrowserScrapeResult(
            source="cloakbrowser",
            success=True,
            extracted_data={"timeline": []},
        )

        with patch.object(adapter, 'is_available', return_value=True):
            with patch('config.settings.load_config', return_value={
                "google_trends": {
                    "manual_start_wait": 0,
                    "min_delay": 0,
                    "max_delay": 0,
                    "state_file": "trends_state.json",
                    "headless": False,
                }
            }):
                with patch('utils.browser_scraper_trends.time.sleep'):
                    with patch('utils.browser_scraper.BrowserScraper') as MockScraper:
                        mock_scraper_instance = MockScraper.return_value
                        mock_scraper_instance.scrape_google_trends.side_effect = [
                            alpha_result,
                            page_rank_result,
                        ]

                        result = adapter.get_trends(request)

        # Successful keyword data is preserved.
        assert len(result.interest_over_time) == 2
        assert result.interest_over_time[0].values == {"alpha": 10}
        assert result.interest_over_time[1].values == {"alpha": 30}
        assert result.averages == {"alpha": 20.0}

        # The benign empty_data failure is still recorded for debugging.
        assert len(result.failures) == 1
        assert result.failures[0].kind == "empty_data"
        assert result.provider_metadata["status"] == "partial"

        # Confidence is MEDIUM (not DEGRADED) — all failures are benign empty_data.
        assert result.data_confidence == GoogleTrendsDataConfidence.MEDIUM.value

        # integrity_warnings is ONE consolidated batch-level message ...
        assert len(result.integrity_warnings) == 1
        consolidated = result.integrity_warnings[0]
        assert "No Google Trends data for 1 of 2 keyword" in consolidated
        assert "page rank" in consolidated
        # ... and must NOT contain the duplicated per-keyword noise string.
        for warning in result.integrity_warnings:
            assert "Downloaded CSV contains no data rows" not in warning




class TestBrowserScraperTrendsExecution:

    # GRACE: function _make_scraper declaration.
    def _make_scraper(self) -> BrowserScraper:
        return BrowserScraper(BrowserScraperConfig(headless=False))

    @pytest.mark.skipif(
        not hasattr(BrowserScraper, "_execute_cloakbrowser_trends"),
        reason="Browser scraper Trends execution is unavailable",
    )
    # GRACE: function test_subresource_429_does_not_block_successful_csv_download declaration.
    def test_subresource_429_does_not_block_successful_csv_download(self, monkeypatch) -> None:
        page = _FakeTrendsPage(
            body_text="Interest over time",
            csv_content=WEEKLY_EN_CSV,
            responses=[
                _FakeResponse(429, "image"),
                _FakeResponse(200, "document"),
            ],
        )
        _install_fake_cloakbrowser(monkeypatch, page)

        scraper = self._make_scraper()
        result = scraper._execute_cloakbrowser_trends(
            ["seo"],
            {
                "geo": "UA",
                "timeframe": "today 12-m",
                "category": 0,
                "gprop": "",
                "hl": "en-US",
                "tz": 0,
                "state_file": "",
                "headless": False,
            },
        )

        assert result.success is True
        assert result.errors == []
        assert result.metadata["mode"] == "csv_download"
        assert result.extracted_data["status"] == "csv_downloaded"
        assert len(result.extracted_data["timeline"]) == 2

    @pytest.mark.skipif(
        not hasattr(BrowserScraper, "_execute_cloakbrowser_trends"),
        reason="Browser scraper Trends execution is unavailable",
    )
    # GRACE: function test_body_block_text_returns_blocked_result declaration.
    def test_body_block_text_returns_blocked_result(self, monkeypatch) -> None:
        page = _FakeTrendsPage(
            body_text="Our systems have detected unusual traffic from your computer network.",
            csv_content=WEEKLY_EN_CSV,
            responses=[
                _FakeResponse(200, "document"),
            ],
        )
        _install_fake_cloakbrowser(monkeypatch, page)

        scraper = self._make_scraper()
        result = scraper._execute_cloakbrowser_trends(
            ["seo"],
            {
                "geo": "UA",
                "timeframe": "today 12-m",
                "category": 0,
                "gprop": "",
                "hl": "en-US",
                "tz": 0,
                "state_file": "",
                "headless": False,
            },
        )

        assert result.success is False
        assert result.metadata["status"] == "blocked"
        assert result.errors == ["Google returned 429/block page"]




# GRACE: class TestSessionStateHelpers declaration.
class TestSessionStateHelpers:


    @pytest.mark.skipif(_load_session_state is None, reason="Implementation not yet available")
    def test_nonexistent_state_file_returns_empty_dict(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nonexistent.json"
            assert not path.exists()
            state = _load_session_state(path)
            assert isinstance(state, dict)
            assert len(state) == 0

    # ---- Valid JSON state file ----

    @pytest.mark.skipif(
        _load_session_state is None or _save_session_state is None,
        reason="Implementation not yet available",
    )
    # GRACE: function test_valid_state_file_returns_dict declaration.
    def test_valid_state_file_returns_dict(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state.json"
            expected = {
                "cookies": [{"name": "NID", "value": "abc123", "domain": ".google.com"}],
                "origins": [],
            }
            _save_session_state(path, expected)
            assert path.exists()

            loaded = _load_session_state(path)
            assert isinstance(loaded, dict)
            assert loaded == expected

    @pytest.mark.skipif(
        _load_session_state is None or _save_session_state is None,
        reason="Implementation not yet available",
    )
    # GRACE: function test_valid_state_file_contains_cookies declaration.
    def test_valid_state_file_contains_cookies(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state.json"
            cookies_data = [{"name": "NID", "value": "abc123"}]
            _save_session_state(path, {"cookies": cookies_data})
            loaded = _load_session_state(path)
            assert "cookies" in loaded
            assert len(loaded["cookies"]) > 0


    @pytest.mark.skipif(_load_session_state is None, reason="Implementation not yet available")
    def test_corrupted_state_file_returns_empty_dict(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "corrupted.json"
            path.write_text("{invalid: json content", encoding="utf-8")
            state = _load_session_state(path)
            assert isinstance(state, dict)
            assert len(state) == 0

    @pytest.mark.skipif(_load_session_state is None, reason="Implementation not yet available")
    def test_corrupted_state_file_logs_warning(self, caplog) -> None:
        from utils.logger import logger as _proj_logger
        _old_handlers = list(_proj_logger.main_logger.handlers)
        try:
            _proj_logger.main_logger.addHandler(caplog.handler)
            _proj_logger.main_logger.setLevel(logging.WARNING)
            with tempfile.TemporaryDirectory() as tmpdir:
                path = Path(tmpdir) / "corrupted.json"
                path.write_text("{invalid json}", encoding="utf-8")
                _load_session_state(path)

            warning_records = [
                r for r in caplog.records
                if r.levelno >= logging.WARNING and "state" in str(r.message).lower()
            ]
            assert len(warning_records) > 0, (
                f"Expected a warning log containing 'state', got: {[r.message for r in caplog.records]}"
            )
        finally:
            _proj_logger.main_logger.handlers = _old_handlers
# GRACE: ========================================================================= Fake browser harness for Trends execution tests =========================================================================
    # GRACE: class _FakeDownload declaration
# GRACE: function save_as declaration
    # GRACE: class _FakeDownloadContext declaration
    # GRACE: function __enter__ declaration
    # GRACE: function __exit__ declaration
    # GRACE: function value declaration
    # GRACE: class _FakeDownloadItem declaration
    # GRACE: function is_visible declaration
# GRACE: function click declaration
    # GRACE: class _FakeTextLocator declaration
    # GRACE: function first declaration
    # GRACE: function wait_for declaration
    # GRACE: function count declaration
    # GRACE: class _FakeBodyLocator declaration
# GRACE: function inner_text declaration
    # GRACE: class _FakeDownloadLocator declaration
    # GRACE: function count declaration
    # GRACE: function nth declaration
    # GRACE: function first declaration
# GRACE: function wait_for declaration
    # GRACE: class _FakeTrendsPage declaration
    # GRACE: function on declaration
    # GRACE: function wait_for_timeout declaration
    # GRACE: function expect_download declaration
# GRACE: function close declaration
    # GRACE: class _FakeTrendsContext declaration
# GRACE: function new_page declaration
    # GRACE: class _FakeTrendsBrowser declaration
    # GRACE: function new_context declaration
# GRACE: function close declaration
    # GRACE: class _FakeResponse declaration
# GRACE: ========================================================================= TestCSVParsing =========================================================================
    # GRACE: ---- Standard CSV ----
    # GRACE: function test_parse_standard_csv_returns_list declaration
    # GRACE: function test_parse_standard_csv_has_correct_row_count declaration
    # GRACE: function test_parse_standard_csv_has_expected_keys declaration
    # GRACE: function test_parse_standard_csv_values declaration
    # GRACE: function test_parse_standard_csv_time_present declaration
    # GRACE: ---- Header-only CSV ----
    # GRACE: function test_parse_header_only_csv_returns_empty_list declaration
    # GRACE: ---- Missing data columns ----
    # GRACE: function test_parse_missing_data_columns_returns_empty_list declaration
    # GRACE: function test_parse_missing_data_columns_logs_warning declaration
    # GRACE: ---- BOM ----
    # GRACE: function test_parse_csv_with_bom_returns_correct_count declaration
    # GRACE: function test_parse_csv_with_bom_values declaration
    # GRACE: ---- Single date column ----
    # GRACE: function test_parse_single_date_column_returns_list declaration
    # GRACE: function test_parse_single_date_column_count declaration
    # GRACE: function test_parse_single_date_column_values declaration
# GRACE: ========================================================================= TestCSVGranularityHeaders (regression for the live "no parsing" bug) =========================================================================
    # GRACE: function test_weekly_uk_header_is_parsed declaration
    # GRACE: function test_weekly_ru_header_is_parsed declaration
    # GRACE: function test_weekly_en_header_is_parsed declaration
    # GRACE: function test_monthly_uk_header_is_parsed declaration
    # GRACE: function test_low_volume_lt_one_percent_is_normalized declaration
    # GRACE: function test_daily_header_still_parsed_after_fix declaration
# GRACE: ========================================================================= TestBlockDetection =========================================================================
    # GRACE: class TestBlockDetection declaration
    # GRACE: function test_body_contains_too_many_requests declaration
    # GRACE: function test_body_contains_unusual_traffic declaration
    # GRACE: function test_body_contains_429 declaration
    # GRACE: function test_body_contains_automated_queries declaration
    # GRACE: function test_body_contains_detected_phrase declaration
    # GRACE: function test_normal_page_body_returns_false declaration
    # GRACE: function test_empty_body_returns_false declaration
    # GRACE: function test_case_insensitive_detection declaration
# GRACE: ========================================================================= TestSingleKeywordValidation =========================================================================
    # GRACE: class TestSingleKeywordValidation declaration
    # GRACE: function test_single_keyword_no_error declaration
    # GRACE: function test_keyword_with_comma_raises_value_error declaration
    # GRACE: function test_empty_keyword_raises_value_error declaration
    # GRACE: function test_whitespace_only_keyword_raises_value_error declaration
# GRACE: ========================================================================= TestGoogleTrendsResultConstruction =========================================================================
    # GRACE: class TestGoogleTrendsResultConstruction declaration
    # GRACE: Regression test for Fix 2: a PARTIAL batch where some keywords succeed with real timeline data AND the only failures are benign empty_data (valid CSV, zero rows) must NOT be stamped DEGRADED Such all-empty_data partial batches map to MEDIUM confidence with ONE consolidated batch-level integrity warning; the per-keyword "Downloaded CSV contains no data rows for ..." noise must NOT leak into integrity_warnings (it gets duplicated across every exported row)
# GRACE: ========================================================================= TestBrowserScraperTrendsExecution =========================================================================
    # GRACE: class TestBrowserScraperTrendsExecution declaration
# GRACE: ========================================================================= TestSessionStateHelpers =========================================================================
    # GRACE: ---- Non-existent state file ----
    # GRACE: function test_nonexistent_state_file_returns_empty_dict declaration
    # GRACE: ---- Corrupted JSON ----
    # GRACE: function test_corrupted_state_file_returns_empty_dict declaration
    # GRACE: function test_corrupted_state_file_logs_warning declaration
