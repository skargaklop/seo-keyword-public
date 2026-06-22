# MODULE_CONTRACT: components/sidebar
# Purpose: Streamlit sidebar configuration UI for workflow settings, crawl limits, API options, Google Ads selections, prompts, logging, and storage limits; dynamic model selector with cache-backed dropdown; custom provider management
# Rationale: Keep the configuration surface explicit for GRACE adoption and review
# Dependencies: os, streamlit, config.settings, config.i18n, utils.model_fetcher
# Exports: render_sidebar
# LINKS: requirements.xml#UC-001, requirements.xml#UC-003
# MODULE_MAP: components/sidebar.py
# Public Functions: render_sidebar
# Private Helpers: _normalize_log_level_name, _safe_log_level_index, _normalize_language_value, _resolve_google_ads_selection, _build_sidebar_config_updates, _load_saved_ui
# Key Semantic Blocks: block_sidebar_language_select, block_sidebar_provider_settings, block_sidebar_google_ads_settings, block_sidebar_prompt_settings, block_sidebar_logging_settings, block_sidebar_crawl_settings
# Critical Flows: load config -> render sidebar -> validate selections -> save config
# Verification: python -m py_compile, python -m ruff check ., python -m pytest -q
# CHANGE_SUMMARY: Added dynamic model selector with cache; added Mistral to provider_keys; added custom provider UI with validation; removed hardcoded default_presets; added SERP provider config block before Google Ads; added model search filter; SERP settings persist to settings.yaml; Phase 8 Plan 03: added top-level crawler settings controls and persistence

import html
import os
from typing import Any, Dict

import streamlit as st
import utils.browser_scraper_trends  # noqa: F401 — registers browser_scraper_trends provider at module load
from config.i18n import t
from config.settings import (
    CACHE_CONFIG,
    CLEANUP_CONFIG,
    CRAWLER_CONFIG,
    GOOGLE_TRENDS_CONFIG,
    HISTORY_CONFIG,
    KEYWORD_EXTRACTION_PROMPT,
    LLM_DELAY_BETWEEN_REQUESTS,
    LLM_TIMEOUT,
    RETRY_ATTEMPTS,
    RETRY_DELAY,
    SCRAPER_CONFIG,
    SEO_DESCRIPTION_PROMPT,
    SEO_MATH_CONFIG,
    SERP_DEVICE_OPTIONS,
    SERP_GOOGLE_DOMAIN_OPTIONS,
    SERP_LANGUAGE_OPTIONS,
    SERP_LOCATION_OPTIONS,
    SERP_PROVIDER_OPTIONS,
    SERP_SAFE_SEARCH_OPTIONS,
    SERP_SEARCH_TYPE_OPTIONS,
    SERP_TIME_PERIOD_OPTIONS,
    UPLOADS_CONFIG,
    get_available_serp_providers,
    load_config,
    save_config,
)
from utils.browser_scraper import (
    BrowserScraper,
    DependencyStatus,
    build_optional_dependency_install_command,
    get_problem_dependencies,
)
from utils.model_fetcher import (
    fetch_all_models,
    get_cached_models,
    save_models_cache,
    validate_custom_provider,
)

LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
GOOGLE_ADS_CURRENCIES = ["UAH", "USD", "EUR"]
UI_LANGUAGE_OPTIONS: Dict[str, str] = {
    "🇷🇺 Русский": "ru",
    "🇺🇦 Українська": "uk",
    "🇬🇧 English": "en",
}
# Source: Google Ads geo targets CSV dated 2026-02-25.
GOOGLE_ADS_LOCATIONS: Dict[str, str] = {
    "Ukraine": "2804",
    "Russia": "2643",
    "United States": "2840",
    "United Kingdom": "2826",
    "Austria": "2040",
    "Belgium": "2056",
    "Bulgaria": "2100",
    "Croatia": "2191",
    "Cyprus": "2196",
    "Czech Republic": "2203",
    "Denmark": "2208",
    "Estonia": "2233",
    "Finland": "2246",
    "France": "2250",
    "Georgia": "2268",
    "Germany": "2276",
    "Greece": "2300",
    "Hungary": "2348",
    "Ireland": "2372",
    "Italy": "2380",
    "Kazakhstan": "2398",
    "Kyrgyzstan": "2417",
    "Latvia": "2428",
    "Lithuania": "2440",
    "Luxembourg": "2442",
    "Malta": "2470",
    "Moldova": "2498",
    "Netherlands": "2528",
    "Poland": "2616",
    "Portugal": "2620",
    "Romania": "2642",
    "Slovakia": "2703",
    "Slovenia": "2705",
    "Spain": "2724",
    "Sweden": "2752",
    "Tajikistan": "2762",
    "Uzbekistan": "2860",
    "Azerbaijan": "2031",
    "Armenia": "2051",
    "Belarus": "2112",
}
GOOGLE_ADS_LANGUAGES: Dict[str, Any] = {
    "Russian & Ukrainian": ["1031", "1036"],
    "Russian": "1031",
    "Ukrainian": "1036",
    "English": "1000",
    "German": "1001",
    "French": "1002",
    "Spanish": "1003",
    "Italian": "1004",
    "Portuguese": "1014",
    "Polish": "1015",
}


def _render_section_header(title: str, description: str, divider: str) -> None:
    st.subheader(title, divider=divider)
    if description:
        st.caption(description)
# FUNCTION_CONTRACT: _normalize_log_level_name
# Purpose: Implement the  normalize log level name helper for this module.
# Input: level_name (str), default (str)
# Output: str
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def _normalize_log_level_name(level_name: str, default: str) -> str:
    aliases = {"WARN": "WARNING", "FATAL": "CRITICAL"}
    normalized_default = str(default).strip().upper()
    normalized = aliases.get(
        str(level_name).strip().upper(), str(level_name).strip().upper()
    )
    return normalized if normalized in LOG_LEVELS else normalized_default
# FUNCTION_CONTRACT: _safe_log_level_index
# Purpose: Implement the  safe log level index helper for this module.
# Input: level_name (str), default (str)
# Output: int
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def _safe_log_level_index(level_name: str, default: str) -> int:
    return LOG_LEVELS.index(_normalize_log_level_name(level_name, default))
# FUNCTION_CONTRACT: _normalize_language_value
# Purpose: Implement the  normalize language value helper for this module.
# Input: language_value (Any)
# Output: tuple[str, ...]
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def _normalize_language_value(language_value: Any) -> tuple[str, ...]:
    if isinstance(language_value, list):
        return tuple(str(item) for item in language_value)
    return (str(language_value),)
# FUNCTION_CONTRACT: _resolve_google_ads_selection
# Purpose: Implement the  resolve google ads selection helper for this module.
# Input: google_ads_config (Dict[str, Any]), locations (Dict[str, str]), languages (Dict[str, Any])
# Output: tuple[str, str]
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def _resolve_google_ads_selection(
    google_ads_config: Dict[str, Any],
    locations: Dict[str, str],
    languages: Dict[str, Any],
) -> tuple[str, str]:
    default_location = next(iter(locations))
    default_language = next(iter(languages))

    saved_location_id = str(google_ads_config.get("location_id", ""))
    saved_language_id = _normalize_language_value(
        google_ads_config.get("language_id", languages[default_language])
    )

    location_name = next(
        (name for name, value in locations.items() if str(value) == saved_location_id),
        default_location,
    )
    language_name = next(
        (
            name
            for name, value in languages.items()
            if _normalize_language_value(value) == saved_language_id
        ),
        default_language,
    )
    return location_name, language_name
