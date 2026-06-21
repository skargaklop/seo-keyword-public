# MODULE_CONTRACT: utils/logger
# Purpose: Provide logger helpers for this module.
# Rationale: Keep the module boundary explicit for GRACE adoption and review.
# Dependencies: logging, os, re, sys, pathlib, logging.handlers, config.settings
# Exports: LOG_DIR, APP_LOG, API_LOG, ERROR_LOG, AppLogger, logger, sanitize_log_message
# LINKS: requirements.xml#UC-001, development-plan.xml#MOD-001
# MODULE_MAP: utils/logger.py
# Public Functions: exported callables and classes defined in this module
# Private Helpers: internal helpers and private methods defined in this module
# Key Semantic Blocks: main workflow paths and state transitions in this module, block_logger_secret_safe_event
# Critical Flows: preserve existing runtime behavior and integrations
# Verification: python -m py_compile, python -m ruff check ., python -m pytest -q
# CHANGE_SUMMARY: Added file-local module metadata and declaration contracts; Phase 8 Plan 03: added secret-safe structured log helper for expected credential-routing failures.

import logging
import os
import re
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

from config.settings import load_config

# Define log paths
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

APP_LOG = LOG_DIR / "app.log"
API_LOG = LOG_DIR / "api_requests.log"
ERROR_LOG = LOG_DIR / "errors.log"

SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|token|secret|password)(\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(bearer\s+)([A-Za-z0-9._~+/=-]{8,})"),
    re.compile(r"\b(sk-[A-Za-z0-9_-]{8,})\b"),
)


# block_logger_secret_safe_event: Secret-safe structured logging for expected runtime events
# Semantic block: Redacts common credential shapes before writing concise operational markers.


# FUNCTION_CONTRACT: sanitize_log_message
# Purpose: Redact common secret/token shapes before logging externally supplied error text.
# Input: message (str)
# Output: str
# Side Effects: none
# Business Rules: Preserve useful provider/error context while removing API keys, bearer tokens, and password/token values.
# Failure Modes: never raises; non-string inputs are stringified.
# LINKS: PLAN 08-03 Task 1
def sanitize_log_message(message: str) -> str:
    sanitized = str(message)
    for pattern in SECRET_PATTERNS:
        if pattern.pattern.startswith("(?i)(bearer"):
            sanitized = pattern.sub(r"\1[REDACTED]", sanitized)
        elif pattern.pattern.startswith("\\b(sk-"):
            sanitized = pattern.sub("[REDACTED]", sanitized)
        else:
            sanitized = pattern.sub(r"\1\2[REDACTED]", sanitized)
    return sanitized

