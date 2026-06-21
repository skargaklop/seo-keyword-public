"""Focused tests for pipeline deduplication helpers.

These cover the refactor surface only: URL validation, keyword grouping and
processing, SERP row accumulation, Trends orchestration/state storage, and
math profile block extraction.
"""

import importlib
from types import ModuleType, SimpleNamespace
import sys

import pandas as pd
import pytest


if "tenacity" not in sys.modules:
    tenacity_stub = ModuleType("tenacity")

    class _Retrying:
        def __iter__(self):
            return iter(())

    class _RetryCallState:
        pass

    def _identity_decorator(*args, **kwargs):
        def _decorator(fn):
            return fn

        return _decorator

    def _noop(*args, **kwargs):
        return None

    tenacity_stub.Retrying = _Retrying
    tenacity_stub.RetryCallState = _RetryCallState
    tenacity_stub.retry = _identity_decorator
    tenacity_stub.retry_if_exception = _noop
    tenacity_stub.retry_if_exception_type = _noop
    tenacity_stub.stop_after_attempt = _noop
    tenacity_stub.wait_exponential = _noop
    tenacity_stub.wait_fixed = _noop
    tenacity_stub.before_sleep_log = lambda *args, **kwargs: _identity_decorator
    sys.modules["tenacity"] = tenacity_stub

for _module_name in ("trafilatura", "aiohttp"):
    if _module_name not in sys.modules:
        sys.modules[_module_name] = ModuleType(_module_name)

if "bs4" not in sys.modules:
    bs4_stub = ModuleType("bs4")

    class _BeautifulSoup:
        def __init__(self, markup, parser=None) -> None:
            self.markup = markup

        def get_text(self, *args, **kwargs):
            return str(self.markup)

    bs4_stub.BeautifulSoup = _BeautifulSoup
    sys.modules["bs4"] = bs4_stub

if "aiohttp" in sys.modules:
    aiohttp_stub = sys.modules["aiohttp"]

    class _AiohttpClientError(Exception):
        pass

    class _AiohttpClientConnectorCertificateError(_AiohttpClientError):
        pass

    class _AiohttpClientTimeout:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

    class _AiohttpClientResponse:
        def __init__(self) -> None:
            self.connection = None
            self._protocol = None

    class _AiohttpClientSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    aiohttp_stub.ClientError = _AiohttpClientError
    aiohttp_stub.ClientConnectorCertificateError = _AiohttpClientConnectorCertificateError
    aiohttp_stub.ClientTimeout = _AiohttpClientTimeout
    aiohttp_stub.ClientResponse = _AiohttpClientResponse
    aiohttp_stub.ClientSession = _AiohttpClientSession

import streamlit as st  # noqa: E402
import utils.pipeline as pipeline  # noqa: E402


class _SessionState(dict):
    def clear(self) -> None:  # type: ignore[override]
        super().clear()

    def __getattr__(self, item):
        return self.get(item)

    def __setattr__(self, key, value):
        self[key] = value


class _DummyProgress:
    def progress(self, *args, **kwargs) -> None:
        return None


class _DummyStatus:
    def text(self, *args, **kwargs) -> None:
        return None

    def success(self, *args, **kwargs) -> None:
        return None


@pytest.fixture(autouse=True)
def _reset_streamlit_state(monkeypatch: pytest.MonkeyPatch) -> None:
    st.session_state.clear()

    monkeypatch.setattr(pipeline.st, "progress", lambda *args, **kwargs: _DummyProgress())
    monkeypatch.setattr(pipeline.st, "empty", lambda: _DummyStatus())
    monkeypatch.setattr(pipeline.st, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "error", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "info", lambda *args, **kwargs: None)


def test_pipeline_deduplication_import_keeps_streamlit_real_for_later_app_import() -> None:
    saved_app = sys.modules.pop("app", None)

    try:
        app_module = importlib.import_module("app")
        assert app_module.st is st
    finally:
        if saved_app is not None:
            sys.modules["app"] = saved_app
        else:
            sys.modules.pop("app", None)


