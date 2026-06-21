# Test: Phase 8 Workflow - Keyword-Gated SERP and Bidirectional Ads Chaining
# Tests for PLAN 08-01: SERP never receives bare URL input; keyword candidates gated workflows

import pandas as pd
from utils.pipeline import (
    is_url_like_query,
    filter_serp_eligible_keywords,
    store_keyword_candidates,
    get_selected_keyword_candidates,
    SOURCE_LLM_EXTRACTION,
    SOURCE_ADS_URL_SEED,
    SOURCE_KEYWORD_INPUT,
)
from components.results import _run_serp_after_ads_keywords


# Purpose: Test URL-like query detection for SERP keyword guarding.
class TestURLLikeQueryDetection:

    # Purpose: Should detect URLs starting with http://
    def test_detects_http_url(self):
        assert is_url_like_query("http://example.com") is True

    # Purpose: Should detect URLs starting with https://
    def test_detects_https_url(self):
        assert is_url_like_query("https://example.com") is True

    # Purpose: Should detect www domain pattern
    def test_detects_www_domain(self):
        assert is_url_like_query("www.example.com") is True

    # Purpose: Should allow plain keyword strings
    def test_allows_plain_keyword(self):
        assert is_url_like_query("buy shoes online") is False

    # Purpose: Should allow multi-word keywords
    def test_allows_keyword_with_spaces(self):
        assert is_url_like_query("best running shoes 2024") is False

    # Purpose: Should allow single word keywords
    def test_allows_single_word(self):
        assert is_url_like_query("shoes") is False

    # Purpose: Should handle empty strings gracefully
    def test_allows_empty_string(self):
        assert is_url_like_query("") is False
        assert is_url_like_query("   ") is False

    # Purpose: Should detect domain.tld pattern
    def test_detects_domain_without_www(self):
        assert is_url_like_query("example.com") is True

    # Purpose: Should allow keywords with special characters but not URLs
    def test_allows_keywords_with_special_chars(self):
        assert is_url_like_query("shoes & accessories") is False
        assert is_url_like_query("men's shoes") is False


# Purpose: Test filtering of SERP-eligible keywords.
class TestSERPEligibleFiltering:

    # Purpose: Should filter out a single URL from keyword list
    def test_filters_single_url(self):
        keywords = ["buy shoes", "https://example.com", "best shoes"]
        result = filter_serp_eligible_keywords(keywords)
        assert result == ["buy shoes", "best shoes"]

    # Purpose: Should filter out multiple URLs
    def test_filters_multiple_urls(self):
        keywords = [
            "http://site1.com",
            "keyword1",
            "https://site2.com",
            "keyword2",
            "www.site3.com",
        ]
        result = filter_serp_eligible_keywords(keywords)
        assert result == ["keyword1", "keyword2"]

    # Purpose: Should pass through all keywords when no URLs present
    def test_passes_all_keywords(self):
        keywords = ["shoes", "boots", "sandals"]
        result = filter_serp_eligible_keywords(keywords)
        assert result == keywords

    # Purpose: Should handle empty list gracefully
    def test_handles_empty_list(self):
        result = filter_serp_eligible_keywords([])
        assert result == []

    # Purpose: Should return empty list when all inputs are URLs
    def test_handles_all_urls(self):
        keywords = ["http://a.com", "https://b.com", "www.c.com"]
        result = filter_serp_eligible_keywords(keywords)
        assert result == []

    # Purpose: Should preserve duplicates in input (deduplication happens elsewhere)
    def test_preserves_duplicates(self):
        keywords = ["shoes", "http://example.com", "shoes", "boots"]
        result = filter_serp_eligible_keywords(keywords)
        assert "shoes" in result
        assert result.count("shoes") == 2  # Preserves original order and count


