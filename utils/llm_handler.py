"""
LLM handler module — manages interactions with various LLM providers.
Rate limiting added (improvement #16).
Type hints added (improvement #5).
"""

import os
import re
import time
from typing import List, Optional, Dict, Any

from tenacity import (
    stop_after_attempt,
    wait_fixed,
    before_sleep_log,
    Retrying,
)
from config.settings import (
    LLM_CONFIG,
    RETRY_ATTEMPTS,
    RETRY_DELAY,
    FALLBACK_PROVIDER,
    FALLBACK_MODEL,
    KEYWORD_EXTRACTION_PROMPT,
    SEO_DESCRIPTION_PROMPT,
    LLM_DELAY_BETWEEN_REQUESTS,
    LLM_TIMEOUT,
    load_config,
)
from utils.logger import logger
from utils.rate_limiter import get_rate_limiter
import logging
from tenacity import RetryCallState

# SDK Imports with safe fallbacks if not installed
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None


# Custom exception for logical flow
class LLMGenerationError(Exception):
    pass


def _log_tenacity_retry(retry_state: RetryCallState) -> None:
    """Log retries with request context (provider/model/mode) for debugging."""
    try:
        llm = retry_state.args[0] if retry_state.args else None
        run_prefix = (
            llm._run_prefix() if llm is not None and hasattr(llm, "_run_prefix") else ""
        )
        provider = retry_state.args[1] if len(retry_state.args) > 1 else "unknown"
        model = retry_state.args[2] if len(retry_state.args) > 2 else "unknown"
        parse_csv = retry_state.kwargs.get("parse_csv", True)
        mode = "keyword_extraction" if parse_csv else "seo_generation"
        sleep_for = (
            retry_state.next_action.sleep
            if retry_state.next_action is not None
            else 0.0
        )
        exc = retry_state.outcome.exception() if retry_state.outcome else None
        logger.warning(
            f"{run_prefix}Retrying LLM {mode} ({provider}/{model}) in {sleep_for:.1f}s due to "
            f"{type(exc).__name__ if exc else 'unknown'}: {exc}"
        )
    except Exception:
        before_sleep_log(logger.main_logger, logging.WARNING)(retry_state)


