"""
Browser-based scraping module for Google Trends and SERP (OPT-IN fallback).

This module provides browser automation capabilities as an optional fallback
when API-based methods fail or are unavailable. Browser scraping is disabled
by default and requires manual installation of optional dependencies:

    python -m pip install --upgrade cloakbrowser trafilatura

The module uses cloakbrowser for stealth browser automation and trafilatura for HTML content extraction.
"""

import csv
import hashlib
import importlib
import importlib.util
import io
import json
import os
import random
import re
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

try:  # Optional parser dependency: do not make the app fail at import time.
    import trafilatura
except Exception:  # pragma: no cover - optional dependency guard
    trafilatura = None  # type: ignore[assignment]

try:  # Optional playwright dependency — TargetClosedError for graceful error handling
    from playwright._impl._errors import TargetClosedError
except Exception:  # pragma: no cover - optional dependency guard
    class TargetClosedError(Exception):  # type: ignore[assignment]
        """Fallback sentinel — never raised when playwright is absent."""

from config.settings import load_config
from utils.logger import logger


# MODULE_CONTRACT: utils/browser_scraper
# Purpose: OPT-IN browser-based scraping for Google SERP and Trends with GRACE compliance
# Rationale: Provides resilient browser automation with CSS-class-agnostic parsing and trafilatura fallback
# Dependencies: typing, dataclasses, enum, json, time, asyncio, trafilatura, cloakbrowser, config.settings, utils.logger
# Exports: DependencyStatus, BrowserEngine, ParserType, BrowserScraperConfig, BrowserScrapeResult, BrowserScraper, create_browser_scraper
# LINKS: requirements.xml#UC-010, .planning/phases/12-browser-google-parsing-prompt-cleanup/12-01-PLAN.md#task-12-02
# MODULE_MAP: utils/browser_scraper.py
# Public Functions: BrowserScraper.check_dependencies, BrowserScraper.is_available, BrowserScraper.dependency_install_message, BrowserScraper.scrape_google_trends, BrowserScraper.scrape_serp, create_browser_scraper, build_optional_dependency_install_command, get_problem_dependencies, get_dependency_install_message, get_no_browser_engine_error
# Private Helpers: _check_dependency, _check_playwright_binary, _build_cache_key, _parse_with_trafilatura, _execute_cloakbrowser_trends, _execute_cloakbrowser_serp, _wait_for_dynamic_content, _detect_captcha, _load_js_parser, _handle_cookie_consent, _click_next_page, _extract_serp_data, _extract_with_trafilatura, _apply_rate_limit, _detect_trends_block, _parse_trends_csv, _validate_trends_keyword, _extract_trends_widget_data, _load_session_state, _save_session_state
# Key Semantic Blocks: block_browser_dependency_check, block_browser_trends_csv_download, block_browser_serp_parsing, block_browser_handle_pagination, block_browser_cookie_handling, block_browser_paa_extraction, block_browser_rich_snippets
# Critical Flows: Dependency check → engine selection → stealth config → cookie handling → pagination → SERP/Trends extraction → trafilatura fallback → result normalization
# Verification: verification-plan.xml#V-10-BROWSER-SCRAPER, Phase 11 Task 11-14 validation tests, Phase 12 grep guards
# CHANGE_SUMMARY: Wave 1 (Phase 10 Task 10): Initial implementation. Wave 2 (Phase 11 Task 11-14): Integrated working parse_google_bigbox.py logic with GRACE compliance, CSS-class-agnostic SERP parser, pagination, PAA extraction, proper stealth configuration, and trafilatura integration. Wave 3 (Phase 12): Added PLAYWRIGHT and AUTO to BrowserEngine enum, playwright binary detection, browser-based SERP provider (browser_cloakbrowser), and removed suffix_stripping option. Wave 4 (Phase 16 Task 2): Replaced DOM/JS extraction with CSV-download-based extraction, added module-level helpers (_detect_trends_block, _parse_trends_csv, _validate_trends_keyword, _load_session_state, _save_session_state), added BrowserScraper instance methods for CSV download flow, updated GRACE log markers from _trends_parsing to _trends_csv.


# CLASS_CONTRACT: DependencyStatus
# Purpose: Represent installation status of optional browser dependencies
# LINKS: requirements.xml#UC-010
class DependencyStatus(Enum):
    AVAILABLE = "available"
    MISSING = "missing"
    UNKNOWN = "unknown"
    UNUSABLE = "unusable"


# CLASS_CONTRACT: BrowserEngine
# Purpose: Supported browser automation engines
# LINKS: requirements.xml#UC-010
class BrowserEngine(Enum):
    CLOAKBROWSER = "cloakbrowser"
    PLAYWRIGHT = "playwright"
    AUTO = "auto"


# CLASS_CONTRACT: ParserType
# Purpose: Supported HTML parsers
# LINKS: requirements.xml#UC-010
class ParserType(Enum):
    TRAFILATURA = "trafilatura"


# CLASS_CONTRACT: BrowserScraperConfig
# Purpose: Configuration for browser scraping operations
# LINKS: requirements.xml#UC-010
@dataclass
# Purpose: Configuration for browser scraping operations.
class BrowserScraperConfig:
    engine: Literal["cloakbrowser", "playwright", "auto"] = "cloakbrowser"
    parser: Literal["trafilatura"] = "trafilatura"
    headless: bool = True
    timeout_seconds: int = 30
    user_agent: str = ""
    proxy: Optional[str] = None
    viewport: Dict[str, int] = field(default_factory=lambda: {"width": 1920, "height": 1080})
    retry_on_failure: int = 3
    rate_limit_delay: float = 3.0

    @classmethod
    # Purpose: Create config from settings dict or load from defaults.
    def from_settings(cls, settings: Optional[Dict[str, Any]] = None) -> "BrowserScraperConfig":
        if settings is None:
            settings = load_config().get("scraper", {})

        return cls(
            engine=settings.get("engine", "cloakbrowser"),
            parser=settings.get("parser", "trafilatura"),
            headless=settings.get("headless", True),
            timeout_seconds=settings.get("timeout_seconds", 30),
            user_agent=settings.get("user_agent", ""),
            proxy=settings.get("proxy"),
            viewport=settings.get("viewport", {"width": 1920, "height": 1080}),
            retry_on_failure=settings.get("retry_on_failure", 3),
            rate_limit_delay=settings.get("rate_limit_delay", 3.0),
        )


# CLASS_CONTRACT: BrowserScrapeResult
# Purpose: Result from browser scraping with source metadata
# LINKS: requirements.xml#UC-010
@dataclass
# Purpose: Result from browser scraping operations.
class BrowserScrapeResult:
    source: Literal["api", "cloakbrowser", "trafilatura", "none"]
    raw_html: Optional[str] = None
    parsed_content: Dict[str, Any] = field(default_factory=dict)
    extracted_data: Optional[Any] = None  # Will be GoogleTrendsResult or SERPSearchResult
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    cache_key: str = ""
    success: bool = True


# FUNCTION_CONTRACT: _check_dependency
# Purpose: Check if a Python package is installed and exposes the expected API
# Input: package_name (str), required_attrs (tuple[str, ...])
# Output: DependencyStatus
# Side Effects: none
# Business Rules: Uses importlib.util to check package availability; imports packages when API validation is required
# Failure Modes: Returns UNKNOWN on unexpected check errors and UNUSABLE when installed packages miss required APIs
# LINKS: requirements.xml#UC-010
def _check_dependency(package_name: str, required_attrs: tuple[str, ...] = ()) -> DependencyStatus:
    try:
        spec = importlib.util.find_spec(package_name)
        if spec is None:
            return DependencyStatus.MISSING
        if not required_attrs:
            return DependencyStatus.AVAILABLE
        module = importlib.import_module(package_name)
        if all(hasattr(module, attr) for attr in required_attrs):
            return DependencyStatus.AVAILABLE
        logger.warning(
            f"Dependency '{package_name}' is installed but missing required API: "
            f"{', '.join(required_attrs)}"
        )
        return DependencyStatus.UNUSABLE
    except ImportError:
        return DependencyStatus.UNUSABLE
    except Exception:
        return DependencyStatus.UNKNOWN


BROWSER_DEPENDENCY_APIS: Dict[str, tuple[str, ...]] = {
    "cloakbrowser": ("launch",),
    # Playwright uses nested modules (sync_api, sync_playwright)
    # We check package availability only; binary checked separately
    "playwright": (),
    "trafilatura": ("extract", "extract_metadata"),
}

OPTIONAL_BROWSER_PACKAGES: tuple[str, ...] = tuple(BROWSER_DEPENDENCY_APIS)


# Purpose: Build an install/upgrade command for optional browser scraping tools.
def build_optional_dependency_install_command(scope: str = "project") -> str:
    packages = " ".join(OPTIONAL_BROWSER_PACKAGES)
    if scope == "global":
        return f"python -m pip install --user --upgrade {packages}"
    return f"python -m pip install --upgrade {packages}"


