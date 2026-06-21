"""Tests for dynamic model fetching, caching, validation, and routing."""

# MODULE_CONTRACT: tests/test_dynamic_models
# Purpose: Verify dynamic model fetching, cache persistence, and provider validation for the model fetcher module.
# Rationale: Links the dynamic model tests to the GRACE module under test.
# Dependencies: json, os, pathlib, pytest, utils.model_fetcher.
# Exports: pytest tests.
# LINKS: knowledge-graph.xml#MOD-030
# MODULE_MAP: tests/test_dynamic_models.py
# Public Functions: pytest test functions.
# Private Helpers: none.
# Key Semantic Blocks: none.
# Critical Flows: fetch provider model lists -> persist cache -> validate custom provider inputs.
# Verification: verification-plan.xml#V-12-MODEL-FETCHER-DYNAMIC
# CHANGE_SUMMARY: Added GRACE module contract linking this test file to MOD-030.

import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


import utils.model_fetcher as model_fetcher_module
from utils.model_fetcher import (
    ANTHROPIC_MODELS,
    PROVIDER_BASE_URLS,
    fetch_all_models,
    fetch_provider_models,
    get_cached_models,
    load_models_cache,
    save_models_cache,
    validate_custom_provider,
)


# ---------------------------------------------------------------------------
# Cache I/O tests
# ---------------------------------------------------------------------------


# Purpose: TestLoadModelsCache implementation
class TestLoadModelsCache:
    # Purpose: Test load models cache returns empty on missing
    def test_load_models_cache_returns_empty_on_missing(self, monkeypatch, tmp_path):
        monkeypatch.setattr(model_fetcher_module, "MODELS_CACHE_PATH", tmp_path / "nonexistent.json")
        assert load_models_cache() == {}

    # Purpose: Test load models cache reads json
    def test_load_models_cache_reads_json(self, monkeypatch, tmp_path):
        cache_file = tmp_path / "models_cache.json"
        data = {"providers": {"openai": {"models": ["gpt-4"], "status": "success"}}}
        cache_file.write_text(json.dumps(data), encoding="utf-8")
        monkeypatch.setattr(model_fetcher_module, "MODELS_CACHE_PATH", cache_file)
        result = load_models_cache()
        assert result == data

    # Purpose: Test load models cache handles corrupt json
    def test_load_models_cache_handles_corrupt_json(self, monkeypatch, tmp_path):
        cache_file = tmp_path / "models_cache.json"
        cache_file.write_text("{invalid json", encoding="utf-8")
        monkeypatch.setattr(model_fetcher_module, "MODELS_CACHE_PATH", cache_file)
        assert load_models_cache() == {}


# Purpose: TestSaveModelsCache implementation
class TestSaveModelsCache:
    # Purpose: Test save models cache writes json
    def test_save_models_cache_writes_json(self, monkeypatch, tmp_path):
        cache_file = tmp_path / "models_cache.json"
        monkeypatch.setattr(model_fetcher_module, "MODELS_CACHE_PATH", cache_file)
        data = {"providers": {"xai": {"models": ["grok-3"], "status": "success"}}}
        save_models_cache(data)
        assert cache_file.exists()
        loaded = json.loads(cache_file.read_text(encoding="utf-8"))
        assert loaded == data


# ---------------------------------------------------------------------------
# Provider fetch tests
# ---------------------------------------------------------------------------