def test_collect_keyword_groups_from_csv_rows_handles_keyword_column_and_plain_rows() -> None:
    from utils.pipeline import _build_keyword_groups_from_csv_rows

    grouped_rows = [
        {"keywords": "alpha, beta; gamma"},
        {"keywords": "delta"},
    ]
    plain_rows = [
        {"one": "alpha", "two": "beta"},
        {"one": "", "two": "gamma"},
    ]

    grouped = _build_keyword_groups_from_csv_rows(grouped_rows, has_header=True)
    plain = _build_keyword_groups_from_csv_rows(plain_rows, has_header=False)

    assert grouped == [
        {"group_id": 1, "keywords": ["alpha", "beta", "gamma"]},
        {"group_id": 2, "keywords": ["delta"]},
    ]
    assert plain == [
        {"group_id": 1, "keywords": ["alpha", "beta"]},
        {"group_id": 2, "keywords": ["gamma"]},
    ]


def test_validate_urls_for_pipeline_filters_invalid_and_renders_details(monkeypatch: pytest.MonkeyPatch) -> None:
    from utils.pipeline import _validated_urls_for_pipeline

    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "utils.pipeline.URLValidator.validate_urls",
        staticmethod(lambda urls: (["https://example.com"], [{"url": "bad"}])),
    )
    monkeypatch.setattr(
        "utils.pipeline._render_invalid_url_details",
        lambda invalid_results: captured.setdefault("invalid", list(invalid_results)),
    )

    valid_urls = _validated_urls_for_pipeline(["bad", "https://example.com"])

    assert valid_urls == ["https://example.com"]
    assert captured["invalid"] == [{"url": "bad"}]


def test_build_pipeline_feedback_returns_streamlit_handles(monkeypatch: pytest.MonkeyPatch) -> None:
    from utils.pipeline import _build_pipeline_feedback

    progress_marker = object()
    status_marker = object()

    monkeypatch.setattr("utils.pipeline.st.progress", lambda *args, **kwargs: progress_marker)
    monkeypatch.setattr("utils.pipeline.st.empty", lambda: status_marker)

    progress_bar, status_text, run_prefix = _build_pipeline_feedback("42")

    assert progress_bar is progress_marker
    assert status_text is status_marker
    assert run_prefix == "[run 42] "


def test_process_keyword_sources_for_ads_deduplicates_and_keeps_first_url(monkeypatch: pytest.MonkeyPatch) -> None:
    from utils.pipeline import _process_keyword_sources_for_ads

    monkeypatch.setattr(
        "utils.pipeline.KeywordProcessor.process_keywords",
        staticmethod(lambda keywords: [kw.strip().upper() for kw in keywords]),
    )
    monkeypatch.setattr(
        "utils.pipeline.KeywordProcessor.deduplicate_across_sources",
        staticmethod(
            lambda processed: {
                "https://one.example": ["ALPHA", "BETA"],
                "https://two.example": ["GAMMA"],
            }
        ),
    )

    processed, all_keywords, keyword_to_url = _process_keyword_sources_for_ads(
        {
            "https://one.example": ["alpha", "beta"],
            "https://two.example": ["gamma"],
        }
    )

    assert processed == {
        "https://one.example": ["ALPHA", "BETA"],
        "https://two.example": ["GAMMA"],
    }
    assert all_keywords == ["ALPHA", "BETA", "GAMMA"]
    assert keyword_to_url == {
        "ALPHA": "https://one.example",
        "BETA": "https://one.example",
        "GAMMA": "https://two.example",
    }


