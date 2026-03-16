"""
Unit tests for LLMHandler runtime behavior and response cleanup.
"""

import os
from types import SimpleNamespace

import pytest

import utils.llm_handler as llm_handler_module
from utils.llm_handler import LLMHandler


class TestCleanLLMResponse:
    """Tests for stripping <thinking> blocks and other LLM artifacts."""

    def test_removes_thinking_block(self) -> None:
        raw = "<thinking>Let me analyze this...</thinking>купить кофе, чай зеленый"
        assert LLMHandler._clean_llm_response(raw) == "купить кофе, чай зеленый"

    def test_removes_multiline_thinking_block(self) -> None:
        raw = (
            "<thinking>\nStep 1: analyze keywords\n"
            "Step 2: filter\n</thinking>\n"
            "купить кофе, чай зеленый"
        )
        assert LLMHandler._clean_llm_response(raw) == "купить кофе, чай зеленый"

    def test_removes_case_insensitive_thinking(self) -> None:
        raw = "<Thinking>some reasoning</Thinking>result text"
        assert LLMHandler._clean_llm_response(raw) == "result text"

    def test_removes_orphan_thinking_tags(self) -> None:
        raw = "<thinking>unclosed block\nresult text"
        result = LLMHandler._clean_llm_response(raw)
        assert "<thinking>" not in result.lower()

    def test_preserves_clean_content(self) -> None:
        raw = "купить кофе, чай зеленый, молоко"
        assert LLMHandler._clean_llm_response(raw) == raw

    def test_handles_empty_string(self) -> None:
        assert LLMHandler._clean_llm_response("") == ""

    def test_handles_none_like_empty(self) -> None:
        # The method returns content as-is if falsy
        assert LLMHandler._clean_llm_response("") == ""

    def test_removes_thinking_with_surrounding_content(self) -> None:
        raw = "prefix <thinking>reasoning here</thinking> suffix"
        assert LLMHandler._clean_llm_response(raw) == "prefix  suffix"

    def test_removes_multiple_thinking_blocks(self) -> None:
        raw = "<thinking>block1</thinking>text1<thinking>block2</thinking>text2"
        assert LLMHandler._clean_llm_response(raw) == "text1text2"