# Purpose: Test keyword candidate storage and retrieval.
class TestKeywordCandidateStorage:

    # Purpose: Clear session state before each test
    def setup_method(self):
        import streamlit as st

        if hasattr(st, "session_state"):
            st.session_state.clear()

    # Purpose: Should store and retrieve keyword candidates
    def test_store_and_retrieve_candidates(self):
        import streamlit as st

        keywords = ["shoes", "boots"]
        store_keyword_candidates(
            keywords=keywords,
            source_url="http://example.com",
            source_type=SOURCE_LLM_EXTRACTION,
            selection_prefix="test_stage",
        )

        candidates_key = "kw_candidates_test_stage"
        assert candidates_key in st.session_state
        candidates = st.session_state[candidates_key]
        assert len(candidates) == 2
        assert candidates[0]["keyword"] == "shoes"
        assert candidates[0]["source_url"] == "http://example.com"
        assert candidates[0]["source_type"] == SOURCE_LLM_EXTRACTION

    # Purpose: Should return empty list when no checkboxes selected
    def test_selected_keywords_default_empty(self):
        keywords = ["shoes", "boots"]
        store_keyword_candidates(
            keywords=keywords,
            source_url="http://example.com",
            source_type=SOURCE_KEYWORD_INPUT,
            selection_prefix="test_select",
        )

        selected = get_selected_keyword_candidates("test_select")
        assert selected == []

    # Purpose: Should return selected keywords based on checkbox state
    def test_selected_keywords_with_checkboxes(self):
        import streamlit as st

        keywords = ["shoes", "boots"]
        store_keyword_candidates(
            keywords=keywords,
            source_url="http://example.com",
            source_type=SOURCE_KEYWORD_INPUT,
            selection_prefix="test_check",
        )

        # Simulate checkbox selection
        st.session_state["test_check::shoes"] = True
        st.session_state["test_check::boots"] = False

        selected = get_selected_keyword_candidates("test_check")
        assert selected == ["shoes"]

    # Purpose: Should store candidates with Ads metrics
    def test_candidates_with_ads_metrics(self):
        import streamlit as st

        keywords = ["shoes"]
        ads_metrics = {"shoes": {"volume": 1000, "cpc": 0.5}}
        store_keyword_candidates(
            keywords=keywords,
            source_url="http://example.com",
            source_type=SOURCE_ADS_URL_SEED,
            selection_prefix="test_ads",
            ads_metrics=ads_metrics,
        )

        candidates_key = "kw_candidates_test_ads"
        candidates = st.session_state[candidates_key]
        assert candidates[0]["ads_metrics"] == ads_metrics["shoes"]


# Purpose: Regression tests for URL-to-SERP bug (PLAN 08-01 Task 7).
class TestSERPKeywordGuardRegression:

    # Purpose: URL workflow should not call SERP with raw URL strings
    def test_url_workflow_does_not_call_serp_with_url(self, monkeypatch):
        from utils.pipeline import run_serp_analysis_workflow
        import streamlit as st

        # Mock the SERP client to capture calls
        calls = []

        # Purpose: mock create client implementation
        def mock_create_client(config=None):
            class MockClient:
                provider = "mock_provider"
                num_results = 10
                gl = "US"
                hl = "en"
                extra_params = {}

                def search_batch(self, keywords, progress_callback=None):
                    calls.append(keywords)
                    return []

            return MockClient()

        monkeypatch.setattr(
            "utils.pipeline.create_serp_client", mock_create_client
        )

        # Initialize session state
        if hasattr(st, "session_state"):
            st.session_state.clear()

        # Submit URL-like input
        run_serp_analysis_workflow(
            keywords=["https://example.com"], run_id="test123"
        )

        # SERP should not be called with URL (guard filters it out)
        assert len(calls) == 0 or (
            len(calls) > 0 and all(
                "https://example.com" not in call for call in calls
            )
        )

    # Purpose: Keyword workflow should call SERP with keyword strings
    def test_keyword_workflow_calls_serp_with_keywords(self, monkeypatch):
        from utils.pipeline import run_serp_analysis_workflow
        import streamlit as st

        # Mock the SERP client
        calls = []

        # Purpose: mock create client implementation
        def mock_create_client(config=None):
            class MockClient:
                provider = "mock_provider"
                num_results = 10
                gl = "US"
                hl = "en"
                extra_params = {}

                def search_batch(self, keywords, progress_callback=None):
                    calls.append(keywords)
                    return []

            return MockClient()

        monkeypatch.setattr(
            "utils.pipeline.create_serp_client", mock_create_client
        )

        # Initialize session state
        if hasattr(st, "session_state"):
            st.session_state.clear()

        # Submit keyword input
        run_serp_analysis_workflow(
            keywords=["running shoes", "best sneakers"], run_id="test456"
        )

        # SERP should be called with keywords
        assert len(calls) > 0
        assert "running shoes" in calls[0] or "best sneakers" in calls[0]


