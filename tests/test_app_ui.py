from contextlib import nullcontext

import pytest
import streamlit as st

import app


class _DummyContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _TrackedForm:
    def __init__(self, state):
        self.state = state

    def __enter__(self):
        self.state["in_form"] = True
        return self

    def __exit__(self, exc_type, exc, tb):
        self.state["in_form"] = False
        return False


def test_workflow_mode_selector_is_rendered_outside_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    st.session_state.clear()
    app._ensure_session_defaults()
    tracker = {"in_form": False, "workflow_selectbox_in_form": None}

    monkeypatch.setattr("app.st.columns", lambda spec: (_DummyContext(), _DummyContext()))
    monkeypatch.setattr("app.st.form", lambda *args, **kwargs: _TrackedForm(tracker))
    monkeypatch.setattr("app.st.subheader", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.st.text_area", lambda *args, **kwargs: "")
    monkeypatch.setattr("app.st.file_uploader", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.st.checkbox", lambda *args, **kwargs: False)
    monkeypatch.setattr("app.st.code", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.st.form_submit_button", lambda *args, **kwargs: False)

    def _fake_selectbox(label, options, index=0, **kwargs):
        if label == app.t("workflow_mode_label"):
            tracker["workflow_selectbox_in_form"] = tracker["in_form"]
        return options[index]

    monkeypatch.setattr("app.st.selectbox", _fake_selectbox)

    app._render_input_form()

    assert tracker["workflow_selectbox_in_form"] is False


def test_sync_workflow_mode_updates_session_state_from_widget() -> None:
    st.session_state.clear()
    app._ensure_session_defaults()
    st.session_state["workflow_mode_widget"] = app.WORKFLOW_MODE_URL_SEED

    app._sync_workflow_mode_from_widget()

    assert st.session_state.workflow_mode == app.WORKFLOW_MODE_URL_SEED


def test_render_input_form_syncs_widget_state_with_programmatic_workflow_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    st.session_state.clear()
    app._ensure_session_defaults()
    st.session_state.workflow_mode = app.WORKFLOW_MODE_KEYWORD_SEED
    st.session_state["workflow_mode_widget"] = app.WORKFLOW_MODE_URL_LLM
    captured = {}

    monkeypatch.setattr("app.st.columns", lambda spec: (_DummyContext(), _DummyContext()))
    monkeypatch.setattr("app.st.form", lambda *args, **kwargs: _TrackedForm({}))
    monkeypatch.setattr("app.st.subheader", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.st.text_area", lambda *args, **kwargs: "")
    monkeypatch.setattr("app.st.file_uploader", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.st.checkbox", lambda *args, **kwargs: False)
    monkeypatch.setattr("app.st.code", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.st.form_submit_button", lambda *args, **kwargs: False)

    def _fake_selectbox(label, options, **kwargs):
        if label == app.t("workflow_mode_label"):
            captured["options"] = options
            captured["kwargs"] = kwargs
        return st.session_state["workflow_mode_widget"]

    monkeypatch.setattr("app.st.selectbox", _fake_selectbox)

    selected_mode, _, _, _ = app._render_input_form()

    assert captured["options"] == list(app.WORKFLOW_MODES)
    assert "index" not in captured["kwargs"]
    assert st.session_state["workflow_mode_widget"] == app.WORKFLOW_MODE_KEYWORD_SEED
    assert selected_mode == app.WORKFLOW_MODE_KEYWORD_SEED


def test_render_input_form_does_not_pass_index_when_widget_state_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    st.session_state.clear()
    app._ensure_session_defaults()
    st.session_state["workflow_mode_widget"] = app.WORKFLOW_MODE_URL_SEED
    captured = {}

    monkeypatch.setattr("app.st.columns", lambda spec: (_DummyContext(), _DummyContext()))
    monkeypatch.setattr("app.st.form", lambda *args, **kwargs: _TrackedForm({}))
    monkeypatch.setattr("app.st.subheader", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.st.text_area", lambda *args, **kwargs: "")
    monkeypatch.setattr("app.st.file_uploader", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.st.checkbox", lambda *args, **kwargs: False)
    monkeypatch.setattr("app.st.code", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.st.form_submit_button", lambda *args, **kwargs: False)

    def _fake_selectbox(label, options, **kwargs):
        if label == app.t("workflow_mode_label"):
            captured["kwargs"] = kwargs
        return st.session_state["workflow_mode_widget"]

    monkeypatch.setattr("app.st.selectbox", _fake_selectbox)

    app._render_input_form()

    assert "index" not in captured["kwargs"]


def test_main_ignores_immediate_duplicate_form_submission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    st.session_state.clear()
    calls = []

    monkeypatch.setattr(
        "app.render_sidebar",
        lambda: {
            "provider": "OpenAI",
            "model_name": "gpt-test",
            "max_keywords": 10,
            "location_id": "2840",
            "language_id": "1000",
            "currency_code": "USD",
            "auto_save_excel": False,
            "keyword_prompt": "",
            "seo_prompt": "",
            "api_timeout": 10,
            "api_delay": 2,
            "api_retry_count": 4,
            "api_retry_delay": 4,
            "upload_max_file_size_mb": 5,
            "upload_max_rows": 1000,
        },
    )
    monkeypatch.setattr(
        "app._render_input_form",
        lambda: (
            app.WORKFLOW_MODE_URL_LLM,
            "https://example.com\nhttps://example.org",
            None,
            True,
        ),
    )
    monkeypatch.setattr("app.run_startup_cleanup", lambda: {})
    monkeypatch.setattr("app.validate_api_keys", lambda: {"openai": True})
    monkeypatch.setattr("app.logger.close_handlers", lambda: None)
    monkeypatch.setattr("app.logger.refresh_config", lambda: None)
    monkeypatch.setattr("app.logger.info", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.st.title", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.st.markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.st.warning", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.st.error", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.st.button", lambda *args, **kwargs: False)
    monkeypatch.setattr("app.render_keyword_results", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.render_scraping_preview", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.render_keyword_selection", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "app.render_keyword_ideas_generation", lambda *args, **kwargs: None
    )
    monkeypatch.setattr("app.render_seo_generation", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.render_seo_results", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.render_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "app.run_llm_url_workflow",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    app.main()
    app.main()

    assert len(calls) == 1


def test_main_allows_same_submission_again_after_non_submit_rerun(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    st.session_state.clear()
    calls = []
    submissions = iter([True, False, True])

    monkeypatch.setattr(
        "app.render_sidebar",
        lambda: {
            "provider": "OpenAI",
            "model_name": "gpt-test",
            "max_keywords": 10,
            "location_id": "2840",
            "language_id": "1000",
            "currency_code": "USD",
            "auto_save_excel": False,
            "keyword_prompt": "",
            "seo_prompt": "",
            "api_timeout": 10,
            "api_delay": 2,
            "api_retry_count": 4,
            "api_retry_delay": 4,
            "upload_max_file_size_mb": 5,
            "upload_max_rows": 1000,
        },
    )
    monkeypatch.setattr(
        "app._render_input_form",
        lambda: (
            app.WORKFLOW_MODE_URL_LLM,
            "https://example.com",
            None,
            next(submissions),
        ),
    )
    monkeypatch.setattr("app.run_startup_cleanup", lambda: {})
    monkeypatch.setattr("app.validate_api_keys", lambda: {"openai": True})
    monkeypatch.setattr("app.logger.close_handlers", lambda: None)
    monkeypatch.setattr("app.logger.refresh_config", lambda: None)
    monkeypatch.setattr("app.logger.info", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.st.title", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.st.markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.st.warning", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.st.error", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.st.button", lambda *args, **kwargs: False)
    monkeypatch.setattr("app.render_keyword_results", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.render_scraping_preview", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.render_keyword_selection", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "app.render_keyword_ideas_generation", lambda *args, **kwargs: None
    )
    monkeypatch.setattr("app.render_seo_generation", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.render_seo_results", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.render_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "app.run_llm_url_workflow",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    app.main()
    app.main()
    app.main()

    assert len(calls) == 2