class TestRuntimeLLMConfig:
    def test_supports_runtime_delay_and_retry_settings(self) -> None:
        handler = LLMHandler(
            timeout_seconds=5,
            delay_between_requests_seconds=7,
            retry_attempts=2,
            retry_delay_seconds=6,
        )

        assert handler.timeout_seconds == 5.0
        assert handler.delay_between_requests_seconds == 7.0
        assert handler.retry_attempts == 2
        assert handler.retry_delay_seconds == 6.0

    def test_loads_retry_delay_from_runtime_config(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_load_runtime_config() -> dict[str, object]:
            return {"llm": {}, "retry": {"max_attempts": 5, "delay_seconds": 9}}

        monkeypatch.setattr(
            LLMHandler,
            "_load_runtime_config",
            staticmethod(fake_load_runtime_config),
        )

        handler = LLMHandler(timeout_seconds=5, delay_between_requests_seconds=0)

        assert handler.retry_attempts == 5
        assert handler.retry_delay_seconds == 9.0

    def test_execute_generation_passes_keyword_timeout_to_google(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        handler = LLMHandler(
            timeout_seconds=12,
            delay_between_requests_seconds=0,
            retry_attempts=1,
        )
        captured: dict[str, float] = {}

        def fake_call_google(
            model: str,
            prompt: str,
            system_prompt: str,
            request_timeout: float,
        ) -> str:
            captured["timeout"] = request_timeout
            return "alpha, beta"

        monkeypatch.setattr(handler, "_call_google", fake_call_google)

        result = LLMHandler._execute_generation.__wrapped__(
            handler,
            "google",
            "gemini-test",
            "source text",
            "system prompt",
            True,
        )

        assert result == ["alpha", "beta"]
        assert captured["timeout"] == 12.0

    def test_execute_generation_passes_extended_timeout_to_google_for_seo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        handler = LLMHandler(
            timeout_seconds=15,
            delay_between_requests_seconds=0,
            retry_attempts=1,
        )
        captured: dict[str, float] = {}

        def fake_call_google(
            model: str,
            prompt: str,
            system_prompt: str,
            request_timeout: float,
        ) -> str:
            captured["timeout"] = request_timeout
            return "generated seo text"

        monkeypatch.setattr(handler, "_call_google", fake_call_google)

        result = LLMHandler._execute_generation.__wrapped__(
            handler,
            "google",
            "gemini-test",
            "source text",
            "system prompt",
            False,
        )

        assert result == "generated seo text"
        assert captured["timeout"] == 60.0

    def test_build_retrying_uses_runtime_attempts_and_delay(self) -> None:
        handler = LLMHandler(
            timeout_seconds=15,
            delay_between_requests_seconds=0,
            retry_attempts=3,
            retry_delay_seconds=8,
        )

        retrier = handler._build_retrying()

        assert retrier.stop.max_attempt_number == 3
        assert retrier.wait.wait_fixed == 8.0

    def test_openai_compatible_uses_runtime_delay_and_canonical_zai_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ZAI_API_KEY", "test-key")
        monkeypatch.delenv("ZAI_BASE_URL", raising=False)

        captured_client_args: dict[str, object] = {}
        slept: list[float] = []

        class FakeLimiter:
            def wait(self) -> None:
                return None

        class FakeOpenAI:
            def __init__(self, **kwargs: object) -> None:
                captured_client_args.update(kwargs)
                self.chat = SimpleNamespace(
                    completions=SimpleNamespace(create=self._create_completion)
                )

            @staticmethod
            def _create_completion(**kwargs: object) -> object:
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content="keyword1, keyword2")
                        )
                    ]
                )

        monkeypatch.setattr(llm_handler_module, "OpenAI", FakeOpenAI)
        monkeypatch.setattr(llm_handler_module, "get_rate_limiter", lambda _: FakeLimiter())
        monkeypatch.setattr(llm_handler_module.time, "sleep", lambda seconds: slept.append(seconds))

        handler = LLMHandler(
            timeout_seconds=9,
            delay_between_requests_seconds=3,
            retry_attempts=1,
        )

        result = handler._call_openai_compatible(
            provider="zai",
            model="glm-4.7",
            prompt="source text",
            system_prompt="system prompt",
            request_timeout=9.0,
        )

        assert result == "keyword1, keyword2"
        assert captured_client_args["base_url"] == "https://api.z.ai/api/coding/paas/v4"
        assert slept == [3]

    def test_openai_compatible_uses_explicit_openai_base_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("OPENAI_BASE_URL", "https://proxy.example/v1")

        captured_client_args: dict[str, object] = {}

        class FakeLimiter:
            def wait(self) -> None:
                return None

        class FakeOpenAI:
            def __init__(self, **kwargs: object) -> None:
                captured_client_args.update(kwargs)
                self.responses = SimpleNamespace(create=self._create_response)

            @staticmethod
            def _create_response(**kwargs: object) -> object:
                return SimpleNamespace(output_text="keyword1, keyword2")

        monkeypatch.setattr(llm_handler_module, "OpenAI", FakeOpenAI)
        monkeypatch.setattr(
            llm_handler_module, "get_rate_limiter", lambda _: FakeLimiter()
        )

        handler = LLMHandler(
            timeout_seconds=9,
            delay_between_requests_seconds=0,
            retry_attempts=1,
        )

        result = handler._call_openai_compatible(
            provider="openai",
            model="gpt-test",
            prompt="source text",
            system_prompt="system prompt",
            request_timeout=9.0,
        )

        assert result == "keyword1, keyword2"
        assert captured_client_args["base_url"] == "https://proxy.example/v1"

    def test_anthropic_uses_explicit_base_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://anthropic-proxy.example")

        captured_client_args: dict[str, object] = {}

        class FakeLimiter:
            def wait(self) -> None:
                return None

        class FakeAnthropic:
            def __init__(self, **kwargs: object) -> None:
                captured_client_args.update(kwargs)
                self.messages = SimpleNamespace(create=self._create_message)

            @staticmethod
            def _create_message(**kwargs: object) -> object:
                return SimpleNamespace(
                    content=[SimpleNamespace(text="keyword1, keyword2")]
                )

        monkeypatch.setattr(llm_handler_module, "Anthropic", FakeAnthropic)
        monkeypatch.setattr(
            llm_handler_module, "get_rate_limiter", lambda _: FakeLimiter()
        )

        handler = LLMHandler(
            timeout_seconds=9,
            delay_between_requests_seconds=0,
            retry_attempts=1,
        )

        result = handler._call_anthropic(
            model="claude-test",
            prompt="source text",
            system_prompt="system prompt",
            request_timeout=9.0,
        )

        assert result == "keyword1, keyword2"
        assert captured_client_args["base_url"] == "https://anthropic-proxy.example"

    def test_google_uses_explicit_base_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.setenv("GEMINI_BASE_URL", "https://gemini-proxy.example")

        captured_client_args: dict[str, object] = {}

        class FakeLimiter:
            def wait(self) -> None:
                return None

        def fake_http_options(**kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(**kwargs)

        def fake_generate_content_config(**kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(**kwargs)

        class FakeClient:
            def __init__(self, **kwargs: object) -> None:
                captured_client_args.update(kwargs)
                self.models = SimpleNamespace(generate_content=self._generate_content)

            @staticmethod
            def _generate_content(**kwargs: object) -> object:
                return SimpleNamespace(text="keyword1, keyword2")

        monkeypatch.setattr(
            llm_handler_module,
            "types",
            SimpleNamespace(
                HttpOptions=fake_http_options,
                GenerateContentConfig=fake_generate_content_config,
            ),
        )
        monkeypatch.setattr(llm_handler_module, "genai", SimpleNamespace(Client=FakeClient))
        monkeypatch.setattr(
            llm_handler_module, "get_rate_limiter", lambda _: FakeLimiter()
        )

        handler = LLMHandler(
            timeout_seconds=9,
            delay_between_requests_seconds=0,
            retry_attempts=1,
        )

        result = handler._call_google(
            model="gemini-test",
            prompt="source text",
            system_prompt="system prompt",
            request_timeout=9.0,
        )

        assert result == "keyword1, keyword2"
        http_options = captured_client_args["http_options"]
        assert http_options.base_url == "https://gemini-proxy.example"
        assert http_options.timeout == 10000

    def test_google_converts_timeout_seconds_to_milliseconds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.delenv("GEMINI_BASE_URL", raising=False)

        captured_client_args: dict[str, object] = {}

        class FakeLimiter:
            def wait(self) -> None:
                return None

        def fake_http_options(**kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(**kwargs)

        def fake_generate_content_config(**kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(**kwargs)

        class FakeClient:
            def __init__(self, **kwargs: object) -> None:
                captured_client_args.update(kwargs)
                self.models = SimpleNamespace(generate_content=self._generate_content)

            @staticmethod
            def _generate_content(**kwargs: object) -> object:
                return SimpleNamespace(text="keyword1, keyword2")

        monkeypatch.setattr(
            llm_handler_module,
            "types",
            SimpleNamespace(
                HttpOptions=fake_http_options,
                GenerateContentConfig=fake_generate_content_config,
            ),
        )
        monkeypatch.setattr(llm_handler_module, "genai", SimpleNamespace(Client=FakeClient))
        monkeypatch.setattr(
            llm_handler_module, "get_rate_limiter", lambda _: FakeLimiter()
        )

        handler = LLMHandler(
            timeout_seconds=1,
            delay_between_requests_seconds=0,
            retry_attempts=1,
        )

        result = handler._call_google(
            model="gemini-test",
            prompt="source text",
            system_prompt="system prompt",
            request_timeout=1.0,
        )

        assert result == "keyword1, keyword2"
        http_options = captured_client_args["http_options"]
        assert http_options.timeout == 10000

    def test_keyword_prompt_with_literal_braces_is_preserved(self) -> None:
        handler = LLMHandler()

        prompt = 'Return JSON like {"keywords": []} and keep {max_keywords} as placeholder.'

        rendered = handler._get_system_prompt(5, prompt)

        assert rendered == prompt

    def test_seo_prompt_with_literal_braces_is_preserved(self) -> None:
        handler = LLMHandler()

        prompt = (
            'Use schema {"faq": []} and variables {language} / {keywords_list} '
            'without crashing on literal braces.'
        )

        rendered = handler._get_seo_prompt("Russian", "- alpha", prompt)

        assert rendered == prompt
