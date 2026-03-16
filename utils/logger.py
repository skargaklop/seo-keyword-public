import logging
import os
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

# Create custom logger class to support api logging easier
class AppLogger:
    def __init__(self):
        self._setup_loggers()

    @staticmethod
    def _resolve_level(level_name: str, default: int) -> int:
        """Resolve string log level safely."""
        return getattr(logging, str(level_name).upper(), default)

    @staticmethod
    def _is_test_context() -> bool:
        """Detect pytest/test execution context."""
        return bool(os.getenv("PYTEST_CURRENT_TEST") or "pytest" in sys.modules)

    def refresh_config(self) -> None:
        """Reload logger handlers from current settings.yaml."""
        self._setup_loggers()

    def close_handlers(self) -> None:
        """Close current handlers so maintenance can delete/rotate log files safely."""
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

    def _setup_loggers(self):
        def _reset_handlers(target_logger: logging.Logger) -> None:
            """Reset handlers to avoid duplicate log lines on hot reload/rerun."""
            for handler in list(target_logger.handlers):
                target_logger.removeHandler(handler)
                try:
                    handler.close()
                except Exception:
                    pass

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

        class _TestContextFilter(logging.Filter):
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

    def info(self, message: str):
        self.main_logger.info(message)

    def warning(self, message: str):
        self.main_logger.warning(message)

    def error(self, message: str, exc_info=True):
        self.main_logger.error(message, exc_info=exc_info)

    def critical(self, message: str, exc_info=True):
        self.main_logger.critical(message, exc_info=exc_info)

    def log_api_request(self, provider: str, endpoint: str, payload: dict):
        """Log API request details."""
        msg = f"[{provider.upper()}] REQUEST to {endpoint}\nPayload: {payload}\n{'-'*50}"
        self.api_logger.debug(msg)

    def log_api_response(self, provider: str, duration: float, response: any, status_code: int = 200, error: str = None):
        """Log API response details."""
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
