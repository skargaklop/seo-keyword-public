# Test coverage for modules: MOD-001,MOD-002,MOD-003,MOD-004,MOD-005
# MODULE_CONTRACT: tests/test_pipeline_workflows
# Purpose: Verify workflow orchestration across pipeline and result-rendering integration points.
# Rationale: Links pipeline workflow tests to GRACE workflow and results modules.
# Dependencies: pandas, pytest, streamlit, utils.pipeline.
# Exports: pytest tests.
# LINKS: knowledge-graph.xml#MOD-002, knowledge-graph.xml#MOD-007
# MODULE_MAP: tests/test_pipeline_workflows.py
# Public Functions: pytest test functions.
# Private Helpers: _DummyProgress, _DummyStatus.
# Key Semantic Blocks: none.
# Critical Flows: prepare workflow inputs -> invoke pipeline functions -> assert session/result structures.
# Verification: verification-plan.xml#V-MOD-002, verification-plan.xml#V-10-RESULTS-UI
# CHANGE_SUMMARY: Added GRACE module contract linking this test file to MOD-002 and MOD-007.

from contextlib import nullcontext

import pandas as pd
import pytest
import streamlit as st

import utils.pipeline as pipeline
from utils.scraper import ScrapedContent
from utils.google_trends_client import (
    GoogleTrendsInterestPoint,
    GoogleTrendsRequest,
    GoogleTrendsResult,
)


# Purpose:  DummyProgress implementation
class _DummyProgress:
    # Purpose: progress implementation
    def progress(self, *args, **kwargs) -> None:
        return None


# Purpose:  DummyStatus implementation
class _DummyStatus:
    # Purpose: text implementation
    def text(self, *args, **kwargs) -> None:
        return None

    # Purpose: success implementation
    def success(self, *args, **kwargs) -> None:
        return None


# Purpose:  reset streamlit state implementation
# Purpose:  reset streamlit state implementation
@pytest.fixture(autouse=True)
def _reset_streamlit_state(monkeypatch: pytest.MonkeyPatch) -> None:
    st.session_state.clear()
    monkeypatch.setattr("utils.pipeline.st.progress", lambda *args, **kwargs: _DummyProgress())
    monkeypatch.setattr("utils.pipeline.st.empty", lambda: _DummyStatus())
    monkeypatch.setattr("utils.pipeline.st.warning", lambda *args, **kwargs: None)
    monkeypatch.setattr("utils.pipeline.st.error", lambda *args, **kwargs: None)
    monkeypatch.setattr("utils.pipeline.st.expander", lambda *args, **kwargs: nullcontext())


