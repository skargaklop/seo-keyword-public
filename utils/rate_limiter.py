"""
Rate limiter for LLM API calls — prevents rate limit errors (improvement #16).
"""

import time
import threading
from typing import Dict

from utils.logger import logger


class RateLimiter:
    """Token-bucket style rate limiter for API calls."""

    def __init__(self, requests_per_minute: int = 30) -> None:
        """
        Args:
            requests_per_minute: Maximum number of requests allowed per minute.
        """
        self._rpm: int = requests_per_minute
        self._interval: float = 60.0 / requests_per_minute
        self._last_request_time: float = 0.0
        self._lock: threading.Lock = threading.Lock()

    def wait(self) -> None:
        """Block until the next request is allowed."""
        with self._lock:
            now: float = time.time()
            elapsed: float = now - self._last_request_time
            if elapsed < self._interval:
                sleep_time: float = self._interval - elapsed
                logger.info(f"Rate limiter: waiting {sleep_time:.2f}s before next request")
                time.sleep(sleep_time)
            self._last_request_time = time.time()

    def set_rpm(self, requests_per_minute: int) -> None:
        """Update the rate limit."""
        with self._lock:
            self._rpm = requests_per_minute
            self._interval = 60.0 / requests_per_minute


# Per-provider rate limiters
_limiters: Dict[str, RateLimiter] = {}


def get_rate_limiter(provider: str, default_rpm: int = 30) -> RateLimiter:
    """Get or create a rate limiter for a specific provider."""
    if provider not in _limiters:
        _limiters[provider] = RateLimiter(requests_per_minute=default_rpm)
    return _limiters[provider]