# FUNCTION_CONTRACT: _build_sidebar_config_updates
# Purpose: Implement the  build sidebar config updates helper for this module.
# Input: current_config (Dict[str, Any]), values (Dict[str, Any])
# Output: Dict[str, Any]
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def _build_sidebar_config_updates(
    current_config: Dict[str, Any], values: Dict[str, Any]
) -> Dict[str, Any]:
    llm_config = current_config.setdefault("llm", {})
    llm_prompts = llm_config.setdefault("prompts", {})
    llm_prompts["keyword_extraction"] = values["keyword_prompt"]
    llm_prompts["seo_description"] = values["seo_prompt"]
    llm_config["timeout_seconds"] = values["api_timeout"]
    llm_config["delay_between_requests_seconds"] = values["api_delay"]
    llm_config["keyword_llm_generation_language"] = values.get(
        "keyword_llm_generation_language", "Russian"
    )
    llm_config["page_type"] = values.get("page_type", "product")

    retry_config = current_config.setdefault("retry", {})
    retry_config["max_attempts"] = values["api_retry_count"]
    retry_config["delay_seconds"] = values["api_retry_delay"]

    cleanup_config = current_config.setdefault("cleanup", {})
    cleanup_config["max_age_days"] = values["cleanup_max_age"]

    logging_config = current_config.setdefault("logging", {})
    logging_config["app_level"] = _normalize_log_level_name(
        values["app_log_level"], "INFO"
    )
    logging_config["console_enabled"] = values["console_logging_enabled"]
    logging_config["console_level"] = _normalize_log_level_name(
        values["console_log_level"], "INFO"
    )
    logging_config["api_enabled"] = values["api_logging_enabled"]
    logging_config["api_level"] = _normalize_log_level_name(
        values["api_log_level"], "DEBUG"
    )
    logging_config["api_retention_days"] = values["api_retention_days"]
    logging_config["error_level"] = _normalize_log_level_name(
        values["error_log_level"], "ERROR"
    )
    logging_config["log_test_runs"] = values["log_test_runs"]

    history_config = current_config.setdefault("history", {})
    history_config["retention_days"] = values["history_retention_days"]

    uploads_config = current_config.setdefault("uploads", {})
    uploads_config["max_file_size_mb"] = values["upload_max_file_size_mb"]
    uploads_config["max_rows"] = values["upload_max_rows"]

    google_ads_config = current_config.setdefault("google_ads", {})
    google_ads_config["location_id"] = values["location_id"]
    google_ads_config["language_id"] = values["language_id"]
    google_ads_config["currency_code"] = values["currency_code"]

    serp_config = current_config.setdefault("serp", {})
    serp_config["provider"] = values.get("serp_provider", "serper_dev")
    serp_config["num_results"] = values.get("serp_num_results", 10)
    serp_config["gl"] = values.get("serp_gl", "ua")
    serp_config["hl"] = values.get("serp_hl", "uk")
    serp_config["device"] = values.get("serp_device", "desktop")
    serp_config["search_type"] = values.get("serp_search_type", "web")
    serp_config["time_period"] = values.get("serp_time_period", "any")
    serp_config["safe_search"] = values.get("serp_safe_search", "off")
    serp_config["google_domain"] = values.get("serp_google_domain", "google.com")
    serp_config["location"] = values.get("serp_city", "")
    serp_config["uule"] = values.get("serp_uule", "")
    serp_config["headless"] = bool(
        values.get(
            "serp_headless",
            serp_config.get("headless", False),
        )
    )

    ui_prefs = current_config.setdefault("ui", {})
    ui_prefs["language"] = values["ui_lang"]
    ui_prefs["provider"] = values["provider"]
    ui_prefs["model"] = values["model_name"]
    ui_prefs["max_keywords"] = values["max_keywords"]

    seo_math_config = current_config.setdefault("seo_math", {})

    # FUNCTION_CONTRACT: _setting_value - get setting with fallback chain
    def _setting_value(
        value_key: str,
        config_key: str,
        defaults: Dict[str, Any],
        fallback: Any,
    ) -> Any:
        return values.get(
            value_key,
            seo_math_config.get(config_key, defaults.get(config_key, fallback)),
        )

    seo_math_config["enabled"] = _setting_value(
        "seo_math_enabled", "enabled", SEO_MATH_CONFIG, False
    )
    seo_math_config["analyze_ngrams"] = _setting_value(
        "seo_math_analyze_ngrams", "analyze_ngrams", SEO_MATH_CONFIG, True
    )
    seo_math_config["analyze_bm25f"] = _setting_value(
        "seo_math_analyze_bm25f", "analyze_bm25f", SEO_MATH_CONFIG, True
    )
    seo_math_config["analyze_tfidf"] = _setting_value(
        "seo_math_analyze_tfidf", "analyze_tfidf", SEO_MATH_CONFIG, True
    )
    seo_math_config["analyze_cooccurrence"] = _setting_value(
        "seo_math_analyze_cooccurrence",
        "analyze_cooccurrence",
        SEO_MATH_CONFIG,
        True,
    )
    seo_math_config["analyze_intent"] = _setting_value(
        "seo_math_analyze_intent", "analyze_intent", SEO_MATH_CONFIG, True
    )
    seo_math_config["analyze_generation_quality"] = _setting_value(
        "seo_math_analyze_generation_quality",
        "analyze_generation_quality",
        SEO_MATH_CONFIG,
        True,
    )
    seo_math_config["analyze_generated_text"] = _setting_value(
        "seo_math_analyze_generated_text",
        "analyze_generated_text",
        SEO_MATH_CONFIG,
        False,
    )
    seo_math_config["ngram_min"] = _setting_value(
        "seo_math_ngram_min", "ngram_min", SEO_MATH_CONFIG, 1
    )
    seo_math_config["ngram_max"] = _setting_value(
        "seo_math_ngram_max", "ngram_max", SEO_MATH_CONFIG, 3
    )
    seo_math_config["top_terms_limit"] = _setting_value(
        "seo_math_top_terms", "top_terms_limit", SEO_MATH_CONFIG, 30
    )
    seo_math_config["min_ngram_count"] = _setting_value(
        "seo_math_min_count", "min_ngram_count", SEO_MATH_CONFIG, 2
    )
    seo_math_config["min_document_frequency"] = _setting_value(
        "seo_math_min_df", "min_document_frequency", SEO_MATH_CONFIG, 2
    )
    seo_math_config["use_related_searches"] = _setting_value(
        "seo_math_use_related", "use_related_searches", SEO_MATH_CONFIG, True
    )
    seo_math_config["use_people_also_ask"] = _setting_value(
        "seo_math_use_paa", "use_people_also_ask", SEO_MATH_CONFIG, True
    )
    seo_math_config["strip_suffixes"] = _setting_value(
        "seo_math_strip_suffixes", "strip_suffixes", SEO_MATH_CONFIG, False
    )
    bm25f_params = seo_math_config.setdefault("bm25f_params", {})
    default_bm25f = SEO_MATH_CONFIG.get("bm25f_params", {})
    for key in ("k1", "b_body", "b_title", "b_snippet"):
        bm25f_params[key] = values.get(
            f"seo_math_bm25f_{key}",
            bm25f_params.get(key, default_bm25f.get(key)),
        )
    field_weights = seo_math_config.setdefault("field_weights", {})
    default_weights = SEO_MATH_CONFIG.get("field_weights", {})
    for key in (
        "serp_title",
        "page_title",
        "h1",
        "meta_description",
        "serp_snippet",
        "related_searches",
        "people_also_ask",
        "trends_related",
        "body_text",
        "anchor_text",
    ):
        field_weights[key] = values.get(
            f"seo_math_weight_{key}",
            field_weights.get(key, default_weights.get(key)),
        )
    signals = seo_math_config.setdefault("signals", {})
    default_signals = SEO_MATH_CONFIG.get("signals", {})
    for key in ("title_alignment", "content_effort", "topical_overlap", "simhash"):
        signals[key] = values.get(
            f"seo_math_signal_{key}",
            signals.get(key, default_signals.get(key, True)),
        )

    cache_config = current_config.setdefault("cache", {})
    cache_config["enabled"] = values.get(
        "cache_enabled", cache_config.get("enabled", CACHE_CONFIG.get("enabled", True))
    )
    cache_config["default_ttl_hours"] = values.get(
        "cache_default_ttl_hours",
        cache_config.get(
            "default_ttl_hours",
            CACHE_CONFIG.get("default_ttl_hours", 168),
        ),
    )
    cache_config["max_cache_records"] = values.get(
        "cache_max_records",
        cache_config.get(
            "max_cache_records",
            CACHE_CONFIG.get("max_cache_records", 10000),
        ),
    )

    trends_config = current_config.setdefault("google_trends", {})
    trends_config.pop("enabled", None)
    trends_config["default_geo"] = values.get(
        "google_trends_default_geo",
        trends_config.get("default_geo", GOOGLE_TRENDS_CONFIG.get("default_geo", "UA")),
    )
    trends_config["default_timeframe"] = values.get(
        "google_trends_default_timeframe",
        trends_config.get(
            "default_timeframe",
            GOOGLE_TRENDS_CONFIG.get("default_timeframe", "today 12-m"),
        ),
    )
    trends_config["cache_ttl_hours"] = values.get(
        "google_trends_cache_ttl_hours",
        trends_config.get(
            "cache_ttl_hours",
            GOOGLE_TRENDS_CONFIG.get("cache_ttl_hours", 24),
        ),
    )
    trends_config["max_keywords_per_request"] = int(values.get(
        "google_trends_max_keywords_per_request",
        trends_config.get(
            "max_keywords_per_request",
            GOOGLE_TRENDS_CONFIG.get("max_keywords_per_request", 10),
        ),
    ))
    trends_config["show_confidence_metadata"] = bool(
        values.get("google_trends_show_confidence", trends_config.get("show_confidence_metadata", True))
    )
    trends_config["headless"] = bool(
        values.get(
            "google_trends_headless",
            trends_config.get(
                "headless",
                GOOGLE_TRENDS_CONFIG.get("headless", False),
            ),
        )
    )
    trends_config["manual_start_wait"] = int(values.get(
        "trends_manual_warmup",
        trends_config.get(
            "manual_start_wait",
            GOOGLE_TRENDS_CONFIG.get("manual_start_wait", 0),
        ),
    ))
    trends_config["min_delay"] = int(values.get(
        "trends_min_delay",
        trends_config.get("min_delay", GOOGLE_TRENDS_CONFIG.get("min_delay", 60)),
    ))
    trends_config["max_delay"] = int(values.get(
        "trends_max_delay",
        trends_config.get("max_delay", GOOGLE_TRENDS_CONFIG.get("max_delay", 60)),
    ))
    trends_config["state_file"] = str(values.get(
        "trends_state_file",
        trends_config.get("state_file", "trends_state.json"),
    ))

    scraper_config = current_config.setdefault("scraper", {})
    scraper_config["browser_enabled"] = values.get(
        "scraper_browser_enabled",
        scraper_config.get(
            "browser_enabled",
            SCRAPER_CONFIG.get("browser_enabled", False),
        ),
    )

    crawler_config = current_config.setdefault("crawler", {})
    crawler_config["enabled"] = values.get(
        "crawler_enabled", crawler_config.get("enabled", CRAWLER_CONFIG.get("enabled", False))
    )
    crawler_config["max_pages"] = values.get(
        "crawler_max_pages",
        crawler_config.get("max_pages", CRAWLER_CONFIG.get("max_pages", 50)),
    )
    crawler_config["max_depth"] = values.get(
        "crawler_max_depth",
        crawler_config.get("max_depth", CRAWLER_CONFIG.get("max_depth", 3)),
    )
    crawler_config["same_domain_only"] = values.get(
        "crawler_same_domain_only",
        crawler_config.get(
            "same_domain_only",
            CRAWLER_CONFIG.get("same_domain_only", True),
        ),
    )
    crawler_config["timeout_seconds"] = values.get(
        "crawler_timeout_seconds",
        crawler_config.get(
            "timeout_seconds",
            CRAWLER_CONFIG.get("timeout_seconds", 120),
        ),
    )
    crawler_config["max_response_bytes"] = values.get(
        "crawler_max_response_bytes",
        crawler_config.get(
            "max_response_bytes",
            CRAWLER_CONFIG.get("max_response_bytes", 10_485_760),
        ),
    )
    crawler_config["max_retries"] = values.get(
        "crawler_max_retries",
        crawler_config.get("max_retries", CRAWLER_CONFIG.get("max_retries", 1)),
    )

    return current_config


