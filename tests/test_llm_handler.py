# Test coverage for modules: MOD-001,MOD-004
"""
Unit tests for LLMHandler runtime behavior and response cleanup.
"""

from types import SimpleNamespace

import pytest

import utils.llm_handler as llm_handler_module
from utils.llm_handler import LLMHandler


# Purpose: Tests for stripping <thinking> blocks and other LLM artifacts.
class TestCleanLLMResponse:

    # Purpose: Test removes thinking block
    def test_removes_thinking_block(self) -> None:
        raw = "<thinking>Let me analyze this...</thinking>купить кофе, чай зеленый"
        assert LLMHandler._clean_llm_response(raw) == "купить кофе, чай зеленый"

    # Purpose: Test removes multiline thinking block
    def test_removes_multiline_thinking_block(self) -> None:
        raw = (
            "<thinking>\nStep 1: analyze keywords\n"
            "Step 2: filter\n</thinking>\n"
            "купить кофе, чай зеленый"
        )
        assert LLMHandler._clean_llm_response(raw) == "купить кофе, чай зеленый"

    # Purpose: Test removes case insensitive thinking
    def test_removes_case_insensitive_thinking(self) -> None:
        raw = "<Thinking>some reasoning</Thinking>result text"
        assert LLMHandler._clean_llm_response(raw) == "result text"

    # Purpose: Test removes orphan thinking tags
    def test_removes_orphan_thinking_tags(self) -> None:
        raw = "<thinking>unclosed block\nresult text"
        result = LLMHandler._clean_llm_response(raw)
        assert "<thinking>" not in result.lower()

    # Purpose: Test preserves clean content
    def test_preserves_clean_content(self) -> None:
        raw = "купить кофе, чай зеленый, молоко"
        assert LLMHandler._clean_llm_response(raw) == raw

    # Purpose: Test handles empty string
    def test_handles_empty_string(self) -> None:
        assert LLMHandler._clean_llm_response("") == ""

    # Purpose: Test handles none like empty
    # The method returns content as-is if falsy.
    def test_handles_none_like_empty(self) -> None:
        assert LLMHandler._clean_llm_response("") == ""

    # Purpose: Test removes thinking with surrounding content
    def test_removes_thinking_with_surrounding_content(self) -> None:
        raw = "prefix <thinking>reasoning here</thinking> suffix"
        assert LLMHandler._clean_llm_response(raw) == "prefix  suffix"

    # Purpose: Test removes multiple thinking blocks
    def test_removes_multiple_thinking_blocks(self) -> None:
        raw = "<thinking>block1</thinking>text1<thinking>block2</thinking>text2"
        assert LLMHandler._clean_llm_response(raw) == "text1text2"


