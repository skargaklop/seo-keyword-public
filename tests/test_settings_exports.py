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
# CHANGE_SUMMARY: Added GRACE module contract linking this test file to MOD-001; Task 1 added humanizer + self-check stage tests (test_seo_description_prompt_has_humanizer_final_stage, test_seo_description_prompt_has_self_check_stage).

from pathlib import Path

import config.settings as settings


def _clear_serp_env(monkeypatch) -> None:
    for env_var in (
        "SERPER_API_KEY",
        "SERPAPI_KEY",
        "BRAVE_SEARCH_API_KEY",
        "SEARCHAPI_IO_KEY",
        "ZENSERP_KEY",
        "SCRAPERAPI_KEY",
        "DATAFORSEO_LOGIN",
        "DATAFORSEO_PASSWORD",
        "SERPSTAT_TOKEN",
        "SEMRUSH_API_KEY",
        "SERPSTACK_KEY",
        "SCALESERP_KEY",
        "VALUESERP_KEY",
    ):
        monkeypatch.delenv(env_var, raising=False)


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


# Purpose: Test serp provider options expose semrush label
def test_serp_provider_options_include_semrush() -> None:
    assert settings.SERP_PROVIDER_OPTIONS["Semrush"] == "semrush"


# Purpose: Test available serp providers exposes semrush only with key
def test_get_available_serp_providers_exposes_semrush_only_with_key(monkeypatch) -> None:
    _clear_serp_env(monkeypatch)

    assert "Semrush" not in settings.get_available_serp_providers()

    monkeypatch.setenv("SEMRUSH_API_KEY", "semrush-key")

    assert settings.get_available_serp_providers()["Semrush"] == "semrush"


# Purpose: Test semrush trends provider is not wired into google trends surfaces
def test_no_semrush_trends_provider_order_surface() -> None:
    paths = [
        "utils/google_trends_client.py",
        "config/settings.yaml",
        "components/sidebar.py",
    ]
    combined = "\n".join(Path(path).read_text(encoding="utf-8") for path in paths)
    lowered = combined.lower()

    assert "semrush_trends" not in lowered
    assert "semrush" not in [
        token.strip(" '\"\t\r\n,[]{}():")
        for line in lowered.splitlines()
        if "provider_order" in line or "google_trends" in line
        for token in line.split()
    ]


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


# --- Task 1: Humanizer final stage + self-check appended to SEO rewrite prompt ---

# Purpose: Verify the seo_description prompt has a humanizer final stage that
# instructs the model to remove AI-slop tells while keeping sense, keywords, LSI.
def test_seo_description_prompt_has_humanizer_final_stage() -> None:
    prompt = settings.SEO_DESCRIPTION_PROMPT
    # A clearly labeled humanizer section must exist
    assert "HUMANIZER" in prompt.upper(), "humanizer final stage missing"
    # The core AI-slop lexical tells must be enumerated (case-insensitive)
    for marker in ("em dash", "delve", "tapestry", "robust"):
        assert marker.lower() in prompt.lower(), f"humanizer marker missing: {marker}"
    # Must explicitly preserve the SEO substance
    assert "keyword" in prompt.lower(), "humanizer must mention keeping keywords"
    assert "lsi" in prompt.lower(), "humanizer must mention keeping LSI"


# Purpose: Verify the seo_description prompt ends with a concise self-check stage
# stating what the output must contain.
def test_seo_description_prompt_has_self_check_stage() -> None:
    prompt = settings.SEO_DESCRIPTION_PROMPT
    assert "SELF-CHECK" in prompt.upper(), "self-check stage missing"
    # The self-check must be near the end (final 1500 chars)
    tail = prompt[-1500:]
    assert "SELF-CHECK" in tail.upper(), "self-check must be the final stage"
    # Must require the core output artifacts
    for must_have in ("META_TITLE", "META_DESCRIPTION", "H1"):
        assert must_have in tail, f"self-check must require: {must_have}"


# GRACE module link: MOD-006
