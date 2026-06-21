# MODULE_CONTRACT: utils/rate_limiter
# Purpose: Rate limiter for LLM API calls — prevents rate limit errors (improvement #16).
# Rationale: Keep the module boundary explicit for GRACE adoption and review.
# Dependencies: time, threading, typing, utils.logger
# Exports: RateLimiter, get_rate_limiter
# LINKS: requirements.xml#UC-001, development-plan.xml#MOD-001
# MODULE_MAP: utils/rate_limiter.py
# Public Functions: exported callables and classes defined in this module
# Private Helpers: internal helpers and private methods defined in this module
# Key Semantic Blocks: main workflow paths and state transitions in this module
# Critical Flows: preserve existing runtime behavior and integrations
# Verification: python -m py_compile, python -m ruff check ., python -m pytest -q
# CHANGE_SUMMARY: Added file-local module metadata and declaration contracts.

import time
import threading
from typing import Dict

from utils.logger import logger

# CLASS_CONTRACT: RateLimiter
# Purpose: Serialize API calls to respect a configured requests-per-minute budget.
# LINKS: requirements.xml#UC-001
class RateLimiter:
    # FUNCTION_CONTRACT: __init__
    # Purpose: Initialize the surrounding object state.
    # Input: requests_per_minute (int = 30)
    # Output: None
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def __init__(self, requests_per_minute: int = 30) -> None:
        self._rpm: int = requests_per_minute
        self._interval: float = 60.0 / requests_per_minute
        self._last_request_time: float = 0.0
        self._lock: threading.Lock = threading.Lock()
    # FUNCTION_CONTRACT: wait
    # Purpose: Implement the wait helper for this module.
    # Input: (none)
    # Output: None
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def wait(self) -> None:
        with self._lock:
            now: float = time.time()
            elapsed: float = now - self._last_request_time
            if elapsed < self._interval:
                sleep_time: float = self._interval - elapsed
                logger.info(f"Rate limiter: waiting {sleep_time:.2f}s before next request")
                time.sleep(sleep_time)
            self._last_request_time = time.time()
    # FUNCTION_CONTRACT: set_rpm
    # Purpose: Implement the set rpm helper for this module.
    # Input: requests_per_minute (int)
    # Output: None
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def set_rpm(self, requests_per_minute: int) -> None:
        with self._lock:
            self._rpm = requests_per_minute
            self._interval = 60.0 / requests_per_minute


# Per-provider rate limiters
_limiters: Dict[str, RateLimiter] = {}
# FUNCTION_CONTRACT: get_rate_limiter
# Purpose: Implement the get rate limiter helper for this module.
# Input: provider (str), default_rpm (int = 30)
# Output: RateLimiter
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def get_rate_limiter(provider: str, default_rpm: int = 30) -> RateLimiter:
    if provider not in _limiters:
        _limiters[provider] = RateLimiter(requests_per_minute=default_rpm)
    return _limiters[provider]
