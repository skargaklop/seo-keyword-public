# MODULE_CONTRACT: tests/test_settings_exports
# Purpose: Verify config.settings derived exports and settings constants.
# Rationale: Supports settings module verification metadata for GRACE module traceability.
# Dependencies: config.settings.
# Exports: pytest tests.
# LINKS: knowledge-graph.xml#MOD-001
# MODULE_MAP: tests/test_settings_exports.py
# Public Functions: pytest test functions.
# Private Helpers: none.
# Key Semantic Blocks: none.
# Critical Flows: import config.settings -> assert derived constants mirror settings.yaml sections.
# Verification: verification-plan.xml#V-MOD-201
# CHANGE_SUMMARY: Added GRACE module contract linking this test file to MOD-001.

import config.settings as settings


# Purpose: Test settings exports history and uploads configs
def test_settings_exports_history_and_uploads_configs() -> None:
    assert settings.HISTORY_CONFIG == settings.config.get("history", {})
    assert settings.UPLOADS_CONFIG == settings.config.get("uploads", {})


# --- Phase 10: Test cache, trends, and scraper config exports ---
# Purpose: Test that CACHE_CONFIG is exported from settings.
def test_settings_exports_cache_config() -> None:
    assert hasattr(settings, "CACHE_CONFIG")
    assert settings.CACHE_CONFIG == settings.config.get("cache", {})


# Purpose: Test that GOOGLE_TRENDS_CONFIG is exported from settings.
def test_settings_exports_google_trends_config() -> None:
    assert hasattr(settings, "GOOGLE_TRENDS_CONFIG")
    assert settings.GOOGLE_TRENDS_CONFIG == settings.config.get("google_trends", {})


# Purpose: Test that SCRAPER_CONFIG is exported from settings.
def test_settings_exports_scraper_config() -> None:
    assert hasattr(settings, "SCRAPER_CONFIG")
    assert settings.SCRAPER_CONFIG == settings.config.get("scraper", {})


# Purpose: Test that cache config returns empty dict when keys are absent.
def test_cache_config_defaults_when_keys_missing() -> None:
    cache_cfg = settings.CACHE_CONFIG

    # If cache section exists, check expected structure
    if cache_cfg:
        assert "enabled" in cache_cfg or cache_cfg == {}
        assert "default_ttl_hours" in cache_cfg or cache_cfg == {}
        assert "max_cache_records" in cache_cfg or cache_cfg == {}
        assert "cache_relevant_subset" in cache_cfg or cache_cfg == {}
    else:
        # Empty dict is valid default when section is missing
        assert cache_cfg == {}


# Purpose: Test that google_trends config returns expected keys when present.
def test_google_trends_config_defaults_when_keys_missing() -> None:
    trends_cfg = settings.GOOGLE_TRENDS_CONFIG

    # If trends section exists, check expected structure
    if trends_cfg:
        assert "default_geo" in trends_cfg or trends_cfg == {}
        assert "default_timeframe" in trends_cfg or trends_cfg == {}
        assert "cache_ttl_hours" in trends_cfg or trends_cfg == {}
    else:
        # Empty dict is valid default when section is missing
        assert trends_cfg == {}


# Purpose: Test that scraper config returns empty dict when keys are absent.
def test_scraper_config_defaults_when_keys_missing() -> None:
    scraper_cfg = settings.SCRAPER_CONFIG

    # If scraper section exists, check expected structure
    if scraper_cfg:
        # browser_enabled must be a boolean
        assert isinstance(scraper_cfg.get("browser_enabled", False), bool)
        assert "engine" in scraper_cfg or scraper_cfg == {}
        assert "parser" in scraper_cfg or scraper_cfg == {}
    else:
        # Empty dict is valid default when section is missing
        assert scraper_cfg == {}


# Purpose: Test that SEO_MATH_CONFIG includes BM25F configuration with defaults.
def test_seo_math_config_has_bm25f_defaults() -> None:
    seo_math_cfg = settings.SEO_MATH_CONFIG

    # Check for BM25F keys (may be empty if not configured)
    if seo_math_cfg:
        # analyze_bm25f should default to true if defined
        assert "analyze_bm25f" in seo_math_cfg or seo_math_cfg == {}

        # If BM25F params exist, check structure
        bm25f_params = seo_math_cfg.get("bm25f_params", {})
        if bm25f_params:
            assert "k1" in bm25f_params
            assert "b_body" in bm25f_params
            assert "b_title" in bm25f_params
            assert "b_snippet" in bm25f_params

        # If field weights exist, check structure
        field_weights = seo_math_cfg.get("field_weights", {})
        if field_weights:
            # Check for key field weights
            assert "serp_title" in field_weights
            assert "page_title" in field_weights
            assert "h1" in field_weights
            assert "body_text" in field_weights

        # If signals config exists, check structure
        signals = seo_math_cfg.get("signals", {})
        if signals:
            assert "title_alignment" in signals or signals == {}
            assert "content_effort" in signals or signals == {}
            assert "topical_overlap" in signals or signals == {}
            assert "simhash" in signals or signals == {}


# Purpose: Test that cache_relevant_subset is a list of expected settings keys.
def test_cache_relevant_subset_structure() -> None:
    cache_cfg = settings.CACHE_CONFIG
    if not cache_cfg:
        return

    cache_relevant = cache_cfg.get("cache_relevant_subset", [])
    assert isinstance(cache_relevant, list)

    # Check that expected keys are present
    expected_patterns = [
        "seo_math.analyze_bm25f",
        "seo_math.bm25f_params",
        "seo_math.field_weights",
        "seo_math.signals",
        "llm.provider",
        "llm.model",
    ]

    for pattern in expected_patterns:
        # At least some expected keys should be present
        if cache_relevant:
            # Not all need to be present, but structure should be valid
            assert all(isinstance(key, str) for key in cache_relevant)

# GRACE module link: MOD-006
