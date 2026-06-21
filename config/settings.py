import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent

# Load environment variables from project root .env
load_dotenv(BASE_DIR / ".env", override=True)
CONFIG_PATH = BASE_DIR / "config" / "settings.yaml"


# MODULE_CONTRACT: config/settings
# Purpose: Central configuration loader and derived constants for the application
# Rationale: Single source of truth for all runtime configuration; reads settings.yaml and .env once
# Dependencies: yaml, python-dotenv, config/settings.yaml
# Exports: load_config, save_config, config, RETRY_CONFIG, LLM_CONFIG, KEYWORDS_CONFIG, SCRAPING_CONFIG, CLEANUP_CONFIG, GOOGLE_ADS_CONFIG, SERP_CONFIG, SEO_MATH_CONFIG, CRAWLER_CONFIG, LOGGING_CONFIG, HISTORY_CONFIG, UPLOADS_CONFIG, UI_CONFIG, CACHE_CONFIG, GOOGLE_TRENDS_CONFIG, SCRAPER_CONFIG, RETRY_ATTEMPTS, RETRY_DELAY, FALLBACK_PROVIDER, FALLBACK_MODEL, LLM_MODELS, KEYWORD_EXTRACTION_PROMPT, SEO_DESCRIPTION_PROMPT, LLM_TIMEOUT, LLM_DELAY_BETWEEN_REQUESTS, CUSTOM_PROVIDERS, SERP_PROVIDER_OPTIONS, SERP_LOCATION_OPTIONS, SERP_LANGUAGE_OPTIONS, SERP_DEVICE_OPTIONS, SERP_SEARCH_TYPE_OPTIONS, SERP_TIME_PERIOD_OPTIONS, SERP_SAFE_SEARCH_OPTIONS, SERP_GOOGLE_DOMAIN_OPTIONS, get_available_serp_providers
# LINKS: requirements.xml#UC-001, knowledge-graph.xml#MOD-001, PLAN 08-02 Task 5, PLAN 10-02 Task 1
# MODULE_MAP: config/settings.py
# Public Functions: load_config, save_config
# Private Helpers: (none)
# Key Semantic Blocks: block_settings_load_yaml_parse, block_settings_derived_constants
# Critical Flows: every module reads derived constants; sidebar writes back via save_config
# Verification: V-SUITE
# CHANGE_SUMMARY: Added module-level contracts; added FUNCTION_CONTRACT blocks for load_config and save_config; removed post-declaration docstrings; added SERP UI constants (SERP_PROVIDER_OPTIONS, SERP_LOCATION_OPTIONS, SERP_LANGUAGE_OPTIONS) and get_available_serp_providers(); added Phase 6 advanced SERP option dicts (SERP_DEVICE_OPTIONS, SERP_SEARCH_TYPE_OPTIONS, SERP_SAFE_SEARCH_OPTIONS, SERP_GOOGLE_DOMAIN_OPTIONS); Phase 7 Cycle 3: removed HasData, added SearchApi.io, Zenserp, ScraperAPI, DataForSEO, Serpstat to SERP_PROVIDER_OPTIONS; _SERP_ENV_MAP updated with tuple env_var for DataForSEO dual auth; get_available_serp_providers now handles tuple env vars via _check_env_keys helper; Phase 8 Task 5: added SEO_MATH_CONFIG export; Phase 8 Plan 03: added top-level CRAWLER_CONFIG export; Phase 10 Task 1: added CACHE_CONFIG, GOOGLE_TRENDS_CONFIG, SCRAPER_CONFIG exports
# FUNCTION_CONTRACT: load_config
# Purpose: Parse settings.yaml into a nested dict, raising if the file is absent
# Input: (none)
# Output: dict — parsed YAML configuration
# Side Effects: reads filesystem
# Business Rules: raises FileNotFoundError if settings.yaml missing
# Failure Modes: FileNotFoundError, yaml.YAMLError on malformed YAML
# LINKS: requirements.xml#UC-001
def load_config():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Configuration file not found: {CONFIG_PATH}")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# FUNCTION_CONTRACT: save_config
# Purpose: Write configuration dict back to settings.yaml preserving structure and Unicode
# Input: config_data (dict) — full configuration tree
# Output: (none)
# Side Effects: writes to config/settings.yaml on disk
# Business Rules: uses safe_dump with allow_unicode and unsorted keys
# Failure Modes: IOError if filesystem unwritable
# LINKS: requirements.xml#UC-001
def save_config(config_data):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            config_data,
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )


# Load config once
try:
    config = load_config()
except FileNotFoundError:
    import sys
    print(f"ERROR: Configuration file not found at {CONFIG_PATH}", file=sys.stderr)
    config = {}

# Export sections
RETRY_CONFIG = config.get("retry", {})
LLM_CONFIG = config.get("llm", {})
KEYWORDS_CONFIG = config.get("keywords", {})
SCRAPING_CONFIG = config.get("scraping", {})
CLEANUP_CONFIG = config.get("cleanup", {})
GOOGLE_ADS_CONFIG = config.get("google_ads", {})
SERP_CONFIG = config.get("serp", {})
SEO_MATH_CONFIG = config.get("seo_math", {})
CRAWLER_CONFIG = config.get("crawler", {})
LOGGING_CONFIG = config.get("logging", {})
HISTORY_CONFIG = config.get("history", {})
UPLOADS_CONFIG = config.get("uploads", {})
UI_CONFIG = config.get("ui", {})
# Phase 10 new sections
CACHE_CONFIG = config.get("cache", {})
GOOGLE_TRENDS_CONFIG = config.get("google_trends", {})
SCRAPER_CONFIG = config.get("scraper", {"browser_enabled": False})