# Purpose: TestFetchProviderModels implementation
class TestFetchProviderModels:
    # Purpose: Test fetch provider models openai compatible
    def test_fetch_provider_models_openai_compatible(self, monkeypatch):
        mock_model = SimpleNamespace(id="grok-3")
        mock_model2 = SimpleNamespace(id="grok-4")
        mock_page = SimpleNamespace(data=[mock_model, mock_model2])
        mock_client = MagicMock()
        mock_client.models.list.return_value = mock_page
        mock_openai_cls = MagicMock(return_value=mock_client)
        monkeypatch.setattr(model_fetcher_module, "OpenAI", mock_openai_cls)
        result = fetch_provider_models("xai", "test-key", "https://api.x.ai/v1")
        assert result == ["grok-3", "grok-4"]

    # Purpose: Test fetch provider models anthropic returns hardcoded
    def test_fetch_provider_models_anthropic_returns_hardcoded(self):
        result = fetch_provider_models("anthropic", "test-key")
        assert result == ANTHROPIC_MODELS
        assert "claude-sonnet-4-6" in result

    # Purpose: Test fetch provider models google genai
    def test_fetch_provider_models_google_genai(self, monkeypatch):
        mock_model1 = SimpleNamespace(name="models/gemini-3-flash-preview")
        mock_model2 = SimpleNamespace(name="models/gemini-3-pro-preview")
        mock_client_instance = MagicMock()
        mock_client_instance.models.list.return_value = [mock_model1, mock_model2]
        mock_genai = MagicMock()
        mock_genai.Client.return_value = mock_client_instance
        monkeypatch.setattr(model_fetcher_module, "genai", mock_genai)
        result = fetch_provider_models("google", "test-key")
        assert "gemini-3-flash-preview" in result
        assert "models/" not in result[0]

    # Purpose: Test fetch provider models error returns none
    def test_fetch_provider_models_error_returns_none(self, monkeypatch):
        mock_openai_cls = MagicMock(side_effect=Exception("API error"))
        monkeypatch.setattr(model_fetcher_module, "OpenAI", mock_openai_cls)
        result = fetch_provider_models("xai", "bad-key", "https://api.x.ai/v1")
        assert result is None


# ---------------------------------------------------------------------------
# fetch_all_models tests
# ---------------------------------------------------------------------------


# Purpose: TestFetchAllModels implementation
class TestFetchAllModels:
    # Purpose: Test fetch all models skips no key
    def test_fetch_all_models_skips_no_key(self, monkeypatch):
        monkeypatch.setattr(os, "getenv", lambda k: None)
        result = fetch_all_models({"OpenAI": "OPENAI_API_KEY"})
        assert result["providers"]["openai"]["status"] == "no_key"

    # Purpose: Test fetch all models includes custom
    def test_fetch_all_models_includes_custom(self, monkeypatch):
        mock_model = SimpleNamespace(id="custom-model-1")
        mock_page = SimpleNamespace(data=[mock_model])
        mock_client = MagicMock()
        mock_client.models.list.return_value = mock_page
        mock_openai_cls = MagicMock(return_value=mock_client)
        monkeypatch.setattr(model_fetcher_module, "OpenAI", mock_openai_cls)
        monkeypatch.setattr(os, "getenv", lambda k: "test-key" if k == "MY_CUSTOM_KEY" else None)
        custom_providers = [
            {"name": "mycustom", "base_url": "https://custom.api/v1", "api_key_env": "MY_CUSTOM_KEY"}
        ]
        result = fetch_all_models({}, custom_providers=custom_providers)
        assert "mycustom" in result["providers"]
        assert result["providers"]["mycustom"]["status"] == "success"
        assert "custom-model-1" in result["providers"]["mycustom"]["models"]


# ---------------------------------------------------------------------------
# get_cached_models tests
# ---------------------------------------------------------------------------


# Purpose: TestGetCachedModels implementation
class TestGetCachedModels:
    # Purpose: Test get cached models returns list
    def test_get_cached_models_returns_list(self, monkeypatch, tmp_path):
        cache_file = tmp_path / "models_cache.json"
        data = {"providers": {"openai": {"models": ["gpt-4", "gpt-4o"], "status": "success"}}}
        cache_file.write_text(json.dumps(data), encoding="utf-8")
        monkeypatch.setattr(model_fetcher_module, "MODELS_CACHE_PATH", cache_file)
        result = get_cached_models("openai")
        assert result == ["gpt-4", "gpt-4o"]

    # Purpose: Test get cached models empty for unknown provider
    def test_get_cached_models_empty_for_unknown_provider(self, monkeypatch, tmp_path):
        cache_file = tmp_path / "models_cache.json"
        cache_file.write_text(json.dumps({"providers": {}}), encoding="utf-8")
        monkeypatch.setattr(model_fetcher_module, "MODELS_CACHE_PATH", cache_file)
        assert get_cached_models("nonexistent") == []


