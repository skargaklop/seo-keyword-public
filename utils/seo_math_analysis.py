# MODULE_CONTRACT: utils/seo_math_analysis
# Purpose: Pure deterministic mathematical SEO analysis engine with memoization and no external ML dependencies
# Rationale: Provides n-gram ranking, TF-IDF scoring, BM25F field-weighted scoring, co-occurrence analysis, intent detection, and content gap analysis for SERP results and generated SEO text
# Dependencies: functools, re, typing, collections, dataclasses, math; OPTIONAL pymorphy3 (ru/uk lemmatization) and simplemma (Latin lemmatization) — both lazily imported inside factory functions, never required at startup and absent from requirements.txt
# Exports: TextSource, NgramScore, TfidfTermScore, CooccurrenceTermScore, IntentSignal, ContentGapResult, ElementQualityScore, BM25FScore, FieldWeightedProfile, FieldStats, DomainMetrics, extract_ngrams, compute_tfidf, compute_cooccurrence_terms, analyze_intent, analyze_content_gap, score_generated_text, compute_bm25f, build_field_weighted_profile, compute_domain_metrics, lemmatize_token, LemmatizerDependencyStatus, check_lemmatizer_dependencies, build_lemmatizer_install_command, get_lemmatizer_problem_dependencies
# LINKS: PLAN 08-02 Tasks 1-4, PLAN 10-02 Task 2, requirements.xml#MATH-08-01, requirements.xml#MATH-08-02, requirements.xml#MATH-08-03, requirements.xml#MATH-08-04, requirements.xml#MATH-10-01, requirements.xml#MATH-10-02, requirements.xml#GENQA-08-01, requirements.xml#GENQA-08-02
# MODULE_MAP: utils/seo_math_analysis.py
# Public Functions: extract_ngrams, compute_tfidf, compute_cooccurrence_terms, analyze_intent, analyze_content_gap, score_generated_text, compute_bm25f, build_field_weighted_profile, compute_domain_metrics, lemmatize_token, check_lemmatizer_dependencies, build_lemmatizer_install_command, get_lemmatizer_problem_dependencies
# Private Helpers: _tokenize_text, _normalize_for_hashing, _build_cooccurrence_matrix, _compute_jaccard_similarity, _compute_cosine_similarity, _parse_generated_sections, _score_element, _calculate_keyword_density, _check_forbidden_phrases, _get_field_b_param, _compute_field_length_normalization, _compute_bm25f_idf, _is_cyrillic, _get_pymorphy_ru, _get_pymorphy_uk, _get_simplemma
# Key Semantic Blocks: block_math_tokenize_corpus, block_math_ngram_rank, block_math_tfidf_score, block_math_bm25f_scoring, block_math_cooccurrence_terms, block_math_generation_quality, block_math_cache_memoization, block_math_lemmatizer_dependency_check
# Critical Flows: SERP results -> tokenization -> n-gram/TF-IDF/BM25F/cooccurrence analysis -> intent/gap scoring; Generated text -> parsing -> element-specific quality scoring with optional BM25F coverage
# Verification: python -m py_compile, python -m ruff check ., python -m pytest -q
# CHANGE_SUMMARY: Initial module with deterministic mathematical analysis; pure Python implementation with memoization; no external ML dependencies; Phase 10: added BM25F with BM25+ IDF smoothing (+1 term); Inverted _stem_matches so strip_suffixes=True is the BROAD mode (real lemmatization) and False is the STRICT mode (exact equality); replaced regex suffix hack with lazy pymorphy3/simplemma lemmatizer (optional deps, lazy-loaded, graceful identity fallback); added LemmatizerDependencyStatus + check_lemmatizer_dependencies/build_lemmatizer_install_command/get_lemmatizer_problem_dependencies for the UI dependency table under the lemmatization checkbox

from __future__ import annotations

import functools
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

# Optional cache import (available in Phase 10)
try:
    import importlib.util
    CACHE_AVAILABLE = importlib.util.find_spec("utils.request_cache") is not None
except ImportError:
    import importlib.util  # type: ignore[no-redef]
    CACHE_AVAILABLE = False

if TYPE_CHECKING:
    import pandas as pd


# block_math_tokenize_corpus: Tokenization and text normalization for mathematical analysis
# Semantic block: Handles text preprocessing, tokenization, stopword filtering, and optional suffix stripping
# Ensures consistent token representation across all analysis functions


# FUNCTION_CONTRACT: _normalize_for_hashing
# Purpose: Convert list of TextSource to hashable input for memoization cache key
# Input: corpus (List[TextSource])
# Output: Tuple[Tuple[str, str, float], ...] — hashable representation
# Side Effects: (none)
# Business Rules: Converts to tuple of tuples for hashing; order-insensitive for cache hits
# Failure Modes: never raises
# LINKS: PLAN 08-02 Task 2
def _normalize_for_hashing(corpus: List[TextSource]) -> tuple[tuple[str, str, float], ...]:
    return tuple((item.text, item.field, item.weight) for item in corpus)


# FUNCTION_CONTRACT: _tokenize_text
# Purpose: Tokenize input text into normalized terms with stopword filtering and optional real lemmatization
# Input: text (str), strip_suffixes (bool), stopwords (Set[str])
# Output: List[str]
# Side Effects: When strip_suffixes=True, lazily constructs pymorphy3/simplemma lemmatizers (cached); never imports them at module top level
# Business Rules: Lowercases, strips HTML tags, preserves Cyrillic/Latin/digits/hyphens, filters stopwords; when strip_suffixes=True each token is passed through lemmatize_token (real dictionary lemmatization), otherwise tokens are kept verbatim; degrades to no-lemmatization when the optional libs are absent
# Failure Modes: never raises; returns empty list for empty/None input
# LINKS: PLAN 08-02 Task 2
def _tokenize_text(text: str, strip_suffixes: bool = False, stopwords: Optional[Set[str]] = None) -> List[str]:
    if not text:
        return []

    if stopwords is None:
        stopwords = _get_default_stopwords()

    # Strip HTML tags
    text = re.sub(r"<[^>]+>", " ", text)

    # Lowercase
    text = text.lower()

    # Preserve Cyrillic, Latin, digits, hyphens inside words
    # Token pattern: word chars including hyphens (but not standalone hyphens)
    tokens = re.findall(r"[a-zа-яіїєґё0-9]+(?:-[a-zа-яіїєґё0-9]+)*", text)

    if strip_suffixes:
        # BROAD mode: collapse each token to its dictionary lemma via the real
        # lemmatizer (pymorphy3 for Cyrillic, simplemma for Latin). When the
        # optional libs are absent lemmatize_token returns the token unchanged,
        # so this degrades gracefully to "no morphology collapsing".
        tokens = [lemmatize_token(token) for token in tokens]

    # Filter stopwords and empty tokens
    return [t for t in tokens if t and t not in stopwords]


# FUNCTION_CONTRACT: _strip_ru_uk_suffix
# Purpose: Remove common Russian/Ukrainian suffixes for keyword grouping (optional feature)
# Input: token (str)
# Output: str
# Side Effects: (none)
# Business Rules: Strips common RU/UK suffix endings (several common patterns) if token length > 4
# Failure Modes: never raises; returns original token if no suffix match
# LINKS: PLAN 08-02 Task 2
def _strip_ru_uk_suffix(token: str) -> str:
    if len(token) <= 4:
        return token

    # Common RU/UK suffix endings
    suffixes = (
        "ий", "ия", "ое", "ый", "ая", "ой",
        "ем", "их", "ых", "ому", "ему",
        "ого", "его", "ому", "ими", "ами",
        "сть", "ность", "тель",
    )

    for suffix in suffixes:
        if token.endswith(suffix):
            return token[:-len(suffix)]

    return token


# FUNCTION_CONTRACT: _is_cyrillic
# Purpose: Detect whether a token contains any Cyrillic character (ru/uk/mk/bg/etc.)
# Input: token (str)
# Output: bool — True if any character lies in the Cyrillic Unicode block
# Side Effects: (none)
# Business Rules: Covers the contiguous Cyrillic range U+0400 "Ѐ" through U+04FF "ӿ"; a single Cyrillic char is enough to route the token to pymorphy3 rather than simplemma
# Failure Modes: never raises; returns False for empty/None-like input
# LINKS: PLAN 08-02 Task 2
def _is_cyrillic(token: str) -> bool:
    return any("Ѐ" <= ch <= "ӿ" for ch in token)


# FUNCTION_CONTRACT: _get_pymorphy_ru
# Purpose: Lazily build and cache a pymorphy3 MorphAnalyzer for Russian
# Input: (none)
# Output: Optional[pymorphy3.MorphAnalyzer] — the analyzer, or None if pymorphy3 is not importable / fails to construct
# Side Effects: On first successful call imports pymorphy3 and constructs a ~15MB analyzer (cached via lru_cache so it happens at most once per process); never imports at module top level
# Business Rules: Pure lazy factory; pymorphy3 is an OPTIONAL dependency and must be absent from requirements.txt; the Russian dict auto-installs with pymorphy3
# Failure Modes: returns None on ImportError or ANY construction error; never raises
# LINKS: PLAN 08-02 Task 2
@functools.lru_cache(maxsize=1)
def _get_pymorphy_ru():
    try:
        import pymorphy3
        return pymorphy3.MorphAnalyzer()
    except Exception:
        return None


# FUNCTION_CONTRACT: _get_pymorphy_uk
# Purpose: Lazily build and cache a pymorphy3 MorphAnalyzer for Ukrainian
# Input: (none)
# Output: Optional[pymorphy3.MorphAnalyzer] — the analyzer, or None if pymorphy3 or the uk dict is not importable / fails to construct
# Side Effects: On first successful call imports pymorphy3 and constructs the Ukrainian analyzer (cached); never imports at module top level
# Business Rules: Pure lazy factory; pymorphy3 + pymorphy3-dicts-uk are OPTIONAL dependencies; the uk analyzer requires the separate uk dict package
# Failure Modes: returns None on ImportError or ANY construction error; never raises
# LINKS: PLAN 08-02 Task 2
@functools.lru_cache(maxsize=1)
def _get_pymorphy_uk():
    try:
        import pymorphy3
        return pymorphy3.MorphAnalyzer(lang="uk")
    except Exception:
        return None


# FUNCTION_CONTRACT: _get_simplemma
# Purpose: Lazily build and cache a simplemma Lemmatizer for Latin/other languages
# Input: (none)
# Output: Optional[simplemma.Lemmatizer] — the lemmatizer, or None if simplemma is not importable / fails to construct
# Side Effects: On first successful call imports simplemma and constructs the lemmatizer with a small dictionary cache (cached); never imports at module top level
# Business Rules: Pure lazy factory; simplemma is an OPTIONAL dependency and must be absent from requirements.txt; constructed with DefaultStrategy + DefaultDictionaryFactory(cache_max_size=4)
# Failure Modes: returns None on ImportError or ANY construction error; never raises
# LINKS: PLAN 08-02 Task 2
@functools.lru_cache(maxsize=1)
def _get_simplemma():
    try:
        from simplemma import Lemmatizer
        from simplemma.strategies import DefaultStrategy
        from simplemma.strategies.dictionaries import DefaultDictionaryFactory
        return Lemmatizer(lemmatization_strategy=DefaultStrategy(
            dictionary_factory=DefaultDictionaryFactory(cache_max_size=4)))
    except Exception:
        return None


