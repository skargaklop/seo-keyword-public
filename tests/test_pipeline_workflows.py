from contextlib import nullcontext

import pandas as pd
import pytest
import streamlit as st

import utils.pipeline as pipeline
from utils.scraper import ScrapedContent


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
    monkeypatch.setattr("utils.pipeline.st.progress", lambda *args, **kwargs: _DummyProgress())
    monkeypatch.setattr("utils.pipeline.st.empty", lambda: _DummyStatus())
    monkeypatch.setattr("utils.pipeline.st.warning", lambda *args, **kwargs: None)
    monkeypatch.setattr("utils.pipeline.st.error", lambda *args, **kwargs: None)
    monkeypatch.setattr("utils.pipeline.st.expander", lambda *args, **kwargs: nullcontext())


class TestSeedWorkflows:
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

        class _FakeLLMHandler:
            def __init__(self, *args, **kwargs) -> None:
                pass

            def generate_keywords(
                self, text, provider, model, max_keywords, custom_prompt=""
            ):
                assert text == "scraped text"
                return ["buy boxes"]

        class _FakeAdsHandler:
            def __init__(self, *args, **kwargs) -> None:
                pass

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

        class _FakeAdsHandler:
            def __init__(self, *args, **kwargs) -> None:
                pass

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

    def test_prepare_urls_for_seo_scrapes_only_on_explicit_transition(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "utils.pipeline.URLValidator.validate_urls",
            lambda urls: (urls, []),
        )
        scrape_calls = []

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

        class _FakeLLMHandler:
            def __init__(self, *args, **kwargs) -> None:
                pass

            def generate_keywords(
                self, text, provider, model, max_keywords, custom_prompt=""
            ):
                assert text == "cached content"
                assert provider == "OpenAI"
                assert model == "gpt-test"
                assert max_keywords == 10
                return ["купить коробки", "цена коробок"]

        class _FakeAdsHandler:
            def __init__(self, *args, **kwargs) -> None:
                pass

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

        class _FakeLLMHandler:
            def __init__(self, *args, **kwargs) -> None:
                pass

            def generate_keywords(
                self, text, provider, model, max_keywords, custom_prompt=""
            ):
                return ["buy boxes"]

        class _FakeAdsHandler:
            def __init__(self, *args, **kwargs) -> None:
                pass

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
