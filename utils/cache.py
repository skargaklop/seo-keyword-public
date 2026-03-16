"""
Scraping cache with TTL — avoids re-scraping the same URLs (improvement #6).
"""

import time
from typing import Optional, Dict, Any

from utils.logger import logger


class ScrapingCache:
    """Simple in-memory cache for scraped content with TTL support."""

    def __init__(self, ttl_seconds: int = 3600) -> None:
        """
        Args:
            ttl_seconds: Time-to-live for cache entries in seconds (default: 1 hour).
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._ttl: int = ttl_seconds

    def get(self, url: str) -> Optional[Any]:
        """Get cached content for a URL if it exists and hasn't expired."""
        entry = self._cache.get(url)
        if entry is None:
            return None

        if time.time() - entry["timestamp"] > self._ttl:
            del self._cache[url]
            logger.info(f"Cache expired for {url}")
            return None

        logger.info(f"Cache hit for {url}")
        return entry["data"]

    def set(self, url: str, data: Any) -> None:
        """Store content in cache for a URL."""
        self._cache[url] = {
            "data": data,
            "timestamp": time.time(),
        }
        logger.info(f"Cached content for {url}")

    def invalidate(self, url: str) -> None:
        """Remove a specific URL from cache."""
        self._cache.pop(url, None)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()

    @property
    def size(self) -> int:
        """Return number of cached entries."""
        return len(self._cache)


# Global cache instance
scraping_cache = ScrapingCache(ttl_seconds=3600)