# FUNCTION_CONTRACT: lemmatize_token
# Purpose: Reduce a token to its dictionary lemma using real morphology, routing by script (Cyrillic -> pymorphy3 ru then uk; Latin/other -> simplemma en)
# Input: token (str)
# Output: str — the lowercased lemma, or the original token unchanged when no lemmatizer is available or any error occurs
# Side Effects: Triggers lazy construction of the pymorphy3/simplemma singletons on first use (cached for the process); zero cost when the libs are absent
# Business Rules: Cyrillic tokens try Russian pymorphy3 first, then Ukrainian if Russian yields no parse; Latin/other tokens use simplemma with lang="en"; result is lowercased; on ANY exception or when all lemmatizers are None/unavailable the original token is returned verbatim (graceful identity fallback)
# Failure Modes: never raises; returns the input token unchanged when libs are missing or parsing fails
# LINKS: PLAN 08-02 Task 2
def lemmatize_token(token: str) -> str:
    try:
        if _is_cyrillic(token):
            morph_ru = _get_pymorphy_ru()
            if morph_ru is not None:
                parses = morph_ru.parse(token)
                if parses:
                    return parses[0].normal_form.lower()
            # Russian had no parse (OOV) or pymorphy3 is absent: try the uk dict.
            morph_uk = _get_pymorphy_uk()
            if morph_uk is not None:
                parses = morph_uk.parse(token)
                if parses:
                    return parses[0].normal_form.lower()
            return token.lower()
        # Latin / other scripts -> simplemma.
        lem = _get_simplemma()
        if lem is not None:
            return lem.lemmatize(token, lang="en").lower()
        return token.lower()
    except Exception:
        return token


# block_math_lemmatizer_dependency_check: Detect the optional lemmatizer packages so the
# UI can mirror the browser-scraper dependency table. Pure detection only — never installs.
# Semantic block: Reports per-package install status and builds the matching pip command.

# CLASS_CONTRACT: LemmatizerDependencyStatus
# Purpose: Represent installation status of the optional lemmatizer dependencies
# Input: (none)
# Output: Enum with available/missing/unknown/unusable values
# Side Effects: (none)
# Business Rules: Mirrors utils.browser_scraper.DependencyStatus by value string so the UI status-label map and tests interoperate; defined locally to avoid importing browser_scraper (keeps this module's import graph light)
# Failure Modes: (none — plain enum)
# LINKS: PLAN 08-02 Task 2
class LemmatizerDependencyStatus(Enum):
    AVAILABLE = "available"
    MISSING = "missing"
    UNKNOWN = "unknown"
    UNUSABLE = "unusable"


# Map PyPI package name -> importable module name. pymorphy3-dicts-uk ships the
# underscored module pymorphy3_dicts_uk (the hyphenated form is not importable).
LEMMATIZER_DEPENDENCY_PACKAGES: tuple[str, ...] = (
    "pymorphy3",
    "pymorphy3-dicts-uk",
    "simplemma",
)

# PyPI name -> (import module name, required attribute tuple). Empty attrs means
# presence is sufficient; the uk dict is a data-only package with no public API.
_LEMMATIZER_DEPENDENCY_MODULES: Dict[str, tuple[str, tuple[str, ...]]] = {
    "pymorphy3": ("pymorphy3", ("MorphAnalyzer",)),
    "pymorphy3-dicts-uk": ("pymorphy3_dicts_uk", ()),
    "simplemma": ("simplemma", ("Lemmatizer",)),
}


# FUNCTION_CONTRACT: _check_lemmatizer_dependency
# Purpose: Check whether a single optional lemmatizer package is importable with its required API
# Input: pypi_name (str) — the pip name, looked up in _LEMMATIZER_DEPENDENCY_MODULES
# Output: LemmatizerDependencyStatus
# Side Effects: (none) — uses importlib.util.find_spec for presence and importlib.import_module only when attribute validation is required
# Business Rules: MISSING when find_spec returns None; AVAILABLE when present with all required attrs; UNUSABLE when present but missing a required attr or import fails; UNKNOWN on unexpected errors
# Failure Modes: never raises; returns UNKNOWN on any unexpected exception
# LINKS: PLAN 08-02 Task 2
def _check_lemmatizer_dependency(pypi_name: str) -> LemmatizerDependencyStatus:
    module_name, required_attrs = _LEMMATIZER_DEPENDENCY_MODULES.get(
        pypi_name, (pypi_name.replace("-", "_"), ())
    )
    try:
        spec = importlib.util.find_spec(module_name)
        if spec is None:
            return LemmatizerDependencyStatus.MISSING
        if not required_attrs:
            return LemmatizerDependencyStatus.AVAILABLE
        module = importlib.import_module(module_name)
        if all(hasattr(module, attr) for attr in required_attrs):
            return LemmatizerDependencyStatus.AVAILABLE
        return LemmatizerDependencyStatus.UNUSABLE
    except ImportError:
        return LemmatizerDependencyStatus.UNUSABLE
    except Exception:
        return LemmatizerDependencyStatus.UNKNOWN


# FUNCTION_CONTRACT: check_lemmatizer_dependencies
# Purpose: Report the install status of every optional lemmatizer package
# Input: (none)
# Output: Dict[str, LemmatizerDependencyStatus] keyed by IMPORT module name (pymorphy3, pymorphy3_dicts_uk, simplemma) so the UI can map to display labels
# Side Effects: (none) — delegates to _check_lemmatizer_dependency
# Business Rules: Iterates LEMMATIZER_DEPENDENCY_PACKAGES in fixed order; keys are import module names, not PyPI names (uk dict -> pymorphy3_dicts_uk)
# Failure Modes: never raises; individual checks degrade to UNKNOWN
# LINKS: PLAN 08-02 Task 2
def check_lemmatizer_dependencies() -> Dict[str, LemmatizerDependencyStatus]:
    result: Dict[str, LemmatizerDependencyStatus] = {}
    for pypi_name in LEMMATIZER_DEPENDENCY_PACKAGES:
        module_name = _LEMMATIZER_DEPENDENCY_MODULES[pypi_name][0]
        result[module_name] = _check_lemmatizer_dependency(pypi_name)
    return result


# FUNCTION_CONTRACT: build_lemmatizer_install_command
# Purpose: Build the pip install/upgrade command for the optional lemmatizer packages
# Input: scope (str) — "project" (default) installs into the current interpreter; "global" targets the per-user site-packages
# Output: str — the full python -m pip command
# Side Effects: (none)
# Business Rules: scope="global" adds the --user flag; packages joined in the canonical order pymorphy3 pymorphy3-dicts-uk simplemma; mirrors utils.browser_scraper.build_optional_dependency_install_command
# Failure Modes: never raises
# LINKS: PLAN 08-02 Task 2
def build_lemmatizer_install_command(scope: str = "project") -> str:
    packages = " ".join(LEMMATIZER_DEPENDENCY_PACKAGES)
    if scope == "global":
        return f"python -m pip install --user {packages}"
    return f"python -m pip install {packages}"


# FUNCTION_CONTRACT: get_lemmatizer_problem_dependencies
# Purpose: Return the subset of lemmatizer packages that are not fully available (missing/unknown/unusable)
# Input: dependencies (Optional[Dict[str, LemmatizerDependencyStatus]]) — when None, check_lemmatizer_dependencies() is called
# Output: Dict[str, LemmatizerDependencyStatus] containing only non-AVAILABLE entries
# Side Effects: When dependencies is None, runs a live detection pass (importlib probes)
# Business Rules: AVAILABLE entries are filtered out so the UI only warns when user action is needed
# Failure Modes: never raises; an empty dict means everything is installed and usable
# LINKS: PLAN 08-02 Task 2
def get_lemmatizer_problem_dependencies(
    dependencies: Optional[Dict[str, LemmatizerDependencyStatus]] = None,
) -> Dict[str, LemmatizerDependencyStatus]:
    deps = dependencies if dependencies is not None else check_lemmatizer_dependencies()
    return {
        name: status
        for name, status in deps.items()
        if status != LemmatizerDependencyStatus.AVAILABLE
    }


# FUNCTION_CONTRACT: _get_default_stopwords
# Purpose: Provide default stopwords for Russian, Ukrainian, and English
# Input: (none)
# Output: Set[str]
# Side Effects: (none)
# Business Rules: Returns common stopwords for ru/uk/en languages
# Failure Modes: never raises
# LINKS: PLAN 08-02 Task 2
@functools.lru_cache(maxsize=1)
def _get_default_stopwords() -> Set[str]:
    return {
        # Russian
        "и", "в", "во", "не", "что", "он", "на", "я", "с", "со", "как", "а",
        "то", "все", "она", "так", "его", "но", "да", "ты", "к", "у", "же",
        "вы", "за", "бы", "по", "только", "ее", "мне", "было", "вот", "от",
        "меня", "еще", "нет", "о", "из", "ему", "теперь", "когда", "ничего",
        "ей", "при", "можно", "хоть", "были", "вы", "вас", "нас", "могу",
        "который", "это", "этого", "этом", "для", "или", "чтобы", "под",
        # Ukrainian
        "і", "в", "во", "не", "що", "він", "на", "я", "з", "со", "як",
        "а", "то", "все", "вона", "так", "його", "але", "да", "ти", "к",
        "у", "же", "ви", "за", "були", "по", "тільки", "її", "мені", "було",
        "ось", "від", "мене", "ще", "немає", "о", "з", "йому", "тепер",
        "коли", "нічого", "їй", "при", "можна", "хоча", "були", "вас",
        "нас", "можу", "який", "це", "цього", "цьому", "для", "аби",
        # English
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
        "for", "of", "with", "by", "from", "up", "about", "into", "over",
        "after", "is", "it", "this", "that", "be", "are", "was", "were",
        "have", "has", "had", "do", "does", "did", "can", "could", "will",
        "would", "should", "may", "might", "must", "shall", "you", "your",
        "we", "they", "them", "their", "our", "us", "i", "me", "my", "he",
        "she", "him", "her", "his", "its", "who", "which", "what", "when",
        "where", "why", "how", "all", "each", "every", "both", "few", "more",
        "most", "other", "some", "such", "no", "nor", "not", "only", "own",
        "same", "so", "than", "too", "very",
    }


# block_math_bm25f_scoring: BM25F field-weighted scoring with BM25+ IDF smoothing
# Semantic block: Computes BM25F scores with field-length normalization and weighted aggregation
# Uses BM25+ variant: IDF = log((N - df + 0.5) / (df + 0.5) + 1) to prevent negative IDF


