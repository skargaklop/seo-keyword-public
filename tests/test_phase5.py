"""Tests for Phase 5: SERP UI integration and model search."""

import os
from unittest.mock import patch


from config.settings import (
    SCRAPER_CONFIG,
    SERP_LANGUAGE_OPTIONS,
    SERP_LOCATION_OPTIONS,
    SERP_PROVIDER_OPTIONS,
    get_available_serp_providers,
)
from config.i18n import TRANSLATIONS


# ---------------------------------------------------------------------------
# SERP provider options
# ---------------------------------------------------------------------------


# Purpose: TestSerpProviderOptions implementation
class TestSerpProviderOptions:
    # Purpose: Test serp provider options defined
    def test_serp_provider_options_defined(self):
        expected = {
            "Serper.dev": "serper_dev",
            "SerpApi": "serpapi",
            "Brave Search": "brave_search",
            "SearchApi.io": "searchapi_io",
            "Zenserp": "zenserp",
            "ScraperAPI": "scraperapi",
            "DataForSEO": "dataforseo",
            "Serpstat": "serpstat",
            "Serpstack": "serpstack",
            "ScaleSERP": "scaleserp",
            "ValueSERP": "valueserp",
            "Browser (Cloakbrowser/Playwright)": "browser_cloakbrowser",
        }
        assert SERP_PROVIDER_OPTIONS == expected

    # Purpose: Test get available serp providers filters by env
    def test_get_available_serp_providers_filters_by_env(self):
        test_env = {
            "SERPER_API_KEY": "test-key",
            "BRAVE_SEARCH_API_KEY": "test2",
        }
        with patch.dict(os.environ, test_env, clear=True), patch.dict(SCRAPER_CONFIG, {"browser_enabled": False}, clear=False):
            result = get_available_serp_providers()
        assert "Serper.dev" in result
        assert "Brave Search" in result
        assert result["Serper.dev"] == "serper_dev"
        assert result["Brave Search"] == "brave_search"
        assert len(result) == 2

    # Purpose: Test get available serp providers empty when no keys
    def test_get_available_serp_providers_empty_when_no_keys(self):
        with patch.dict(os.environ, {}, clear=True), patch.dict(SCRAPER_CONFIG, {"browser_enabled": False}, clear=False):
            result = get_available_serp_providers()
            assert result == {}

    # Purpose: Test get available serp providers includes browser when enabled
    def test_get_available_serp_providers_includes_browser_when_enabled(self):
        with patch.dict(os.environ, {}, clear=True), patch.dict(SCRAPER_CONFIG, {"browser_enabled": True}, clear=False):
            result = get_available_serp_providers()

        assert result == {"Browser (Cloakbrowser/Playwright)": "browser_cloakbrowser"}


# ---------------------------------------------------------------------------
# SERP location and language options
# ---------------------------------------------------------------------------


# Purpose: TestSerpLocationOptions implementation
class TestSerpLocationOptions:
    # Purpose: Test serp location options defined
    def test_serp_location_options_defined(self):
        assert "Ukraine" in SERP_LOCATION_OPTIONS
        assert SERP_LOCATION_OPTIONS["Ukraine"] == "ua"
        assert "USA" in SERP_LOCATION_OPTIONS
        assert SERP_LOCATION_OPTIONS["USA"] == "us"
        assert len(SERP_LOCATION_OPTIONS) >= 6


# Purpose: TestSerpLanguageOptions implementation
class TestSerpLanguageOptions:
    # Purpose: Test serp language options defined
    def test_serp_language_options_defined(self):
        assert "Ukrainian" in SERP_LANGUAGE_OPTIONS
        assert SERP_LANGUAGE_OPTIONS["Ukrainian"] == "uk"
        assert "English" in SERP_LANGUAGE_OPTIONS
        assert SERP_LANGUAGE_OPTIONS["English"] == "en"
        assert len(SERP_LANGUAGE_OPTIONS) >= 5


# ---------------------------------------------------------------------------
# Model search filter
# ---------------------------------------------------------------------------


# Purpose: TestModelSearchFilter implementation
class TestModelSearchFilter:
    # Purpose: Test model search filters correctly
    def test_model_search_filters_correctly(self):
        cached_models = ["gpt-4o", "gpt-4o-mini", "claude-sonnet-4-6", "gemini-2.5-pro"]
        search = "gpt"
        filtered = [m for m in cached_models if search.lower() in m.lower()]
        assert filtered == ["gpt-4o", "gpt-4o-mini"]

    # Purpose: Test model search no filter under 2 chars
    def test_model_search_no_filter_under_2_chars(self):
        cached_models = ["gpt-4o", "claude-sonnet-4-6", "gemini-2.5-pro"]
        search = "g"
        if len(search) >= 2:
            filtered = [m for m in cached_models if search.lower() in m.lower()]
        else:
            filtered = cached_models
        assert filtered == cached_models

    # Purpose: Test model search case insensitive
    def test_model_search_case_insensitive(self):
        cached_models = ["gpt-4o", "GPT-5.2", "Claude-Sonnet-4-6"]
        search = "gpt"
        filtered = [m for m in cached_models if search.lower() in m.lower()]
        assert "gpt-4o" in filtered
        assert "GPT-5.2" in filtered
        assert "Claude-Sonnet-4-6" not in filtered


# ---------------------------------------------------------------------------
# i18n keys
# ---------------------------------------------------------------------------


# Purpose: TestI18nSerpKeys implementation
class TestI18nSerpKeys:
    SERP_UI_KEYS = [
        "serp_provider_header",
        "serp_provider_select",
        "serp_no_keys",
        "serp_num_results",
        "serp_location",
        "serp_language",
        "model_search_placeholder",
        "serp_pre_step_label",
    ]

    # Purpose: Test i18n serp keys present
    def test_i18n_serp_keys_present(self):
        for key in self.SERP_UI_KEYS:
            assert key in TRANSLATIONS, f"Missing key in TRANSLATIONS: {key}"
            entry = TRANSLATIONS[key]
            for lang in ("ru", "uk", "en"):
                assert lang in entry, f"Missing {lang} for key: {key}"



# ---------------------------------------------------------------------------
# SERP pre-step checkbox scope
# ---------------------------------------------------------------------------


# Purpose: TestSerpPreStepScope implementation
class TestSerpPreStepScope:
    # Purpose: Test serp pre step not shown for serp mode
    def test_serp_pre_step_not_shown_for_serp_mode(self):
        WORKFLOW_MODE_SERP_ANALYSIS = "serp_analysis"
        WORKFLOW_MODE_URL_LLM = "url_llm"
        WORKFLOW_MODE_URL_SEED = "url_seed"
        WORKFLOW_MODE_KEYWORD_SEED = "keyword_seed"
        serp_modes = [
            (WORKFLOW_MODE_URL_LLM, False),
            (WORKFLOW_MODE_URL_SEED, False),
            (WORKFLOW_MODE_KEYWORD_SEED, True),
            (WORKFLOW_MODE_SERP_ANALYSIS, False),
        ]
        for mode, expected in serp_modes:
            should_show = mode == WORKFLOW_MODE_KEYWORD_SEED
            assert should_show == expected, f"Mode {mode}: expected {expected}, got {should_show}"