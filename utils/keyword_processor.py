"""
Keyword processor module — cleans, filters, and deduplicates keywords.
Type hints added (improvement #5).
"""

import re
from typing import List, Dict, Set

from config.settings import KEYWORDS_CONFIG

ALLOWED_LANGS: Set[str] = set(KEYWORDS_CONFIG.get("allowed_languages", ["ru", "uk"]))
MIN_LENGTH: int = KEYWORDS_CONFIG.get("min_keyword_length", 3)


class KeywordProcessor:
    @staticmethod
    def clean_keyword(keyword: str) -> str:
        """Normalize keyword: lowercase, remove extra spaces/symbols."""
        cleaned: str = re.sub(r"[^\w\s-]", "", keyword)
        return " ".join(cleaned.lower().split())

    @staticmethod
    def is_valid_keyword(keyword: str) -> bool:
        """Check if keyword meets criteria (length, language)."""
        if len(keyword) < MIN_LENGTH:
            return False

        # Check for cyrillic characters (simplest check for RU/UK)
        if not re.search(r"[\u0400-\u04FF]", keyword):
            return False

        return True

    @staticmethod
    def process_keywords(raw_keywords: List[str]) -> List[str]:
        """
        Process a list of raw keywords: clean, filter, deduplicate.
        Returns unique list.
        """
        processed: List[str] = []
        seen: Set[str] = set()

        for kw in raw_keywords:
            cleaned: str = KeywordProcessor.clean_keyword(kw)

            if (
                cleaned
                and cleaned not in seen
                and KeywordProcessor.is_valid_keyword(cleaned)
            ):
                seen.add(cleaned)
                processed.append(cleaned)

        return processed

    @staticmethod
    def deduplicate_across_sources(
        source_keywords: Dict[str, List[str]],
    ) -> Dict[str, List[str]]:
        """
        Deduplicate keywords across multiple sources.
        Heuristic: Keep the keyword for the FIRST source it appeared in.

        Args:
            source_keywords: Dict {url: [keywords]}

        Returns:
            Dict {url: [unique_keywords]} (keywords removed if they appeared in previous URLs)
        """
        global_seen: Set[str] = set()
        result: Dict[str, List[str]] = {}

        for url, keywords in source_keywords.items():
            unique_for_url: List[str] = []
            for kw in keywords:
                if kw not in global_seen:
                    global_seen.add(kw)
                    unique_for_url.append(kw)
            result[url] = unique_for_url

        return result