# FUNCTION_CONTRACT: _get_field_b_param
# Purpose: Get length normalization (b) parameter for a specific field
# Input: field (str), field_b (Dict[str, float])
# Output: float
# Side Effects: (none)
# Business Rules: Returns field-specific b parameter; defaults to 0.75 (body) if not found
# Failure Modes: never raises
# LINKS: PLAN 10-02 Task 2
def _get_field_b_param(field: str, field_b: Dict[str, float]) -> float:
    if field in field_b:
        return field_b[field]

    # Default b parameters by field type
    if "title" in field.lower():
        return 0.5  # Titles are shorter, less normalization
    elif "snippet" in field.lower() or "description" in field.lower():
        return 0.6  # Medium normalization for snippets
    else:
        return 0.75  # Standard normalization for body text


# FUNCTION_CONTRACT: _compute_field_length_normalization
# Purpose: Compute field length normalization factor for BM25F
# Input: field_len (int), avg_field_len (float), b_param (float)
# Output: float
# Side Effects: (none)
# Business Rules: Computes 1 / ((1 - b) + b * field_len / avg_field_len); returns 1.0 if avg_field_len is 0
# Failure Modes: never raises
# LINKS: PLAN 10-02 Task 2
def _compute_field_length_normalization(
    field_len: int,
    avg_field_len: float,
    b_param: float
) -> float:
    """Compute field length normalization factor.

    Formula: 1 / ((1 - b) + b * (field_len / avg_field_len))

    Args:
        field_len: Length of field in tokens
        avg_field_len: Average length of field across corpus
        b_param: Length normalization parameter (0-1)

    Returns:
        Normalization factor (prevents long documents from dominating)
    """
    if avg_field_len == 0:
        return 1.0

    ratio = field_len / avg_field_len
    denominator = (1 - b_param) + (b_param * ratio)
    return 1.0 / denominator if denominator > 0 else 1.0


# FUNCTION_CONTRACT: _compute_bm25f_idf
# Purpose: Compute BM25+ IDF for a term (smoothed variant)
# Input: doc_freq (int), corpus_size (int)
# Output: float
# Side Effects: (none)
# Business Rules: Uses BM25+ formula: log((N - df + 0.5) / (df + 0.5) + 1); prevents negative IDF
# Failure Modes: never raises
# LINKS: PLAN 10-02 Task 2
def _compute_bm25f_idf(doc_freq: int, corpus_size: int) -> float:
    if doc_freq == 0:
        return 0.0

    if doc_freq >= corpus_size:
        return 0.0

    # BM25+ IDF formula with +1 smoothing
    numerator = corpus_size - doc_freq + 0.5
    denominator = doc_freq + 0.5
    return math.log(numerator / denominator + 1.0)


# FUNCTION_CONTRACT: build_field_weighted_profile
# Purpose: Build field statistics and weights profile for BM25F scoring
# Input: corpus (List[TextSource]), settings (Optional[Dict])
# Output: FieldWeightedProfile
# Side Effects: (none)
# Business Rules: Computes field lengths, averages, and weights; uses defaults from settings if not provided
# Failure Modes: Returns empty profile with defaults for empty corpus
# LINKS: PLAN 10-02 Task 2
def build_field_weighted_profile(
    corpus: List[TextSource],
    settings: Optional[Dict] = None
) -> FieldWeightedProfile:
    """Build field-weighted profile for BM25F scoring.

    Computes field statistics (lengths, averages) and combines with
    configured weights for BM25F scoring.

    Args:
        corpus: List of TextSource documents
        settings: Optional settings dict with field_weights and bm25f_params

    Returns:
        FieldWeightedProfile with computed statistics and weights
    """
    if settings is None:
        settings = {}

    # Extract field weights from settings or use defaults
    default_weights = {
        "serp_title": 3.0,
        "page_title": 3.0,
        "h1": 2.5,
        "meta_description": 1.5,
        "serp_snippet": 1.5,
        "related_searches": 1.2,
        "people_also_ask": 1.1,
        "trends_related": 1.2,
        "body_text": 1.0,
        "anchor_text": 1.4,
    }

    seo_math_config = settings.get("seo_math", {})
    configured_weights = seo_math_config.get("field_weights", {})
    field_weights = {**default_weights, **configured_weights}

    # Extract b parameters from settings or use defaults
    bm25f_params = seo_math_config.get("bm25f_params", {})
    configured_b = {
        "body": bm25f_params.get("b_body", 0.75),
        "title": bm25f_params.get("b_title", 0.5),
        "snippet": bm25f_params.get("b_snippet", 0.6),
    }

    # Map field types to b parameters
    field_b_params: Dict[str, float] = {}
    for field in field_weights.keys():
        field_b_params[field] = _get_field_b_param(field, configured_b)

    # Compute field statistics
    stopwords = _get_default_stopwords()
    field_lengths: Dict[str, List[int]] = defaultdict(list)
    field_token_counts: Dict[str, int] = defaultdict(int)

    for doc in corpus:
        tokens = _tokenize_text(doc.text, False, stopwords)
        field = doc.field
        field_lengths[field].append(len(tokens))
        field_token_counts[field] += len(tokens)

    # Build field stats
    field_stats: Dict[str, FieldStats] = {}
    avg_field_lengths: Dict[str, float] = {}

    for field, lengths in field_lengths.items():
        total_len = sum(lengths)
        avg_len = total_len / len(lengths) if lengths else 0
        field_stats[field] = FieldStats(
            field=field,
            total_length=total_len,
            avg_length=avg_len,
            doc_count=len(lengths)
        )
        avg_field_lengths[field] = avg_len

    # Algorithm version for cache invalidation
    algorithm_version = "bm25f_v1"

    return FieldWeightedProfile(
        field_weights=field_weights,
        field_b_params=field_b_params,
        field_stats=field_stats,
        avg_field_lengths=avg_field_lengths,
        corpus_size=len(corpus),
        algorithm_version=algorithm_version,
    )


# FUNCTION_CONTRACT: compute_bm25f
# Purpose: Compute BM25F scores for documents against query terms
# Input: corpus_hash (tuple), query_terms (List[str]), field_weights (Dict), field_b (Dict), k1 (float), top_n (int), strip_suffixes (bool)
# Output: List[BM25FScore]
# Side Effects: Uses memoization cache keyed by corpus hash, query terms, and parameters
# Business Rules: Computes BM25F with field-length normalization, weighted aggregation, and BM25+ IDF; returns top_n results
# Failure Modes: Returns empty list for empty corpus or query terms
# LINKS: PLAN 10-02 Task 2
@functools.lru_cache(maxsize=128)
def compute_bm25f(
    corpus_hash: tuple[tuple[str, str, float], ...],
    query_terms: tuple[str, ...],
    field_weights: tuple[tuple[str, float], ...],
    field_b: tuple[tuple[str, float], ...],
    k1: float = 1.2,
    top_n: int = 100,
    strip_suffixes: bool = False,
) -> List[BM25FScore]:
    """Compute BM25F scores for documents against query terms.

    BM25F extends BM25 with field-level scoring:
    - Each field is normalized separately using field-specific b parameter
    - Field contributions are weighted and summed
    - Uses BM25+ IDF smoothing: log((N - df + 0.5) / (df + 0.5) + 1)

    Formula per document and term:
    1. For each field f:
       field_tf_f = count(term, field_f)
       norm_f = 1 / ((1 - b_f) + b_f * len(field_f) / avg_len_f)
       weighted_tf_f = field_tf_f * norm_f * weight_f
    2. Sum across fields: total_weighted_tf = sum(weighted_tf_f for all fields)
    3. Apply BM25 saturation: tf_component = total_weighted_tf / (k1 + total_weighted_tf)
    4. Multiply by IDF: score = tf_component * idf(term)

    Args:
        corpus_hash: Hashable representation of TextSource corpus
        query_terms: Tuple of query terms to score against
        field_weights: Tuple of (field, weight) pairs for memoization
        field_b: Tuple of (field, b_param) pairs for memoization
        k1: BM25 saturation parameter (default 1.2)
        top_n: Maximum number of results to return
        strip_suffixes: Whether to apply suffix stripping

    Returns:
        List of BM25FScore sorted by score desc, query_coverage desc, doc_id asc
    """
    # Reconstruct corpus from hash
    corpus = [TextSource(text=t, field=f, weight=w) for t, f, w in corpus_hash]

    # Reconstruct dicts from tuples
    field_weights_dict = dict(field_weights)
    field_b_dict = dict(field_b)

    if not corpus or not query_terms:
        return []

    stopwords = _get_default_stopwords()
    N = len(corpus)

    # Tokenize all documents and build field representations
    doc_fields: List[Dict[str, List[str]]] = []
    for doc in corpus:
        tokens = _tokenize_text(doc.text, strip_suffixes, stopwords)
        doc_fields.append({doc.field: tokens})

    # Compute document frequencies for each query term across all fields
    doc_freqs: Dict[str, int] = defaultdict(int)
    for term in query_terms:
        term_lower = term.lower()
        for fields in doc_fields:
            for field_tokens in fields.values():
                if term_lower in field_tokens:
                    doc_freqs[term] += 1
                    break  # Count once per document

    # Pre-compute IDFs using BM25+ formula
    idfs: Dict[str, float] = {}
    for term in query_terms:
        df = doc_freqs.get(term.lower(), 0)
        idfs[term] = _compute_bm25f_idf(df, N)

    # Compute average field lengths
    field_lengths: Dict[str, List[int]] = defaultdict(list)
    for doc_idx, doc in enumerate(corpus):
        tokens = _tokenize_text(doc.text, strip_suffixes, stopwords)
        field_lengths[doc.field].append(len(tokens))

    avg_field_lengths: Dict[str, float] = {}
    for field, lengths in field_lengths.items():
        avg_field_lengths[field] = sum(lengths) / len(lengths) if lengths else 1.0

    # Score each document
    scores: List[BM25FScore] = []

    for doc_idx, doc in enumerate(corpus):
        doc_tokens = _tokenize_text(doc.text, strip_suffixes, stopwords)
        doc_field = doc.field
        doc_field_len = len(doc_tokens)
        avg_len = avg_field_lengths.get(doc_field, 1.0)
        b_param = field_b_dict.get(doc_field, 0.75)
        field_weight = field_weights_dict.get(doc_field, 1.0)

        # Compute term scores
        term_scores: Dict[str, float] = {}
        field_contributions: Dict[str, float] = defaultdict(float)
        matched_terms: List[str] = []

        for term in query_terms:
            term_lower = term.lower()
            if term_lower not in doc_tokens:
                continue

            # Raw term frequency in this document
            tf = sum(1 for t in doc_tokens if t == term_lower)

            # Field length normalization
            norm_factor = _compute_field_length_normalization(
                doc_field_len, avg_len, b_param
            )

            # Weighted term frequency
            weighted_tf = tf * norm_factor * field_weight

            # BM25 saturation
            tf_component = weighted_tf / (k1 + weighted_tf)

            # Final score component
            term_score = tf_component * idfs.get(term, 0.0)
            term_scores[term] = term_score
            field_contributions[doc_field] += term_score
            matched_terms.append(term)

        # Sum all term scores for document
        total_score = sum(term_scores.values())

        # Query coverage ratio
        query_coverage = len(matched_terms) / len(query_terms) if query_terms else 0.0

        if total_score > 0 or matched_terms:
            scores.append(BM25FScore(
                doc_id=doc_idx,
                doc_text=doc.text,
                score=total_score,
                term_scores=term_scores,
                field_contributions=dict(field_contributions),
                query_coverage=query_coverage,
                matched_terms=matched_terms,
            ))

    # Sort: score desc, query_coverage desc, doc_id asc for stability
    scores.sort(key=lambda x: (-x.score, -x.query_coverage, x.doc_id))

    return scores[:top_n]


