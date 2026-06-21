"""
TDD RED tests for Plan 15-01 Task 1-2: Grouped keyword parsing and routing.

These tests verify:
1. Keyword grouping parser: textarea, TXT, CSV, separator handling
2. Keyword->LLM routing: one text per group, group id tracking
3. --- visual separator ignored
"""

from contextlib import nullcontext
from unittest.mock import MagicMock, patch

import pytest
import streamlit as st

from utils.pipeline import run_keyword_to_llm_workflow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Grouped keyword parser tests
# ---------------------------------------------------------------------------

# Purpose: Verify the parse_keyword_groups helper produces correct groups.
class TestGroupedKeywordParser:

    # Purpose: 'keyword one, keyword two' -> one group with two keywords.
    def test_comma_separated_line_produces_one_group(self) -> None:
        from utils.pipeline import parse_keyword_groups
        groups = parse_keyword_groups(["keyword one, keyword two"])
        assert len(groups) == 1
        assert groups[0]["keywords"] == ["keyword one", "keyword two"]

    # Purpose: Two non-empty lines -> two groups.
    def test_two_lines_produce_two_groups(self) -> None:
        from utils.pipeline import parse_keyword_groups
        groups = parse_keyword_groups(["alpha, beta", "gamma"])
        assert len(groups) == 2
        assert groups[0]["keywords"] == ["alpha", "beta"]
        assert groups[1]["keywords"] == ["gamma"]

    # Purpose: A line containing only '---' is ignored.
    def test_separator_line_ignored(self) -> None:
        from utils.pipeline import parse_keyword_groups
        groups = parse_keyword_groups(["alpha", "---", "beta"])
        assert len(groups) == 2
        assert groups[0]["keywords"] == ["alpha"]
        assert groups[1]["keywords"] == ["beta"]

    # Purpose: Empty and whitespace-only lines are skipped.
    def test_empty_lines_skipped(self) -> None:
        from utils.pipeline import parse_keyword_groups
        groups = parse_keyword_groups(["alpha", "", "   ", "beta"])
        assert len(groups) == 2

    # Purpose: Semicolons split keywords within a group.
    def test_semicolon_split(self) -> None:
        from utils.pipeline import parse_keyword_groups
        groups = parse_keyword_groups(["alpha; beta; gamma"])
        assert len(groups) == 1
        assert groups[0]["keywords"] == ["alpha", "beta", "gamma"]

    # Purpose: Pipe characters split keywords within a group.
    def test_pipe_split(self) -> None:
        from utils.pipeline import parse_keyword_groups
        groups = parse_keyword_groups(["alpha | beta | gamma"])
        assert len(groups) == 1
        assert groups[0]["keywords"] == ["alpha", "beta", "gamma"]

    # Purpose: Comma, semicolon, and pipe can be mixed in one line.
    def test_mixed_separators(self) -> None:
        from utils.pipeline import parse_keyword_groups
        groups = parse_keyword_groups(["alpha, beta; gamma | delta"])
        assert len(groups) == 1
        assert groups[0]["keywords"] == ["alpha", "beta", "gamma", "delta"]

    # Purpose: Groups receive sequential group_id starting from 1.
    def test_group_id_sequential(self) -> None:
        from utils.pipeline import parse_keyword_groups
        groups = parse_keyword_groups(["a, b", "c", "d, e, f"])
        assert groups[0]["group_id"] == 1
        assert groups[1]["group_id"] == 2
        assert groups[2]["group_id"] == 3

    # Purpose: CSV import with 'keywords' column splits that cell.
    def test_csv_keywords_column_split(self) -> None:
        from utils.pipeline import parse_keyword_groups_from_csv_rows
        rows = [{"keywords": "alpha, beta, gamma"}, {"keywords": "delta"}]
        groups = parse_keyword_groups_from_csv_rows(rows)
        assert len(groups) == 2
        assert groups[0]["keywords"] == ["alpha", "beta", "gamma"]
        assert groups[1]["keywords"] == ["delta"]

    # Purpose: CSV without header: non-empty cells in one row form one group.
    def test_csv_no_header_row_cells_form_group(self) -> None:
        from utils.pipeline import parse_keyword_groups_from_csv_rows
        rows = [
            ["alpha", "beta", ""],
            ["gamma"],
        ]
        groups = parse_keyword_groups_from_csv_rows(rows, has_header=False)
        assert len(groups) == 2
        assert groups[0]["keywords"] == ["alpha", "beta"]
        assert groups[1]["keywords"] == ["gamma"]


# ---------------------------------------------------------------------------
# Keyword->LLM routing with grouped keywords
# ---------------------------------------------------------------------------

