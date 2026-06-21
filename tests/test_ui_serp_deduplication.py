from contextlib import nullcontext

import streamlit as st

import components.results as results
from components.sidebar import _build_serp_sidebar_values


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
    }