def test_finalize_keyword_ads_workflow_handles_empty_and_success_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    from utils.pipeline import _finalize_keyword_ads_workflow

    class _RecordingProgress:
        def __init__(self) -> None:
            self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def progress(self, *args, **kwargs) -> None:
            self.calls.append((args, kwargs))

    class _FakeHandler:
        def __init__(self, location_id, language_id, target_currency_code) -> None:
            self.location_id = location_id
            self.language_id = language_id
            self.target_currency_code = target_currency_code

    progress_bar = _RecordingProgress()
    status_text = _DummyStatus()
    warnings: list[str] = []

    monkeypatch.setattr("utils.pipeline._format_pipeline_message", lambda key, **kwargs: key)
    monkeypatch.setattr("utils.pipeline.st.warning", lambda message: warnings.append(message))

    empty_result = _finalize_keyword_ads_workflow(
        all_keywords=[],
        keyword_to_url={},
        location_id="loc",
        language_id="lang",
        currency_code="USD",
        scraped_content={},
        progress_bar=progress_bar,
        status_text=status_text,
        run_prefix="[run 1] ",
        completion_log_message="ignored",
        force_refresh=False,
    )

    assert empty_result is None
    assert warnings == ["pipeline_no_keywords_found"]
    assert progress_bar.calls == [((1.0,), {})]

    warnings.clear()
    progress_bar.calls.clear()
    captured: dict[str, object] = {}

    monkeypatch.setattr("utils.pipeline.GoogleAdsHandler", _FakeHandler)
    monkeypatch.setattr(
        "utils.pipeline._get_keyword_metrics_with_optional_cache",
        lambda ads_handler, all_keywords, force_refresh=False: pd.DataFrame([{"Keyword": "alpha"}]),
    )
    def _capture_finalize(**kwargs):
        captured["kwargs"] = kwargs
        return "finalized"

    monkeypatch.setattr("utils.pipeline._finalize_keyword_metrics_workflow", _capture_finalize)

    success_result = _finalize_keyword_ads_workflow(
        all_keywords=["alpha", "beta"],
        keyword_to_url={"alpha": "https://one.example", "beta": "https://two.example"},
        location_id="loc",
        language_id="lang",
        currency_code="USD",
        scraped_content={"https://one.example": "content"},
        progress_bar=progress_bar,
        status_text=status_text,
        run_prefix="[run 2] ",
        completion_log_message="completed",
        force_refresh=True,
    )

    assert success_result == "finalized"
    assert isinstance(captured["kwargs"]["metrics_df"], pd.DataFrame)
    assert captured["kwargs"]["all_keywords"] == ["alpha", "beta"]
    assert captured["kwargs"]["keyword_to_url"] == {
        "alpha": "https://one.example",
        "beta": "https://two.example",
    }


def test_collect_serp_rows_preserves_context_and_related_queries() -> None:
    from utils.pipeline import EMPTY_SOURCE_URL, _collect_serp_rows

    results = [
        SimpleNamespace(
            success=True,
            keyword="alpha",
            provider="serper",
            organic=[
                SimpleNamespace(
                    position=1,
                    title="Alpha title",
                    url="https://alpha.example",
                    snippet="Alpha snippet",
                    displayed_link="alpha.example",
                    rich_snippet_text="alpha rich",
                )
            ],
            related_searches=["alpha related"],
            people_also_ask=[SimpleNamespace(question="alpha question")],
            error=None,
        ),
        SimpleNamespace(
            success=False,
            keyword="beta",
            provider="serper",
            organic=[],
            related_searches=[],
            people_also_ask=[],
            error="boom",
        ),
    ]

    rows, related_data, failed_keywords = _collect_serp_rows(
        results,
        source_contexts=[("alpha", "https://source.example"), ("beta", EMPTY_SOURCE_URL)],
    )

    assert rows == [
        {
            "Keyword": "alpha",
            "Position": 1,
            "Title": "Alpha title",
            "URL": "https://alpha.example",
            "Snippet": "Alpha snippet",
            "Displayed Link": "alpha.example",
            "Rich Snippet": "alpha rich",
            "Provider": "serper",
            "source_context_key": ("alpha", "https://source.example"),
        }
    ]
    assert related_data == [
        {"Keyword": "alpha", "Related Query": "alpha related", "Type": "related_search"},
        {"Keyword": "alpha", "Related Query": "alpha question", "Type": "people_also_ask"},
    ]
    assert failed_keywords == [("beta", "boom")]