# FUNCTION_CONTRACT: _build_serp_sidebar_values
# Purpose: Build the SERP settings fragment shared by sidebar persistence and sidebar return values.
# Input: current_serp_config (Dict[str, Any]), serp_selected_provider (str | None), serp_num (int), serp_gl (str), serp_hl (str), serp_device (str), serp_search_type (str), serp_time_period (str), serp_safe_search (str), serp_google_domain (str), serp_city (str), serp_uule (str)
# Output: Dict[str, Any]
# Side Effects: None
# Business Rules: Preserves the provider fallback and the current UI-selected or default SERP values exactly once for both code paths.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def _build_serp_sidebar_values(
    current_serp_config: Dict[str, Any],
    serp_selected_provider: str | None,
    serp_num: int,
    serp_gl: str,
    serp_hl: str,
    serp_device: str,
    serp_search_type: str,
    serp_time_period: str,
    serp_safe_search: str,
    serp_google_domain: str,
    serp_city: str,
    serp_uule: str,
    serp_headless: bool,
) -> Dict[str, Any]:
    return {
        "serp_provider": SERP_PROVIDER_OPTIONS.get(serp_selected_provider, "serper_dev")
        if serp_selected_provider
        else current_serp_config.get("provider", "serper_dev"),
        "serp_num_results": serp_num,
        "serp_gl": serp_gl,
        "serp_hl": serp_hl,
        "serp_device": serp_device,
        "serp_search_type": serp_search_type,
        "serp_time_period": serp_time_period,
        "serp_safe_search": serp_safe_search,
        "serp_google_domain": serp_google_domain,
        "serp_city": serp_city,
        "serp_uule": serp_uule,
        "serp_headless": serp_headless,
    }

# FUNCTION_CONTRACT: _load_saved_ui
# Purpose: Implement the  load saved ui helper for this module.
# Input: (none)
# Output: Dict[str, Any]
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def _load_saved_ui() -> Dict[str, Any]:
    try:
        cfg = load_config()
        return cfg.get("ui", {})
    except Exception:
        return {}
# FUNCTION_CONTRACT: _section_config_value - get config value with fallback
def _section_config_value(
    section_config: Dict[str, Any],
    defaults: Dict[str, Any],
    config_key: str,
    fallback: Any,
) -> Any:
    return section_config.get(config_key, defaults.get(config_key, fallback))
# FUNCTION_CONTRACT: _sync_sidebar_widget_from_config - sync widget state with config
def _sync_sidebar_widget_from_config(widget_key: str, config_value: Any) -> None:
    # Refresh when settings.yaml changes, but preserve unsaved UI edits on normal reruns.
    marker_key = f"_{widget_key}_config_value"
    if (
        widget_key not in st.session_state
        or st.session_state.get(marker_key) != config_value
    ):
        st.session_state[widget_key] = config_value
        st.session_state[marker_key] = config_value


