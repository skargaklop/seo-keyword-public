"""
Unit tests for cache, rate limiter, cleanup, and history modules (improvement #17).
"""

import os
import time
from pathlib import Path

import pytest

from utils.cache import ScrapingCache
from utils.rate_limiter import RateLimiter, get_rate_limiter
from utils.cleanup import cleanup_api_logs, cleanup_old_files
from utils.history import HistoryManager
from components.results import _build_history_signature
from components.sidebar import (
    GOOGLE_ADS_CURRENCIES,
    GOOGLE_ADS_LANGUAGES,
    GOOGLE_ADS_LOCATIONS,
    LOG_LEVELS,
    UI_LANGUAGE_OPTIONS,
    _build_sidebar_config_updates,
    _normalize_log_level_name,
    _resolve_google_ads_selection,
    _safe_log_level_index,
)


class TestScrapingCache:
    def test_set_and_get(self) -> None:
        cache = ScrapingCache(ttl_seconds=60)
        cache.set("https://example.com", "content")
        assert cache.get("https://example.com") == "content"

    def test_cache_miss(self) -> None:
        cache = ScrapingCache(ttl_seconds=60)
        assert cache.get("https://nonexistent.com") is None

    def test_cache_expiry(self) -> None:
        cache = ScrapingCache(ttl_seconds=1)
        cache.set("https://example.com", "content")
        time.sleep(1.1)
        assert cache.get("https://example.com") is None

    def test_invalidate(self) -> None:
        cache = ScrapingCache(ttl_seconds=60)
        cache.set("https://example.com", "content")
        cache.invalidate("https://example.com")
        assert cache.get("https://example.com") is None

    def test_clear(self) -> None:
        cache = ScrapingCache(ttl_seconds=60)
        cache.set("url1", "data1")
        cache.set("url2", "data2")
        assert cache.size == 2
        cache.clear()
        assert cache.size == 0

    def test_size(self) -> None:
        cache = ScrapingCache(ttl_seconds=60)
        assert cache.size == 0
        cache.set("url1", "data1")
        assert cache.size == 1


class TestRateLimiter:
    def test_basic_wait(self) -> None:
        limiter = RateLimiter(requests_per_minute=600)  # 10 per second
        start = time.time()
        limiter.wait()
        limiter.wait()
        elapsed = time.time() - start
        assert elapsed >= 0.09  # At least ~0.1s between calls

    def test_get_rate_limiter(self) -> None:
        limiter1 = get_rate_limiter("test_provider")
        limiter2 = get_rate_limiter("test_provider")
        assert limiter1 is limiter2  # Same instance

    def test_different_providers(self) -> None:
        limiter1 = get_rate_limiter("provider_a")
        limiter2 = get_rate_limiter("provider_b")
        assert limiter1 is not limiter2


class TestCleanup:
    def test_cleanup_old_files(self, tmp_path: Path) -> None:
        # Create an old file
        old_file = tmp_path / "old_file.xlsx"
        old_file.write_text("old data")
        # Set modification time to 10 days ago
        old_time = time.time() - (10 * 86400)
        os.utime(old_file, (old_time, old_time))

        # Create a new file
        new_file = tmp_path / "new_file.xlsx"
        new_file.write_text("new data")

        deleted = cleanup_old_files(directory=tmp_path, max_age_days=7)
        assert len(deleted) == 1
        assert not old_file.exists()
        assert new_file.exists()

    def test_cleanup_empty_dir(self, tmp_path: Path) -> None:
        deleted = cleanup_old_files(directory=tmp_path, max_age_days=7)
        assert deleted == []

    def test_cleanup_nonexistent_dir(self) -> None:
        deleted = cleanup_old_files(directory=Path("/nonexistent/dir"), max_age_days=7)
        assert deleted == []


