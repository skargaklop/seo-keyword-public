# Test coverage for modules: MOD-001,MOD-002,MOD-003,MOD-004,MOD-005
# MODULE_CONTRACT: tests/test_app_ui
# Purpose: Verify Streamlit app routing, session-state behavior, and UI configuration flows.
# Rationale: Links app UI tests to GRACE app, results, and sidebar modules.
# Dependencies: pandas, pytest, streamlit, app.
# Exports: pytest tests.
# LINKS: knowledge-graph.xml#MOD-001, knowledge-graph.xml#MOD-007, knowledge-graph.xml#MOD-011
# MODULE_MAP: tests/test_app_ui.py
# Public Functions: pytest test functions.
# Private Helpers: _DummyContext, _TrackedForm, local monkeypatch helpers.
# Key Semantic Blocks: none.
# Critical Flows: patch Streamlit widgets -> call app entrypoints -> assert routing/session effects.
# Verification: verification-plan.xml#V-MOD-001, verification-plan.xml#V-10-RESULTS-UI, verification-plan.xml#V-12-SUFFIX-REMOVAL
# CHANGE_SUMMARY: Added GRACE module contract linking this test file to MOD-001, MOD-007, and MOD-011.

import pandas as pd
import pytest
import streamlit as st
from types import SimpleNamespace

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
        "app.render_keyword_candidate_selector_with_sources",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.run_llm_url_keyword_extraction_tupled",
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
        "app.render_keyword_candidate_selector_with_sources",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.run_llm_url_keyword_extraction_tupled",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    app.main()
    app.main()
    app.main()

    assert len(calls) == 2


