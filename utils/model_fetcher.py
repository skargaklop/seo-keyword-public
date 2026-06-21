"""
Model fetcher utility — single source of truth for provider base URLs,
model cache I/O, dynamic model fetching from provider APIs, and custom
provider validation.
"""

import ipaddress
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

# SDK Imports with safe fallbacks if not installed
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    from google import genai
except ImportError:
    genai = None

from utils.logger import logger

BASE_DIR = Path(__file__).parent.parent

# MODULE_CONTRACT: model_fetcher
# Purpose: Single source of truth for provider base URLs, model cache I/O, dynamic model fetching from provider /models endpoints, and custom provider validation
# Rationale: Eliminates hardcoded model lists from sidebar and config; enables dynamic model discovery with persistent cache; centralizes provider URL management so llm_handler imports from here
# Dependencies: openai SDK (optional), google-genai SDK (optional), utils.logger, json, os, re, datetime, pathlib
# Exports: PROVIDER_BASE_URLS, ANTHROPIC_MODELS, GOOGLE_MODELS, MODELS_CACHE_PATH, load_models_cache, save_models_cache, fetch_provider_models, fetch_all_models, get_cached_models, validate_custom_provider
# LINKS: requirements.xml#UC-001, PLAN-04-01 Task 1
# MODULE_MAP: utils/model_fetcher.py
# Public Functions: load_models_cache, save_models_cache, fetch_provider_models, fetch_all_models, get_cached_models, validate_custom_provider
# Private Helpers: (none)
# Key Semantic Blocks: block_model_fetcher_constants, block_fetcher_cache_io, block_fetcher_provider_fetch, block_model_fetcher_validation
# Critical Flows: fetch_all_models -> fetch_provider_models per provider -> save cache -> get_cached_models reads cache
# Verification: tests/test_dynamic_models.py
# CHANGE_SUMMARY: Initial creation — new module

# ---------------------------------------------------------------------------
# block_model_fetcher_constants
# ---------------------------------------------------------------------------