# Purpose: Regression tests for post-Ads SERP handoff in URL workflows.
class TestPostAdsSERPHandoffRegression:

    # Purpose: setup method implementation
    def setup_method(self):
        import streamlit as st

        st.session_state.clear()

    # Purpose: Test url llm ads results handoff selected keywords to serp
    def test_url_llm_ads_results_handoff_selected_keywords_to_serp(self, monkeypatch):
        import streamlit as st

        ads_df = pd.DataFrame(
            [
                {
                    "Source URL": "https://example.com/blog/llm",
                    "Keyword": "best running shoes",
                    "Avg Monthly Searches": 100,
                },
                {
                    "Source URL": "https://example.com/blog/llm",
                    "Keyword": "trail running shoes",
                    "Avg Monthly Searches": 80,
                },
            ]
        )
        selection_prefix = "llm_ads_serp::run-llm-1"
        st.session_state[f"{selection_prefix}::best running shoes"] = True
        st.session_state[f"{selection_prefix}::trail running shoes"] = False

        captured = {}

        # Purpose: mock run serp analysis workflow implementation
        def mock_run_serp_analysis_workflow(keywords, run_id="", serp_config=None, force_refresh=False):
            captured["keywords"] = keywords
            captured["run_id"] = run_id
            captured["serp_config"] = serp_config
            captured["force_refresh"] = force_refresh
            return pd.DataFrame()

        monkeypatch.setattr(
            "components.results.run_serp_analysis_workflow",
            mock_run_serp_analysis_workflow,
        )

        result = _run_serp_after_ads_keywords(
            ads_df,
            selection_prefix=selection_prefix,
            run_id="run-llm-1",
        )

        assert isinstance(result, pd.DataFrame)
        assert captured["keywords"] == ["best running shoes"]
        assert "https://example.com/blog/llm" not in captured["keywords"]

    # Purpose: Test url ads ideas results handoff selected keywords to serp
    def test_url_ads_ideas_results_handoff_selected_keywords_to_serp(self, monkeypatch):
        import streamlit as st

        ads_df = pd.DataFrame(
            [
                {
                    "Source URL": "https://example.com/category/ads-ideas",
                    "Keyword": "buy running shoes online",
                    "Avg Monthly Searches": 140,
                },
                {
                    "Source URL": "https://example.com/category/ads-ideas",
                    "Keyword": "running shoe deals",
                    "Avg Monthly Searches": 90,
                },
            ]
        )
        selection_prefix = "url_seed_ads_serp::run-ads-1"
        st.session_state[f"{selection_prefix}::buy running shoes online"] = False
        st.session_state[f"{selection_prefix}::running shoe deals"] = True

        captured = {}

        # Purpose: mock run serp analysis workflow implementation
        def mock_run_serp_analysis_workflow(keywords, run_id="", serp_config=None, force_refresh=False):
            captured["keywords"] = keywords
            captured["run_id"] = run_id
            captured["serp_config"] = serp_config
            captured["force_refresh"] = force_refresh
            return pd.DataFrame()

        monkeypatch.setattr(
            "components.results.run_serp_analysis_workflow",
            mock_run_serp_analysis_workflow,
        )

        result = _run_serp_after_ads_keywords(
            ads_df,
            selection_prefix=selection_prefix,
            run_id="run-ads-1",
        )

        assert isinstance(result, pd.DataFrame)
        assert captured["keywords"] == ["running shoe deals"]
        assert "https://example.com/category/ads-ideas" not in captured["keywords"]
