"""
TDD test for Plan 14-03 Task 1: run_keyword_to_llm_workflow pipeline function.

RED: Tests that verify:
1. Function returns DataFrame with keyword, SEO text, and empty URL column
2. Individual keyword failures don't abort the batch (MEDIUM-4)
3. Empty keywords returns None
4. Function exists and is importable
"""
from contextlib import nullcontext
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import streamlit as st

from utils.pipeline import run_keyword_to_llm_workflow


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
    st.session_state["generated_seo_texts"] = None
    st.session_state["scraped_content"] = {}
    monkeypatch.setattr("utils.pipeline.st.progress", lambda *args, **kwargs: _DummyProgress())
    monkeypatch.setattr("utils.pipeline.st.empty", lambda: _DummyStatus())
    monkeypatch.setattr("utils.pipeline.st.warning", lambda *args, **kwargs: None)
    monkeypatch.setattr("utils.pipeline.st.error", lambda *args, **kwargs: None)
    monkeypatch.setattr("utils.pipeline.st.expander", lambda *args, **kwargs: nullcontext())
    monkeypatch.setattr("utils.pipeline.st.success", lambda *args, **kwargs: None)


# Purpose: Verify the function exists and is importable.
class TestRunKeywordToLlmWorkflowImportable:

    # Purpose: Test function exists
    def test_function_exists(self) -> None:
        assert callable(run_keyword_to_llm_workflow), (
            "run_keyword_to_llm_workflow should be a callable function"
        )


# Purpose: Verify empty keyword input returns None.
class TestRunKeywordToLlmWorkflowEmptyInput:

    # Purpose: Test empty keywords returns none
    def test_empty_keywords_returns_none(self) -> None:
        result = run_keyword_to_llm_workflow(
            keywords=[],
            provider="openai",
            model="gpt-4",
        )
        assert result is None, "Empty keywords should return None"

    # Purpose: Test whitespace only keywords returns none
    def test_whitespace_only_keywords_returns_none(self) -> None:
        result = run_keyword_to_llm_workflow(
            keywords=["  ", "", "   "],
            provider="openai",
            model="gpt-4",
        )
        assert result is None, "Whitespace-only keywords should return None"


# Purpose: Verify the output DataFrame structure.
class TestRunKeywordToLlmWorkflowOutput:

    # Purpose: Test returns dataframe with keyword and seo text
    # Purpose: Test returns dataframe with keyword and seo text
    @patch("utils.pipeline.LLMHandler")
    def test_returns_dataframe_with_keyword_and_seo_text(self, mock_llm_class: MagicMock) -> None:
        mock_llm = MagicMock()
        mock_llm.generate_seo_text.return_value = "<p>Generated SEO text for keyword</p>"
        mock_llm_class.return_value = mock_llm

        result = run_keyword_to_llm_workflow(
            keywords=["купить ноутбук"],
            provider="openai",
            model="gpt-4",
            language="Russian",
        )

        assert result is not None, "Should return a DataFrame for valid keywords"
        assert isinstance(result, pd.DataFrame), "Result should be a DataFrame"
        assert len(result.columns) > 0, "DataFrame should have columns"
        assert len(result) == 1, "Should have one row for one keyword"

    @patch("utils.pipeline.LLMHandler")
    # Purpose: HIGH-1: DataFrame MUST include an empty-string URL column.
    def test_dataframe_has_empty_url_column(self, mock_llm_class: MagicMock) -> None:
        mock_llm = MagicMock()
        mock_llm.generate_seo_text.return_value = "<p>SEO text</p>"
        mock_llm_class.return_value = mock_llm

        result = run_keyword_to_llm_workflow(
            keywords=["keyword1"],
            provider="openai",
            model="gpt-4",
        )

        assert result is not None
        assert "URL" in result.columns, (
            "DataFrame MUST have a 'URL' column for render_seo_results compatibility (HIGH-1)"
        )
        assert all(v == "" for v in result["URL"]), (
            "All URL values must be empty strings (HIGH-1)"
        )

    @patch("utils.pipeline.LLMHandler")
    # Purpose: Verify results stored in st.session_state.generated_seo_texts.
    def test_stores_in_session_state(self, mock_llm_class: MagicMock) -> None:
        mock_llm = MagicMock()
        mock_llm.generate_seo_text.return_value = "<p>SEO text</p>"
        mock_llm_class.return_value = mock_llm

        run_keyword_to_llm_workflow(
            keywords=["keyword1"],
            provider="openai",
            model="gpt-4",
        )

        assert st.session_state.get("generated_seo_texts") is not None, (
            "Results should be stored in st.session_state.generated_seo_texts"
        )
        assert st.session_state.get("scraped_content") == {}, (
            "scraped_content should be set to empty dict"
        )