class LLMHandler:
    def __init__(
        self,
        timeout_seconds: Optional[float] = None,
        delay_between_requests_seconds: Optional[float] = None,
        retry_attempts: Optional[int] = None,
        retry_delay_seconds: Optional[float] = None,
        run_label: str = "",
    ) -> None:
        runtime_config = self._load_runtime_config()
        runtime_llm_config = runtime_config.get("llm", {})
        runtime_retry_config = runtime_config.get("retry", {})

        self.max_keywords: int = LLM_CONFIG.get("max_keywords_per_url", 15)
        if timeout_seconds is None:
            timeout_seconds = runtime_llm_config.get("timeout_seconds", LLM_TIMEOUT)
        if delay_between_requests_seconds is None:
            delay_between_requests_seconds = runtime_llm_config.get(
                "delay_between_requests_seconds", LLM_DELAY_BETWEEN_REQUESTS
            )
        if retry_attempts is None:
            retry_attempts = runtime_retry_config.get("max_attempts", RETRY_ATTEMPTS)
        if retry_delay_seconds is None:
            retry_delay_seconds = runtime_retry_config.get("delay_seconds", RETRY_DELAY)
        self.timeout_seconds: float = float(max(timeout_seconds, 1))
        self.delay_between_requests_seconds: float = float(
            max(delay_between_requests_seconds, 0)
        )
        self.retry_attempts: int = int(max(retry_attempts, 1))
        self.retry_delay_seconds: float = float(max(retry_delay_seconds, 0))
        self.run_label: str = run_label

    @staticmethod
    def _load_runtime_config() -> Dict[str, Any]:
        """Load current config with safe fallback for runtime-adjustable settings."""
        try:
            return load_config()
        except Exception:
            return {}

    def _run_prefix(self) -> str:
        return f"[run {self.run_label}] " if self.run_label else ""

    def _sleep_between_requests(self) -> None:
        """Throttle requests using the current runtime delay."""
        if self.delay_between_requests_seconds > 0:
            time.sleep(self.delay_between_requests_seconds)

    def _build_retrying(self) -> Retrying:
        """Build a retry controller from the current runtime settings."""
        return Retrying(
            stop=stop_after_attempt(self.retry_attempts),
            wait=wait_fixed(self.retry_delay_seconds),
            reraise=True,
            before_sleep=_log_tenacity_retry,
        )

    @staticmethod
    def _clean_llm_response(content: str) -> str:
        """Remove <thinking> blocks and other LLM reasoning artifacts from response."""
        if not content:
            return content
        # Remove <thinking>...</thinking> blocks (case-insensitive, dotall for multiline)
        cleaned = re.sub(
            r"<thinking>.*?</thinking>", "", content, flags=re.DOTALL | re.IGNORECASE
        )
        # Remove any standalone orphan <thinking> or </thinking> tags
        cleaned = re.sub(r"</?thinking>", "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    def _get_system_prompt(self, max_keywords: int, custom_prompt: str = "") -> str:
        """Build keyword extraction system prompt from template or custom prompt."""
        template = (
            custom_prompt.strip()
            if custom_prompt.strip()
            else KEYWORD_EXTRACTION_PROMPT.strip()
        )
        if not template:
            # Hardcoded fallback if no prompt configured at all
            template = (
                "You are an SEO expert. Analyze the webpage content and extract {max_keywords} "
                "high-intent commercial keywords suitable for Google Ads campaigns in RUSSIAN and UKRAINIAN.\n\n"
                "REQUIREMENTS:\n"
                "- Focus on transactional/commercial intent (buy, price, order, delivery)\n"
                "- Phrases of 2-4 words preferred\n"
                "- STRICTLY ONLY Russian or Ukrainian language\n"
                "- Avoid informational or generic terms (about, main, home)\n"
                "- Return ONLY a comma-separated list. No numbering, no introduction.\n\n"
                "Example Output:\n"
                "купить кофемашину киев, кава в зернах ціна, профессиональные кофемолки, оренда кавоварок"
            )
        try:
            return template.format(max_keywords=max_keywords)
        except (KeyError, IndexError, ValueError) as e:
            logger.warning(
                f"Prompt template formatting error: {e}. Using template as-is."
            )
            return template

    def _get_seo_prompt(
        self, language: str, kw_list_str: str, custom_prompt: str = ""
    ) -> str:
        """Build SEO description system prompt from template or custom prompt."""
        template = (
            custom_prompt.strip()
            if custom_prompt.strip()
            else SEO_DESCRIPTION_PROMPT.strip()
        )
        if not template:
            # Hardcoded fallback
            template = (
                "You are a professional SEO Copywriter who writes for humans, not robots.\n\n"
                "TASK:\n"
                "Write a category or product description text based on the provided page content "
                "and target keywords. The text must be written strictly in {language} language.\n\n"
                "REQUIREMENTS:\n"
                "1. STYLE: Simple, engaging, human-like language. Write in {language}.\n"
                "2. FORMAT: Use ONLY these HTML tags: <p>, <b>, <br/>, <u>, <i>.\n"
                "3. KEYWORDS: Naturally integrate the provided high-volume keywords.\n"
                "4. LSI: Use Latent Semantic Indexing (LSI) terms naturally.\n"
                "5. STRUCTURE:\n"
                "   - Engaging introduction.\n"
                "   - Main body describing the value/features.\n"
                "   - Conclusion.\n"
                "   - **FAQ SECTION**: 3-5 relevant questions and answers.\n\n"
                "INPUT KEYWORDS (incorporate naturally):\n"
                "{keywords_list}\n\n"
                'Refrain from using "In conclusion", "In this article", etc.'
            )
        try:
            return template.format(language=language.upper(), keywords_list=kw_list_str)
        except (KeyError, IndexError, ValueError) as e:
            logger.warning(
                f"SEO prompt template formatting error: {e}. Using template as-is."
            )
            return template

    def _call_openai_compatible(
        self,
        provider: str,
        model: str,
        prompt: str,
        system_prompt: str,
        request_timeout: float,
    ) -> str:
        api_key_env: str = f"{provider.upper()}_API_KEY"
        api_key: Optional[str] = os.getenv(api_key_env)

        base_url_env: str = f"{provider.upper()}_BASE_URL"
        base_url: Optional[str] = os.getenv(base_url_env)

        DEFAULT_BASE_URLS: Dict[str, str] = {
            "xai": "https://api.x.ai/v1",
            "groq": "https://api.groq.com/openai/v1",
            "deepseek": "https://api.deepseek.com/v1",
            "minimax": "https://api.minimax.io/v1",
            "moonshot": "https://api.moonshot.cn/v1",
            "openrouter": "https://openrouter.ai/api/v1",
            "cerebras": "https://api.cerebras.ai/v1",
            "mistral": "https://api.mistral.ai/v1",
            "zai": "https://api.z.ai/api/coding/paas/v4",
        }

        if not base_url and provider in DEFAULT_BASE_URLS:
            base_url = DEFAULT_BASE_URLS[provider]

        if not api_key:
            if provider != "openai":
                if provider == "openrouter":
                    api_key = os.getenv("OPENROUTER_API_KEY")

                if not api_key:
                    raise LLMGenerationError(
                        f"API Key not found for {provider} ({api_key_env})"
                    )
            else:
                api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise LLMGenerationError(f"Missing API key for {provider}")

        if OpenAI is None:
            raise LLMGenerationError(
                "OpenAI SDK is not installed. Install it with: pip install openai"
            )

        if base_url:
            if provider == "openai" and (
                "aliyuncs.com" in base_url or "compatible-mode" in base_url
            ):
                logger.warning(
                    f"{self._run_prefix()}[{provider}] Detected DashScope/Aliyun base_url '{base_url}' "
                    f"which may not support model '{model}'. Reverting to official OpenAI URL."
                )
                base_url = "https://api.openai.com/v1"

            if base_url and base_url != "https://api.openai.com/v1":
                logger.info(
                    f"{self._run_prefix()}[{provider}] Using Custom Base URL: {base_url}"
                )
            else:
                logger.info(
                    f"{self._run_prefix()}[{provider}] Using Default Base URL (Official OpenAI)"
                )
        else:
            logger.info(
                f"{self._run_prefix()}[{provider}] Using Default Base URL (Official OpenAI)"
            )

        client_args: Dict[str, Any] = {
            "api_key": api_key,
            "base_url": base_url,
            "timeout": request_timeout,
        }

        if provider == "openrouter":
            client_args["default_headers"] = {
                "HTTP-Referer": "http://localhost:8501",
                "X-Title": "Auto SEO Keyword Planner",
            }

        client = OpenAI(**client_args)

        # Rate limiting (improvement #16)
        limiter = get_rate_limiter(provider)
        limiter.wait()

        # Configurable delay between requests
        self._sleep_between_requests()

        start_time: float = time.time()

        content: str = ""

        if provider == "openai" and hasattr(client, "responses"):
            logger.log_api_request(
                provider,
                f"responses.create ({model})",
                {"prompt": prompt[:100] + "..."},
            )
            try:
                input_messages: List[Dict[str, str]] = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ]

                response = client.responses.create(model=model, input=input_messages)

                if hasattr(response, "output_text"):
                    content = response.output_text
                else:
                    content = str(response)

            except Exception as e:
                logger.warning(
                    f"Responses API failed for {model}, falling back to chat.completions: {e}"
                )
        if not content:
            logger.log_api_request(
                provider,
                f"chat.completions ({model})",
                {"prompt": prompt[:100] + "..."},
            )

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
            )
            content = response.choices[0].message.content or ""

        duration: float = time.time() - start_time
        logger.log_api_response(provider, duration, content[:200] + "...")

        return content

    def _call_anthropic(
        self,
        model: str,
        prompt: str,
        system_prompt: str,
        request_timeout: float,
    ) -> str:
        api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
        base_url: Optional[str] = os.getenv("ANTHROPIC_BASE_URL")
        if not api_key:
            raise LLMGenerationError("ANTHROPIC_API_KEY is missing")

        if Anthropic is None:
            raise LLMGenerationError(
                "Anthropic SDK is not installed. Install it with: pip install anthropic"
            )

        client_args: Dict[str, Any] = {
            "api_key": api_key,
            "timeout": request_timeout,
        }
        if base_url:
            client_args["base_url"] = base_url
            logger.info(
                f"{self._run_prefix()}[anthropic] Using Custom Base URL: {base_url}"
            )

        client = Anthropic(**client_args)

        # Rate limiting (improvement #16)
        limiter = get_rate_limiter("anthropic")
        limiter.wait()

        # Configurable delay between requests
        self._sleep_between_requests()

        start_time: float = time.time()
        logger.log_api_request(
            "anthropic",
            f"messages.create ({model})",
            {"prompt": prompt[:100] + "..."},
        )

        response = client.messages.create(
            model=model,
            max_tokens=8192,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )

        duration: float = time.time() - start_time
        content: str = response.content[0].text
        logger.log_api_response("anthropic", duration, content[:200] + "...")

        return content

    def _call_google(
        self,
        model: str,
        prompt: str,
        system_prompt: str,
        request_timeout: float,
    ) -> str:
        api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
        base_url: Optional[str] = os.getenv("GEMINI_BASE_URL")
        if not api_key:
            raise LLMGenerationError("GEMINI_API_KEY is missing")

        if genai is None:
            raise LLMGenerationError(
                "Google GenAI SDK is not installed. Install it with: pip install google-genai"
            )

        timeout_ms: int = int(max(request_timeout, 10.0) * 1000)
        http_options_args: Dict[str, Any] = {
            "timeout": timeout_ms,
        }
        if base_url:
            http_options_args["base_url"] = base_url
            logger.info(f"{self._run_prefix()}[google] Using Custom Base URL: {base_url}")

        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(**http_options_args),
        )

        full_prompt: str = f"{system_prompt}\n\nTEXT:\n{prompt}"

        # Rate limiting (improvement #16)
        limiter = get_rate_limiter("google")
        limiter.wait()

        # Configurable delay between requests
        self._sleep_between_requests()

        start_time: float = time.time()
        logger.log_api_request(
            "google",
            f"generate_content ({model})",
            {"prompt": full_prompt[:100] + "..."},
        )

        response = client.models.generate_content(
            model=model,
            contents=full_prompt,
            config=types.GenerateContentConfig(temperature=0.7),
        )

        duration: float = time.time() - start_time
        content: str = response.text
        logger.log_api_response("google", duration, content[:200] + "...")

        return content

    def generate_keywords(
        self,
        text: str,
        provider: str,
        model: str,
        max_keywords: int = 15,
        custom_prompt: str = "",
    ) -> List[str]:
        """
        Generate keywords with retry and fallback logic.

        Args:
            text: Page content text.
            provider: LLM provider name.
            model: Model name.
            max_keywords: Maximum number of keywords to extract.
            custom_prompt: Optional custom system prompt template (with {max_keywords} placeholder).
        """
        system_prompt: str = self._get_system_prompt(max_keywords, custom_prompt)
        truncated_text: str = text[:12000]

        try:
            return self._execute_generation(
                provider, model, truncated_text, system_prompt
            )
        except Exception as e:
            logger.error(f"{self._run_prefix()}Primary provider {provider} failed: {e}")
            logger.info(
                f"{self._run_prefix()}Attempting fallback to {FALLBACK_PROVIDER}"
            )

            fallback_model: str = FALLBACK_MODEL

            try:
                return self._execute_generation(
                    FALLBACK_PROVIDER, fallback_model, truncated_text, system_prompt
                )
            except Exception as e2:
                logger.error(
                    f"{self._run_prefix()}Fallback provider {FALLBACK_PROVIDER} also failed: {e2}"
                )
                return []

    def _execute_generation(
        self,
        provider: str,
        model: str,
        text: str,
        system_prompt: str,
        parse_csv: bool = True,
    ) -> Any:
        """Execute generation with runtime-configured retries."""
        retrier = self._build_retrying()
        return retrier(
            LLMHandler._execute_generation_once,
            self,
            provider,
            model,
            text,
            system_prompt,
            parse_csv=parse_csv,
        )

    def _execute_generation_once(
        self,
        provider: str,
        model: str,
        text: str,
        system_prompt: str,
        parse_csv: bool = True,
    ) -> Any:
        """Core execution logic mapped to provider."""
        provider = provider.lower()
        request_timeout: float = (
            float(max(self.timeout_seconds * 3, 60))
            if not parse_csv
            else float(self.timeout_seconds)
        )

        content: str = ""
        if provider == "anthropic":
            content = self._call_anthropic(
                model, text, system_prompt, request_timeout=request_timeout
            )
        elif provider == "google" or provider == "google gemini":
            content = self._call_google(
                model,
                text,
                system_prompt,
                request_timeout=request_timeout,
            )
        else:
            content = self._call_openai_compatible(
                provider,
                model,
                text,
                system_prompt,
                request_timeout=request_timeout,
            )

        # Clean LLM response: strip <thinking> blocks and other artifacts
        content = self._clean_llm_response(content)

        if not parse_csv:
            return content

        # Parse CSV
        keywords: List[str] = [kw.strip() for kw in content.split(",")]
        return [kw for kw in keywords if kw]

    def generate_seo_text(
        self,
        text: str,
        keywords: List[Dict[str, Any]],
        provider: str,
        model: str,
        language: str = "Russian",
        custom_prompt: str = "",
    ) -> str:
        """
        Generate SEO optimization text based on page content and keywords.

        Args:
            text: Page content text.
            keywords: List of keyword dicts with 'Keyword' and optional 'Avg Monthly Searches'.
            provider: LLM provider name.
            model: Model name.
            language: Target language for the generated text.
            custom_prompt: Optional custom system prompt template (with {language}, {keywords_list} placeholders).
        """
        kw_list_str: str = "\n".join(
            [
                f"- {k['Keyword']} (Vol: {k.get('Avg Monthly Searches', 'N/A')})"
                for k in keywords[:20]
            ]
        )

        system_prompt: str = self._get_seo_prompt(language, kw_list_str, custom_prompt)

        truncated_text: str = text[:15000]

        try:
            return self._execute_generation(
                provider, model, truncated_text, system_prompt, parse_csv=False
            )
        except Exception as e:
            logger.error(f"{self._run_prefix()}SEO Text Generation failed: {e}")
            logger.info(
                f"{self._run_prefix()}Attempting fallback to {FALLBACK_PROVIDER}"
            )
            fallback_model: str = FALLBACK_MODEL
            try:
                return self._execute_generation(
                    FALLBACK_PROVIDER,
                    fallback_model,
                    truncated_text,
                    system_prompt,
                    parse_csv=False,
                )
            except Exception as e2:
                logger.error(
                    f"{self._run_prefix()}Fallback text generation failed: {e2}"
                )
                return "Error generating SEO text. Please check logs for details."


LLMHandler._execute_generation.__wrapped__ = LLMHandler._execute_generation_once
