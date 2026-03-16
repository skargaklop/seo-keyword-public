"""
URL validator module — validates URL format and structure.
Unused check_accessibility() removed (improvement #2).
Type hints added (improvement #5).
"""

import os
from typing import List, Tuple, Optional, Dict

from pydantic import BaseModel

from utils.logger import logger
from utils.url_safety import URLSafetyError, validate_safe_url


class ValidationResult(BaseModel):
    url: str
    is_valid: bool
    error: Optional[str] = None


class URLValidator:
    @staticmethod
    def validate_url(url: str) -> ValidationResult:
        """Validate URL format and schema."""
        if not url:
            return ValidationResult(url=url, is_valid=False, error="Empty URL")

        url = url.strip()
        if not url.startswith(("http://", "https://")):
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

    @staticmethod
    def validate_urls(urls: List[str]) -> Tuple[List[str], List[ValidationResult]]:
        """
        Validate a list of URLs.
        Returns: (valid_urls, invalid_results)
        """
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
                valid_urls.append(url)
            else:
                invalid_results.append(result)
                logger.warning(f"Invalid URL: {url} - {result.error}")

        return valid_urls, invalid_results


def validate_api_keys() -> Dict[str, bool]:
    """
    Validate presence of API keys at startup (improvement #14).

    Returns:
        Dict mapping provider name to whether its key is present.
    """
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
