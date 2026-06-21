"""
TDD test for Phase 14 i18n keys and settings config (Plan 14-01 Task 2).

RED: All 14 keys must exist with ru/uk/en entries, and settings.yaml must have
the keyword_llm_generation_language key.
"""
import sys
from types import ModuleType

try:
    import streamlit as st
except ModuleNotFoundError:
    st = ModuleType("streamlit")
    st.session_state = {}
    sys.modules["streamlit"] = st

import yaml

from config.i18n import TRANSLATIONS


PHASE_14_I18N_KEYS = [
    "workflow_mode_keyword_llm",
    "keyword_llm_input_header",
    "keyword_llm_input_placeholder",
    "keyword_llm_warning",
    "keyword_llm_language_label",
    "keyword_llm_language_help",
    "keyword_llm_generating",
    "keyword_llm_generating_keyword",
    "keyword_llm_complete",
    "serp_domain_math_header",
    "serp_domain_avg_position",
    "serp_domain_keyword_serps",
    "serp_domain_result_frequency",
    "serp_domain_export_sheet",
]


# Purpose: TestPhase14I18nKeys implementation
class TestPhase14I18nKeys:
    # Purpose: Test all 14 keys exist in translations
    def test_all_14_keys_exist_in_translations(self) -> None:
        missing = [k for k in PHASE_14_I18N_KEYS if k not in TRANSLATIONS]
        assert not missing, f"Missing i18n keys: {missing}"

    # Purpose: Test all 14 keys have ru uk en
    def test_all_14_keys_have_ru_uk_en(self) -> None:
        incomplete = [
            k for k in PHASE_14_I18N_KEYS
            if not all(lang in TRANSLATIONS[k] for lang in ("ru", "uk", "en"))
        ]
        assert not incomplete, f"Incomplete translations: {incomplete}"


# Purpose: TestPhase14SettingsConfig implementation
class TestPhase14SettingsConfig:
    # Purpose: Test keyword llm generation language in settings
    def test_keyword_llm_generation_language_in_settings(self) -> None:
        with open("config/settings.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert "llm" in config, "Missing llm section in settings.yaml"
        assert "keyword_llm_generation_language" in config["llm"], (
            "Missing keyword_llm_generation_language in llm section"
        )