# Purpose: get problem dependencies implementation
def get_problem_dependencies(
    dependencies: Optional[Dict[str, DependencyStatus]] = None,
) -> Dict[str, DependencyStatus]:
    """Return optional dependencies that are missing, unknown, or unusable."""
    deps = dependencies or BrowserScraper.check_dependencies()
    return {
        name: status
        for name, status in deps.items()
        if status != DependencyStatus.AVAILABLE
    }


# Purpose: Return a concise dependency install/upgrade hint for logs and failures.
def get_dependency_install_message() -> str:
    base_install = "python -m pip install " + " ".join(OPTIONAL_BROWSER_PACKAGES)
    return (
        f"Install optional browser tools with `{base_install}`. "
        "Install or upgrade them in the project environment with "
        f"`{build_optional_dependency_install_command('project')}` or globally with "
        f"`{build_optional_dependency_install_command('global')}`."
    )


# Purpose: Return the standard browser engine availability error.
def get_no_browser_engine_error() -> str:
    return f"No browser engine available or no parser usable. {get_dependency_install_message()}"


# FUNCTION_CONTRACT: _check_playwright_binary
# Purpose: Verify Playwright Chromium binary is installed for browser automation
# Input: (none)
# Output: bool — True if Chromium binary available, False otherwise
# Business Rules: Uses subprocess with sys.executable for Python resolution; checks known binary locations
# Failure Modes: Returns False on subprocess errors or missing binaries
# LINKS: .planning/phases/12-browser-google-parsing-prompt-cleanup/12-01-PLAN.md#task-12-02
def _check_playwright_binary() -> bool:
    import subprocess
    import sys
    from pathlib import Path

    # Check known binary locations first (faster than subprocess)
    # Windows: %USERPROFILE%\AppData\Local\ms-playwright\
    # Linux/Mac: ~/.cache/ms-playwright/
    home = Path.home()
    possible_locations = [
        home / "AppData" / "Local" / "ms-playwright",  # Windows
        home / ".cache" / "ms-playwright",  # Linux/Mac
    ]

    for location in possible_locations:
        if location.exists() and any(location.iterdir()):
            logger.info(f"Playwright binary found at {location}")
            return True

    # Fallback: try playwright CLI detection (may fail on some systems)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "--dry-run", "chromium"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # If command succeeds, binary is available or can be installed
        if result.returncode == 0:
            logger.info("Playwright CLI reports binary available")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as e:
        logger.info(f"Playwright CLI check failed: {e}")

    return False


# FUNCTION_CONTRACT: _ensure_windows_playwright_event_loop_policy
# Purpose: Configure Windows asyncio policy so Playwright can spawn its driver subprocess.
# Input: (none)
# Output: None
# Side Effects: Sets asyncio event-loop policy on Windows when Proactor policy is available.
# Business Rules: Playwright sync API requires subprocess support; Selector policy raises NotImplementedError on Windows.
# Failure Modes: Logs and continues when policy adjustment is unavailable.
# LINKS: .planning/phases/12-browser-google-parsing-prompt-cleanup/12-01-PLAN.md#task-12-02
def _ensure_windows_playwright_event_loop_policy() -> None:
    if os.name != "nt":
        return
    try:
        import asyncio

        policy_factory = getattr(asyncio, "WindowsProactorEventLoopPolicy", None)
        if policy_factory is None:
            return
        current_policy = asyncio.get_event_loop_policy()
        if current_policy.__class__.__name__ != "WindowsProactorEventLoopPolicy":
            asyncio.set_event_loop_policy(policy_factory())
            logger.info("Windows Playwright event loop policy set to Proactor")
    except Exception as exc:
        logger.warning(f"Could not set Windows Playwright event loop policy: {exc}")


# FUNCTION_CONTRACT: _detect_trends_block
# Purpose: Check page body text for Google Trends block/429 markers
# Input: body_text (str) — page body text content
# Output: bool — True if block markers detected
# Side Effects: none
# Business Rules: Case-insensitive matching against known block markers
# Failure Modes: Returns False on empty input
# LINKS: .planning/phases/16-local-cloakbrowser-trends-csv/16-01-PLAN.md#task-2
def _detect_trends_block(body_text: str) -> bool:
    if not body_text:
        return False
    text = body_text.lower()
    markers = [
        "too many requests",
        "unusual traffic",
        "automated queries",
        "our systems have detected",
        "error 429",
    ]
    return any(marker in text for marker in markers)


# FUNCTION_CONTRACT: _is_trends_block_response
# Purpose: Identify a Google Trends navigation response that indicates a real block
# Input: response (Any)
# Output: bool — True when the main document returned a 429
# Side Effects: none
# Business Rules: Ignore subresource 429s; only a 429 on the document navigation
#   should be treated as a hard block signal.
def _is_trends_block_response(response: Any) -> bool:
    try:
        if getattr(response, "status", None) != 429:
            return False
        request = getattr(response, "request", None)
        resource_type = str(getattr(request, "resource_type", "") or "").lower()
        return resource_type == "document"
    except Exception:
        return False


# FUNCTION_CONTRACT: _parse_trends_csv
# Purpose: Parse Google Trends CSV content into structured timeline data
# Input: csv_content (str) — raw CSV text from Google Trends download
# Output: list[dict[str, Any]] — list of {time, formatted_time, value} dicts
# Side Effects: none
# Business Rules: Handles BOM, multi-granularity/multi-language headers (Day/Week/
#   Month localized), date ranges, <1% values. Falls back to a structural probe
#   (date cell + numeric cell) so unknown/added localized headers still parse.
# Failure Modes: Returns empty list on empty/invalid CSV, logs warning
# LINKS: .planning/phases/16-local-cloakbrowser-trends-csv/16-01-PLAN.md#task-2
#   tmp/google_trends_test_results.md (weekly "today 12-m" CSV capture)
def _parse_trends_csv(csv_content: str) -> list[dict[str, Any]]:
    if not csv_content or not csv_content.strip():
        logger.warning("Empty CSV content in _parse_trends_csv")
        return []

    # Strip BOM character if present
    if csv_content.startswith('﻿'):
        csv_content = csv_content[1:]

    reader = csv.reader(io.StringIO(csv_content))
    rows = list(reader)

    # Localized granularity labels Google Trends uses as the header first cell.
    # Daily (День/Day), Weekly (Тиждень/Неделя/Week), Monthly (Місяць/Месяц/Month).
    # Coverage matters: "today 12-m" returns WEEKLY buckets, not daily — the
    # original parser only matched День/Day and dropped every weekly/monthly CSV.
    header_labels = {
        # Daily
        "День", "Day", "Ден",  # Ден = truncated Дeнь on some locales
        # Weekly
        "Тиждень", "Тиж.",     # UK week
        "Неделя", "Неделю", "Нед.",  # RU week
        "Week",                # EN week
        # Monthly
        "Місяць", "Міс.",      # UK month
        "Месяц", "Месяцев", "Мес.",  # RU month
        "Month",               # EN month
    }

    def _is_data_row(row: list[str]) -> bool:
        """A data row is [date-like, value-like]. Robust across granularities."""
        if not row or len(row) < 2:
            return False
        date_cell = (row[0] or "").strip()
        value_cell = (row[1] or "").strip()
        if not date_cell or not value_cell:
            return False
        # Date cell: YYYY-MM-DD, YYYY-MM, or a YYYY-MM-DD – YYYY-MM-DD range.
        date_ok = bool(re.search(r"\d{4}-\d{2}", date_cell))
        # Value cell: integer or Google's "<1%" low-volume marker.
        value_ok = value_cell.isdigit() or value_cell == "<1%" or value_cell.startswith("%")
        return date_ok and value_ok

    # Find the header row: known localized label, else the first structural
    # data row (date + numeric) marks where data begins directly.
    header_idx = None
    for i, row in enumerate(rows):
        if row and (row[0] or "").strip() in header_labels:
            header_idx = i
            break

    # Determine the data-start index: after a recognized header, or the first
    # structural data row when no label header is present.
    if header_idx is not None:
        data_rows = rows[header_idx + 1:]
    else:
        data_rows = rows
        # Only warn if we can't find ANY structural data row either — that's the
        # genuine empty/invalid case.
        if not any(_is_data_row(r) for r in rows):
            logger.warning("No data header found in Trends CSV")
            return []

    result = []
    for row in data_rows:
        if not _is_data_row(row):
            continue
        raw_date = (row[0] or "").strip()
        raw_value = (row[1] or "").strip()

        # Parse value: "<1%" / "%" markers -> 0; integer otherwise.
        if raw_value.startswith("%"):
            value = 0
        else:
            try:
                value = int(raw_value)
            except (ValueError, TypeError):
                value = 0

        # Extract first date component for "time" field
        time_match = re.match(r'(\d{4}-\d{2}-\d{2})', raw_date)
        time_val = time_match.group(1) if time_match else raw_date

        result.append({
            "time": time_val,
            "formatted_time": raw_date,
            "value": value,
        })

    if not result:
        logger.warning("No data rows found in Trends CSV")

    return result


