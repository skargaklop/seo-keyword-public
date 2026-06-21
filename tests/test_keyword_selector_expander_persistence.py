"""Tests for keyword-grouping expander state persistence (TDD).

Bug: keyword-grouping ``st.expander`` blocks used ``st.expander(label, expanded=False)``
without an explicit ``key=``. An expander without a stable key gets an auto-generated
positional key, so the first checkbox interaction (a cold Streamlit rerun) could shift
the widget tree, change the expander's auto-key, and reset it to ``expanded=False`` —
"the block collapses on the first check." Fix: every grouping expander must carry an
explicit, stable ``key=`` so its identity (and open/closed state) survives reruns.

Verification approach: spy on ``st.expander`` calls and assert each one is invoked with
a ``key=`` kwarg. (We do NOT rely on AppTest's ``Expander.key`` attribute — in stock
Streamlit 1.58 that property returns None for blocks, so asserting on the call args is
the stable, dependency-free contract.)
"""

from unittest.mock import patch


# GRACE: function _collect_expander_keys declaration.
def _collect_expander_keys(run_render):
    seen = []
    real_expander = None

    # GRACE: function _spy declaration.
    def _spy(*args, **kwargs):
        seen.append(kwargs.get("key"))
        return real_expander(*args, **kwargs)

    import streamlit as st
    real_expander = st.expander
    with patch("streamlit.expander", _spy):
        run_render()
    return seen


def test_keyword_candidate_selector_expander_has_stable_key():
    def render():
        import streamlit as st
        st.session_state["kw_candidates_test_prefix"] = [
            {"keyword": "nike", "source_url": "https://example.com",
             "source_stage": "https://example.com", "source_type": "ads_keyword_ideas",
             "selection_prefix": "test_prefix"},
            {"keyword": "shoes", "source_url": "https://example.com",
             "source_stage": "https://example.com", "source_type": "ads_keyword_ideas",
             "selection_prefix": "test_prefix"},
        ]
        from components.results import render_keyword_candidate_selector
        render_keyword_candidate_selector("kw_candidates_test_prefix", "test_prefix", "Test")

    keys = _collect_expander_keys(render)
    assert keys, "expected at least one grouping expander to be rendered"
    for k in keys:
        assert k, (
            "Grouping expander was rendered without an explicit key; its expanded state "
            "cannot survive a cold rerun, causing the 'first checkbox collapses the block' bug."
        )


def test_keyword_candidate_selector_with_sources_expander_has_stable_key():
    def render():
        candidates = [
            {"keyword": "nike", "source_url": "https://example.com"},
            {"keyword": "shoes", "source_url": "https://example.com"},
        ]
        from components.results import render_keyword_candidate_selector_with_sources
        render_keyword_candidate_selector_with_sources(candidates, "ws_prefix", "Test")

    keys = _collect_expander_keys(render)
    assert keys, "expected at least one grouping expander to be rendered"
    for k in keys:
        assert k, (
            "Grouping expander was rendered without an explicit key; expanded state "
            "cannot survive a cold rerun (first-checkbox-collapse bug)."
        )


def test_keyword_results_url_grouped_expanders_have_stable_keys():
    def render():
        import pandas as pd
        import streamlit as st
        st.session_state.workflow_mode = "keyword_seed"
        st.session_state.processed_data = pd.DataFrame([
            {"Keyword": "nike", "Source URL": "https://a.com",
             "Avg Monthly Searches": 10, "Competition": "LOW", "Competition Index": 0,
             "Low CPC": 0.1, "High CPC": 0.2, "CPC Currency": "USD", "Months With Data": 12},
            {"Keyword": "potato", "Source URL": "https://b.com",
             "Avg Monthly Searches": 20, "Competition": "LOW", "Competition Index": 0,
             "Low CPC": 0.1, "High CPC": 0.2, "CPC Currency": "USD", "Months With Data": 12},
        ])
        st.session_state.keywords_excel_saved = False
        from components.results import render_keyword_results
        render_keyword_results(False)

    keys = _collect_expander_keys(render)
    assert keys, "expected at least one grouping expander in render_keyword_results"
    for k in keys:
        assert k, (
            "URL-grouped expander rendered without an explicit key; expanded state "
            "cannot survive a cold rerun (first-checkbox-collapse bug)."
        )
# GRACE: Purpose: every source-grouping expander in render_keyword_candidate_selector must carry an explicit, stable key so its expanded state survives reruns (fix for the "first checkbox check collapses the block" bug)
# GRACE: Purpose: source-grouping expanders in the _with_sources selector must likewise carry an explicit stable key
# GRACE: Purpose: render_keyword_results (via its chained render path) must give its grouping expanders explicit stable keys