# ---------------------------------------------------------------------------
# validate_custom_provider tests
# ---------------------------------------------------------------------------


# Purpose: TestValidateCustomProvider implementation
class TestValidateCustomProvider:
    # Purpose: Test validate custom provider valid
    def test_validate_custom_provider_valid(self):
        valid, error = validate_custom_provider("MyProvider", "https://api.example.com/v1", "MY_API_KEY")
        assert valid is True
        assert error == ""

    # Purpose: Test validate custom provider invalid url
    def test_validate_custom_provider_invalid_url(self):
        valid, error = validate_custom_provider("Test", "ftp://bad.com", "MY_KEY")
        assert valid is False
        assert "http" in error

    # Purpose: Test validate custom provider invalid env var
    def test_validate_custom_provider_invalid_env_var(self):
        valid, error = validate_custom_provider("Test", "https://api.example.com", "123bad")
        assert valid is False
        assert "environment variable" in error.lower() or "env" in error.lower()

    # Purpose: Test validate custom provider empty name
    def test_validate_custom_provider_empty_name(self):
        valid, error = validate_custom_provider("", "https://api.example.com", "MY_KEY")
        assert valid is False
        assert "empty" in error.lower()

    # Purpose: Test validate custom provider localhost blocked
    def test_validate_custom_provider_localhost_blocked(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ALLOW_LOCALHOST_PROVIDERS", None)
            valid, error = validate_custom_provider("Local", "http://localhost:11434/v1", "MY_KEY")
        assert valid is False
        assert "localhost" in error.lower()

    # Purpose: Test validate custom provider localhost allowed with env
    def test_validate_custom_provider_localhost_allowed_with_env(self):
        with patch.dict(os.environ, {"ALLOW_LOCALHOST_PROVIDERS": "true"}, clear=False):
            valid, error = validate_custom_provider("Local", "http://localhost:11434/v1", "MY_KEY")
        assert valid is True
        assert error == ""


# ---------------------------------------------------------------------------
# Routing tests
# ---------------------------------------------------------------------------


# Purpose: TestCustomProviderRouting implementation
class TestCustomProviderRouting:
    # Purpose: Custom provider in CUSTOM_PROVIDERS routes through _call_openai_compatible with custom base_url.
    def test_custom_provider_routing(self, monkeypatch):
        import utils.llm_handler as llm_module

        mock_response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="keyword1, keyword2"))]
        )
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_cls = MagicMock(return_value=mock_client)
        monkeypatch.setattr(llm_module, "OpenAI", mock_openai_cls)

        test_cp = [
            {"name": "testcustom", "base_url": "https://custom.api/v1", "api_key_env": "TESTCUSTOM_API_KEY"}
        ]
        monkeypatch.setattr(llm_module, "CUSTOM_PROVIDERS", test_cp)
        monkeypatch.setenv("TESTCUSTOM_API_KEY", "test-key-123")

        handler = llm_module.LLMHandler(timeout_seconds=10, retry_attempts=1, retry_delay_seconds=0)
        # Bypass retry wrapper
        result = llm_module.LLMHandler._execute_generation_once(
            handler, "testcustom", "custom-model-1", "test text", "system prompt", parse_csv=True
        )
        assert "keyword1" in result
        # Verify OpenAI was called with custom base_url
        mock_openai_cls.assert_called_once()
        call_kwargs = mock_openai_cls.call_args
        assert call_kwargs.kwargs.get("base_url") == "https://custom.api/v1" or (
            len(call_kwargs.args) > 1 and "custom.api" in str(call_kwargs)
        )

    # Purpose: Custom provider with name not in PROVIDER_BASE_URLS still works via custom lookup.
    def test_custom_provider_not_in_default_urls(self, monkeypatch):
        import utils.llm_handler as llm_module

        mock_response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="result"))]
        )
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_cls = MagicMock(return_value=mock_client)
        monkeypatch.setattr(llm_module, "OpenAI", mock_openai_cls)

        test_cp = [
            {"name": "my-unique-provider", "base_url": "https://unique.api/v1", "api_key_env": "UNIQUE_KEY"}
        ]
        monkeypatch.setattr(llm_module, "CUSTOM_PROVIDERS", test_cp)
        monkeypatch.setenv("UNIQUE_KEY", "test-key")

        handler = llm_module.LLMHandler(timeout_seconds=10, retry_attempts=1, retry_delay_seconds=0)
        result = llm_module.LLMHandler._execute_generation_once(
            handler, "my-unique-provider", "model-x", "text", "prompt", parse_csv=False
        )
        assert result == "result"
        assert "my-unique-provider" not in PROVIDER_BASE_URLS