# FUNCTION_CONTRACT: _validate_trends_keyword
# Purpose: Validate a single keyword for Google Trends CSV extraction
# Input: keyword (str)
# Output: None
# Side Effects: none
# Business Rules: Enforces single-keyword mode (no commas), non-empty
# Failure Modes: Raises ValueError on validation failure
# LINKS: .planning/phases/16-local-cloakbrowser-trends-csv/16-01-PLAN.md#task-2
def _validate_trends_keyword(keyword: str) -> None:
    if not keyword or not keyword.strip():
        raise ValueError("Keyword cannot be empty")
    if "," in keyword:
        raise ValueError(
            f"Comma is not allowed in one-keyword mode: {keyword}"
        )


# FUNCTION_CONTRACT: _load_session_state
# Purpose: Load session state from a JSON file
# Input: state_path (str | Path) — path to JSON state file
# Output: dict[str, Any] — loaded state or empty dict
# Side Effects: Reads file from disk
# Business Rules: Returns empty dict if file doesn't exist or is corrupted
# Failure Modes: Never raises; logs warning on corrupted JSON
# LINKS: .planning/phases/16-local-cloakbrowser-trends-csv/16-01-PLAN.md#task-2
def _load_session_state(state_path) -> dict[str, Any]:
    path = state_path if isinstance(state_path, Path) else Path(state_path)
    if not path.exists():
        return {}
    if path.stat().st_size == 0:
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load session state from {path}: {e}")
        return {}


