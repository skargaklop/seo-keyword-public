# TDD tests restoring the "add your own keyword" capability in the
#          URL->LLM->Ads workflow's keyword candidate selector. Historically the
#          user could add manual keywords to the LLM-gathered set BEFORE SEO text
#          generation. The Stage-1 selector (render_keyword_candidate_selector_with_sources)
#          is what renders in URL_LLM mode, so the manual-add must live there.
#
#          The input is a multi-line TEXTAREA: the user may add one or several
#          keywords, one keyword per line. Each non-empty line becomes its own
#          candidate that flows into Ads / SEO generation like any other keyword.
# Reference: PLAN 08-01, requirements.xml#UC-001

from contextlib import nullcontext

import streamlit as st

import components.results as results
from utils.pipeline import SESSION_KEY_STAGED_KEYWORDS


# GRACE: function _mock_streamlit_for_selector declaration.
def _mock_streamlit_for_selector(monkeypatch, captured: dict):
    st.session_state.setdefault("current_run_id", "run-test")

    monkeypatch.setattr(results.st, "subheader", lambda *a, **k: None)
    monkeypatch.setattr(results.st, "divider", lambda *a, **k: None)
    monkeypatch.setattr(results.st, "write", lambda *a, **k: None)
    monkeypatch.setattr(results.st, "info", lambda *a, **k: None)
    monkeypatch.setattr(results.st, "warning", lambda *a, **k: None)
    monkeypatch.setattr(results.st, "expander", lambda *a, **k: nullcontext())

    def _checkbox(label, key=None, **kwargs):
        return st.session_state.get(key, False)

    def _text_input(label, key=None, **kwargs):
        captured.setdefault("text_input_keys", []).append(key)
        return st.session_state.get(key, "")

    def _text_area(label, key=None, **kwargs):
        captured.setdefault("text_area_keys", []).append(key)
        return st.session_state.get(key, "")

    # GRACE: function _selectbox declaration.
    def _selectbox(label, options, key=None, **kwargs):
        captured.setdefault("selectbox_keys", []).append(key)
        captured.setdefault("selectbox_options", []).append(options)
        idx = 0
        if options:
            idx = min(0, len(options) - 1)
        return options[idx] if options else ""

    # GRACE: function _button declaration.
    def _button(label, key=None, **kwargs):
        captured.setdefault("button_keys", []).append(key)
        clicked = st.session_state.get(key, False)
        # Faithful Streamlit emulation: when a button with on_click is "clicked",
        # Streamlit fires the callback at the start of the NEXT run, before any
        # widget is re-instantiated. That ordering is what makes it legal to
        # mutate widget session-state keys inside the callback. Replicate it here
        # so the mock enforces the same constraint real Streamlit does.
        if clicked:
            on_click = kwargs.get("on_click")
            if callable(on_click):
                on_click()
        return clicked

    monkeypatch.setattr(results.st, "checkbox", _checkbox)
    monkeypatch.setattr(results.st, "text_input", _text_input)
    monkeypatch.setattr(results.st, "text_area", _text_area)
    monkeypatch.setattr(results.st, "selectbox", _selectbox)
    monkeypatch.setattr(results.st, "button", _button)
    monkeypatch.setattr(results.st, "rerun", lambda *a, **k: None)