# Purpose: TestSeedWorkflows implementation
class TestSeedWorkflows:
    # Purpose: Test llm url workflow preserves source url when metrics include empty source column
    def test_llm_url_workflow_preserves_source_url_when_metrics_include_empty_source_column(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "utils.pipeline.URLValidator.validate_urls",
            lambda urls: (urls, []),
        )
        monkeypatch.setattr(
            "utils.pipeline.WebScraper.scrape_urls",
            lambda *args, **kwargs: [
                ScrapedContent(
                    url="https://example.com",
                    text="scraped text",
                    success=True,
                )
            ],
        )
        monkeypatch.setattr(
            "utils.pipeline.KeywordProcessor.process_keywords",
            staticmethod(lambda keywords: keywords),
        )
        monkeypatch.setattr(
            "utils.pipeline.KeywordProcessor.deduplicate_across_sources",
            staticmethod(lambda source_keywords: source_keywords),
        )

        # Purpose:  FakeLLMHandler implementation
        class _FakeLLMHandler:
            # Purpose:   init   implementation
            def __init__(self, *args, **kwargs) -> None:
                pass

            # Purpose: generate keywords implementation
            def generate_keywords(
                self, text, provider, model, max_keywords, custom_prompt=""
            ):
                assert text == "scraped text"
                return ["buy boxes"]

        # Purpose:  FakeAdsHandler implementation
        class _FakeAdsHandler:
            # Purpose:   init   implementation
            def __init__(self, *args, **kwargs) -> None:
                pass

            # Purpose: get keyword metrics implementation
            def get_keyword_metrics(self, keywords):
                assert keywords == ["buy boxes"]
                return pd.DataFrame(
                    [
                        {
                            "Keyword": "buy boxes",
                            "Source URL": "",
                            "Avg Monthly Searches": 100,
                        }
                    ]
                )

        monkeypatch.setattr("utils.pipeline.LLMHandler", _FakeLLMHandler)
        monkeypatch.setattr("utils.pipeline.GoogleAdsHandler", _FakeAdsHandler)

        df = pipeline.run_llm_url_workflow(
            urls=["https://example.com"],
            provider="OpenAI",
            model="gpt-test",
            max_keywords=10,
            location_id="2840",
            language_id="1000",
            currency_code="USD",
        )

        assert df is not None
        assert df["Source URL"].tolist() == ["https://example.com"]
        assert st.session_state.scraped_content == {
            "https://example.com": "scraped text"
        }

    # Purpose: Test url seed workflow fetches ideas without scraper or llm
    def test_url_seed_workflow_fetches_ideas_without_scraper_or_llm(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "utils.pipeline.URLValidator.validate_urls",
            lambda urls: (urls, []),
        )
        monkeypatch.setattr(
            "utils.pipeline.WebScraper.scrape_urls",
            lambda *args, **kwargs: pytest.fail("scraper should not run for url_seed"),
        )
        monkeypatch.setattr(
            "utils.pipeline.LLMHandler",
            lambda *args, **kwargs: pytest.fail("LLM should not run for url_seed"),
        )

        # Purpose:  FakeAdsHandler implementation
        class _FakeAdsHandler:
            # Purpose:   init   implementation
            def __init__(self, *args, **kwargs) -> None:
                pass

            # Purpose: get keyword ideas implementation
            def get_keyword_ideas(self, seed_keywords, page_url=None, source_url=None):
                assert seed_keywords == []
                return pd.DataFrame(
                    [
                        {
                            "Keyword": f"idea for {source_url}",
                            "Source URL": source_url,
                            "Avg Monthly Searches": 120,
                        }
                    ]
                )

        monkeypatch.setattr("utils.pipeline.GoogleAdsHandler", _FakeAdsHandler)

        assert hasattr(pipeline, "run_url_seed_workflow")
        df = pipeline.run_url_seed_workflow(
            urls=["https://example.com", "https://example.org"],
            location_id="2840",
            language_id="1000",
            currency_code="USD",
        )

        assert df is not None
        assert df["Source URL"].tolist() == [
            "https://example.com",
            "https://example.org",
        ]
        assert st.session_state.processed_data.equals(df)
        assert st.session_state.scraped_content == {}

    # Purpose: Test keyword seed workflow uses synthetic source url
    def test_keyword_seed_workflow_uses_synthetic_source_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "utils.pipeline.GoogleAdsHandler",
            lambda *args, **kwargs: type(
                "_FakeAdsHandler",
                (),
                {
                    "get_keyword_ideas": staticmethod(
                        lambda seed_keywords, page_url=None, source_url=None: pd.DataFrame(
                            [
                                {
                                    "Keyword": "seed idea",
                                    "Source URL": source_url,
                                    "Avg Monthly Searches": 90,
                                }
                            ]
                        )
                    )
                },
            )(),
        )

        assert hasattr(pipeline, "run_keyword_seed_workflow")
        assert hasattr(pipeline, "KEYWORD_SEED_SOURCE_URL")
        df = pipeline.run_keyword_seed_workflow(
            seed_keywords=["alpha", " beta ", "alpha"],
            location_id="2840",
            language_id="1000",
            currency_code="USD",
        )

        assert df is not None
        assert df.loc[0, "Source URL"] == pipeline.KEYWORD_SEED_SOURCE_URL
        assert st.session_state.processed_data.equals(df)
        assert st.session_state.scraped_content == {}

    # Purpose: Test prepare urls for seo scrapes only on explicit transition
    def test_prepare_urls_for_seo_scrapes_only_on_explicit_transition(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "utils.pipeline.URLValidator.validate_urls",
            lambda urls: (urls, []),
        )
        scrape_calls = []

        # Purpose:  fake scrape implementation
        def _fake_scrape(urls, progress_callback=None, use_async=True):
            scrape_calls.append(list(urls))
            return [
                ScrapedContent(
                    url=urls[0],
                    text="scraped text",
                    success=True,
                )
            ]

        monkeypatch.setattr("utils.pipeline.WebScraper.scrape_urls", _fake_scrape)

        assert st.session_state.get("scraped_content") is None

        assert hasattr(pipeline, "prepare_urls_for_seo")
        scraped = pipeline.prepare_urls_for_seo(["https://example.com"])

        assert scrape_calls == [["https://example.com"]]
        assert scraped == {"https://example.com": "scraped text"}
        assert st.session_state.scraped_content == {"https://example.com": "scraped text"}

    # Purpose: Test prepare urls for seo warns when scraping returns no content
    def test_prepare_urls_for_seo_warns_when_scraping_returns_no_content(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "utils.pipeline.URLValidator.validate_urls",
            lambda urls: (urls, []),
        )
        monkeypatch.setattr(
            "utils.pipeline.WebScraper.scrape_urls",
            lambda *args, **kwargs: [
                ScrapedContent(
                    url="https://example.com",
                    success=False,
                    error="scrape failed",
                )
            ],
        )

        warning_messages = []
        monkeypatch.setattr(
            "utils.pipeline.st.warning",
            lambda message: warning_messages.append(message),
        )

        scraped = pipeline.prepare_urls_for_seo(["https://example.com"])

        assert scraped == {}
        assert st.session_state.scraped_content == {}
        assert warning_messages

    # Purpose: Test llm keyword stage from checkpoint skips scraper
    def test_llm_keyword_stage_from_checkpoint_skips_scraper(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "utils.pipeline.WebScraper.scrape_urls",
            lambda *args, **kwargs: pytest.fail("scraper should not run for checkpoint"),
        )
        monkeypatch.setattr(
            "utils.pipeline.KeywordProcessor.process_keywords",
            staticmethod(lambda keywords: keywords),
        )
        monkeypatch.setattr(
            "utils.pipeline.KeywordProcessor.deduplicate_across_sources",
            staticmethod(lambda source_keywords: source_keywords),
        )

        # Purpose:  FakeLLMHandler implementation
        class _FakeLLMHandler:
            # Purpose:   init   implementation
            def __init__(self, *args, **kwargs) -> None:
                pass

            # Purpose: generate keywords implementation
            def generate_keywords(
                self, text, provider, model, max_keywords, custom_prompt=""
            ):
                assert text == "cached content"
                assert provider == "OpenAI"
                assert model == "gpt-test"
                assert max_keywords == 10
                return ["купить коробки", "цена коробок"]

        # Purpose:  FakeAdsHandler implementation
        class _FakeAdsHandler:
            # Purpose:   init   implementation
            def __init__(self, *args, **kwargs) -> None:
                pass

            # Purpose: get keyword metrics implementation
            def get_keyword_metrics(self, keywords):
                assert keywords == ["купить коробки", "цена коробок"]
                return pd.DataFrame(
                    [
                        {
                            "Keyword": "купить коробки",
                            "Avg Monthly Searches": 100,
                        },
                        {
                            "Keyword": "цена коробок",
                            "Avg Monthly Searches": 80,
                        },
                    ]
                )

        monkeypatch.setattr("utils.pipeline.LLMHandler", _FakeLLMHandler)
        monkeypatch.setattr("utils.pipeline.GoogleAdsHandler", _FakeAdsHandler)

        assert hasattr(pipeline, "run_llm_keyword_stage_from_checkpoint")
        df = pipeline.run_llm_keyword_stage_from_checkpoint(
            scraped_content={"https://example.com": "cached content"},
            provider="OpenAI",
            model="gpt-test",
            max_keywords=10,
            location_id="2840",
            language_id="1000",
            currency_code="USD",
        )

        assert df is not None
        assert df["Keyword"].tolist() == ["купить коробки", "цена коробок"]
        assert df["Source URL"].tolist() == [
            "https://example.com",
            "https://example.com",
        ]
        assert st.session_state.scraped_content == {
            "https://example.com": "cached content"
        }

    # Purpose: Test llm keyword stage from checkpoint preserves source url when metrics include empty source column
    def test_llm_keyword_stage_from_checkpoint_preserves_source_url_when_metrics_include_empty_source_column(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "utils.pipeline.WebScraper.scrape_urls",
            lambda *args, **kwargs: pytest.fail("scraper should not run for checkpoint"),
        )
        monkeypatch.setattr(
            "utils.pipeline.KeywordProcessor.process_keywords",
            staticmethod(lambda keywords: keywords),
        )
        monkeypatch.setattr(
            "utils.pipeline.KeywordProcessor.deduplicate_across_sources",
            staticmethod(lambda source_keywords: source_keywords),
        )

        # Purpose:  FakeLLMHandler implementation
        class _FakeLLMHandler:
            # Purpose:   init   implementation
            def __init__(self, *args, **kwargs) -> None:
                pass

            # Purpose: generate keywords implementation
            def generate_keywords(
                self, text, provider, model, max_keywords, custom_prompt=""
            ):
                return ["buy boxes"]

        # Purpose:  FakeAdsHandler implementation
        class _FakeAdsHandler:
            # Purpose:   init   implementation
            def __init__(self, *args, **kwargs) -> None:
                pass

            # Purpose: get keyword metrics implementation
            def get_keyword_metrics(self, keywords):
                assert keywords == ["buy boxes"]
                return pd.DataFrame(
                    [
                        {
                            "Keyword": "buy boxes",
                            "Source URL": "",
                            "Avg Monthly Searches": 100,
                        }
                    ]
                )

        monkeypatch.setattr("utils.pipeline.LLMHandler", _FakeLLMHandler)
        monkeypatch.setattr("utils.pipeline.GoogleAdsHandler", _FakeAdsHandler)

        df = pipeline.run_llm_keyword_stage_from_checkpoint(
            scraped_content={"https://example.com": "cached content"},
            provider="OpenAI",
            model="gpt-test",
            max_keywords=10,
            location_id="2840",
            language_id="1000",
            currency_code="USD",
        )

        assert df is not None
        assert df["Source URL"].tolist() == ["https://example.com"]


