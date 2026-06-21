# Test: Phase 8 log regressions and non-retriable LLM credential routing
# LINKS: PLAN 08-03 Tasks 1 and 6

from types import SimpleNamespace

import pytest

import utils.llm_handler as llm_handler_module
from utils.llm_handler import (
    LLMHandler,
    LLMNonRetriableCredentialError,
    is_non_retriable_credential_error,
)
from utils.logger import sanitize_log_message


# Purpose:  FakeCredentialError implementation
class _FakeCredentialError(Exception):
    # Purpose:   init   implementation
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = {"error": {"message": message}}


# Purpose: Test non retriable credential classifier matches omniroute error
def test_non_retriable_credential_classifier_matches_omniroute_error() -> None:
    assert is_non_retriable_credential_error(
        400,
        {"error": {"message": "No credentials for provider: nvidia"}},
    )
    assert is_non_retriable_credential_error(
        400,
        {"error": {"message": "Invalid API key"}},
    )
    assert not is_non_retriable_credential_error(
        429,
        {"error": {"message": "Invalid API key"}},
    )


# Purpose: Test non retriable credential error does not retry
def test_non_retriable_credential_error_does_not_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = []
    safe_logs = []

    # Purpose: fake call openai compatible implementation
    def fake_call_openai_compatible(*args, **kwargs):
        attempts.append(args)
        raise _FakeCredentialError("No credentials for provider: nvidia")

    monkeypatch.setattr(LLMHandler, "_call_openai_compatible", fake_call_openai_compatible)
    monkeypatch.setattr(
        llm_handler_module.logger,
        "log_secret_safe_event",
        lambda marker, message, level="warning": safe_logs.append((marker, message)),
    )

    handler = LLMHandler(
        timeout_seconds=1,
        delay_between_requests_seconds=0,
        retry_attempts=4,
        retry_delay_seconds=0,
    )

    with pytest.raises(LLMNonRetriableCredentialError):
        handler._execute_generation(
            "omniroute",
            "nvidia/z-ai/glm-5.1",
            "source text",
            "system prompt",
        )

    assert len(attempts) == 1
    assert safe_logs
    assert "NON_RETRIABLE_CREDENTIAL" in safe_logs[0][0]
    assert safe_logs[0][1] == "Credential error for nvidia; retry skipped."


# Purpose: Test non retriable credential error attempts fallback once
def test_non_retriable_credential_error_attempts_fallback_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    # Purpose: fake call openai compatible implementation
    def fake_call_openai_compatible(
        self,
        provider,
        model,
        text,
        system_prompt,
        request_timeout,
    ):
        calls.append((provider, model))
        if provider == "omniroute":
            raise _FakeCredentialError("No credentials for provider: nvidia")
        return "fallback keyword"

    monkeypatch.setattr(
        LLMHandler,
        "_call_openai_compatible",
        fake_call_openai_compatible,
    )
    monkeypatch.setattr(
        llm_handler_module.LLMHandler,
        "_has_provider_credentials",
        staticmethod(lambda provider: provider == "openrouter"),
    )
    monkeypatch.setattr(llm_handler_module, "FALLBACK_PROVIDER", "openrouter")
    monkeypatch.setattr(llm_handler_module, "FALLBACK_MODEL", "fallback-model")
    monkeypatch.setattr(
        llm_handler_module.logger,
        "log_secret_safe_event",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(llm_handler_module.logger, "info", lambda *args, **kwargs: None)
    monkeypatch.setattr(llm_handler_module.logger, "warning", lambda *args, **kwargs: None)

    handler = LLMHandler(
        timeout_seconds=1,
        delay_between_requests_seconds=0,
        retry_attempts=4,
        retry_delay_seconds=0,
    )

    result = handler.generate_keywords(
        "source text",
        "omniroute",
        "nvidia/z-ai/glm-5.1",
        force_refresh=True,
    )

    assert result == ["fallback keyword"]
    assert calls == [
        ("omniroute", "nvidia/z-ai/glm-5.1"),
        ("openrouter", "fallback-model"),
    ]


# Purpose: Test secret safe log sanitizer redacts credentials
def test_secret_safe_log_sanitizer_redacts_credentials() -> None:
    raw = (
        "No credentials for provider: nvidia api_key=sk-secret123 "
        "Bearer token-value-123 password:plain"
    )

    sanitized = sanitize_log_message(raw)

    assert "sk-secret123" not in sanitized
    assert "token-value-123" not in sanitized
    assert "plain" not in sanitized
    assert "[REDACTED]" in sanitized


# Purpose: Test url like input blocked before serp provider logs
def test_url_like_input_blocked_before_serp_provider_logs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import utils.pipeline as pipeline

    calls = []
    warnings = []
    logs = []

    # Purpose:  MockClient implementation
    class _MockClient:
        # Purpose: search batch implementation
        def search_batch(self, keywords, progress_callback=None):
            calls.append(keywords)
            return []

    mock_st = SimpleNamespace(
        session_state=SimpleNamespace(**{"serp_domain_metrics": None}),
        warning=lambda message: warnings.append(message),
    )

    monkeypatch.setattr(pipeline, "st", mock_st)
    monkeypatch.setattr(pipeline, "create_serp_client", lambda config=None: _MockClient())
    monkeypatch.setattr(pipeline.logger, "warning", lambda message: logs.append(message))

    result = pipeline.run_serp_analysis_workflow(
        keywords=["https://bigbox.com.ua/derevyana-struzhka/"],
        run_id="log-regression",
    )

    assert result is None
    assert calls == []
    assert warnings
    assert any("[GRACE:block_workflow_keyword_gate:STATE] beliefState=" in log for log in logs)
    assert not any("bigbox.com.ua" in str(call) for call in calls)