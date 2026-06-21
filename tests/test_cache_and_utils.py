"""
Unit tests for cache, rate limiter, cleanup, and history modules (improvement #17).
Phase 10 Task 5: Added history schema migration and cache record tests.
"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# MODULE_CONTRACT: tests/test_cache_and_utils
# Purpose: Verify cache, sidebar-adjacent utility behavior, history migration, and cleanup helpers.
# Rationale: Links shared utility tests to sidebar and request-cache verification entries.
# Dependencies: pytest, streamlit, utils.cache, utils.history, utils.rate_limiter, utils.cleanup.
# Exports: pytest tests.
# LINKS: knowledge-graph.xml#MOD-011, knowledge-graph.xml#MOD-014
# MODULE_MAP: tests/test_cache_and_utils.py
# Public Functions: pytest test functions.
# Private Helpers: fixtures and local helpers in this file.
# Key Semantic Blocks: none.
# Critical Flows: construct utility state -> exercise cache/history/sidebar-adjacent behavior -> assert stable outputs.
# Verification: verification-plan.xml#V-09-SIDEBAR, verification-plan.xml#V-10-HISTORY-CACHE
# CHANGE_SUMMARY: Added GRACE module contract linking this test file to MOD-011 and MOD-014.

import pytest
import streamlit as st

from utils.cache import ScrapingCache
from utils.rate_limiter import RateLimiter, get_rate_limiter
from utils.cleanup import cleanup_api_logs, cleanup_old_files
from utils.history import (
    HistoryManager,
    migrate_history_data,
    HISTORY_SCHEMA_VERSION,
)
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
    _section_config_value,
    _safe_log_level_index,
    _sync_sidebar_widget_from_config,
)


# Purpose: TestScrapingCache implementation
class TestScrapingCache:
    # Purpose: Test set and get
    def test_set_and_get(self) -> None:
        cache = ScrapingCache(ttl_seconds=60)
        cache.set("https://example.com", "content")
        assert cache.get("https://example.com") == "content"

    # Purpose: Test cache miss
    def test_cache_miss(self) -> None:
        cache = ScrapingCache(ttl_seconds=60)
        assert cache.get("https://nonexistent.com") is None

    # Purpose: Test cache expiry
    def test_cache_expiry(self) -> None:
        cache = ScrapingCache(ttl_seconds=1)
        cache.set("https://example.com", "content")
        time.sleep(1.1)
        assert cache.get("https://example.com") is None

    # Purpose: Test invalidate
    def test_invalidate(self) -> None:
        cache = ScrapingCache(ttl_seconds=60)
        cache.set("https://example.com", "content")
        cache.invalidate("https://example.com")
        assert cache.get("https://example.com") is None

    # Purpose: Test clear
    def test_clear(self) -> None:
        cache = ScrapingCache(ttl_seconds=60)
        cache.set("url1", "data1")
        cache.set("url2", "data2")
        assert cache.size == 2
        cache.clear()
        assert cache.size == 0

    # Purpose: Test size
    def test_size(self) -> None:
        cache = ScrapingCache(ttl_seconds=60)
        assert cache.size == 0
        cache.set("url1", "data1")
        assert cache.size == 1


# Purpose: TestRateLimiter implementation
class TestRateLimiter:
    # Purpose: Test basic wait
    def test_basic_wait(self) -> None:
        limiter = RateLimiter(requests_per_minute=600)  # 10 per second
        start = time.time()
        limiter.wait()
        limiter.wait()
        elapsed = time.time() - start
        assert elapsed >= 0.09  # At least ~0.1s between calls

    # Purpose: Test get rate limiter
    def test_get_rate_limiter(self) -> None:
        limiter1 = get_rate_limiter("test_provider")
        limiter2 = get_rate_limiter("test_provider")
        assert limiter1 is limiter2  # Same instance

    # Purpose: Test different providers
    def test_different_providers(self) -> None:
        limiter1 = get_rate_limiter("provider_a")
        limiter2 = get_rate_limiter("provider_b")
        assert limiter1 is not limiter2


# Purpose: TestCleanup implementation
class TestCleanup:
    # Purpose: Test cleanup old files.
    # Create an old file, age it by 10 days, and create a new file.
    def test_cleanup_old_files(self, tmp_path: Path) -> None:
        old_file = tmp_path / "old_file.xlsx"
        old_file.write_text("old data")
        old_time = time.time() - (10 * 86400)
        os.utime(old_file, (old_time, old_time))

        new_file = tmp_path / "new_file.xlsx"
        new_file.write_text("new data")

        deleted = cleanup_old_files(directory=tmp_path, max_age_days=7)
        assert len(deleted) == 1
        assert not old_file.exists()
        assert new_file.exists()

    # Purpose: Test cleanup empty dir
    def test_cleanup_empty_dir(self, tmp_path: Path) -> None:
        deleted = cleanup_old_files(directory=tmp_path, max_age_days=7)
        assert deleted == []

    # Purpose: Test cleanup nonexistent dir
    def test_cleanup_nonexistent_dir(self) -> None:
        deleted = cleanup_old_files(directory=Path("/nonexistent/dir"), max_age_days=7)
        assert deleted == []


# Purpose: TestHistoryManager implementation
class TestHistoryManager:
    # Purpose: Test save and load.
    # Redirect the history file into the temporary directory.
    def test_save_and_load(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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

    # Purpose: Test save entry persists checkpoint payload
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

    # Purpose: Test clear history
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

    # Purpose: Test clear history with cache removes all records
    def test_clear_history_with_cache_removes_all_records(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        test_file = tmp_path / "history.json"
        monkeypatch.setattr("utils.history.HISTORY_FILE", test_file)
        monkeypatch.setattr("utils.history.HISTORY_DIR", tmp_path)

        test_file.write_text(
            json.dumps({
                "schema_version": 2,
                "records": [
                    {"record_type": "history", "created_at": "2026-06-05T00:00:00", "urls": ["a"]},
                    {"record_type": "cache", "kind": "serp", "cache_key": "key1"},
                ],
            }),
            encoding="utf-8",
        )

        assert HistoryManager.clear_history(clear_cache=True) is True
        assert HistoryManager.load_history(include_cache=True) == []


# Purpose: TestSidebarHelpers implementation
class TestSidebarHelpers:
    # Purpose: Test section config value prefers fresh config over module default
    def test_section_config_value_prefers_fresh_config_over_module_default(
        self,
    ) -> None:
        assert (
            _section_config_value(
                {"enabled": True},
                {"enabled": False},
                "enabled",
                False,
            )
            is True
        )

    # Purpose: Test sync sidebar widget updates when saved config changes
    def test_sync_sidebar_widget_updates_when_saved_config_changes(self) -> None:
        st.session_state.clear()

        _sync_sidebar_widget_from_config("seo_math_enabled_checkbox", False)
        assert st.session_state["seo_math_enabled_checkbox"] is False

        _sync_sidebar_widget_from_config("seo_math_enabled_checkbox", True)

        assert st.session_state["seo_math_enabled_checkbox"] is True

    # Purpose: Test sync sidebar widget preserves unsaved ui toggle
    def test_sync_sidebar_widget_preserves_unsaved_ui_toggle(self) -> None:
        st.session_state.clear()

        _sync_sidebar_widget_from_config("seo_math_enabled_checkbox", True)
        st.session_state["seo_math_enabled_checkbox"] = False

        _sync_sidebar_widget_from_config("seo_math_enabled_checkbox", True)

        assert st.session_state["seo_math_enabled_checkbox"] is False

    # Purpose: Test normalize log level name handles aliases and fallback
    def test_normalize_log_level_name_handles_aliases_and_fallback(self) -> None:
        assert _normalize_log_level_name("debug", "INFO") == "DEBUG"
        assert _normalize_log_level_name("Warn", "INFO") == "WARNING"
        assert _normalize_log_level_name("unexpected", "INFO") == "INFO"

    # Purpose: Test safe log level index uses default for unknown level
    def test_safe_log_level_index_uses_default_for_unknown_level(self) -> None:
        expected = LOG_LEVELS.index("ERROR")
        assert _safe_log_level_index("not-a-level", "ERROR") == expected

    # Purpose: Test resolve google ads selection uses saved config
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

    # Purpose: Test google ads constants match expected ids
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

    # Purpose: Test resolve google ads selection supports new language ids
    def test_resolve_google_ads_selection_supports_new_language_ids(self) -> None:
        location_name, language_name = _resolve_google_ads_selection(
            {"location_id": "2276", "language_id": "1001"},
            GOOGLE_ADS_LOCATIONS,
            GOOGLE_ADS_LANGUAGES,
        )

        assert location_name == "Germany"
        assert language_name == "German"

    # Purpose: Test google ads locations include requested eu and cis countries
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

    # Purpose: Test ui language options include english
    def test_ui_language_options_include_english(self) -> None:
        assert UI_LANGUAGE_OPTIONS["🇬🇧 English"] == "en"

    # Purpose: Test build sidebar config updates persists google ads and logging
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


# Purpose: TestHistoryHelpers implementation
class TestHistoryHelpers:
    # Purpose: Test build history signature distinguishes runs
    def test_build_history_signature_distinguishes_runs(self) -> None:
        run_a = _build_history_signature("run-a", ["https://example.com"], ["kw1"])
        run_b = _build_history_signature("run-b", ["https://example.com"], ["kw1"])

        assert run_a != run_b


# Purpose: TestRetentionCleanup implementation
class TestRetentionCleanup:
    # Purpose: Test cleanup api logs removes old rotated files
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

    # Purpose: Test trim history entries removes only old items
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


# Purpose: Phase 10 Task 5: Tests for history schema v2 migration (HIGH-01).
class TestHistoryMigration:

    # Purpose: Old schema (list) should migrate to new schema (dict).
    def test_migrate_from_old_list_schema(self) -> None:
        old_data = [
            {"timestamp": "2026-01-01T00:00:00", "urls": ["a"], "keywords": ["kw1"]},
            {"timestamp": "2026-02-01T00:00:00", "urls": ["b"], "keywords": ["kw2"]},
        ]

        migrated = migrate_history_data(old_data)

        assert isinstance(migrated, dict)
        assert migrated["schema_version"] == HISTORY_SCHEMA_VERSION
        assert "records" in migrated
        assert len(migrated["records"]) == 2
        assert "migrated_at" in migrated

    # Purpose: Running migration multiple times should be safe.
    def test_migration_is_idempotent(self) -> None:
        old_data = [
            {"timestamp": "2026-01-01T00:00:00", "urls": ["a"], "keywords": ["kw1"]},
        ]

        migrated1 = migrate_history_data(old_data)
        migrated2 = migrate_history_data(migrated1)

        assert migrated1 == migrated2

    # Purpose: Migration should preserve checkpoint payloads.
    def test_migration_preserves_checkpoint_data(self) -> None:
        old_data = [
            {
                "timestamp": "2026-01-01T00:00:00",
                "urls": ["https://example.com"],
                "keywords": ["kw1"],
                "checkpoint": {"workflow_mode": "url_llm", "processed_data": [1, 2, 3]},
            },
        ]

        migrated = migrate_history_data(old_data)

        record = migrated["records"][0]
        assert record["checkpoint"]["workflow_mode"] == "url_llm"
        assert record["checkpoint"]["processed_data"] == [1, 2, 3]

    # Purpose: Already-migrated data should pass through unchanged.
    def test_new_schema_passthrough(self) -> None:
        new_data = {
            "schema_version": HISTORY_SCHEMA_VERSION,
            "records": [{"created_at": "2026-06-05T00:00:00", "record_type": "cache"}],
            "migrated_at": "2026-06-05T00:00:00",
        }

        migrated = migrate_history_data(new_data)

        assert migrated == new_data

    # Purpose: Future schema versions should not be downgraded by v2 migration.
    def test_future_schema_passthrough(self) -> None:
        future_data = {
            "schema_version": HISTORY_SCHEMA_VERSION + 1,
            "records": [{"record_type": "future", "payload": {"ok": True}}],
            "future_field": "preserve",
        }

        migrated = migrate_history_data(future_data)

        assert migrated is future_data
        assert migrated["schema_version"] == HISTORY_SCHEMA_VERSION + 1
        assert migrated["future_field"] == "preserve"


# Purpose: Phase 10 Task 5: Tests for HistoryManager with cache records.
class TestHistoryManagerWithCache:

    # Purpose: Test save entry preserves cache records
    def test_save_entry_preserves_cache_records(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Saving history entry should preserve existing cache records."""
        test_file = tmp_path / "history.json"
        monkeypatch.setattr("utils.history.HISTORY_FILE", test_file)
        monkeypatch.setattr("utils.history.HISTORY_DIR", tmp_path)

        # Create history with cache record
        test_file.write_text(
            json.dumps({
                "schema_version": 2,
                "records": [
                    {
                        "record_type": "cache",
                        "kind": "serp",
                        "cache_key": "test_key",
                        "expires_at": (datetime.now() + timedelta(days=1)).isoformat(),
                    },
                ],
            }),
            encoding="utf-8",
        )

        # Save new history entry
        HistoryManager.save_entry(
            urls=["https://new.com"],
            keywords=["new_kw"],
            keyword_count=1,
            url_count=1,
        )

        # Load all records
        all_records = HistoryManager.load_all_records()

        # Cache record should be preserved
        cache_records = [r for r in all_records if r.get("record_type") == "cache"]
        assert len(cache_records) == 1
        assert cache_records[0]["cache_key"] == "test_key"

        # New history entry should be present
        history_records = [r for r in all_records if r.get("record_type") != "cache"]
        assert len(history_records) == 1
        assert history_records[0]["urls"] == ["https://new.com"]

    # Purpose: Test load history excludes cache records
    def test_load_history_excludes_cache_records(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """load_history should return only visible history, not cache records."""
        test_file = tmp_path / "history.json"
        monkeypatch.setattr("utils.history.HISTORY_FILE", test_file)
        monkeypatch.setattr("utils.history.HISTORY_DIR", tmp_path)

        test_file.write_text(
            json.dumps({
                "schema_version": 2,
                "records": [
                    {
                        "record_type": "history",
                        "created_at": "2026-06-05T00:00:00",
                        "urls": ["https://example.com"],
                        "keywords": ["kw1"],
                    },
                    {
                        "record_type": "cache",
                        "kind": "serp",
                        "cache_key": "key1",
                    },
                    {
                        "record_type": "cache",
                        "kind": "ads",
                        "cache_key": "key2",
                    },
                ],
            }),
            encoding="utf-8",
        )

        history = HistoryManager.load_history()

        # Should only return visible history
        assert len(history) == 1
        assert history[0]["record_type"] == "history"

    # Purpose: Test trim preserves unexpired cache
    def test_trim_preserves_unexpired_cache(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Trim history should preserve unexpired cache records."""
        test_file = tmp_path / "history.json"
        monkeypatch.setattr("utils.history.HISTORY_FILE", test_file)
        monkeypatch.setattr("utils.history.HISTORY_DIR", tmp_path)

        future_time = (datetime.now() + timedelta(days=1)).isoformat()

        test_file.write_text(
            json.dumps({
                "schema_version": 2,
                "records": [
                    {
                        "record_type": "history",
                        "created_at": "2026-01-01T00:00:00",
                        "urls": ["old"],
                    },
                    {
                        "record_type": "cache",
                        "kind": "serp",
                        "cache_key": "valid_cache",
                        "expires_at": future_time,
                    },
                ],
            }),
            encoding="utf-8",
        )

        HistoryManager.trim_history_entries(max_age_days=30)

        # Should remove old history but keep valid cache
        all_records = HistoryManager.load_all_records()
        cache_records = [r for r in all_records if r.get("record_type") == "cache"]

        assert len(cache_records) == 1
        assert cache_records[0]["cache_key"] == "valid_cache"

    # Purpose: Test clear history preserves cache by default
    def test_clear_history_preserves_cache_by_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """clear_history should preserve cache records by default."""
        test_file = tmp_path / "history.json"
        monkeypatch.setattr("utils.history.HISTORY_FILE", test_file)
        monkeypatch.setattr("utils.history.HISTORY_DIR", tmp_path)

        future_time = (datetime.now() + timedelta(days=1)).isoformat()

        test_file.write_text(
            json.dumps({
                "schema_version": 2,
                "records": [
                    {
                        "record_type": "history",
                        "created_at": "2026-06-05T00:00:00",
                        "urls": ["a"],
                    },
                    {
                        "record_type": "cache",
                        "kind": "serp",
                        "cache_key": "cache1",
                        "expires_at": future_time,
                    },
                ],
            }),
            encoding="utf-8",
        )

        HistoryManager.clear_history(clear_cache=False)

        all_records = HistoryManager.load_all_records()
        cache_records = [r for r in all_records if r.get("record_type") == "cache"]
        history_records = [r for r in all_records if r.get("record_type") != "cache"]

        # Cache should be preserved
        assert len(cache_records) == 1
        # History should be cleared
        assert len(history_records) == 0

    # Purpose: get_cache_stats should return accurate statistics.
    def test_get_cache_stats(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        test_file = tmp_path / "history.json"
        monkeypatch.setattr("utils.history.HISTORY_FILE", test_file)
        monkeypatch.setattr("utils.history.HISTORY_DIR", tmp_path)

        future_time = (datetime.now() + timedelta(days=1)).isoformat()
        expired_time = (datetime.now() - timedelta(hours=1)).isoformat()

        test_file.write_text(
            json.dumps({
                "schema_version": 2,
                "records": [
                    {
                        "record_type": "history",
                        "created_at": "2026-06-05T00:00:00",
                    },
                    {
                        "record_type": "cache",
                        "kind": "serp",
                        "cache_key": "key1",
                        "cache_hit_count": 5,
                        "expires_at": future_time,
                    },
                    {
                        "record_type": "cache",
                        "kind": "ads",
                        "cache_key": "key2",
                        "cache_hit_count": 3,
                        "expires_at": expired_time,
                    },
                ],
            }),
            encoding="utf-8",
        )

        stats = HistoryManager.get_cache_stats()

        assert stats["total_cache_records"] == 2
        assert stats["total_visible_history"] == 1
        assert stats["by_kind"]["serp"] == 1
        assert stats["by_kind"]["ads"] == 1
        assert stats["total_hits"] == 8
        assert stats["expired_count"] == 1


# Purpose: Phase 10 Task 11: Tests for cache key collision prevention via settings hash (HIGH-02).
class TestCacheSettingsHash:

    # Purpose: Settings hash should be deterministic and stable across multiple runs.
    def test_settings_hash_is_stable_across_runs(self):
        from utils.request_cache import build_settings_hash

        config = {
            "seo_math": {
                "analyze_bm25f": True,
                "bm25f_params": {"k1": 1.2, "b_body": 0.75},
                "field_weights": {"serp_title": 3.0, "page_title": 3.0},
                "signals": {"title_alignment": True, "content_effort": True},
            },
            "llm": {"provider": "openai", "model": "gpt-4"},
            "cache": {"enabled": True, "default_ttl_hours": 168},
            "google_trends": {"default_geo": "UA", "cache_ttl_hours": 24},
            "ui": {"language": "en"},  # Should be ignored
            "logging": {"app_level": "INFO"},  # Should be ignored
        }

        # Build hash multiple times
        hash1 = build_settings_hash(config)
        hash2 = build_settings_hash(config)
        hash3 = build_settings_hash(config)

        # All hashes should be identical
        assert hash1 == hash2 == hash3
        assert len(hash1) == 64  # SHA256 hex length

    # Purpose: Changing UI-only settings should NOT invalidate cache.
    def test_settings_hash_ignores_ui_only_settings(self):
        from utils.request_cache import build_settings_hash

        config_base = {
            "seo_math": {"analyze_bm25f": True},
            "llm": {"provider": "openai"},
        }

        config_ui_en = {**config_base, "ui": {"language": "en"}}
        config_ui_ru = {**config_base, "ui": {"language": "ru"}}
        config_ui_uk = {**config_base, "ui": {"language": "uk"}}

        hash_en = build_settings_hash(config_ui_en)
        hash_ru = build_settings_hash(config_ui_ru)
        hash_uk = build_settings_hash(config_ui_uk)

        # All hashes should be identical despite different UI languages
        assert hash_en == hash_ru == hash_uk

    # Purpose: Changing logging settings should NOT invalidate cache.
    def test_settings_hash_ignores_logging_settings(self):
        from utils.request_cache import build_settings_hash

        config_debug = {
            "seo_math": {"analyze_bm25f": True},
            "logging": {"app_level": "DEBUG"},
        }
        config_info = {
            "seo_math": {"analyze_bm25f": True},
            "logging": {"app_level": "INFO"},
        }
        config_error = {
            "seo_math": {"analyze_bm25f": True},
            "logging": {"app_level": "ERROR"},
        }

        hash_debug = build_settings_hash(config_debug)
        hash_info = build_settings_hash(config_info)
        hash_error = build_settings_hash(config_error)

        # All hashes should be identical despite different log levels
        assert hash_debug == hash_info == hash_error

    # Purpose: Changing BM25F analysis toggle SHOULD invalidate cache.
    def test_settings_hash_changes_with_bm25f_toggle(self):
        from utils.request_cache import build_settings_hash

        config_enabled = {"seo_math": {"analyze_bm25f": True}}
        config_disabled = {"seo_math": {"analyze_bm25f": False}}

        hash_enabled = build_settings_hash(config_enabled)
        hash_disabled = build_settings_hash(config_disabled)

        assert hash_enabled != hash_disabled

    # Purpose: Changing BM25F parameters SHOULD invalidate cache.
    def test_settings_hash_changes_with_bm25f_params(self):
        from utils.request_cache import build_settings_hash

        config_k1_1_2 = {"seo_math": {"bm25f_params": {"k1": 1.2}}}
        config_k1_2_0 = {"seo_math": {"bm25f_params": {"k1": 2.0}}}

        hash_1_2 = build_settings_hash(config_k1_1_2)
        hash_2_0 = build_settings_hash(config_k1_2_0)

        assert hash_1_2 != hash_2_0

    # Purpose: Changing field weights SHOULD invalidate cache.
    def test_settings_hash_changes_with_field_weights(self):
        from utils.request_cache import build_settings_hash

        config_default = {
            "seo_math": {
                "field_weights": {"serp_title": 3.0, "h1": 2.5}
            }
        }
        config_custom = {
            "seo_math": {
                "field_weights": {"serp_title": 5.0, "h1": 1.0}
            }
        }

        hash_default = build_settings_hash(config_default)
        hash_custom = build_settings_hash(config_custom)

        assert hash_default != hash_custom

    # Purpose: Changing LLM provider SHOULD invalidate cache.
    def test_settings_hash_changes_with_llm_provider(self):
        from utils.request_cache import build_settings_hash

        config_openai = {"llm": {"provider": "openai", "model": "gpt-4"}}
        config_anthropic = {"llm": {"provider": "anthropic", "model": "gpt-4"}}

        hash_openai = build_settings_hash(config_openai)
        hash_anthropic = build_settings_hash(config_anthropic)

        assert hash_openai != hash_anthropic

    # Purpose: Changing LLM model SHOULD invalidate cache.
    def test_settings_hash_changes_with_llm_model(self):
        from utils.request_cache import build_settings_hash

        config_gpt4 = {"llm": {"provider": "openai", "model": "gpt-4"}}
        config_gpt35 = {"llm": {"provider": "openai", "model": "gpt-3.5"}}

        hash_gpt4 = build_settings_hash(config_gpt4)
        hash_gpt35 = build_settings_hash(config_gpt35)

        assert hash_gpt4 != hash_gpt35

    # Purpose: Changing cache TTL SHOULD invalidate cache.
    def test_settings_hash_changes_with_cache_ttl(self):
        from utils.request_cache import build_settings_hash

        config_24h = {"cache": {"default_ttl_hours": 24}}
        config_168h = {"cache": {"default_ttl_hours": 168}}

        hash_24h = build_settings_hash(config_24h)
        hash_168h = build_settings_hash(config_168h)

        assert hash_24h != hash_168h

    # Purpose: Changing Google Trends config SHOULD invalidate cache.
    def test_settings_hash_changes_with_google_trends_config(self):
        from utils.request_cache import build_settings_hash

        config_ua = {"google_trends": {"default_geo": "UA"}}
        config_us = {"google_trends": {"default_geo": "US"}}

        hash_ua = build_settings_hash(config_ua)
        hash_us = build_settings_hash(config_us)

        assert hash_ua != hash_us

    # Purpose: UI display toggles should NOT affect cache hash.
    def test_settings_hash_ignores_display_toggles(self):
        from utils.request_cache import build_settings_hash

        base_config = {"seo_math": {"analyze_bm25f": True}}

        config_with_display = {
            **base_config,
            "ui": {
                "show_bm25f_details": True,
                "show_signal_details": True,
                "compact_view": False,
            },
        }

        config_without_display = {
            **base_config,
            "ui": {
                "show_bm25f_details": False,
                "show_signal_details": False,
                "compact_view": True,
            },
        }

        hash_with = build_settings_hash(config_with_display)
        hash_without = build_settings_hash(config_without_display)

        assert hash_with == hash_without

    # Purpose: Cache keys must include settings hash for collision prevention.
    def test_cache_key_includes_settings_hash(self, tmp_path: Path, monkeypatch):
        from utils.request_cache import build_cache_key, build_settings_hash

        params = {"keywords": ["coffee", "tea"]}

        settings_hash1 = build_settings_hash({"seo_math": {"analyze_bm25f": True}})
        settings_hash2 = build_settings_hash({"seo_math": {"analyze_bm25f": False}})

        key1 = build_cache_key("math", "local", params, settings_hash1)
        key2 = build_cache_key("math", "local", params, settings_hash2)

        # Different settings hashes should produce different cache keys
        assert key1 != key2

    # Purpose: Cache keys should remain stable when only UI settings change.
    def test_cache_key_stable_with_ui_changes(self, tmp_path: Path, monkeypatch):
        from utils.request_cache import build_cache_key, build_settings_hash

        params = {"keywords": ["coffee"]}

        # Both configs have same cache-relevant settings, different UI
        config1 = {
            "seo_math": {"analyze_bm25f": True},
            "ui": {"language": "en"},
        }
        config2 = {
            "seo_math": {"analyze_bm25f": True},
            "ui": {"language": "ru"},
        }

        settings_hash1 = build_settings_hash(config1)
        settings_hash2 = build_settings_hash(config2)

        key1 = build_cache_key("serp", "test", params, settings_hash1)
        key2 = build_cache_key("serp", "test", params, settings_hash2)

        # Same cache-relevant settings = same cache key
        assert key1 == key2

    # Purpose: Test cache miss after analysis settings change
    def test_cache_miss_after_analysis_settings_change(
        self, tmp_path: Path, monkeypatch
    ):
        """Changing analysis settings should cause cache miss."""
        from utils.request_cache import (
            RequestCache,
            build_cache_key,
            build_settings_hash,
        )

        test_file = tmp_path / "history.json"
        monkeypatch.setattr("utils.request_cache.HISTORY_FILE", test_file)

        cache = RequestCache(enabled=True)

        params = {"keywords": ["test"]}

        # Cache with BM25F enabled
        settings_enabled = build_settings_hash({"seo_math": {"analyze_bm25f": True}})
        key_enabled = build_cache_key("math", "local", params, settings_enabled)

        cache.set("math", key_enabled, params, {"bm25f_enabled": True})

        # Should hit cache
        assert cache.get(key_enabled) is not None

        # Try with BM25F disabled - different settings hash
        settings_disabled = build_settings_hash({"seo_math": {"analyze_bm25f": False}})
        key_disabled = build_cache_key("math", "local", params, settings_disabled)

        # Should miss cache (different settings)
        assert cache.get(key_disabled) is None

    # Purpose: Changing only UI settings should still hit cache.
    def test_cache_hit_after_ui_only_change(self, tmp_path: Path, monkeypatch):
        from utils.request_cache import (
            RequestCache,
            build_cache_key,
            build_settings_hash,
        )

        test_file = tmp_path / "history.json"
        monkeypatch.setattr("utils.request_cache.HISTORY_FILE", test_file)

        cache = RequestCache(enabled=True)

        params = {"keywords": ["test"]}

        # Cache with UI language set to English
        config_en = {"seo_math": {"analyze_bm25f": True}, "ui": {"language": "en"}}
        hash_en = build_settings_hash(config_en)
        key_en = build_cache_key("serp", "test", params, hash_en)

        cache.set("serp", key_en, params, {"results": "data"})

        # Should hit cache with same cache-relevant settings
        config_ru = {"seo_math": {"analyze_bm25f": True}, "ui": {"language": "ru"}}
        hash_ru = build_settings_hash(config_ru)
        key_ru = build_cache_key("serp", "test", params, hash_ru)

        # Same key, should hit cache despite different UI language
        assert key_en == key_ru
        assert cache.get(key_ru) is not None
        assert cache.get(key_ru)["result"]["payload"] == {"results": "data"}

    # Purpose: Wildcard patterns should match sub-settings.
    def test_is_cache_relevant_setting_wildcard_match(self):
        from utils.request_cache import is_cache_relevant_setting

        # cache.* should match all cache sub-settings
        assert is_cache_relevant_setting("cache.enabled")
        assert is_cache_relevant_setting("cache.default_ttl_hours")
        assert is_cache_relevant_setting("cache.max_cache_records")

        # google_trends.* should match all trends sub-settings
        assert is_cache_relevant_setting("google_trends.default_geo")
        assert is_cache_relevant_setting("google_trends.cache_ttl_hours")
        assert is_cache_relevant_setting("google_trends.batch_delay_seconds")

    # Purpose: Exact path matches should return True.
    def test_is_cache_relevant_setting_exact_match(self):
        from utils.request_cache import is_cache_relevant_setting

        assert is_cache_relevant_setting("seo_math.analyze_bm25f")
        assert is_cache_relevant_setting("llm.provider")
        assert is_cache_relevant_setting("llm.model")

    # Purpose: Nested settings under cache-relevant parents should match.
    def test_is_cache_relevant_setting_nested_match(self):
        from utils.request_cache import is_cache_relevant_setting

        # Nested under seo_math.bm25f_params
        assert is_cache_relevant_setting("seo_math.bm25f_params.k1")
        assert is_cache_relevant_setting("seo_math.bm25f_params.b_body")

        # Nested under seo_math.field_weights
        assert is_cache_relevant_setting("seo_math.field_weights.serp_title")
        assert is_cache_relevant_setting("seo_math.field_weights.h1")

        # Nested under seo_math.signals
        assert is_cache_relevant_setting("seo_math.signals.title_alignment")
        assert is_cache_relevant_setting("seo_math.signals.content_effort")

    # Purpose: UI-only settings should return False.
    def test_is_cache_relevant_setting_ui_only_false(self):
        from utils.request_cache import is_cache_relevant_setting

        assert not is_cache_relevant_setting("ui.language")
        assert not is_cache_relevant_setting("ui.provider")
        assert not is_cache_relevant_setting("ui.show_bm25f_details")
        assert not is_cache_relevant_setting("logging.app_level")
        assert not is_cache_relevant_setting("logging.console_level")
        assert not is_cache_relevant_setting("retry.delay_seconds")

    # Purpose: Extraction should filter out UI-only settings.
    def test_extract_cache_relevant_settings_filters_ui(self):
        from utils.request_cache import _extract_cache_relevant_settings

        full_config = {
            "seo_math": {
                "analyze_bm25f": True,
                "bm25f_params": {"k1": 1.2},
            },
            "llm": {"provider": "openai", "model": "gpt-4"},
            "cache": {"enabled": True, "default_ttl_hours": 168},
            "google_trends": {"default_geo": "UA"},
            "ui": {"language": "en", "compact_view": True},
            "logging": {"app_level": "DEBUG"},
        }

        relevant = _extract_cache_relevant_settings(full_config)

        # Should include cache-relevant settings
        assert "seo_math" in relevant
        assert "llm" in relevant
        assert "cache" in relevant
        assert "google_trends" in relevant

        # Should NOT include UI-only settings
        assert "ui" not in relevant
        assert "logging" not in relevant

    # Purpose: Extraction should preserve entire subtrees for relevant paths.
    def test_extract_cache_relevant_settings_preserves_subtrees(self):
        from utils.request_cache import _extract_cache_relevant_settings

        full_config = {
            "seo_math": {
                "analyze_bm25f": True,
                "bm25f_params": {
                    "k1": 1.2,
                    "b_body": 0.75,
                    "b_title": 0.5,
                },
                "field_weights": {
                    "serp_title": 3.0,
                    "page_title": 3.0,
                    "h1": 2.5,
                },
            },
            "ui": {"language": "en"},
        }

        relevant = _extract_cache_relevant_settings(full_config)

        # Should preserve entire seo_math subtree
        assert relevant["seo_math"]["analyze_bm25f"] is True
        assert relevant["seo_math"]["bm25f_params"]["k1"] == 1.2
        assert relevant["seo_math"]["bm25f_params"]["b_body"] == 0.75
        assert relevant["seo_math"]["bm25f_params"]["b_title"] == 0.5
        assert relevant["seo_math"]["field_weights"]["serp_title"] == 3.0
        assert relevant["seo_math"]["field_weights"]["page_title"] == 3.0
        assert relevant["seo_math"]["field_weights"]["h1"] == 2.5

        # Should NOT include ui
        assert "ui" not in relevant

    # Purpose: Relevant settings subtrees should not preserve secret-bearing keys.
    def test_extract_cache_relevant_settings_strips_nested_secrets(self):
        from utils.request_cache import _extract_cache_relevant_settings

        full_config = {
            "google_trends": {
                "default_geo": "UA",
                "api_key": "secret-value",
                "nested": {"access_token": "token-value", "batch_delay_seconds": 2},
            },
            "cache": {
                "enabled": True,
                "credentials": {"password": "hidden", "safe_value": "kept"},
            },
        }

        relevant = _extract_cache_relevant_settings(full_config)

        assert relevant["google_trends"]["default_geo"] == "UA"
        assert "api_key" not in relevant["google_trends"]
        assert "access_token" not in relevant["google_trends"]["nested"]
        assert relevant["google_trends"]["nested"]["batch_delay_seconds"] == 2
        assert "credentials" not in relevant["cache"]

    # Purpose: Settings hash should handle empty config gracefully.
    def test_settings_hash_empty_config(self):
        from utils.request_cache import build_settings_hash

        hash1 = build_settings_hash({})
        hash2 = build_settings_hash({})

        # Should be stable
        assert hash1 == hash2
        assert len(hash1) == 64

    # Purpose: Settings hash should handle None by using app config.
    def test_settings_hash_none_config(self):
        from utils.request_cache import build_settings_hash

        # When None is passed, it should use the module's config
        # This test verifies it doesn't crash
        hash_result = build_settings_hash(None)

        # Should return a valid hash (or empty string on error)
        assert isinstance(hash_result, str)
        # If config loading works, should be a proper hash
        if hash_result:
            assert len(hash_result) == 64


# ---------------------------------------------------------------------------
# PLAN 15-03: History/Cache visibility and duplicate key tests (HIST-15-01, HIST-15-02)
# ---------------------------------------------------------------------------

# Purpose: HIST-15-01: History entries must have unique keys for Streamlit widgets.
class TestHistoryUniqueKeys:

    # Purpose: Test history entry with created at has unique key
    def test_history_entry_with_created_at_has_unique_key(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Entries saved with created_at (no timestamp) must produce unique keys."""
        test_file = tmp_path / "history.json"
        monkeypatch.setattr("utils.history.HISTORY_FILE", test_file)
        monkeypatch.setattr("utils.history.HISTORY_DIR", tmp_path)

        # Save two entries in quick succession (same second)
        HistoryManager.save_entry(
            urls=["https://a.com"], keywords=["kw1"], keyword_count=1, url_count=1
        )
        HistoryManager.save_entry(
            urls=["https://b.com"], keywords=["kw2"], keyword_count=1, url_count=1
        )

        history = HistoryManager.load_history()
        assert len(history) == 2

        # Both entries should have created_at
        keys = []
        for entry in history:
            raw_ts = entry.get("timestamp") or entry.get("created_at", "na")
            keys.append(f"history-restore::{raw_ts}")

        # Keys must be unique (no duplicates from "na" fallback)
        assert len(keys) == len(set(keys)), f"Duplicate keys found: {keys}"

    # Purpose: Test history entry without timestamp uses created at for key
    def test_history_entry_without_timestamp_uses_created_at_for_key(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Entry with only created_at should use created_at as key, not 'na'."""
        test_file = tmp_path / "history.json"
        monkeypatch.setattr("utils.history.HISTORY_FILE", test_file)
        monkeypatch.setattr("utils.history.HISTORY_DIR", tmp_path)

        HistoryManager.save_entry(
            urls=["https://example.com"], keywords=["kw"], keyword_count=1, url_count=1
        )

        history = HistoryManager.load_history()
        assert len(history) == 1

        entry = history[0]
        assert "created_at" in entry
        assert "timestamp" not in entry

        # The key should use created_at, not fallback to "na"
        raw_ts = entry.get("timestamp") or entry.get("created_at", "na")
        assert raw_ts != "na", "Key should not fallback to 'na' when created_at exists"


# Purpose: HIST-15-02: Cache records visibility can be toggled.
class TestCacheVisibilityToggle:

    # Purpose: Test load all records includes cache
    def test_load_all_records_includes_cache(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """load_all_records should return all records including cache."""
        test_file = tmp_path / "history.json"
        monkeypatch.setattr("utils.history.HISTORY_FILE", test_file)
        monkeypatch.setattr("utils.history.HISTORY_DIR", tmp_path)

        test_file.write_text(
            json.dumps({
                "schema_version": 2,
                "records": [
                    {"record_type": "history", "created_at": "2026-06-05T00:00:00", "urls": ["a"]},
                    {"record_type": "cache", "kind": "serp", "cache_key": "key1"},
                ],
            }),
            encoding="utf-8",
        )

        all_records = HistoryManager.load_all_records()
        assert len(all_records) == 2
        cache_records = [r for r in all_records if r.get("record_type") == "cache"]
        assert len(cache_records) == 1

    # Purpose: Test load history excludes cache by default
    def test_load_history_excludes_cache_by_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """load_history should exclude cache records by default."""
        test_file = tmp_path / "history.json"
        monkeypatch.setattr("utils.history.HISTORY_FILE", test_file)
        monkeypatch.setattr("utils.history.HISTORY_DIR", tmp_path)

        test_file.write_text(
            json.dumps({
                "schema_version": 2,
                "records": [
                    {"record_type": "history", "created_at": "2026-06-05T00:00:00", "urls": ["a"]},
                    {"record_type": "cache", "kind": "serp", "cache_key": "key1"},
                ],
            }),
            encoding="utf-8",
        )

        history = HistoryManager.load_history()
        assert len(history) == 1
        assert history[0]["record_type"] == "history"

    # Purpose: Test load history can include cache when toggled
    def test_load_history_can_include_cache_when_toggled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """load_history with include_cache=True should include cache records."""
        test_file = tmp_path / "history.json"
        monkeypatch.setattr("utils.history.HISTORY_FILE", test_file)
        monkeypatch.setattr("utils.history.HISTORY_DIR", tmp_path)

        test_file.write_text(
            json.dumps({
                "schema_version": 2,
                "records": [
                    {"record_type": "history", "created_at": "2026-06-05T00:00:00", "urls": ["a"]},
                    {"record_type": "cache", "kind": "serp", "cache_key": "key1"},
                ],
            }),
            encoding="utf-8",
        )

        # This test will FAIL until load_history supports include_cache parameter
        history = HistoryManager.load_history(include_cache=True)
        assert len(history) == 2


# Purpose: EXPORT-15-03: Merged report export combining SERP, Ads, and math analysis.
class TestMergedReportExport:

    # Purpose: Test export merged report has all sections
    def test_export_merged_report_has_all_sections(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Merged export should include SERP, Ads, and math analysis sections."""
        from utils.excel_exporter import ExcelExporter

        # Create test data for each section
        serp_df = pd.DataFrame({
            "URL": ["https://a.com", "https://b.com"],
            "Title": ["Title A", "Title B"],
            "Position": [1, 2],
        })
        ads_df = pd.DataFrame({
            "Keyword": ["coffee", "tea"],
            "Avg Monthly Searches": [1000, 500],
            "Competition": [0.8, 0.5],
        })
        math_df = pd.DataFrame({
            "Keyword": ["coffee"],
            "BM25F Score": [2.5],
            "TF-IDF": [0.8],
        })

        exporter = ExcelExporter()
        # Use the allowed outputs directory
        outputs_dir = Path(__file__).parent.parent / "outputs"
        outputs_dir.mkdir(exist_ok=True)
        output_path = outputs_dir / "merged_report.xlsx"

        try:
            result = exporter.export_merged_report(
                output_path=output_path,
                serp_data=serp_df,
                ads_data=ads_df,
                math_data=math_df,
                report_title="Test Merged Report",
            )

            assert result is True
            assert output_path.exists()
        finally:
            # Cleanup
            if output_path.exists():
                output_path.unlink()

    # Purpose: Test export merged report includes serp sheet
    def test_export_merged_report_includes_serp_sheet(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Merged export should have a SERP Analysis sheet."""
        from utils.excel_exporter import ExcelExporter

        serp_df = pd.DataFrame({
            "URL": ["https://example.com"],
            "Title": ["Example"],
        })

        exporter = ExcelExporter()
        # Use the allowed outputs directory
        outputs_dir = Path(__file__).parent.parent / "outputs"
        outputs_dir.mkdir(exist_ok=True)
        output_path = outputs_dir / "merged_serp.xlsx"

        try:
            exporter.export_merged_report(
                output_path=output_path,
                serp_data=serp_df,
                ads_data=pd.DataFrame(),
                math_data=pd.DataFrame(),
            )

            # Verify the file contains expected sheet names
            import openpyxl
            wb = openpyxl.load_workbook(output_path)
            sheet_names = wb.sheetnames
            assert any("SERP" in name.upper() for name in sheet_names), \
                f"Expected SERP sheet, got: {sheet_names}"
        finally:
            # Cleanup
            if output_path.exists():
                output_path.unlink()