# Purpose: MEDIUM-4: Individual keyword failures must not abort the batch.
class TestRunKeywordToLlmWorkflowPerKeywordErrorHandling:

    # Purpose: Test one failure does not abort batch
    # Purpose: Test one failure does not abort batch
    @patch("utils.pipeline.LLMHandler")
    def test_one_failure_does_not_abort_batch(self, mock_llm_class: MagicMock) -> None:
        mock_llm = MagicMock()
        mock_llm.generate_seo_text.side_effect = [
            "<p>SEO text 1</p>",
            Exception("LLM API error"),
            "<p>SEO text 3</p>",
        ]
        mock_llm_class.return_value = mock_llm

        result = run_keyword_to_llm_workflow(
            keywords=["keyword1", "keyword2", "keyword3"],
            provider="openai",
            model="gpt-4",
        )

        assert result is not None, "Should still return results despite one failure"
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3, (
            "Should have 3 rows (one per keyword) even when one fails"
        )

    # Purpose: Test all failures still returns dataframe
    # Purpose: Test all failures still returns dataframe
    @patch("utils.pipeline.LLMHandler")
    def test_all_failures_still_returns_dataframe(self, mock_llm_class: MagicMock) -> None:
        mock_llm = MagicMock()
        mock_llm.generate_seo_text.side_effect = Exception("All fail")
        mock_llm_class.return_value = mock_llm

        result = run_keyword_to_llm_workflow(
            keywords=["keyword1", "keyword2"],
            provider="openai",
            model="gpt-4",
        )

        # Should still return a DataFrame (with empty SEO texts) rather than None or raising
        assert result is not None, (
            "Should return DataFrame with empty texts even when all keywords fail"
        )


# Purpose: Verify LLM handler is called correctly per keyword.
class TestRunKeywordToLlmWorkflowCallsGenerateSeoText:

    # Purpose: Test calls generate seo text per keyword
    # Purpose: Test calls generate seo text per keyword
    @patch("utils.pipeline.LLMHandler")
    def test_calls_generate_seo_text_per_keyword(self, mock_llm_class: MagicMock) -> None:
        mock_llm = MagicMock()
        mock_llm.generate_seo_text.return_value = "<p>SEO text</p>"
        mock_llm_class.return_value = mock_llm

        run_keyword_to_llm_workflow(
            keywords=["kw1", "kw2", "kw3"],
            provider="openai",
            model="gpt-4",
            language="Ukrainian",
            seo_prompt="custom prompt",
        )

        assert mock_llm.generate_seo_text.call_count == 3, (
            "Should call generate_seo_text once per keyword"
        )

    # Purpose: Test generate seo text receives correct params
    # Purpose: Test generate seo text receives correct params
    @patch("utils.pipeline.LLMHandler")
    def test_generate_seo_text_receives_correct_params(self, mock_llm_class: MagicMock) -> None:
        mock_llm = MagicMock()
        mock_llm.generate_seo_text.return_value = "<p>SEO text</p>"
        mock_llm_class.return_value = mock_llm

        run_keyword_to_llm_workflow(
            keywords=["test keyword"],
            provider="openai",
            model="gpt-4",
            language="Ukrainian",
            seo_prompt="custom prompt",
            force_refresh=True,
        )

        call_kwargs = mock_llm.generate_seo_text.call_args
        assert call_kwargs.kwargs.get("provider") == "openai"
        assert call_kwargs.kwargs.get("model") == "gpt-4"
        assert call_kwargs.kwargs.get("language") == "Ukrainian"
        assert call_kwargs.kwargs.get("custom_prompt") == "custom prompt"
        assert call_kwargs.kwargs.get("force_refresh") is True
