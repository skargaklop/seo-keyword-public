"""
Sidebar UI component — LLM provider settings, Google Ads config, export options,
system prompts, and API parameters.
"""

import os
from typing import Dict, Any

import streamlit as st

from config.settings import (
    LLM_MODELS,
    CLEANUP_CONFIG,
    HISTORY_CONFIG,
    KEYWORD_EXTRACTION_PROMPT,
    SEO_DESCRIPTION_PROMPT,
    LLM_TIMEOUT,
    LLM_DELAY_BETWEEN_REQUESTS,
    RETRY_ATTEMPTS,
    RETRY_DELAY,
    UPLOADS_CONFIG,
    load_config,
    save_config,
)
from config.i18n import t

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
}


def _normalize_log_level_name(level_name: str, default: str) -> str:
    """Normalize log levels from YAML/UI without raising on invalid values."""
    aliases = {"WARN": "WARNING", "FATAL": "CRITICAL"}
    normalized_default = str(default).strip().upper()
    normalized = aliases.get(
        str(level_name).strip().upper(), str(level_name).strip().upper()
    )
    return normalized if normalized in LOG_LEVELS else normalized_default


def _safe_log_level_index(level_name: str, default: str) -> int:
    """Map possibly invalid log level name to a safe selectbox index."""
    return LOG_LEVELS.index(_normalize_log_level_name(level_name, default))


def _normalize_language_value(language_value: Any) -> tuple[str, ...]:
    """Normalize single or multi-language Google Ads values for comparisons."""
    if isinstance(language_value, list):
        return tuple(str(item) for item in language_value)
    return (str(language_value),)


def _resolve_google_ads_selection(
    google_ads_config: Dict[str, Any],
    locations: Dict[str, str],
    languages: Dict[str, Any],
) -> tuple[str, str]:
    """Resolve saved Google Ads ids back to sidebar labels."""
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


def _build_sidebar_config_updates(
    current_config: Dict[str, Any], values: Dict[str, Any]
) -> Dict[str, Any]:
    """Apply sidebar settings to config in one testable place."""
    llm_config = current_config.setdefault("llm", {})
    llm_prompts = llm_config.setdefault("prompts", {})
    llm_prompts["keyword_extraction"] = values["keyword_prompt"]
    llm_prompts["seo_description"] = values["seo_prompt"]
    llm_config["timeout_seconds"] = values["api_timeout"]
    llm_config["delay_between_requests_seconds"] = values["api_delay"]

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

    ui_prefs = current_config.setdefault("ui", {})
    ui_prefs["language"] = values["ui_lang"]
    ui_prefs["provider"] = values["provider"]
    ui_prefs["model"] = values["model_name"]
    ui_prefs["max_keywords"] = values["max_keywords"]
    return current_config


def _load_saved_ui() -> Dict[str, Any]:
    """Load saved UI preferences from settings.yaml."""
    try:
        cfg = load_config()
        return cfg.get("ui", {})
    except Exception:
        return {}


def render_sidebar() -> Dict[str, Any]:
    """
    Render the sidebar with all settings and return a dict of selected values.

    Returns:
        Dict with keys: provider, model_name, max_keywords, location_id,
        language_id, auto_save_excel, keyword_prompt, seo_prompt,
        api_timeout, api_delay, api_retry_count, api_retry_delay.
    """
    with st.sidebar:
        current_config = load_config()
        current_llm_config = current_config.get("llm", {})
        current_retry_config = current_config.get("retry", {})
        current_logging_config = current_config.get("logging", {})
        current_history_config = current_config.get("history", {})
        current_google_ads_config = current_config.get("google_ads", {})
        current_uploads_config = current_config.get("uploads", {})
        current_prompts = current_llm_config.get("prompts", {})

        # --- Language Selector ---
        lang_options = UI_LANGUAGE_OPTIONS
        lang_labels = list(lang_options.keys())
        # Load saved UI preferences on first run
        if "_ui_prefs_loaded" not in st.session_state:
            saved_ui = _load_saved_ui()
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

        selected_label = st.selectbox(
            t("ui_language"), lang_labels, index=current_index, key="ui_lang_selector"
        )
        st.session_state["ui_lang"] = lang_options[selected_label]

        st.header(t("settings_header"))

        # --- LLM Provider ---
        st.subheader(t("llm_provider"))

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
            "ZAI": "ZAI_API_KEY",
        }

        available_providers: list[str] = [
            name for name, key in provider_keys.items() if os.getenv(key)
        ]

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

        # Model presets
        default_presets: Dict[str, str] = {
            "OpenAI": "gpt-5.4",
            "Anthropic": "claude-sonnet-4-6",
            "Google": "gemini-3-flash-preview",
            "xAI": "grok-4-1-fast-reasoning",
            "Groq": "openai/gpt-oss-120b",
            "DeepSeek": "deepseek-chat",
            "MiniMax": "MiniMax-M2.5",
            "Moonshot": "moonshot/kimi-k2.5",
            "OpenRouter": "openrouter/free",
            "Cerebras": "gpt-oss-120b",
            "ZAI": "glm-4.7",
        }

        current_preset: str = default_presets.get(provider, "")
        if provider.lower() in LLM_MODELS:
            current_preset = LLM_MODELS[provider.lower()]
        # Use saved model if provider matches
        saved_model = st.session_state.get("_saved_model", "")
        if saved_model and saved_provider == provider:
            current_preset = saved_model

        model_name: str = st.text_input(t("model_name"), value=current_preset)
        saved_max_kw: int = st.session_state.get("_saved_max_keywords", 50)
        max_keywords: int = st.slider(t("max_keywords_per_url"), 5, 100, saved_max_kw)

        st.divider()

        # --- Google Ads ---
        st.subheader("Google Ads")

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
        st.subheader(t("api_params"))

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
        st.subheader(t("system_prompts"))

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

        st.divider()

        # --- Storage & Limits ---
        st.subheader(t("storage_limits_header"))

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
        st.subheader(t("logging_header"))

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
        st.subheader(t("export_header"))
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
    }