def test_finalize_serp_results_workflow_handles_empty_and_success_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    from utils.pipeline import _finalize_serp_results_workflow

    class _RecordingProgress:
        def __init__(self) -> None:
            self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def progress(self, *args, **kwargs) -> None:
            self.calls.append((args, kwargs))

    class _RecordingStatus:
        def __init__(self) -> None:
            self.text_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
            self.success_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def text(self, *args, **kwargs) -> None:
            self.text_calls.append((args, kwargs))

        def success(self, *args, **kwargs) -> None:
            self.success_calls.append((args, kwargs))

    progress_bar = _RecordingProgress()
    status_text = _RecordingStatus()
    events: list[tuple[str, object]] = []

    monkeypatch.setattr("utils.pipeline._format_pipeline_message", lambda key, **kwargs: key)
    monkeypatch.setattr("utils.pipeline.st.warning", lambda message: events.append(("warning", message)))
    monkeypatch.setattr("utils.pipeline.st.info", lambda message: events.append(("info", message)))

    empty_result = _finalize_serp_results_workflow(
        rows=[],
        related_data=[{"Keyword": "alpha"}],
        failed_keywords=[("alpha", "boom")],
        progress_bar=progress_bar,
        status_text=status_text,
        run_prefix="[run 3] ",
        result_columns=["Keyword"],
        completion_log_message="ignored",
        on_success=lambda df: events.append(("success", df)),
    )

    assert empty_result is None
    assert events == [("warning", "Some keywords failed: alpha"), ("info", "serp_no_results")]
    assert progress_bar.calls == [((1.0,), {"text": "pipeline_done"})]
    assert status_text.text_calls == [(( "serp_no_results",), {})]

    events.clear()
    progress_bar.calls.clear()
    status_text.text_calls.clear()
    status_text.success_calls.clear()
    captured_frames: list[pd.DataFrame] = []

    success_result = _finalize_serp_results_workflow(
        rows=[{"Keyword": "alpha", "Position": 1}],
        related_data=[{"Keyword": "alpha"}],
        failed_keywords=[],
        progress_bar=progress_bar,
        status_text=status_text,
        run_prefix="[run 4] ",
        result_columns=["Keyword", "Position"],
        completion_log_message="SERP analysis completed",
        on_success=lambda df: captured_frames.append(df),
    )

    assert isinstance(success_result, pd.DataFrame)
    assert captured_frames and list(captured_frames[0]["Keyword"]) == ["alpha"]
    assert progress_bar.calls == [((1.0,), {"text": "pipeline_done"})]
    assert status_text.success_calls == [(( "serp_analysis_complete",), {})]


def test_store_tupled_keyword_candidate_state_converts_and_persists(monkeypatch: pytest.MonkeyPatch) -> None:
    from utils.pipeline import _store_tupled_keyword_candidate_state

    url_to_keywords = {
        "https://one.example": ["alpha", "beta"],
        "https://two.example": ["gamma"],
    }

    candidates = _store_tupled_keyword_candidate_state(url_to_keywords, run_id="run-9")

    assert [candidate.keyword for candidate in candidates] == ["alpha", "beta", "gamma"]
    assert [candidate.source_url for candidate in candidates] == [
        "https://one.example",
        "https://one.example",
        "https://two.example",
    ]
    assert st.session_state[pipeline.SESSION_KEY_STAGED_KEYWORDS] == candidates
    assert st.session_state[pipeline.SESSION_KEY_LAST_EXTRACTION_RUN_ID] == "run-9"
    assert st.session_state[pipeline.SESSION_KEY_ACTIVE_SOURCE_URLS] == [
        "https://one.example",
        "https://two.example",
    ]


