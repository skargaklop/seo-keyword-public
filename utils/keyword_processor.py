# MODULE_CONTRACT: utils/keyword_processor
# Purpose: Keyword processor module — cleans, filters, and deduplicates keywords.
# Rationale: Keep the module boundary explicit for GRACE adoption and review.
# Dependencies: re, typing, config.settings
# Exports: KeywordProcessor
# LINKS: requirements.xml#UC-001, development-plan.xml#MOD-001
# MODULE_MAP: utils/keyword_processor.py
# Public Functions: exported callables and classes defined in this module
# Private Helpers: internal helpers and private methods defined in this module
# Key Semantic Blocks: main workflow paths and state transitions in this module
# Critical Flows: preserve existing runtime behavior and integrations
# Verification: python -m py_compile, python -m ruff check ., python -m pytest -q
# CHANGE_SUMMARY: Added file-local module metadata and declaration contracts.

import re
from typing import List, Dict, Set

from config.settings import KEYWORDS_CONFIG

ALLOWED_LANGS: Set[str] = set(KEYWORDS_CONFIG.get("allowed_languages", ["ru", "uk"]))
MIN_LENGTH: int = KEYWORDS_CONFIG.get("min_keyword_length", 3)

# CLASS_CONTRACT: KeywordProcessor
# Purpose: Normalize, validate, and deduplicate keyword candidate lists.
# LINKS: requirements.xml#UC-001
class KeywordProcessor:
    # FUNCTION_CONTRACT: clean_keyword
    # Purpose: Implement the clean keyword helper for this module.
    # Input: keyword (str)
    # Output: str
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    def clean_keyword(keyword: str) -> str:
        cleaned: str = re.sub(r"[^\w\s-]", "", keyword)
        return " ".join(cleaned.lower().split())
    # FUNCTION_CONTRACT: is_valid_keyword
    # Purpose: Implement the is valid keyword helper for this module.
    # Input: keyword (str)
    # Output: bool
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    def is_valid_keyword(keyword: str) -> bool:
        if len(keyword) < MIN_LENGTH:
            return False

        # Check for cyrillic characters (simplest check for RU/UK)
        if not re.search(r"[\u0400-\u04FF]", keyword):
            return False

        return True
    # FUNCTION_CONTRACT: process_keywords
    # Purpose: Implement the process keywords helper for this module.
    # Input: raw_keywords (List[str])
    # Output: List[str]
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    def process_keywords(raw_keywords: List[str]) -> List[str]:
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
    # FUNCTION_CONTRACT: deduplicate_across_sources
    # Purpose: Implement the deduplicate across sources helper for this module.
    # Input: source_keywords (Dict[str, List[str]])
    # Output: Dict[str, List[str]]
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    def deduplicate_across_sources(
        source_keywords: Dict[str, List[str]],
    ) -> Dict[str, List[str]]:
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
