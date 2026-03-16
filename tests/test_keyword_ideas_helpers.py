from contextlib import nullcontext

import pandas as pd
import streamlit as st

import components.results as results
from utils.pipeline import KEYWORD_SEED_SOURCE_URL


class TestKeywordIdeaHelpers:
    def test_keyword_ideas_translations_are_human_readable(self) -> None:
        header = results.t("keyword_ideas_header")
        description = results.t("keyword_ideas_desc")
        add_button = results.t("keyword_ideas_add_button")

        assert "??" not in header
        assert "Keyword Planner" in header
        assert "??" not in description
        assert "??" not in add_button

    def test_merge_keyword_ideas_into_processed_data_adds_only_new_keywords(self) -> None:
        processed_df = pd.DataFrame(
            [
                {
                    "Keyword": "stretch film",
                    "Source URL": "https://example.com/stretch-film",
                    "Avg Monthly Searches": 390,
                },
                {
                    "Keyword": "packing tape",
                    "Source URL": "https://example.com/tape",
                    "Avg Monthly Searches": 260,
                },
            ]
        )
        keyword_ideas_df = pd.DataFrame(
            [
                {
                    "Keyword": "stretch film",
                    "Source URL": "https://example.com/stretch-film",
                    "Avg Monthly Searches": 390,
                },
                {
                    "Keyword": "stretch film wholesale",
                    "Source URL": "https://example.com/stretch-film",
                    "Avg Monthly Searches": 120,
                },
            ]
        )

        merged_df = results.merge_keyword_ideas_into_processed_data(
            processed_df, keyword_ideas_df
        )

        assert len(merged_df) == 3
        assert merged_df["Keyword"].tolist().count("stretch film") == 1
        new_row = merged_df[merged_df["Keyword"] == "stretch film wholesale"].iloc[0]
        assert new_row["Source URL"] == "https://example.com/stretch-film"
        assert new_row["Avg Monthly Searches"] == 120

    def test_build_keyword_ideas_display_df_matches_analysis_metrics_columns(self) -> None:
        keyword_ideas_df = pd.DataFrame(
            [
                {
                    "Keyword": "stretch film wholesale",
                    "Source URL": "https://example.com/stretch-film",
                    "Avg Monthly Searches": 120,
                    "Competition": "MEDIUM",
                    "Competition Index": 52,
                    "Low CPC": 3.0,
                    "High CPC": 9.0,
                    "CPC Currency": "USD",
                    "Months With Data": 12,
                }
            ]
        )

        display_df = results.build_keyword_ideas_display_df(keyword_ideas_df)

        assert display_df.columns.tolist() == [
            "Keyword",
            "Avg Monthly Searches",
            "Competition",
            "Competition Index",
            "Low CPC",
            "High CPC",
            "CPC Currency",
            "Months With Data",
        ]
        assert "Source URL" not in display_df.columns

    def test_render_keyword_ideas_generation_does_not_mutate_existing_keyword_widget_state(
        self, monkeypatch
    ) -> None:
        st.session_state.clear()
        source_url = "https://example.com/stretch-film"
        keyword = "stretch film wholesale"
        existing_kw_key = f"kw_{source_url}_{keyword}"
        idea_key = f"idea_kw::{source_url}::{keyword}"

        st.session_state.processed_data = pd.DataFrame(
            [
                {
                    "Keyword": keyword,
                    "Source URL": source_url,
                    "Avg Monthly Searches": 120,
                }
            ]
        )
        st.session_state.keyword_ideas_data = pd.DataFrame(
            [
                {
                    "Keyword": keyword,
                    "Source URL": source_url,
                    "Avg Monthly Searches": 120,
                    "Competition": "MEDIUM",
                    "Competition Index": 52,
                    "Low CPC": 3.0,
                    "High CPC": 9.0,
                    "CPC Currency": "USD",
                    "Months With Data": 12,
                }
            ]
        )
        st.session_state[existing_kw_key] = True
        st.session_state[idea_key] = True

        monkeypatch.setattr(results.st, "divider", lambda: None)
        monkeypatch.setattr(results.st, "subheader", lambda *args, **kwargs: None)
        monkeypatch.setattr(results.st, "write", lambda *args, **kwargs: None)
        monkeypatch.setattr(results.st, "success", lambda *args, **kwargs: None)
        monkeypatch.setattr(results.st, "info", lambda *args, **kwargs: None)
        monkeypatch.setattr(results.st, "warning", lambda *args, **kwargs: None)
        monkeypatch.setattr(results.st, "caption", lambda *args, **kwargs: None)
        monkeypatch.setattr(results.st, "dataframe", lambda *args, **kwargs: None)
        monkeypatch.setattr(results.st, "expander", lambda *args, **kwargs: nullcontext())
        monkeypatch.setattr(results.st, "rerun", lambda: None)
        monkeypatch.setattr(
            results.st,
            "checkbox",
            lambda label, key=None, **kwargs: st.session_state.get(key, True),
        )
        monkeypatch.setattr(
            results.st,
            "button",
            lambda *args, key=None, **kwargs: key == "apply_keyword_ideas",
        )

        results.render_keyword_ideas_generation(
            location_id="2840",
            language_id="1000",
            currency_code="USD",
            selected_kw_by_url={source_url: [keyword]},
            total_selected=1,
        )

        assert st.session_state.keyword_ideas_flash_message is not None

    def test_deduplicate_processed_data_removes_duplicate_keyword_pairs(self) -> None:
        processed_df = pd.DataFrame(
            [
                {
                    "Keyword": "деревна шерсть",
                    "Source URL": "https://example.com/page",
                    "Avg Monthly Searches": 100,
                },
                {
                    "Keyword": "деревна шерсть",
                    "Source URL": "https://example.com/page",
                    "Avg Monthly Searches": 100,
                },
                {
                    "Keyword": "деревна шерсть",
                    "Source URL": "https://example.com/other",
                    "Avg Monthly Searches": 90,
                },
            ]
        )

        deduped_df = results.deduplicate_processed_data(processed_df)

        assert len(deduped_df) == 2
        assert (
            deduped_df["Keyword"].tolist().count("деревна шерсть") == 2
        )

    def test_append_manual_keyword_ignores_existing_url_keyword_pair(self) -> None:
        processed_df = pd.DataFrame(
            [
                {
                    "Keyword": "деревна шерсть",
                    "Source URL": "https://example.com/page",
                    "Avg Monthly Searches": 100,
                }
            ]
        )

        updated_df, added = results.append_manual_keyword(
            processed_df,
            target_url="https://example.com/page",
            keyword="деревна шерсть",
        )

        assert added is False
        assert len(updated_df) == 1

    def test_build_keyword_selection_signature_changes_for_new_run(self) -> None:
        st.session_state.clear()
        st.session_state.current_run_id = "run-a"
        processed_df = pd.DataFrame(
            [
                {
                    "Keyword": "buy boxes",
                    "Source URL": "https://example.com/page",
                }
            ]
        )

        signature_a = results.build_keyword_selection_signature(processed_df)

        st.session_state.current_run_id = "run-b"
        signature_b = results.build_keyword_selection_signature(processed_df)

        assert signature_a != signature_b

    def test_build_keyword_ideas_signature_changes_when_seed_flags_change(self) -> None:
        selected_kw_by_url = {
            "https://example.com/a": ["alpha", "beta"],
            "https://example.com/b": ["gamma"],
        }

        signature_a = results.build_keyword_ideas_signature(
            selected_kw_by_url,
            {
                "https://example.com/a": False,
                "https://example.com/b": False,
            },
        )
        signature_b = results.build_keyword_ideas_signature(
            selected_kw_by_url,
            {
                "https://example.com/a": True,
                "https://example.com/b": False,
            },
        )

        assert signature_a != signature_b

    def test_limit_keyword_idea_seed_keywords_trims_to_google_ads_cap(self) -> None:
        keywords = [f"keyword {index}" for index in range(25)]

        limited = results.limit_keyword_idea_seed_keywords(keywords)

        assert limited == keywords[:20]

    def test_set_keyword_idea_seed_selection_updates_all_keyword_checkboxes(self) -> None:
        st.session_state.clear()
        url = "https://example.com/page"
        keywords = ["alpha", "beta", "gamma"]

        results.set_keyword_idea_seed_selection(url, keywords, selected=False)
        assert (
            st.session_state[results.build_keyword_idea_seed_key(url, "alpha")] is False
        )
        assert (
            st.session_state[results.build_keyword_idea_seed_key(url, "beta")] is False
        )
        assert (
            st.session_state[results.build_keyword_idea_seed_key(url, "gamma")] is False
        )

        results.set_keyword_idea_seed_selection(url, keywords, selected=True)
        assert (
            st.session_state[results.build_keyword_idea_seed_key(url, "alpha")] is True
        )
        assert (
            st.session_state[results.build_keyword_idea_seed_key(url, "beta")] is True
        )
        assert (
            st.session_state[results.build_keyword_idea_seed_key(url, "gamma")] is True
        )

    def test_render_keyword_ideas_generation_uses_checked_keyword_seed_subset_and_caps_at_20(
        self, monkeypatch
    ) -> None:
        st.session_state.clear()
        source_url = "https://example.com/page"
        keywords = [f"keyword {index}" for index in range(25)]
        recorded_calls = []

        for index, keyword in enumerate(keywords):
            st.session_state[results.build_keyword_idea_seed_key(source_url, keyword)] = (
                index < 22
            )

        class _FakeStatus:
            def __init__(self) -> None:
                self.messages = []

            def write(self, message) -> None:
                self.messages.append(message)

            def update(self, **kwargs) -> None:
                self.messages.append(kwargs)

        class _FakeAdsHandler:
            def __init__(self, *args, **kwargs) -> None:
                pass

            def get_keyword_ideas(self, seed_keywords, page_url=None, source_url=None):
                recorded_calls.append(
                    {
                        "seed_keywords": list(seed_keywords),
                        "page_url": page_url,
                        "source_url": source_url,
                    }
                )
                return pd.DataFrame()

        monkeypatch.setattr(results, "GoogleAdsHandler", _FakeAdsHandler)
        monkeypatch.setattr(results.st, "divider", lambda: None)
        monkeypatch.setattr(results.st, "subheader", lambda *args, **kwargs: None)
        monkeypatch.setattr(results.st, "write", lambda *args, **kwargs: None)
        monkeypatch.setattr(results.st, "success", lambda *args, **kwargs: None)
        monkeypatch.setattr(results.st, "info", lambda *args, **kwargs: None)
        monkeypatch.setattr(results.st, "warning", lambda *args, **kwargs: None)
        monkeypatch.setattr(results.st, "caption", lambda *args, **kwargs: None)
        monkeypatch.setattr(results.st, "dataframe", lambda *args, **kwargs: None)
        monkeypatch.setattr(results.st, "expander", lambda *args, **kwargs: nullcontext())
        monkeypatch.setattr(results.st, "rerun", lambda: None)
        monkeypatch.setattr(results.st, "status", lambda *args, **kwargs: _FakeStatus())
        monkeypatch.setattr(
            results.st,
            "checkbox",
            lambda label, key=None, **kwargs: st.session_state.get(key, True),
        )
        monkeypatch.setattr(
            results.st,
            "button",
            lambda *args, key=None, **kwargs: key == "generate_keyword_ideas",
        )

        results.render_keyword_ideas_generation(
            location_id="2840",
            language_id="1000",
            currency_code="USD",
            selected_kw_by_url={source_url: keywords},
            total_selected=len(keywords),
        )

        assert len(recorded_calls) == 1
        assert recorded_calls[0]["source_url"] == source_url
        assert recorded_calls[0]["page_url"] is None
        assert len(recorded_calls[0]["seed_keywords"]) == 20
        assert recorded_calls[0]["seed_keywords"] == keywords[:20]

    def test_apply_keyword_ideas_updates_processed_data_and_preserves_seo_keyword_selection(
        self, monkeypatch
    ) -> None:
        st.session_state.clear()
        source_url = "https://example.com/page"
        original_keyword = "boxes"
        new_keyword = "buy cardboard boxes"
        idea_key = f"idea_kw::{source_url}::{new_keyword}"

        st.session_state.processed_data = pd.DataFrame(
            [
                {
                    "Keyword": original_keyword,
                    "Source URL": source_url,
                    "Avg Monthly Searches": 100,
                }
            ]
        )
        st.session_state.keyword_selection_signature = ("stale-run", tuple())
        st.session_state.scraped_content = {source_url: "cached page content"}
        st.session_state.keyword_ideas_data = pd.DataFrame(
            [
                {
                    "Keyword": new_keyword,
                    "Source URL": source_url,
                    "Avg Monthly Searches": 120,
                    "Competition": "MEDIUM",
                    "Competition Index": 52,
                    "Low CPC": 3.0,
                    "High CPC": 9.0,
                    "CPC Currency": "USD",
                    "Months With Data": 12,
                }
            ]
        )
        st.session_state[idea_key] = True

        monkeypatch.setattr(results.st, "divider", lambda: None)
        monkeypatch.setattr(results.st, "subheader", lambda *args, **kwargs: None)
        monkeypatch.setattr(results.st, "write", lambda *args, **kwargs: None)
        monkeypatch.setattr(results.st, "success", lambda *args, **kwargs: None)
        monkeypatch.setattr(results.st, "info", lambda *args, **kwargs: None)
        monkeypatch.setattr(results.st, "warning", lambda *args, **kwargs: None)
        monkeypatch.setattr(results.st, "caption", lambda *args, **kwargs: None)
        monkeypatch.setattr(results.st, "dataframe", lambda *args, **kwargs: None)
        monkeypatch.setattr(results.st, "expander", lambda *args, **kwargs: nullcontext())
        monkeypatch.setattr(results.st, "rerun", lambda: None)
        monkeypatch.setattr(
            results.st,
            "checkbox",
            lambda label, key=None, **kwargs: st.session_state.get(key, True),
        )
        monkeypatch.setattr(
            results.st,
            "button",
            lambda *args, key=None, **kwargs: key == "apply_keyword_ideas",
        )

        results.render_keyword_ideas_generation(
            location_id="2840",
            language_id="1000",
            currency_code="USD",
            selected_kw_by_url={source_url: [original_keyword]},
            total_selected=1,
        )

        assert set(st.session_state.processed_data["Keyword"].tolist()) == {
            new_keyword,
            original_keyword,
        }
        assert st.session_state.keyword_selection_signature is None

        selection_result = results.render_keyword_selection()

        assert selection_result is not None
        selected_kw_by_url, total_selected = selection_result
        assert total_selected == 2
        assert selected_kw_by_url[source_url] == [original_keyword, new_keyword]

    def test_format_source_label_humanizes_keyword_seed_source(self) -> None:
        assert hasattr(results, "format_source_label")
        assert results.format_source_label(KEYWORD_SEED_SOURCE_URL) != KEYWORD_SEED_SOURCE_URL

    def test_build_history_metadata_includes_workflow_mode_and_seed_strategy(self) -> None:
        assert hasattr(results, "build_history_metadata")
        metadata = results.build_history_metadata("keyword_seed")

        assert metadata["workflow_mode"] == "keyword_seed"
        assert metadata["seed_strategy"] == "keyword_seed"

    def test_build_history_entry_title_has_no_question_marks(self) -> None:
        assert hasattr(results, "build_history_entry_title")

        title = results.build_history_entry_title(
            {
                "timestamp": "2026-03-10T12:34:56",
                "url_count": 1,
                "keyword_count": 52,
            }
        )

        assert "??" not in title
        assert "2026-03-10T12:34:56" in title
        assert "1 URL" in title
        assert "52" in title

    def test_restore_history_checkpoint_populates_session_state(self) -> None:
        st.session_state.clear()
        assert hasattr(results, "restore_history_checkpoint")

        restored = results.restore_history_checkpoint(
            {
                "timestamp": "2026-03-10T12:34:56",
                "checkpoint": {
                    "workflow_mode": "url_llm",
                    "active_inputs": ["https://example.com/page"],
                    "scraped_content": {"https://example.com/page": "cached content"},
                    "processed_data": [
                        {
                            "Keyword": "buy boxes",
                            "Source URL": "https://example.com/page",
                            "Avg Monthly Searches": 100,
                        }
                    ],
                },
            }
        )

        assert restored is True
        assert st.session_state.workflow_mode == "url_llm"
        assert st.session_state.active_inputs == ["https://example.com/page"]
        assert st.session_state.scraped_content == {
            "https://example.com/page": "cached content"
        }
        assert st.session_state.processed_data is not None
        assert st.session_state.processed_data.loc[0, "Keyword"] == "buy boxes"