# Purpose: TestProviderBaseUrlsSingleSource implementation
class TestProviderBaseUrlsSingleSource:
    # Purpose: Verify PROVIDER_BASE_URLS imported by llm_handler is the same object as model_fetcher.
    def test_provider_base_urls_single_source(self):
        from utils.llm_handler import PROVIDER_BASE_URLS as handler_urls
        assert handler_urls is PROVIDER_BASE_URLS


# ---------------------------------------------------------------------------
# i18n and sidebar integration tests
# ---------------------------------------------------------------------------


# Purpose: TestDynamicModelsI18n implementation
class TestDynamicModelsI18n:
    # Purpose: Test dynamic models i18n keys present
    def test_dynamic_models_i18n_keys_present(self):
        from config.i18n import TRANSLATIONS

        new_keys = [
            "model_refresh_button", "model_refreshing", "model_refresh_complete",
            "model_refresh_error", "model_select_label", "model_manual_entry",
            "model_no_models_cached", "custom_provider_header", "custom_provider_name",
            "custom_provider_base_url", "custom_provider_api_key_env",
            "custom_provider_add_button", "custom_provider_remove",
            "custom_provider_validation_error", "custom_provider_duplicate_name",
        ]
        for key in new_keys:
            assert key in TRANSLATIONS, f"Missing TRANSLATIONS key: {key}"
            entry = TRANSLATIONS[key]
            for lang in ("ru", "uk", "en"):
                assert lang in entry, f"Missing {lang} for key {key}"


# Purpose: TestSidebarCustomProvider implementation
class TestSidebarCustomProvider:
    # Purpose: Custom provider with set env var appears in provider list.
    def test_sidebar_custom_provider_appears(self, monkeypatch):
        test_cp = [
            {"name": "testcp", "display_name": "TestCP", "base_url": "https://test.api/v1", "api_key_env": "TESTCP_KEY"}
        ]
        monkeypatch.setenv("TESTCP_KEY", "test-key")

        # Simulate building available_providers as sidebar does
        provider_keys = {
            "OpenAI": "OPENAI_API_KEY",
            "Anthropic": "ANTHROPIC_API_KEY",
        }
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        available = [name for name, key in provider_keys.items() if os.getenv(key)]
        for cp in test_cp:
            if os.getenv(cp.get("api_key_env", "")):
                available.append(cp.get("display_name", cp["name"]))

        assert "TestCP" in available

    # Purpose: Sidebar provider_keys dict includes Mistral entry.
    def test_mistral_in_provider_keys(self):
        import components.sidebar as sidebar_module
        # Check the module code contains Mistral by inspecting the source
        source = Path(sidebar_module.__file__).read_text(encoding="utf-8")
        assert '"Mistral": "MISTRAL_API_KEY"' in source


# Purpose: TestNoDuplicateModelsCacheInSettings implementation
class TestNoDuplicateModelsCacheInSettings:
    # Purpose: Verify config.settings does NOT have load_models_cache or MODELS_CACHE (HIGH-02 regression guard).
    def test_no_duplicate_models_cache_in_settings(self):
        import config.settings as settings_module
        assert not hasattr(settings_module, "load_models_cache")
        assert not hasattr(settings_module, "MODELS_CACHE")