# block_math_ngram_rank: N-gram extraction and ranking by weighted frequency
# Semantic block: Generates n-grams, computes scores with source weighting, filters by thresholds


# FUNCTION_CONTRACT: extract_ngrams
# Purpose: Extract and rank n-grams from SERP corpus with source weighting
# Input: corpus (List[TextSource]), n (int), min_count (int), min_df (int)
# Output: List[NgramScore]
# Side Effects: Uses memoization cache keyed by corpus hash
# Business Rules: Filters by min_count and min_document_frequency; returns sorted by weighted_count desc then ngram asc
# Failure Modes: Returns empty list for empty corpus; never raises
# LINKS: PLAN 08-02 Task 3
@functools.lru_cache(maxsize=128)
def extract_ngrams(
    corpus_hash: tuple[tuple[str, str, float], ...],
    n: int = 1,
    min_count: int = 2,
    min_df: int = 2,
    strip_suffixes: bool = False,
) -> List[NgramScore]:
    """Extract n-grams from corpus with frequency filtering.

    Args:
        corpus_hash: Hashable representation of TextSource corpus (for memoization)
        n: N-gram size (1-4)
        min_count: Minimum raw count threshold
        min_df: Minimum document frequency threshold
        strip_suffixes: Whether to apply suffix stripping

    Returns:
        List of NgramScore sorted by weighted_count desc, ngram asc
    """
    # Reconstruct corpus from hash
    corpus = [TextSource(text=t, field=f, weight=w) for t, f, w in corpus_hash]

    if not corpus:
        return []

    stopwords = _get_default_stopwords()
    ngram_counts: Dict[str, int] = defaultdict(int)
    weighted_counts: Dict[str, float] = defaultdict(float)
    doc_frequencies: Dict[str, Set[int]] = defaultdict(set)
    source_breakdown: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for doc_idx, source in enumerate(corpus):
        tokens = _tokenize_text(source.text, strip_suffixes, stopwords)

        # Generate n-grams
        for i in range(len(tokens) - n + 1):
            ngram = " ".join(tokens[i:i + n])

            # Count occurrences in this document
            doc_count = sum(1 for j in range(len(tokens) - n + 1) if " ".join(tokens[j:j + n]) == ngram)

            ngram_counts[ngram] += doc_count
            weighted_counts[ngram] += doc_count * source.weight
            doc_frequencies[ngram].add(doc_idx)
            source_breakdown[ngram][source.field] += doc_count

    # Filter and build results
    results: List[NgramScore] = []
    for ngram, raw_count in ngram_counts.items():
        df = len(doc_frequencies[ngram])

        if raw_count < min_count or df < min_df:
            continue

        results.append(NgramScore(
            ngram=ngram,
            gram_size=n,
            raw_count=raw_count,
            weighted_count=weighted_counts[ngram],
            doc_frequency=df,
            sources=dict(source_breakdown[ngram]),
        ))

    # Sort: weighted_count desc, then ngram asc for stability
    results.sort(key=lambda x: (-x.weighted_count, x.ngram))

    return results


# block_math_tfidf_score: TF-IDF computation with small-corpus smoothing
# Semantic block: Computes TF-IDF scores using exact formulas with source weighting


# FUNCTION_CONTRACT: compute_tfidf
# Purpose: Compute TF-IDF scores for terms in SERP corpus with small-corpus smoothing
# Input: corpus (List[TextSource])
# Output: List[TfidfTermScore]
# Side Effects: Uses memoization cache keyed by corpus hash
# Business Rules: Uses formula tf(t,d) = count(t,d) / total_terms(d); idf(t) = log((N+1)/(df+1)) + 1; filters by df >= 2
# Failure Modes: Returns empty list for empty corpus; never raises
# LINKS: PLAN 08-02 Task 2
@functools.lru_cache(maxsize=128)
def compute_tfidf(
    corpus_hash: tuple[tuple[str, str, float], ...],
    strip_suffixes: bool = False,
) -> List[TfidfTermScore]:
    """Compute TF-IDF scores for terms in corpus.

    Uses exact formula with small-corpus smoothing:
    - tf(term, doc) = count(term, doc) / total_terms(doc)
    - idf(term) = log((N + 1) / (df(term) + 1)) + 1
    - tfidf(term, doc) = tf(term, doc) * idf(term)

    Args:
        corpus_hash: Hashable representation of TextSource corpus
        strip_suffixes: Whether to apply suffix stripping

    Returns:
        List of TfidfTermScore sorted by tfidf desc, term asc
    """
    # Reconstruct corpus from hash
    corpus = [TextSource(text=t, field=f, weight=w) for t, f, w in corpus_hash]

    if not corpus:
        return []

    N = len(corpus)
    stopwords = _get_default_stopwords()

    # Compute term frequencies per document
    doc_terms: List[List[str]] = []
    for source in corpus:
        tokens = _tokenize_text(source.text, strip_suffixes, stopwords)
        doc_terms.append(tokens)

    # Count document frequencies
    doc_freq: Dict[str, int] = defaultdict(int)
    for tokens in doc_terms:
        unique_terms = set(tokens)
        for term in unique_terms:
            doc_freq[term] += 1

    # Compute aggregated TF-IDF with source weighting
    term_scores: Dict[str, TfidfTermScore] = {}

    for doc_idx, (tokens, source) in enumerate(zip(doc_terms, corpus)):
        if not tokens:
            continue

        total_terms = len(tokens)
        term_counts = Counter(tokens)

        for term, count in term_counts.items():
            df = doc_freq.get(term, 0)

            # Skip terms appearing in only one document (low signal)
            if df < 2:
                continue

            # TF-IDF calculation
            tf = count / total_terms
            idf = math.log((N + 1) / (df + 1)) + 1  # Small-corpus smoothing
            tfidf = tf * idf

            # Aggregate with source weight
            if term not in term_scores:
                term_scores[term] = TfidfTermScore(
                    term=term,
                    tfidf=0.0,
                    raw_tf=tf,
                    idf=idf,
                    doc_frequency=df,
                )

            term_scores[term].tfidf += tfidf * source.weight

    # Convert to list and sort
    results = list(term_scores.values())
    results.sort(key=lambda x: (-x.tfidf, x.term))

    return results


# block_math_cooccurrence_terms: Co-occurrence analysis using Jaccard similarity
# Semantic block: Builds co-occurrence matrix and computes similarity scores (NOT true LSI/SVD per review feedback)


# FUNCTION_CONTRACT: _build_cooccurrence_matrix
# Purpose: Build term co-occurrence matrix from corpus within sliding window
# Input: corpus (List[TextSource]), window (int), stopwords (Set[str])
# Output: Dict[str, Counter]
# Side Effects: (none)
# Business Rules: Tracks term pairs appearing within window distance
# Failure Modes: Returns empty dict for empty corpus; never raises
# LINKS: PLAN 08-02 Task 3
def _build_cooccurrence_matrix(
    corpus: List[TextSource],
    window: int = 5,
    stopwords: Optional[Set[str]] = None,
) -> Dict[str, Counter]:
    """Build co-occurrence matrix from corpus.

    Returns mapping from term -> Counter of co-occurring terms.
    """
    if stopwords is None:
        stopwords = _get_default_stopwords()

    cooccurrence: Dict[str, Counter] = defaultdict(Counter)

    for source in corpus:
        tokens = _tokenize_text(source.text, False, stopwords)

        # Build sliding window co-occurrence
        for i, term in enumerate(tokens):
            window_end = min(i + window + 1, len(tokens))
            for j in range(i + 1, window_end):
                other = tokens[j]
                if other != term:
                    cooccurrence[term][other] += 1
                    cooccurrence[other][term] += 1  # Symmetric

    return cooccurrence


# FUNCTION_CONTRACT: _compute_jaccard_similarity
# Purpose: Compute Jaccard similarity between two term sets
# Input: set_a (Set[str]), set_b (Set[str])
# Output: float
# Side Effects: (none)
# Business Rules: J(A,B) = |A ∩ B| / |A ∪ B|; returns 0.0 for empty union
# Failure Modes: never raises
# LINKS: PLAN 08-02 Task 3
def _compute_jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


# FUNCTION_CONTRACT: compute_cooccurrence_terms
# Purpose: Find co-occurring terms for seed terms using Jaccard similarity
# Input: corpus (List[TextSource]), seed_terms (List[str]), window (int), top_n (int)
# Output: List[CooccurrenceTermScore]
# Side Effects: Uses memoization cache keyed by corpus hash and seed terms
# Business Rules: Returns top co-occurring terms sorted by cooccurrence_count desc, jaccard desc, term asc
# Failure Modes: Returns empty list for empty corpus/seeds; never raises
# LINKS: PLAN 08-02 Task 3
@functools.lru_cache(maxsize=128)
def compute_cooccurrence_terms(
    corpus_hash: tuple[tuple[str, str, float], ...],
    seed_terms: tuple[str, ...],
    window: int = 5,
    top_n: int = 30,
    strip_suffixes: bool = False,
) -> List[CooccurrenceTermScore]:
    """Compute co-occurring terms for seed terms.

    NOT true LSI/SVD — uses co-occurrence matrix and Jaccard similarity
    (per review feedback).

    Args:
        corpus_hash: Hashable representation of TextSource corpus
        seed_terms: Terms to find co-occurrences for
        window: Context window size
        top_n: Maximum number of results to return
        strip_suffixes: Whether to apply suffix stripping

    Returns:
        List of CooccurrenceTermScore sorted by cooccurrence_count desc
    """
    # Reconstruct corpus from hash
    corpus = [TextSource(text=t, field=f, weight=w) for t, f, w in corpus_hash]

    if not corpus or not seed_terms:
        return []

    stopwords = _get_default_stopwords()
    cooccurrence = _build_cooccurrence_matrix(corpus, window, stopwords)

    # Find co-occurrences for each seed term
    seed_term_set = set(term.lower() for term in seed_terms)
    results: Dict[str, CooccurrenceTermScore] = {}

    for seed_term in seed_terms:
        seed_lower = seed_term.lower()
        if seed_lower not in cooccurrence:
            continue

        # Get co-occurrence context set for Jaccard
        seed_context: Set[str] = set(cooccurrence[seed_lower].keys())

        for other_term, count in cooccurrence[seed_lower].items():
            if other_term in seed_term_set:
                continue  # Skip seed terms themselves

            # Build Jaccard similarity
            other_context = set(cooccurrence.get(other_term, {}).keys())
            jaccard = _compute_jaccard_similarity(seed_context, other_context)

            # Aggregate or create result
            if other_term not in results:
                results[other_term] = CooccurrenceTermScore(
                    term=other_term,
                    cooccurrence_count=0,
                    jaccard_similarity=0.0,
                    context_terms=[],
                )

            results[other_term].cooccurrence_count += count
            results[other_term].jaccard_similarity = max(
                results[other_term].jaccard_similarity,
                jaccard
            )
            if seed_lower not in results[other_term].context_terms:
                results[other_term].context_terms.append(seed_lower)

    # Sort and limit
    sorted_results = sorted(
        results.values(),
        key=lambda x: (-x.cooccurrence_count, -x.jaccard_similarity, x.term)
    )

    return sorted_results[:top_n]