# Purpose: TestGoogleTrendsWorkflow implementation
class TestGoogleTrendsWorkflow:
    # Purpose: Test google trends workflow rejects bare urls
    def test_google_trends_workflow_rejects_bare_urls(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        warnings: list[str] = []
        monkeypatch.setattr(
            "utils.pipeline.st.warning",
            lambda message: warnings.append(message),
        )
        monkeypatch.setattr(
            "utils.pipeline.TrendsOrchestrator",
            lambda *args, **kwargs: pytest.fail("Trends orchestrator should not receive bare URLs"),
        )

        result = pipeline.run_google_trends_workflow(
            keywords=["https://example.com/page"],
            trends_config={"enabled": True},
        )

        assert result is None
        assert warnings

    # Purpose: Test google trends workflow uses keywords and writes cache
    def test_google_trends_workflow_uses_keywords_and_writes_cache(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        requests_seen: list = []
        orchestrator_calls: list[dict] = []

        # Purpose:  FakeOrchestrator implementation
        class _FakeOrchestrator:
            # Purpose:   init   implementation
            def __init__(self, *args, **kwargs):
                orchestrator_calls.append({"args": args, "kwargs": kwargs})

            # Purpose: run trends implementation
            def run_trends(self, keywords, provider=None, force_refresh=False, settings=None):
                requests_seen.append(
                    {
                        "keywords": list(keywords),
                        "provider": provider,
                        "force_refresh": force_refresh,
                        "settings": settings,
                    }
                )
                request = GoogleTrendsRequest(keywords=list(keywords), geo="US")
                return GoogleTrendsResult(
                    request=request,
                    provider="serpapi_trends",
                    averages={"alpha keyword": 42.0},
                    provider_metadata={
                        "provider": "serpapi_trends",
                        "provider_version": "phase13-v1",
                        "endpoint_mode": "trends.interestByTime",
                    },
                    cache_metadata={"cache_key": "cache-123", "cache_hit": False},
                    data_confidence="high",
                )

        monkeypatch.setattr("utils.pipeline.TrendsOrchestrator", _FakeOrchestrator)

        result = pipeline.run_google_trends_workflow(
            keywords=["alpha keyword", "alpha keyword", "https://example.com"],
            trends_config={"enabled": True, "default_geo": "US"},
            force_refresh=True,
        )

        assert result is not None
        assert requests_seen[0]["keywords"] == ["alpha keyword"]
        assert requests_seen[0]["force_refresh"] is True
        assert orchestrator_calls
        assert result.cache_metadata["cache_key"] == "cache-123"
        assert st.session_state.google_trends_result is result
        assert "averages" in st.session_state.google_trends_tables

    # Purpose: Test google trends stage uses orchestrator and preserves selection
    def test_google_trends_stage_uses_orchestrator_and_preserves_selection(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        orchestrator_calls: list[dict] = []

        # Purpose:  FakeOrchestrator implementation
        class _FakeOrchestrator:
            # Purpose:   init   implementation
            def __init__(self, *args, **kwargs):
                orchestrator_calls.append({"args": args, "kwargs": kwargs})

            # Purpose: run trends implementation
            def run_trends(self, keywords, provider=None, force_refresh=False, settings=None):
                orchestrator_calls.append(
                    {
                        "keywords": list(keywords),
                        "provider": provider,
                        "force_refresh": force_refresh,
                        "settings": settings,
                    }
                )
                request = GoogleTrendsRequest(keywords=list(keywords), geo="UA")
                return GoogleTrendsResult(
                    request=request,
                    provider="serpapi_trends",
                    averages={"alpha keyword": 33.0},
                    provider_metadata={"provider": "serpapi_trends"},
                    data_confidence="high",
                )

        monkeypatch.setattr("utils.pipeline.TrendsOrchestrator", _FakeOrchestrator)

        result = pipeline.run_trends_stage_from_keywords(
            keywords=["alpha keyword", "https://example.com"],
            trends_config={"enabled": True, "provider": "serpapi_trends"},
            force_refresh=False,
        )

        assert result is not None
        assert orchestrator_calls[1]["keywords"] == ["alpha keyword"]
        assert orchestrator_calls[1]["provider"] == "serpapi_trends"
        assert st.session_state.google_trends_result is result

    # Purpose: Test trends tables calculate missing averages from timeline data
    def test_google_trends_tables_calculate_missing_zero_average_from_timeline(self) -> None:
        request = GoogleTrendsRequest(keywords=["ice cream"], geo="UA", timeframe="today 12-m")
        result = GoogleTrendsResult(
            request=request,
            provider="browser_scraper_trends",
            interest_over_time=[
                GoogleTrendsInterestPoint(
                    time="2026-06-07",
                    formatted_time="Jun 7, 2026",
                    values={"ice cream": 0},
                ),
                GoogleTrendsInterestPoint(
                    time="2026-06-14",
                    formatted_time="Jun 14, 2026",
                    values={"ice cream": 0},
                ),
            ],
            averages={},
        )

        tables = pipeline.google_trends_result_to_tables(result)
        averages = tables["averages"]

        assert len(averages) == 1
        assert averages.iloc[0]["Keyword"] == "ice cream"
        assert averages.iloc[0]["Average Interest"] == 0.0


# ---------------------------------------------------------------------------
# PLAN 15-02: Pipeline cache key and provider option tests
# ---------------------------------------------------------------------------


# Purpose: TestTrendsPipelineProviderOptions implementation
class TestTrendsPipelineProviderOptions:
    # Purpose: Test trends pipeline passes provider to orchestrator
    def test_trends_pipeline_passes_provider_to_orchestrator(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pipeline passes provider setting to TrendsOrchestrator."""
        orchestrator_calls: list[dict] = []

        # Purpose:  FakeOrchestrator implementation
        class _FakeOrchestrator:
            # Purpose:   init   implementation
            def __init__(self, *args, **kwargs):
                orchestrator_calls.append({"args": args, "kwargs": kwargs})

            # Purpose: run trends implementation
            def run_trends(self, keywords, provider=None, force_refresh=False, settings=None):
                request = GoogleTrendsRequest(keywords=list(keywords), geo="US")
                return GoogleTrendsResult(
                    request=request,
                    provider=provider or "google_trends_direct",
                    averages={},
                    provider_metadata={"provider": provider or "google_trends_direct"},
                    data_confidence="high",
                )

        monkeypatch.setattr("utils.pipeline.TrendsOrchestrator", _FakeOrchestrator)

        result = pipeline.run_google_trends_workflow(
            keywords=["seo"],
            trends_config={
                "enabled": True,
                "provider": "serpapi_trends",
                "default_geo": "US",
            },
        )

        assert result is not None
        settings_dict = orchestrator_calls[0]["kwargs"].get("settings") or orchestrator_calls[0]["args"][0] if orchestrator_calls[0]["args"] else orchestrator_calls[0]["kwargs"].get("settings")
        assert settings_dict is not None

    # Purpose: Test trends pipeline passes request options via settings
    def test_trends_pipeline_passes_request_options_via_settings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pipeline passes request options (timeframe, category, etc.) via settings dict."""
        captured_settings = []

        # Purpose:  FakeOrchestrator implementation
        class _FakeOrchestrator:
            # Purpose:   init   implementation
            def __init__(self, *args, **kwargs):
                captured_settings.append(kwargs.get("settings") or (args[0] if args else {}))

            # Purpose: run trends implementation
            def run_trends(self, keywords, provider=None, force_refresh=False, settings=None):
                request = GoogleTrendsRequest(keywords=list(keywords), geo="US")
                return GoogleTrendsResult(
                    request=request,
                    provider=provider or "google_trends_direct",
                    averages={},
                    provider_metadata={"provider": provider or "google_trends_direct"},
                    data_confidence="high",
                )

        monkeypatch.setattr("utils.pipeline.TrendsOrchestrator", _FakeOrchestrator)

        result = pipeline.run_google_trends_workflow(
            keywords=["seo"],
            trends_config={
                "enabled": True,
                "provider": "serpapi_trends",
                "default_geo": "US",
                "default_timeframe": "today 3-m",
                "default_category": 5,
                "default_gprop": "images",
            },
        )

        assert result is not None
        assert captured_settings[0].get("default_timeframe") == "today 3-m"
        assert captured_settings[0].get("default_category") == 5

    # Purpose: Test trends pipeline cache key differs by provider
    def test_trends_pipeline_cache_key_differs_by_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cache keys from pipeline must differ when provider changes."""
        cache_keys_seen = []

        # Purpose:  FakeOrchestrator implementation
        class _FakeOrchestrator:
            # Purpose:   init   implementation
            def __init__(self, *args, **kwargs):
                pass

            # Purpose: run trends implementation
            def run_trends(self, keywords, provider=None, force_refresh=False, settings=None):
                from utils.request_cache import build_trends_cache_key
                request = GoogleTrendsRequest(keywords=list(keywords), geo="US")
                cache_key = build_trends_cache_key(
                    provider=provider or "google_trends_direct",
                    endpoint_mode="trends.interestByTime",
                    params={**request.to_dict(), "normalized_keywords": request.keywords},
                )
                cache_keys_seen.append(cache_key)
                return GoogleTrendsResult(
                    request=request,
                    provider=provider or "google_trends_direct",
                    averages={},
                    provider_metadata={"provider": provider or "google_trends_direct"},
                    data_confidence="high",
                    cache_metadata={"cache_key": cache_key, "cache_hit": False},
                )

        monkeypatch.setattr("utils.pipeline.TrendsOrchestrator", _FakeOrchestrator)

        pipeline.run_google_trends_workflow(
            keywords=["seo"],
            trends_config={"provider": "google_trends_direct", "default_geo": "US"},
        )
        pipeline.run_google_trends_workflow(
            keywords=["seo"],
            trends_config={"provider": "serpapi_trends", "default_geo": "US"},
        )

        assert len(cache_keys_seen) == 2
        assert cache_keys_seen[0] != cache_keys_seen[1]

    # Purpose: Test trends orchestrator cache key includes options
    def test_trends_orchestrator_cache_key_includes_options(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cache keys differ when request options (timeframe) change."""
        from utils.request_cache import build_trends_cache_key

        key_12m = build_trends_cache_key(
            provider="serpapi_trends",
            endpoint_mode="trends.interestByTime",
            params={"keywords": ["seo"], "geo": "US", "timeframe": "today 12-m"},
        )
        key_3m = build_trends_cache_key(
            provider="serpapi_trends",
            endpoint_mode="trends.interestByTime",
            params={"keywords": ["seo"], "geo": "US", "timeframe": "today 3-m"},
        )
        assert key_12m != key_3m

    # Purpose: Test run trends stage from keywords passes provider
    def test_run_trends_stage_from_keywords_passes_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """run_trends_stage_from_keywords passes provider to orchestrator."""
        orchestrator_calls: list[dict] = []

        # Purpose:  FakeOrchestrator implementation
        class _FakeOrchestrator:
            # Purpose:   init   implementation
            def __init__(self, *args, **kwargs):
                orchestrator_calls.append({"args": args, "kwargs": kwargs})

            # Purpose: run trends implementation
            def run_trends(self, keywords, provider=None, force_refresh=False, settings=None):
                request = GoogleTrendsRequest(keywords=list(keywords), geo="UA")
                return GoogleTrendsResult(
                    request=request,
                    provider=provider or "google_trends_direct",
                    averages={"seo": 50.0},
                    provider_metadata={"provider": provider or "google_trends_direct"},
                    data_confidence="high",
                )

        monkeypatch.setattr("utils.pipeline.TrendsOrchestrator", _FakeOrchestrator)

        result = pipeline.run_trends_stage_from_keywords(
            keywords=["seo", "marketing"],
            trends_config={
                "enabled": True,
                "provider": "dataforseo_trends",
                "default_geo": "UA",
            },
            force_refresh=False,
        )

        assert result is not None
        settings_dict = orchestrator_calls[0]["kwargs"].get("settings") or orchestrator_calls[0]["args"][0] if orchestrator_calls[0]["args"] else orchestrator_calls[0]["kwargs"].get("settings")
        assert settings_dict is not None
