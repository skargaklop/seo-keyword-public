"""
LLM handler module — manages interactions with various LLM providers.
Rate limiting added (improvement #16).
Type hints added (improvement #5).
"""

import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup
from config.settings import (
    CUSTOM_PROVIDERS,
    FALLBACK_MODEL,
    FALLBACK_PROVIDER,
    KEYWORD_EXTRACTION_PROMPT,
    LLM_CONFIG,
    LLM_DELAY_BETWEEN_REQUESTS,
    LLM_TIMEOUT,
    RETRY_ATTEMPTS,
    RETRY_DELAY,
    SEO_DESCRIPTION_PROMPT,
    load_config,
)
from tenacity import (
    RetryCallState,
    Retrying,
    before_sleep_log,
    retry_if_exception,
    stop_after_attempt,
    wait_fixed,
)

from utils.logger import logger
from utils.model_fetcher import PROVIDER_BASE_URLS
from utils.rate_limiter import get_rate_limiter
from utils.request_cache import build_cache_key, request_cache

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


# MODULE_CONTRACT: llm_handler
# Purpose: Multi-provider LLM abstraction supporting OpenAI, Anthropic, Google Gemini, XAI, Groq, and other OpenAI-compatible APIs
# Rationale: Centralizes keyword extraction and SEO text generation with retry logic, rate limiting, and provider fallback
# Dependencies: openai SDK, anthropic SDK, google.genai SDK, tenacity, config.settings (incl. CUSTOM_PROVIDERS), utils.rate_limiter, utils.logger, utils.model_fetcher.PROVIDER_BASE_URLS
# Exports: LLMHandler (class with generate_keywords, generate_seo_text), LLMGenerationError, LLMNonRetriableCredentialError, is_non_retriable_credential_error
# LINKS: requirements.xml#UC-001, requirements.xml#UC-004, technology.xml#SVC-001, development-plan.xml#MOD-004
# MODULE_MAP: llm_handler
# Public Functions: LLMHandler.generate_keywords(), LLMHandler.generate_seo_text()
# Private Helpers: _call_openai_compatible(), _call_anthropic(), _call_google(), _execute_generation(), _execute_generation_once(), _build_retrying(), _get_system_prompt(), _get_seo_prompt(), _clean_llm_response(), _sleep_between_requests(), _run_prefix(), _extract_error_status_and_body(), _raise_if_non_retriable_credential_error(), _cache_generation_result(), _execute_fallback_and_cache()
# Key Semantic Blocks: block_llm_keyword_extraction, block_llm_seo_generation, block_llm_provider_routing, block_llm_error_classify_retry
# Critical Flows: Provider routing -> API call with rate limiting -> retry on failure -> fallback provider on persistent failure
# Verification: verification-plan.xml#V-MOD-004
# CHANGE_SUMMARY: Replaced shallow GRACE markers with complete module-level contracts; Phase 8 Plan 03: classified non-retriable credential-routing errors to skip repeated retries and use secret-safe fallback logging; Phase 9 review fix: SEO prompt generation can include sanitized scraped content while preserving keyword volume hints.

# CLASS_CONTRACT: LLMGenerationError
# Purpose: Signal handled LLM generation failures for retry and fallback logic.
# LINKS: requirements.xml#UC-004
class LLMGenerationError(Exception):
    pass


# CLASS_CONTRACT: LLMNonRetriableCredentialError
# Purpose: Signal expected provider credential/routing failures that must not be retried.
# LINKS: PLAN 08-03 Task 1
class LLMNonRetriableCredentialError(LLMGenerationError):
    pass


NON_RETRIABLE_CREDENTIAL_MARKER = (
    "[GRACE:block_llm_error_classify_retry:NON_RETRIABLE_CREDENTIAL]"
)
NON_RETRIABLE_CREDENTIAL_MESSAGES = (
    "no credentials for provider",
    "invalid api key",
    "authentication failed",
    "provider not found",
    "invalid argument",
    "input cannot be empty",
)


# block_llm_error_classify_retry: Classify expected credential/routing failures before retry
# Semantic block: OpenAI-compatible 400 credential errors bypass tenacity retries and may fallback once.