class TestHistoryManager:
    def test_save_and_load(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Redirect history file to tmp
        test_file = tmp_path / "history.json"
        monkeypatch.setattr("utils.history.HISTORY_FILE", test_file)
        monkeypatch.setattr("utils.history.HISTORY_DIR", tmp_path)

        HistoryManager.save_entry(
            urls=["https://example.com"],
            keywords=["кофе", "чай"],
            keyword_count=2,
            url_count=1,
        )

        history = HistoryManager.load_history()
        assert len(history) == 1
        assert history[0]["url_count"] == 1
        assert history[0]["keyword_count"] == 2

    def test_save_entry_persists_checkpoint_payload(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        test_file = tmp_path / "history.json"
        monkeypatch.setattr("utils.history.HISTORY_FILE", test_file)
        monkeypatch.setattr("utils.history.HISTORY_DIR", tmp_path)

        HistoryManager.save_entry(
            urls=["https://example.com"],
            keywords=["buy boxes"],
            keyword_count=1,
            url_count=1,
            checkpoint={
                "workflow_mode": "url_llm",
                "active_inputs": ["https://example.com"],
                "scraped_content": {"https://example.com": "cached text"},
                "processed_data": [{"Keyword": "buy boxes", "Source URL": "https://example.com"}],
            },
        )

        history = HistoryManager.load_history()
        assert history[0]["checkpoint"]["workflow_mode"] == "url_llm"
        assert history[0]["checkpoint"]["scraped_content"] == {
            "https://example.com": "cached text"
        }

    def test_clear_history(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        test_file = tmp_path / "history.json"
        monkeypatch.setattr("utils.history.HISTORY_FILE", test_file)
        monkeypatch.setattr("utils.history.HISTORY_DIR", tmp_path)

        HistoryManager.save_entry(
            urls=["url1"], keywords=["kw1"], keyword_count=1, url_count=1
        )
        HistoryManager.clear_history()
        history = HistoryManager.load_history()
        assert history == []


class TestSidebarHelpers:
    def test_normalize_log_level_name_handles_aliases_and_fallback(self) -> None:
        assert _normalize_log_level_name("debug", "INFO") == "DEBUG"
        assert _normalize_log_level_name("Warn", "INFO") == "WARNING"
        assert _normalize_log_level_name("unexpected", "INFO") == "INFO"

    def test_safe_log_level_index_uses_default_for_unknown_level(self) -> None:
        expected = LOG_LEVELS.index("ERROR")
        assert _safe_log_level_index("not-a-level", "ERROR") == expected

    def test_resolve_google_ads_selection_uses_saved_config(self) -> None:
        locations = {
            "Ukraine": "2804",
            "Russia": "2643",
            "Germany": "2276",
        }
        languages = {
            "Russian & Ukrainian": ["1031", "1036"],
            "Russian": "1031",
            "Ukrainian": "1036",
        }

        location_name, language_name = _resolve_google_ads_selection(
            {"location_id": "2276", "language_id": "1036"},
            locations,
            languages,
        )

        assert location_name == "Germany"
        assert language_name == "Ukrainian"

    def test_google_ads_constants_match_expected_ids(self) -> None:
        assert GOOGLE_ADS_LOCATIONS["Ukraine"] == "2804"
        assert GOOGLE_ADS_LOCATIONS["United States"] == "2840"
        assert GOOGLE_ADS_LANGUAGES["Russian"] == "1031"
        assert GOOGLE_ADS_LANGUAGES["Ukrainian"] == "1036"
        assert GOOGLE_ADS_LANGUAGES["English"] == "1000"
        assert GOOGLE_ADS_LANGUAGES["German"] == "1001"
        assert GOOGLE_ADS_LANGUAGES["French"] == "1002"
        assert GOOGLE_ADS_LANGUAGES["Spanish"] == "1003"
        assert GOOGLE_ADS_LANGUAGES["Italian"] == "1004"
        assert GOOGLE_ADS_LANGUAGES["Portuguese"] == "1014"
        assert GOOGLE_ADS_LANGUAGES["Russian & Ukrainian"] == ["1031", "1036"]
        assert GOOGLE_ADS_CURRENCIES == ["UAH", "USD", "EUR"]

    def test_resolve_google_ads_selection_supports_new_language_ids(self) -> None:
        location_name, language_name = _resolve_google_ads_selection(
            {"location_id": "2276", "language_id": "1001"},
            GOOGLE_ADS_LOCATIONS,
            GOOGLE_ADS_LANGUAGES,
        )

        assert location_name == "Germany"
        assert language_name == "German"

    def test_google_ads_locations_include_requested_eu_and_cis_countries(self) -> None:
        expected_locations = {
            "Austria": "2040",
            "Belgium": "2056",
            "Bulgaria": "2100",
            "Hungary": "2348",
            "Germany": "2276",
            "Greece": "2300",
            "Denmark": "2208",
            "Ireland": "2372",
            "Spain": "2724",
            "Italy": "2380",
            "Cyprus": "2196",
            "Latvia": "2428",
            "Lithuania": "2440",
            "Luxembourg": "2442",
            "Malta": "2470",
            "Netherlands": "2528",
            "Poland": "2616",
            "Portugal": "2620",
            "Romania": "2642",
            "Slovakia": "2703",
            "Slovenia": "2705",
            "Finland": "2246",
            "France": "2250",
            "Croatia": "2191",
            "Czech Republic": "2203",
            "Sweden": "2752",
            "Estonia": "2233",
            "Azerbaijan": "2031",
            "Armenia": "2051",
            "Belarus": "2112",
            "Kazakhstan": "2398",
            "Kyrgyzstan": "2417",
            "Moldova": "2498",
            "Tajikistan": "2762",
            "Uzbekistan": "2860",
            "Georgia": "2268",
        }

        for country, location_id in expected_locations.items():
            assert GOOGLE_ADS_LOCATIONS[country] == location_id

    def test_ui_language_options_include_english(self) -> None:
        assert UI_LANGUAGE_OPTIONS["🇬🇧 English"] == "en"

    def test_build_sidebar_config_updates_persists_google_ads_and_logging(self) -> None:
        config = {
            "llm": {"prompts": {}},
            "retry": {},
            "logging": {},
            "google_ads": {},
            "ui": {},
        }

        updated = _build_sidebar_config_updates(
            config,
            {
                "keyword_prompt": "kw",
                "seo_prompt": "seo",
                "api_timeout": 15,
                "api_delay": 2,
                "api_retry_count": 5,
                "api_retry_delay": 9,
                "cleanup_max_age": 30,
                "app_log_level": "debug",
                "console_logging_enabled": True,
                "console_log_level": "info",
                "api_logging_enabled": False,
                "api_log_level": "warning",
                "api_retention_days": 14,
                "error_log_level": "error",
                "log_test_runs": True,
                "provider": "OpenAI",
                "model_name": "gpt-5.2",
                "max_keywords": 25,
                "history_retention_days": 45,
                "upload_max_file_size_mb": 8,
                "upload_max_rows": 2500,
                "ui_lang": "en",
                "location_id": "2276",
                "language_id": "1002",
                "currency_code": "USD",
            },
        )

        assert updated["google_ads"]["location_id"] == "2276"
        assert updated["google_ads"]["language_id"] == "1002"
        assert updated["google_ads"]["currency_code"] == "USD"
        assert updated["retry"]["delay_seconds"] == 9
        assert updated["logging"]["app_level"] == "DEBUG"
        assert updated["logging"]["console_level"] == "INFO"
        assert updated["logging"]["api_level"] == "WARNING"
        assert updated["logging"]["api_retention_days"] == 14
        assert updated["logging"]["error_level"] == "ERROR"
        assert updated["history"]["retention_days"] == 45
        assert updated["uploads"]["max_file_size_mb"] == 8
        assert updated["uploads"]["max_rows"] == 2500
        assert updated["ui"]["language"] == "en"


class TestHistoryHelpers:
    def test_build_history_signature_distinguishes_runs(self) -> None:
        run_a = _build_history_signature("run-a", ["https://example.com"], ["kw1"])
        run_b = _build_history_signature("run-b", ["https://example.com"], ["kw1"])

        assert run_a != run_b


class TestRetentionCleanup:
    def test_cleanup_api_logs_removes_old_rotated_files(self, tmp_path: Path) -> None:
        old_log = tmp_path / "api_requests.log.1"
        old_log.write_text("old")
        old_time = time.time() - (10 * 86400)
        os.utime(old_log, (old_time, old_time))

        fresh_log = tmp_path / "api_requests.log"
        fresh_log.write_text("fresh")

        deleted = cleanup_api_logs(directory=tmp_path, max_age_days=7)

        assert str(old_log) in deleted
        assert not old_log.exists()
        assert fresh_log.exists()

    def test_trim_history_entries_removes_only_old_items(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        test_file = tmp_path / "history.json"
        monkeypatch.setattr("utils.history.HISTORY_FILE", test_file)
        monkeypatch.setattr("utils.history.HISTORY_DIR", tmp_path)
        test_file.write_text(
            '[{"timestamp":"2026-01-01T00:00:00","urls":["a"],"keywords":[],"keyword_count":0,"url_count":1},'
            '{"timestamp":"2026-03-10T00:00:00","urls":["b"],"keywords":[],"keyword_count":0,"url_count":1}]',
            encoding="utf-8",
        )

        removed = HistoryManager.trim_history_entries(
            max_age_days=30,
            now_ts=1773100800.0,
        )

        history = HistoryManager.load_history()
        assert removed == 1
        assert len(history) == 1
        assert history[0]["urls"] == ["b"]
