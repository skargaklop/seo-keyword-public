import yaml
import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).parent.parent

# Load environment variables from project root .env
load_dotenv(BASE_DIR / ".env")
CONFIG_PATH = BASE_DIR / "config" / "settings.yaml"


def load_config():
    """Load configuration from YAML file."""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Configuration file not found: {CONFIG_PATH}")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_config(config_data):
    """Save configuration to YAML file."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            config_data,
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )


# Load config once
config = load_config()

# Export sections
RETRY_CONFIG = config.get("retry", {})
LLM_CONFIG = config.get("llm", {})
KEYWORDS_CONFIG = config.get("keywords", {})
SCRAPING_CONFIG = config.get("scraping", {})
CLEANUP_CONFIG = config.get("cleanup", {})
GOOGLE_ADS_CONFIG = config.get("google_ads", {})
LOGGING_CONFIG = config.get("logging", {})
HISTORY_CONFIG = config.get("history", {})
UPLOADS_CONFIG = config.get("uploads", {})
UI_CONFIG = config.get("ui", {})

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