# block_math_cache_memoization: Intent and content gap analysis with confidence metrics
# Semantic block: Analyzes search intent from SERP corpus and content gaps between source and target


# FUNCTION_CONTRACT: analyze_intent
# Purpose: Analyze search intent from SERP corpus with confidence metric
# Input: corpus (List[TextSource])
# Output: IntentSignal
# Side Effects: Uses memoization cache keyed by corpus hash
# Business Rules: Scores informational, commercial, transactional, and navigational signals via field-aware matching; confidence blends source coverage, signal opportunity coverage, and dominance
# Failure Modes: Returns zero-scored IntentSignal for empty corpus; never raises
# LINKS: PLAN 08-02 Task 4
@functools.lru_cache(maxsize=128)
def analyze_intent(
    corpus_hash: tuple[tuple[str, str, float], ...],
    strip_suffixes: bool = False,
) -> IntentSignal:
    """Analyze search intent from SERP corpus.

    Uses field-aware token and URL heuristics so title and H1 signals carry
    more weight than snippet or related-query signals. Intent categories are
    informational, commercial, transactional, navigational, mixed, and
    undetermined.

    Confidence is based on source coverage, matched signal opportunities, and
    category dominance. A single repeated token from one source should not
    produce high confidence across a large SERP corpus.

    Args:
        corpus_hash: Hashable representation of TextSource corpus
        strip_suffixes: Whether to apply suffix stripping

    Returns:
        IntentSignal with scores and confidence
    """
    corpus = [TextSource(text=t, field=f, weight=w) for t, f, w in corpus_hash]

    if not corpus:
        return IntentSignal(
            intent_type="undetermined",
            score=0.0,
            confidence=0.0,
            signals=[],
        )

    stopwords = _get_default_stopwords()
    total_sources = len(corpus)

    def _field_multiplier(field: str) -> float:
        field_lower = field.lower()
        if field_lower in {"title", "serp_title", "page_title", "h1"}:
            return 1.4
        if "title" in field_lower or field_lower in {"headline"}:
            return 1.25
        if "snippet" in field_lower or "description" in field_lower:
            return 1.0
        if field_lower in {"related_searches", "related_search", "people_also_ask", "paa"}:
            return 0.6
        if field_lower == "displayed_link":
            return 0.85
        return 0.9

    informational_exact: Set[str] = {
        "how", "what", "why", "guide", "tutorial", "wiki", "faq",
        "explain", "definition", "meaning", "examples", "overview",
        "introduction", "basics", "beginner", "advanced", "questions",
        "answers", "choose", "choosing", "review", "comparison",
        "compare", "vs", "versus",
    }

    commercial_exact: Set[str] = {
        "best", "top", "price", "pricing", "cost", "catalog", "product", "products",
        "shop", "store", "availability", "offer", "offers", "deal", "deals",
    }

    transactional_exact: Set[str] = {
        "buy", "order", "checkout", "cart", "pay", "payment",
        "delivery", "shipping", "discount", "sale", "coupon", "purchase",
        "subscribe", "subscription", "reserve", "book",
    }

    navigational_exact: Set[str] = {
        "official", "site", "login", "log", "account",
        "signin", "sign", "portal", "dashboard", "profile",
    }

    informational_stems: Set[str] = {
        "\u043a\u0430\u043a", "\u0447\u0442\u043e", "\u043e\u0431\u0437\u043e\u0440", "\u0441\u0440\u0430\u0432\u043d\u0435\u043d", "\u0438\u043d\u0441\u0442\u0440\u0443\u043a\u0446", "\u0441\u043e\u0432\u0435\u0442", "\u0432\u044b\u0431\u0438\u0440\u0430",
        "\u0432\u044b\u0431\u043e\u0440", "\u0440\u0435\u0439\u0442\u0438\u043d\u0433", "\u0442\u043e\u043f", "\u043b\u0443\u0447\u0448\u0438", "\u043f\u043e\u043b\u044c\u0437\u043d", "\u0441\u0442\u0430\u0442", "\u043f\u043e\u0447\u0435\u043c\u0443",
        "\u0437\u0430\u0447\u0435\u043c", "\u044f\u043a\u0456", "\u0449\u043e", "\u043e\u0433\u043b\u044f\u0434", "\u043f\u043e\u0440\u0456\u0432\u043d\u044f", "\u0456\u043d\u0441\u0442\u0440\u0443\u043a\u0446", "\u043f\u043e\u0440\u0430\u0434",
        "\u0432\u0438\u0431\u0438\u0440\u0430", "\u0432\u0438\u0431\u0456\u0440", "\u0440\u0435\u0439\u0442\u0438\u043d\u0433", "\u043a\u0440\u0430\u0449", "\u043a\u043e\u0440\u0438\u0441\u043d", "\u0441\u0442\u0430\u0442\u0442", "\u0447\u043e\u043c\u0443", "\u043d\u0430\u0432\u0456\u0449\u043e",
    }

    commercial_stems: Set[str] = {
        "\u0446\u0435\u043d", "\u0441\u0442\u043e\u0438\u043c", "\u0434\u0435\u0448\u0435\u0432", "\u043a\u0430\u0442\u0430\u043b\u043e\u0433", "\u0442\u043e\u0432\u0430\u0440", "\u043f\u0440\u043e\u0434\u0443\u043a\u0442", "\u043c\u0430\u0433\u0430\u0437\u0438\u043d", "\u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0435\u043d",
        "\u043e\u043f\u0442", "\u043f\u0440\u0430\u0439\u0441", "\u0446\u0456\u043d", "\u0432\u0430\u0440\u0442", "\u043f\u0440\u043e\u043f\u043e\u0437\u0438\u0446", "\u0440\u043e\u0437\u0434\u0440\u0456\u0431",
        "\u0446\u0456\u043d\u0430", "\u0432\u0430\u0440\u0442\u0456\u0441\u0442", "\u0442\u043e\u0432\u0430\u0440", "\u043f\u0440\u043e\u0434\u0443\u043a\u0442", "\u043c\u0430\u0433\u0430\u0437\u0438\u043d", "\u043a\u0430\u0442\u0430\u043b\u043e\u0433",
    }

    transactional_stems: Set[str] = {
        "\u043a\u0443\u043f", "\u0437\u0430\u043a\u0430\u0437", "\u043e\u043f\u043b\u0430\u0442", "\u0434\u043e\u0441\u0442\u0430\u0432", "\u0441\u043a\u0438\u0434\u043a", "\u043a\u043e\u0440\u0437\u0438\u043d", "\u043f\u0440\u043e\u043c\u043e\u043a\u043e\u0434",
        "\u0430\u043a\u0446\u0438", "\u0440\u0430\u0441\u043f\u0440\u043e\u0434", "\u043f\u043e\u043a\u0443\u043f", "\u043a\u0443\u043f\u0443\u0432", "\u0437\u0430\u043c\u043e\u0432", "\u0437\u043d\u0438\u0436\u043a", "\u043a\u043e\u0448\u0438\u043a",
        "\u0430\u043a\u0446\u0456", "\u0440\u043e\u0437\u043f\u0440\u043e\u0434", "\u0431\u0440\u043e\u043d\u044c",
    }

    navigational_stems: Set[str] = {
        "\u043e\u0444\u0438\u0446", "\u0433\u043b\u0430\u0432\u043d", "\u0434\u043e\u043c\u0430\u0448\u043d", "\u0432\u0445\u043e\u0434", "\u0430\u043a\u043a\u0430\u0443\u043d\u0442", "\u043b\u0438\u0447\u043d", "\u043a\u0430\u0431\u0438\u043d\u0435\u0442",
        "\u043f\u043e\u0440\u0442\u0430\u043b", "\u0430\u0434\u043c\u0438\u043d", "\u043e\u0444\u0456\u0446\u0456\u0439", "\u0433\u043e\u043b\u043e\u0432\u043d", "\u0443\u0432\u0456\u0439", "\u0430\u043a\u0430\u0443\u043d\u0442", "\u043a\u0430\u0431\u0456\u043d\u0435\u0442",
    }

    def _is_url_like(text: str) -> bool:
        return bool(re.search(r"(?:https?://|www\.)|\.[a-z]{2,}(?:/|$)", text))

    def _append_score(
        category_scores: Dict[str, float],
        category: str,
        signal: str,
        source_index: int,
        source_weight: float,
        field_weight: float,
        signal_weight: float,
        matched_signals: Set[str],
        category_sources: Dict[str, Set[int]],
    ) -> None:
        category_scores[category] += source_weight * field_weight * signal_weight
        category_sources[category].add(source_index)
        matched_signals.add(signal)

    def _mark_signal(
        category_scores: Dict[str, float],
        category_sources: Dict[str, Set[int]],
        matched_signals: Set[str],
        source_index: int,
        source_weight: float,
        field_weight: float,
        category: str,
        signal: str,
        signal_weight: float,
    ) -> None:
        _append_score(
            category_scores,
            category,
            signal,
            source_index,
            source_weight,
            field_weight,
            signal_weight,
            matched_signals,
            category_sources,
        )

    category_scores: Dict[str, float] = {
        "informational": 0.0,
        "commercial": 0.0,
        "transactional": 0.0,
        "navigational": 0.0,
    }
    category_sources: Dict[str, Set[int]] = {
        "informational": set(),
        "commercial": set(),
        "transactional": set(),
        "navigational": set(),
    }
    matched_signals: Set[str] = set()
    matched_source_count = 0
    matched_opportunities = 0
    evaluated_opportunities = 0

    for source_index, source in enumerate(corpus):
        tokens = _tokenize_text(source.text, strip_suffixes, stopwords)
        token_set = set(tokens)
        field_lower = source.field.lower()
        field_weight = _field_multiplier(field_lower)
        raw_lower = source.text.lower()
        source_had_signal = False
        evaluated_opportunities += 4

        def mark_signal(category: str, signal: str, signal_weight: float) -> None:
            nonlocal source_had_signal, matched_opportunities
            if signal not in matched_signals:
                matched_opportunities += 1
            _mark_signal(
                category_scores,
                category_sources,
                matched_signals,
                source_index,
                source.weight,
                field_weight,
                category,
                signal,
                signal_weight,
            )
            source_had_signal = True

        if field_lower == "displayed_link" or _is_url_like(raw_lower):
            commerce_path_hits = (
                "buy", "order", "checkout", "cart", "pay", "payment",
                "shipping", "delivery", "discount", "sale", "coupon",
                "price", "pricing", "catalog", "product", "shop", "store",
            )
            navigational_path_hits = (
                "login", "account", "home", "homepage", "official",
                "signin", "portal", "dashboard", "profile", "site",
            )
            url_has_commerce = any(hit in raw_lower for hit in commerce_path_hits)
            url_has_navigation = any(hit in raw_lower for hit in navigational_path_hits)

            if url_has_navigation and not url_has_commerce:
                if "login" in raw_lower or "account" in raw_lower:
                    mark_signal("navigational", "nav:login", 1.7)
                    mark_signal("navigational", "nav:account", 1.5)
                elif "home" in raw_lower or "homepage" in raw_lower:
                    mark_signal("navigational", "nav:homepage", 1.5)
                elif "official" in raw_lower or "site" in raw_lower:
                    mark_signal("navigational", "nav:official", 1.4)
                mark_signal("navigational", "nav:domain", 1.2)
            elif url_has_commerce:
                transactional_hits = (
                    "buy", "order", "checkout", "cart", "pay", "payment",
                    "shipping", "delivery", "discount", "sale", "coupon",
                )
                if any(hit in raw_lower for hit in transactional_hits):
                    for signal in transactional_hits:
                        if signal in raw_lower:
                            mark_signal("transactional", f"url:{signal}", 1.6)
                else:
                    for signal in ("price", "pricing", "catalog", "product", "shop", "store"):
                        if signal in raw_lower:
                            mark_signal("commercial", f"url:{signal}", 1.3)

        for signal in informational_exact:
            if signal in token_set:
                weight = 1.15 if signal in {"how", "what", "why", "guide", "tutorial", "faq"} else 0.85
                mark_signal("informational", signal, weight)

        for signal in commercial_exact:
            if signal in token_set:
                weight = 1.15 if signal in {"best", "top", "price", "pricing", "cost", "catalog", "product", "products"} else 0.95
                mark_signal("commercial", signal, weight)

        for signal in transactional_exact:
            if signal in token_set:
                weight = 1.2 if signal in {"buy", "order", "checkout", "cart", "pay", "payment"} else 1.0
                mark_signal("transactional", signal, weight)

        for signal in navigational_exact:
            if signal in token_set:
                weight = 1.35 if signal in {"official", "homepage", "home", "login", "account", "portal", "dashboard"} else 0.9
                mark_signal("navigational", f"nav:{signal}", weight)

        cyrillic_tokens = {token for token in token_set if re.search("[\u0430-\u044f\u0456\u0457\u0454\u0491]", token)}
        # Intent morphology toggle (INVERTED from naive intuition):
        #  - strip_suffixes=True  (ENABLED)  = BROAD/permissive: lemmatize the token
        #    then prefix-match the lemma, so inflected forms collapse onto a stem
        #    (\u043a\u0443\u043f\u0438\u0442\u044c = \u043a\u0443\u043f\u0438\u043b = \u043a\u0443\u043f\u043b\u044e -> all match stem "\u043a\u0443\u043f"). When enabled the token
        #    is already lemmatized by _tokenize_text, so lemmatize_token is idempotent
        #    here; calling it again keeps the matcher self-contained.
        #  - strip_suffixes=False (DISABLED) = STRICT: exact equality token == stem,
        #    no morphology collapsing at all (\u043a\u0443\u043f\u0438\u0442\u044c != \u043a\u0443\u043f).
        def _stem_matches(token: str, stem: str) -> bool:
            if strip_suffixes:
                lemma_form = lemmatize_token(token)
                return lemma_form.startswith(stem) or stem.startswith(lemma_form)
            return token == stem
        for token in cyrillic_tokens:
            for stem in informational_stems:
                if _stem_matches(token, stem):
                    mark_signal("informational", stem, 0.95)
                    break

            for stem in commercial_stems:
                if _stem_matches(token, stem):
                    mark_signal("commercial", stem, 0.9)
                    break

            for stem in transactional_stems:
                if _stem_matches(token, stem):
                    mark_signal("transactional", stem, 1.05)
                    break

            for stem in navigational_stems:
                if _stem_matches(token, stem):
                    mark_signal("navigational", f"nav:{stem}", 1.2)
                    break

        if source_had_signal:
            matched_source_count += 1

    total_score = sum(category_scores.values())
    if total_score <= 0:
        return IntentSignal(
            intent_type="undetermined",
            score=0.0,
            confidence=0.0,
            signals=[],
        )

    sorted_categories = sorted(category_scores.items(), key=lambda item: item[1], reverse=True)
    top_category, top_score = sorted_categories[0]
    second_score = sorted_categories[1][1] if len(sorted_categories) > 1 else 0.0

    dominance = top_score / total_score if total_score > 0 else 0.0
    source_coverage = matched_source_count / total_sources if total_sources > 0 else 0.0
    opportunity_coverage = matched_opportunities / evaluated_opportunities if evaluated_opportunities > 0 else 0.0
    confidence = round(
        min(
            1.0,
            (0.55 * source_coverage) + (0.25 * dominance) + (0.20 * opportunity_coverage),
        ),
        3,
    )

    if top_score <= 0:
        intent_type = "undetermined"
        score = 0.0
    else:
        close_runner_up = second_score > 0 and (top_score - second_score) <= max(0.45, top_score * 0.18)
        low_signal_density = top_score < 0.8 and total_score < 1.2

        if low_signal_density:
            intent_type = "undetermined"
            score = 0.0
        elif close_runner_up:
            intent_type = "mixed"
            score = round(top_score, 2)
        else:
            intent_type = top_category
            score = round(top_score, 2)

    return IntentSignal(
        intent_type=intent_type,
        score=score,
        confidence=confidence,
        signals=sorted(matched_signals),
    )

