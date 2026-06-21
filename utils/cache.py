# MODULE_CONTRACT: utils/cache
# Purpose: Scraping cache with TTL — avoids re-scraping the same URLs (improvement #6).
# Rationale: Keep the module boundary explicit for GRACE adoption and review.
# Dependencies: time, typing, utils.logger
# Exports: ScrapingCache, scraping_cache
# LINKS: requirements.xml#UC-001, development-plan.xml#MOD-001
# MODULE_MAP: utils/cache.py
# Public Functions: exported callables and classes defined in this module
# Private Helpers: internal helpers and private methods defined in this module
# Key Semantic Blocks: main workflow paths and state transitions in this module
# Critical Flows: preserve existing runtime behavior and integrations
# Verification: python -m py_compile, python -m ruff check ., python -m pytest -q
# CHANGE_SUMMARY: Added file-local module metadata and declaration contracts.

import time
from typing import Optional, Dict, Any

from utils.logger import logger

# CLASS_CONTRACT: ScrapingCache
# Purpose: Store scraped content in memory with per-entry TTL expiration.
# LINKS: requirements.xml#UC-001
class ScrapingCache:
    # FUNCTION_CONTRACT: __init__
    # Purpose: Initialize the surrounding object state.
    # Input: ttl_seconds (int = 3600)
    # Output: None
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._ttl: int = ttl_seconds
    # FUNCTION_CONTRACT: get
    # Purpose: Implement the get helper for this module.
    # Input: url (str)
    # Output: Optional[Any]
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def get(self, url: str) -> Optional[Any]:
        entry = self._cache.get(url)
        if entry is None:
            return None

        if time.time() - entry["timestamp"] > self._ttl:
            del self._cache[url]
            logger.info(f"Cache expired for {url}")
            return None

        logger.info(f"Cache hit for {url}")
        return entry["data"]
    # FUNCTION_CONTRACT: set
    # Purpose: Implement the set helper for this module.
    # Input: url (str), data (Any)
    # Output: None
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def set(self, url: str, data: Any) -> None:
        self._cache[url] = {
            "data": data,
            "timestamp": time.time(),
        }
        logger.info(f"Cached content for {url}")
    # FUNCTION_CONTRACT: invalidate
    # Purpose: Implement the invalidate helper for this module.
    # Input: url (str)
    # Output: None
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def invalidate(self, url: str) -> None:
        self._cache.pop(url, None)
    # FUNCTION_CONTRACT: clear
    # Purpose: Implement the clear helper for this module.
    # Input: (none)
    # Output: None
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def clear(self) -> None:
        self._cache.clear()
    # FUNCTION_CONTRACT: size
    # Purpose: Implement the size helper for this module.
    # Input: (none)
    # Output: int
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @property
    def size(self) -> int:
        return len(self._cache)


# Global cache instance
scraping_cache = ScrapingCache(ttl_seconds=3600)