# CLASS_CONTRACT: AppLogger
# Purpose: Configure application, API, and error loggers from runtime settings.
# LINKS: requirements.xml#UC-001
class AppLogger:
    # FUNCTION_CONTRACT: __init__
    # Purpose: Initialize the surrounding object state.
    # Input: (none)
    # Output: None
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def __init__(self):
        self._setup_loggers()
    # FUNCTION_CONTRACT: _resolve_level
    # Purpose: Implement the  resolve level helper for this module.
    # Input: level_name (str), default (int)
    # Output: int
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    def _resolve_level(level_name: str, default: int) -> int:
        return getattr(logging, str(level_name).upper(), default)
    # FUNCTION_CONTRACT: _is_test_context
    # Purpose: Implement the  is test context helper for this module.
    # Input: (none)
    # Output: bool
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    def _is_test_context() -> bool:
        return bool(os.getenv("PYTEST_CURRENT_TEST") or "pytest" in sys.modules)
    # FUNCTION_CONTRACT: refresh_config
    # Purpose: Implement the refresh config helper for this module.
    # Input: (none)
    # Output: None
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def refresh_config(self) -> None:
        self._setup_loggers()
    # FUNCTION_CONTRACT: close_handlers
    # Purpose: Implement the close handlers helper for this module.
    # Input: (none)
    # Output: None
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def close_handlers(self) -> None:
        for target_logger in (
            logging.getLogger("seo_planner"),
            logging.getLogger("api_tracker"),
        ):
            for handler in list(target_logger.handlers):
                target_logger.removeHandler(handler)
                try:
                    handler.close()
                except Exception:
                    pass
    # FUNCTION_CONTRACT: _setup_loggers
    # Purpose: Implement the  setup loggers helper for this module.
    # Input: (none)
    # Output: None
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def _setup_loggers(self):
        cfg = load_config()
        logging_cfg = cfg.get("logging", {})
        app_level = self._resolve_level(logging_cfg.get("app_level", "INFO"), logging.INFO)
        console_enabled = bool(logging_cfg.get("console_enabled", True))
        console_level = self._resolve_level(
            logging_cfg.get("console_level", "INFO"), logging.INFO
        )
        api_enabled = bool(logging_cfg.get("api_enabled", True))
        api_level = self._resolve_level(logging_cfg.get("api_level", "DEBUG"), logging.DEBUG)
        error_level = self._resolve_level(
            logging_cfg.get("error_level", "ERROR"), logging.ERROR
        )
        log_test_runs = bool(logging_cfg.get("log_test_runs", False))
        # FUNCTION_CONTRACT: _reset_handlers
        # Purpose: Remove and close all handlers currently attached to a logger.
        # Input: target_logger (logging.Logger)
        # Output: None
        # Side Effects: Mutates logger handler lists and closes handler resources.
        # Business Rules: Ignores handler close failures to keep logger refresh best-effort.
        # Failure Modes: Propagates unexpected logger mutation errors.
        # LINKS: requirements.xml#UC-001
        def _reset_handlers(target_logger: logging.Logger) -> None:
            for handler in list(target_logger.handlers):
                target_logger.removeHandler(handler)
                try:
                    handler.close()
                except Exception:
                    pass

        # CLASS_CONTRACT: _TestContextFilter
        # Purpose: Suppress console log records during tests unless explicitly enabled.
        # LINKS: requirements.xml#UC-001
        class _TestContextFilter(logging.Filter):
            # FUNCTION_CONTRACT: filter
            # Purpose: Implement the filter helper for this module.
            # Input: record (logging.LogRecord)
            # Output: bool
            # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
            # Business Rules: Preserves the current validation and control flow for this call path.
            # Failure Modes: Propagates upstream exceptions and existing fallback paths.
            # LINKS: requirements.xml#UC-001
            def filter(self, record: logging.LogRecord) -> bool:
                if log_test_runs:
                    return True
                return not AppLogger._is_test_context()

        test_filter = _TestContextFilter()

        # Formatters
        simple_formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        verbose_formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 1. Main App Logger
        self.main_logger = logging.getLogger("seo_planner")
        _reset_handlers(self.main_logger)
        self.main_logger.setLevel(min(app_level, console_level, error_level, api_level))
        # Prevent propagation to avoid double logging if root logger is configured
        self.main_logger.propagate = False

        # File handler for app.log
        app_handler = RotatingFileHandler(APP_LOG, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
        app_handler.setFormatter(simple_formatter)
        app_handler.setLevel(app_level)
        app_handler.addFilter(test_filter)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(simple_formatter)
        console_handler.setLevel(console_level)
        console_handler.addFilter(test_filter)

        # Error handler for errors.log
        error_handler = RotatingFileHandler(ERROR_LOG, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
        error_handler.setFormatter(verbose_formatter)
        error_handler.setLevel(error_level)
        error_handler.addFilter(test_filter)

        self.main_logger.addHandler(app_handler)
        if console_enabled:
            self.main_logger.addHandler(console_handler)
        self.main_logger.addHandler(error_handler)

        # 2. API Logger (Specialized)
        self.api_logger = logging.getLogger("api_tracker")
        _reset_handlers(self.api_logger)
        self.api_logger.setLevel(api_level)
        self.api_logger.propagate = False

        api_handler = RotatingFileHandler(API_LOG, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
        api_handler.setFormatter(logging.Formatter('%(message)s')) # Raw message for easier json parsing if needed
        api_handler.setLevel(api_level)
        api_handler.addFilter(test_filter)
        if api_enabled:
            self.api_logger.addHandler(api_handler)
    # FUNCTION_CONTRACT: info
    # Purpose: Implement the info helper for this module.
    # Input: message (str)
    # Output: None
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def info(self, message: str):
        self.main_logger.info(message)
    # FUNCTION_CONTRACT: warning
    # Purpose: Implement the warning helper for this module.
    # Input: message (str)
    # Output: None
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def warning(self, message: str):
        self.main_logger.warning(message)
    # FUNCTION_CONTRACT: log_secret_safe_event
    # Purpose: Log a structured marker and redacted message without exposing credentials.
    # Input: marker (str), message (str), level (str = "warning")
    # Output: None
    # Side Effects: Writes to configured application log at requested level.
    # Business Rules: Applies sanitize_log_message to all caller-provided message content.
    # Failure Modes: Falls back to warning for unknown levels.
    # LINKS: PLAN 08-03 Task 1
    def log_secret_safe_event(self, marker: str, message: str, level: str = "warning") -> None:
        safe_message = f"{marker} {sanitize_log_message(message)}"
        log_level = str(level).lower()
        if log_level == "info":
            self.main_logger.info(safe_message)
        elif log_level == "error":
            self.main_logger.error(safe_message, exc_info=False)
        else:
            self.main_logger.warning(safe_message)
    # FUNCTION_CONTRACT: error
    # Purpose: Implement the error helper for this module.
    # Input: message (str), exc_info (Any = True)
    # Output: None
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def error(self, message: str, exc_info=True):
        self.main_logger.error(message, exc_info=exc_info)
    # FUNCTION_CONTRACT: critical
    # Purpose: Implement the critical helper for this module.
    # Input: message (str), exc_info (Any = True)
    # Output: None
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def critical(self, message: str, exc_info=True):
        self.main_logger.critical(message, exc_info=exc_info)
    # FUNCTION_CONTRACT: log_api_request
    # Purpose: Implement the log api request helper for this module.
    # Input: provider (str), endpoint (str), payload (dict)
    # Output: None
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def log_api_request(self, provider: str, endpoint: str, payload: dict):
        msg = f"[{provider.upper()}] REQUEST to {endpoint}\nPayload: {payload}\n{'-'*50}"
        self.api_logger.debug(msg)
    # FUNCTION_CONTRACT: log_api_response
    # Purpose: Implement the log api response helper for this module.
    # Input: provider (str), duration (float), response (any), status_code (int = 200), error (str = None)
    # Output: None
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def log_api_response(self, provider: str, duration: float, response: any, status_code: int = 200, error: str = None):
        status = "ERROR" if error else "SUCCESS"
        msg = f"[{provider.upper()}] RESPONSE ({status}) - {duration:.2f}s - Status: {status_code}\n"
        if error:
            msg += f"Error: {error}\n"
        else:
            msg += f"Response: {response}\n"
        msg += f"{'='*50}"
        self.api_logger.debug(msg)

# Global logger instance
logger = AppLogger()