# FUNCTION_CONTRACT: is_non_retriable_credential_error
# Purpose: Detect OpenAI-compatible provider credential/routing failures that retry cannot fix.
# Input: status_code (int), response_body (dict)
# Output: bool
# Side Effects: none
# Business Rules: Only 400-class routing/credential messages are treated as non-retriable.
# Failure Modes: never raises; malformed bodies return False.
# LINKS: PLAN 08-03 Task 1
def is_non_retriable_credential_error(status_code: int, response_body: dict) -> bool:
    try:
        status = int(status_code)
    except (TypeError, ValueError):
        return False
    if status != 400:
        return False

    body_text = _stringify_error_body(response_body).lower()
    return any(marker in body_text for marker in NON_RETRIABLE_CREDENTIAL_MESSAGES)


# FUNCTION_CONTRACT: _stringify_error_body
# Purpose: Convert provider error body into lowercase-searchable text without assuming schema.
# Input: response_body (Any)
# Output: str
# Side Effects: none
# Business Rules: Handles OpenAI-compatible {"error": {"message": ...}} bodies and fallback strings.
# Failure Modes: never raises.
# LINKS: PLAN 08-03 Task 1
def _stringify_error_body(response_body: Any) -> str:
    if response_body is None:
        return ""
    if isinstance(response_body, dict):
        parts: List[str] = []
        for value in response_body.values():
            parts.append(_stringify_error_body(value))
        return " ".join(part for part in parts if part)
    if isinstance(response_body, (list, tuple)):
        return " ".join(_stringify_error_body(item) for item in response_body)
    return str(response_body)


# FUNCTION_CONTRACT: _extract_error_status_and_body
# Purpose: Extract status code and response body from SDK/provider exceptions.
# Input: exc (BaseException)
# Output: tuple[int, dict]
# Side Effects: may call response.json() on exception response object.
# Business Rules: Supports OpenAI SDK status_code/body plus generic response.status_code/json/text.
# Failure Modes: never raises; unknown values return (0, {"message": str(exc)}).
# LINKS: PLAN 08-03 Task 1
def _extract_error_status_and_body(exc: BaseException) -> tuple[int, dict]:
    status_code = getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    if status_code is None and response is not None:
        status_code = getattr(response, "status_code", None)

    body = getattr(exc, "body", None)
    if body is None and response is not None:
        try:
            body = response.json()
        except Exception:
            body = getattr(response, "text", None)

    if body is None:
        body = {"message": str(exc)}
    elif not isinstance(body, dict):
        body = {"message": str(body)}

    try:
        status = int(status_code or 0)
    except (TypeError, ValueError):
        status = 0
    return status, body


# FUNCTION_CONTRACT: _provider_from_credential_error
# Purpose: Prefer provider named in credential-routing body when available.
# Input: default_provider (str), response_body (dict)
# Output: str
# Side Effects: none
# Business Rules: Extracts "No credentials for provider: X" without exposing body text.
# Failure Modes: never raises.
# LINKS: PLAN 08-03 Task 1
def _provider_from_credential_error(default_provider: str, response_body: dict) -> str:
    body_text = _stringify_error_body(response_body)
    match = re.search(
        r"no credentials for provider\s*:\s*([A-Za-z0-9._/-]+)",
        body_text,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)
    return default_provider
# FUNCTION_CONTRACT: _log_tenacity_retry
# Purpose: Implement the  log tenacity retry helper for this module.
# Input: retry_state (RetryCallState)
# Output: None
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def _log_tenacity_retry(retry_state: RetryCallState) -> None:
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