# GRACE: class TestManualKeywordInCandidateSelector declaration.
class TestManualKeywordInCandidateSelector:

    # GRACE: function test_selector_renders_manual_keyword_textarea declaration.
    def test_selector_renders_manual_keyword_textarea(self, monkeypatch):
        st.session_state.clear()
        captured: dict = {}
        _mock_streamlit_for_selector(monkeypatch, captured)

        candidates = [
            {"keyword": "buy coffee", "source_url": "https://example.com"},
            {"keyword": "coffee beans", "source_url": "https://example.com"},
        ]

        results.render_keyword_candidate_selector_with_sources(
            candidates,
            selection_prefix="llm_extract_run-test",
            title="Select keywords",
        )

        # A text_area for manual keyword entry must have been rendered.
        assert any(
            "manual" in str(k).lower() for k in captured.get("text_area_keys", [])
        ), (
            f"Expected a manual-keyword text_area in the candidate selector, "
            f"got text_area keys: {captured.get('text_area_keys')}"
        )

    # GRACE: function test_single_keyword_added_and_selected_when_button_clicked declaration.
    def test_single_keyword_added_and_selected_when_button_clicked(self, monkeypatch):
        st.session_state.clear()
        captured: dict = {}
        _mock_streamlit_for_selector(monkeypatch, captured)

        source_url = "https://example.com"
        # Pre-select one LLM candidate
        from utils.pipeline import make_selection_key

        st.session_state[
            make_selection_key("buy coffee", source_url, "llm_extract_run-test")
        ] = True

        # Simulate the user typing a single manual keyword
        st.session_state["manual_keyword_input_llm_extract_run-test"] = "best espresso machine"
        # And choosing the source URL
        st.session_state["manual_kw_url_llm_extract_run-test"] = source_url
        # And clicking Add
        st.session_state["add_manual_kw_llm_extract_run-test"] = True

        selected = results.render_keyword_candidate_selector_with_sources(
            [{"keyword": "buy coffee", "source_url": source_url}],
            selection_prefix="llm_extract_run-test",
            title="Select keywords",
        )

        assert selected is not None, "Expected non-None selection after adding manual keyword"
        keywords = [kw for kw, _ in selected]
        assert "best espresso machine" in keywords, (
            f"Manual keyword not in selected set: {keywords}"
        )
        assert "buy coffee" in keywords

    # GRACE: function test_multiple_keywords_one_per_line_added_and_selected declaration.
    def test_multiple_keywords_one_per_line_added_and_selected(self, monkeypatch):
        st.session_state.clear()
        captured: dict = {}
        _mock_streamlit_for_selector(monkeypatch, captured)

        source_url = "https://example.com"
        # User pastes THREE keywords, one per line, into the textarea.
        st.session_state["manual_keyword_input_llm_extract_run-test"] = (
            "best espresso machine\nbuy coffee grinder\norganic coffee beans"
        )
        st.session_state["manual_kw_url_llm_extract_run-test"] = source_url
        st.session_state["add_manual_kw_llm_extract_run-test"] = True

        selected = results.render_keyword_candidate_selector_with_sources(
            [{"keyword": "llm kw", "source_url": source_url}],
            selection_prefix="llm_extract_run-test",
            title="Select keywords",
        )

        assert selected is not None, "Expected non-None selection after adding keywords"
        keywords = [kw for kw, _ in selected]
        for expected in (
            "best espresso machine",
            "buy coffee grinder",
            "organic coffee beans",
        ):
            assert expected in keywords, (
                f"Manual keyword '{expected}' not in selected set: {keywords}"
            )

    # GRACE: function test_multiple_keywords_persist_in_staged_candidates declaration.
    def test_multiple_keywords_persist_in_staged_candidates(self, monkeypatch):
        st.session_state.clear()
        captured: dict = {}
        _mock_streamlit_for_selector(monkeypatch, captured)

        source_url = "https://example.com"
        st.session_state["manual_keyword_input_llm_extract_run-test"] = (
            "manual kw one\nmanual kw two\nmanual kw three"
        )
        st.session_state["manual_kw_url_llm_extract_run-test"] = source_url
        st.session_state["add_manual_kw_llm_extract_run-test"] = True

        results.render_keyword_candidate_selector_with_sources(
            [{"keyword": "llm kw", "source_url": source_url}],
            selection_prefix="llm_extract_run-test",
            title="Select keywords",
        )

        staged = st.session_state.get(SESSION_KEY_STAGED_KEYWORDS) or []
        staged_kws = [c.get("keyword") if isinstance(c, dict) else getattr(c, "keyword", None) for c in staged]
        for expected in ("manual kw one", "manual kw two", "manual kw three"):
            assert expected in staged_kws, (
                f"Manual keyword '{expected}' must persist in staged candidates, got: {staged_kws}"
            )

    # GRACE: function test_blank_lines_in_textarea_are_ignored declaration.
    def test_blank_lines_in_textarea_are_ignored(self, monkeypatch):
        st.session_state.clear()
        captured: dict = {}
        _mock_streamlit_for_selector(monkeypatch, captured)

        source_url = "https://example.com"
        # Two real keywords separated by blank and whitespace-only lines.
        st.session_state["manual_keyword_input_llm_extract_run-test"] = (
            "real keyword a\n\n   \nreal keyword b"
        )
        st.session_state["manual_kw_url_llm_extract_run-test"] = source_url
        st.session_state["add_manual_kw_llm_extract_run-test"] = True

        selected = results.render_keyword_candidate_selector_with_sources(
            [{"keyword": "llm kw", "source_url": source_url}],
            selection_prefix="llm_extract_run-test",
            title="Select keywords",
        )

        assert selected is not None
        keywords = [kw for kw, _ in selected]
        assert "real keyword a" in keywords
        assert "real keyword b" in keywords
        # No empty/whitespace keywords should leak through.
        assert all(kw.strip() for kw in keywords), (
            f"Blank lines produced empty keywords: {keywords}"
        )
    # GRACE: function _checkbox declaration
    # GRACE: function _text_input declaration
    # GRACE: function _text_area declaration
    # GRACE: The pre-selected LLM candidate must still be present