# Purpose: Verify grouped keywords produce one LLM call per group.
class TestGroupedKeywordRouting:

    @patch("utils.pipeline.LLMHandler")
    # Purpose: One line with multiple keywords -> one LLM call, one output row.
    def test_one_group_one_llm_call(self, mock_llm_class: MagicMock) -> None:
        mock_llm = MagicMock()
        mock_llm.generate_seo_text.return_value = "<p>SEO text for group</p>"
        mock_llm_class.return_value = mock_llm

        result = run_keyword_to_llm_workflow(
            keywords=["keyword one, keyword two"],
            provider="openai",
            model="gpt-4",
        )

        assert result is not None
        assert len(result) == 1, "One group should produce one output row"
        assert mock_llm.generate_seo_text.call_count == 1

    @patch("utils.pipeline.LLMHandler")
    # Purpose: Two lines -> two LLM calls, two output rows.
    def test_two_groups_two_llm_calls(self, mock_llm_class: MagicMock) -> None:
        mock_llm = MagicMock()
        mock_llm.generate_seo_text.return_value = "<p>SEO text</p>"
        mock_llm_class.return_value = mock_llm

        result = run_keyword_to_llm_workflow(
            keywords=["alpha, beta", "gamma"],
            provider="openai",
            model="gpt-4",
        )

        assert result is not None
        assert len(result) == 2, "Two groups should produce two output rows"
        assert mock_llm.generate_seo_text.call_count == 2

    @patch("utils.pipeline.LLMHandler")
    # Purpose: Output DataFrame includes group_id and keywords_list columns.
    def test_output_includes_group_id_and_joined_keywords(self, mock_llm_class: MagicMock) -> None:
        mock_llm = MagicMock()
        mock_llm.generate_seo_text.return_value = "<p>SEO text</p>"
        mock_llm_class.return_value = mock_llm

        result = run_keyword_to_llm_workflow(
            keywords=["alpha, beta", "gamma"],
            provider="openai",
            model="gpt-4",
        )

        assert result is not None
        # Check for group metadata columns
        assert "group_id" in result.columns or "Group ID" in result.columns, \
            "Output must include group identifier"
        # The keywords column should contain the joined keyword list
        kw_col = None
        for col in result.columns:
            if col in ("keywords_list", "Keywords", "Ключевые слова", "Ключові слова"):
                kw_col = col
                break
        assert kw_col is not None, "Output must include joined keyword list"


# ---------------------------------------------------------------------------
# Flat (UI textarea) input must honor comma/semicolon/pipe separators per line
# so the documented i18n rule ("several keywords per line via comma") is real.
# ---------------------------------------------------------------------------

# Purpose: Verify flat UI input splits several-keyword lines into one group each.
class TestFlatInputHonorsSeparators:

    @patch("utils.pipeline.LLMHandler")
    # Purpose: A single line "a, b" -> ONE group with two keywords -> ONE call.
    def test_comma_line_becomes_single_group(self, mock_llm_class: MagicMock) -> None:
        mock_llm = MagicMock()
        mock_llm.generate_seo_text.return_value = "<p>SEO text</p>"
        mock_llm_class.return_value = mock_llm

        result = run_keyword_to_llm_workflow(
            keywords=["keyword one, keyword two"],
            provider="openai",
            model="gpt-4",
        )

        assert result is not None
        assert len(result) == 1, "Comma-separated line must form one group (one SEO text)"
        assert mock_llm.generate_seo_text.call_count == 1

    @patch("utils.pipeline.LLMHandler")
    # Purpose: The comma-separated keywords must reach the LLM as separate items.
    def test_comma_keywords_reach_llm_separately(self, mock_llm_class: MagicMock) -> None:
        mock_llm = MagicMock()
        mock_llm.generate_seo_text.return_value = "<p>SEO text</p>"
        mock_llm_class.return_value = mock_llm

        run_keyword_to_llm_workflow(
            keywords=["alpha, beta, gamma"],
            provider="openai",
            model="gpt-4",
        )

        # generate_seo_text is called with keywords=[{"Keyword": kw, ...}, ...]
        call_kwargs = mock_llm.generate_seo_text.call_args.kwargs
        passed_keywords = call_kwargs["keywords"]
        keyword_values = [entry["Keyword"] for entry in passed_keywords]
        assert keyword_values == ["alpha", "beta", "gamma"], (
            "Comma-separated keywords must be split, not kept as one literal string"
        )

    @patch("utils.pipeline.LLMHandler")
    # Purpose: Semicolon and pipe also separate; multiple lines -> multiple groups.
    def test_semicolon_pipe_and_multiline(self, mock_llm_class: MagicMock) -> None:
        mock_llm = MagicMock()
        mock_llm.generate_seo_text.return_value = "<p>SEO text</p>"
        mock_llm_class.return_value = mock_llm

        result = run_keyword_to_llm_workflow(
            keywords=["alpha; beta", "gamma | delta"],
            provider="openai",
            model="gpt-4",
        )

        assert result is not None
        assert len(result) == 2, "Two lines must form two groups"
        assert mock_llm.generate_seo_text.call_count == 2