# FUNCTION_CONTRACT: render_sidebar
# Purpose: Implement the render sidebar helper for this module.
# Input: (none)
# Output: Dict[str, Any]
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def render_sidebar() -> Dict[str, Any]:
    with st.sidebar:
        current_config = load_config()
        custom_providers = current_config.get("llm", {}).get("custom_providers", [])
        current_llm_config = current_config.get("llm", {})
        current_retry_config = current_config.get("retry", {})
        current_logging_config = current_config.get("logging", {})
        current_history_config = current_config.get("history", {})
        current_google_ads_config = current_config.get("google_ads", {})
        current_uploads_config = current_config.get("uploads", {})
        current_serp_config = current_config.get("serp", {})
        current_prompts = current_llm_config.get("prompts", {})

        st.markdown(
            f"""
<div class="sidebar-brand">
  <div class="sidebar-brand-mark">SEO</div>
  <div class="sidebar-brand-copy">
    <div class="sidebar-brand-title">{html.escape(t("app_console_title"))}</div>
    <div class="sidebar-brand-desc">{html.escape(t("sidebar_settings_desc"))}</div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
        st.divider()

        # --- Language Selector ---
        lang_options = UI_LANGUAGE_OPTIONS
        lang_labels = list(lang_options.keys())
        # Load saved UI preferences on first run
        if "_ui_prefs_loaded" not in st.session_state:
            saved_ui = _load_saved_ui()
            if "ui_lang" not in st.session_state:
                st.session_state["ui_lang"] = saved_ui.get("language", "ru")
            st.session_state["_saved_provider"] = saved_ui.get("provider", "")
            st.session_state["_saved_model"] = saved_ui.get("model", "")
            st.session_state["_saved_max_keywords"] = saved_ui.get("max_keywords", 50)
            st.session_state["_ui_prefs_loaded"] = True
        current_lang = st.session_state["ui_lang"]
        current_index = (
            list(lang_options.values()).index(current_lang)
            if current_lang in lang_options.values()
            else 0
        )

        # Purpose:  on lang change implementation
        def _on_lang_change() -> None:
            _label = st.session_state.get("ui_lang_selector")
            if _label and _label in lang_options:
                st.session_state["ui_lang"] = lang_options[_label]

        st.selectbox(
            t("ui_language"), lang_labels, index=current_index,
            key="ui_lang_selector", on_change=_on_lang_change,
        )

        _render_section_header(t("settings_header"), t("sidebar_settings_desc"), "blue")

        # --- LLM Provider ---
        _render_section_header(t("llm_provider"), t("sidebar_provider_desc"), "green")

        provider_keys: Dict[str, str] = {
            "OpenAI": "OPENAI_API_KEY",
            "Anthropic": "ANTHROPIC_API_KEY",
            "Google": "GEMINI_API_KEY",
            "xAI": "XAI_API_KEY",
            "Groq": "GROQ_API_KEY",
            "DeepSeek": "DEEPSEEK_API_KEY",
            "MiniMax": "MINIMAX_API_KEY",
            "Moonshot": "MOONSHOT_API_KEY",
            "OpenRouter": "OPENROUTER_API_KEY",
            "Cerebras": "CEREBRAS_API_KEY",
            "Mistral": "MISTRAL_API_KEY",
            "ZAI": "ZAI_API_KEY",
        }

        available_providers: list[str] = [
            name for name, key in provider_keys.items() if os.getenv(key)
        ]

        # Custom provider availability — append those with API key set
        for cp in custom_providers:
            if os.getenv(cp.get("api_key_env", "")):
                available_providers.append(cp.get("display_name", cp["name"]))

        if not available_providers:
            st.warning(t("no_api_keys_sidebar"))
            available_providers = ["OpenAI"]

        # Use saved provider as default if available
        saved_provider = st.session_state.get("_saved_provider", "")
        default_index: int = 0
        if saved_provider and saved_provider in available_providers:
            default_index = available_providers.index(saved_provider)
        elif "Google" in available_providers:
            default_index = available_providers.index("Google")

        provider: str = st.selectbox(
            t("select_provider"), available_providers, index=default_index
        )

        # Dynamic model selector — uses cached models when available
        cached_models = get_cached_models(provider.lower())
        saved_model = st.session_state.get("_saved_model", "")

        if cached_models:
            model_search = st.text_input(t("model_search_placeholder"), key="model_search_filter")
            if len(model_search) >= 2:
                filtered_models = [m for m in cached_models if model_search.lower() in m.lower()]
            else:
                filtered_models = cached_models
            model_options = filtered_models + [t("model_manual_entry")]
            # Determine pre-selection index
            default_model_index = 0
            if saved_model and saved_provider == provider:
                if saved_model in model_options:
                    default_model_index = model_options.index(saved_model)
            selected_model = st.selectbox(
                t("model_select_label"),
                model_options,
                index=default_model_index,
            )
            if selected_model == t("model_manual_entry"):
                model_name = st.text_input(t("model_name"), value=saved_model)
            else:
                model_name = selected_model
        else:
            # Fallback to text_input when no cache
            fallback_value = ""
            if saved_model and saved_provider == provider:
                fallback_value = saved_model
            model_name = st.text_input(t("model_name"), value=fallback_value)
            st.caption(t("model_no_models_cached"))

        # Refresh models button
        if st.button(t("model_refresh_button")):
            with st.spinner(t("model_refreshing")):
                cache = fetch_all_models(provider_keys, custom_providers)
                save_models_cache(cache)
                st.session_state._models_refresh_result = {
                    "success": True,
                    "count": sum(
                        1
                        for v in cache.get("providers", {}).values()
                        if v.get("status") == "success"
                    ),
                }
                st.rerun()

        # Display refresh result after rerun
        if "_models_refresh_result" in st.session_state:
            result = st.session_state._models_refresh_result
            if result.get("success"):
                st.success(t("model_refresh_complete").format(count=result["count"]))
            del st.session_state._models_refresh_result

        saved_max_kw: int = st.session_state.get("_saved_max_keywords", 50)
        max_keywords: int = st.slider(t("max_keywords_per_url"), 5, 100, saved_max_kw)

        # --- Custom Provider Section ---
        with st.expander(t("custom_provider_header")):
            # Show existing custom providers with Remove buttons
            for i, cp in enumerate(custom_providers):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.text(f"{cp.get('display_name', cp['name'])} ({cp['base_url']})")
                with col2:
                    if st.button(t("custom_provider_remove"), key=f"remove_cp_{i}"):
                        cfg = load_config()
                        custom_list = cfg.setdefault("llm", {}).setdefault(
                            "custom_providers", []
                        )
                        cp_name_to_remove = cp.get("name", "").lower()
                        custom_list[:] = [
                            c for c in custom_list
                            if c.get("name", "").lower() != cp_name_to_remove
                        ]
                        save_config(cfg)
                        st.rerun()

            st.divider()

            # Add new custom provider
            cp_name = st.text_input(t("custom_provider_name"), key="new_cp_name")
            cp_base_url = st.text_input(
                t("custom_provider_base_url"), key="new_cp_base_url"
            )
            cp_api_key_env = st.text_input(
                t("custom_provider_api_key_env"), key="new_cp_api_key_env"
            )

            if st.button(t("custom_provider_add_button")):
                valid, error = validate_custom_provider(
                    cp_name, cp_base_url, cp_api_key_env
                )
                if not valid:
                    st.error(t("custom_provider_validation_error").format(error=error))
                else:
                    cfg = load_config()
                    custom_list = cfg.setdefault("llm", {}).setdefault(
                        "custom_providers", []
                    )
                    existing_names = [
                        cp.get("name", "").lower() for cp in custom_list
                    ]
                    if cp_name.lower() in existing_names:
                        st.error(
                            t("custom_provider_duplicate_name").format(name=cp_name)
                        )
                    else:
                        custom_list.append(
                            {
                                "name": cp_name.lower(),
                                "display_name": cp_name,
                                "base_url": cp_base_url.rstrip("/"),
                                "api_key_env": cp_api_key_env,
                            }
                        )
                        save_config(cfg)
                        st.rerun()

        st.divider()

        # --- SERP Provider ---
        _render_section_header(t("serp_provider_header"), t("sidebar_serp_desc"), "green")
        available_serp = get_available_serp_providers()
        serp_selected_provider = None
        serp_num = 10
        serp_gl = "ua"
        serp_hl = "uk"
        serp_headless = bool(current_serp_config.get("headless", False))

        if not available_serp:
            st.info(t("serp_no_keys"))
        else:
            current_serp_provider = current_serp_config.get("provider", "serper_dev")
            serp_display_names = {v: k for k, v in SERP_PROVIDER_OPTIONS.items()}
            current_display = serp_display_names.get(
                current_serp_provider, list(available_serp.keys())[0]
            )
            default_serp_index = (
                list(available_serp.keys()).index(current_display)
                if current_display in available_serp
                else 0
            )
            serp_selected_provider = st.selectbox(
                t("serp_provider_select"),
                list(available_serp.keys()),
                index=default_serp_index,
            )
            serp_num = st.number_input(
                t("serp_num_results"),
                min_value=1,
                max_value=100,
                value=current_serp_config.get("num_results", 10),
            )
            current_gl = current_serp_config.get("gl", "ua")
            default_gl_index = (
                list(SERP_LOCATION_OPTIONS.values()).index(current_gl)
                if current_gl in SERP_LOCATION_OPTIONS.values()
                else 0
            )
            serp_gl_display = st.selectbox(
                t("serp_location"),
                list(SERP_LOCATION_OPTIONS.keys()),
                index=default_gl_index,
            )
            serp_gl = SERP_LOCATION_OPTIONS[serp_gl_display]

            current_hl = current_serp_config.get("hl", "uk")
            default_hl_index = (
                list(SERP_LANGUAGE_OPTIONS.values()).index(current_hl)
                if current_hl in SERP_LANGUAGE_OPTIONS.values()
                else 0
            )
            serp_hl_display = st.selectbox(
                t("serp_language"),
                list(SERP_LANGUAGE_OPTIONS.keys()),
                index=default_hl_index,
            )
            serp_hl = SERP_LANGUAGE_OPTIONS[serp_hl_display]

            # Advanced SERP parameters
            current_device = current_serp_config.get("device", "desktop")
            default_device_index = (
                list(SERP_DEVICE_OPTIONS.values()).index(current_device)
                if current_device in SERP_DEVICE_OPTIONS.values() else 0
            )
            serp_device_display = st.selectbox(
                t("serp_device"),
                list(SERP_DEVICE_OPTIONS.keys()),
                index=default_device_index,
            )
            serp_device = SERP_DEVICE_OPTIONS[serp_device_display]

            current_search_type = current_serp_config.get("search_type", "web")
            default_st_index = (
                list(SERP_SEARCH_TYPE_OPTIONS.values()).index(current_search_type)
                if current_search_type in SERP_SEARCH_TYPE_OPTIONS.values() else 0
            )
            serp_search_type_display = st.selectbox(
                t("serp_search_type"),
                list(SERP_SEARCH_TYPE_OPTIONS.keys()),
                index=default_st_index,
            )
            serp_search_type = SERP_SEARCH_TYPE_OPTIONS[serp_search_type_display]

            current_time_period = current_serp_config.get("time_period", "any")
            default_tp_index = (
                list(SERP_TIME_PERIOD_OPTIONS.values()).index(current_time_period)
                if current_time_period in SERP_TIME_PERIOD_OPTIONS.values() else 0
            )
            serp_time_period_display = st.selectbox(
                t("serp_time_period"),
                list(SERP_TIME_PERIOD_OPTIONS.keys()),
                index=default_tp_index,
            )
            serp_time_period = SERP_TIME_PERIOD_OPTIONS[serp_time_period_display]

            current_safe_search = current_serp_config.get("safe_search", "off")
            default_ss_index = (
                list(SERP_SAFE_SEARCH_OPTIONS.values()).index(current_safe_search)
                if current_safe_search in SERP_SAFE_SEARCH_OPTIONS.values() else 0
            )
            serp_safe_search_display = st.selectbox(
                t("serp_safe_search"),
                list(SERP_SAFE_SEARCH_OPTIONS.keys()),
                index=default_ss_index,
            )
            serp_safe_search = SERP_SAFE_SEARCH_OPTIONS[serp_safe_search_display]

            current_google_domain = current_serp_config.get("google_domain", "google.com")
            default_gd_index = (
                list(SERP_GOOGLE_DOMAIN_OPTIONS.values()).index(current_google_domain)
                if current_google_domain in SERP_GOOGLE_DOMAIN_OPTIONS.values() else 0
            )
            serp_google_domain_display = st.selectbox(
                t("serp_google_domain"),
                list(SERP_GOOGLE_DOMAIN_OPTIONS.keys()),
                index=default_gd_index,
            )
            serp_google_domain = SERP_GOOGLE_DOMAIN_OPTIONS[serp_google_domain_display]

            serp_city = st.text_input(
                t("serp_city"),
                value=current_serp_config.get("location", ""),
            )
            serp_uule = st.text_input(
                t("serp_uule"),
                value=current_serp_config.get("uule", ""),
            )
            serp_provider_value = SERP_PROVIDER_OPTIONS.get(
                serp_selected_provider,
                current_serp_provider,
            )
            if serp_provider_value == "browser_cloakbrowser":
                serp_headless = st.checkbox(
                    t("serp_local_headless"),
                    value=serp_headless,
                    key="serp_local_headless_checkbox",
                )

        serp_sidebar_values = _build_serp_sidebar_values(
            current_serp_config,
            serp_selected_provider,
            serp_num,
            serp_gl,
            serp_hl,
            serp_device if available_serp else "desktop",
            serp_search_type if available_serp else "web",
            serp_time_period if available_serp else "any",
            serp_safe_search if available_serp else "off",
            serp_google_domain if available_serp else "google.com",
            serp_city if available_serp else "",
            serp_uule if available_serp else "",
            serp_headless,
        )

        st.divider()

        # --- SEO Math Analysis ---
        _render_section_header(t("seo_math_header"), t("sidebar_seo_math_desc"), "orange")
        current_seo_math_config = current_config.get("seo_math", {})

        # FUNCTION_CONTRACT: _seo_math_value - get SEO math config value
        def _seo_math_value(config_key: str, fallback: Any) -> Any:
            return _section_config_value(
                current_seo_math_config,
                SEO_MATH_CONFIG,
                config_key,
                fallback,
            )

        _sync_sidebar_widget_from_config(
            "seo_math_enabled_checkbox", bool(_seo_math_value("enabled", False))
        )
        seo_math_enabled = st.checkbox(
            t("seo_math_enabled"),
            key="seo_math_enabled_checkbox",
            help=t("seo_math_enabled_help"),
        )

        if seo_math_enabled:
            _sync_sidebar_widget_from_config(
                "seo_math_analyze_ngrams_checkbox",
                bool(_seo_math_value("analyze_ngrams", True)),
            )
            seo_math_analyze_ngrams = st.checkbox(
                t("seo_math_analyze_ngrams"),
                key="seo_math_analyze_ngrams_checkbox",
            )
            _sync_sidebar_widget_from_config(
                "seo_math_analyze_bm25f_checkbox",
                bool(_seo_math_value("analyze_bm25f", True)),
            )
            seo_math_analyze_bm25f = st.checkbox(
                t("seo_math_analyze_bm25f"),
                key="seo_math_analyze_bm25f_checkbox",
            )
            _sync_sidebar_widget_from_config(
                "seo_math_analyze_tfidf_checkbox",
                bool(_seo_math_value("analyze_tfidf", True)),
            )
            seo_math_analyze_tfidf = st.checkbox(
                t("seo_math_analyze_tfidf"),
                key="seo_math_analyze_tfidf_checkbox",
            )
            _sync_sidebar_widget_from_config(
                "seo_math_analyze_cooccurrence_checkbox",
                bool(_seo_math_value("analyze_cooccurrence", True)),
            )
            seo_math_analyze_cooccurrence = st.checkbox(
                t("seo_math_analyze_cooccurrence"),
                key="seo_math_analyze_cooccurrence_checkbox",
            )
            _sync_sidebar_widget_from_config(
                "seo_math_analyze_intent_checkbox",
                bool(_seo_math_value("analyze_intent", True)),
            )
            seo_math_analyze_intent = st.checkbox(
                t("seo_math_analyze_intent"),
                key="seo_math_analyze_intent_checkbox",
            )
            _sync_sidebar_widget_from_config(
                "seo_math_analyze_generation_quality_checkbox",
                bool(_seo_math_value("analyze_generation_quality", True)),
            )
            seo_math_analyze_generation_quality = st.checkbox(
                t("seo_math_analyze_generation_quality"),
                key="seo_math_analyze_generation_quality_checkbox",
            )
            _sync_sidebar_widget_from_config(
                "seo_math_analyze_generated_text_checkbox",
                bool(_seo_math_value("analyze_generated_text", False)),
            )
            seo_math_analyze_generated_text = st.checkbox(
                t("seo_math_analyze_generated_text"),
                key="seo_math_analyze_generated_text_checkbox",
            )

            with st.expander(t("seo_math_advanced")):
                _sync_sidebar_widget_from_config(
                    "seo_math_ngram_min_slider",
                    int(_seo_math_value("ngram_min", 1)),
                )
                seo_math_ngram_min = st.slider(
                    t("seo_math_ngram_min"),
                    min_value=1,
                    max_value=2,
                    key="seo_math_ngram_min_slider",
                )
                _sync_sidebar_widget_from_config(
                    "seo_math_ngram_max_slider",
                    int(_seo_math_value("ngram_max", 3)),
                )
                seo_math_ngram_max = st.slider(
                    t("seo_math_ngram_max"),
                    min_value=2,
                    max_value=4,
                    key="seo_math_ngram_max_slider",
                )
                _sync_sidebar_widget_from_config(
                    "seo_math_top_terms_slider",
                    int(_seo_math_value("top_terms_limit", 30)),
                )
                seo_math_top_terms = st.slider(
                    t("seo_math_top_terms"),
                    min_value=10,
                    max_value=50,
                    key="seo_math_top_terms_slider",
                )
                _sync_sidebar_widget_from_config(
                    "seo_math_min_count_slider",
                    int(_seo_math_value("min_ngram_count", 2)),
                )
                seo_math_min_count = st.slider(
                    t("seo_math_min_count"),
                    min_value=1,
                    max_value=5,
                    key="seo_math_min_count_slider",
                )
                _sync_sidebar_widget_from_config(
                    "seo_math_min_df_slider",
                    int(_seo_math_value("min_document_frequency", 2)),
                )
                seo_math_min_df = st.slider(
                    t("seo_math_min_df"),
                    min_value=1,
                    max_value=5,
                    key="seo_math_min_df_slider",
                )
                _sync_sidebar_widget_from_config(
                    "seo_math_use_related_checkbox",
                    bool(_seo_math_value("use_related_searches", True)),
                )
                seo_math_use_related = st.checkbox(
                    t("seo_math_use_related"),
                    key="seo_math_use_related_checkbox",
                )
                _sync_sidebar_widget_from_config(
                    "seo_math_use_paa_checkbox",
                    bool(_seo_math_value("use_people_also_ask", True)),
                )
                seo_math_use_paa = st.checkbox(
                    t("seo_math_use_paa"),
                    key="seo_math_use_paa_checkbox",
                )
                _sync_sidebar_widget_from_config(
                    "seo_math_strip_suffixes_checkbox",
                    bool(_seo_math_value("strip_suffixes", False)),
                )
                seo_math_strip_suffixes = st.checkbox(
                    t("seo_math_strip_suffixes"),
                    key="seo_math_strip_suffixes_checkbox",
                    help=t("seo_math_strip_suffixes_help"),
                )
                bm25f_params = current_seo_math_config.get("bm25f_params", {})
                default_bm25f_params = SEO_MATH_CONFIG.get("bm25f_params", {})
                st.caption(t("seo_math_bm25f_params"))
                seo_math_bm25f_k1 = st.number_input(
                    "k1",
                    min_value=0.1,
                    max_value=5.0,
                    value=float(bm25f_params.get("k1", default_bm25f_params.get("k1", 1.2))),
                    step=0.1,
                    key="seo_math_bm25f_k1_input",
                )
                seo_math_bm25f_b_body = st.number_input(
                    "b_body",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(bm25f_params.get("b_body", default_bm25f_params.get("b_body", 0.75))),
                    step=0.05,
                    key="seo_math_bm25f_b_body_input",
                )
                seo_math_bm25f_b_title = st.number_input(
                    "b_title",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(bm25f_params.get("b_title", default_bm25f_params.get("b_title", 0.5))),
                    step=0.05,
                    key="seo_math_bm25f_b_title_input",
                )
                seo_math_bm25f_b_snippet = st.number_input(
                    "b_snippet",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(bm25f_params.get("b_snippet", default_bm25f_params.get("b_snippet", 0.6))),
                    step=0.05,
                    key="seo_math_bm25f_b_snippet_input",
                )
                field_weights = current_seo_math_config.get("field_weights", {})
                default_field_weights = SEO_MATH_CONFIG.get("field_weights", {})
                st.caption(t("seo_math_field_weights"))
                seo_math_weight_serp_title = st.number_input(
                    "SERP title",
                    0.0,
                    10.0,
                    float(field_weights.get("serp_title", default_field_weights.get("serp_title", 3.0))),
                    0.1,
                    key="seo_math_weight_serp_title_input",
                )
                seo_math_weight_page_title = st.number_input(
                    "Page title",
                    0.0,
                    10.0,
                    float(field_weights.get("page_title", default_field_weights.get("page_title", 3.0))),
                    0.1,
                    key="seo_math_weight_page_title_input",
                )
                seo_math_weight_h1 = st.number_input(
                    "H1",
                    0.0,
                    10.0,
                    float(field_weights.get("h1", default_field_weights.get("h1", 2.5))),
                    0.1,
                    key="seo_math_weight_h1_input",
                )
                seo_math_weight_meta_description = st.number_input(
                    "Meta description",
                    0.0,
                    10.0,
                    float(field_weights.get("meta_description", default_field_weights.get("meta_description", 1.5))),
                    0.1,
                    key="seo_math_weight_meta_description_input",
                )
                seo_math_weight_serp_snippet = st.number_input(
                    "SERP snippet",
                    0.0,
                    10.0,
                    float(field_weights.get("serp_snippet", default_field_weights.get("serp_snippet", 1.5))),
                    0.1,
                    key="seo_math_weight_serp_snippet_input",
                )
                seo_math_weight_related_searches = st.number_input(
                    "Related searches",
                    0.0,
                    10.0,
                    float(field_weights.get("related_searches", default_field_weights.get("related_searches", 1.2))),
                    0.1,
                    key="seo_math_weight_related_searches_input",
                )
                seo_math_weight_people_also_ask = st.number_input(
                    "People Also Ask",
                    0.0,
                    10.0,
                    float(field_weights.get("people_also_ask", default_field_weights.get("people_also_ask", 1.1))),
                    0.1,
                    key="seo_math_weight_people_also_ask_input",
                )
                seo_math_weight_trends_related = st.number_input(
                    "Trends related",
                    0.0,
                    10.0,
                    float(field_weights.get("trends_related", default_field_weights.get("trends_related", 1.2))),
                    0.1,
                    key="seo_math_weight_trends_related_input",
                )
                seo_math_weight_body_text = st.number_input(
                    "Body text",
                    0.0,
                    10.0,
                    float(field_weights.get("body_text", default_field_weights.get("body_text", 1.0))),
                    0.1,
                    key="seo_math_weight_body_text_input",
                )
                seo_math_weight_anchor_text = st.number_input(
                    "Anchor text",
                    0.0,
                    10.0,
                    float(field_weights.get("anchor_text", default_field_weights.get("anchor_text", 1.4))),
                    0.1,
                    key="seo_math_weight_anchor_text_input",
                )
                signal_config = current_seo_math_config.get("signals", {})
                default_signal_config = SEO_MATH_CONFIG.get("signals", {})
                st.caption(t("seo_math_signals"))
                seo_math_signal_title_alignment = st.checkbox(
                    "Title alignment",
                    value=bool(signal_config.get("title_alignment", default_signal_config.get("title_alignment", True))),
                    key="seo_math_signal_title_alignment_checkbox",
                )
                seo_math_signal_content_effort = st.checkbox(
                    "Content effort",
                    value=bool(signal_config.get("content_effort", default_signal_config.get("content_effort", True))),
                    key="seo_math_signal_content_effort_checkbox",
                )
                seo_math_signal_topical_overlap = st.checkbox(
                    "Topical overlap",
                    value=bool(signal_config.get("topical_overlap", default_signal_config.get("topical_overlap", True))),
                    key="seo_math_signal_topical_overlap_checkbox",
                )
                seo_math_signal_simhash = st.checkbox(
                    "SimHash",
                    value=bool(signal_config.get("simhash", default_signal_config.get("simhash", True))),
                    key="seo_math_signal_simhash_checkbox",
                )
        else:
            seo_math_analyze_ngrams = bool(_seo_math_value("analyze_ngrams", True))
            seo_math_analyze_bm25f = bool(_seo_math_value("analyze_bm25f", True))
            seo_math_analyze_tfidf = bool(_seo_math_value("analyze_tfidf", True))
            seo_math_analyze_cooccurrence = bool(
                _seo_math_value("analyze_cooccurrence", True)
            )
            seo_math_analyze_intent = bool(_seo_math_value("analyze_intent", True))
            seo_math_analyze_generation_quality = bool(
                _seo_math_value("analyze_generation_quality", True)
            )
            seo_math_analyze_generated_text = bool(
                _seo_math_value("analyze_generated_text", False)
            )
            seo_math_ngram_min = int(_seo_math_value("ngram_min", 1))
            seo_math_ngram_max = int(_seo_math_value("ngram_max", 3))
            seo_math_top_terms = int(_seo_math_value("top_terms_limit", 30))
            seo_math_min_count = int(_seo_math_value("min_ngram_count", 2))
            seo_math_min_df = int(_seo_math_value("min_document_frequency", 2))
            seo_math_use_related = bool(
                _seo_math_value("use_related_searches", True)
            )
            seo_math_use_paa = bool(_seo_math_value("use_people_also_ask", True))
            seo_math_strip_suffixes = bool(_seo_math_value("strip_suffixes", False))
            bm25f_params = current_seo_math_config.get("bm25f_params", {})
            default_bm25f_params = SEO_MATH_CONFIG.get("bm25f_params", {})
            seo_math_bm25f_k1 = float(bm25f_params.get("k1", default_bm25f_params.get("k1", 1.2)))
            seo_math_bm25f_b_body = float(bm25f_params.get("b_body", default_bm25f_params.get("b_body", 0.75)))
            seo_math_bm25f_b_title = float(bm25f_params.get("b_title", default_bm25f_params.get("b_title", 0.5)))
            seo_math_bm25f_b_snippet = float(bm25f_params.get("b_snippet", default_bm25f_params.get("b_snippet", 0.6)))
            field_weights = current_seo_math_config.get("field_weights", {})
            default_field_weights = SEO_MATH_CONFIG.get("field_weights", {})
            seo_math_weight_serp_title = float(field_weights.get("serp_title", default_field_weights.get("serp_title", 3.0)))
            seo_math_weight_page_title = float(field_weights.get("page_title", default_field_weights.get("page_title", 3.0)))
            seo_math_weight_h1 = float(field_weights.get("h1", default_field_weights.get("h1", 2.5)))
            seo_math_weight_meta_description = float(field_weights.get("meta_description", default_field_weights.get("meta_description", 1.5)))
            seo_math_weight_serp_snippet = float(field_weights.get("serp_snippet", default_field_weights.get("serp_snippet", 1.5)))
            seo_math_weight_related_searches = float(field_weights.get("related_searches", default_field_weights.get("related_searches", 1.2)))
            seo_math_weight_people_also_ask = float(field_weights.get("people_also_ask", default_field_weights.get("people_also_ask", 1.1)))
            seo_math_weight_trends_related = float(field_weights.get("trends_related", default_field_weights.get("trends_related", 1.2)))
            seo_math_weight_body_text = float(field_weights.get("body_text", default_field_weights.get("body_text", 1.0)))
            seo_math_weight_anchor_text = float(field_weights.get("anchor_text", default_field_weights.get("anchor_text", 1.4)))
            signal_config = current_seo_math_config.get("signals", {})
            default_signal_config = SEO_MATH_CONFIG.get("signals", {})
            seo_math_signal_title_alignment = bool(signal_config.get("title_alignment", default_signal_config.get("title_alignment", True)))
            seo_math_signal_content_effort = bool(signal_config.get("content_effort", default_signal_config.get("content_effort", True)))
            seo_math_signal_topical_overlap = bool(signal_config.get("topical_overlap", default_signal_config.get("topical_overlap", True)))
            seo_math_signal_simhash = bool(signal_config.get("simhash", default_signal_config.get("simhash", True)))

        st.divider()

        current_cache_config = current_config.get("cache", {})
        _render_section_header(t("cache_header"), t("sidebar_cache_desc"), "blue")
        cache_enabled = st.checkbox(
            t("cache_enabled"),
            value=bool(current_cache_config.get("enabled", CACHE_CONFIG.get("enabled", True))),
            key="cache_enabled_checkbox",
        )
        cache_force_refresh = st.checkbox(
            t("cache_force_refresh"),
            value=False,
            key="cache_force_refresh_checkbox",
        )
        cache_default_ttl_hours = st.number_input(
            t("cache_default_ttl_hours"),
            min_value=1,
            max_value=24 * 365,
            value=int(current_cache_config.get("default_ttl_hours", CACHE_CONFIG.get("default_ttl_hours", 168))),
            key="cache_default_ttl_hours_input",
        )
        cache_max_records = st.number_input(
            t("cache_max_records"),
            min_value=100,
            max_value=100000,
            value=int(current_cache_config.get("max_cache_records", CACHE_CONFIG.get("max_cache_records", 10000))),
            step=100,
            key="cache_max_records_input",
        )

        st.divider()

        current_trends_config = current_config.get("google_trends", {})
        _render_section_header(t("google_trends_header"), t("sidebar_trends_desc"), "green")
        google_trends_default_geo = st.text_input(
            t("google_trends_default_geo"),
            value=str(current_trends_config.get("default_geo", GOOGLE_TRENDS_CONFIG.get("default_geo", "UA"))),
            key="google_trends_default_geo_input",
        )
        google_trends_default_timeframe = st.text_input(
            t("google_trends_default_timeframe"),
            value=str(current_trends_config.get("default_timeframe", GOOGLE_TRENDS_CONFIG.get("default_timeframe", "today 12-m"))),
            key="google_trends_default_timeframe_input",
        )
        google_trends_cache_ttl_hours = st.number_input(
            t("google_trends_cache_ttl_hours"),
            min_value=1,
            max_value=24 * 365,
            value=int(current_trends_config.get("cache_ttl_hours", GOOGLE_TRENDS_CONFIG.get("cache_ttl_hours", 24))),
            key="google_trends_cache_ttl_hours_input",
        )
        google_trends_max_keywords_min = int(
            current_trends_config.get(
                "max_keywords_per_request_min",
                GOOGLE_TRENDS_CONFIG.get("max_keywords_per_request_min", 1),
            )
        )
        google_trends_max_keywords_max = int(
            current_trends_config.get(
                "max_keywords_per_request_max",
                GOOGLE_TRENDS_CONFIG.get("max_keywords_per_request_max", 100),
            )
        )
        if google_trends_max_keywords_min > google_trends_max_keywords_max:
            google_trends_max_keywords_min, google_trends_max_keywords_max = (
                google_trends_max_keywords_max,
                google_trends_max_keywords_min,
            )
        google_trends_max_keywords_per_request = st.number_input(
            t("google_trends_max_keywords_per_request"),
            min_value=google_trends_max_keywords_min,
            max_value=google_trends_max_keywords_max,
            value=int(
                current_trends_config.get(
                    "max_keywords_per_request",
                    GOOGLE_TRENDS_CONFIG.get("max_keywords_per_request", 10),
                )
            ),
            help=t("google_trends_max_keywords_per_request_help"),
            key="google_trends_max_keywords_per_request_input",
        )

        google_trends_show_confidence = st.checkbox(
            t("trends_show_confidence_metadata"),
            value=bool(current_trends_config.get("show_confidence_metadata", True)),
            key="google_trends_show_confidence_checkbox",
        )

        from utils.google_trends_client import (
            TRENDS_PROVIDER_OPTIONS,
            TRENDS_PROVIDER_REGISTRY,
        )
        TRENDS_PROVIDER_LABELS: dict[str, str] = {
            "browser_scraper_trends": t("trends_provider_local_browser"),
            "serpapi_trends": t("trends_provider_serpapi"),
            "dataforseo_trends": t("trends_provider_dataforseo"),
            "scrapebadger_web": t("trends_provider_scrapebadger"),
        }

        available_providers: list[str] = []
        for _prov_name in list(
            dict.fromkeys(
                list(TRENDS_PROVIDER_REGISTRY.keys()) + list(TRENDS_PROVIDER_OPTIONS)
            )
        ):
            _prov_adapter = TRENDS_PROVIDER_REGISTRY.get(_prov_name)
            if _prov_adapter is None:
                continue
            try:
                _is_available = bool(_prov_adapter.is_available())
            except Exception:
                _is_available = False
            if not _is_available:
                continue
            # google_trends_auto is added by the dedicated auto-insert block below,
            # which checks that the primary adapter (google_trends_direct) is available.
            if _prov_name == "google_trends_auto":
                continue
            available_providers.append(_prov_name)

        current_provider = str(
            current_trends_config.get(
                "provider",
                GOOGLE_TRENDS_CONFIG.get(
                    "provider", "browser_scraper_trends"
                ),
            )
        )
        if available_providers:
            google_trends_provider = st.selectbox(
                t("google_trends_provider_selectbox"),
                options=available_providers,
                format_func=lambda p: TRENDS_PROVIDER_LABELS.get(p, p),
                index=available_providers.index(current_provider)
                if current_provider in available_providers
                else 0,
                key="google_trends_provider_selectbox",
            )
        else:
            google_trends_provider = ""

        category_options = ["", "5", "10", "17", "18", "22", "29", "47", "71", "91", "284", "366"]
        current_category = str(current_trends_config.get("default_category", GOOGLE_TRENDS_CONFIG.get("default_category", "")))
        google_trends_default_category = st.selectbox(
            t("google_trends_default_category"),
            options=category_options,
            index=category_options.index(current_category) if current_category in category_options else 0,
            key="google_trends_default_category_selectbox",
        )

        property_options = ["", "images", "news", "youtube", "froogle"]
        current_property = str(current_trends_config.get("default_property", GOOGLE_TRENDS_CONFIG.get("default_property", "")))
        google_trends_default_property = st.selectbox(
            t("google_trends_default_property"),
            options=property_options,
            index=property_options.index(current_property) if current_property in property_options else 0,
            key="google_trends_default_property_selectbox",
        )

        language_options = ["", "en", "ru", "uk", "de", "fr", "es", "it", "pt", "ja", "ko", "zh"]
        current_language = str(current_trends_config.get("default_language", GOOGLE_TRENDS_CONFIG.get("default_language", "")))
        google_trends_default_language = st.selectbox(
            t("google_trends_default_language"),
            options=language_options,
            index=language_options.index(current_language) if current_language in language_options else 0,
            key="google_trends_default_language_selectbox",
        )

        timezone_options = ["", "0", "1", "2", "3", "-1", "-2", "-3", "-5", "-8"]
        current_timezone = str(current_trends_config.get("default_timezone", GOOGLE_TRENDS_CONFIG.get("default_timezone", "")))
        google_trends_default_timezone = st.selectbox(
            t("google_trends_default_timezone"),
            options=timezone_options,
            index=timezone_options.index(current_timezone) if current_timezone in timezone_options else 0,
            key="google_trends_default_timezone_selectbox",
        )

        google_trends_force_refresh = st.checkbox(
            t("google_trends_force_refresh"),
            value=False,
            key="google_trends_force_refresh_checkbox",
        )

        # Local browser trends settings
        BROWSER_TRENDS_PROVIDERS = {"browser_scraper_trends", "google_trends_auto"}
        google_trends_headless = bool(
            current_trends_config.get(
                "headless",
                GOOGLE_TRENDS_CONFIG.get("headless", False),
            )
        )
        if google_trends_provider in BROWSER_TRENDS_PROVIDERS:
            _render_section_header(t("trends_local_settings_header"), t("sidebar_trends_local_desc"), "orange")

            google_trends_headless = st.checkbox(
                t("google_trends_local_headless"),
                value=google_trends_headless,
                key="google_trends_local_headless_checkbox",
            )
            trends_manual_warmup = st.number_input(
                t("trends_local_warmup_wait"),
                min_value=0,
                max_value=300,
                value=int(
                    current_trends_config.get(
                        "manual_start_wait",
                        GOOGLE_TRENDS_CONFIG.get("manual_start_wait", 0),
                    )
                ),
                help=t("trends_local_warmup_wait_help"),
                key="trends_manual_warmup_input",
            )
            trends_min_delay = st.number_input(
                t("trends_local_min_delay"),
                min_value=1,
                max_value=1800,
                value=int(
                    current_trends_config.get(
                        "min_delay",
                        GOOGLE_TRENDS_CONFIG.get("min_delay", 60),
                    )
                ),
                key="trends_min_delay_input",
            )
            trends_max_delay = st.number_input(
                t("trends_local_max_delay"),
                min_value=10,
                max_value=1800,
                value=int(
                    current_trends_config.get(
                        "max_delay",
                        GOOGLE_TRENDS_CONFIG.get("max_delay", 60),
                    )
                ),
                key="trends_max_delay_input",
            )
            trends_state_file = st.text_input(
                t("trends_local_state_file"),
                value=str(current_trends_config.get("state_file", "trends_state.json")),
                key="trends_state_file_input",
            )
            st.caption(t("trends_local_constraint_note"))
        else:
            trends_manual_warmup = int(
                current_trends_config.get(
                    "manual_start_wait",
                    GOOGLE_TRENDS_CONFIG.get("manual_start_wait", 0),
                )
            )
            trends_min_delay = int(
                current_trends_config.get("min_delay", GOOGLE_TRENDS_CONFIG.get("min_delay", 60))
            )
            trends_max_delay = int(
                current_trends_config.get("max_delay", GOOGLE_TRENDS_CONFIG.get("max_delay", 60))
            )
            trends_state_file = str(current_trends_config.get("state_file", "trends_state.json"))

        current_scraper_config = current_config.get("scraper", {})
        _render_section_header(t("scraper_header"), t("sidebar_scraper_desc"), "green")
        scraper_browser_enabled = st.checkbox(
            t("scraper_browser_enabled"),
            value=bool(current_scraper_config.get("browser_enabled", SCRAPER_CONFIG.get("browser_enabled", False))),
            help=t("scraper_browser_enabled_help"),
            key="scraper_browser_enabled_checkbox",
        )
        if scraper_browser_enabled:
            dependency_statuses = BrowserScraper.check_dependencies()
            status_labels = {
                DependencyStatus.AVAILABLE: t("scraper_dependency_status_available"),
                DependencyStatus.MISSING: t("scraper_dependency_status_missing"),
                DependencyStatus.UNKNOWN: t("scraper_dependency_status_unknown"),
                DependencyStatus.UNUSABLE: t("scraper_dependency_status_unusable"),
            }
            # Map tool names to localized display names
            tool_name_labels = {
                "cloakbrowser": t("scraper_dependency_name_cloakbrowser"),
                "trafilatura": t("scraper_dependency_name_trafilatura"),
            }
            st.caption(t("scraper_dependency_status_header"))
            st.table(
                [
                    {
                        t("scraper_dependency_name_col"): tool_name_labels.get(name, name),
                        t("scraper_dependency_status_col"): status_labels.get(status, status.value),
                    }
                    for name, status in dependency_statuses.items()
                ]
            )
            problem_dependencies = get_problem_dependencies(dependency_statuses)
            if problem_dependencies:
                st.warning(t("scraper_dependencies_missing_prompt"))
                install_scope = st.radio(
                    t("scraper_install_scope_label"),
                    options=["project", "global"],
                    format_func=lambda value: (
                        t("scraper_install_scope_project")
                        if value == "project"
                        else t("scraper_install_scope_global")
                    ),
                    horizontal=True,
                    key="scraper_install_scope_radio",
                )
                st.caption(t("scraper_install_command_label"))
                st.code(
                    build_optional_dependency_install_command(install_scope),
                    language="powershell",
                )
            else:
                st.success(t("scraper_dependencies_ready"))

        st.divider()

        # --- Crawl Workflow ---
        _render_section_header(t("crawl_settings_header"), t("sidebar_crawl_desc"), "blue")
        # Load fresh config for crawler to ensure saved values are used
        fresh_config = load_config()
        fresh_crawler = fresh_config.get("crawler", {})
        crawler_enabled = st.checkbox(
            t("crawl_enabled"),
            value=fresh_crawler.get("enabled", False),
            help=t("crawl_enabled_help"),
            key="crawler_enabled_checkbox",
        )
        crawler_max_pages = st.slider(
            t("crawl_max_pages"),
            min_value=1,
            max_value=100,
            value=fresh_crawler.get("max_pages", 50),
            key="crawler_max_pages_slider",
        )
        st.caption(t("crawl_max_pages_help"))
        crawler_max_depth = st.slider(
            t("crawl_max_depth"),
            min_value=0,
            max_value=5,
            value=fresh_crawler.get("max_depth", 3),
            key="crawler_max_depth_slider",
        )
        crawler_same_domain_only = st.checkbox(
            t("crawl_same_domain_only"),
            value=fresh_crawler.get("same_domain_only", True),
            key="crawler_same_domain_checkbox",
        )
        crawler_timeout_seconds = st.number_input(
            t("crawl_timeout_seconds"),
            min_value=10,
            max_value=600,
            value=fresh_crawler.get("timeout_seconds", 120),
            key="crawler_timeout_input",
        )
        crawler_max_response_bytes = st.number_input(
            t("crawl_max_response_bytes"),
            min_value=1_048_576,
            max_value=52_428_800,
            value=fresh_crawler.get("max_response_bytes", 10_485_760),
            step=1_048_576,
            key="crawler_max_bytes_input",
        )
        crawler_max_retries = st.slider(
            t("crawl_max_retries"),
            min_value=0,
            max_value=2,
            value=fresh_crawler.get("max_retries", 1),
            key="crawler_max_retries_slider",
        )

        st.divider()

        # --- Google Ads ---
        _render_section_header(t("google_ads_header"), t("sidebar_ads_desc"), "orange")

        current_location_name, current_language_name = _resolve_google_ads_selection(
            current_google_ads_config, GOOGLE_ADS_LOCATIONS, GOOGLE_ADS_LANGUAGES
        )
        current_currency_code = str(
            current_google_ads_config.get("currency_code", GOOGLE_ADS_CURRENCIES[0])
        ).upper()
        if current_currency_code not in GOOGLE_ADS_CURRENCIES:
            current_currency_code = GOOGLE_ADS_CURRENCIES[0]
        location_options = list(GOOGLE_ADS_LOCATIONS.keys())
        location_name: str = st.selectbox(
            t("location"),
            location_options,
            index=location_options.index(current_location_name),
        )
        selected_location_id: str = GOOGLE_ADS_LOCATIONS[location_name]

        language_options = list(GOOGLE_ADS_LANGUAGES.keys())
        language_name: str = st.selectbox(
            t("language"),
            language_options,
            index=language_options.index(current_language_name),
        )
        selected_language_id = GOOGLE_ADS_LANGUAGES[language_name]
        currency_code: str = st.selectbox(
            t("currency"),
            GOOGLE_ADS_CURRENCIES,
            index=GOOGLE_ADS_CURRENCIES.index(current_currency_code),
            help=t("currency_help"),
        )

        st.divider()

        # --- API Parameters ---
        _render_section_header(t("api_params"), t("sidebar_api_desc"), "green")

        api_timeout: int = st.number_input(
            t("request_timeout"),
            min_value=10,
            max_value=300,
            value=max(int(current_llm_config.get("timeout_seconds", LLM_TIMEOUT)), 10),
            step=1,
            help=t("request_timeout_help"),
        )

        api_delay: int = st.number_input(
            t("delay_between_requests"),
            min_value=0,
            max_value=60,
            value=int(
                current_llm_config.get(
                    "delay_between_requests_seconds", LLM_DELAY_BETWEEN_REQUESTS
                )
            ),
            step=1,
            help=t("delay_between_requests_help"),
        )

        api_retry_count: int = st.number_input(
            t("retry_count"),
            min_value=1,
            max_value=20,
            value=int(current_retry_config.get("max_attempts", RETRY_ATTEMPTS)),
            step=1,
            help=t("retry_count_help"),
        )

        api_retry_delay: int = st.number_input(
            t("retry_delay"),
            min_value=0,
            max_value=300,
            value=int(current_retry_config.get("delay_seconds", RETRY_DELAY)),
            step=1,
            help=t("retry_delay_help"),
        )

        # --- System Prompts ---
        _render_section_header(t("system_prompts"), t("sidebar_prompts_desc"), "blue")

        st.markdown(t("keyword_prompt_desc"))
        keyword_prompt: str = st.text_area(
            t("keyword_prompt_label"),
            value=current_prompts.get(
                "keyword_extraction", KEYWORD_EXTRACTION_PROMPT
            ).strip(),
            height=250,
            key="keyword_extraction_prompt",
        )

        st.markdown(t("seo_prompt_desc"))
        seo_prompt: str = st.text_area(
            t("seo_prompt_label"),
            value=current_prompts.get(
                "seo_description", SEO_DESCRIPTION_PROMPT
            ).strip(),
            height=350,
            key="seo_description_prompt",
        )

        # --- Keyword-to-LLM Language (independent from generation_language) ---
        keyword_llm_language_options = [
            "Russian", "Ukrainian", "English", "German", "French",
            "Spanish", "Italian", "Portuguese", "Polish",
        ]
        keyword_llm_saved_language = current_llm_config.get(
            "keyword_llm_generation_language", "Russian"
        )
        keyword_llm_default_index = (
            keyword_llm_language_options.index(keyword_llm_saved_language)
            if keyword_llm_saved_language in keyword_llm_language_options
            else 0
        )
        keyword_llm_generation_language: str = st.selectbox(
            t("keyword_llm_language_label"),
            keyword_llm_language_options,
            index=keyword_llm_default_index,
            help=t("keyword_llm_language_help"),
            key="keyword_llm_generation_language",
        )

        # --- Page Type (Keyword -> LLM) — controls {page_type} in SEO prompt ---
        page_type_options = [
            "product",
            "category",
            "blog post",
            t("page_type_user_defined"),
        ]
        page_type_saved = current_llm_config.get("page_type", "product")
        # Saved value may be a user-defined string not present in the preset list;
        # fall back to the "Other / Custom" entry so the value is preserved verbatim.
        page_type_default_index = (
            page_type_options.index(page_type_saved)
            if page_type_saved in page_type_options
            else 3
        )
        page_type: str = st.selectbox(
            t("page_type_label"),
            page_type_options,
            index=page_type_default_index,
            help=t("page_type_help"),
            key="page_type",
        )
        # When the user selects "Other / Custom", expose a free-text input so they
        # can define the exact page type for the rewrite (e.g. "landing page").
        if page_type == t("page_type_user_defined"):
            page_type_custom_saved = current_llm_config.get("page_type", "")
            page_type_custom: str = st.text_input(
                t("page_type_custom_label"),
                value=page_type_custom_saved
                if page_type_custom_saved not in page_type_options
                else "",
                placeholder=t("page_type_custom_placeholder"),
                key="page_type_custom",
            )
            page_type = page_type_custom.strip() or "product"

        st.divider()

        # --- Storage & Limits ---
        _render_section_header(t("storage_limits_header"), t("sidebar_storage_desc"), "green")

        api_retention_days: int = st.number_input(
            t("api_retention_days_label"),
            min_value=0,
            max_value=365,
            value=int(current_logging_config.get("api_retention_days", 30)),
            step=1,
            help=t("api_retention_days_help"),
        )
        history_retention_days: int = st.number_input(
            t("history_retention_days_label"),
            min_value=0,
            max_value=365,
            value=int(
                current_history_config.get(
                    "retention_days", HISTORY_CONFIG.get("retention_days", 30)
                )
            ),
            step=1,
            help=t("history_retention_days_help"),
        )
        upload_max_file_size_mb: int = st.number_input(
            t("upload_max_file_size_mb_label"),
            min_value=1,
            max_value=100,
            value=int(
                current_uploads_config.get(
                    "max_file_size_mb", UPLOADS_CONFIG.get("max_file_size_mb", 5)
                )
            ),
            step=1,
            help=t("upload_max_file_size_mb_help"),
        )
        upload_max_rows: int = st.number_input(
            t("upload_max_rows_label"),
            min_value=1,
            max_value=100000,
            value=int(
                current_uploads_config.get(
                    "max_rows", UPLOADS_CONFIG.get("max_rows", 1000)
                )
            ),
            step=1,
            help=t("upload_max_rows_help"),
        )

        st.divider()

        # --- Logging ---
        _render_section_header(t("logging_header"), t("sidebar_logging_desc"), "orange")

        app_log_level: str = st.selectbox(
            t("log_app_level"),
            LOG_LEVELS,
            index=_safe_log_level_index(
                current_logging_config.get("app_level", "INFO"), "INFO"
            ),
        )
        console_logging_enabled: bool = st.checkbox(
            t("log_console_enabled"),
            value=bool(current_logging_config.get("console_enabled", True)),
        )
        console_log_level: str = st.selectbox(
            t("log_console_level"),
            LOG_LEVELS,
            index=_safe_log_level_index(
                current_logging_config.get("console_level", "INFO"), "INFO"
            ),
        )
        api_logging_enabled: bool = st.checkbox(
            t("log_api_enabled"),
            value=bool(current_logging_config.get("api_enabled", True)),
        )
        api_log_level: str = st.selectbox(
            t("log_api_level"),
            LOG_LEVELS,
            index=_safe_log_level_index(
                current_logging_config.get("api_level", "DEBUG"), "DEBUG"
            ),
        )
        error_log_level: str = st.selectbox(
            t("log_error_level"),
            LOG_LEVELS,
            index=_safe_log_level_index(
                current_logging_config.get("error_level", "ERROR"), "ERROR"
            ),
        )
        log_test_runs: bool = st.checkbox(
            t("log_test_runs"),
            value=bool(current_logging_config.get("log_test_runs", False)),
        )

        st.divider()

        # --- Export & Cleanup ---
        _render_section_header(t("export_header"), t("sidebar_export_desc"), "green")
        auto_save_excel: bool = st.checkbox(t("auto_save_excel"), value=True)

        cleanup_max_age: int = st.number_input(
            t("cleanup_days_label"),
            min_value=0,
            max_value=365,
            value=CLEANUP_CONFIG.get("max_age_days", 30),
            step=1,
            help=t("cleanup_days_help"),
        )

        st.divider()

        # Save prompts & API params button
        if st.button(t("save_settings"), type="primary"):
            try:
                save_config(
                    _build_sidebar_config_updates(
                        current_config,
                        {
                            "keyword_prompt": keyword_prompt,
                            "seo_prompt": seo_prompt,

                            "api_timeout": api_timeout,
                            "api_delay": api_delay,
                            "api_retry_count": api_retry_count,
                            "api_retry_delay": api_retry_delay,
                            "cleanup_max_age": cleanup_max_age,
                            "app_log_level": app_log_level,
                            "console_logging_enabled": console_logging_enabled,
                            "console_log_level": console_log_level,
                            "api_logging_enabled": api_logging_enabled,
                            "api_log_level": api_log_level,
                            "api_retention_days": api_retention_days,
                            "error_log_level": error_log_level,
                            "history_retention_days": history_retention_days,
                            "log_test_runs": log_test_runs,
                            "provider": provider,
                            "model_name": model_name,
                            "max_keywords": max_keywords,
                            "upload_max_file_size_mb": upload_max_file_size_mb,
                            "upload_max_rows": upload_max_rows,
                            "ui_lang": st.session_state.get("ui_lang", "ru"),
                            "location_id": selected_location_id,
                            "language_id": selected_language_id,
                            "currency_code": currency_code,
                            **serp_sidebar_values,
                            "seo_math_enabled": seo_math_enabled,
                            "seo_math_analyze_ngrams": seo_math_analyze_ngrams,
                            "seo_math_analyze_bm25f": seo_math_analyze_bm25f,
                            "seo_math_analyze_tfidf": seo_math_analyze_tfidf,
                            "seo_math_analyze_cooccurrence": seo_math_analyze_cooccurrence,
                            "seo_math_analyze_intent": seo_math_analyze_intent,
                            "seo_math_analyze_generation_quality": seo_math_analyze_generation_quality,
                            "seo_math_analyze_generated_text": seo_math_analyze_generated_text,
                            "seo_math_ngram_min": seo_math_ngram_min,
                            "seo_math_ngram_max": seo_math_ngram_max,
                            "seo_math_top_terms": seo_math_top_terms,
                            "seo_math_min_count": seo_math_min_count,
                            "seo_math_min_df": seo_math_min_df,
                            "seo_math_use_related": seo_math_use_related,
                            "seo_math_use_paa": seo_math_use_paa,
                            "seo_math_strip_suffixes": seo_math_strip_suffixes,
                            "seo_math_bm25f_k1": seo_math_bm25f_k1,
                            "seo_math_bm25f_b_body": seo_math_bm25f_b_body,
                            "seo_math_bm25f_b_title": seo_math_bm25f_b_title,
                            "seo_math_bm25f_b_snippet": seo_math_bm25f_b_snippet,
                            "seo_math_weight_serp_title": seo_math_weight_serp_title,
                            "seo_math_weight_page_title": seo_math_weight_page_title,
                            "seo_math_weight_h1": seo_math_weight_h1,
                            "seo_math_weight_meta_description": seo_math_weight_meta_description,
                            "seo_math_weight_serp_snippet": seo_math_weight_serp_snippet,
                            "seo_math_weight_related_searches": seo_math_weight_related_searches,
                            "seo_math_weight_people_also_ask": seo_math_weight_people_also_ask,
                            "seo_math_weight_trends_related": seo_math_weight_trends_related,
                            "seo_math_weight_body_text": seo_math_weight_body_text,
                            "seo_math_weight_anchor_text": seo_math_weight_anchor_text,
                            "seo_math_signal_title_alignment": seo_math_signal_title_alignment,
                            "seo_math_signal_content_effort": seo_math_signal_content_effort,
                            "seo_math_signal_topical_overlap": seo_math_signal_topical_overlap,
                            "seo_math_signal_simhash": seo_math_signal_simhash,
                            "cache_enabled": cache_enabled,
                            "cache_default_ttl_hours": cache_default_ttl_hours,
                            "cache_max_records": cache_max_records,
                            "google_trends_default_geo": google_trends_default_geo,
                            "google_trends_default_timeframe": google_trends_default_timeframe,
                            "google_trends_cache_ttl_hours": google_trends_cache_ttl_hours,
                            "google_trends_max_keywords_per_request": google_trends_max_keywords_per_request,
                            "google_trends_show_confidence": google_trends_show_confidence,
                            "google_trends_headless": google_trends_headless,
                            "trends_manual_warmup": trends_manual_warmup,
                            "trends_min_delay": trends_min_delay,
                            "trends_max_delay": trends_max_delay,
                            "trends_state_file": trends_state_file,
                            "scraper_browser_enabled": scraper_browser_enabled,
                            "crawler_enabled": crawler_enabled,
                            "crawler_max_pages": crawler_max_pages,
                            "crawler_max_depth": crawler_max_depth,
                            "crawler_same_domain_only": crawler_same_domain_only,
                            "crawler_timeout_seconds": crawler_timeout_seconds,
                            "crawler_max_response_bytes": crawler_max_response_bytes,
                            "crawler_max_retries": crawler_max_retries,
                            "keyword_llm_generation_language": keyword_llm_generation_language,
                            "page_type": page_type,
                        },
                    )
                )
                st.success(t("settings_saved"))
            except Exception as e:
                st.error(f"{t('settings_save_error')}: {e}")

    return {
        "provider": provider,
        "model_name": model_name,
        "max_keywords": max_keywords,
        "location_id": selected_location_id,
        "language_id": selected_language_id,
        "currency_code": currency_code,
        "auto_save_excel": auto_save_excel,
        "cleanup_max_age_days": cleanup_max_age,
        "keyword_prompt": keyword_prompt,
        "seo_prompt": seo_prompt,
        "api_timeout": api_timeout,
        "api_delay": api_delay,
        "api_retry_count": api_retry_count,
        "api_retry_delay": api_retry_delay,
        "upload_max_file_size_mb": upload_max_file_size_mb,
        "upload_max_rows": upload_max_rows,
        **serp_sidebar_values,
        "cache_force_refresh": cache_force_refresh,
        "google_trends_settings": {
            "default_geo": google_trends_default_geo,
            "default_timeframe": google_trends_default_timeframe,
            "cache_ttl_hours": google_trends_cache_ttl_hours,
            "max_keywords_per_request": google_trends_max_keywords_per_request,
            "provider": google_trends_provider,
            "default_category": int(google_trends_default_category) if google_trends_default_category else 0,
            "default_property": google_trends_default_property,
            "default_language": google_trends_default_language,
            "default_timezone": google_trends_default_timezone,
            "force_refresh": google_trends_force_refresh,
            "headless": google_trends_headless,
            "manual_start_wait": trends_manual_warmup,
            "min_delay": trends_min_delay,
            "max_delay": trends_max_delay,
            "state_file": trends_state_file,
        },
        "crawler_settings": {
            "enabled": crawler_enabled,
            "max_pages": crawler_max_pages,
            "max_depth": crawler_max_depth,
            "same_domain_only": crawler_same_domain_only,
            "timeout_seconds": crawler_timeout_seconds,
            "max_response_bytes": crawler_max_response_bytes,
            "max_retries": crawler_max_retries,
        },
        "keyword_llm_generation_language": keyword_llm_generation_language,
        "page_type": page_type,
    }