# FUNCTION_CONTRACT: _compute_cosine_similarity
# Purpose: Compute cosine similarity between two TF-IDF vectors
# Input: vector_a (Dict[str, float]), vector_b (Dict[str, float])
# Output: float
# Side Effects: (none)
# Business Rules: cos(A,B) = (A·B) / (||A|| * ||B||); returns 0.0 for zero vectors
# Failure Modes: never raises
# LINKS: PLAN 08-02 Task 4
def _compute_cosine_similarity(
    vector_a: Dict[str, float],
    vector_b: Dict[str, float]
) -> float:
    """Compute cosine similarity between two TF-IDF vectors."""
    # Dot product
    dot_product = sum(vector_a.get(k, 0) * vector_b.get(k, 0) for k in set(vector_a) | set(vector_b))

    # Magnitudes
    magnitude_a = math.sqrt(sum(v * v for v in vector_a.values()))
    magnitude_b = math.sqrt(sum(v * v for v in vector_b.values()))

    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0

    return dot_product / (magnitude_a * magnitude_b)


# FUNCTION_CONTRACT: analyze_content_gap
# Purpose: Analyze content gap between source text and target keyword profile
# Input: source_text (str), target_profile (List[str])
# Output: ContentGapResult
# Side Effects: (none)
# Business Rules: Computes coverage ratio, Jaccard overlap, cosine similarity; identifies missing/overused terms
# Failure Modes: Returns zero-scored result for empty inputs; never raises
# LINKS: PLAN 08-02 Task 4
def analyze_content_gap(
    source_text: str,
    target_profile: List[str],
    strip_suffixes: bool = False,
) -> ContentGapResult:
    """Analyze content gap between source text and target profile.

    Args:
        source_text: Source text to analyze
        target_profile: List of target terms to check coverage for
        strip_suffixes: Whether to apply suffix stripping

    Returns:
        ContentGapResult with coverage metrics and missing/overused terms
    """
    stopwords = _get_default_stopwords()

    # Tokenize source
    source_tokens = _tokenize_text(source_text, strip_suffixes, stopwords)
    source_set = set(source_tokens)
    target_set = set(term.lower() for term in target_profile)

    if not target_set:
        return ContentGapResult(
            coverage_ratio=0.0,
            jaccard_overlap=0.0,
            cosine_similarity=0.0,
            missing_high_value=[],
            overused_low_value=[],
        )

    # Coverage ratio
    covered_terms = source_set & target_set
    coverage_ratio = len(covered_terms) / len(target_set) if target_set else 0.0

    # Jaccard overlap
    jaccard = _compute_jaccard_similarity(source_set, target_set)

    # Cosine similarity (using term frequency as vectors)
    source_tf = Counter(source_tokens)
    target_tf = Counter(term.lower() for term in target_profile)
    cosine = _compute_cosine_similarity(source_tf, target_tf)

    # Missing high-value terms (in target but not in source)
    missing_high_value = sorted(target_set - source_set)

    # Overused low-value terms (terms appearing >3 times in source but not in target)
    term_counts = Counter(source_tokens)
    overused_low_value = [
        term for term, count in term_counts.items()
        if count > 3 and term not in target_set
    ]

    return ContentGapResult(
        coverage_ratio=coverage_ratio,
        jaccard_overlap=jaccard,
        cosine_similarity=cosine,
        missing_high_value=missing_high_value,
        overused_low_value=overused_low_value,
    )


# block_math_generation_quality: Generated SEO text scoring with element-specific rubrics
# Semantic block: Parses generated SEO sections and scores each against SERP-derived profile


# FUNCTION_CONTRACT: _parse_generated_sections
# Purpose: Parse generated SEO output into sections (META_TITLE, META_DESCRIPTION, H1, DESCRIPTION)
# Input: generated_text (str)
# Output: Dict[str, str]
# Side Effects: (none)
# Business Rules: Extracts sections using regex patterns; returns empty strings for missing sections
# Failure Modes: Never raises; returns dict with empty strings for all sections on parse failure
# LINKS: PLAN 08-02 Task 7
def _parse_generated_sections(generated_text: str) -> Dict[str, str]:
    sections = {
        "META_TITLE": "",
        "META_DESCRIPTION": "",
        "H1": "",
        "DESCRIPTION": "",
    }

    if not generated_text:
        return sections

    lines = generated_text.split("\n")
    current_section = None  # No default section
    current_content: List[str] = []
    has_section_header = False

    for line in lines:
        line = line.strip()

        # Detect section headers
        if line.upper().startswith("META_TITLE:") or line.upper().startswith("**META_TITLE:**"):
            has_section_header = True
            if current_section is not None and current_content:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = "META_TITLE"
            current_content = []
            # Extract content after colon
            if ":" in line:
                content = line.split(":", 1)[1].strip()
                if content:
                    current_content = [content]
            continue

        if line.upper().startswith("META_DESCRIPTION:") or line.upper().startswith("**META_DESCRIPTION:**"):
            has_section_header = True
            if current_section is not None and current_content:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = "META_DESCRIPTION"
            current_content = []
            if ":" in line:
                content = line.split(":", 1)[1].strip()
                if content:
                    current_content = [content]
            continue

        if line.upper().startswith("H1:") or line.upper().startswith("**H1:**"):
            has_section_header = True
            if current_section is not None and current_content:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = "H1"
            current_content = []
            if ":" in line:
                content = line.split(":", 1)[1].strip()
                if content:
                    current_content = [content]
            continue

        if line.upper().startswith("DESCRIPTION:") or line.upper().startswith("**DESCRIPTION:**"):
            has_section_header = True
            if current_section is not None and current_content:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = "DESCRIPTION"
            current_content = []
            # Extract inline content after colon
            if ":" in line:
                content = line.split(":", 1)[1].strip()
                if content:
                    current_content = [content]
            continue

        # Add content to current section (only if we found a section header)
        if current_section is not None and line:
            current_content.append(line)

    # Don't forget the last section
    if current_section is not None and current_content:
        sections[current_section] = "\n".join(current_content).strip()

    # If no section headers found, try HTML patterns as fallback
    if not has_section_header:
        if not sections["META_TITLE"]:
            title_match = re.search(r"<title>(.*?)</title>", generated_text, re.IGNORECASE | re.DOTALL)
            if title_match:
                sections["META_TITLE"] = title_match.group(1).strip()

        if not sections["META_DESCRIPTION"]:
            desc_match = re.search(
                r'<meta\s+name="description"\s+content="([^"]*)?"',
                generated_text,
                re.IGNORECASE
            )
            if desc_match:
                sections["META_DESCRIPTION"] = desc_match.group(1).strip()

        if not sections["H1"]:
            h1_match = re.search(r"<h1>(.*?)</h1>", generated_text, re.IGNORECASE | re.DOTALL)
            if h1_match:
                sections["H1"] = h1_match.group(1).strip()
            else:
                # Try markdown H1
                h1_md_match = re.search(r"^#\s+(.+)$", generated_text, re.MULTILINE)
                if h1_md_match:
                    sections["H1"] = h1_md_match.group(1).strip()

    return sections


