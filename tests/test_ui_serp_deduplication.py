from contextlib import nullcontext

import streamlit as st

import components.results as results
from components.sidebar import _build_serp_sidebar_values, _build_sidebar_config_updates
from config.i18n import TRANSLATIONS


def _stub_results_streamlit(monkeypatch) -> None:
    monkeypatch.setattr(results.st, "subheader", lambda *args, **kwargs: None)
    monkeypatch.setattr(results.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(results.st, "info", lambda *args, **kwargs: None)
    monkeypatch.setattr(results.st, "expander", lambda *args, **kwargs: nullcontext())
    monkeypatch.setattr(
        results.st,
        "checkbox",
        lambda label, key=None, **kwargs: st.session_state.get(key, False),
    )


def test_grouped_keyword_selector_helper_keeps_source_specific_selections(monkeypatch):
    from components.results import _render_grouped_keyword_candidate_selector

    st.session_state.clear()
    _stub_results_streamlit(monkeypatch)

    candidates = [
        {"keyword": "alpha", "source_url": "https://source-a.example"},
        {"keyword": "alpha", "source_url": "https://source-b.example"},
    ]
    st.session_state["test::alpha::https://source-a.example"] = True
    st.session_state["test::alpha::https://source-b.example"] = False

    selected = _render_grouped_keyword_candidate_selector(
        candidates=candidates,
        selection_prefix="test",
        source_for_candidate=lambda candidate: str(candidate.get("source_url", "unknown") or "unknown"),
        expander_key_for_source=lambda source: f"test_expander::{source}",
        checkbox_key_for_candidate=lambda candidate: f"test::{candidate['keyword']}::{candidate['source_url']}",
        selected_value_for_candidate=lambda candidate: candidate["keyword"],
        title="Test",
    )

    assert selected == {
        "https://source-a.example": ["alpha"],
    }


def test_build_serp_sidebar_values_reuses_current_provider_and_serp_settings() -> None:
    current_serp_config = {"provider": "serpapi"}

    result = _build_serp_sidebar_values(
        current_serp_config=current_serp_config,
        serp_selected_provider=None,
        serp_num=17,
        serp_gl="ua",
        serp_hl="en",
        serp_device="desktop",
        serp_search_type="web",
        serp_time_period="any",
        serp_safe_search="off",
        serp_google_domain="google.com",
        serp_city="Kyiv",
        serp_uule="w+CAIQICI",
        serp_headless=False,
    )

    assert result == {
        "serp_provider": "serpapi",
        "serp_num_results": 17,
        "serp_gl": "ua",
        "serp_hl": "en",
        "serp_device": "desktop",
        "serp_search_type": "web",
        "serp_time_period": "any",
        "serp_safe_search": "off",
        "serp_google_domain": "google.com",
        "serp_city": "Kyiv",
        "serp_uule": "w+CAIQICI",
        "serp_headless": False,
    }


def test_build_serp_sidebar_values_persists_local_browser_headless_flag() -> None:
    result = _build_serp_sidebar_values(
        current_serp_config={"provider": "browser_cloakbrowser"},
        serp_selected_provider="Browser (Cloakbrowser/Playwright)",
        serp_num=10,
        serp_gl="ua",
        serp_hl="uk",
        serp_device="desktop",
        serp_search_type="web",
        serp_time_period="any",
        serp_safe_search="off",
        serp_google_domain="google.com.ua",
        serp_city="",
        serp_uule="",
        serp_headless=True,
    )

    assert result["serp_provider"] == "browser_cloakbrowser"
    assert result["serp_headless"] is True


def test_sidebar_config_updates_persist_local_headless_flags() -> None:
    updated = _build_sidebar_config_updates(
        {"llm": {"prompts": {}}},
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
            "serp_headless": True,
            "google_trends_headless": False,
        },
    )

    assert updated["serp"]["headless"] is True
    assert updated["google_trends"]["headless"] is False


def test_local_headless_i18n_keys_exist_for_all_locales() -> None:
    for key in ("serp_local_headless", "google_trends_local_headless"):
        assert key in TRANSLATIONS
        assert set(TRANSLATIONS[key]) >= {"ru", "uk", "en"}
        assert all(TRANSLATIONS[key][locale] for locale in ("ru", "uk", "en"))
