# MODULE_CONTRACT: utils/validator
# Purpose: URL validator module — validates URL format and structure.
# Rationale: Keep the module boundary explicit for GRACE adoption and review.
# Dependencies: os, typing, pydantic, utils.logger, utils.url_safety
# Exports: ValidationResult, URLValidator, validate_api_keys
# LINKS: requirements.xml#UC-001, development-plan.xml#MOD-001
# MODULE_MAP: utils/validator.py
# Public Functions: exported callables and classes defined in this module
# Private Helpers: internal helpers and private methods defined in this module
# Key Semantic Blocks: main workflow paths and state transitions in this module
# Critical Flows: preserve existing runtime behavior and integrations
# Verification: python -m py_compile, python -m ruff check ., python -m pytest -q
# CHANGE_SUMMARY: Added file-local module metadata and declaration contracts; PLAN 15-01 URL-15-01: normalize bare domains to https:// in validate_url; Bug fix: validate_urls now returns the NORMALIZED url (validate_url had prepended https:// to bare domains, but validate_urls appended the raw input), which caused "Unsupported URL scheme: missing" downstream in the scraper's validate_safe_url_with_ips for scheme-less inputs.

import os
import re
from typing import List, Tuple, Optional, Dict

from pydantic import BaseModel

from utils.logger import logger
from utils.url_safety import URLSafetyError, validate_safe_url

# CLASS_CONTRACT: ValidationResult
# Purpose: Represent a URL validation decision with optional failure details.
# LINKS: requirements.xml#UC-001
class ValidationResult(BaseModel):
    url: str
    is_valid: bool
    error: Optional[str] = None

# CLASS_CONTRACT: URLValidator
# Purpose: Validate URL syntax, schemes, safety constraints, and duplicate inputs.
# LINKS: requirements.xml#UC-001
class URLValidator:
    # FUNCTION_CONTRACT: validate_url
    # Purpose: Implement the validate url helper for this module.
    # Input: url (str)
    # Output: ValidationResult
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    def validate_url(url: str) -> ValidationResult:
        if not url:
            return ValidationResult(url=url, is_valid=False, error="Empty URL")

        url = url.strip()

        # PLAN 15-01 URL-15-01: Normalize bare domains to https://
        if not url.startswith(("http://", "https://")):
            # Check if it looks like a bare domain (contains a dot, no spaces)
            if re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}(/.*)?$', url):
                url = f"https://{url}"
            else:
                return ValidationResult(
                    url=url, is_valid=False, error="URL must start with http:// or https://"
                )

        try:
            validate_safe_url(url, resolve_dns=False)
            return ValidationResult(url=url, is_valid=True)
        except URLSafetyError as exc:
            return ValidationResult(url=url, is_valid=False, error=str(exc))
        except Exception as exc:
            return ValidationResult(url=url, is_valid=False, error=str(exc))
    # FUNCTION_CONTRACT: validate_urls
    # Purpose: Implement the validate urls helper for this module.
    # Input: urls (List[str])
    # Output: Tuple[List[str], List[ValidationResult]]
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    def validate_urls(urls: List[str]) -> Tuple[List[str], List[ValidationResult]]:
        valid_urls: List[str] = []
        invalid_results: List[ValidationResult] = []

        seen: set = set()

        for url in urls:
            url = url.strip()
            if not url or url in seen:
                continue

            seen.add(url)
            result: ValidationResult = URLValidator.validate_url(url)
            if result.is_valid:
                # Append the NORMALIZED url (validate_url prepends https:// to bare
                # domains). Appending the raw input here caused "Unsupported URL scheme:
                # missing" downstream in the scraper's validate_safe_url_with_ips.
                valid_urls.append(result.url)
            else:
                invalid_results.append(result)
                logger.warning(f"Invalid URL: {url} - {result.error}")

        return valid_urls, invalid_results
# FUNCTION_CONTRACT: validate_api_keys
# Purpose: Implement the validate api keys helper for this module.
# Input: (none)
# Output: Dict[str, bool]
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def validate_api_keys() -> Dict[str, bool]:
    provider_keys: Dict[str, str] = {
        "OpenAI": "OPENAI_API_KEY",
        "Anthropic": "ANTHROPIC_API_KEY",
        "Google (Gemini)": "GEMINI_API_KEY",
        "xAI (Grok)": "XAI_API_KEY",
        "Groq": "GROQ_API_KEY",
        "DeepSeek": "DEEPSEEK_API_KEY",
        "MiniMax": "MINIMAX_API_KEY",
        "Moonshot": "MOONSHOT_API_KEY",
        "OpenRouter": "OPENROUTER_API_KEY",
        "Cerebras": "CEREBRAS_API_KEY",
        "ZAI": "ZAI_API_KEY",
    }

    results: Dict[str, bool] = {}
    for name, env_var in provider_keys.items():
        key: Optional[str] = os.getenv(env_var)
        is_present: bool = bool(key and key.strip())
        results[name] = is_present
        if is_present:
            logger.info(f"API key found for {name}")
        else:
            logger.warning(f"API key missing for {name} ({env_var})")

    return results
