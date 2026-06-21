"""
TDD test for Plan 14-03 Task 2: Workflow routing, sidebar language config, and results rendering.

RED: Tests that verify:
1. WORKFLOW_MODE_KEYWORD_LLM exists in WORKFLOW_MODES
2. _workflow_options() includes keyword_llm mode
3. _workflow_mode_label() includes keyword_llm mode
4. _build_sidebar_config_updates persists keyword_llm_generation_language (MEDIUM-6)
5. Sidebar returns keyword_llm_generation_language in config
"""


from app import (
    WORKFLOW_MODE_KEYWORD_LLM,
    WORKFLOW_MODES,
    _workflow_options,
    _workflow_mode_label,
)
from components.sidebar import _build_sidebar_config_updates


# Purpose: Verify WORKFLOW_MODE_KEYWORD_LLM constant and its inclusion in WORKFLOW_MODES.
class TestWorkflowModeKeywordLlm:

    # Purpose: Test keyword llm constant exists
    def test_keyword_llm_constant_exists(self) -> None:
        assert WORKFLOW_MODE_KEYWORD_LLM == "keyword_llm", (
            "WORKFLOW_MODE_KEYWORD_LLM should equal 'keyword_llm'"
        )

    # Purpose: Test keyword llm in workflow modes
    def test_keyword_llm_in_workflow_modes(self) -> None:
        assert WORKFLOW_MODE_KEYWORD_LLM in WORKFLOW_MODES, (
            "WORKFLOW_MODE_KEYWORD_LLM must be in the WORKFLOW_MODES list"
        )

    # Purpose: Test workflow options includes keyword llm
    def test_workflow_options_includes_keyword_llm(self) -> None:
        options = _workflow_options()
        assert WORKFLOW_MODE_KEYWORD_LLM in options.values(), (
            "_workflow_options() must include keyword_llm mode value"
        )

    # Purpose: Test workflow mode label includes keyword llm
    def test_workflow_mode_label_includes_keyword_llm(self) -> None:
        label = _workflow_mode_label(WORKFLOW_MODE_KEYWORD_LLM)
        assert label and label != WORKFLOW_MODE_KEYWORD_LLM, (
            "_workflow_mode_label('keyword_llm') should return a translated label, not the raw mode id"
        )


# Purpose: MEDIUM-6: Verify sidebar persists keyword_llm_generation_language.
class TestSidebarKeywordLlmLanguage:

    # Purpose: _build_sidebar_config_updates must include keyword_llm_generation_language in llm_config.
    def test_build_sidebar_config_updates_persists_keyword_llm_language(self) -> None:
        current_config: dict = {}
        values = {
            "keyword_prompt": "",
            "seo_prompt": "",
            "api_timeout": 10,
            "api_delay": 2,
            "api_retry_count": 4,
            "api_retry_delay": 4,
            "cleanup_max_age": 30,
            "app_log_level": "INFO",
            "console_logging_enabled": True,
            "console_log_level": "INFO",
            "api_logging_enabled": True,
            "api_log_level": "DEBUG",
            "api_retention_days": 30,
            "error_log_level": "ERROR",
            "history_retention_days": 30,
            "log_test_runs": False,
            "provider": "OpenAI",
            "model_name": "gpt-4",
            "max_keywords": 50,
            "upload_max_file_size_mb": 5,
            "upload_max_rows": 1000,
            "ui_lang": "ru",
            "location_id": "2804",
            "language_id": "1031",
            "currency_code": "UAH",
            "keyword_llm_generation_language": "Ukrainian",
        }

        result = _build_sidebar_config_updates(current_config, values)
        assert "llm" in result, "Config should have llm section"
        assert "keyword_llm_generation_language" in result["llm"], (
            "llm config must include keyword_llm_generation_language (MEDIUM-6)"
        )
        assert result["llm"]["keyword_llm_generation_language"] == "Ukrainian", (
            "keyword_llm_generation_language should be 'Ukrainian'"
        )

    # Purpose: When not specified, should default to Russian.
    def test_build_sidebar_config_defaults_to_russian(self) -> None:
        current_config: dict = {}
        values = {
            "keyword_prompt": "",
            "seo_prompt": "",
            "api_timeout": 10,
            "api_delay": 2,
            "api_retry_count": 4,
            "api_retry_delay": 4,
            "cleanup_max_age": 30,
            "app_log_level": "INFO",
            "console_logging_enabled": True,
            "console_log_level": "INFO",
            "api_logging_enabled": True,
            "api_log_level": "DEBUG",
            "api_retention_days": 30,
            "error_log_level": "ERROR",
            "history_retention_days": 30,
            "log_test_runs": False,
            "provider": "OpenAI",
            "model_name": "gpt-4",
            "max_keywords": 50,
            "upload_max_file_size_mb": 5,
            "upload_max_rows": 1000,
            "ui_lang": "ru",
            "location_id": "2804",
            "language_id": "1031",
            "currency_code": "UAH",
            # keyword_llm_generation_language intentionally omitted
        }

        result = _build_sidebar_config_updates(current_config, values)
        assert result["llm"]["keyword_llm_generation_language"] == "Russian", (
            "Default should be 'Russian' when not specified (MEDIUM-6)"
        )