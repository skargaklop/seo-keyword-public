"""
Unit tests for localized pipeline status messages.
"""

import streamlit as st

from config.i18n import EN_TRANSLATIONS, TRANSLATIONS, t
from utils.pipeline import _format_pipeline_message


class TestPipelineI18n:
    def test_pipeline_status_messages_are_localized_for_ukrainian(self) -> None:
        st.session_state["ui_lang"] = "uk"

        assert (
            _format_pipeline_message("pipeline_scraping_content")
            == TRANSLATIONS["pipeline_scraping_content"]["uk"]
        )
        assert (
            _format_pipeline_message(
                "pipeline_analyzing_url",
                idx=1,
                total=2,
                url="https://example.com",
            )
            == TRANSLATIONS["pipeline_analyzing_url"]["uk"].format(
                idx=1,
                total=2,
                url="https://example.com",
            )
        )

    def test_pipeline_translation_keys_exist_for_all_supported_languages(self) -> None:
        expected_keys = [
            "pipeline_validating_urls",
            "pipeline_invalid_urls_skipped",
            "pipeline_no_valid_urls",
            "pipeline_scraping_content",
            "pipeline_no_content_scraped",
            "pipeline_extracting_keywords",
            "pipeline_analyzing_url",
            "pipeline_processing_deduplicating",
            "pipeline_no_keywords_found",
            "pipeline_fetching_metrics",
            "pipeline_querying_google_ads",
            "pipeline_finalizing_report",
            "pipeline_done",
            "pipeline_analysis_complete",
            "keyword_ideas_header",
            "keyword_ideas_desc",
            "use_url_as_seed",
            "generate_keyword_ideas_button",
            "keyword_ideas_generating",
            "keyword_ideas_add_button",
            "keyword_ideas_added_success",
            "workflow_mode_label",
            "workflow_mode_url_llm",
            "workflow_mode_url_seed",
            "workflow_mode_keyword_seed",
            "keyword_seed_header",
            "keyword_seed_placeholder",
            "keyword_seed_warning",
            "url_seed_start_seo",
            "url_seed_start_seo_help",
            "keyword_seed_source_label",
        ]

        for key in expected_keys:
            assert key in TRANSLATIONS
            assert "ru" in TRANSLATIONS[key]
            assert "uk" in TRANSLATIONS[key]
            assert "en" in TRANSLATIONS[key]

    def test_workflow_mode_labels_are_localized_for_ru_and_uk(self) -> None:
        english_placeholders = {
            "workflow_mode_label": "Workflow mode",
            "workflow_mode_url_seed": "URL -> Ads ideas",
            "workflow_mode_keyword_seed": "Keyword seed -> Ads ideas",
            "keyword_seed_header": "Keyword seeds",
            "keyword_seed_placeholder": "Enter one keyword per line",
            "keyword_seed_warning": "Please enter at least one keyword seed.",
            "url_seed_start_seo": "Continue to SEO",
            "url_seed_start_seo_help": (
                "Scrape the selected URLs only when you are ready to generate SEO text."
            ),
            "keyword_seed_source_label": "Manual keyword seed",
        }

        for key, english_text in english_placeholders.items():
            assert TRANSLATIONS[key]["ru"] != english_text
            assert TRANSLATIONS[key]["uk"] != english_text

    def test_every_translation_key_has_explicit_english_source(self) -> None:
        assert set(EN_TRANSLATIONS) == set(TRANSLATIONS)
        for key, entry in TRANSLATIONS.items():
            assert entry["en"] == EN_TRANSLATIONS[key]

    def test_core_ui_strings_are_localized_for_english(self) -> None:
        st.session_state["ui_lang"] = "en"

        assert t("ui_language") == "Interface language"
        assert t("workflow_mode_label") == "Workflow mode"
        assert t("location") == "Location"