def test_main_routes_google_trends_mode_to_trends_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    st.session_state.clear()
    captured = {}

    trends_settings = {
        "default_geo": "US",
        "default_timeframe": "today 3-m",
    }
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
            "google_trends_settings": trends_settings,
            "cache_force_refresh": True,
        },
    )
    monkeypatch.setattr(
        "app._render_input_form",
        lambda: (
            app.WORKFLOW_MODE_TRENDS,
            "alpha keyword\nhttps://example.com/page",
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
    monkeypatch.setattr("app.render_google_trends_results", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.render_chained_serp_results", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.render_history", lambda *args, **kwargs: None)

    def _capture_trends_workflow(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr("app.run_google_trends_workflow", _capture_trends_workflow)

    app.main()

    assert captured["kwargs"]["keywords"] == [
        "alpha keyword",
        "https://example.com/page",
    ]
    assert captured["kwargs"]["trends_config"] is trends_settings
    assert captured["kwargs"]["force_refresh"] is True
    assert st.session_state.workflow_mode == app.WORKFLOW_MODE_TRENDS


def test_sidebar_trends_settings_do_not_include_enabled_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from components.sidebar import render_sidebar
    from utils.google_trends_client import GoogleTrendsProviderCapabilities

    st.session_state.clear()
    st.session_state.ui_lang = "en"
    checkbox_labels: list[str] = []

    monkeypatch.setattr("components.sidebar.st.subheader", lambda *a, **kw: None)
    monkeypatch.setattr(
        "components.sidebar.st.checkbox",
        lambda label, *a, **kw: checkbox_labels.append(label) or True,
    )
    monkeypatch.setattr("components.sidebar.st.text_input", lambda *a, **kw: "UA")
    monkeypatch.setattr("components.sidebar.st.number_input", lambda *a, **kw: 24)
    monkeypatch.setattr("components.sidebar.st.select_slider", lambda *a, **kw: None)
    monkeypatch.setattr("components.sidebar.st.divider", lambda *a, **kw: None)
    monkeypatch.setattr("components.sidebar.st.warning", lambda *a, **kw: None)
    monkeypatch.setattr("components.sidebar.st.info", lambda *a, **kw: None)
    monkeypatch.setattr(
        "components.sidebar.get_available_serp_providers",
        lambda: {"Serper.dev": "serper_dev"},
    )
    monkeypatch.setattr("components.sidebar.st.expander", lambda *a, **kw: type("_Ctx", (), {"__enter__": lambda s: s, "__exit__": lambda s, *a: False})())

    class _AvailableAdapter:
        provider_name = "fake_trends_available"
        capabilities = GoogleTrendsProviderCapabilities(
            provider="fake_trends_available",
            supports_time_series=True,
            supports_related_queries=True,
            supports_related_topics=True,
            supports_geo_breakdown=True,
            supports_trending_now=False,
            supports_autocomplete=False,
            supports_topic_ids=False,
            supports_historical_depth="years",
            max_keywords_per_request=5,
            cache_ttl_seconds=3600,
            notes=[],
        )

        def is_available(self) -> bool:
            return True

        def get_trends(self, request):
            return None

    monkeypatch.setattr(
        "utils.google_trends_client.TRENDS_PROVIDER_REGISTRY",
        {"fake_trends_available": _AvailableAdapter()},
    )
    monkeypatch.setattr(
        "utils.google_trends_client.TRENDS_PROVIDER_OPTIONS",
        ["fake_trends_available"],
    )
    monkeypatch.setattr(
        "components.sidebar.st.selectbox",
        lambda label, options, **kwargs: options[0] if options else None,
    )

    config = render_sidebar()

    assert "Enable Google Trends" not in checkbox_labels
    assert "google_trends_enabled" not in config["google_trends_settings"]


def test_render_serp_math_report_shows_full_profile_without_fixed_truncation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from components import results

    st.session_state.clear()

    ngrams = [
        SimpleNamespace(ngram=f"ngram-{i}", raw_count=i + 1, doc_frequency=i + 2)
        for i in range(20)
    ]
    tfidf_terms = [
        SimpleNamespace(term=f"tfidf-{i}", tfidf=i / 10, doc_frequency=i + 3)
        for i in range(20)
    ]
    cooccurrence_terms = [
        SimpleNamespace(
            term=f"cooccur-{i}",
            cooccurrence_count=i + 4,
            jaccard_similarity=0.01 * i,
            context_terms=[],
        )
        for i in range(20)
    ]
    intent = SimpleNamespace(
        intent_type="commercial",
        score=3.2,
        confidence=0.84,
        signals=["buy", "price"],
    )

    monkeypatch.setattr(
        "components.results.build_reverse_math_report",
        lambda *args, **kwargs: {
            "serp_profile": {
                "enabled": True,
                "info_message": "",
                "has_partial_data": False,
                "ngrams_by_size": {1: ngrams},
                "tfidf_terms": tfidf_terms,
                "cooccurrence_terms": cooccurrence_terms,
                "intent": intent,
                "related_searches": ["related-1", "related-2"],
                "people_also_ask": ["paa-1", "paa-2"],
            },
            "ads_enrichment": [],
            "overlap_keywords": [],
            "ads_only_keywords": [],
            "serp_only_terms": [],
        },
    )

    section = {"name": None, "count": 0}
    rendered_ngram_terms: list[str] = []
    rendered_tfidf_terms: list[str] = []
    rendered_cooccurrence_terms: list[str] = []

    class _DummyContext:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("components.results.st.divider", lambda *args, **kwargs: None)

    def _subheader(label, *args, **kwargs):
        section["count"] += 1
        if section["count"] == 1:
            section["name"] = "ngrams"
        elif section["count"] == 2:
            section["name"] = "tfidf"
        elif section["count"] == 3:
            section["name"] = "cooccurrence"
        else:
            section["name"] = None

    monkeypatch.setattr("components.results.st.subheader", _subheader)
    monkeypatch.setattr("components.results.st.info", lambda *args, **kwargs: None)
    monkeypatch.setattr("components.results.st.warning", lambda *args, **kwargs: None)
    monkeypatch.setattr("components.results.st.success", lambda *args, **kwargs: None)
    monkeypatch.setattr("components.results.st.dataframe", lambda *args, **kwargs: None)
    monkeypatch.setattr("components.results.st.caption", lambda *args, **kwargs: None)
    monkeypatch.setattr("components.results.st.tabs", lambda labels: [_DummyContext() for _ in labels])
    monkeypatch.setattr("components.results.st.columns", lambda spec: [_DummyContext() for _ in (spec if isinstance(spec, (list, tuple)) else range(spec))])
    monkeypatch.setattr("components.results.st.expander", lambda *args, **kwargs: _DummyContext())
    monkeypatch.setattr("components.results.st.button", lambda *args, **kwargs: False)
    monkeypatch.setattr("components.results.st.download_button", lambda *args, **kwargs: None)

    def _write(value, *args, **kwargs):
        if section["name"] == "ngrams" and isinstance(value, str) and value.startswith("**"):
            rendered_ngram_terms.append(value)
        elif section["name"] == "cooccurrence" and isinstance(value, str) and value.startswith("**"):
            rendered_cooccurrence_terms.append(value)

    def _checkbox(label, *args, **kwargs):
        if section["name"] == "tfidf":
            rendered_tfidf_terms.append(label)
        return False

    monkeypatch.setattr("components.results.st.write", _write)
    monkeypatch.setattr("components.results.st.checkbox", _checkbox)
    monkeypatch.setattr("components.results.st.metric", lambda *args, **kwargs: None)

    results.render_serp_math_report()

    assert len(rendered_ngram_terms) == 20
    assert len(rendered_tfidf_terms) == 20
    assert len(rendered_cooccurrence_terms) == 20


def test_math_analysis_export_sheets_include_bm25f_scores() -> None:
    from components import results

    st.session_state.clear()

    sheets = results._build_math_analysis_export_sheets(
        {
            "bm25f_scores": [
                SimpleNamespace(
                    doc_id=7,
                    doc_text="alpha keyword title",
                    score=1.23456,
                    query_coverage=0.5,
                    field_contributions={"title": 1.2, "snippet": 0.03456},
                    matched_terms=["alpha", "keyword"],
                )
            ]
        }
    )

    bm25f_df = sheets["BM25F Scores"]
    assert list(bm25f_df.columns) == [
        "Doc ID",
        "Text",
        "Score",
        "Coverage",
        "Field Contributions",
        "Matched Terms",
    ]
    assert bm25f_df.iloc[0]["Doc ID"] == 7
    assert bm25f_df.iloc[0]["Score"] == 1.2346
    assert bm25f_df.iloc[0]["Coverage"] == 0.5
    assert "title: 1.2000" in bm25f_df.iloc[0]["Field Contributions"]
    assert bm25f_df.iloc[0]["Matched Terms"] == "alpha, keyword"


def test_render_bm25f_scores_section_uses_localized_ui_labels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from components import results

    st.session_state.clear()
    st.session_state.ui_lang = "uk"
    captured = {"headers": [], "frames": []}
    profile = {
        "bm25f_scores": [
            SimpleNamespace(
                doc_id=7,
                doc_text="alpha keyword title",
                score=1.23456,
                query_coverage=0.5,
                field_contributions={"title": 1.2},
                matched_terms=["alpha", "keyword"],
            )
        ]
    }

    monkeypatch.setattr(
        "components.results.st.subheader",
        lambda label, *args, **kwargs: captured["headers"].append(label),
    )
    monkeypatch.setattr(
        "components.results.st.dataframe",
        lambda df, *args, **kwargs: captured["frames"].append(df.copy()),
    )

    results._render_bm25f_scores_section(profile)
    results._render_bm25f_scores_section(
        profile,
        header_key="crawl_bm25f_scores_header",
    )

    assert captured["headers"] == [
        "Оцінки BM25F",
        "Оцінки BM25F для краулінгу",
    ]
    assert list(captured["frames"][0].columns) == [
        "ID документа",
        "Текст",
        "Оцінка",
        "Покриття",
        "Внесок полів",
        "Збіги термінів",
    ]


def test_render_google_trends_results_shows_provider_and_confidence_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from components import results

    st.session_state.clear()
    st.session_state.ui_lang = "en"
    st.session_state.google_trends_result = SimpleNamespace(
        provider="google_trends_alpha",
        data_confidence="degraded",
        warnings=["batch warning"],
        integrity_warnings=["soft_block"],
        provider_metadata={"provider": "google_trends_alpha", "mode": "official"},
        cache_metadata={"cache_hit": True, "cache_key": "abc123"},
    )
    st.session_state.google_trends_tables = None

    tables = {
        "averages": pd.DataFrame({"Keyword": ["alpha"], "Average Interest": [75]}),
        "interest": pd.DataFrame({"Time": ["2025-01-01"], "alpha": [50]}),
        "related": pd.DataFrame(),
        "regions": pd.DataFrame(),
    }
    monkeypatch.setattr(
        "components.results.google_trends_result_to_tables",
        lambda *args, **kwargs: tables,
    )
    monkeypatch.setattr(
        "components.results.ExcelExporter.export_multi_sheet_to_buffer",
        lambda *args, **kwargs: True,
    )

    metric_calls = []
    warnings = []
    infos = []
    download_labels = []

    class _DummyContext:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("components.results.st.divider", lambda *args, **kwargs: None)
    monkeypatch.setattr("components.results.st.subheader", lambda *args, **kwargs: None)
    monkeypatch.setattr("components.results.st.dataframe", lambda *args, **kwargs: None)
    monkeypatch.setattr("components.results.st.caption", lambda *args, **kwargs: None)
    monkeypatch.setattr("components.results.st.warning", lambda message, *args, **kwargs: warnings.append(message))
    monkeypatch.setattr("components.results.st.info", lambda message, *args, **kwargs: infos.append(message))
    monkeypatch.setattr("components.results.st.metric", lambda label, value, *args, **kwargs: metric_calls.append((label, value)))
    monkeypatch.setattr("components.results.st.json", lambda *args, **kwargs: None)
    monkeypatch.setattr("components.results.st.download_button", lambda label, *args, **kwargs: download_labels.append(label))
    monkeypatch.setattr("components.results.st.expander", lambda *args, **kwargs: _DummyContext())
    monkeypatch.setattr("components.results.st.columns", lambda spec: [_DummyContext() for _ in range(spec if isinstance(spec, int) else len(spec))])

    results.render_google_trends_results(
        auto_save_excel=False,
        location_id="2840",
        language_id="1000",
        currency_code="USD",
    )

    assert any(label == "Provider" and value == "google_trends_alpha" for label, value in metric_calls)
    assert any(label == "Data confidence" and value == "degraded" for label, value in metric_calls)
    assert "Google Trends returned degraded or partial data." in warnings
    assert "batch warning" in infos
    assert "Export Math Analysis" in download_labels


# ---------------------------------------------------------------------------
# PLAN 15-01: Export parity and SERP count stability tests
# ---------------------------------------------------------------------------


def test_render_serp_domain_metrics_exposes_both_xlsx_and_csv_download(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from components import results
    from dataclasses import dataclass

    st.session_state.clear()
    st.session_state.ui_lang = "en"

    @dataclass
    class _FakeDomainMetrics:
        domain: str
        avg_position: float
        keyword_serp_count: int
        total_keyword_serps: int
        result_count: int
        total_results: int
        domain_mentioned: int = 0
        domain_visibility: float = 0.0

    st.session_state.serp_domain_metrics = [
        _FakeDomainMetrics("a.com", 2.5, 3, 5, 10, 20),
        _FakeDomainMetrics("b.com", 4.0, 2, 5, 8, 20),
    ]

    download_labels: list[str] = []

    monkeypatch.setattr("components.results.st.subheader", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.dataframe", lambda *a, **kw: None)
    monkeypatch.setattr(
        "components.results.st.download_button",
        lambda label, *a, **kw: download_labels.append(label) or None,
    )

    results.render_serp_domain_metrics()

    has_xlsx = any("Excel" in lbl or "XLSX" in lbl.upper() for lbl in download_labels)
    has_csv = any("CSV" in lbl.upper() for lbl in download_labels)
    assert has_xlsx, f"Expected XLSX download button, got: {download_labels}"
    assert has_csv, f"Expected CSV download button, got: {download_labels}"


def test_render_trends_results_exposes_both_xlsx_and_csv_download(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from components import results

    st.session_state.clear()
    st.session_state.ui_lang = "en"
    st.session_state.google_trends_result = SimpleNamespace(
        provider="google_trends_alpha",
        data_confidence="high",
        warnings=[],
        integrity_warnings=[],
        provider_metadata={"provider": "google_trends_alpha", "mode": "official"},
        cache_metadata={"cache_hit": False, "cache_key": ""},
    )
    st.session_state.google_trends_tables = {
        "averages": pd.DataFrame({"Keyword": ["alpha"], "Average Interest": [75]}),
        "interest": pd.DataFrame(),
        "related": pd.DataFrame(),
        "regions": pd.DataFrame(),
    }

    download_labels: list[str] = []

    class _DummyCtx:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    monkeypatch.setattr("components.results.st.divider", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.subheader", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.dataframe", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.caption", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.warning", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.info", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.json", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.metric", lambda *a, **kw: None)
    monkeypatch.setattr(
        "components.results.st.download_button",
        lambda label, *a, **kw: download_labels.append(label) or None,
    )
    monkeypatch.setattr("components.results.st.expander", lambda *a, **kw: _DummyCtx())
    monkeypatch.setattr(
        "components.results.st.columns",
        lambda spec: [_DummyCtx() for _ in (spec if isinstance(spec, (list, tuple)) else range(spec))],
    )
    monkeypatch.setattr(
        "components.results.google_trends_result_to_tables",
        lambda *a, **kw: st.session_state.google_trends_tables,
    )
    monkeypatch.setattr(
        "components.results.ExcelExporter.export_multi_sheet_to_buffer",
        lambda *a, **kw: True,
    )

    results.render_google_trends_results(
        auto_save_excel=False,
        location_id="2840",
        language_id="1000",
        currency_code="USD",
    )

    has_xlsx = any("Excel" in lbl or "XLSX" in lbl.upper() for lbl in download_labels)
    has_csv = any("CSV" in lbl.upper() for lbl in download_labels)
    assert has_xlsx, f"Expected XLSX download button, got: {download_labels}"
    assert has_csv, f"Expected CSV download button, got: {download_labels}"


def test_serp_domain_counts_are_derived_from_parsed_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from components import results
    from dataclasses import dataclass

    st.session_state.clear()
    st.session_state.ui_lang = "en"

    @dataclass
    class _FakeDomainMetrics:
        domain: str
        avg_position: float
        keyword_serp_count: int
        total_keyword_serps: int
        result_count: int
        total_results: int
        domain_mentioned: int = 0
        domain_visibility: float = 0.0

    st.session_state.serp_domain_metrics = [
        _FakeDomainMetrics("a.com", 2.5, 3, 5, 10, 20),
        _FakeDomainMetrics("b.com", 4.0, 2, 5, 8, 20),
    ]

    dataframe_calls: list[pd.DataFrame] = []

    monkeypatch.setattr("components.results.st.subheader", lambda *a, **kw: None)
    monkeypatch.setattr(
        "components.results.st.dataframe",
        lambda df, *a, **kw: dataframe_calls.append(df),
    )
    monkeypatch.setattr("components.results.st.download_button", lambda *a, **kw: None)

    results.render_serp_domain_metrics()

    assert len(dataframe_calls) >= 1, "Expected at least one dataframe call"
    df = dataframe_calls[0]
    # Column names are now i18n-localized
    result_freq_col = results.t("serp_domain_result_frequency")
    assert result_freq_col in df.columns, f"Expected '{result_freq_col}' column, got {list(df.columns)}"
    assert len(df) == 2, f"Expected 2 domain rows, got {len(df)}"


# ---------------------------------------------------------------------------
# PLAN 15-02: Sidebar Trends provider/option UI tests
# ---------------------------------------------------------------------------


def test_sidebar_trends_provider_selectbox_is_rendered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from components.sidebar import render_sidebar

    st.session_state.clear()
    st.session_state.ui_lang = "en"
    selectbox_labels: list[str] = []

    monkeypatch.setattr("components.sidebar.st.subheader", lambda *a, **kw: None)
    monkeypatch.setattr("components.sidebar.st.checkbox", lambda *a, **kw: True)
    monkeypatch.setattr("components.sidebar.st.text_input", lambda *a, **kw: "UA")
    monkeypatch.setattr("components.sidebar.st.number_input", lambda *a, **kw: 24)
    monkeypatch.setattr("components.sidebar.st.select_slider", lambda *a, **kw: None)
    monkeypatch.setattr("components.sidebar.st.divider", lambda *a, **kw: None)

    def _fake_selectbox(label, options, **kwargs):
        selectbox_labels.append(label)
        return options[0] if options else None

    monkeypatch.setattr("components.sidebar.st.selectbox", _fake_selectbox)
    monkeypatch.setattr("components.sidebar.st.expander", lambda *a, **kw: type("_Ctx", (), {"__enter__": lambda s: s, "__exit__": lambda s, *a: False})())

    render_sidebar()

    provider_labels = [label for label in selectbox_labels if "provider" in label.lower() or "trends" in label.lower()]
    assert len(provider_labels) >= 1, f"Expected at least one Trends provider selectbox, got labels: {selectbox_labels}"


def test_sidebar_trends_request_options_are_rendered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from components.sidebar import render_sidebar

    st.session_state.clear()
    st.session_state.ui_lang = "en"
    selectbox_labels: list[str] = []
    selectbox_values: dict = {}

    monkeypatch.setattr("components.sidebar.st.subheader", lambda *a, **kw: None)
    monkeypatch.setattr("components.sidebar.st.checkbox", lambda *a, **kw: True)
    monkeypatch.setattr("components.sidebar.st.text_input", lambda label, *a, **kw: selectbox_values.get(label, "UA"))
    monkeypatch.setattr("components.sidebar.st.number_input", lambda *a, **kw: 24)
    monkeypatch.setattr("components.sidebar.st.select_slider", lambda *a, **kw: None)
    monkeypatch.setattr("components.sidebar.st.divider", lambda *a, **kw: None)

    def _fake_selectbox(label, options, **kwargs):
        selectbox_labels.append(label)
        return options[0] if options else None

    monkeypatch.setattr("components.sidebar.st.selectbox", _fake_selectbox)
    monkeypatch.setattr("components.sidebar.st.expander", lambda *a, **kw: type("_Ctx", (), {"__enter__": lambda s: s, "__exit__": lambda s, *a: False})())

    render_sidebar()

    option_labels = [label for label in selectbox_labels if any(kw in label.lower() for kw in ["timeframe", "category", "property"])]
    assert len(option_labels) >= 1, f"Expected at least one request option selectbox, got labels: {selectbox_labels}"


def test_sidebar_hides_unavailable_trends_providers_and_omits_status_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from components.sidebar import render_sidebar
    from utils.google_trends_client import GoogleTrendsProviderCapabilities

    st.session_state.clear()
    st.session_state.ui_lang = "en"
    info_calls: list[str] = []
    selectbox_calls: list[tuple[str, list[str]]] = []

    monkeypatch.setattr("components.sidebar.st.subheader", lambda *a, **kw: None)
    monkeypatch.setattr("components.sidebar.st.checkbox", lambda *a, **kw: True)
    monkeypatch.setattr("components.sidebar.st.text_input", lambda *a, **kw: "UA")
    monkeypatch.setattr("components.sidebar.st.number_input", lambda *a, **kw: 24)
    monkeypatch.setattr("components.sidebar.st.select_slider", lambda *a, **kw: None)
    monkeypatch.setattr("components.sidebar.st.divider", lambda *a, **kw: None)
    monkeypatch.setattr("components.sidebar.st.info", lambda msg, *a, **kw: info_calls.append(msg))
    monkeypatch.setattr("components.sidebar.st.warning", lambda *a, **kw: None)
    monkeypatch.setattr(
        "components.sidebar.get_available_serp_providers",
        lambda: {"Serper.dev": "serper_dev"},
    )
    monkeypatch.setattr("components.sidebar.st.expander", lambda *a, **kw: type("_Ctx", (), {"__enter__": lambda s: s, "__exit__": lambda s, *a: False})())

    class _UnavailableAdapter:
        provider_name = "fake_trends_unavailable"
        capabilities = GoogleTrendsProviderCapabilities(
            provider="fake_trends_unavailable",
            supports_time_series=True,
            supports_related_queries=True,
            supports_related_topics=True,
            supports_geo_breakdown=True,
            supports_trending_now=False,
            supports_autocomplete=False,
            supports_topic_ids=False,
            supports_historical_depth="years",
            max_keywords_per_request=5,
            cache_ttl_seconds=3600,
            notes=[],
        )

        def is_available(self) -> bool:
            return False

        def get_trends(self, request):
            return None

    class _AvailableAdapter:
        provider_name = "fake_trends_available"
        capabilities = GoogleTrendsProviderCapabilities(
            provider="fake_trends_available",
            supports_time_series=True,
            supports_related_queries=True,
            supports_related_topics=True,
            supports_geo_breakdown=True,
            supports_trending_now=False,
            supports_autocomplete=False,
            supports_topic_ids=False,
            supports_historical_depth="years",
            max_keywords_per_request=5,
            cache_ttl_seconds=3600,
            notes=[],
        )

        def is_available(self) -> bool:
            return True

        def get_trends(self, request):
            return None

    monkeypatch.setattr(
        "utils.google_trends_client.TRENDS_PROVIDER_REGISTRY",
        {
            "fake_trends_unavailable": _UnavailableAdapter(),
            "fake_trends_available": _AvailableAdapter(),
        },
    )
    monkeypatch.setattr(
        "utils.google_trends_client.TRENDS_PROVIDER_OPTIONS",
        ["fake_trends_unavailable", "fake_trends_available"],
    )

    def _fake_selectbox(label, options, **kwargs):
        selectbox_calls.append((label, list(options)))
        return options[0] if options else None

    monkeypatch.setattr("components.sidebar.st.selectbox", _fake_selectbox)

    config = render_sidebar()

    trends_calls = [
        options
        for label, options in selectbox_calls
        if label == app.t("google_trends_provider_selectbox")
    ]
    assert trends_calls == [["fake_trends_available"]]
    assert info_calls == []
    assert config["google_trends_settings"]["provider"] == "fake_trends_available"


def test_sidebar_returns_empty_trends_provider_when_none_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from components.sidebar import render_sidebar
    from utils.google_trends_client import GoogleTrendsProviderCapabilities

    st.session_state.clear()
    st.session_state.ui_lang = "en"
    selectbox_calls: list[tuple[str, list[str]]] = []

    monkeypatch.setattr("components.sidebar.st.subheader", lambda *a, **kw: None)
    monkeypatch.setattr("components.sidebar.st.checkbox", lambda *a, **kw: True)
    monkeypatch.setattr("components.sidebar.st.text_input", lambda *a, **kw: "UA")
    monkeypatch.setattr("components.sidebar.st.number_input", lambda *a, **kw: 24)
    monkeypatch.setattr("components.sidebar.st.select_slider", lambda *a, **kw: None)
    monkeypatch.setattr("components.sidebar.st.divider", lambda *a, **kw: None)
    monkeypatch.setattr("components.sidebar.st.info", lambda *a, **kw: None)
    monkeypatch.setattr("components.sidebar.st.warning", lambda *a, **kw: None)
    monkeypatch.setattr(
        "components.sidebar.get_available_serp_providers",
        lambda: {"Serper.dev": "serper_dev"},
    )
    monkeypatch.setattr("components.sidebar.st.expander", lambda *a, **kw: type("_Ctx", (), {"__enter__": lambda s: s, "__exit__": lambda s, *a: False})())

    class _UnavailableAdapter:
        provider_name = "fake_trends_unavailable"
        capabilities = GoogleTrendsProviderCapabilities(
            provider="fake_trends_unavailable",
            supports_time_series=True,
            supports_related_queries=True,
            supports_related_topics=True,
            supports_geo_breakdown=True,
            supports_trending_now=False,
            supports_autocomplete=False,
            supports_topic_ids=False,
            supports_historical_depth="years",
            max_keywords_per_request=5,
            cache_ttl_seconds=3600,
            notes=[],
        )

        def is_available(self) -> bool:
            return False

        def get_trends(self, request):
            return None

    monkeypatch.setattr(
        "utils.google_trends_client.TRENDS_PROVIDER_REGISTRY",
        {"fake_trends_unavailable": _UnavailableAdapter()},
    )
    monkeypatch.setattr(
        "utils.google_trends_client.TRENDS_PROVIDER_OPTIONS",
        ["fake_trends_unavailable"],
    )

    def _fake_selectbox(label, options, **kwargs):
        selectbox_calls.append((label, list(options)))
        return options[0] if options else None

    monkeypatch.setattr("components.sidebar.st.selectbox", _fake_selectbox)

    config = render_sidebar()

    trends_calls = [
        options
        for label, options in selectbox_calls
        if label == app.t("google_trends_provider_selectbox")
    ]
    assert trends_calls == []
    assert config["google_trends_settings"]["provider"] == ""


def test_sidebar_trends_force_refresh_checkbox_is_rendered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from components.sidebar import render_sidebar

    st.session_state.clear()
    st.session_state.ui_lang = "en"
    checkbox_labels: list[str] = []

    monkeypatch.setattr("components.sidebar.st.subheader", lambda *a, **kw: None)
    monkeypatch.setattr("components.sidebar.st.text_input", lambda *a, **kw: "UA")
    monkeypatch.setattr("components.sidebar.st.number_input", lambda *a, **kw: 24)
    monkeypatch.setattr("components.sidebar.st.select_slider", lambda *a, **kw: None)
    monkeypatch.setattr("components.sidebar.st.divider", lambda *a, **kw: None)
    monkeypatch.setattr("components.sidebar.st.info", lambda *a, **kw: None)
    monkeypatch.setattr("components.sidebar.st.warning", lambda *a, **kw: None)

    def _fake_checkbox(label, **kwargs):
        checkbox_labels.append(label)
        return False

    monkeypatch.setattr("components.sidebar.st.checkbox", _fake_checkbox)

    def _fake_selectbox(label, options, **kwargs):
        return options[0] if options else None

    monkeypatch.setattr("components.sidebar.st.selectbox", _fake_selectbox)
    monkeypatch.setattr("components.sidebar.st.expander", lambda *a, **kw: type("_Ctx", (), {"__enter__": lambda s: s, "__exit__": lambda s, *a: False})())

    render_sidebar()

    refresh_labels = [label for label in checkbox_labels if "refresh" in label.lower() or "force" in label.lower() or "cache" in label.lower()]
    assert len(refresh_labels) >= 1, f"Expected force-refresh checkbox, got: {checkbox_labels}"


# ---------------------------------------------------------------------------
# PLAN 15-03: History UI duplicate key and visibility tests (HIST-15-01, HIST-15-02)
# ---------------------------------------------------------------------------


def test_render_history_unique_keys_for_entries_with_created_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from components import results

    st.session_state.clear()
    st.session_state.ui_lang = "en"

    # Mock history entries with created_at (no timestamp) and checkpoints
    history_entries = [
        {
            "record_type": "history",
            "created_at": "2026-06-05T10:00:00",
            "urls": ["https://a.com"],
            "keywords": ["kw1"],
            "keyword_count": 1,
            "url_count": 1,
            "checkpoint": {"workflow_mode": "url_llm", "scraped_content": {"https://a.com": "text"}},
        },
        {
            "record_type": "history",
            "created_at": "2026-06-05T10:00:01",
            "urls": ["https://b.com"],
            "keywords": ["kw2"],
            "keyword_count": 1,
            "url_count": 1,
            "checkpoint": {"workflow_mode": "url_llm", "scraped_content": {"https://b.com": "text"}},
        },
    ]

    monkeypatch.setattr(
        "components.results.HistoryManager.load_history",
        lambda include_cache=False: history_entries,
    )

    button_keys: list[str] = []

    class _DummyCtx:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    def _fake_button(label, **kwargs):
        if "key" in kwargs:
            button_keys.append(kwargs["key"])
        return False

    monkeypatch.setattr("components.results.st.divider", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.subheader", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.info", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.success", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.expander", lambda *a, **kw: _DummyCtx())
    monkeypatch.setattr("components.results.st.columns", lambda spec: [_DummyCtx(), _DummyCtx()])
    monkeypatch.setattr("components.results.st.button", _fake_button)
    monkeypatch.setattr("components.results.st.json", lambda *a, **kw: None)

    results.render_history(
        provider="OpenAI",
        model_name="gpt-4",
        max_keywords=10,
        location_id="2840",
        language_id="1000",
        currency_code="USD",
    )

    # All button keys should be unique (no Streamlit DuplicateKeyError)
    assert len(button_keys) == len(set(button_keys)), \
        f"Duplicate Streamlit keys found: {button_keys}"


def test_render_history_unique_keys_without_timestamp_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from components import results

    st.session_state.clear()
    st.session_state.ui_lang = "en"

    history_entries = [
        {
            "record_type": "history",
            "urls": ["https://a.com"],
            "keywords": ["kw1"],
            "checkpoint": {
                "workflow_mode": "url_llm",
                "scraped_content": {"https://a.com": "text"},
            },
        },
        {
            "record_type": "history",
            "urls": ["https://a.com"],
            "keywords": ["kw1"],
            "checkpoint": {
                "workflow_mode": "url_llm",
                "scraped_content": {"https://a.com": "text"},
            },
        },
    ]

    monkeypatch.setattr(
        "components.results.HistoryManager.load_history",
        lambda include_cache=False: history_entries,
    )

    button_keys: list[str] = []

    class _DummyCtx:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    def _fake_button(label, **kwargs):
        if "key" in kwargs:
            button_keys.append(kwargs["key"])
        return False

    monkeypatch.setattr("components.results.st.divider", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.subheader", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.info", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.success", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.expander", lambda *a, **kw: _DummyCtx())
    monkeypatch.setattr("components.results.st.columns", lambda spec: [_DummyCtx(), _DummyCtx()])
    monkeypatch.setattr("components.results.st.button", _fake_button)
    monkeypatch.setattr("components.results.st.json", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.markdown", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.caption", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.error", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.warning", lambda *a, **kw: None)

    def _fake_tabs(labels):
        return [_DummyCtx() for _ in labels]
    monkeypatch.setattr("components.results.st.tabs", _fake_tabs)

    results.render_history(
        provider="OpenAI",
        model_name="gpt-4",
        max_keywords=10,
        location_id="2840",
        language_id="1000",
        currency_code="USD",
    )

    # 5 entries × 3 tabs = 15 restore buttons + 1 clear button = 16 max,
    # but only history entries (not cache) get restore+regenerate buttons,
    # and only in tabs where they appear. With 5 history + 0 cache entries,
    # each entry has 2 buttons (restore + regenerate) × 2 tabs (all + history) = 20 + 1 clear = 21
    # Just verify uniqueness and no ::na fallback
    assert len(button_keys) == len(set(button_keys)), button_keys
    assert all("::na" not in key for key in button_keys)


def test_render_history_shows_cache_records_when_toggled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from components import results

    st.session_state.clear()
    st.session_state.ui_lang = "en"

    all_records = [
        {
            "record_type": "cache",
            "kind": "serp",
            "cache_key": "key1",
            "cache_hit_count": 5,
        },
    ]

    monkeypatch.setattr(
        "components.results.HistoryManager.load_history",
        lambda include_cache=False: all_records,
    )

    info_calls: list[str] = []
    expander_labels: list[str] = []
    button_labels: list[str] = []

    class _DummyCtx:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    monkeypatch.setattr("components.results.st.divider", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.subheader", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.info", lambda msg, *a, **kw: info_calls.append(msg))
    monkeypatch.setattr("components.results.st.success", lambda *a, **kw: None)
    monkeypatch.setattr(
        "components.results.st.expander",
        lambda label, *a, **kw: expander_labels.append(label) or _DummyCtx(),
    )
    monkeypatch.setattr("components.results.st.columns", lambda spec: [_DummyCtx(), _DummyCtx()])
    def _fake_button(label, **kwargs):
        button_labels.append(label)
        return False
    monkeypatch.setattr("components.results.st.button", _fake_button)
    monkeypatch.setattr("components.results.st.json", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.markdown", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.caption", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.error", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.warning", lambda *a, **kw: None)

    def _fake_tabs(labels):
        return [_DummyCtx() for _ in labels]
    monkeypatch.setattr("components.results.st.tabs", _fake_tabs)

    results.render_history(
        provider="OpenAI",
        model_name="gpt-4",
        max_keywords=10,
        location_id="2840",
        language_id="1000",
        currency_code="USD",
    )

    assert results.t("history_clear_cache_button") in button_labels
    assert info_calls == []
    # Cache entry renders in All + Cache tabs = 2 expanders
    assert len(expander_labels) == 2
    # Both should start with 💾 (cache indicator)
    assert all(label.startswith("\U0001f4be") for label in expander_labels)
    # Both should contain SERP Analysis and Hits: 5
    assert all("SERP Analysis" in label for label in expander_labels)
    assert all("Hits: 5" in label for label in expander_labels)


def _patch_history_render_common(monkeypatch: pytest.MonkeyPatch, results_module):
    """Patch the Streamlit/HistoryManager surface that render_history touches.

    Shared by the clear-cache confirmation tests. The dialog opener
    (show_clear_cache_confirm_dialog) is patched to run its testable body inline,
    bypassing Streamlit's deferred dialog-open machinery.
    """
    cache_records = [
        {
            "record_type": "cache",
            "kind": "serp",
            "cache_key": "key1",
        }
    ]

    monkeypatch.setattr(
        "components.results.HistoryManager.load_history",
        lambda include_cache=False: cache_records if include_cache else [],
    )

    class _DummyCtx:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("components.results.st.divider", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.subheader", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.info", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.success", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.error", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.expander", lambda *a, **kw: _DummyCtx())
    monkeypatch.setattr("components.results.st.columns", lambda spec: [_DummyCtx(), _DummyCtx()])
    monkeypatch.setattr("components.results.st.json", lambda *a, **kw: None)
    monkeypatch.setattr("components.results.st.rerun", lambda: None)
    monkeypatch.setattr("components.results.st.write", lambda *a, **kw: None)

    # Route the @st.dialog opener straight to its (plain, testable) body.
    monkeypatch.setattr(
        "components.results.show_clear_cache_confirm_dialog",
        results_module.render_clear_cache_dialog_body,
    )

    return _DummyCtx


# Purpose: pressing the "Clear history and cache" button must NOT clear immediately —
# it only opens the confirmation dialog. clear_history must not be called yet.
def test_render_history_clear_button_opens_dialog_without_clearing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from components import results

    st.session_state.clear()
    st.session_state.ui_lang = "en"

    _patch_history_render_common(monkeypatch, results)

    clear_calls: list[bool] = []
    monkeypatch.setattr(
        "components.results.HistoryManager.clear_history",
        lambda clear_cache=False: clear_calls.append(clear_cache) or True,
    )

    # Only the main clear-cache button is "clicked"; the confirm button inside the
    # dialog is NOT clicked.
    def _fake_button(label, **kwargs):
        return label == results.t("history_clear_cache_button")

    monkeypatch.setattr("components.results.st.button", _fake_button)

    results.render_history(
        provider="OpenAI",
        model_name="gpt-4",
        max_keywords=10,
        location_id="2840",
        language_id="1000",
        currency_code="USD",
    )

    # The destructive action was NOT taken on the first click.
    assert clear_calls == []
    assert "history_flash_message" not in st.session_state


# Purpose: confirming inside the dialog actually clears history+cache and sets the
# success flash message (mirrors the old immediate-clear contract, now gated).
def test_render_history_clear_confirmation_dialog_clears_history_and_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from components import results

    st.session_state.clear()
    st.session_state.ui_lang = "en"

    _patch_history_render_common(monkeypatch, results)

    clear_calls: list[bool] = []
    monkeypatch.setattr(
        "components.results.HistoryManager.clear_history",
        lambda clear_cache=False: clear_calls.append(clear_cache) or True,
    )

    # Both the main button AND the confirmation button are "clicked".
    def _fake_button(label, **kwargs):
        return label in (
            results.t("history_clear_cache_button"),
            results.t("history_clear_cache_confirm_yes"),
        )

    monkeypatch.setattr("components.results.st.button", _fake_button)

    results.render_history(
        provider="OpenAI",
        model_name="gpt-4",
        max_keywords=10,
        location_id="2840",
        language_id="1000",
        currency_code="USD",
    )

    assert clear_calls == [True]
    assert st.session_state.history_flash_message == results.t("history_clear_cache_success")


# ---------------------------------------------------------------------------
# Cache restore — deserialization and session state recovery
# ---------------------------------------------------------------------------

class TestRestoreCacheToSession:

    def _call_restore(self, entry: dict) -> bool:
        from components.results import _restore_cache_to_session

        return _restore_cache_to_session(entry)

    # --- DataFrame-based kinds (serp, ads, crawl, llm_extract) ---

    @pytest.mark.parametrize("kind", ["serp", "ads", "crawl", "llm_extract"])
    def test_dataframe_payload_restores_to_processed_data(self, kind: str) -> None:
        st.session_state.pop("processed_data", None)
        entry = {
            "kind": kind,
            "result": {
                "type": "dataframe",
                "payload": {
                    "columns": ["Keyword", "Volume"],
                    "data": [
                        {"Keyword": "seo", "Volume": 100},
                        {"Keyword": "marketing", "Volume": 80},
                    ],
                },
            },
        }
        assert self._call_restore(entry) is True
        assert "processed_data" in st.session_state
        df = st.session_state.processed_data
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["Keyword", "Volume"]
        assert len(df) == 2

    # --- Trends ---

    def test_trends_dataframe_payload_restores_to_trends_results(self) -> None:
        st.session_state.pop("trends_results", None)
        entry = {
            "kind": "trends",
            "result": {
                "type": "dataframe",
                "payload": {
                    "columns": ["Keyword", "Interest"],
                    "data": [{"Keyword": "ai", "Interest": 95}],
                },
            },
        }
        assert self._call_restore(entry) is True
        assert "trends_results" in st.session_state
        df = st.session_state.trends_results
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1

    # --- Math (dict) ---

    def test_math_dict_payload_restores_to_serp_math_profile(self) -> None:
        st.session_state.pop("serp_math_profile", None)
        profile = {"tfidf": {"seo": 0.8}, "bm25f_scores": {"seo": 1.2}}
        entry = {
            "kind": "math",
            "result": {
                "type": "json",
                "payload": profile,
            },
        }
        assert self._call_restore(entry) is True
        assert st.session_state.serp_math_profile == profile

    # --- Edge cases ---

    def test_missing_result_returns_false(self) -> None:
        assert self._call_restore({"kind": "serp"}) is False

    def test_empty_payload_returns_false(self) -> None:
        entry = {"kind": "serp", "result": {"type": "dataframe", "payload": None}}
        assert self._call_restore(entry) is False

    def test_unknown_kind_returns_false(self) -> None:
        entry = {
            "kind": "model_fetch",
            "result": {"type": "json", "payload": {"models": ["gpt-4"]}},
        }
        assert self._call_restore(entry) is False

    def test_empty_dataframe_payload_returns_false(self) -> None:
        entry = {
            "kind": "serp",
            "result": {
                "type": "dataframe",
                "payload": {"columns": ["Keyword"], "data": []},
            },
        }
        assert self._call_restore(entry) is False

    def test_list_payload_restores_for_serp(self) -> None:
        st.session_state.pop("processed_data", None)
        # SERP payload is a list of {keyword, organic: [...]} dicts
        entry = {
            "kind": "serp",
            "result": {
                "type": "json",
                "payload": [{
                    "keyword": "seo",
                    "organic": [
                        {
                            "position": 1,
                            "title": "SEO Tools",
                            "url": "https://example.com",
                            "snippet": "Best SEO tools",
                            "displayed_link": "example.com",
                        },
                    ],
                    "related_searches": [],
                    "people_also_ask": [],
                    "provider": "test",
                    "success": True,
                    "error": None,
                }],
            },
        }
        assert self._call_restore(entry) is True
        assert isinstance(st.session_state.processed_data, pd.DataFrame)
        assert len(st.session_state.processed_data) == 1
        assert st.session_state.processed_data.iloc[0]["Keyword"] == "seo"


# ---------------------------------------------------------------------------
# _deserialize_cache_payload unit tests
# ---------------------------------------------------------------------------

class TestDeserializeCachePayload:

    def _call(self, payload):
        from components.results import _deserialize_cache_payload

        return _deserialize_cache_payload(payload)

    def test_dataframe_columns_data_format(self) -> None:
        payload = {
            "columns": ["A", "B"],
            "data": [{"A": 1, "B": 2}],
        }
        result = self._call(payload)
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == ["A", "B"]
        assert result.iloc[0]["A"] == 1

    def test_plain_list_returns_unchanged(self) -> None:
        data = [{"x": 1}, {"x": 2}]
        assert self._call(data) is data

    def test_plain_dict_without_columns_returns_unchanged(self) -> None:
        data = {"key": "value"}
        assert self._call(data) == data

    def test_scalar_returns_unchanged(self) -> None:
        assert self._call("hello") == "hello"


class TestSeoRegenerateButton:

    # GRACE: function _make_seo_df declaration.
    def _make_seo_df(self) -> pd.DataFrame:
        return pd.DataFrame({
            "Keywords": ["kw1, kw2"],
            "URL": ["https://example.com"],
            "SEO Text": ["META_TITLE: Test Title\nMETA_DESCRIPTION: Test desc\nH1: Heading\nDESCRIPTION: Body text"],
        })

    # GRACE: function _patch_st_render declaration.
    def _patch_st_render(self, monkeypatch, button_results=None):
        if button_results is None:
            button_results = {}

        # GRACE: function fake_button declaration.
        def fake_button(label, **kwargs):
            key = kwargs.get("key", label)
            return button_results.get(key, False)

        monkeypatch.setattr("streamlit.button", fake_button)
        monkeypatch.setattr("streamlit.divider", lambda: None)
        monkeypatch.setattr("streamlit.subheader", lambda *a, **kw: None)
        monkeypatch.setattr("streamlit.success", lambda *a, **kw: None)
        monkeypatch.setattr("streamlit.info", lambda *a, **kw: None)
        monkeypatch.setattr("streamlit.warning", lambda *a, **kw: None)
        monkeypatch.setattr("streamlit.error", lambda *a, **kw: None)
        monkeypatch.setattr("streamlit.rerun", lambda: None)
        monkeypatch.setattr("streamlit.dataframe", lambda *a, **kw: None)
        monkeypatch.setattr("streamlit.download_button", lambda *a, **kw: False)
        monkeypatch.setattr("streamlit.checkbox", lambda *a, **kw: False)

    # GRACE: function test_regenerate_button_sets_force_flag declaration.
    def test_regenerate_button_sets_force_flag(self, monkeypatch):
        from components.results import render_seo_results

        df = self._make_seo_df()
        st.session_state["generated_seo_texts"] = df
        st.session_state["scraped_content"] = {"https://example.com": "page content"}
        st.session_state["seo_excel_saved"] = False

        self._patch_st_render(monkeypatch, button_results={"seo_regenerate_btn": True})

        render_seo_results(auto_save_excel=False)

        assert st.session_state.get("seo_force_regenerate") is True

    # GRACE: function test_regenerate_flag_survives_render_seo_results declaration.
    def test_regenerate_flag_survives_render_seo_results(self, monkeypatch):
        from components.results import render_seo_results

        st.session_state["seo_force_regenerate"] = True
        st.session_state["generated_seo_texts"] = self._make_seo_df()
        st.session_state["scraped_content"] = {"https://example.com": "page content"}
        st.session_state["seo_excel_saved"] = False

        self._patch_st_render(monkeypatch, button_results={"seo_regenerate_btn": False})

        render_seo_results(auto_save_excel=False)

        assert st.session_state.get("seo_force_regenerate") is True

    # GRACE: function test_no_regenerate_button_when_no_texts declaration.
    def test_no_regenerate_button_when_no_texts(self, monkeypatch):
        from components.results import render_seo_results

        st.session_state["generated_seo_texts"] = None
        buttons_clicked = []
        # GRACE: function tracking_button declaration.
        def tracking_button(label, **kwargs):
            key = kwargs.get("key", label)
            if key == "seo_regenerate_btn":
                buttons_clicked.append(True)
            return False

        monkeypatch.setattr("streamlit.button", tracking_button)
        render_seo_results(auto_save_excel=False)

        # Regenerate button should not have been rendered
        assert len(buttons_clicked) == 0


class TestSeoGenerationForceRefresh:

    # GRACE: function _patch_st_generation declaration.
    def _patch_st_generation(self, monkeypatch):
        monkeypatch.setattr("streamlit.button", lambda *a, **kw: False)
        monkeypatch.setattr("streamlit.divider", lambda: None)
        monkeypatch.setattr("streamlit.subheader", lambda *a, **kw: None)
        monkeypatch.setattr("streamlit.status", lambda *a, **kw: SimpleNamespace(
            write=lambda *a, **kw: None,
            update=lambda *a, **kw: None,
            __enter__=lambda s: s,
            __exit__=lambda s, *a: False,
        ))
        monkeypatch.setattr("streamlit.progress", lambda *a, **kw: SimpleNamespace(
            progress=lambda *a, **kw: None,
        ))
        monkeypatch.setattr("streamlit.success", lambda *a, **kw: None)
        monkeypatch.setattr("streamlit.info", lambda *a, **kw: None)
        monkeypatch.setattr("streamlit.warning", lambda *a, **kw: None)
        monkeypatch.setattr("streamlit.rerun", lambda: None)

    # GRACE: function test_force_flag_consumed_by_generation declaration.
    def test_force_flag_consumed_by_generation(self, monkeypatch):
        from components.results import render_seo_generation

        st.session_state["seo_force_regenerate"] = True
        st.session_state["processed_data"] = pd.DataFrame({
            "Source URL": ["https://example.com"],
            "Keyword": ["test kw"],
            "Avg Monthly Searches": [100],
        })
        st.session_state["scraped_content"] = {"https://example.com": "page content"}

        self._patch_st_generation(monkeypatch)

        captured = {}
        class FakeLLM:
            def __init__(self, **kwargs):
                pass
            # GRACE: function generate_seo_text declaration.
            def generate_seo_text(self, **kwargs):
                captured["force_refresh"] = kwargs.get("force_refresh", False)
                return "META_TITLE: Test\nDESCRIPTION: Test body"

        monkeypatch.setattr("components.results.LLMHandler", FakeLLM)

        render_seo_generation(
            provider="google",
            model_name="gemini",
            selected_kw_by_url={"https://example.com": ["test kw"]},
            total_selected=1,
        )

        assert captured.get("force_refresh") is True

    # GRACE: function test_normal_generation_has_force_refresh_false declaration.
    def test_normal_generation_has_force_refresh_false(self, monkeypatch):
        from components.results import render_seo_generation

        st.session_state.pop("seo_force_regenerate", None)
        st.session_state["processed_data"] = pd.DataFrame({
            "Source URL": ["https://example.com"],
            "Keyword": ["test kw"],
            "Avg Monthly Searches": [100],
        })
        st.session_state["scraped_content"] = {"https://example.com": "page content"}

        # Button returns True (user clicked Generate SEO), but no force flag
        monkeypatch.setattr("streamlit.button", lambda *a, **kw: True)
        monkeypatch.setattr("streamlit.divider", lambda: None)
        monkeypatch.setattr("streamlit.subheader", lambda *a, **kw: None)
        monkeypatch.setattr("streamlit.status", lambda *a, **kw: SimpleNamespace(
            write=lambda *a, **kw: None,
            update=lambda *a, **kw: None,
            __enter__=lambda s: s,
            __exit__=lambda s, *a: False,
        ))
        monkeypatch.setattr("streamlit.progress", lambda *a, **kw: SimpleNamespace(
            progress=lambda *a, **kw: None,
        ))
        monkeypatch.setattr("streamlit.success", lambda *a, **kw: None)
        monkeypatch.setattr("streamlit.info", lambda *a, **kw: None)
        monkeypatch.setattr("streamlit.warning", lambda *a, **kw: None)
        monkeypatch.setattr("streamlit.rerun", lambda: None)

        captured = {}
        class FakeLLM:
            def __init__(self, **kwargs):
                pass
            # GRACE: function generate_seo_text declaration.
            def generate_seo_text(self, **kwargs):
                captured["force_refresh"] = kwargs.get("force_refresh", False)
                return "META_TITLE: Test\nDESCRIPTION: Test body"

        monkeypatch.setattr("components.results.LLMHandler", FakeLLM)

        render_seo_generation(
            provider="google",
            model_name="gemini",
            selected_kw_by_url={"https://example.com": ["test kw"]},
            total_selected=1,
        )

        assert captured.get("force_refresh") is False


class TestSeoGenerationAutoGenerate:

    # GRACE: function _patch_st declaration.
    def _patch_st(self, monkeypatch):
        monkeypatch.setattr("streamlit.button", lambda *a, **kw: False)
        monkeypatch.setattr("streamlit.divider", lambda: None)
        monkeypatch.setattr("streamlit.subheader", lambda *a, **kw: None)
        monkeypatch.setattr("streamlit.status", lambda *a, **kw: SimpleNamespace(
            write=lambda *a, **kw: None,
            update=lambda *a, **kw: None,
            __enter__=lambda s: s,
            __exit__=lambda s, *a: False,
        ))
        monkeypatch.setattr("streamlit.progress", lambda *a, **kw: SimpleNamespace(
            progress=lambda *a, **kw: None,
        ))
        monkeypatch.setattr("streamlit.success", lambda *a, **kw: None)
        monkeypatch.setattr("streamlit.info", lambda *a, **kw: None)
        monkeypatch.setattr("streamlit.warning", lambda *a, **kw: None)
        monkeypatch.setattr("streamlit.rerun", lambda: None)

    # GRACE: function test_auto_generate_flag_runs_generation_without_button_click declaration.
    def test_auto_generate_flag_runs_generation_without_button_click(self, monkeypatch):
        from components.results import render_seo_generation

        st.session_state.clear()
        st.session_state["seo_auto_generate"] = True
        st.session_state["processed_data"] = pd.DataFrame({
            "Source URL": ["https://example.com"],
            "Keyword": ["test kw"],
            "Avg Monthly Searches": [100],
        })
        st.session_state["generated_seo_texts"] = None
        st.session_state["scraped_content"] = {"https://example.com": "page content"}

        self._patch_st(monkeypatch)

        captured = {}

        class FakeLLM:
            def __init__(self, **kwargs):
                pass

            # GRACE: function generate_seo_text declaration.
            def generate_seo_text(self, **kwargs):
                captured["called"] = True
                return "META_TITLE: Test\nDESCRIPTION: Test body"

        monkeypatch.setattr("components.results.LLMHandler", FakeLLM)

        render_seo_generation(
            provider="google",
            model_name="gemini",
            selected_kw_by_url={"https://example.com": ["test kw"]},
            total_selected=1,
        )

        # Generation must have run (auto flag), and the produced text must be stored.
        assert captured.get("called") is True, (
            "auto-generate flag did not run SEO generation"
        )
        gen_df = st.session_state.get("generated_seo_texts")
        assert gen_df is not None and not gen_df.empty
        assert "META_TITLE: Test" in str(gen_df.iloc[0].to_dict())

    # GRACE: function test_auto_generate_flag_is_consumed_after_use declaration.
    def test_auto_generate_flag_is_consumed_after_use(self, monkeypatch):
        from components.results import render_seo_generation

        st.session_state.clear()
        st.session_state["seo_auto_generate"] = True
        st.session_state["processed_data"] = pd.DataFrame({
            "Source URL": ["https://example.com"],
            "Keyword": ["test kw"],
            "Avg Monthly Searches": [100],
        })
        st.session_state["generated_seo_texts"] = None
        st.session_state["scraped_content"] = {"https://example.com": "page content"}

        self._patch_st(monkeypatch)

        class FakeLLM:
            def __init__(self, **kwargs):
                pass

            # GRACE: function generate_seo_text declaration.
            def generate_seo_text(self, **kwargs):
                return "META_TITLE: Test"

        monkeypatch.setattr("components.results.LLMHandler", FakeLLM)

        render_seo_generation(
            provider="google",
            model_name="gemini",
            selected_kw_by_url={"https://example.com": ["test kw"]},
            total_selected=1,
        )

        assert "seo_auto_generate" not in st.session_state


class TestBuildGeneratedTextMathProfile:

    # GRACE: function _make_seo_df declaration.
    def _make_seo_df(self, text_content="META_TITLE: Купить ноутбук\nMETA_DESCRIPTION: Лучшие ноутбуки по низким ценам\nH1: Ноутбуки\nDESCRIPTION: Большой выбор ноутбуков и компьютеров. Купите сейчас с доставкой.") -> pd.DataFrame:
        return pd.DataFrame({
            "Keywords": ["ноутбук, компьютер"],
            "URL": ["https://example.com"],
            "SEO Text": [text_content],
        })

    # GRACE: function test_returns_empty_profile_when_disabled declaration.
    def test_returns_empty_profile_when_disabled(self, monkeypatch):
        from utils.pipeline import build_generated_text_math_profile
        monkeypatch.setattr("utils.pipeline.SEO_MATH_CONFIG", {"enabled": False, "analyze_generated_text": False})
        result = build_generated_text_math_profile(self._make_seo_df())
        assert result["info_message"] != ""
        assert result["total_rows"] == 0

    # GRACE: function test_returns_early_when_generated_text_flag_off declaration.
    def test_returns_early_when_generated_text_flag_off(self, monkeypatch):
        from utils.pipeline import build_generated_text_math_profile
        monkeypatch.setattr("utils.pipeline.SEO_MATH_CONFIG", {
            "enabled": True, "analyze_generated_text": False,
        })
        result = build_generated_text_math_profile(self._make_seo_df())
        assert result["total_rows"] == 0

    # GRACE: function test_returns_empty_for_none_df declaration.
    def test_returns_empty_for_none_df(self, monkeypatch):
        from utils.pipeline import build_generated_text_math_profile
        monkeypatch.setattr("utils.pipeline.SEO_MATH_CONFIG", {
            "enabled": True, "analyze_generated_text": True,
        })
        result = build_generated_text_math_profile(None)
        assert result["info_message"] != ""

    # GRACE: function test_returns_empty_for_empty_df declaration.
    def test_returns_empty_for_empty_df(self, monkeypatch):
        from utils.pipeline import build_generated_text_math_profile
        monkeypatch.setattr("utils.pipeline.SEO_MATH_CONFIG", {
            "enabled": True, "analyze_generated_text": True,
        })
        result = build_generated_text_math_profile(pd.DataFrame())
        assert result["info_message"] != ""

    # GRACE: function test_produces_tfidf_terms_from_generated_text declaration.
    def test_produces_tfidf_terms_from_generated_text(self, monkeypatch):
        from utils.pipeline import build_generated_text_math_profile
        monkeypatch.setattr("utils.pipeline.SEO_MATH_CONFIG", {
            "enabled": True, "analyze_generated_text": True,
            "strip_suffixes": False, "ngram_min": 1, "ngram_max": 2,
            "top_terms_limit": 30, "min_ngram_count": 1, "min_document_frequency": 1,
            "analyze_ngrams": True, "analyze_tfidf": True,
            "analyze_cooccurrence": False, "analyze_intent": False, "analyze_bm25f": False,
        })
        result = build_generated_text_math_profile(self._make_seo_df())
        assert result["total_rows"] == 1
        assert len(result["tfidf_terms"]) > 0
        all_terms = [t.term for t in result["tfidf_terms"]]
        assert any("ноутбук" in t for t in all_terms) or len(all_terms) > 0

    # GRACE: function test_produces_ngrams_by_size declaration.
    def test_produces_ngrams_by_size(self, monkeypatch):
        from utils.pipeline import build_generated_text_math_profile
        monkeypatch.setattr("utils.pipeline.SEO_MATH_CONFIG", {
            "enabled": True, "analyze_generated_text": True,
            "strip_suffixes": False, "ngram_min": 1, "ngram_max": 2,
            "top_terms_limit": 30, "min_ngram_count": 1, "min_document_frequency": 1,
            "analyze_ngrams": True, "analyze_tfidf": True,
            "analyze_cooccurrence": False, "analyze_intent": False, "analyze_bm25f": False,
        })
        result = build_generated_text_math_profile(self._make_seo_df())
        assert 1 in result["ngrams_by_size"]
        assert len(result["ngrams_by_size"][1]) > 0

    # GRACE: function test_produces_per_row_profiles declaration.
    def test_produces_per_row_profiles(self, monkeypatch):
        from utils.pipeline import build_generated_text_math_profile
        monkeypatch.setattr("utils.pipeline.SEO_MATH_CONFIG", {
            "enabled": True, "analyze_generated_text": True,
            "strip_suffixes": False, "ngram_min": 1, "ngram_max": 2,
            "top_terms_limit": 30, "min_ngram_count": 1, "min_document_frequency": 1,
            "analyze_ngrams": True, "analyze_tfidf": True,
            "analyze_cooccurrence": False, "analyze_intent": True, "analyze_bm25f": False,
        })
        df = pd.DataFrame({
            "Keywords": ["kw1", "kw2"],
            "URL": ["https://a.com", "https://b.com"],
            "SEO Text": [
                "META_TITLE: First Title\nDESCRIPTION: First body text with keywords",
                "META_TITLE: Second Title\nDESCRIPTION: Second body text with data",
            ],
        })
        result = build_generated_text_math_profile(df)
        assert result["total_rows"] == 2
        assert len(result["per_row_profiles"]) == 2
        assert result["per_row_profiles"][0]["url"] == "https://a.com"
        assert result["per_row_profiles"][1]["url"] == "https://b.com"

    # GRACE: function test_intent_analysis_runs_on_generated_text declaration.
    def test_intent_analysis_runs_on_generated_text(self, monkeypatch):
        from utils.pipeline import build_generated_text_math_profile
        monkeypatch.setattr("utils.pipeline.SEO_MATH_CONFIG", {
            "enabled": True, "analyze_generated_text": True,
            "strip_suffixes": False, "ngram_min": 1, "ngram_max": 2,
            "top_terms_limit": 30, "min_ngram_count": 1, "min_document_frequency": 1,
            "analyze_ngrams": False, "analyze_tfidf": True,
            "analyze_cooccurrence": False, "analyze_intent": True, "analyze_bm25f": False,
        })
        result = build_generated_text_math_profile(self._make_seo_df(
            "META_TITLE: Купить ноутбук недорого\nDESCRIPTION: Купите лучший ноутбук с быстрой доставкой. Заказывайте онлайн."
        ))
        assert result["intent"] is not None
        assert result["intent"].intent_type == "transactional"

    # GRACE: function test_skips_rows_with_no_text declaration.
    def test_skips_rows_with_no_text(self, monkeypatch):
        from utils.pipeline import build_generated_text_math_profile
        monkeypatch.setattr("utils.pipeline.SEO_MATH_CONFIG", {
            "enabled": True, "analyze_generated_text": True,
            "strip_suffixes": False, "ngram_min": 1, "ngram_max": 2,
            "top_terms_limit": 30, "min_ngram_count": 1, "min_document_frequency": 1,
            "analyze_ngrams": True, "analyze_tfidf": True,
            "analyze_cooccurrence": False, "analyze_intent": False, "analyze_bm25f": False,
        })
        df = pd.DataFrame({
            "Keywords": ["kw1", "kw2"],
            "URL": ["https://a.com", "https://b.com"],
            "SEO Text": ["META_TITLE: Good Title\nDESCRIPTION: Good body", ""],
        })
        result = build_generated_text_math_profile(df)
        assert result["total_rows"] == 1


class TestUrlLlmSeoHandoff:

    # GRACE: function _stub_common declaration.
    def _stub_common(self, monkeypatch):
        monkeypatch.setattr("app.run_startup_cleanup", lambda: {})
        monkeypatch.setattr("app.validate_api_keys", lambda: {"openai": True})
        monkeypatch.setattr("app.logger.close_handlers", lambda: None)
        monkeypatch.setattr("app.logger.refresh_config", lambda: None)
        monkeypatch.setattr("app.logger.info", lambda *args, **kwargs: None)
        for attr in (
            "title", "markdown", "warning", "error", "info", "success",
            "subheader", "divider", "write", "code",
        ):
            monkeypatch.setattr(f"app.st.{attr}", lambda *a, **kw: None)
        monkeypatch.setattr("app.st.rerun", lambda *a, **kw: None)
        monkeypatch.setattr("app.render_keyword_results", lambda *a, **kw: None)
        monkeypatch.setattr("app.render_scraping_preview", lambda *a, **kw: None)
        monkeypatch.setattr("app.render_keyword_selection", lambda *a, **kw: None)
        monkeypatch.setattr("app.render_keyword_ideas_generation", lambda *a, **kw: None)
        monkeypatch.setattr("app.render_seo_results", lambda *a, **kw: None)
        monkeypatch.setattr("app.render_history", lambda *a, **kw: None)
        # A 4-column row must unpack cleanly for the SERP/Ads/Trends/SEO buttons.
        monkeypatch.setattr("app.st.columns", lambda spec: tuple(
            type("C", (), {"__enter__": lambda s: s, "__exit__": lambda s, *a: False})()
            for _ in range(spec if isinstance(spec, int) else len(spec))
        ))

    # GRACE: function test_seo_button_prepared_context_and_renders_generation declaration.
    def test_seo_button_prepared_context_and_renders_generation(self, monkeypatch):
        st.session_state.clear()
        app._ensure_session_defaults()
        st.session_state["workflow_mode"] = app.WORKFLOW_MODE_URL_LLM
        st.session_state["current_run_id"] = "run-test"
        # URL_LLM extraction already scraped the pages into scraped_content.
        st.session_state["scraped_content"] = {
            "https://example.com/a": "page A text",
        }

        monkeypatch.setattr(
            "app.render_sidebar",
            lambda: {
                "provider": "OpenAI", "model_name": "gpt-test", "max_keywords": 10,
                "location_id": "2840", "language_id": "1000", "currency_code": "USD",
                "auto_save_excel": False, "keyword_prompt": "", "seo_prompt": "prompt",
                "keyword_llm_language": "Russian", "page_type": "product",
                "api_timeout": 10, "api_delay": 2, "api_retry_count": 4,
                "api_retry_delay": 4, "upload_max_file_size_mb": 5, "upload_max_rows": 1000,
            },
        )
        monkeypatch.setattr(
            "app._render_input_form",
            lambda: (app.WORKFLOW_MODE_URL_LLM, "", None, False),
        )
        self._stub_common(monkeypatch)

        # Stage-1 selector returns two selected (keyword, url) tuples.
        monkeypatch.setattr(
            "app.render_keyword_candidate_selector_with_sources",
            lambda *a, **kw: [("buy coffee", "https://example.com/a"),
                              ("coffee beans", "https://example.com/a")],
        )

        def _button(label, *a, **kw):
            return label == app.t("send_selected_to_seo")
        monkeypatch.setattr("app.st.button", _button)

        seo_calls = []
        monkeypatch.setattr(
            "app.render_seo_generation",
            lambda *a, **kw: seo_calls.append((a, kw)),
        )

        app.main()

        # render_seo_generation must have been invoked with the prepared context.
        assert len(seo_calls) == 1, f"Expected render_seo_generation once, got {seo_calls}"
        args, kwargs = seo_calls[0]
        selected_kw_by_url = args[2]
        total_selected = args[3]
        assert selected_kw_by_url == {
            "https://example.com/a": ["buy coffee", "coffee beans"],
        }
        assert total_selected == 2
        # page_type and language must flow through.
        assert kwargs.get("page_type") == "product"
        assert kwargs.get("language") == "Russian"

        # processed_data must now exist with the canonical columns for downstream export.
        df = st.session_state["processed_data"]
        assert "Keyword" in df.columns
        assert "Avg Monthly Searches" in df.columns
        assert "buy coffee" in set(df["Keyword"].astype(str))

    # GRACE: function test_no_double_render_when_seo_context_ready declaration.
    def test_no_double_render_when_seo_context_ready(self, monkeypatch):
        st.session_state.clear()
        app._ensure_session_defaults()
        st.session_state["workflow_mode"] = app.WORKFLOW_MODE_URL_LLM
        st.session_state["current_run_id"] = "run-test"
        st.session_state["scraped_content"] = {"https://example.com/a": "page A"}
        # Pre-seed the direct-SEO context so the new block renders generation.
        st.session_state["seo_context_ready"] = (
            {"https://example.com/a": ["buy coffee"]}, 1
        )
        st.session_state["processed_data"] = pd.DataFrame({
            "Keyword": ["buy coffee"],
            "Source URL": ["https://example.com/a"],
            "Avg Monthly Searches": [None],
        })

        monkeypatch.setattr(
            "app.render_sidebar",
            lambda: {
                "provider": "OpenAI", "model_name": "gpt-test", "max_keywords": 10,
                "location_id": "2840", "language_id": "1000", "currency_code": "USD",
                "auto_save_excel": False, "keyword_prompt": "", "seo_prompt": "",
                "keyword_llm_language": "Russian", "page_type": "product",
                "api_timeout": 10, "api_delay": 2, "api_retry_count": 4,
                "api_retry_delay": 4, "upload_max_file_size_mb": 5, "upload_max_rows": 1000,
            },
        )
        monkeypatch.setattr(
            "app._render_input_form",
            lambda: (app.WORKFLOW_MODE_URL_LLM, "", None, False),
        )
        self._stub_common(monkeypatch)
        monkeypatch.setattr(
            "app.render_keyword_candidate_selector_with_sources",
            lambda *a, **kw: None,
        )
        monkeypatch.setattr("app.st.button", lambda *a, **kw: False)

        selection_calls = []
        monkeypatch.setattr(
            "app.render_keyword_selection",
            lambda *a, **kw: selection_calls.append(1),
        )
        monkeypatch.setattr("app.render_seo_generation", lambda *a, **kw: None)

        app.main()

        assert selection_calls == [], (
            "render_keyword_selection must not render when seo_context_ready is set"
        )

    # GRACE: function test_seo_handoff_button_sets_auto_generate_flag declaration.
    def test_seo_handoff_button_sets_auto_generate_flag(self, monkeypatch):
        st.session_state.clear()
        app._ensure_session_defaults()
        st.session_state["workflow_mode"] = app.WORKFLOW_MODE_URL_LLM
        st.session_state["current_run_id"] = "run-test"
        st.session_state["scraped_content"] = {"https://example.com/a": "page A"}

        monkeypatch.setattr(
            "app.render_sidebar",
            lambda: {
                "provider": "OpenAI", "model_name": "gpt-test", "max_keywords": 10,
                "location_id": "2840", "language_id": "1000", "currency_code": "USD",
                "auto_save_excel": False, "keyword_prompt": "", "seo_prompt": "",
                "keyword_llm_language": "Russian", "page_type": "product",
                "api_timeout": 10, "api_delay": 2, "api_retry_count": 4,
                "api_retry_delay": 4, "upload_max_file_size_mb": 5, "upload_max_rows": 1000,
            },
        )
        monkeypatch.setattr(
            "app._render_input_form",
            lambda: (app.WORKFLOW_MODE_URL_LLM, "", None, False),
        )
        self._stub_common(monkeypatch)

        monkeypatch.setattr(
            "app.render_keyword_candidate_selector_with_sources",
            lambda *a, **kw: [("buy coffee", "https://example.com/a")],
        )

        # GRACE: function _button declaration.
        # Only the SEO handoff button "clicks"; the inner Generate button
        # (generate_seo_button) returns False so generation fires via the
        # auto flag, not the inner button.
        def _button(label, *a, **kw):
            return label == app.t("send_selected_to_seo")
        monkeypatch.setattr("app.st.button", _button)

        # render_seo_generation runs for real, so stub the global Streamlit
        # widgets it touches (status/progress/success/etc.) and its LLM handler.
        from types import SimpleNamespace as _NS
        monkeypatch.setattr("streamlit.divider", lambda: None)
        monkeypatch.setattr("streamlit.subheader", lambda *a, **kw: None)
        monkeypatch.setattr("streamlit.status", lambda *a, **kw: _NS(
            write=lambda *a, **kw: None,
            update=lambda *a, **kw: None,
            __enter__=lambda s: s,
            __exit__=lambda s, *a: False,
        ))
        monkeypatch.setattr("streamlit.progress", lambda *a, **kw: _NS(
            progress=lambda *a, **kw: None,
        ))
        monkeypatch.setattr("streamlit.success", lambda *a, **kw: None)
        monkeypatch.setattr("streamlit.info", lambda *a, **kw: None)
        monkeypatch.setattr("streamlit.warning", lambda *a, **kw: None)
        monkeypatch.setattr("streamlit.rerun", lambda: None)

        class _FakeLLM:
            def __init__(self, **kwargs):
                pass

            # GRACE: function generate_seo_text declaration.
            def generate_seo_text(self, **kwargs):
                return "META_TITLE: Test\nDESCRIPTION: Test body"

        monkeypatch.setattr("components.results.LLMHandler", _FakeLLM)

        # render_seo_generation is real (not stubbed) so we can observe the flag.
        from components.results import render_seo_generation as _real_render
        monkeypatch.setattr("app.render_seo_generation", _real_render)

        app.main()

        # The handoff button armed generation, and the real render_seo_generation
        # (armed by seo_auto_generate) must have produced the SEO text — proving
        # the handoff now actually generates instead of only staging an Excel.
        gen_df = st.session_state.get("generated_seo_texts")
        assert gen_df is not None and not gen_df.empty, (
            "SEO handoff button must trigger generation that produces SEO text"
        )
        assert "META_TITLE: Test" in str(gen_df.iloc[0].to_dict())
        # The one-shot flag must be consumed so it doesn't re-run on later renders.
        assert "seo_auto_generate" not in st.session_state

# GRACE: Purpose:  DummyContext implementation
    # GRACE: Purpose:   enter   implementation
    # GRACE: Purpose:   exit   implementation
# GRACE: Purpose:  TrackedForm implementation
    # GRACE: Purpose:   init   implementation
    # GRACE: Purpose:   enter   implementation
    # GRACE: Purpose:   exit   implementation
# GRACE: Purpose: Test workflow mode selector is rendered outside form
    # GRACE: Purpose:  fake selectbox implementation
# GRACE: Purpose: Test sync workflow mode updates session state from widget
# GRACE: Purpose: Test render input form syncs widget state with programmatic workflow change
    # GRACE: Purpose:  fake selectbox implementation
# GRACE: Purpose: Test render input form does not pass index when widget state exists
    # GRACE: Purpose:  fake selectbox implementation
# GRACE: Purpose: Test main ignores immediate duplicate form submission
# GRACE: Purpose: Test main allows same submission again after non submit rerun
# GRACE: Purpose: Test main routes google trends mode to trends workflow
    # GRACE: Purpose:  capture trends workflow implementation
# GRACE: Purpose: Test sidebar trends settings do not include enabled flag
    # GRACE: Purpose:  AvailableAdapter implementation
        # GRACE: Purpose: is available implementation
        # GRACE: Purpose: get trends implementation
# GRACE: Purpose: Test render serp math report shows full profile without fixed truncation
    # GRACE: Purpose:  DummyContext implementation
        # GRACE: Purpose:   enter   implementation
        # GRACE: Purpose:   exit   implementation
    # GRACE: Purpose:  subheader implementation
    # GRACE: Purpose:  write implementation
    # GRACE: Purpose:  checkbox implementation
# GRACE: Purpose: Test math analysis export sheets include bm25f scores
# GRACE: Purpose: Test render bm25f scores section uses localized ui labels
# GRACE: Purpose: Test render google trends results shows provider and confidence metadata
    # GRACE: Purpose:  DummyContext implementation
        # GRACE: Purpose:   enter   implementation
        # GRACE: Purpose:   exit   implementation
# GRACE: Purpose: Test render serp domain metrics exposes both xlsx and csv download
    # GRACE: Purpose:  FakeDomainMetrics implementation Purpose:  FakeDomainMetrics implementation
# GRACE: Purpose: Test render trends results exposes both xlsx and csv download
    # GRACE: Purpose:  DummyCtx implementation
        # GRACE: Purpose:   enter   implementation
        # GRACE: Purpose:   exit   implementation
# GRACE: Purpose: Test serp domain counts are derived from parsed rows
    # GRACE: Purpose:  FakeDomainMetrics implementation Purpose:  FakeDomainMetrics implementation
# GRACE: Purpose: Test sidebar trends provider selectbox is rendered
    # GRACE: Purpose:  fake selectbox implementation
# GRACE: Purpose: Test sidebar trends request options are rendered
    # GRACE: Purpose:  fake selectbox implementation
# GRACE: Purpose: Test sidebar hides unavailable trends providers and omits status messages
    # GRACE: Purpose:  UnavailableAdapter implementation
        # GRACE: Purpose: is available implementation
        # GRACE: Purpose: get trends implementation
    # GRACE: Purpose:  AvailableAdapter implementation
        # GRACE: Purpose: is available implementation
        # GRACE: Purpose: get trends implementation
    # GRACE: Purpose:  fake selectbox implementation
# GRACE: Purpose: Test sidebar returns empty trends provider when none available
    # GRACE: Purpose:  UnavailableAdapter implementation
        # GRACE: Purpose: is available implementation
        # GRACE: Purpose: get trends implementation
    # GRACE: Purpose:  fake selectbox implementation
# GRACE: Purpose: Test sidebar trends force refresh checkbox is rendered
    # GRACE: Purpose:  fake checkbox implementation
    # GRACE: Purpose:  fake selectbox implementation
# GRACE: Purpose: Test render history unique keys for entries with created at
    # GRACE: Purpose:  DummyCtx implementation
        # GRACE: Purpose:   enter   implementation
        # GRACE: Purpose:   exit   implementation
    # GRACE: Purpose:  fake button implementation
# GRACE: Purpose: Test render history unique keys without timestamp fields
    # GRACE: Purpose:  DummyCtx implementation
        # GRACE: Purpose:   enter   implementation
        # GRACE: Purpose:   exit   implementation
    # GRACE: Purpose:  fake button implementation
    # GRACE: Mock st.tabs to return a list of DummyCtx context managers Purpose:  fake tabs implementation
# GRACE: Purpose: Test render history shows cache records when toggled
    # GRACE: Purpose:  DummyCtx implementation
        # GRACE: Purpose:   enter   implementation
        # GRACE: Purpose:   exit   implementation
    # GRACE: Purpose:  fake button implementation
    # GRACE: Mock st.tabs — cache entry appears in All + Cache tabs = 2 expanders Purpose:  fake tabs implementation
# GRACE: Purpose: Test render history clear button clears history and cache
    # GRACE: Purpose:  DummyCtx implementation
        # GRACE: Purpose:   enter   implementation
        # GRACE: Purpose:   exit   implementation
    # GRACE: Purpose:  fake button implementation
# GRACE: Purpose: Verify _restore_cache_to_session handles real serialized payloads
    # GRACE: Purpose:  call restore implementation
    # GRACE: Purpose: Test dataframe payload restores to processed data
    # GRACE: Purpose: Test trends dataframe payload restores to trends results
    # GRACE: Purpose: Test math dict payload restores to serp math profile
    # GRACE: Purpose: Test missing result returns false
    # GRACE: Purpose: Test empty payload returns false
    # GRACE: Purpose: Test unknown kind returns false
    # GRACE: Purpose: Test empty dataframe payload returns false
    # GRACE: Purpose: Test list payload restores for serp
# GRACE: Purpose: Verify _deserialize_cache_payload handles all serialization formats
    # GRACE: Purpose:  call implementation
    # GRACE: Purpose: Test dataframe columns data format
    # GRACE: Purpose: Test plain list returns unchanged
    # GRACE: Purpose: Test plain dict without columns returns unchanged
    # GRACE: Purpose: Test scalar returns unchanged
# GRACE: ============================================================ Test: render_seo_results regenerate button ============================================================
    # GRACE: Button was clicked → flag should be set
    # GRACE: Flag survives render_seo_results — consumed later by workflow handler
# GRACE: ============================================================ Test: render_seo_generation respects force_refresh flag ============================================================
        # GRACE: Mock LLMHandler.generate_seo_text to capture force_refresh
            # GRACE: function __init__ declaration
    # GRACE: force_refresh should have been passed as True
            # GRACE: class FakeLLM declaration
# GRACE: ============================================================ Test: render_seo_generation auto-generate flag (URL_LLM handoff) ============================================================
            # GRACE: class FakeLLM declaration
            # GRACE: class FakeLLM declaration
# GRACE: ============================================================ Test: build_generated_text_math_profile ============================================================
    # GRACE: Should find terms from the generated text
# GRACE: ============================================================ Test: URL_LLM SEO handoff — "Generate SEO text" button after page scraping ============================================================
        # GRACE: Only the SEO button "clicks"
    # GRACE: The scraped-content selector must NOT render in the direct-SEO path
            # GRACE: class _FakeLLM declaration