# FUNCTION_CONTRACT: _calculate_keyword_density
# Purpose: Calculate keyword density for a specific keyword in text
# Input: text (str), keyword (str)
# Output: float
# Side Effects: (none)
# Business Rules: Density = (keyword occurrences / total words) * 100
# Failure Modes: never raises
# LINKS: PLAN 08-02 Task 7
def _calculate_keyword_density(text: str, keyword: str) -> float:
    if not text or not keyword:
        return 0.0

    stopwords = _get_default_stopwords()
    tokens = _tokenize_text(text, False, stopwords)

    if not tokens:
        return 0.0

    keyword_lower = keyword.lower()
    count = sum(1 for token in tokens if token == keyword_lower)

    return (count / len(tokens)) * 100


# FUNCTION_CONTRACT: _check_forbidden_phrases
# Purpose: Check for weak/forbidden phrases in generated text
# Input: text (str)
# Output: List[str]
# Side Effects: (none)
# Business Rules: Returns list of found forbidden phrases (click here, learn more, etc.)
# Failure Modes: never raises
# LINKS: PLAN 08-02 Task 7
def _check_forbidden_phrases(text: str) -> List[str]:
    forbidden = [
        "click here", "learn more", "read more", "find out more",
        "нажмите здесь", "узнайте больше", "читать далее", "подробнее",
        "натисніть тут", "дізнайтеся більше", "читати далі",
    ]

    text_lower = text.lower()
    return [phrase for phrase in forbidden if phrase in text_lower]


# FUNCTION_CONTRACT: _score_element
# Purpose: Score a single SEO element against SERP profile using element-specific rubric
# Input: element_type (str), element_text (str), primary_keyword (str), serp_profile (Dict), generated_text (str), top_terms_limit (int)
# Output: ElementQualityScore
# Side Effects: (none)
# Business Rules: Applies element-specific length, keyword placement, and coverage rules
# Failure Modes: Returns zero-scored result with issues for empty/invalid input
# LINKS: PLAN 08-02 Task 7
def _score_element(
    element_type: str,
    element_text: str,
    primary_keyword: str,
    serp_profile: Dict[str, List[str]],
    generated_text: str,
    top_terms_limit: int = 50,
) -> ElementQualityScore:
    """Score a single SEO element.

    Args:
        element_type: One of META_TITLE, META_DESCRIPTION, H1, DESCRIPTION
        element_text: The text content of the element
        primary_keyword: Primary keyword to check for
        serp_profile: SERP-derived profile with top_ngrams, tfidf_terms, etc.
        generated_text: Full generated text for density checks

    Returns:
        ElementQualityScore with score and issues
    """
    issues: List[str] = []
    score = 100.0

    # Length compliance check
    length = len(element_text or "")

    if element_type == "META_TITLE":
        if length < 50:
            issues.append("meta_title_too_short")
            score -= 20
        elif length > 60:
            issues.append("meta_title_too_long")
            score -= 10
        # Primary keyword at start
        if primary_keyword and primary_keyword.lower() not in (element_text or "")[:30].lower():
            issues.append("meta_title_keyword_not_at_start")
            score -= 15
        # Top 3-grams coverage
        top_ngrams = serp_profile.get("top_ngrams", [])[:top_terms_limit]
        covered_ngrams = sum(1 for ngram in top_ngrams if ngram.lower() in (element_text or "").lower())
        if covered_ngrams < 2:
            issues.append("meta_title_low_ngram_coverage")
            score -= 10

    elif element_type == "META_DESCRIPTION":
        if length < 150:
            issues.append("meta_desc_too_short")
            score -= 15
        elif length > 160:
            issues.append("meta_desc_too_long")
            score -= 10
        # Primary keyword present
        if primary_keyword and primary_keyword.lower() not in (element_text or "").lower():
            issues.append("meta_desc_missing_keyword")
            score -= 15
        # Call-to-action check
        cta_phrases = ["купить", "замовити", "buy", "order", "shop"]
        has_cta = any(phrase in (element_text or "").lower() for phrase in cta_phrases)
        if not has_cta:
            issues.append("meta_desc_no_cta")
            score -= 10

    elif element_type == "H1":
        if length < 30:
            issues.append("h1_too_short")
            score -= 15
        elif length > 70:
            issues.append("h1_too_long")
            score -= 10
        # Primary keyword present
        if primary_keyword and primary_keyword.lower() not in (element_text or "").lower():
            issues.append("h1_missing_keyword")
            score -= 20
        # Should match title intent (rough check - not duplicated title)
        title = serp_profile.get("meta_title", "")
        if title and (element_text or "").strip() == title.strip():
            issues.append("h1_duplicates_title")
            score -= 15

    elif element_type == "DESCRIPTION":
        if length < 500:
            issues.append("description_too_short")
            score -= 20
        # TF-IDF overlap (should be 0.3-0.6)
        tfidf_overlap = serp_profile.get("tfidf_overlap", 0.0)
        if tfidf_overlap < 0.3:
            issues.append("description_low_tfidf_overlap")
            score -= 15
        elif tfidf_overlap > 0.8:
            issues.append("description_too_much_tfidf_overlap")
            score -= 10
        # Co-occurrence coverage
        cooccurrence_coverage = serp_profile.get("cooccurrence_coverage", 0.0)
        if cooccurrence_coverage < 0.5:
            issues.append("description_low_cooccurrence_coverage")
            score -= 15
        # Keyword density check
        density = _calculate_keyword_density(generated_text, primary_keyword or "")
        if density > 7.0:
            issues.append("description_keyword_stuffing")
            score -= 20
        # Forbidden phrases
        forbidden = _check_forbidden_phrases(generated_text)
        if forbidden:
            issues.extend([f"forbidden_phrase_{phrase}" for phrase in forbidden])
            score -= len(forbidden) * 5

    # Primary keyword presence check
    primary_present = primary_keyword and primary_keyword.lower() in (element_text or "").lower()

    # Calculate coverage ratio
    top_terms = serp_profile.get("top_ngrams", [])[:top_terms_limit]
    coverage = sum(1 for term in top_terms if term.lower() in (element_text or "").lower())
    keyword_coverage = coverage / len(top_terms) if top_terms else 0.0

    return ElementQualityScore(
        element=element_type,
        score=max(0.0, score),
        issues=issues,
        keyword_coverage=keyword_coverage,
        length_compliant=50 <= length <= 60 if element_type == "META_TITLE" else
                        150 <= length <= 160 if element_type == "META_DESCRIPTION" else
                        30 <= length <= 70 if element_type == "H1" else
                        length >= 500,
        primary_keyword_present=primary_present,
    )


# FUNCTION_CONTRACT: score_generated_text
# Purpose: Score generated SEO text against SERP-derived profile (public API)
# Input: generated_text (str), primary_keyword (str), serp_profile (Dict), enable_bm25f (bool), field_weights (Dict), field_b (Dict), signal_gaps (Optional[Dict]), top_terms_limit (int)
# Output: Dict[str, ElementQualityScore]
# Side Effects: (none)
# Business Rules: Parses sections, scores each with element-specific rubric; optionally computes BM25F coverage per element; optionally includes signal gaps
# Failure Modes: Returns dict with zero-scored elements for empty/missing sections; never raises
# LINKS: PLAN 08-02 Task 7, PLAN 10-02 Task 2, PLAN 10-02 Task 4
def score_generated_text(
    generated_text: str,
    primary_keyword: str,
    serp_profile: Dict[str, List[str]],
    enable_bm25f: bool = False,
    field_weights: Optional[Dict[str, float]] = None,
    field_b: Optional[Dict[str, float]] = None,
    signal_gaps: Optional[Dict[str, Any]] = None,
    top_terms_limit: int = 50,
) -> Dict[str, ElementQualityScore]:
    """Score generated SEO text against SERP-derived profile.

    Public API function for scoring (per review feedback).
    Optionally computes BM25F coverage per element when enabled.
    Optionally includes signal-based gap feedback (Phase 10 Task 4).

    Args:
        generated_text: Full generated SEO text output
        primary_keyword: Primary target keyword
        serp_profile: SERP analysis profile with top_ngrams, tfidf_terms, etc.
        enable_bm25f: Whether to compute BM25F coverage (default False)
        field_weights: Optional field weights for BM25F (uses defaults if None)
        field_b: Optional field b parameters for BM25F (uses defaults if None)
        signal_gaps: Optional signal gaps from crawl/SERP analysis for feedback

    Returns:
        Dict mapping element type -> ElementQualityScore with optional BM25F scores
    """
    sections = _parse_generated_sections(generated_text)

    results: Dict[str, ElementQualityScore] = {}

    # Build BM25F profile if enabled
    bm25f_profile = None
    query_terms = ()

    if enable_bm25f and serp_profile:
        # Build corpus from sections for BM25F
        corpus = []
        field_mapping = {
            "META_TITLE": ("page_title", 3.0),
            "META_DESCRIPTION": ("meta_description", 1.5),
            "H1": ("h1", 2.5),
            "DESCRIPTION": ("body_text", 1.0),
        }

        for element_type, (field, default_weight) in field_mapping.items():
            text = sections.get(element_type, "")
            if text:
                weight = field_weights.get(field, default_weight) if field_weights else default_weight
                corpus.append(TextSource(text=text, field=field, weight=weight))

        # Get query terms from SERP profile
        top_ngrams = serp_profile.get("top_ngrams", [])
        if top_ngrams:
            query_terms = tuple(term.lower() for term in top_ngrams[:top_terms_limit])

        if corpus and query_terms:
            # Build field profile
            settings = {"seo_math": {"field_weights": field_weights or {}}}
            bm25f_profile = build_field_weighted_profile(corpus, settings)

    for element_type in ["META_TITLE", "META_DESCRIPTION", "H1", "DESCRIPTION"]:
        element_text = sections.get(element_type, "")
        base_score = _score_element(
            element_type,
            element_text,
            primary_keyword,
            serp_profile,
            generated_text,
            top_terms_limit=top_terms_limit,
        )

        # Compute BM25F coverage if enabled
        if enable_bm25f and bm25f_profile and query_terms:
            field_mapping = {
                "META_TITLE": "page_title",
                "META_DESCRIPTION": "meta_description",
                "H1": "h1",
                "DESCRIPTION": "body_text",
            }
            field = field_mapping.get(element_type, "")

            if field:
                # Build mini corpus for this element
                element_corpus = [TextSource(text=element_text, field=field, weight=1.0)]
                corpus_hash = _normalize_for_hashing(element_corpus)

                # Convert profile data to tuples for memoization
                weights_tuple = tuple(sorted(bm25f_profile.field_weights.items()))
                b_tuple = tuple(sorted(bm25f_profile.field_b_params.items()))

                # Compute BM25F score for this element
                bm25f_scores = compute_bm25f(
                    corpus_hash=corpus_hash,
                    query_terms=query_terms,
                    field_weights=weights_tuple,
                    field_b=b_tuple,
                    k1=1.2,
                    top_n=1,
                )

                if bm25f_scores:
                    base_score.bm25f_score = bm25f_scores[0].score
                    base_score.bm25f_coverage = bm25f_scores[0].query_coverage

        # Add signal gap feedback (Phase 10 Task 4)
        if signal_gaps and element_type in ["META_TITLE", "H1"]:
            element_gaps = {}
            # Title alignment gaps
            if "title_alignment" in signal_gaps:
                title_alignment = signal_gaps["title_alignment"]
                if title_alignment.get("title_alignment_score", 1.0) < 0.5:
                    element_gaps["low_title_alignment"] = title_alignment.get("title_alignment_score")
                if title_alignment.get("title_rewrite_risk", 0.0) > 0.5:
                    element_gaps["title_rewrite_risk"] = title_alignment.get("title_rewrite_risk")

            if element_gaps:
                base_score.signal_gaps = element_gaps

        results[element_type] = base_score

    return results


