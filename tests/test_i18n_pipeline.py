"""
Unit tests for localized pipeline status messages.
"""

import sys
from types import ModuleType

# MODULE_CONTRACT: tests/test_i18n_pipeline
# Purpose: Verify localized strings and pipeline message formatting.
# Rationale: Links i18n verification tests to their owning GRACE module.
# Dependencies: config.i18n, utils.pipeline, streamlit stub.
# Exports: pytest tests.
# LINKS: knowledge-graph.xml#MOD-008
# MODULE_MAP: tests/test_i18n_pipeline.py
# Public Functions: pytest test functions.
# Private Helpers: streamlit module stub.
# Key Semantic Blocks: none.
# Critical Flows: load translations -> format localized pipeline messages -> assert expected strings.
# Verification: verification-plan.xml#V-MOD-205, verification-plan.xml#V-09-I18N, verification-plan.xml#V-10-I18N
# CHANGE_SUMMARY: Added GRACE module contract linking this test file to MOD-008.

try:
    import streamlit as st
except ModuleNotFoundError:
    st = ModuleType("streamlit")
    st.session_state = {}
    sys.modules["streamlit"] = st

from config.i18n import TRANSLATIONS, t
from utils.pipeline import _format_pipeline_message


# Purpose: TestPipelineI18n implementation
class TestPipelineI18n:
    # Purpose: Test pipeline status messages are localized for ukrainian
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

    # Purpose: Test pipeline translation keys exist for all supported languages
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
            "seo_math_partial_data_warning",
            "seo_math_top_ngrams_header",
            "seo_math_tfidf_header",
            "seo_math_cooccurrence_header",
            "seo_math_intent_header",
            "seo_math_intent_type",
            "seo_math_intent_score",
            "seo_math_intent_confidence",
            "seo_math_intent_transactional",
            "seo_math_intent_navigational",
            "seo_math_related_queries_header",
            "seo_math_related_searches_label",
            "seo_math_paa_label",
            "export_math_analysis",
            "google_trends_provider_label",
            "google_trends_data_confidence_label",
            "google_trends_blocked_warning",
            "google_trends_degraded_warning",
            "google_trends_provider_metadata_header",
            "google_trends_cache_metadata_header",
            "google_trends_relative_scale_caveat",
            "google_trends_official_alpha_caveat",
            "scraper_browser_enabled_help",
            "scraper_not_installed_warning",
            "scraper_dependency_status_header",
            "scraper_dependencies_missing_prompt",
            "scraper_install_scope_label",
        ]

        for key in expected_keys:
            assert key in TRANSLATIONS
            assert "ru" in TRANSLATIONS[key]
            assert "uk" in TRANSLATIONS[key]
            assert "en" in TRANSLATIONS[key]

    # Purpose: Test workflow mode labels are localized for ru and uk
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
            "scraper_browser_enabled_help": (
                "OPT-IN: Requires optional tools (cloakbrowser, trafilatura)"
            ),
            "scraper_not_installed_warning": (
                "Browser scraping is enabled, but optional dependencies are missing or unusable."
            ),
        }

        for key, english_text in english_placeholders.items():
            assert TRANSLATIONS[key]["ru"] != english_text
            assert TRANSLATIONS[key]["uk"] != english_text

    # Purpose: Test every translation key has en key
    def test_every_translation_key_has_en_key(self) -> None:
        for key, entry in TRANSLATIONS.items():
            assert "en" in entry, f"Missing 'en' key for {key}"

    # Purpose: Test core ui strings are localized for english
    def test_core_ui_strings_are_localized_for_english(self) -> None:
        st.session_state["ui_lang"] = "en"

        assert t("ui_language") == "Interface language"
        assert t("workflow_mode_label") == "Workflow mode"
        assert t("location") == "Location"

    # Purpose: I18N-15-01: user-reported labels must not be hardcoded English in ru/uk.
    def test_user_reported_labels_are_not_hardcoded_english(self) -> None:
        reported_keys = [
            "serp_intent_header",
            "serp_intent_type_label",
            "handoff_to_analysis",
            "send_to_serp_ads",
        ]
        for key in reported_keys:
            if key in TRANSLATIONS:
                for lang in ("ru", "uk"):
                    val = TRANSLATIONS[key].get(lang, "")
                    assert val != "", f"Translation key '{key}' missing for {lang}"
                    assert val != TRANSLATIONS[key].get("en", ""), (
                        f"Translation key '{key}' for {lang} is identical to English — likely hardcoded"
                    )

    # Purpose: I18N-15-01: all touched keys must have ru, uk, and en.
    def test_all_touched_i18n_keys_exist_in_three_languages(self) -> None:
        touched_keys = [
            "serp_intent_header",
            "serp_intent_type_label",
            "serp_intent_score_label",
            "serp_intent_confidence_label",
            "handoff_to_analysis",
            "send_to_serp_ads",
            "export_math_analysis",
            "keyword_llm_warning",
            "keyword_llm_generating",
            "keyword_llm_generating_keyword",
            "keyword_llm_complete",
        ]
        for key in touched_keys:
            if key in TRANSLATIONS:
                assert "ru" in TRANSLATIONS[key], f"Key '{key}' missing ru"
                assert "uk" in TRANSLATIONS[key], f"Key '{key}' missing uk"
                assert "en" in TRANSLATIONS[key], f"Key '{key}' missing en"

    # Purpose: I18N-16: the Keyword->LLM input must advertise that several keywords
    # can be entered per line (comma-separated). The placeholder alone is too short
    # to convey the grouping rule, so a longer help tooltip is required as well.
    def test_keyword_llm_input_documents_comma_separated_keywords(self) -> None:
        required_keys = [
            "keyword_llm_input_placeholder",
            "keyword_llm_input_help",
        ]
        for key in required_keys:
            assert key in TRANSLATIONS, f"Missing i18n key '{key}'"
            for lang in ("ru", "uk", "en"):
                assert lang in TRANSLATIONS[key], f"Key '{key}' missing {lang}"
                value = TRANSLATIONS[key][lang]
                assert isinstance(value, str) and value, f"Key '{key}' empty for {lang}"

        # The help tooltip must explain the comma-separator rule in every language.
        comma_markers = {",", "кома", "кому", "comma"}
        for lang in ("ru", "uk", "en"):
            help_text = TRANSLATIONS["keyword_llm_input_help"][lang].lower()
            assert any(marker in help_text for marker in comma_markers), (
                f"keyword_llm_input_help for {lang} does not mention the comma separator"
            )
            # ru/uk must not be identical to en (no hardcoded English).
            if lang in ("ru", "uk"):
                assert help_text != TRANSLATIONS["keyword_llm_input_help"]["en"].lower(), (
                    f"keyword_llm_input_help for {lang} is identical to English"
                )

    # Purpose: I18N-16: the placeholder must mention several keywords per line.
    def test_keyword_llm_placeholder_mentions_several_keywords_per_line(self) -> None:
        for lang in ("ru", "uk", "en"):
            text = TRANSLATIONS["keyword_llm_input_placeholder"][lang].lower()
            assert "одну" in text or "одне" in text or "several" in text or "несколько" in text or "кілька" in text, (
                f"keyword_llm_input_placeholder for {lang} must allow several keywords per line"
            )