# CLASS_CONTRACT: LLMHandler
# Purpose: Route keyword and SEO text generation across configured LLM providers.
# LINKS: requirements.xml#UC-001, requirements.xml#UC-004
class LLMHandler:
    # FUNCTION_CONTRACT: __init__
    # Purpose: Initialize the surrounding object state.
    # Input: timeout_seconds (Optional[float] = None), delay_between_requests_seconds (Optional[float] = None), retry_attempts (Optional[int] = None), retry_delay_seconds (Optional[float] = None), run_label (str = '')
    # Output: None
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
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
    # FUNCTION_CONTRACT: _load_runtime_config
    # Purpose: Implement the  load runtime config helper for this module.
    # Input: (none)
    # Output: Dict[str, Any]
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    def _load_runtime_config() -> Dict[str, Any]:
        try:
            return load_config()
        except Exception:
            return {}
    # FUNCTION_CONTRACT: _run_prefix
    # Purpose: Implement the  run prefix helper for this module.
    # Input: (none)
    # Output: str
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def _run_prefix(self) -> str:
        return f"[run {self.run_label}] " if self.run_label else ""
    # FUNCTION_CONTRACT: _sleep_between_requests
    # Purpose: Implement the  sleep between requests helper for this module.
    # Input: (none)
    # Output: None
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def _sleep_between_requests(self) -> None:
        if self.delay_between_requests_seconds > 0:
            time.sleep(self.delay_between_requests_seconds)
    # FUNCTION_CONTRACT: _build_retrying
    # Purpose: Implement the  build retrying helper for this module.
    # Input: (none)
    # Output: Retrying
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def _build_retrying(self) -> Retrying:
        return Retrying(
            stop=stop_after_attempt(self.retry_attempts),
            wait=wait_fixed(self.retry_delay_seconds),
            reraise=True,
            before_sleep=_log_tenacity_retry,
            retry=retry_if_exception(
                lambda exc: not isinstance(exc, LLMNonRetriableCredentialError)
            ),
        )
    # FUNCTION_CONTRACT: _has_provider_credentials
    # Purpose: Check whether configured fallback provider has credentials before attempting fallback.
    # Input: provider (str)
    # Output: bool
    # Side Effects: reads environment variables.
    # Business Rules: Supports built-in providers plus custom provider api_key_env from settings.yaml.
    # Failure Modes: never raises; missing provider/key returns False.
    # LINKS: PLAN 08-03 Task 1
    @staticmethod
    def _has_provider_credentials(provider: str) -> bool:
        normalized_provider = str(provider or "").lower()
        if not normalized_provider:
            return False

        for custom_provider in CUSTOM_PROVIDERS:
            if normalized_provider == str(custom_provider.get("name", "")).lower():
                api_key_env = custom_provider.get(
                    "api_key_env", f"{normalized_provider.upper()}_API_KEY"
                )
                return bool(os.getenv(str(api_key_env), ""))

        if normalized_provider == "openai":
            return bool(os.getenv("OPENAI_API_KEY", ""))
        if normalized_provider == "openrouter":
            return bool(os.getenv("OPENROUTER_API_KEY", ""))
        if normalized_provider in {"google", "google gemini"}:
            return bool(os.getenv("GEMINI_API_KEY", ""))
        if normalized_provider == "anthropic":
            return bool(os.getenv("ANTHROPIC_API_KEY", ""))
        return bool(os.getenv(f"{normalized_provider.upper()}_API_KEY", ""))

    # FUNCTION_CONTRACT: _execute_fallback_generation
    # Purpose: Attempt fallback provider once after primary provider failure when credentials are configured.
    # Input: primary_provider, text, system_prompt, parse_csv
    # Output: Optional[Any]
    # Side Effects: may call fallback LLM provider and writes concise logs.
    # Business Rules: Skips fallback when provider is missing, same as primary, or lacks credentials.
    # Failure Modes: returns None on fallback failure; logs expected credential errors without traceback.
    # LINKS: PLAN 08-03 Task 1
    def _execute_fallback_generation(
        self,
        primary_provider: str,
        text: str,
        system_prompt: str,
        parse_csv: bool = True,
    ) -> Optional[Any]:
        fallback_provider = str(FALLBACK_PROVIDER or "").lower()
        primary_provider = str(primary_provider or "").lower()
        if not fallback_provider or fallback_provider == primary_provider:
            return None
        if not self._has_provider_credentials(fallback_provider):
            logger.warning(
                f"{self._run_prefix()}Fallback provider {FALLBACK_PROVIDER} has no configured credentials; fallback skipped."
            )
            return None

        try:
            logger.info(f"{self._run_prefix()}Attempting fallback to {FALLBACK_PROVIDER}")
            return self._execute_generation(
                FALLBACK_PROVIDER,
                FALLBACK_MODEL,
                text,
                system_prompt,
                parse_csv=parse_csv,
            )
        except LLMNonRetriableCredentialError as exc:
            logger.warning(f"{self._run_prefix()}Fallback credential error: {exc}")
        except Exception as exc:
            logger.error(f"{self._run_prefix()}Fallback provider {FALLBACK_PROVIDER} also failed: {exc}")
        return None

    # FUNCTION_CONTRACT: _cache_generation_result
    # Purpose: Store a generation result in the shared cache when one exists.
    # Input: kind (str), cache_key (str), request_params (Dict[str, Any]), result (Optional[Any]), provider (str)
    # Output: Optional[Any]
    # Side Effects: Writes the generation result to request_cache only when result is not None.
    # Business Rules: Preserves the exact cache record path used by keyword and SEO result branches.
    # Failure Modes: Propagates upstream exceptions from request_cache.set unchanged.
    # LINKS: PLAN 08-03 Task 1
    def _cache_generation_result(
        self,
        kind: str,
        cache_key: str,
        request_params: Dict[str, Any],
        result: Optional[Any],
        provider: str,
    ) -> Optional[Any]:
        if result is not None:
            request_cache.set(
                kind=kind,
                cache_key=cache_key,
                request_params=request_params,
                result=result,
                provider=provider,
            )
        return result

    # FUNCTION_CONTRACT: _cache_fallback_result
    # Purpose: Store a fallback generation result in the shared cache when one exists.
    # Input: kind (str), cache_key (str), request_params (Dict[str, Any]), result (Optional[Any]), provider (str)
    # Output: Optional[Any]
    # Side Effects: Writes the fallback result to request_cache only when result is not None.
    # Business Rules: Preserves the exact cache record path used by keyword and SEO fallback branches.
    # Failure Modes: Propagates upstream exceptions from request_cache.set unchanged.
    # LINKS: PLAN 08-03 Task 1
    def _cache_fallback_result(
        self,
        kind: str,
        cache_key: str,
        request_params: Dict[str, Any],
        result: Optional[Any],
        provider: str,
    ) -> Optional[Any]:
        return self._cache_generation_result(
            kind=kind,
            cache_key=cache_key,
            request_params=request_params,
            result=result,
            provider=provider,
        )

    # FUNCTION_CONTRACT: _execute_fallback_and_cache
    # Purpose: Execute fallback generation and store the result when one exists.
    # Input: primary_provider (str), text (str), system_prompt (str), kind (str), cache_key (str), request_params (Dict[str, Any]), parse_csv (bool = True)
    # Output: Optional[Any]
    # Side Effects: May call the fallback provider and writes any successful fallback result to cache.
    # Business Rules: Preserves the current fallback provider and cache record semantics.
    # Failure Modes: never raises; returns None on fallback failure.
    # LINKS: PLAN 08-03 Task 1
    def _execute_fallback_and_cache(
        self,
        primary_provider: str,
        text: str,
        system_prompt: str,
        kind: str,
        cache_key: str,
        request_params: Dict[str, Any],
        parse_csv: bool = True,
    ) -> Optional[Any]:
        fallback_result = self._execute_fallback_generation(
            primary_provider,
            text,
            system_prompt,
            parse_csv=parse_csv,
        )
        return self._cache_generation_result(
            kind=kind,
            cache_key=cache_key,
            request_params=request_params,
            result=fallback_result,
            provider=primary_provider,
        )

    # FUNCTION_CONTRACT: _raise_if_non_retriable_credential_error
    # Purpose: Convert provider credential-routing errors into a non-retryable exception.
    # Input: provider (str), exc (BaseException)
    # Output: None
    # Side Effects: emits GRACE marker and secret-safe warning when classification matches.
    # Business Rules: Does not log raw provider body or traceback for expected credential errors.
    # Failure Modes: re-raises only when classification matches.
    # LINKS: PLAN 08-03 Task 1
    def _raise_if_non_retriable_credential_error(
        self,
        provider: str,
        exc: BaseException,
    ) -> None:
        status_code, response_body = _extract_error_status_and_body(exc)
        if not is_non_retriable_credential_error(status_code, response_body):
            return

        routed_provider = _provider_from_credential_error(provider, response_body)
        message = f"Credential error for {routed_provider}; retry skipped."
        logger.log_secret_safe_event(
            NON_RETRIABLE_CREDENTIAL_MARKER,
            message,
            level="warning",
        )
        raise LLMNonRetriableCredentialError(message) from exc
    # FUNCTION_CONTRACT: _clean_llm_response
    # Purpose: Implement the  clean llm response helper for this module.
    # Input: content (str)
    # Output: str
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    def _clean_llm_response(content: str) -> str:
        if not content:
            return content
        # Remove <thinking>...</thinking> blocks (case-insensitive, dotall for multiline)
        cleaned = re.sub(
            r"<thinking>.*?</thinking>", "", content, flags=re.DOTALL | re.IGNORECASE
        )
        # Remove any standalone orphan <thinking> or </thinking> tags
        cleaned = re.sub(r"</?thinking>", "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip()
    # FUNCTION_CONTRACT: _get_system_prompt
    # Purpose: Implement the  get system prompt helper for this module.
    # Input: max_keywords (int), custom_prompt (str = '')
    # Output: str
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def _get_system_prompt(self, max_keywords: int, custom_prompt: str = "") -> str:
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
    # FUNCTION_CONTRACT: _get_seo_prompt
    # Purpose: Implement the  get seo prompt helper for this module.
    # Input: language (str), kw_list_str (str), custom_prompt (str = '')
    # Output: str
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def _get_seo_prompt(
        self, language: str, kw_list_str: str, custom_prompt: str = ""
    ) -> str:
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

    # FUNCTION_CONTRACT: _strip_html_safe
    # Purpose: Safely strip HTML tags using BeautifulSoup (CR-01 fix)
    # Input: content (str)
    # Output: str - text content with HTML tags removed
    # Side Effects: (none - pure function)
    # Business Rules: Use BeautifulSoup parser instead of regex for security
    # Failure Modes: Returns empty string on parse error
    # LINKS: CR-01 Phase 9 Code Review
    @staticmethod
    def _strip_html_safe(content: str) -> str:
        try:
            soup = BeautifulSoup(content, 'html.parser')
            return soup.get_text(separator=' ', strip=True)
        except Exception:
            # Fallback to empty string on parse error
            return ""

    # FUNCTION_CONTRACT: render_seo_prompt_with_content
    # Purpose: Render SEO prompt with {language}, {keywords_list}, {page_type}, and optional {content}
    # Input: template (str), language (str), keywords (List[str]), content (Optional[str]), page_type (str = 'product')
    # Output: str
    # Side Effects: (none - pure formatter)
    # Business Rules: Only substitute known variables, smart truncation, handle missing content
    # Failure Modes: Returns template as-is on formatting errors
    # LINKS: PLAN 09-04 Task 10
    @staticmethod
    def render_seo_prompt_with_content(
        template: str,
        language: str,
        keywords: List[str],
        content: Optional[str] = None,
        page_type: str = "product",
    ) -> str:
        # Build keywords list string
        kw_list_str = "\n".join([f"- {kw}" for kw in keywords[:20]])

        # Prepare content text (empty string when None/empty)
        content_text = ""
        if content:
            # Strip HTML tags using safe parser (CR-01 fix)
            clean_content = LLMHandler._strip_html_safe(content)
            # Smart truncate at word boundary (max 5000 chars)
            if len(clean_content) > 5000:
                truncated = clean_content[:5000]
                last_space = truncated.rfind(' ')
                if last_space > 0:
                    clean_content = truncated[:last_space]
                else:
                    clean_content = truncated
            content_text = clean_content.strip()

        # Safe format with only known variables
        try:
            # Use a custom format that only substitutes known keys
            result = template
            result = result.replace("{language}", language.upper())
            result = result.replace("{keywords_list}", kw_list_str)
            result = result.replace("{page_type}", page_type)
            result = result.replace("{content}", content_text)
            return result
        except Exception as e:
            logger.warning(f"SEO prompt formatting error: {e}. Using template as-is.")
            return template

    # FUNCTION_CONTRACT: _call_openai_compatible
    # Purpose: Implement the  call openai compatible helper for this module.
    # Input: provider (str), model (str), prompt (str), system_prompt (str), request_timeout (float)
    # Output: str
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
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

        # Check custom providers first
        for cp in CUSTOM_PROVIDERS:
            if provider == cp["name"].lower():
                base_url = cp["base_url"]
                api_key_env = cp.get("api_key_env", f"{provider.upper()}_API_KEY")
                api_key = os.getenv(api_key_env)
                break
        else:
            # PROVIDER_BASE_URLS lookup (single source of truth from model_fetcher)
            if not base_url and provider in PROVIDER_BASE_URLS:
                base_url = PROVIDER_BASE_URLS[provider]

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
            k: v for k, v in {
                "api_key": api_key,
                "base_url": base_url,
                "timeout": request_timeout,
            }.items() if v is not None
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
            # Guard: Vertex AI (via custom providers) rejects empty user content
            # with 400 INVALID_ARGUMENT and 'Model input cannot be empty'
            effective_prompt = prompt.strip() if prompt else ""
            if not effective_prompt:
                # Merge system instructions into user message so Vertex has
                # a non-empty contents[] array
                effective_prompt = system_prompt or "."
                messages_for_api = [{"role": "user", "content": effective_prompt}]
            else:
                messages_for_api = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ]

            logger.log_api_request(
                provider,
                f"chat.completions ({model})",
                {"prompt": effective_prompt[:100] + "..."},
            )

            response = client.chat.completions.create(
                model=model,
                messages=messages_for_api,
                temperature=0.7,
            )
            content = response.choices[0].message.content or ""

        duration: float = time.time() - start_time
        logger.log_api_response(provider, duration, content[:200] + "...")

        return content
    # FUNCTION_CONTRACT: _call_anthropic
    # Purpose: Implement the  call anthropic helper for this module.
    # Input: model (str), prompt (str), system_prompt (str), request_timeout (float)
    # Output: str
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
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
        if response.content and hasattr(response.content[0], "text"):
            content: str = response.content[0].text or ""
        else:
            content = ""
        logger.log_api_response("anthropic", duration, content[:200] + "...")

        return content
    # FUNCTION_CONTRACT: _call_google
    # Purpose: Implement the  call google helper for this module.
    # Input: model (str), prompt (str), system_prompt (str), request_timeout (float)
    # Output: str
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
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
        content: str = response.text or ""
        logger.log_api_response("google", duration, content[:200] + "...")

        return content
    # FUNCTION_CONTRACT: generate_keywords
    # Purpose: Implement the generate keywords helper for this module.
    # Input: text (str), provider (str), model (str), max_keywords (int = 15), custom_prompt (str = ''), force_refresh (bool = False)
    # Output: List[str]
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function; uses cache lookup
    # Business Rules: Preserves the current validation and control flow for this call path; checks cache before LLM call
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001, PLAN 10-02 Task 6
    def generate_keywords(
        self,
        text: str,
        provider: str,
        model: str,
        max_keywords: int = 15,
        custom_prompt: str = "",
        force_refresh: bool = False,
    ) -> List[str]:
        import hashlib

        # Build text hash for cache key (keep key size reasonable)
        text_hash = hashlib.sha256(text[:10000].encode()).hexdigest()[:16]

        # Hash prompt if present
        prompt_hash = ""
        if custom_prompt:
            prompt_hash = hashlib.sha256(custom_prompt.encode()).hexdigest()[:16]

        params = {
            "text_hash": text_hash,
            "provider": str(provider).lower(),
            "model": str(model).lower(),
            "max_keywords": int(max_keywords),
            "prompt_hash": prompt_hash,
        }

        cache_key = build_cache_key(
            kind="llm_extract",
            provider=params["provider"],
            params=params,
        )

        # Check cache
        cached = request_cache.get(cache_key, force_refresh=force_refresh)
        if cached is not None:
            logger.info(
                f"{self._run_prefix()}[GRACE:block_llm_cache_lookup:HIT] kind=llm_extract key={cache_key[:8]}... "
                f"hits={cached.get('cache_hit_count', 0)}"
            )
            payload = cached.get("result", {}).get("payload")
            if payload is not None:
                return payload if isinstance(payload, list) else []

        # Cache miss - call LLM
        logger.info(f"{self._run_prefix()}[GRACE:block_llm_cache_lookup:MISS] kind=llm_extract key={cache_key[:8]}...")

        system_prompt: str = self._get_system_prompt(max_keywords, custom_prompt)
        truncated_text: str = text[:12000]

        try:
            result = self._execute_generation(
                provider, model, truncated_text, system_prompt
            )
            # Store successful result in cache
            self._cache_generation_result(
                kind="llm_extract",
                cache_key=cache_key,
                request_params=params,
                result=result,
                provider=provider,
            )
            return result
        except LLMNonRetriableCredentialError:
            fallback_result = self._execute_fallback_and_cache(
                provider,
                truncated_text,
                system_prompt,
                kind="llm_extract",
                cache_key=cache_key,
                request_params=params,
            )
            if fallback_result is not None:
                return fallback_result
            return []
        except Exception as e:
            logger.error(f"{self._run_prefix()}Primary provider {provider} failed: {e}")
            fallback_result = self._execute_fallback_and_cache(
                provider,
                truncated_text,
                system_prompt,
                kind="llm_extract",
                cache_key=cache_key,
                request_params=params,
            )
            return fallback_result if fallback_result is not None else []
    # FUNCTION_CONTRACT: _execute_generation
    # Purpose: Implement the  execute generation helper for this module.
    # Input: provider (str), model (str), text (str), system_prompt (str), parse_csv (bool = True)
    # Output: Any
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def _execute_generation(
        self,
        provider: str,
        model: str,
        text: str,
        system_prompt: str,
        parse_csv: bool = True,
    ) -> Any:
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
    # FUNCTION_CONTRACT: _execute_generation_once
    # Purpose: Implement the  execute generation once helper for this module.
    # Input: provider (str), model (str), text (str), system_prompt (str), parse_csv (bool = True)
    # Output: Any
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def _execute_generation_once(
        self,
        provider: str,
        model: str,
        text: str,
        system_prompt: str,
        parse_csv: bool = True,
    ) -> Any:
        provider = provider.lower()

        # Validate provider against known list
        KNOWN_PROVIDERS = {"anthropic", "google", "google gemini", "openai", "openrouter"}
        if provider not in KNOWN_PROVIDERS and not any(
            cp.get("name", "").lower() == provider for cp in CUSTOM_PROVIDERS
        ):
            raise LLMGenerationError(f"Unknown provider: {provider}")

        request_timeout: float = (
            float(max(self.timeout_seconds * 3, 60))
            if not parse_csv
            else float(self.timeout_seconds)
        )

        content: str = ""
        try:
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
        except Exception as exc:
            self._raise_if_non_retriable_credential_error(provider, exc)
            raise

        # Clean LLM response: strip <thinking> blocks and other artifacts
        content = self._clean_llm_response(content)

        if not parse_csv:
            return content

        # Parse CSV
        keywords: List[str] = [kw.strip() for kw in content.split(",")]
        return [kw for kw in keywords if kw]
    # FUNCTION_CONTRACT: generate_seo_text
    # Purpose: Implement the generate seo text helper for this module.
    # Input: text (str), keywords (List[Dict[str, Any]]), provider (str), model (str), language (str = 'Russian'), custom_prompt (str = ''), page_type (str = 'product')
    # Output: str
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function; uses cache lookup
    # Business Rules: Preserves the current validation and control flow for this call path; checks cache before LLM call
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001, PLAN 10-02 Task 6
    def generate_seo_text(
        self,
        text: str,
        keywords: List[Dict[str, Any]],
        provider: str,
        model: str,
        language: str = "Russian",
        custom_prompt: str = "",
        page_type: str = "product",
        force_refresh: bool = False,
    ) -> str:
        import hashlib

        # Build hashes for cache key
        text_hash = hashlib.sha256(text[:10000].encode()).hexdigest()[:16]

        # Hash keywords for stable key
        kw_list_str = "\n".join(
            [
                f"- {k['Keyword']} (Vol: {k.get('Avg Monthly Searches', 'N/A')})"
                for k in keywords[:20]
            ]
        )
        keywords_hash = hashlib.sha256(kw_list_str.encode()).hexdigest()[:16]

        # Hash prompt if present
        prompt_hash = ""
        if custom_prompt:
            prompt_hash = hashlib.sha256(custom_prompt.encode()).hexdigest()[:16]
        content_hash = hashlib.sha256(
            text[:10000].encode()
        ).hexdigest()[:16]

        params = {
            "text_hash": text_hash,
            "keywords_hash": keywords_hash,
            "provider": str(provider).lower(),
            "model": str(model).lower(),
            "language": str(language).lower(),
            "page_type": str(page_type).lower(),
            "prompt_hash": prompt_hash,
            "content_hash": content_hash,
        }

        cache_key = build_cache_key(
            kind="llm_generate",
            provider=params["provider"],
            params=params,
        )

        # Check cache
        cached = request_cache.get(cache_key, force_refresh=force_refresh)
        if cached is not None:
            logger.info(
                f"{self._run_prefix()}[GRACE:block_llm_cache_lookup:HIT] kind=llm_generate key={cache_key[:8]}... "
                f"hits={cached.get('cache_hit_count', 0)}"
            )
            payload = cached.get("result", {}).get("payload")
            if payload is not None:
                return payload if isinstance(payload, str) else ""

        # Cache miss - call LLM
        logger.info(f"{self._run_prefix()}[GRACE:block_llm_cache_lookup:MISS] kind=llm_generate key={cache_key[:8]}...")

        keyword_values = [
            (
                f"{keyword.get('Keyword', '')} "
                f"(Vol: {keyword.get('Avg Monthly Searches', 'N/A')})"
            ).strip()
            for keyword in keywords[:20]
            if str(keyword.get("Keyword", "")).strip()
        ]
        template = (
            custom_prompt.strip()
            if custom_prompt.strip()
            else SEO_DESCRIPTION_PROMPT.strip()
        )
        system_prompt = self.render_seo_prompt_with_content(
            template=template,
            language=language,
            keywords=keyword_values,
            content=text,
            page_type=page_type,
        )

        truncated_text: str = text[:15000]

        # Safety net: if user content is empty but keywords exist, build fallback prompt
        # Vertex AI (via Omniroute) rejects empty user messages with 400 INVALID_ARGUMENT
        if not truncated_text.strip() and keyword_values:
            truncated_text = "\n".join(
                f"- {kw}" for kw in keyword_values[:20]
            )
            logger.info(
                f"{self._run_prefix()}Empty text in generate_seo_text; "
                f"built fallback prompt from {min(len(keyword_values), 20)} keyword(s)"
            )

        try:
            result = self._execute_generation(
                provider, model, truncated_text, system_prompt, parse_csv=False
            )
            # Store successful result in cache
            self._cache_generation_result(
                kind="llm_generate",
                cache_key=cache_key,
                request_params=params,
                result=result,
                provider=provider,
            )
            return result
        except LLMNonRetriableCredentialError as exc:
            fallback_result = self._execute_fallback_and_cache(
                provider,
                truncated_text,
                system_prompt,
                kind="llm_generate",
                cache_key=cache_key,
                request_params=params,
                parse_csv=False,
            )
            if fallback_result is not None:
                return fallback_result
            raise LLMGenerationError(str(exc)) from exc
        except Exception as e:
            logger.error(f"{self._run_prefix()}SEO Text Generation failed: {e}")
            fallback_result = self._execute_fallback_and_cache(
                provider,
                truncated_text,
                system_prompt,
                kind="llm_generate",
                cache_key=cache_key,
                request_params=params,
                parse_csv=False,
            )
            if fallback_result is not None:
                return fallback_result
            else:
                raise LLMGenerationError(
                    f"SEO text generation failed for both primary and fallback providers: {e}"
                ) from e


# Note: _execute_generation delegates to tenacity retrier explicitly via
# retrier(LLMHandler._execute_generation_once, ...) — no __wrapped__ attribute needed.