# Data model classes for mathematical analysis


@dataclass
# Purpose: Text source with field type and weight for mathematical analysis.
# Attributes:
# text: The text content
# field: Field type (title, snippet, related_search, people_also_ask, etc.)
# weight: Source weight for scoring (3.0 for title, 1.5 for snippet, etc.)
# provenance_url: Optional URL where text was found
class TextSource:
    text: str
    field: str
    weight: float
    provenance_url: str = ""


@dataclass
# Purpose: N-gram ranking result.
# Attributes:
# ngram: The n-gram phrase
# gram_size: N-gram size (1-4)
# raw_count: Raw occurrence count
# weighted_count: Count weighted by source type
# doc_frequency: Number of documents containing this n-gram
# sources: Breakdown of counts by field type
class NgramScore:
    ngram: str
    gram_size: int
    raw_count: int
    weighted_count: float
    doc_frequency: int
    sources: Dict[str, int]


@dataclass
# Purpose: TF-IDF term score.
# Attributes:
# term: The term
# tfidf: TF-IDF score (aggregated across documents with weights)
# raw_tf: Raw term frequency
# idf: Inverse document frequency
# doc_frequency: Number of documents containing this term
class TfidfTermScore:
    term: str
    tfidf: float
    raw_tf: float
    idf: float
    doc_frequency: int


@dataclass
# Purpose: Co-occurrence term score (NOT true LSI/SVD).
# Attributes:
# term: The co-occurring term
# cooccurrence_count: Number of co-occurrences with seed terms
# jaccard_similarity: Jaccard similarity score
# context_terms: Seed terms this co-occurs with
class CooccurrenceTermScore:
    term: str
    cooccurrence_count: int
    jaccard_similarity: float
    context_terms: List[str]


@dataclass
# Purpose: Search intent analysis result.
# Attributes:
# intent_type: Intent type (informational, commercial, transactional, navigational, mixed, undetermined)
# score: Weighted score for dominant intent
# confidence: Ratio of signals matched / total signals checked (NEW per review)
# signals: List of matched intent signals
class IntentSignal:
    intent_type: str
    score: float
    confidence: float
    signals: List[str]


@dataclass
# Purpose: Content gap analysis result.
# Attributes:
# coverage_ratio: Ratio of target terms covered in source
# jaccard_overlap: Jaccard similarity between source and target
# cosine_similarity: Cosine similarity between TF-IDF vectors
# missing_high_value: Terms in target but not in source
# overused_low_value: Terms overused in source but not in target
class ContentGapResult:
    coverage_ratio: float
    jaccard_overlap: float
    cosine_similarity: float
    missing_high_value: List[str]
    overused_low_value: List[str]


@dataclass
# Purpose: SEO element quality score.
# Attributes:
# element: Element type (META_TITLE, META_DESCRIPTION, H1, DESCRIPTION)
# score: Quality score (0-100)
# issues: List of issue identifiers
# keyword_coverage: Ratio of top keywords covered
# length_compliant: Whether length is within guidelines
# primary_keyword_present: Whether primary keyword is present
# bm25f_score: Optional BM25F score when BM25F analysis is enabled
# bm25f_coverage: Optional BM25F query coverage ratio
# signal_gaps: Optional Dict[str, Any] with signal-based gap feedback (Phase 10 Task 4)
class ElementQualityScore:
    element: str
    score: float
    issues: List[str]
    keyword_coverage: float
    length_compliant: bool
    primary_keyword_present: bool
    bm25f_score: Optional[float] = None
    bm25f_coverage: Optional[float] = None
    signal_gaps: Optional[Dict[str, Any]] = None


@dataclass
# Purpose: Field statistics for BM25F length normalization.
# Attributes:
# field: Field name (title, snippet, body_text, etc.)
# total_length: Total token count across all documents for this field
# avg_length: Average tokens per document for this field
# doc_count: Number of documents with this field
class FieldStats:
    field: str
    total_length: int
    avg_length: float
    doc_count: int


@dataclass
# Purpose: BM25F document score with field-level breakdown.
# Attributes:
# doc_id: Document index in corpus
# doc_text: Document text for reference
# score: Final BM25F score
# term_scores: Dict mapping term -> contribution score
# field_contributions: Dict mapping field_name -> contribution to score
# query_coverage: Ratio of query terms with non-zero score
# matched_terms: List of query terms found in document
class BM25FScore:
    doc_id: int
    doc_text: str
    score: float
    term_scores: Dict[str, float]
    field_contributions: Dict[str, float]
    query_coverage: float
    matched_terms: List[str]


@dataclass
# Purpose: Field-weighted profile for BM25F scoring.
# Attributes:
# field_weights: Dict mapping field_name -> weight
# field_b_params: Dict mapping field_name -> b (length normalization) parameter
# field_stats: Dict mapping field_name -> FieldStats
# avg_field_lengths: Dict mapping field_name -> average length
# corpus_size: Total number of documents
# algorithm_version: Algorithm version identifier for cache invalidation
class FieldWeightedProfile:
    field_weights: Dict[str, float]
    field_b_params: Dict[str, float]
    field_stats: Dict[str, FieldStats]
    avg_field_lengths: Dict[str, float]
    corpus_size: int
    algorithm_version: str


# block_math_domain_metrics: Per-domain metrics from SERP results
# Semantic block: Computes average position, keyword SERP frequency, and result frequency per domain


@dataclass
# Purpose: Per-domain metrics from SERP analysis.
# Attributes:
# domain: Registrable domain (e.g., 'rozetka.com.ua', 'example.com')
# avg_position: Mean of Position values where this domain appears
# keyword_serp_count: Number of unique Keywords where this domain appears
# total_keyword_serps: Total number of unique Keywords in the DataFrame
# result_count: Total number of SERP rows where this domain appears
# total_results: Total number of SERP rows in the DataFrame
# domain_mentioned: Number of SERP results where this domain appears (same as result_count, explicit for UI clarity)
# domain_visibility: Percentage of total SERP results occupied by this domain (result_count / total_results * 100)
class DomainMetrics:
    domain: str
    avg_position: float
    keyword_serp_count: int
    total_keyword_serps: int
    result_count: int
    total_results: int
    domain_mentioned: int = 0
    domain_visibility: float = 0.0


# FUNCTION_CONTRACT: compute_domain_metrics
# Purpose: Compute per-domain metrics from SERP organic results DataFrame
# Input: serp_df (pd.DataFrame) with Keyword, Position, URL columns
# Output: List[DomainMetrics] sorted by keyword_serp_count desc, avg_position asc
# Side Effects: (none - pure function)
# Business Rules: Uses extract_match_domain for domain extraction (handles two-level TLDs); no lru_cache (DataFrames are unhashable)
# Failure Modes: Returns [] for empty DataFrame, missing columns, or no valid URLs
# LINKS: PLAN 14-02 Task 1
def compute_domain_metrics(serp_df: pd.DataFrame) -> List[DomainMetrics]:
    from utils.url_matcher import extract_match_domain

    if serp_df is None or serp_df.empty:
        return []

    # Validate required columns
    required_columns = {"Keyword", "Position", "URL"}
    if not required_columns.issubset(serp_df.columns):
        return []

    total_results = len(serp_df)
    total_keyword_serps = serp_df["Keyword"].nunique()

    # Build per-domain aggregation
    domain_positions: Dict[str, List[float]] = defaultdict(list)
    domain_keywords: Dict[str, set] = defaultdict(set)
    domain_result_count: Dict[str, int] = defaultdict(int)

    for _, row in serp_df.iterrows():
        url = row.get("URL")
        if url is None or (isinstance(url, float) and url != url):  # NaN check without pd
            continue

        domain = extract_match_domain(str(url))
        if not domain:
            continue

        position = row.get("Position", 0)
        if position is not None and not (isinstance(position, float) and position != position):
            domain_positions[domain].append(float(position))

        keyword = row.get("Keyword", "")
        if keyword:
            domain_keywords[domain].add(str(keyword))

        domain_result_count[domain] += 1

    # Build DomainMetrics list
    results: List[DomainMetrics] = []
    for domain in domain_positions:
        positions = domain_positions[domain]
        avg_pos = sum(positions) / len(positions) if positions else 0.0

        results.append(DomainMetrics(
            domain=domain,
            avg_position=round(avg_pos, 10),  # High precision, formatting done at display time
            keyword_serp_count=len(domain_keywords[domain]),
            total_keyword_serps=total_keyword_serps,
            result_count=domain_result_count[domain],
            total_results=total_results,
            domain_mentioned=domain_result_count[domain],
            domain_visibility=round(domain_result_count[domain] / total_results * 100, 1) if total_results > 0 else 0.0,
        ))

    # Sort: keyword_serp_count desc, then avg_position asc
    results.sort(key=lambda x: (-x.keyword_serp_count, x.avg_position))

    return results