PROVIDER_BASE_URLS: dict[str, str] = {
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

ANTHROPIC_MODELS: list[str] = [
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
    "claude-opus-4-8",
]

GOOGLE_MODELS: list[str] = [
    "gemini-3-flash-preview",
    "gemini-3-pro-preview",
]

MODELS_CACHE_PATH: Path = BASE_DIR / "config" / "models_cache.json"

# ---------------------------------------------------------------------------
# block_fetcher_cache_io
# ---------------------------------------------------------------------------


# FUNCTION_CONTRACT: load_models_cache
# Purpose: Read the persistent model cache from config/models_cache.json
# Input: (none)
# Output: dict — parsed cache contents; empty dict on missing or corrupt file
# Side Effects: reads filesystem
# Business Rules: returns {} silently on any read/parse failure
# Failure Modes: FileNotFoundError, json.JSONDecodeError — both caught and logged
# LINKS: PLAN-04-01 Task 1
def load_models_cache() -> dict:
    try:
        if not MODELS_CACHE_PATH.exists():
            return {}
        with open(MODELS_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(f"Failed to load models cache: {exc}")
        return {}


# FUNCTION_CONTRACT: save_models_cache
# Purpose: Write the model cache dict to config/models_cache.json with indented JSON
# Input: cache (dict) — full cache dictionary to persist
# Output: (none)
# Side Effects: writes to config/models_cache.json on disk
# Business Rules: wraps write in try/except to log and return on failure (robustness for concurrent write race)
# Failure Modes: OSError if filesystem unwritable — caught and logged
# LINKS: PLAN-04-01 Task 1
def save_models_cache(cache: dict) -> None:
    try:
        with open(MODELS_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except OSError as exc:
        logger.warning(f"Failed to save models cache: {exc}")


# ---------------------------------------------------------------------------
# block_fetcher_provider_fetch
# ---------------------------------------------------------------------------


# FUNCTION_CONTRACT: fetch_provider_models
# Purpose: Fetch the list of available model IDs from a single LLM provider
# Input: provider (str) — provider name (e.g. "openai", "anthropic", "google"), api_key (str), base_url (str | None) — override URL
# Output: list[str] — sorted list of model ID strings; empty list on any failure
# Side Effects: makes network API call for OpenAI-compatible and Google providers
# Business Rules: Anthropic returns ANTHROPIC_MODELS constant (no /models endpoint); Google strips "models/" prefix from genai response; all others use OpenAI-compatible /models endpoint
# Failure Modes: network error, auth error, SDK not installed — all caught, returns []
# LINKS: PLAN-04-01 Task 1
def fetch_provider_models(
    provider: str, api_key: str, base_url: Optional[str] = None
) -> list[str]:
    provider_lower = provider.lower()

    # Anthropic has no public /models endpoint
    if provider_lower == "anthropic":
        return list(ANTHROPIC_MODELS)

    # Google GenAI — strip "models/" prefix
    if provider_lower in ("google", "google gemini", "gemini"):
        if genai is None:
            return list(GOOGLE_MODELS)
        try:
            client = genai.Client(api_key=api_key)
            models_list = client.models.list()
            result = [
                m.name.replace("models/", "")
                for m in models_list
                if hasattr(m, "name")
            ]
            return sorted(result) if result else list(GOOGLE_MODELS)
        except Exception as exc:
            logger.warning(f"Google GenAI model fetch failed: {exc}")
            return list(GOOGLE_MODELS)

    # OpenAI-compatible providers
    if OpenAI is None:
        return []

    effective_base_url = base_url
    if not effective_base_url and provider_lower in PROVIDER_BASE_URLS:
        effective_base_url = PROVIDER_BASE_URLS[provider_lower]

    try:
        client = OpenAI(api_key=api_key, base_url=effective_base_url)
        response = client.models.list()
        models = [m.id for m in response.data]
        return sorted(models)
    except Exception as exc:
        logger.warning(f"Model fetch failed for {provider}: {exc}")
        return None  # None signals API error; [] means success but empty


# FUNCTION_CONTRACT: fetch_all_models
# Purpose: Iterate all configured providers and custom providers, fetch model lists, build full cache dict
# Input: provider_keys (dict[str, str]) — name->env_var mapping, custom_providers (list[dict] | None) — custom provider configs
# Output: dict — full cache with "providers" sub-dict and "last_fetched" ISO timestamp
# Side Effects: makes network API calls; reads environment variables
# Business Rules: skips providers with no API key (status "no_key"); records errors per-provider; sets last_fetched timestamp
# Failure Modes: individual provider failures recorded in cache, do not halt iteration
# LINKS: PLAN-04-01 Task 1
def fetch_all_models(
    provider_keys: dict[str, str],
    custom_providers: Optional[list[dict]] = None,
) -> dict:
    cache: dict = {"providers": {}}

    # Built-in providers
    for name, env_var in provider_keys.items():
        api_key = os.getenv(env_var)
        if not api_key:
            cache["providers"][name.lower()] = {
                "models": [],
                "status": "no_key",
                "error": None,
            }
            continue

        models = fetch_provider_models(name.lower(), api_key)
        if models is None:
            # API error
            cache["providers"][name.lower()] = {
                "models": [],
                "status": "error",
                "error": "API request failed",
            }
        else:
            # Success (possibly empty model list)
            cache["providers"][name.lower()] = {
                "models": models,
                "status": "success",
                "error": None,
            }

    # Custom providers
    if custom_providers:
        for cp in custom_providers:
            cp_name = cp.get("name", "").lower()
            cp_base_url = cp.get("base_url", "")
            cp_key_env = cp.get("api_key_env", "")
            cp_api_key = os.getenv(cp_key_env) if cp_key_env else None

            if not cp_api_key:
                cache["providers"][cp_name] = {
                    "models": [],
                    "status": "no_key",
                    "error": None,
                }
                continue

            models = fetch_provider_models(
                cp_name, cp_api_key, base_url=cp_base_url
            )
            if models is None:
                # API error
                cache["providers"][cp_name] = {
                    "models": [],
                    "status": "error",
                    "error": "API request failed",
                }
            else:
                # Success (possibly empty model list)
                cache["providers"][cp_name] = {
                    "models": models,
                    "status": "success",
                    "error": None,
                }

    cache["last_fetched"] = datetime.now(timezone.utc).isoformat()
    return cache


# FUNCTION_CONTRACT: get_cached_models
# Purpose: Retrieve the cached model list for a single provider from the persistent cache file
# Input: provider (str) — provider name (case-insensitive)
# Output: list[str] — list of model ID strings; empty list if provider not in cache
# Side Effects: reads filesystem via load_models_cache()
# Business Rules: navigates cache["providers"][provider]["models"] with safe .get() chain
# Failure Modes: cache file missing/corrupt — returns []
# LINKS: PLAN-04-01 Task 1
def get_cached_models(provider: str) -> list[str]:
    cache = load_models_cache()
    return (
        cache.get("providers", {})
        .get(provider.lower(), {})
        .get("models", [])
    )


# ---------------------------------------------------------------------------
# block_model_fetcher_validation
# ---------------------------------------------------------------------------


# FUNCTION_CONTRACT: validate_custom_provider
# Purpose: Validate custom provider input fields (name, base_url, api_key_env) against required patterns
# Input: name (str), base_url (str), api_key_env (str)
# Output: tuple[bool, str] — (True, "") if valid; (False, "reason") if invalid
# Side Effects: (none)
# Business Rules: name must match ^[a-zA-Z][a-zA-Z0-9_\-. ]{1,49}$; base_url must start with http:// or https://; api_key_env must match ^[A-Z_][A-Z0-9_]*$
# Failure Modes: returns (False, reason) — never raises
# LINKS: PLAN-04-01 Task 1
def validate_custom_provider(
    name: str, base_url: str, api_key_env: str
) -> tuple[bool, str]:
    name_stripped = name.strip()
    if not name_stripped:
        return False, "Name must not be empty."

    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_\-.]{1,49}$", name_stripped):
        return False, (
            "Name must start with a letter, be 2-50 characters, "
            "and contain only letters, digits, underscores, hyphens, and dots."
        )

    if not base_url.startswith("http://") and not base_url.startswith("https://"):
        return False, "Base URL must start with http:// or https://."

    # SSRF protection: reject localhost, private IPs, link-local, and metadata endpoints
    # Bypass with ALLOW_LOCALHOST_PROVIDERS env var for local dev (Ollama, LM Studio, etc.)
    parsed = urlparse(base_url)
    hostname = parsed.hostname
    allow_localhost = os.environ.get("ALLOW_LOCALHOST_PROVIDERS", "").lower() in ("1", "true", "yes")
    if not allow_localhost:
        if hostname in ("localhost", "127.0.0.1", "::1") or (
            hostname and hostname.startswith("169.254.")
        ):
            return False, "Base URL must not point to localhost or internal addresses."
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False, "Base URL must not point to private or internal addresses."
        except ValueError:
            pass  # hostname is a domain name, not an IP

    if not re.match(r"^[A-Z_][A-Z0-9_]*$", api_key_env):
        return False, (
            "API key environment variable name must start with a letter or underscore "
            "and contain only uppercase letters, digits, and underscores."
        )

    return True, ""