# FUNCTION_CONTRACT: _save_session_state
# Purpose: Save session state data to a JSON file
# Input: state_path (str | Path), data (dict[str, Any])
# Output: None
# Side Effects: Writes JSON file to disk
# Business Rules: Creates parent directories if needed
# Failure Modes: Never raises; logs warning on write errors
# LINKS: .planning/phases/16-local-cloakbrowser-trends-csv/16-01-PLAN.md#task-2
def _save_session_state(state_path, data: dict[str, Any]) -> None:
    path = state_path if isinstance(state_path, Path) else Path(state_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.warning(f"Failed to save session state to {path}: {e}")


def _close_resource_quietly(resource: Any) -> None:
    if not resource:
        return
    try:
        resource.close()
    except Exception:
        pass


def _close_browser_resources(page: Any, browser: Any) -> None:
    _close_resource_quietly(page)
    _close_resource_quietly(browser)


# CLASS_CONTRACT: BrowserScraper
# Purpose: Browser automation scraper for Google Trends and SERP
# LINKS: requirements.xml#UC-010, verification-plan.xml#V-10-BROWSER-SCRAPER
class BrowserScraper:

    # SEMANTIC_BLOCK: block_browser_dependency_check
    # Check which browser engines and parsers are available

    _dependency_cache: Dict[str, DependencyStatus] = {}

    # FUNCTION_CONTRACT: check_dependencies
    # Purpose: Check availability of all optional dependencies
    # Input: (none)
    # Output: Dict[str, DependencyStatus]
    # Side Effects: Caches results in _dependency_cache
    # Business Rules: Checks browser engines and HTML parsers for usable APIs
    # Failure Modes: Returns UNKNOWN for packages that raise during check and UNUSABLE for incompatible installs
    # LINKS: requirements.xml#UC-010
    @classmethod
    # Purpose: Check availability of all optional dependencies.
    def check_dependencies(cls) -> Dict[str, DependencyStatus]:
        if not cls._dependency_cache:
            cls._dependency_cache = {
                name: _check_dependency(name, required_attrs)
                for name, required_attrs in BROWSER_DEPENDENCY_APIS.items()
            }
            # Special case: playwright also needs binary check
            if cls._dependency_cache.get("playwright") == DependencyStatus.AVAILABLE:
                if not _check_playwright_binary():
                    cls._dependency_cache["playwright"] = DependencyStatus.UNUSABLE
                    logger.warning("Playwright package installed but Chromium binary missing")
            logger.info(f"Browser dependency check: {cls._dependency_cache}")
        return cls._dependency_cache

    # FUNCTION_CONTRACT: is_available
    # Purpose: Check if browser scraping is available
    # Input: (none)
    # Output: bool
    # Side Effects: none
    # Business Rules: Returns True if at least one browser engine is installed
    # Failure Modes: Returns False if no engines available
    # LINKS: requirements.xml#UC-010
    @classmethod
    # Purpose: Check if browser scraping is available (engine and parser installed).
    def is_available(cls) -> bool:
        deps = cls.check_dependencies()
        # At least one browser engine must be available
        cloakbrowser_available = deps.get("cloakbrowser") == DependencyStatus.AVAILABLE
        playwright_available = deps.get("playwright") == DependencyStatus.AVAILABLE
        engine_available = cloakbrowser_available or playwright_available
        # Parser must be available
        parser_available = deps.get("trafilatura") == DependencyStatus.AVAILABLE
        return engine_available and parser_available

    @classmethod
    # Purpose: Return dependency install guidance for UI and logs.
    def dependency_install_message(cls) -> str:
        return get_dependency_install_message()

    # FUNCTION_CONTRACT: __init__
    # Purpose: Initialize browser scraper with configuration
    # Input: config (Optional[BrowserScraperConfig] = None)
    # Output: None
    # Side Effects: Stores config and validates dependencies
    # Business Rules: Logs warning if config requires unavailable engine
    # Failure Modes: Never raises; logs warnings for misconfigurations
    # LINKS: requirements.xml#UC-010
    def __init__(self, config: Optional[BrowserScraperConfig] = None) -> None:
        self.config = config or BrowserScraperConfig.from_settings()
        self._rate_limit_last: float = 0

    # FUNCTION_CONTRACT: _apply_rate_limit
    # Purpose: Apply rate limiting between requests
    # Input: (none)
    # Output: None
    # Side Effects: Sleeps if needed to respect rate_limit_delay
    # Business Rules: Ensures minimum delay between requests
    # Failure Modes: Never raises; sleep may be interrupted
    # LINKS: requirements.xml#UC-010
    def _apply_rate_limit(self) -> None:
        now = time.monotonic()
        elapsed = now - self._rate_limit_last
        delay = self.config.rate_limit_delay - elapsed
        if delay > 0:
            logger.info(f"Rate limit delay: {delay:.2f}s")
            time.sleep(delay)
        self._rate_limit_last = time.monotonic()

    # FUNCTION_CONTRACT: _build_cache_key
    # Purpose: Build cache key for request parameters
    # Input: kind (str), params (Dict[str, Any])
    # Output: str
    # Side Effects: none
    # Business Rules: Creates SHA256 hash of normalized params
    # Failure Modes: Never raises; returns hash of empty dict on error
    # LINKS: requirements.xml#UC-010
    def _build_cache_key(self, kind: str, params: Dict[str, Any]) -> str:
        try:
            # WR-06 FIX: More robust cache key generation to avoid collisions
            # Use deterministic serialization with fallback for unsupported types
            # Purpose: normalize implementation
            def normalize(obj):
                if isinstance(obj, dict):
                    return {k: normalize(v) for k, v in sorted(obj.items())}
                elif isinstance(obj, (list, tuple)):
                    return [normalize(item) for item in obj]
                elif isinstance(obj, (str, int, float, bool, type(None))):
                    return obj
                else:
                    # Convert unsupported types to string representation
                    return str(obj)

            normalized = json.dumps(normalize(params), sort_keys=True)
            return hashlib.sha256(f"{kind}:{normalized}".encode()).hexdigest()[:32]
        except Exception:
            # WR-06 FIX: Include timestamp in fallback to reduce collision risk
            fallback = f"{kind}:fallback:{time.time()}".encode()
            return hashlib.sha256(fallback).hexdigest()[:32]

    # FUNCTION_CONTRACT: _parse_with_trafilatura
    # Purpose: Parse HTML content with trafilatura
    # Input: html (str), url (str)
    # Output: Dict[str, Any]
    # Side Effects: none
    # Business Rules: Extracts title, text, metadata from HTML
    # Failure Modes: Returns empty dict on parse errors
    # LINKS: requirements.xml#UC-010
    def _parse_with_trafilatura(self, html: str, url: str = "") -> Dict[str, Any]:
        # WR-03 FIX: Enhanced runtime guard with early return
        if trafilatura is None:
            logger.warning("Trafilatura module is not installed")
            return {}
        if self.check_dependencies().get("trafilatura") != DependencyStatus.AVAILABLE:
            logger.warning("Trafilatura parser is not available")
            return {}
        try:
            metadata = trafilatura.extract_metadata(html, default_url=url)
            text = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                no_fallback=False,
            )
            return {
                "title": (metadata.title or "") if metadata else "",
                "description": (metadata.description or "") if metadata else "",
                "text": (text or "").strip(),
                "author": (metadata.author or "") if metadata else "",
                "date": (metadata.date or "") if metadata else "",
            }
        except Exception as e:
            logger.warning(f"Trafilatura parsing failed: {e}")
            return {}

    # Purpose: Parse HTML with trafilatura.
    def _parse_html(self, html: str, url: str = "") -> Dict[str, Any]:
        return self._parse_with_trafilatura(html, url)

    # FUNCTION_CONTRACT: _load_js_parser
    # Purpose: Load JavaScript parser from file
    # Input: js_filename (str)
    # Output: str
    # Side Effects: Reads file from disk
    # Business Rules: Returns empty string on file read errors
    # Failure Modes: Returns empty string if file not found or unreadable
    # LINKS: utils/batch_parse_serp.js
    def _load_js_parser(self, js_filename: str) -> str:
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(script_dir, js_filename)
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Failed to load JS parser {js_filename}: {e}")
            return ""

    # FUNCTION_CONTRACT: _handle_cookie_consent
    # Purpose: Handle cookie consent dialogs on Google pages
    # Input: page (Any) - browser page object
    # Output: bool - True if consent was handled
    # Side Effects: Clicks consent buttons, waits for dialog dismissal
    # Business Rules: Searches for common consent button text patterns across languages
    # Failure Modes: Returns False on any error
    # LINKS: parse_google_bigbox.py#handle_cookie
    def _handle_cookie_consent(self, page: Any) -> bool:
        try:
            # SEMANTIC_BLOCK: block_browser_cookie_handling
            # Multi-language consent button patterns
            consent_texts = [
                "Прийняти всі", "Принять все", "Accept all", "Я згоден",
                "Соглашаюсь", "Accept", "Прийняти", "Принять",
                "Погодитися", "Согласиться", "I agree", "Accept all"
            ]

            for text in consent_texts:
                try:
                    # Use Playwright text locators so button text is escaped by the library.
                    btn = page.get_by_text(text, exact=True).first
                    if btn.count() == 0:
                        raise ValueError("exact text button not present")
                    btn.click(timeout=2000)
                    page.wait_for_timeout(800)
                    logger.info(f"Clicked cookie consent button: {text}")
                    return True
                # WR-02 FIX: More specific exception handling to avoid obscuring real errors
                except (AttributeError, TypeError) as e:
                    logger.info(f"Button not found for text '{text}': {e}")
                except Exception:
                    try:
                        btn = page.get_by_text(text, exact=False).first
                        if btn.count() == 0:
                            continue
                        btn.click(timeout=2000)
                        page.wait_for_timeout(800)
                        logger.info(f"Clicked cookie consent button: {text}")
                        return True
                    except Exception as e:
                        logger.info(f"Button not found for text '{text}': {e}")
            return False
        except Exception as e:
            logger.warning(f"Cookie consent handling failed: {e}")
            return False

    # FUNCTION_CONTRACT: _click_next_page
    # Purpose: Click the "Next page" button on Google SERP
    # Input: page (Any) - browser page object
    # Output: bool - True if successfully navigated to next page
    # Side Effects: Navigates to next page of results
    # Business Rules: Handles multiple aria-label patterns across languages
    # Failure Modes: Returns False if button not found or navigation fails
    # LINKS: parse_google_bigbox.py#click_next_page
    def _click_next_page(self, page: Any) -> bool:
        try:
            # SEMANTIC_BLOCK: block_browser_handle_pagination
            # Multi-language next page button patterns
            btn = (page.query_selector("a[aria-label='Next page']") or
                   page.query_selector("a[aria-label*='Далі']") or
                   page.query_selector("a[aria-label*='Следующая']") or
                   page.query_selector("a#pnnext") or
                   page.query_selector("a[href*='start=']"))

            if not btn or btn.get_attribute("aria-disabled") == "true":
                return False

            with page.expect_navigation(wait_until="domcontentloaded", timeout=self.config.timeout_seconds * 1000):
                btn.click()
            page.wait_for_timeout(1000)
            logger.info("Navigated to next page")
            return True
        except Exception as e:
            logger.warning(f"Next page navigation failed: {e}")
            return False

    # FUNCTION_CONTRACT: _extract_with_trafilatura
    # Purpose: Extract content from HTML using trafilatura
    # Input: html (str), url (str)
    # Output: tuple[str, str] - (text_content, markdown_content)
    # Side Effects: none
    # Business Rules: Returns both plain text and markdown formats
    # Failure Modes: Returns ("", "") on parse errors
    # LINKS: parse_google_bigbox.py#extract_with_trafilatura
    def _extract_with_trafilatura(self, html: str, url: str = "") -> tuple[str, str]:
        if trafilatura is None:
            return "", ""

        try:
            parsed = trafilatura.load_html(html)
            if parsed is None:
                return "", ""

            text = trafilatura.extract(
                parsed,
                output_format="txt",
                include_links=True,
                include_images=False,
                include_tables=False,
                no_fallback=True,
            )

            md = trafilatura.extract(
                parsed,
                output_format="markdown",
                include_links=True,
                include_images=False,
                include_tables=True,
                no_fallback=True,
            )

            return (text or "", md or "")
        except Exception as e:
            logger.warning(f"Trafilatura extraction failed: {e}")
            return "", ""

    # SEMANTIC_BLOCK: block_browser_trends_csv_download
    # Google Trends browser scraping via CSV download

    # FUNCTION_CONTRACT: _build_trends_url
    # Purpose: Build Google Trends explore URL for a single keyword
    # Input: keyword (str), params (Dict[str, Any])
    # Output: str — fully formed Google Trends URL
    # Side Effects: none
    # Business Rules: Includes q, geo, date, hl, cat, gprop, tz parameters
    # Failure Modes: Returns malformed URL if _encode_params fails
    # LINKS: beta_trends_parsing.py#build_trends_url
    def _build_trends_url(self, keyword: str, params: Dict[str, Any]) -> str:
        category = params.get("category", params.get("cat", 0))
        query_params = {
            "q": keyword,
            "geo": params.get("geo", "UA"),
            "date": params.get("timeframe", "today 12-m"),
        }
        if params.get("hl"):
            query_params["hl"] = params["hl"]
        if category:
            query_params["cat"] = str(category)
        if params.get("gprop"):
            query_params["gprop"] = params["gprop"]
        if params.get("tz") is not None:
            query_params["tz"] = str(params["tz"])
        encoded = self._encode_params(query_params)
        return f"https://trends.google.com/trends/explore?{encoded}"

    # FUNCTION_CONTRACT: BrowserScraper._detect_trends_block
    # Purpose: Check page body text for Google Trends block/429 markers
    # Input: page (Any) — browser page object
    # Output: bool — True if block detected
    # Side Effects: Reads page body text
    # Business Rules: Delegates to module-level _detect_trends_block after extracting text
    # Failure Modes: Returns False on any exception (including timeout)
    # LINKS: beta_trends_parsing.py#detect_block
    def _detect_trends_block(self, page) -> bool:
        try:
            text = page.locator("body").inner_text(timeout=10_000)
        except Exception:
            return False
        return _detect_trends_block(text)

    # FUNCTION_CONTRACT: _maybe_accept_trends_cookies
    # Purpose: Accept cookie consent on Google Trends in EN/RU/UA
    # Input: page (Any) — browser page object
    # Output: bool — True if cookies were accepted
    # Side Effects: Clicks cookie consent button, waits for dialog dismissal
    # Business Rules: Tries multiple language variants with exact text matching
    # Failure Modes: Returns False on any error (button not found, click failure)
    # LINKS: beta_trends_parsing.py#maybe_accept_cookies
    def _maybe_accept_trends_cookies(self, page) -> bool:
        candidates = [
            "Accept all",
            "I agree",
            "Agree",
            "Принять все",
            "Я согласен",
            "Погоджуюсь",
            "Погодитися",
            "Прийняти все",
            "Прийняти всі",
        ]
        for text in candidates:
            try:
                button = page.get_by_text(text, exact=True)
                if button.count() > 0:
                    button.first.click(timeout=3000)
                    page.wait_for_timeout(1500)
                    return True
            except Exception:
                continue
        return False

    # FUNCTION_CONTRACT: _wait_for_trends_chart
    # Purpose: Wait for Google Trends chart to fully load
    # Input: page (Any) — browser page object
    # Output: bool — True if chart loaded successfully
    # Side Effects: Waits for markers or download button appearance
    # Business Rules: Checks multi-language markers first, falls back to download button
    # Failure Modes: Returns False if neither marker nor download button found within timeout
    # LINKS: beta_trends_parsing.py#wait_for_trends_loaded
    def _wait_for_trends_chart(self, page) -> bool:
        markers = [
            "Interest over time",
            "Интерес с течением времени",
            "Інтерес із часом",
            "Інтерес з часом",
            "Популярність із часом",
        ]
        for marker in markers:
            try:
                page.get_by_text(marker).first.wait_for(timeout=20_000)
                return True
            except Exception:
                continue

        # Fallback: download button appeared
        try:
            page.locator(
                'button[aria-label*="Download" i], '
                'button[aria-label*="Завантажити" i], '
                'button[aria-label*="Скачать" i]'
            ).first.wait_for(timeout=5_000)
            return True
        except Exception:
            pass

        return False

    # FUNCTION_CONTRACT: _download_trends_csv
    # Purpose: Download Google Trends CSV data and return as string
    # Input: page (Any) — browser page object
    # Output: str — CSV content as string
    # Side Effects: Triggers CSV download via button click, reads temp file, cleans up
    # Business Rules: Multilingual button selectors, tries all visible buttons
    # Failure Modes: Raises RuntimeError if no download button found or all clicks fail
    # LINKS: beta_trends_parsing.py#download_first_csv
    def _download_trends_csv(self, page) -> str:
        selectors = [
            'button[aria-label*="Download" i]',
            'button[title*="Download" i]',
            '[aria-label*="Download" i]',
            '[title*="Download" i]',
            'button[aria-label*="Завантажити" i]',
            'button[title*="Завантажити" i]',
            '[aria-label*="Завантажити" i]',
            '[title*="Завантажити" i]',
            'button[aria-label*="Скачать" i]',
            'button[title*="Скачать" i]',
            '[aria-label*="Скачать" i]',
            '[title*="Скачать" i]',
            'button:has-text("Download")',
            'button:has-text("Завантажити")',
            'button:has-text("Скачать")',
        ]

        for selector in selectors:
            locator = page.locator(selector)
            count = locator.count()
            if count <= 0:
                continue
            for i in range(count):
                item = locator.nth(i)
                try:
                    if not item.is_visible():
                        continue
                    with page.expect_download(timeout=60_000) as download_info:
                        item.click()
                    download = download_info.value

                    tmp = tempfile.NamedTemporaryFile(suffix='.csv', delete=False)
                    tmp_path = tmp.name
                    tmp.close()

                    download.save_as(tmp_path)

                    with open(tmp_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    Path(tmp_path).unlink(missing_ok=True)
                    return content
                except Exception:
                    continue

        raise RuntimeError("CSV download button was not found")

    # FUNCTION_CONTRACT: BrowserScraper._parse_trends_csv
    # Purpose: Parse Google Trends CSV content into structured timeline data
    # Input: csv_content (str) — raw CSV text from Google Trends download
    # Output: list[dict[str, Any]] — parsed timeline points
    # Side Effects: none
    # Business Rules: Delegates to module-level _parse_trends_csv
    # Failure Modes: Returns empty list on parse errors
    # LINKS: .planning/phases/16-local-cloakbrowser-trends-csv/16-01-PLAN.md#task-2
    def _parse_trends_csv(self, csv_content: str) -> list[dict[str, Any]]:
        return _parse_trends_csv(csv_content)

    # FUNCTION_CONTRACT: _extract_trends_widget_data
    # Purpose: Compatibility shim for the retired DOM/widget Trends parser
    # Input: *args, **kwargs
    # Output: Dict[str, Any]
    # Side Effects: none
    # Business Rules: Keeps older call sites and tests working while CSV download is the primary path
    # Failure Modes: Returns an empty dict when no recoverable payload is supplied
    # LINKS: tests/test_browser_scraper.py, beta_trends_parsing.py
    def _extract_trends_widget_data(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        csv_content = kwargs.get("csv_content")
        if isinstance(csv_content, str) and csv_content.strip():
            return {"timeline": self._parse_trends_csv(csv_content)}

        if args:
            candidate = args[0]
            if isinstance(candidate, str) and candidate.strip():
                if "Interest over time" in candidate or "," in candidate:
                    return {"timeline": self._parse_trends_csv(candidate)}
                return {"html": candidate}

        html = kwargs.get("html")
        if isinstance(html, str) and html.strip():
            return {"html": html}

        return {}

    # FUNCTION_CONTRACT: _load_trends_state
    # Purpose: Load browser session state from JSON file
    # Input: state_path (str) — path to state JSON file
    # Output: dict[str, Any] — loaded state or empty dict
    # Side Effects: Reads file from disk
    # Business Rules: Delegates to module-level _load_session_state
    # Failure Modes: Returns empty dict on file errors
    # LINKS: .planning/phases/16-local-cloakbrowser-trends-csv/16-01-PLAN.md#task-2
    def _load_trends_state(self, state_path: str) -> dict[str, Any]:
        return _load_session_state(state_path)

    # FUNCTION_CONTRACT: _save_trends_state
    # Purpose: Save browser context storage state to JSON file
    # Input: state_path (str), context (Any) — browser context object
    # Output: None
    # Side Effects: Calls context.storage_state() which writes JSON to disk
    # Business Rules: Wraps in try/except, never raises
    # Failure Modes: Logs warning on failure, never raises
    # LINKS: .planning/phases/16-local-cloakbrowser-trends-csv/16-01-PLAN.md#task-2
    def _save_trends_state(self, state_path: str, context) -> None:
        try:
            context.storage_state(path=state_path)
            logger.info(f"[GRACE:trends_csv] Saved session state to {state_path}")
        except Exception as e:
            logger.warning(f"Failed to save session state: {e}")

    # FUNCTION_CONTRACT: _warmup_trends_session
    # Purpose: Open the Google Trends home page and wait for manual warmup before querying
    # Input: context (Any) — browser context, manual_start_wait (int) — seconds to wait
    # Output: None
    # Side Effects: Opens a page to the Trends home, accepts cookies, sleeps, closes the page
    # Business Rules: Mirrors beta_trends_parsing.warmup_session() — lets the user accept
    #   cookies / log in during the wait; no data is extracted here
    # Failure Modes: Logs warnings on navigation/timeout errors; never raises
    # LINKS: beta_trends_parsing.py#warmup_session
    def _warmup_trends_session(self, context, manual_start_wait: int) -> None:
        warmup_page = None
        try:
            warmup_page = context.new_page()
            logger.info(
                f"[GRACE:trends_csv] Warmup: opening Google Trends home, "
                f"waiting {manual_start_wait}s"
            )
            warmup_page.goto(
                "https://trends.google.com/trends/",
                wait_until="domcontentloaded",
                timeout=90_000,
            )
            self._maybe_accept_trends_cookies(warmup_page)
            warmup_page.wait_for_timeout(manual_start_wait * 1000)
            logger.info("[GRACE:trends_csv] Warmup complete")
        except TargetClosedError:
            logger.warning(
                "[GRACE:trends_csv] Warmup failed: the browser/tab was closed externally "
                "(TargetClosedError) — the user may have closed the window"
            )
        except Exception as e:
            logger.warning(f"[GRACE:trends_csv] Warmup failed (non-fatal): {e}")
        finally:
            if warmup_page is not None:
                try:
                    warmup_page.close()
                except Exception:
                    pass

    # FUNCTION_CONTRACT: _execute_cloakbrowser_trends
    # Purpose: Scrape Google Trends using Cloakbrowser with CSV-download-based extraction
    # Input: keywords (List[str]), params (Dict[str, Any])
    # Output: BrowserScrapeResult
    # Side Effects: Launches browser, navigates to Google Trends, downloads CSV
    # Business Rules: Validates single keyword, handles block detection, cookie acceptance, chart loading, CSV download and parsing
    # Failure Modes: Returns failure result on block/429, timeout, or parse errors
    # LINKS: requirements.xml#UC-010, beta_trends_parsing.py
    # GRACE_LOG_MARKER: ENTER_trends_csv, EXIT_trends_csv, ERROR_trends_csv
    def _execute_cloakbrowser_trends(
        self,
        keywords: List[str],
        params: Dict[str, Any],
    ) -> BrowserScrapeResult:
        """Scrape Google Trends with Cloakbrowser and CSV-download-based extraction."""
        logger.info("[GRACE:ENTER_trends_csv] Starting Google Trends CSV download extraction")
        _ensure_windows_playwright_event_loop_policy()

        try:
            from cloakbrowser import launch
        except ImportError:
            logger.error("[GRACE:ERROR_trends_csv] Cloakbrowser not installed")
            return BrowserScrapeResult(
                source="none",
                success=False,
                errors=[f"Cloakbrowser not installed or unusable. {get_dependency_install_message()}"]
            )

        cache_key = self._build_cache_key("trends", {**params, "keywords": keywords})
        errors = []
        browser = None
        page = None

        try:
            self._apply_rate_limit()

            # Validate single keyword
            keyword = keywords[0] if keywords else ""
            try:
                _validate_trends_keyword(keyword)
            except ValueError as e:
                logger.error(f"[GRACE:ERROR_trends_csv] Keyword validation failed: {e}")
                return BrowserScrapeResult(
                    source="cloakbrowser",
                    cache_key=cache_key,
                    success=False,
                    errors=[f"Keyword validation failed: {e}"],
                    metadata={"engine": "cloakbrowser", "mode": "csv_download", "keywords": keywords},
                )

            # Extract parameters
            state_file = params.get("state_file", "")

            # Build Trends URL
            url = self._build_trends_url(keyword, params)
            logger.info(f"[GRACE:trends_csv] URL: {url}")

            # SEMANTIC_BLOCK: block_trends_stealth_config
            # MINIMAL cloakbrowser config — matches the validated beta_trends_parsing.py baseline.
            # Test results (tmp/google_trends_test_results.md) proved the minimal config works
            # reliably, while stealth_args=True / humanize / custom args trigger IMMEDIATE 429.
            timezone = params.get("timezone", "Europe/Kyiv")
            locale = params.get("locale", "uk-UA")

            # Trends must run NON-headless by default: only non-headless was validated in beta.
            # Allow explicit override via the google_trends.headless setting.
            trends_headless = params.get("headless", False)

            browser = launch(
                headless=trends_headless,
                timezone=timezone,
                locale=locale,
            )

            # Create context with accept_downloads and optional session state.
            # Minimal context — no custom user_agent/viewport/extra_http_headers (fingerprint surface).
            context_kwargs = {
                "accept_downloads": True,
                "locale": locale,
                "timezone_id": timezone,
            }
            if state_file:
                state = self._load_trends_state(state_file)
                if state:
                    context_kwargs["storage_state"] = state_file
                    logger.info(f"[GRACE:trends_csv] Loaded session state from {state_file}")

            ctx = browser.new_context(**context_kwargs)

            # Warmup: open the Trends home page and wait manual_start_wait seconds before
            # any query. Matches beta_trends_parsing.warmup_session() — lets the user accept
            # cookies / log in, then persists the warmed-up session state for reuse.
            manual_start_wait = int(params.get("manual_start_wait", 0) or 0)
            if manual_start_wait > 0:
                self._warmup_trends_session(ctx, manual_start_wait)
                if state_file:
                    self._save_trends_state(state_file, ctx)

            page = ctx.new_page()

            # Set up 429 response listener for the main document only.
            main_document_429_seen = [False]

            def on_response(response):
                if _is_trends_block_response(response):
                    main_document_429_seen[0] = True

            page.on("response", on_response)

            # Navigate to Trends URL
            page.goto(url, wait_until="domcontentloaded", timeout=90_000)
            page.wait_for_timeout(random.randint(2500, 5000))

            # Accept cookies if present
            accepted = self._maybe_accept_trends_cookies(page)
            if accepted:
                logger.info("[GRACE:trends_csv] Cookies accepted")
                if state_file:
                    self._save_trends_state(state_file, ctx)

            # Check for block/429 page
            if main_document_429_seen[0] or self._detect_trends_block(page):
                logger.warning("[GRACE:ERROR_trends_csv] Google returned 429/block page")
                return BrowserScrapeResult(
                    source="cloakbrowser",
                    cache_key=cache_key,
                    success=False,
                    errors=["Google returned 429/block page"],
                    metadata={"engine": "cloakbrowser", "mode": "csv_download", "status": "blocked"},
                )

            # Wait for chart to load
            loaded = self._wait_for_trends_chart(page)

            if not loaded:
                # Double-check block after timeout
                if main_document_429_seen[0] or self._detect_trends_block(page):
                    logger.warning("[GRACE:ERROR_trends_csv] Block detected after chart wait")
                    return BrowserScrapeResult(
                        source="cloakbrowser",
                        cache_key=cache_key,
                        success=False,
                        errors=["Google returned 429/block page"],
                        metadata={"engine": "cloakbrowser", "mode": "csv_download", "status": "blocked"},
                    )
                logger.error("[GRACE:ERROR_trends_csv] Trends chart did not load")
                return BrowserScrapeResult(
                    source="cloakbrowser",
                    cache_key=cache_key,
                    success=False,
                    errors=["Trends chart did not load"],
                    metadata={"engine": "cloakbrowser", "mode": "csv_download", "keywords": keywords},
                )

            page.wait_for_timeout(random.randint(1500, 3500))

            # Download CSV; if the download path collapses and the page is actually
            # blocked, surface a blocked result instead of a generic scrape error.
            try:
                csv_content = self._download_trends_csv(page)
            except Exception:
                if main_document_429_seen[0] or self._detect_trends_block(page):
                    logger.warning("[GRACE:ERROR_trends_csv] Block detected during CSV download")
                    return BrowserScrapeResult(
                        source="cloakbrowser",
                        cache_key=cache_key,
                        success=False,
                        errors=["Google returned 429/block page"],
                        metadata={"engine": "cloakbrowser", "mode": "csv_download", "status": "blocked"},
                    )
                raise

            # Parse CSV into structured data
            parsed_data = self._parse_trends_csv(csv_content)

            # Save session state
            if state_file:
                self._save_trends_state(state_file, ctx)

            logger.info(
                f"[GRACE:EXIT_trends_csv] Successfully downloaded and parsed "
                f"{len(parsed_data)} timeline points from CSV"
            )
            return BrowserScrapeResult(
                source="cloakbrowser",
                cache_key=cache_key,
                success=True,
                extracted_data={
                    "timeline": parsed_data,
                    "status": "csv_downloaded",
                },
                metadata={
                    "engine": "cloakbrowser",
                    "mode": "csv_download",
                    "keywords": keywords,
                    "params": params,
                    "timezone": timezone,
                    "locale": locale,
                },
            )

        except TimeoutError:
            errors.append("Timeout waiting for Google Trends page")
            logger.error("[GRACE:ERROR_trends_csv] Timeout")
            return BrowserScrapeResult(
                source="cloakbrowser",
                cache_key=cache_key,
                success=False,
                errors=errors,
            )
        except TargetClosedError:
            errors.append("Browser closed during navigation (TargetClosedError)")
            logger.warning(
                "[GRACE:trends_csv] Browser was closed during navigation — "
                "the user may have closed the window (TargetClosedError)"
            )
            return BrowserScrapeResult(
                source="cloakbrowser",
                cache_key=cache_key,
                success=False,
                errors=errors,
                metadata={"engine": "cloakbrowser", "mode": "csv_download", "status": "browser_closed"},
            )
        except Exception as e:
            errors.append(f"Cloakbrowser error: {str(e)}")
            logger.error(f"[GRACE:ERROR_trends_csv] {e}")
            return BrowserScrapeResult(
                source="cloakbrowser",
                cache_key=cache_key,
                success=False,
                errors=errors,
            )
        finally:
            # CR-02 FIX: Ensure browser resources are always cleaned up
            _close_browser_resources(page, browser)

    # FUNCTION_CONTRACT: _encode_params
    # Purpose: URL-encode query parameters
    # Input: params (Dict[str, Any])
    # Output: str
    # Side Effects: none
    # Business Rules: Converts dict to URL-encoded query string
    # Failure Modes: Returns empty string on error
    # LINKS: requirements.xml#UC-010
    def _encode_params(self, params: Dict[str, Any]) -> str:
        try:
            from urllib.parse import urlencode
            return urlencode(params)
        except Exception as e:
            logger.warning(f"URL encoding failed for params {params}: {e}")
            return ""

    # FUNCTION_CONTRACT: _wait_for_dynamic_content
    # Purpose: Wait for dynamic content to load
    # Input: page (Any) - browser page object
    # Output: None
    # Side Effects: Waits/selects on page for DOM elements
    # Business Rules: Waits for common Google Trends/SERP selectors
    # Failure Modes: Timeout after configured seconds
    # LINKS: requirements.xml#UC-010
    def _wait_for_dynamic_content(self, page: Any) -> None:
        try:
            # WR-05 FIX: Use more robust, semantic selectors less likely to break
            # Combine CSS selectors with ARIA-based fallbacks and structural elements
            selectors = [
                # Trends: use multiple indicators for redundancy
                "div.feed-load-more-button",
                "div.timeline-chart",
                "[aria-label*='trends' i]",
                # SERP: use semantic elements
                "div.related-searches",
                "div#search",
                "[role='main']",
                # Fallback to universal elements
                "body",
            ]
            for selector in selectors:
                try:
                    page.wait_for_selector(selector, timeout=5000)
                    logger.info(f"Dynamic content detected via selector: {selector}")
                    break
                except Exception:
                    continue
            # Additional wait for JavaScript execution
            time.sleep(1)
        except Exception as e:
            logger.warning(f"Wait for dynamic content failed: {e}")

    # FUNCTION_CONTRACT: _detect_captcha
    # Purpose: Detect CAPTCHA presence on page
    # Input: page (Any) - browser page object
    # Output: bool
    # Side Effects: none
    # Business Rules: Checks for common CAPTCHA indicators after page stability
    # Failure Modes: Returns False on detection errors
    # LINKS: requirements.xml#UC-010
    def _detect_captcha(self, page: Any) -> bool:
        try:
            # CR-04 FIX: Wait for page stability before detecting CAPTCHA
            # This prevents race conditions where CAPTCHA elements load after detection
            page.wait_for_load_state("networkidle", timeout=3000)
        except Exception:
            # Network idle timeout is acceptable - proceed with detection anyway
            pass

        try:
            # Common CAPTCHA indicators
            captcha_indicators = [
                "div.g-recaptcha",
                "iframe[src*='recaptcha']",
                ".captcha",  # CR-04 FIX: Fixed typo from "divcaptcha"
                "#captcha",
                "form[action*='captcha']",
                "#captcha-form",
                "[data-recaptcha]",
            ]
            for indicator in captcha_indicators:
                try:
                    element = page.query_selector(indicator)
                    if element and element.is_visible():
                        return True
                except Exception:
                    continue

            # Check page title
            title = page.title().lower()
            return any(term in title for term in ["captcha", "verify you are human", "unusual traffic"])
        except Exception as e:
            logger.warning(f"CAPTCHA detection failed: {e}")
            return False

    # FUNCTION_CONTRACT: _extract_paa_data
    # Purpose: Extract People Also Ask (PAA) questions and answers from SERP
    # Input: page (Any) - browser page object
    # Output: List[Dict[str, str]] - List of PAA items with question, answer, source_url
    # Side Effects: May expand PAA items by clicking them (inline JS handles this)
    # Business Rules: Extracts multi-language PAA sections, clicks to reveal answers
    # Failure Modes: Returns empty list on extraction errors
    # LINKS: parse_google_bigbox.py#PAA_PARSE_JS
    def _extract_paa_data(self, page: Any) -> List[Dict[str, str]]:
        try:
            # SEMANTIC_BLOCK: block_browser_paa_extraction
            # PAA extraction JavaScript - handles multi-language triggers
            paa_js = """
            () => {
                const R = [];
                const triggers = [
                    'Люди також питають', 'Люди также спрашивают',
                    'People also ask', 'Люди також запитують',
                ];
                let section = null;

                // Find PAA section by heading text
                for (const el of document.querySelectorAll('h2, h3, h4, div[role="heading"], div')) {
                    const txt = (el.textContent || '').trim();
                    for (const t of triggers) {
                        if (txt.indexOf(t) >= 0) {
                            let s = el.closest('div[data-hveid]') || el.parentElement;
                            if (s) { section = s; break; }
                        }
                    }
                    if (section) break;
                }
                if (!section) return [];

                const seen = new Set();
                for (const item of section.querySelectorAll('div[role="button"], div[jsaction*="tap"], div[jscontroller]')) {
                    try {
                        const txt = ((item.textContent || '').trim());
                        if (txt.length < 10 || txt.length > 200 || seen.has(txt)) continue;
                        seen.add(txt);

                        // Click to reveal answer
                        try { item.click(); } catch(e) {}

                        let answer = '';
                        const p = item.closest('div');
                        if (p) {
                            for (const d of p.querySelectorAll('div')) {
                                const t = ((d.textContent || '').trim());
                                if (t.length > 50 && t !== txt) {
                                    const st = window.getComputedStyle(d);
                                    if (st.display !== 'none' && st.visibility !== 'hidden') {
                                        answer = t.substring(0, 800); break;
                                    }
                                }
                            }
                        }

                        let srcUrl = '';
                        const pd = item.closest('div');
                        if (pd) { const lk = pd.querySelector('a[href^="http"]'); if (lk) srcUrl = lk.href; }

                        R.push({ question: txt.substring(0, 200), answer: answer.substring(0, 500), source_url: srcUrl });
                    } catch(e) {}
                }
                return R;
            }
            """
            return page.evaluate(paa_js) or []
        except Exception as e:
            logger.warning(f"PAA extraction failed: {e}")
            return []

    # FUNCTION_CONTRACT: scrape_google_trends
    # Purpose: Scrape Google Trends using browser automation
    # Input: keywords (List[str]), params (Dict[str, Any])
    # Output: BrowserScrapeResult
    # Side Effects: Launches browser, navigates to Google Trends
    # Business Rules: Handles rate limiting, CAPTCHA detection
    # Failure Modes: Returns failure result with error details
    # LINKS: requirements.xml#UC-010
    def scrape_google_trends(
        self,
        keywords: List[str],
        params: Dict[str, Any],
    ) -> BrowserScrapeResult:
        """Scrape Google Trends using browser automation."""
        if not self.is_available():
            return BrowserScrapeResult(
                source="none",
                success=False,
                errors=[get_no_browser_engine_error()],
            )

        logger.info(f"Scraping Google Trends with cloakbrowser for keywords: {keywords[:3]}")

        # Execute with cloakbrowser
        result = self._execute_cloakbrowser_trends(keywords, params)

        return result

    # SEMANTIC_BLOCK: block_browser_scraper_serp
    # SERP browser scraping with GRACE compliance

    # FUNCTION_CONTRACT: _execute_cloakbrowser_serp
    # Purpose: Scrape Google SERP using Cloakbrowser with GRACE compliance
    # Input: query (str), params (Dict[str, Any])
    # Output: BrowserScrapeResult
    # Side Effects: Launches browser, navigates to Google Search, handles pagination
    # Business Rules: Extracts organic results, PAA, related searches from SERP with pagination support
    # Failure Modes: Returns failure result on errors
    # LINKS: requirements.xml#UC-010, parse_google_bigbox.py#main
    # GRACE_LOG_MARKER: ENTER_serp_parsing, EXIT_serp_parsing, ERROR_serp_parsing
    def _execute_cloakbrowser_serp(
        self,
        query: str,
        params: Dict[str, Any],
    ) -> BrowserScrapeResult:
        """Scrape Google SERP with Cloakbrowser and CSS-class-agnostic parsing."""
        logger.info("[GRACE:ENTER_serp_parsing] Starting Google SERP scraping")
        _ensure_windows_playwright_event_loop_policy()

        try:
            from cloakbrowser import launch
        except ImportError:
            logger.error("[GRACE:ERROR_serp_parsing] Cloakbrowser not installed")
            return BrowserScrapeResult(
                source="none",
                success=False,
                errors=[f"Cloakbrowser not installed or unusable. {get_dependency_install_message()}"]
            )

        cache_key = self._build_cache_key("serp", {**params, "query": query})
        errors = []
        browser = None
        page = None

        try:
            self._apply_rate_limit()

            # SEMANTIC_BLOCK: block_serp_stealth_config
            # Proper stealth configuration for Google SERP
            timezone = params.get("timezone", "Europe/Kyiv")
            locale = params.get("locale", "uk-UA")
            google_domain = params.get("google_domain", "google.com.ua")
            user_agent = self.config.user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

            total_results_target = params.get("total_results_target", 50)
            pages_max = params.get("pages_max", 10)

            browser = launch(
                headless=self.config.headless,
                timezone=timezone,
                locale=locale,
                stealth_args=True,
                humanize=True,
                human_preset="default",
                args=["--disable-blink-features=AutomationControlled", "--window-size=1920,1080"]
            )

            ctx = browser.new_context(
                user_agent=user_agent,
                viewport={"width": 1920, "height": 1080},
                locale=locale,
                timezone_id=timezone,
                extra_http_headers={"Accept-Language": f"{locale},uk;q=0.9,ru;q=0.8,en;q=0.7"}
            )
            page = ctx.new_page()

            # Navigate to Google homepage first
            google_home = f"https://www.{google_domain}"
            logger.info(f"[GRACE:serp_parsing] Navigating to Google home: {google_home}")
            page.goto(google_home, wait_until="load", timeout=30000)
            page.wait_for_timeout(1000)

            # Handle cookie consent
            self._handle_cookie_consent(page)

            # Execute search
            logger.info(f"[GRACE:serp_parsing] Executing search for: {query}")
            search_box = page.wait_for_selector("textarea[name='q'], input[name='q']", timeout=10000)
            search_box.click()
            page.wait_for_timeout(200)
            search_box.fill(query)
            page.wait_for_timeout(300)

            with page.expect_navigation(wait_until="domcontentloaded", timeout=self.config.timeout_seconds * 1000):
                search_box.press("Enter")
            page.wait_for_timeout(1000)

            # SEMANTIC_BLOCK: block_browser_handle_pagination
            # Pagination loop for multiple pages
            all_results = []
            page_num = 0
            people_also_ask = []
            trafilatura_text = ""
            trafilatura_md = ""

            while len(all_results) < total_results_target and page_num < pages_max:
                page_num += 1
                logger.info(f"[GRACE:serp_parsing] Page {page_num} (total results: {len(all_results)})")
                page.wait_for_timeout(800)

                # First page: capture screenshot, stats, and PAA
                if page_num == 1:
                    try:
                        page.screenshot(path="google_serp_results.png", full_page=True)
                        stats_elem = page.query_selector("#result-stats")
                        if stats_elem:
                            logger.info(f"[GRACE:serp_parsing] Stats: {stats_elem.inner_text().strip()}")
                    except Exception as e:
                        logger.warning(f"[GRACE:serp_parsing] Screenshot/stats failed: {e}")

                    # Extract PAA (People Also Ask)
                    people_also_ask = self._extract_paa_data(page)
                    logger.info(f"[GRACE:serp_parsing] PAA items: {len(people_also_ask)}")

                # Load and evaluate the CSS-class-agnostic SERP parser
                batch_parse_js = self._load_js_parser("batch_parse_serp.js")
                if not batch_parse_js:
                    errors.append("Failed to load SERP parser JavaScript")
                    logger.error("[GRACE:ERROR_serp_parsing] Could not load batch_parse_serp.js")
                    return BrowserScrapeResult(
                        source="cloakbrowser",
                        cache_key=cache_key,
                        success=False,
                        errors=errors,
                    )

                try:
                    raw_results = page.evaluate(batch_parse_js) or []
                except Exception as e:
                    logger.warning(f"[GRACE:serp_parsing] Parse error: {e}")
                    raw_results = []

                # Deduplicate by URL
                seen_urls = set(r.get("url") for r in all_results if r.get("url"))
                new_count = 0
                for result in raw_results:
                    url = result.get("url")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_results.append(result)
                        new_count += 1

                logger.info(f"[GRACE:serp_parsing] +{new_count} new results (total: {len(all_results)})")

                # First page: extract trafilatura content
                if page_num == 1:
                    try:
                        html = page.content()
                        trafilatura_text, trafilatura_md = self._extract_with_trafilatura(html, page.url)
                        if trafilatura_text:
                            logger.info(f"[GRACE:serp_parsing] Trafilatura extracted {len(trafilatura_text)} chars")
                    except Exception as e:
                        logger.warning(f"[GRACE:serp_parsing] Trafilatura extraction failed: {e}")

                # Navigate to next page if needed
                if len(all_results) < total_results_target:
                    if not self._click_next_page(page):
                        logger.info("[GRACE:serp_parsing] No more pages available")
                        break
                # WR-04 FIX: Ensure we don't exit the loop if we've reached the target
                # exactly - the break above handles the "no more pages" case
                elif page_num >= pages_max:
                    logger.info(f"[GRACE:serp_parsing] Reached max pages ({pages_max})")
                    break

            logger.info(
                f"[GRACE:EXIT_serp_parsing] Success: {page_num} pages, "
                f"{len(all_results)} results, {len(people_also_ask)} PAA items"
            )

            # Build rich snippet counts for metadata
            rich_counts = {}
            for r in all_results:
                for k in r.get("rich_snippet", {}):
                    rich_counts[k] = rich_counts.get(k, 0) + 1

            return BrowserScrapeResult(
                source="cloakbrowser",
                raw_html="",  # HTML not stored for multi-page results
                parsed_content={
                    "results": [{"position": i + 1, **r} for i, r in enumerate(all_results)],
                    "people_also_ask": people_also_ask[:15],  # Limit PAA items
                    "trafilatura": {
                        "text": trafilatura_text[:4000] if trafilatura_text else "",  # Limit size
                        "markdown": trafilatura_md[:8000] if trafilatura_md else "",
                    }
                },
                cache_key=cache_key,
                metadata={
                    "engine": "cloakbrowser",
                    "parser": "resilient (semantic/ARIA/text, no CSS classes)",
                    "pages_scraped": page_num,
                    "total_results": len(all_results),
                    "paa_count": len(people_also_ask),
                    "rich_snippets": rich_counts,
                    "query": query,
                    "google_domain": google_domain,
                },
                success=True,
            )

        except TimeoutError:
            errors.append("Timeout waiting for Google SERP")
            logger.error("[GRACE:ERROR_serp_parsing] Timeout")
            return BrowserScrapeResult(
                source="cloakbrowser",
                cache_key=cache_key,
                success=False,
                errors=errors,
            )
        except Exception as e:
            errors.append(f"Cloakbrowser SERP error: {str(e)}")
            logger.error(f"[GRACE:ERROR_serp_parsing] {e}")
            return BrowserScrapeResult(
                source="cloakbrowser",
                cache_key=cache_key,
                success=False,
                errors=errors,
            )
        finally:
            # CR-02 FIX: Ensure browser resources are always cleaned up
            _close_browser_resources(page, browser)

    # FUNCTION_CONTRACT: _extract_serp_data
    # Purpose: Extract structured SERP data from browser page
    # Input: page (Any) - browser page object
    # Output: Dict[str, Any]
    # Side Effects: Executes JS to extract SERP elements
    # Business Rules: Extracts organic results, PAA, related searches
    # Failure Modes: Returns empty dict on extraction errors
    # LINKS: requirements.xml#UC-010
    def _extract_serp_data(self, page: Any) -> Dict[str, Any]:
        try:
            js_code = """
            () => {
                const result = {
                    organic: [],
                    related_searches: [],
                    people_also_ask: [],
                };

                // Extract organic results
                document.querySelectorAll('div.g').forEach((el, idx) => {
                    const titleEl = el.querySelector('h3');
                    const linkEl = el.querySelector('a');
                    const snippetEl = el.querySelector('.VwiC3b');
                    if (titleEl && linkEl) {
                        result.organic.push({
                            position: idx + 1,
                            title: titleEl.textContent || '',
                            url: linkEl.href || '',
                            snippet: snippetEl ? snippetEl.textContent : ''
                        });
                    }
                });

                // Extract related searches
                document.querySelectorAll('div[role="listitem"]').forEach((el) => {
                    const text = el.textContent?.trim();
                    if (text) result.related_searches.push(text);
                });

                // Extract People Also Ask
                document.querySelectorAll('div.related-question-pair').forEach((el) => {
                    const questionEl = el.querySelector('.r');
                    if (questionEl) {
                        result.people_also_ask.push({
                            question: questionEl.textContent || '',
                            snippet: ''
                        });
                    }
                });

                return result;
            }
            """
            return page.evaluate(js_code)
        except Exception as e:
            logger.warning(f"SERP data extraction failed: {e}")
            return {"organic": [], "related_searches": [], "people_also_ask": []}

    # FUNCTION_CONTRACT: scrape_serp
    # Purpose: Scrape Google SERP using browser automation
    # Input: query (str), params (Dict[str, Any])
    # Output: BrowserScrapeResult
    # Side Effects: Launches browser, navigates to Google Search
    # Business Rules: Handles rate limiting, CAPTCHA detection
    # Failure Modes: Returns failure result with error details
    # LINKS: requirements.xml#UC-010
    def scrape_serp(
        self,
        query: str,
        params: Dict[str, Any],
    ) -> BrowserScrapeResult:
        """Scrape Google SERP using browser automation."""
        if not self.is_available():
            return BrowserScrapeResult(
                source="none",
                success=False,
                errors=[get_no_browser_engine_error()],
            )

        logger.info(f"Scraping SERP with cloakbrowser for query: {query}")

        # Execute with cloakbrowser
        result = self._execute_cloakbrowser_serp(query, params)

        return result


# FUNCTION_CONTRACT: create_browser_scraper
# Purpose: Factory function to create BrowserScraper with config
# Input: config (Optional[BrowserScraperConfig] = None)
# Output: BrowserScraper
# Side Effects: none
# Business Rules: Creates scraper with provided or default config
# Failure Modes: Never raises
# LINKS: requirements.xml#UC-010
def create_browser_scraper(config: Optional[BrowserScraperConfig | Dict[str, Any]] = None) -> Optional[BrowserScraper]:
    if isinstance(config, dict):
        scraper_config = BrowserScraperConfig.from_settings(config)
    else:
        scraper_config = config or BrowserScraperConfig.from_settings()

    # Check if browser scraping is enabled in settings
    settings = load_config()
    if not settings.get("scraper", {}).get("browser_enabled", False):
        logger.info("Browser scraping is disabled in settings")
        return None

    # Check if at least one engine is available
    if not BrowserScraper.is_available():
        logger.warning("Browser scraping enabled but optional browser dependencies are unavailable")
        logger.info(get_dependency_install_message())
        return None

    return BrowserScraper(scraper_config)