# Purpose: TestRuntimeLLMConfig implementation
class TestRuntimeLLMConfig:
    # Purpose: Test supports runtime delay and retry settings
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

    # Purpose: Test loads retry delay from runtime config
    def test_loads_retry_delay_from_runtime_config(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Purpose: fake load runtime config implementation
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

    # Purpose: Test execute generation passes keyword timeout to google
    def test_execute_generation_passes_keyword_timeout_to_google(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        handler = LLMHandler(
            timeout_seconds=12,
            delay_between_requests_seconds=0,
            retry_attempts=1,
        )
        captured: dict[str, float] = {}

        # Purpose: fake call google implementation
        def fake_call_google(
            model: str,
            prompt: str,
            system_prompt: str,
            request_timeout: float,
        ) -> str:
            captured["timeout"] = request_timeout
            return "alpha, beta"

        monkeypatch.setattr(handler, "_call_google", fake_call_google)

        result = LLMHandler._execute_generation_once(
            handler,
            "google",
            "gemini-test",
            "source text",
            "system prompt",
            True,
        )

        assert result == ["alpha", "beta"]
        assert captured["timeout"] == 12.0

    # Purpose: Test execute generation passes extended timeout to google for seo
    def test_execute_generation_passes_extended_timeout_to_google_for_seo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        handler = LLMHandler(
            timeout_seconds=15,
            delay_between_requests_seconds=0,
            retry_attempts=1,
        )
        captured: dict[str, float] = {}

        # Purpose: fake call google implementation
        def fake_call_google(
            model: str,
            prompt: str,
            system_prompt: str,
            request_timeout: float,
        ) -> str:
            captured["timeout"] = request_timeout
            return "generated seo text"

        monkeypatch.setattr(handler, "_call_google", fake_call_google)

        result = LLMHandler._execute_generation_once(
            handler,
            "google",
            "gemini-test",
            "source text",
            "system prompt",
            False,
        )

        assert result == "generated seo text"
        assert captured["timeout"] == 60.0

    # Purpose: Test build retrying uses runtime attempts and delay
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

    # Purpose: Test openai compatible uses runtime delay and canonical zai url
    def test_openai_compatible_uses_runtime_delay_and_canonical_zai_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ZAI_API_KEY", "test-key")
        monkeypatch.delenv("ZAI_BASE_URL", raising=False)

        captured_client_args: dict[str, object] = {}
        slept: list[float] = []

        # Purpose: FakeLimiter implementation
        class FakeLimiter:
            # Purpose: wait implementation
            def wait(self) -> None:
                return None

        # Purpose: FakeOpenAI implementation
        class FakeOpenAI:
            # Purpose:   init   implementation
            def __init__(self, **kwargs: object) -> None:
                captured_client_args.update(kwargs)
                self.chat = SimpleNamespace(
                    completions=SimpleNamespace(create=self._create_completion)
                )

            # Purpose:  create completion implementation
            # Purpose:  create completion implementation
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

    # Purpose: Test openai compatible uses explicit openai base url
    def test_openai_compatible_uses_explicit_openai_base_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("OPENAI_BASE_URL", "https://proxy.example/v1")

        captured_client_args: dict[str, object] = {}

        # Purpose: FakeLimiter implementation
        class FakeLimiter:
            # Purpose: wait implementation
            def wait(self) -> None:
                return None

        # Purpose: FakeOpenAI implementation
        class FakeOpenAI:
            # Purpose:   init   implementation
            def __init__(self, **kwargs: object) -> None:
                captured_client_args.update(kwargs)
                self.responses = SimpleNamespace(create=self._create_response)

            # Purpose:  create response implementation
            # Purpose:  create response implementation
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

    # Purpose: Test anthropic uses explicit base url
    def test_anthropic_uses_explicit_base_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://anthropic-proxy.example")

        captured_client_args: dict[str, object] = {}

        # Purpose: FakeLimiter implementation
        class FakeLimiter:
            # Purpose: wait implementation
            def wait(self) -> None:
                return None

        # Purpose: FakeAnthropic implementation
        class FakeAnthropic:
            # Purpose:   init   implementation
            def __init__(self, **kwargs: object) -> None:
                captured_client_args.update(kwargs)
                self.messages = SimpleNamespace(create=self._create_message)

            # Purpose:  create message implementation
            # Purpose:  create message implementation
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

    # Purpose: Test google uses explicit base url
    def test_google_uses_explicit_base_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.setenv("GEMINI_BASE_URL", "https://gemini-proxy.example")

        captured_client_args: dict[str, object] = {}

        # Purpose: FakeLimiter implementation
        class FakeLimiter:
            # Purpose: wait implementation
            def wait(self) -> None:
                return None

        # Purpose: fake http options implementation
        def fake_http_options(**kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(**kwargs)

        # Purpose: fake generate content config implementation
        def fake_generate_content_config(**kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(**kwargs)

        # Purpose: FakeClient implementation
        class FakeClient:
            # Purpose:   init   implementation
            def __init__(self, **kwargs: object) -> None:
                captured_client_args.update(kwargs)
                self.models = SimpleNamespace(generate_content=self._generate_content)

            # Purpose:  generate content implementation
            # Purpose:  generate content implementation
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

    # Purpose: Test google converts timeout seconds to milliseconds
    def test_google_converts_timeout_seconds_to_milliseconds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.delenv("GEMINI_BASE_URL", raising=False)

        captured_client_args: dict[str, object] = {}

        # Purpose: FakeLimiter implementation
        class FakeLimiter:
            # Purpose: wait implementation
            def wait(self) -> None:
                return None

        # Purpose: fake http options implementation
        def fake_http_options(**kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(**kwargs)

        # Purpose: fake generate content config implementation
        def fake_generate_content_config(**kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(**kwargs)

        # Purpose: FakeClient implementation
        class FakeClient:
            # Purpose:   init   implementation
            def __init__(self, **kwargs: object) -> None:
                captured_client_args.update(kwargs)
                self.models = SimpleNamespace(generate_content=self._generate_content)

            # Purpose:  generate content implementation
            # Purpose:  generate content implementation
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

    # Purpose: Test keyword prompt with literal braces is preserved
    def test_keyword_prompt_with_literal_braces_is_preserved(self) -> None:
        handler = LLMHandler()

        prompt = 'Return JSON like {"keywords": []} and keep {max_keywords} as placeholder.'

        rendered = handler._get_system_prompt(5, prompt)

        assert rendered == prompt

    # Purpose: Test seo prompt with literal braces is preserved
    def test_seo_prompt_with_literal_braces_is_preserved(self) -> None:
        handler = LLMHandler()

        prompt = (
            'Use schema {"faq": []} and variables {language} / {keywords_list} '
            'without crashing on literal braces.'
        )

        rendered = handler._get_seo_prompt("Russian", "- alpha", prompt)

        assert rendered == prompt

    # Purpose: Test generate seo text always uses rendered prompt with content
    def test_generate_seo_text_always_uses_rendered_prompt_with_content(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        handler = LLMHandler()
        captured: dict[str, object] = {}

        # Purpose: fake render implementation
        def fake_render(template, language, keywords, content=None, page_type="product"):
            captured["template"] = template
            captured["language"] = language
            captured["keywords"] = keywords
            captured["content"] = content
            captured["page_type"] = page_type
            return "prompt with content"

        # Purpose: fake execute generation implementation
        def fake_execute_generation(provider, model, prompt, system_prompt, parse_csv=False):
            captured["prompt"] = prompt
            captured["system_prompt"] = system_prompt
            captured["parse_csv"] = parse_csv
            return "generated seo text"

        monkeypatch.setattr(
            LLMHandler,
            "render_seo_prompt_with_content",
            staticmethod(fake_render),
        )
        monkeypatch.setattr(handler, "_execute_generation", fake_execute_generation)

        result = handler.generate_seo_text(
            text="<p>page content</p>",
            keywords=[{"Keyword": "buy coffee", "Avg Monthly Searches": 100}],
            provider="openai",
            model="gpt-test",
            force_refresh=True,
        )

        assert result == "generated seo text"
        assert captured["content"] == "<p>page content</p>"
        assert captured["keywords"] == ["buy coffee (Vol: 100)"]
        assert captured["system_prompt"] == "prompt with content"
        assert captured["parse_csv"] is False

    # Purpose: Test generate seo text always includes content in prompt
    def test_generate_seo_text_always_includes_content_in_prompt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Content is now always included; verify render_seo_prompt_with_content is called with content."""
        handler = LLMHandler()
        captured: dict[str, object] = {}

        # Purpose: fake render implementation
        def fake_render(template, language, keywords, content=None, page_type="product"):
            captured["template"] = template
            captured["language"] = language
            captured["keywords"] = keywords
            captured["content"] = content
            captured["page_type"] = page_type
            return "prompt with content"

        # Purpose: fake execute generation implementation
        def fake_execute_generation(provider, model, prompt, system_prompt, parse_csv=False):
            captured["prompt"] = prompt
            captured["system_prompt"] = system_prompt
            captured["parse_csv"] = parse_csv
            return "generated seo text"

        monkeypatch.setattr(
            LLMHandler,
            "render_seo_prompt_with_content",
            staticmethod(fake_render),
        )
        monkeypatch.setattr(handler, "_execute_generation", fake_execute_generation)

        result = handler.generate_seo_text(
            text="<p>page content</p>",
            keywords=[{"Keyword": "buy coffee", "Avg Monthly Searches": 100}],
            provider="openai",
            model="gpt-test",
            force_refresh=True,
        )

        assert result == "generated seo text"
        assert captured["content"] == "<p>page content</p>"
        assert captured["language"] == "Russian"
        assert captured["keywords"] == ["buy coffee (Vol: 100)"]
        assert captured["system_prompt"] == "prompt with content"


# Purpose: Tests for {page_type} substitution in the SEO prompt renderer.
class TestPageTypePrompt:
    # Purpose: Test page type substituted into prompt
    def test_page_type_substituted_into_prompt(self) -> None:
        template = "Write a {page_type} page in {language} for {keywords_list}."
        rendered = LLMHandler.render_seo_prompt_with_content(
            template=template,
            language="Russian",
            keywords=["buy coffee"],
            content=None,
            page_type="product",
        )
        assert rendered == "Write a product page in RUSSIAN for - buy coffee."

    # Purpose: Test default page type is product
    def test_default_page_type_is_product(self) -> None:
        template = "Type: {page_type}"
        rendered = LLMHandler.render_seo_prompt_with_content(
            template=template,
            language="Russian",
            keywords=["kw"],
        )
        assert rendered == "Type: product"

    # Purpose: Test custom user-defined page type flows through
    def test_custom_page_type_flows_through(self) -> None:
        template = "Type: {page_type}"
        rendered = LLMHandler.render_seo_prompt_with_content(
            template=template,
            language="Russian",
            keywords=["kw"],
            page_type="landing page",
        )
        assert rendered == "Type: landing page"

    # Purpose: Test prompt without page type placeholder is unaffected
    def test_prompt_without_page_type_placeholder_unaffected(self) -> None:
        template = "Write for {language} about {keywords_list}."
        rendered = LLMHandler.render_seo_prompt_with_content(
            template=template,
            language="Russian",
            keywords=["kw"],
            page_type="category",
        )
        assert rendered == "Write for RUSSIAN about - kw."

    # Purpose: Test generate seo text passes page type to renderer
    def test_generate_seo_text_passes_page_type_to_renderer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        handler = LLMHandler()
        captured: dict[str, object] = {}

        def fake_render(template, language, keywords, content=None, page_type="product"):
            captured["page_type"] = page_type
            return "prompt"

        def fake_execute_generation(provider, model, prompt, system_prompt, parse_csv=False):
            return "generated seo text"

        monkeypatch.setattr(
            LLMHandler,
            "render_seo_prompt_with_content",
            staticmethod(fake_render),
        )
        monkeypatch.setattr(handler, "_execute_generation", fake_execute_generation)

        handler.generate_seo_text(
            text="<p>page content</p>",
            keywords=[{"Keyword": "buy coffee", "Avg Monthly Searches": 100}],
            provider="openai",
            model="gpt-test",
            page_type="blog post",
            force_refresh=True,
        )

        assert captured["page_type"] == "blog post"