# Derived constants for easy access
RETRY_ATTEMPTS = RETRY_CONFIG.get("max_attempts", 4)
RETRY_DELAY = RETRY_CONFIG.get("delay_seconds", 4)
FALLBACK_PROVIDER = LLM_CONFIG.get("fallback_provider", "openrouter")
FALLBACK_MODEL = LLM_CONFIG.get("fallback_model", "meta-llama/llama-3.1-70b-instruct")
LLM_MODELS = LLM_CONFIG.get("models", {})

# Prompt templates
PROMPTS_CONFIG = LLM_CONFIG.get("prompts", {})
KEYWORD_EXTRACTION_PROMPT = PROMPTS_CONFIG.get("keyword_extraction", "")
SEO_DESCRIPTION_PROMPT = PROMPTS_CONFIG.get("seo_description", "")

# API parameters
LLM_TIMEOUT = LLM_CONFIG.get("timeout_seconds", 10)
LLM_DELAY_BETWEEN_REQUESTS = LLM_CONFIG.get("delay_between_requests_seconds", 2)

# Custom providers (from settings.yaml llm.custom_providers)
CUSTOM_PROVIDERS = LLM_CONFIG.get("custom_providers", [])

# --- SERP UI Constants ---
SERP_PROVIDER_OPTIONS: dict[str, str] = {
    "Serper.dev": "serper_dev",
    "SerpApi": "serpapi",
    "Brave Search": "brave_search",
    "SearchApi.io": "searchapi_io",
    "Zenserp": "zenserp",
    "ScraperAPI": "scraperapi",
    "DataForSEO": "dataforseo",
    "Serpstat": "serpstat",
    "Serpstack": "serpstack",
    "ScaleSERP": "scaleserp",
    "ValueSERP": "valueserp",
    "Browser (Cloakbrowser/Playwright)": "browser_cloakbrowser",
}

SERP_LOCATION_OPTIONS: dict[str, str] = {
    "Ukraine": "ua",
    "USA": "us",
    "Russia": "ru",
    "Germany": "de",
    "UK": "uk",
    "Poland": "pl",
}

SERP_LANGUAGE_OPTIONS: dict[str, str] = {
    "Ukrainian": "uk",
    "Russian": "ru",
    "English": "en",
    "German": "de",
    "Polish": "pl",
}

SERP_DEVICE_OPTIONS: dict[str, str] = {
    "Not set": "",
    "Desktop": "desktop",
    "Mobile": "mobile",
    "Tablet": "tablet",
}

SERP_SEARCH_TYPE_OPTIONS: dict[str, str] = {
    "Web": "web",
    "Images": "images",
    "Videos": "videos",
    "News": "news",
    "Shopping": "shopping",
}

SERP_TIME_PERIOD_OPTIONS: dict[str, str] = {
    "Any time": "any",
    "Past hour": "hour",
    "Past day": "day",
    "Past week": "week",
    "Past month": "month",
    "Past year": "year",
}

SERP_SAFE_SEARCH_OPTIONS: dict[str, str] = {
    "Off": "off",
    "Active": "active",
}

SERP_GOOGLE_DOMAIN_OPTIONS: dict[str, str] = {
    "google.com": "google.com",
    "google.co.uk": "google.co.uk",
    "google.de": "google.de",
    "google.fr": "google.fr",
    "google.com.ua": "google.com.ua",
    "google.ru": "google.ru",
    "google.com.tr": "google.com.tr",
    "google.pl": "google.pl",
}

_SERP_ENV_MAP: dict[str, str | tuple[str, ...]] = {
    "serper_dev": "SERPER_API_KEY",
    "serpapi": "SERPAPI_KEY",
    "brave_search": "BRAVE_SEARCH_API_KEY",
    "searchapi_io": "SEARCHAPI_IO_KEY",
    "zenserp": "ZENSERP_KEY",
    "scraperapi": "SCRAPERAPI_KEY",
    "dataforseo": ("DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD"),
    "serpstat": "SERPSTAT_TOKEN",
    "serpstack": "SERPSTACK_KEY",
    "scaleserp": "SCALESERP_KEY",
    "valueserp": "VALUESERP_KEY",
    "browser_cloakbrowser": "",
}

# FUNCTION_CONTRACT: _check_env_keys
# Purpose: Check if all required environment variables are set for a provider
# Input: env_var (str | tuple[str, ...]) — single env var name or tuple of multiple
# Output: bool — True if all env vars have non-empty values
# Side Effects: reads os.environ
# Business Rules: For tuple env_var, all values must be present; for single env_var, checks non-empty
# Failure Modes: never raises
# LINKS: requirements.xml#UC-006
def _check_env_keys(env_var: str | tuple[str, ...]) -> bool:
    if isinstance(env_var, tuple):
        return all(os.environ.get(v, "") for v in env_var)
    return bool(os.environ.get(env_var, ""))

# FUNCTION_CONTRACT: get_available_serp_providers
# Purpose: Return subset of SERP_PROVIDER_OPTIONS where the corresponding env var API key is set
# Input: (none)
# Output: dict[str, str] — display name to internal key mapping for providers with keys configured
# Side Effects: reads os.environ
# Business Rules: Only includes providers whose env var from _SERP_ENV_MAP has a non-empty value; tuple env_vars require all values present
# Failure Modes: returns empty dict when no keys are set
# LINKS: requirements.xml#UC-006, knowledge-graph.xml#MOD-001
def get_available_serp_providers() -> dict[str, str]:
    available: dict[str, str] = {}
    for display, internal in SERP_PROVIDER_OPTIONS.items():
        if internal == "browser_cloakbrowser":
            if SCRAPER_CONFIG.get("browser_enabled", False):
                available[display] = internal
            continue
        if _check_env_keys(_SERP_ENV_MAP.get(internal, "")):
            available[display] = internal
    return available