def test_run_trends_stage_stores_result_and_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    from utils.pipeline import _run_trends_stage

    class _FakeResult:
        def __init__(self) -> None:
            self.cache_metadata = {"cache_key": "abc123", "cache_hit": True, "cache_hit_count": 2}
            self.failures = []
            self.provider = "provider"
            self.request = SimpleNamespace(geo="UA", timeframe="today 12-m")

        def has_data(self) -> bool:
            return True

    class _FakeOrchestrator:
        def __init__(self, settings):
            self.settings = settings

        def run_trends(self, keywords, provider=None, force_refresh=False, settings=None):
            assert keywords == ["alpha", "beta"]
            return _FakeResult()

    monkeypatch.setattr("utils.pipeline.TrendsOrchestrator", _FakeOrchestrator)
    monkeypatch.setattr(
        "utils.pipeline.google_trends_result_to_tables",
        lambda result: {"averages": pd.DataFrame([{"Keyword": "alpha"}])},
    )
    monkeypatch.setattr("utils.pipeline.t", lambda key, **kwargs: key)

    result = _run_trends_stage(
        ["alpha", "beta"],
        {"enabled": True, "provider": "fake"},
        run_prefix="[run 1] ",
        force_refresh=False,
    )

    assert result.cache_metadata["cache_key"] == "abc123"
    assert st.session_state.google_trends_result is result
    assert "averages" in st.session_state.google_trends_tables


def test_apply_text_analysis_profile_populates_profile_and_bm25f_scores(monkeypatch: pytest.MonkeyPatch) -> None:
    from utils.pipeline import TextSource, _apply_text_analysis_profile

    monkeypatch.setattr(
        "utils.pipeline._normalize_for_hashing",
        lambda corpus: "hash-" + str(len(corpus)),
    )
    monkeypatch.setattr(
        "utils.pipeline.extract_ngrams",
        lambda **kwargs: [SimpleNamespace(ngram=f"n{kwargs['n']}")],
    )
    monkeypatch.setattr(
        "utils.pipeline.compute_tfidf",
        lambda **kwargs: [SimpleNamespace(term="tf1"), SimpleNamespace(term="tf2")],
    )
    monkeypatch.setattr(
        "utils.pipeline.compute_cooccurrence_terms",
        lambda **kwargs: [SimpleNamespace(term="co1")],
    )
    monkeypatch.setattr(
        "utils.pipeline.analyze_intent",
        lambda **kwargs: SimpleNamespace(intent_type="informational"),
    )
    monkeypatch.setattr(
        "utils.pipeline.build_field_weighted_profile",
        lambda corpus, config: SimpleNamespace(
            field_weights={"title": 3.0},
            field_b_params={"title": 0.75},
        ),
    )
    monkeypatch.setattr(
        "utils.pipeline.compute_bm25f",
        lambda **kwargs: ["bm25"],
    )

    profile = {"ngrams_by_size": {}, "tfidf_terms": [], "cooccurrence_terms": [], "intent": None, "bm25f_scores": []}
    corpus = [TextSource(text="alpha beta", field="body", weight=1.0)]

    result = _apply_text_analysis_profile(
        profile=profile,
        corpus=corpus,
        config={
            "analyze_ngrams": True,
            "analyze_tfidf": True,
            "analyze_cooccurrence": True,
            "analyze_intent": True,
            "analyze_bm25f": True,
            "bm25f_params": {"k1": 1.2},
        },
        strip_suffixes=False,
        ngram_min=1,
        ngram_max=2,
        min_ngram_count=1,
        min_df=1,
        top_terms_limit=5,
    )

    assert result["ngrams_by_size"][1][0].ngram == "n1"
    assert result["ngrams_by_size"][2][0].ngram == "n2"
    assert [term.term for term in result["tfidf_terms"]] == ["tf1", "tf2"]
    assert [term.term for term in result["cooccurrence_terms"]] == ["co1"]
    assert result["intent"].intent_type == "informational"
    assert result["bm25f_scores"] == ["bm25"]
