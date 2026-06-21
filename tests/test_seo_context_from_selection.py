# TDD tests for the URL_LLM -> SEO handoff. After page scraping + LLM
#          keyword extraction, the user can already send selected keywords to
#          Ads / SERP / Trends. They must ALSO be able to generate an SEO text.
#          render_seo_generation requires processed_data (with Keyword, Source URL,
#          Avg Monthly Searches) plus a selected_kw_by_url mapping. Pure LLM
#          extraction does not build processed_data, so a context-preparation
#          helper must synthesize it from the (keyword, source_url) selection
#          tuples and the already-scraped content.
# Reference: requirements.xml#UC-001, app.py (URL_LLM selector handoff)

import pandas as pd
import streamlit as st

from utils.pipeline import (
    RESULT_COLUMNS,
    prepare_seo_context_from_selection,
)


class TestPrepareSeoContextFromSelection:

    # GRACE: function test_returns_selected_keywords_grouped_by_url declaration.
    def test_returns_selected_keywords_grouped_by_url(self):
        st.session_state.clear()
        selected = [
            ("buy coffee", "https://example.com/a"),
            ("coffee beans", "https://example.com/a"),
            ("best grinder", "https://example.com/b"),
        ]
        st.session_state["scraped_content"] = {
            "https://example.com/a": "page A text",
            "https://example.com/b": "page B text",
        }

        kw_by_url, total = prepare_seo_context_from_selection(selected, run_id="r1")

        assert kw_by_url == {
            "https://example.com/a": ["buy coffee", "coffee beans"],
            "https://example.com/b": ["best grinder"],
        }
        assert total == 3

    # GRACE: function test_builds_processed_data_with_required_columns declaration.
    def test_builds_processed_data_with_required_columns(self):
        st.session_state.clear()
        selected = [("buy coffee", "https://example.com/a")]
        st.session_state["scraped_content"] = {"https://example.com/a": "page A"}

        prepare_seo_context_from_selection(selected, run_id="r1")

        df = st.session_state["processed_data"]
        assert df is not None
        assert not df.empty
        for col in ("Keyword", "Source URL", "Avg Monthly Searches"):
            assert col in df.columns, f"processed_data missing required column: {col}"

    # GRACE: function test_processed_data_contains_selected_keywords declaration.
    def test_processed_data_contains_selected_keywords(self):
        st.session_state.clear()
        selected = [
            ("buy coffee", "https://example.com/a"),
            ("best grinder", "https://example.com/b"),
        ]
        st.session_state["scraped_content"] = {
            "https://example.com/a": "page A",
            "https://example.com/b": "page B",
        }

        prepare_seo_context_from_selection(selected, run_id="r1")

        df = st.session_state["processed_data"]
        keywords = set(df["Keyword"].astype(str))
        assert "buy coffee" in keywords
        assert "best grinder" in keywords
        assert set(df["Source URL"].astype(str)) == {
            "https://example.com/a",
            "https://example.com/b",
        }

    # GRACE: function test_preserves_existing_processed_data_when_present declaration.
    def test_preserves_existing_processed_data_when_present(self):
        st.session_state.clear()
        existing = pd.DataFrame(
            [
                {
                    "Keyword": "buy coffee",
                    "Source URL": "https://example.com/a",
                    "Avg Monthly Searches": 1200,
                    "Competition": "HIGH",
                }
            ]
        )
        st.session_state["processed_data"] = existing
        st.session_state["scraped_content"] = {"https://example.com/a": "page A"}

        # Add a new keyword not yet in processed_data
        selected = [
            ("buy coffee", "https://example.com/a"),
            ("new manual kw", "https://example.com/a"),
        ]
        prepare_seo_context_from_selection(selected, run_id="r1")

        df = st.session_state["processed_data"]
        keywords = set(df["Keyword"].astype(str))
        # Existing metric-bearing keyword preserved...
        assert "buy coffee" in keywords
        coffee_row = df[df["Keyword"] == "buy coffee"].iloc[0]
        assert coffee_row["Avg Monthly Searches"] == 1200
        assert "new manual kw" in keywords

    # GRACE: function test_dedupes_repeated_selection_tuples declaration.
    def test_dedupes_repeated_selection_tuples(self):
        st.session_state.clear()
        selected = [
            ("buy coffee", "https://example.com/a"),
            ("buy coffee", "https://example.com/a"),
        ]
        st.session_state["scraped_content"] = {"https://example.com/a": "page A"}

        kw_by_url, total = prepare_seo_context_from_selection(selected, run_id="r1")

        assert total == 1
        assert kw_by_url == {"https://example.com/a": ["buy coffee"]}
        df = st.session_state["processed_data"]
        assert (df["Keyword"] == "buy coffee").sum() == 1

    # GRACE: function test_returns_none_for_empty_selection declaration.
    def test_returns_none_for_empty_selection(self):
        st.session_state.clear()
        st.session_state["scraped_content"] = {"https://example.com/a": "page A"}

        result = prepare_seo_context_from_selection([], run_id="r1")

        assert result is None

    # GRACE: function test_normalizes_processed_data_to_result_columns_schema declaration.
    def test_normalizes_processed_data_to_result_columns_schema(self):
        st.session_state.clear()
        selected = [("buy coffee", "https://example.com/a")]
        st.session_state["scraped_content"] = {"https://example.com/a": "page A"}

        prepare_seo_context_from_selection(selected, run_id="r1")

        df = st.session_state["processed_data"]
        for col in RESULT_COLUMNS:
            assert col in df.columns, f"processed_data missing canonical column: {col}"
    # GRACE: class TestPrepareSeoContextFromSelection declaration
    # GRACE: ...and the new keyword is present (even without metrics)
