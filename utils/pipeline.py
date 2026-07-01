import hashlib
import re
from typing import Any, Callable, Dict, List, Optional, Tuple, TypedDict
from urllib.parse import urlparse

import requests

import pandas as pd
import streamlit as st

from config.i18n import t
from config.settings import SEO_MATH_CONFIG
from utils.crawler import CrawlPage, CrawlResult, CrawlSettings, bounded_crawl
from utils.google_ads_client import GoogleAdsHandler
from utils.keyword_processor import KeywordProcessor
from utils.llm_handler import LLMHandler
from utils.logger import logger
from utils.request_cache import (
    build_cache_key,
    request_cache,
)
from utils.scraper import WebScraper
from utils.google_trends_client import (
    GoogleTrendsClient,
    GoogleTrendsRequest,
    GoogleTrendsResult,
    TrendsOrchestrator,
    _restore_trends_result_from_payload as _canonical_restore_trends_result_from_payload,
    _trends_request_from_settings as _canonical_trends_request_from_settings,
    _looks_like_url as _google_trends_looks_like_url,
)
from utils.serp_client import (
    SERPKnowledgeGraph,
    SERPOrganicResult,
    SERPPeopleAlsoAsk,
    SERPSearchResult,
    create_serp_client,
)
from utils.seo_math_analysis import (
    TextSource,
    extract_ngrams,
    compute_tfidf,
    compute_cooccurrence_terms,
    analyze_intent,
    _normalize_for_hashing,
    compute_bm25f,
    build_field_weighted_profile,
    compute_domain_metrics,
    lemmatize_token,
    _tokenize_text,
)
from utils.validator import URLValidator
from utils.seo_signal_analysis import (
    extract_page_text_signals,
    compute_title_alignment,
    compute_content_effort_score,
    compute_topical_centroid_overlap,
    compute_simhash64,
)

KEYWORD_SEED_SOURCE_URL = "keyword-seed://manual-input"

# Keyword candidate source types
SOURCE_LLM_EXTRACTION = "llm_extraction"
SOURCE_ADS_URL_SEED = "ads_url_seed"
SOURCE_KEYWORD_INPUT = "keyword_input"
SOURCE_SERP_RELATED = "serp_related"
SOURCE_SERP_PAA = "serp_paa"
SOURCE_MATH_IDENTIFIED = "math_identified"
SOURCE_CRAWL_MATH = "crawl_math"
RESULT_COLUMNS = [
    "Keyword",
    "Source URL",
    "Avg Monthly Searches",
    "Competition",
    "Competition Index",
    "Low CPC",
    "High CPC",
    "CPC Currency",
    "Months With Data",
]

SERP_RESULT_COLUMNS = [
    "Keyword",
    "Position",
    "Title",
    "URL",
    "Snippet",
    "Displayed Link",
    "Rich Snippet",
    "Provider",
]

SERP_RELATED_COLUMNS = [
    "Keyword",
    "Related Query",
    "Type",
]

TRENDS_AVERAGE_COLUMNS = [
    "Keyword",
    "Average Interest",
    "Geo",
    "Timeframe",
    "Provider",
]

TRENDS_RELATED_COLUMNS = [
    "Related Query",
    "Value",
    "Type",
    "Rank Type",
    "Source Keywords",
]

SERP_CHAIN_MAX_KEYWORDS = 20


# block_pipeline_phase9_source_contracts: Source-aware data contracts and session state keys for Phase 9
# Semantic block: Tuple-keyed enrichment contracts, SERP match evidence model, session state GC rules (M4 amended)
# Amended for Cycle 4 pi review: M4 dynamic key patterns added to GC rules

# Source context key type alias: (normalized_keyword, normalized_source_url)
SourceContextKey = Tuple[str, str]

# Empty source URL marker for keyword-only workflows
EMPTY_SOURCE_URL = ""

# SERP match evidence entry (used by match index)
SERPMatchEvidence = TypedDict("SERPMatchEvidence", {
    "keyword": str,
    "source_url": str,
    "matched_serp_url": str,
    "match_type": str,  # "none", "domain", "full_url"
    "serp_rank": int,
    "matched_domain": str,
}, total=False)

# Phase 9 session state keys
SESSION_KEY_MATCH_TARGETS = "serp_match_targets"  # List[Dict] from build_source_url_targets()
SESSION_KEY_SERP_MATCH_INDEX = "serp_match_index"  # Dict[SourceContextKey, SERPMatchEvidence]
SESSION_KEY_STAGED_KEYWORDS = "url_llm_staged_keywords"  # List[KeywordCandidate]
SESSION_KEY_LAST_EXTRACTION_RUN_ID = "last_extraction_run_id"  # str
SESSION_KEY_ACTIVE_SOURCE_URLS = "active_source_urls"  # List[str]

# Dynamic state key prefixes for GC (M4 amendment)
PHASE9_DYNAMIC_STATE_PREFIXES = (
    "url_llm_staged::",
    "serp_match::",
    "keyword_select_::",
    "kw_candidates_url_llm_staged_",
)


# FUNCTION_CONTRACT: make_selection_key
# Purpose: Create stable checkbox key that includes both keyword and source URL hash
# Input: keyword (str), source_url (str), prefix (str)
# Output: str - stable hash-based checkbox key
# Side Effects: (none - pure function)
# Business Rules: Hash is deterministic; same input always produces same key
# Failure Modes: never raises
# LINKS: PLAN 09-04 Task 2
def make_selection_key(keyword: str, source_url: str, prefix: str) -> str:
    kw_norm = keyword.lower().strip()
    src_norm = source_url.lower().strip()
    tuple_str = f"{kw_norm}||{src_norm}"
    hash_val = hashlib.sha256(tuple_str.encode()).hexdigest()[:8]
    return f"{prefix}::kw_{hash_val}"


# FUNCTION_CONTRACT: normalize_keyword_for_lookup
# Purpose: Normalize keyword string for tuple key construction (M5 amendment)
# Input: keyword (str)
# Output: str - normalized keyword
# Side Effects: (none - pure function)
# Business Rules: Lowercase, strip, strip quotes - same normalization as match index build
# Failure Modes: never raises (CR-02 fix: handle None input)
# LINKS: PLAN 09-04 Task 2, Task 4
def normalize_keyword_for_lookup(keyword: str) -> str:
    if keyword is None:
        return ""
    return str(keyword).lower().strip().strip('"').strip("'").strip()


# FUNCTION_CONTRACT: normalize_source_url_for_lookup
# Purpose: Normalize source URL string for tuple key construction without changing URL path semantics
# Input: source_url (str)
# Output: str - trimmed source URL key
# Side Effects: (none - pure function)
# Business Rules: Preserve case because URL paths may be case-sensitive; trim only so Ads/SERP tuple keys align
# Failure Modes: never raises
# LINKS: PLAN 09-04 Task 4
def normalize_source_url_for_lookup(source_url: str) -> str:
    if source_url is None:
        return ""
    return str(source_url).strip()


# Session state GC rules for Phase 9 keys (M4 amended with dynamic patterns)
#
# | Key Type          | Key Pattern/Name                        | Set Trigger            | Clear Trigger                          |
# |-------------------|-----------------------------------------|------------------------|----------------------------------------|
# | Exact             | SESSION_KEY_MATCH_TARGETS               | URL workflow submit    | Mode change, new submit, source change |
# | Exact             | SESSION_KEY_SERP_MATCH_INDEX            | After SERP analysis    | Mode change, new submit                |
# | Exact             | SESSION_KEY_STAGED_KEYWORDS             | After LLM extraction   | Mode change, after downstream handoff  |
# | Exact             | SESSION_KEY_LAST_EXTRACTION_RUN_ID      | After LLM extraction   | New submission                         |
# | Exact             | SESSION_KEY_ACTIVE_SOURCE_URLS          | URL workflow submit    | Mode change, new submit                |
# | Dynamic (prefix)  | {selection_prefix}::kw_*                | Checkbox rendering     | Mode change, new submit, source change |
# | Dynamic (prefix)  | {selection_prefix}_select_all_*         | Select-all rendering   | Mode change, new submit, source change |
# | Dynamic (prefix)  | kw_candidates_*                         | Staged handoff         | Mode change, new submit                |


# block_pipeline_keyword_candidates: Keyword candidate state model and helpers for gated workflows
# Semantic block: Models and helpers for keyword candidate tracking across workflow stages
# Ensures SERP never receives URL-like strings and all handoffs are explicit via checkboxes


# Purpose: KeywordCandidate implementation
class KeywordCandidate(TypedDict, total=False):
    keyword: str
    source_url: Optional[str]
    source_stage: Optional[str]
    source_type: str
    ads_metrics: Optional[Dict[str, object]]
    serp_metrics: Optional[Dict[str, object]]
    selection_prefix: str


class KeywordCandidateRecord(dict):
    def __getattr__(self, item: str) -> Any:
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc

    def __setattr__(self, key: str, value: Any) -> None:
        self[key] = value


# FUNCTION_CONTRACT: is_url_like_query
# Purpose: Detect if a query string looks like a URL rather than a keyword
# Input: value (str)
# Output: bool
# Side Effects: (none)
# Business Rules: Returns True if string starts with http/https, contains domain-like patterns
# Failure Modes: never raises
# LINKS: PLAN 08-01 Task 1
def is_url_like_query(value: str) -> bool:
    return _google_trends_looks_like_url(value)


# FUNCTION_CONTRACT: filter_serp_eligible_keywords
# Purpose: Filter out URL-like strings from a list of keywords before sending to SERP
# Input: values (List[str])
# Output: List[str]
# Side Effects: (none)
# Business Rules: Removes any string that matches is_url_like_query
# Failure Modes: never raises
# LINKS: PLAN 08-01 Task 1
def filter_serp_eligible_keywords(values: List[str]) -> List[str]:
    return [v for v in values if not is_url_like_query(v)]


# FUNCTION_CONTRACT: store_keyword_candidates
# Purpose: Store keyword candidates in session state for checkbox selection
# Input: keywords (List[str]), source_url (str), source_type (str), selection_prefix (str), ads_metrics (Optional[Dict])
# Output: None
# Side Effects: Updates st.session_state with keyword candidates
# Business Rules: Stores candidates as list of dicts with keyword, source, and optional metrics
# Failure Modes: never raises
# LINKS: PLAN 08-01 Task 1
def store_keyword_candidates(
    keywords: List[str],
    source_url: str,
    source_type: str,
    selection_prefix: str,
    ads_metrics: Optional[Dict[str, object]] = None,
    serp_metrics: Optional[Dict[str, object]] = None,
) -> None:
    candidates_key = f"kw_candidates_{selection_prefix}"
    candidates: List[KeywordCandidate] = []
    for kw in keywords:
        candidate: KeywordCandidate = {
            "keyword": kw,
            "source_url": source_url,
            "source_stage": source_url,
            "source_type": source_type,
            "selection_prefix": selection_prefix,
        }
        if ads_metrics and kw in ads_metrics:
            candidate["ads_metrics"] = ads_metrics[kw]
        if serp_metrics and kw in serp_metrics:
            candidate["serp_metrics"] = serp_metrics[kw]
        candidates.append(candidate)
    st.session_state[candidates_key] = candidates


# FUNCTION_CONTRACT: get_selected_keyword_candidates
# Purpose: Get user-selected keywords from checkbox state
# Input: selection_prefix (str), candidates_key (Optional[str])
# Output: List[str]
# Side Effects: Reads st.session_state checkbox values
# Business Rules: Returns list of keywords where checkbox state is True
# Failure Modes: Returns empty list if no candidates or state missing
# LINKS: PLAN 08-01 Task 1
def get_selected_keyword_candidates(
    selection_prefix: str, candidates_key: Optional[str] = None
) -> List[str]:
    if candidates_key is None:
        candidates_key = f"kw_candidates_{selection_prefix}"
    candidates: Optional[List[KeywordCandidate]] = st.session_state.get(candidates_key)
    if not candidates:
        return []
    selected = []
    for candidate in candidates:
        kw = candidate["keyword"]
        checkbox_key = f"{selection_prefix}::{kw}"
        if st.session_state.get(checkbox_key, False):
            selected.append(kw)
    return selected


# MODULE_CONTRACT: utils/pipeline
# Purpose: Orchestrate three workflow modes — URL→LLM→Ads, URL→Ads, Keyword→Ads — with progress reporting, keyword-gated SERP handoffs, crawl math reporting, and Trends-as-stage integration
# Rationale: Encapsulates end-to-end keyword analysis pipelines that coordinate scraping, LLM extraction, Ads metrics, SERP math, bounded crawl reports, and Google Trends analysis as optional stage
# Dependencies: utils.google_ads_client, utils.llm_handler, utils.scraper, utils.keyword_processor, utils.validator, config.i18n, config.settings, utils.logger, utils.serp_client, utils.seo_math_analysis, utils.crawler, utils.google_trends_client, utils.request_cache
# Exports: run_llm_url_workflow, run_url_seed_workflow, run_keyword_seed_workflow, run_llm_keyword_stage_from_checkpoint, prepare_urls_for_seo, process_flow, run_serp_analysis_workflow, run_serp_chain_to_ads_workflow, run_llm_url_keyword_extraction_stage, build_serp_math_profile, build_reverse_math_report, build_crawl_math_report, run_crawl_math_report_workflow, run_google_trends_workflow, run_trends_stage_from_selection, run_trends_stage_from_keywords, run_keyword_to_llm_workflow, KEYWORD_SEED_SOURCE_URL, RESULT_COLUMNS, is_url_like_query, filter_serp_eligible_keywords, store_keyword_candidates, get_selected_keyword_candidates
# LINKS: requirements.xml#UC-001, requirements.xml#UC-002, requirements.xml#UC-003, knowledge-graph.xml#MOD-002, PLAN 08-01, PLAN 08-02 Task 6, PLAN 10-02 Task 9
# MODULE_MAP: utils/pipeline.py
# Public Functions: run_llm_url_workflow, run_url_seed_workflow, run_keyword_seed_workflow, run_llm_keyword_stage_from_checkpoint, prepare_urls_for_seo, process_flow, run_serp_analysis_workflow, run_serp_chain_to_ads_workflow, run_llm_url_keyword_extraction_stage, build_serp_math_profile, build_reverse_math_report, build_crawl_math_report, run_crawl_math_report_workflow, run_google_trends_workflow, run_trends_stage_from_selection, run_trends_stage_from_keywords, run_keyword_to_llm_workflow, is_url_like_query, filter_serp_eligible_keywords, store_keyword_candidates, get_selected_keyword_candidates
# Private Helpers: _format_pipeline_message, _empty_results_df, _ensure_result_columns, _merge_base_keywords_with_metrics, _store_processed_data, _render_invalid_url_details, _normalize_keyword_seed_input
# Key Semantic Blocks: block_pipeline_helpers_df_normalize, block_pipeline_checkpoint_regenerate, block_pipeline_compat_alias_delegate, block_pipeline_keyword_candidates, block_pipeline_serp_keyword_guard, block_pipeline_serp_math_profile, block_pipeline_reverse_math_report, block_pipeline_crawl_math_report, block_pipeline_trends_as_stage
# Critical Flows: app.py dispatches to one of the workflow functions based on selected mode; SERP/crawl results -> math profile -> UI rendering; Trends stage accepts checkbox-selected keywords from any workflow
# Verification: V-MOD-002
# CHANGE_SUMMARY: Added keyword candidate model and helpers for gated SERP workflows; added URL-like query detection; added staged LLM keyword extraction; updated MODULE_CONTRACT with new exports and semantic blocks; Phase 8 Task 6: added SERP math profile building function; Phase 8 Plan 03: added cached crawl math report orchestration and reverse SERP/Ads math report enrichment; Phase 9 review fix: row-scoped SERP source matching and tuple-consistent Ads enrichment; Phase 10 Task 9: added Trends-as-stage functions.
def _format_pipeline_message(key: str, **kwargs: object) -> str:
    return t(key, **kwargs)


# FUNCTION_CONTRACT: _empty_results_df
# Purpose: Create an empty DataFrame with the standardized result columns schema
# Input: currency_code (str)
# Output: pd.DataFrame — empty with RESULT_COLUMNS and currency set
# Side Effects: (none)
# Business Rules: CPC Currency column pre-filled with provided code
# Failure Modes: never raises
# LINKS: requirements.xml#UC-002
def _empty_results_df(currency_code: str) -> pd.DataFrame:
    data = {column: pd.Series(dtype="object") for column in RESULT_COLUMNS}
    empty_df = pd.DataFrame(data)
    empty_df["CPC Currency"] = pd.Series(dtype="object")
    if currency_code:
        empty_df.loc[:, "CPC Currency"] = currency_code
    return empty_df


# FUNCTION_CONTRACT: _ensure_result_columns
# Purpose: Normalize a DataFrame to the processed_data schema by adding missing columns and setting currency
# Input: df (Optional[pd.DataFrame]), currency_code (str)
# Output: pd.DataFrame — schema-conformant DataFrame
# Side Effects: (none)
# Business Rules: empty/None input returns _empty_results_df; missing columns filled with None; CPC Currency backfilled
# Failure Modes: never raises
# LINKS: requirements.xml#UC-002
def _ensure_result_columns(df: Optional[pd.DataFrame], currency_code: str) -> pd.DataFrame:
    if df is None or df.empty:
        return _empty_results_df(currency_code)

    normalized = df.copy()
    for column in RESULT_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = None
    normalized = normalized[RESULT_COLUMNS]
    if normalized["CPC Currency"].isna().all():
        normalized["CPC Currency"] = currency_code
    return normalized.reset_index(drop=True)


# FUNCTION_CONTRACT: _merge_base_keywords_with_metrics
# Purpose: Left-join Ads metrics onto base keywords DataFrame, preserving URL mapping from base
# Input: base_df (pd.DataFrame), metrics_df (Optional[pd.DataFrame]), currency_code (str)
# Output: pd.DataFrame — merged and schema-normalized DataFrame
# Side Effects: (none)
# Business Rules: drops Source URL from metrics before merge to avoid overwriting base URLs
# Failure Modes: empty metrics returns schema-normalized base
# LINKS: requirements.xml#UC-002
def _merge_base_keywords_with_metrics(
    base_df: pd.DataFrame,
    metrics_df: Optional[pd.DataFrame],
    currency_code: str,
) -> pd.DataFrame:
    if metrics_df is None or metrics_df.empty:
        return _ensure_result_columns(base_df, currency_code)

    sanitized_metrics_df = metrics_df.drop(columns=["Source URL"], errors="ignore")
    merged_df = pd.merge(base_df, sanitized_metrics_df, on="Keyword", how="left")
    return _ensure_result_columns(merged_df, currency_code)


# FUNCTION_CONTRACT: _store_processed_data
# Purpose: Store processed results and scraped content in Streamlit session state.
# Input: processed_df (pd.DataFrame), scraped_content (Optional[Dict[str, str]])
# Output: pd.DataFrame
# Side Effects: Writes st.session_state.processed_data and st.session_state.scraped_content.
# Business Rules: Uses an empty scraped-content mapping when no content is supplied.
# Failure Modes: Propagates Streamlit session-state assignment errors.
# LINKS: requirements.xml#UC-002
def _store_processed_data(
    processed_df: pd.DataFrame,
    scraped_content: Optional[Dict[str, str]] = None,
) -> pd.DataFrame:
    st.session_state.processed_data = processed_df
    st.session_state.scraped_content = scraped_content or {}
    return processed_df


# FUNCTION_CONTRACT: _build_pipeline_feedback
# Purpose: Create the shared Streamlit progress/status handles for pipeline workflows.
# Input: run_id (str)
# Output: Tuple[Any, Any, str] - progress bar, status text, and run prefix
# Side Effects: Creates Streamlit progress/status placeholders.
# Business Rules: Run prefix is empty when no run_id is provided.
# Failure Modes: never raises.
def _build_pipeline_feedback(run_id: str) -> Tuple[Any, Any, str]:
    progress_bar = st.progress(0)
    status_text = st.empty()
    run_prefix = f"[run {run_id}] " if run_id else ""
    return progress_bar, status_text, run_prefix


# FUNCTION_CONTRACT: _store_tupled_keyword_candidate_state
# Purpose: Convert staged URL keyword mappings into candidate state and persist it in Streamlit session state.
# Input: url_to_keywords (Dict[str, List[str]]), run_id (str)
# Output: List[KeywordCandidate]
# Side Effects: Updates staged keyword candidate session state keys.
# Business Rules: Preserves source URL order and keyword order within each URL.
# Failure Modes: never raises.
def _store_tupled_keyword_candidate_state(
    url_to_keywords: Dict[str, List[str]],
    run_id: str = "",
) -> List[KeywordCandidate]:
    candidates: List[KeywordCandidate] = []
    active_source_urls: List[str] = []
    for source_url, keywords in url_to_keywords.items():
        active_source_urls.append(source_url)
        for kw in keywords:
            candidates.append(
                KeywordCandidateRecord(
                    keyword=kw,
                    source_url=source_url,
                    source_type=SOURCE_LLM_EXTRACTION,
                    source_stage=source_url,
                    selection_prefix="",
                )
            )

    st.session_state[SESSION_KEY_STAGED_KEYWORDS] = candidates
    st.session_state[SESSION_KEY_LAST_EXTRACTION_RUN_ID] = run_id
    st.session_state[SESSION_KEY_ACTIVE_SOURCE_URLS] = active_source_urls
    return candidates


# FUNCTION_CONTRACT: _finalize_keyword_ads_workflow
# Purpose: Deduplicate extracted keywords, fetch Ads metrics, and finalize the shared Ads workflow tail.
# Input: all_keywords (List[str]), keyword_to_url (Dict[str, str]), location_id (str), language_id (str), currency_code (str), scraped_content (Dict[str, str]), progress_bar, status_text, run_prefix (str), completion_log_message (str), force_refresh (bool)
# Output: Optional[pd.DataFrame]
# Side Effects: Sends warnings/progress updates, queries Google Ads, and stores processed data.
# Business Rules: Empty keyword lists short-circuit with the existing no-keywords warning.
# Failure Modes: Returns None when no keywords remain after deduplication.
def _finalize_keyword_ads_workflow(
    all_keywords: List[str],
    keyword_to_url: Dict[str, str],
    location_id: str,
    language_id: str,
    currency_code: str,
    scraped_content: Dict[str, str],
    progress_bar: Any,
    status_text: Any,
    run_prefix: str,
    completion_log_message: str,
    force_refresh: bool = False,
) -> Optional[pd.DataFrame]:
    if not all_keywords:
        st.warning(_format_pipeline_message("pipeline_no_keywords_found"))
        progress_bar.progress(1.0)
        return None

    ads_handler = GoogleAdsHandler(
        location_id=location_id,
        language_id=language_id,
        target_currency_code=currency_code,
    )
    metrics_df = _get_keyword_metrics_with_optional_cache(
        ads_handler,
        all_keywords,
        force_refresh=force_refresh,
    )

    return _finalize_keyword_metrics_workflow(
        all_keywords=all_keywords,
        keyword_to_url=keyword_to_url,
        metrics_df=metrics_df,
        currency_code=currency_code,
        scraped_content=scraped_content,
        progress_bar=progress_bar,
        status_text=status_text,
        run_prefix=run_prefix,
        completion_log_message=completion_log_message,
    )


# FUNCTION_CONTRACT: _finalize_keyword_source_workflow
# Purpose: Collapse source keywords into Ads-ready keywords and delegate to the shared finalizer.
# Input: source_keywords (Dict[str, List[str]]), location_id (str), language_id (str), currency_code (str), scraped_content (Dict[str, str]), progress_bar, status_text, run_prefix (str), completion_log_message (str), force_refresh (bool)
# Output: Optional[pd.DataFrame]
# Side Effects: Deduplicates keyword sources and reuses the shared Ads finalizer.
# Business Rules: Preserves the same no-keywords behavior as the downstream finalizer.
# Failure Modes: Returns None when no keywords remain after deduplication.
def _finalize_keyword_source_workflow(
    source_keywords: Dict[str, List[str]],
    **workflow_kwargs: Any,
) -> Optional[pd.DataFrame]:
    location_id = workflow_kwargs.get("location_id", "")
    language_id = workflow_kwargs.get("language_id", "")
    currency_code = workflow_kwargs.get("currency_code", "")
    scraped_content = workflow_kwargs.get("scraped_content", {})
    progress_bar = workflow_kwargs.get("progress_bar")
    status_text = workflow_kwargs.get("status_text")
    run_prefix = workflow_kwargs.get("run_prefix", "")
    completion_log_message = workflow_kwargs.get("completion_log_message", "")
    force_refresh = workflow_kwargs.get("force_refresh", False)

    _processed_source_keywords, all_keywords, keyword_to_url = _process_keyword_sources_for_ads(
        source_keywords
    )
    return _finalize_keyword_ads_workflow(
        all_keywords=all_keywords,
        keyword_to_url=keyword_to_url,
        location_id=location_id,
        language_id=language_id,
        currency_code=currency_code,
        scraped_content=scraped_content,
        progress_bar=progress_bar,
        status_text=status_text,
        run_prefix=run_prefix,
        completion_log_message=completion_log_message,
        force_refresh=force_refresh,
    )


# FUNCTION_CONTRACT: _finalize_serp_results_workflow
# Purpose: Normalize common SERP result finalization, warnings, and success handling.
# Input: rows (List[Dict[str, object]]), related_data (List[Dict[str, object]]), failed_keywords (List[Tuple[str, str]]), progress_bar, status_text, run_prefix (str), result_columns (List[str]), completion_log_message (str), on_success (Callable[[pd.DataFrame], None])
# Output: Optional[pd.DataFrame]
# Side Effects: Updates related-data session state, warnings, progress, and status.
# Business Rules: Empty result sets keep the existing no-results handling.
# Failure Modes: Returns None when no SERP rows are available.
def _finalize_serp_results_workflow(
    rows: List[Dict[str, object]],
    related_data: List[Dict[str, object]],
    failed_keywords: List[Tuple[str, str]],
    progress_bar: Any,
    status_text: Any,
    run_prefix: str,
    result_columns: List[str],
    completion_log_message: str,
    on_success: Callable[[pd.DataFrame], None],
) -> Optional[pd.DataFrame]:
    for keyword, error in failed_keywords:
        logger.warning(f"{run_prefix}SERP query failed for '{keyword}': {error}")

    st.session_state.serp_related_data = related_data

    if failed_keywords and not rows:
        st.warning(f"Some keywords failed: {', '.join(k for k, _ in failed_keywords[:5])}")

    if not rows:
        st.info(_format_pipeline_message("serp_no_results"))
        progress_bar.progress(1.0, text=_format_pipeline_message("pipeline_done"))
        status_text.text(_format_pipeline_message("serp_no_results"))
        return None

    serp_df = pd.DataFrame(rows, columns=result_columns)
    on_success(serp_df)

    progress_bar.progress(1.0, text=_format_pipeline_message("pipeline_done"))
    status_text.success(_format_pipeline_message("serp_analysis_complete"))
    logger.info(f"{run_prefix}{completion_log_message}")
    return serp_df


# block_pipeline_seo_context_from_selection: URL_LLM -> SEO handoff context builder
# Semantic block: Turns the (keyword, source_url) selection tuples from the URL_LLM
# Stage-1 candidate selector into the processed_data + selected_kw_by_url inputs
# that render_seo_generation expects, so the user can generate an SEO text right
# after page scraping — alongside the existing Ads / SERP / Trends handoffs.


# FUNCTION_CONTRACT: prepare_seo_context_from_selection
# Purpose: Build the SEO-generation inputs (selected_kw_by_url mapping + a processed_data DataFrame carrying the canonical RESULT_COLUMNS) from the (keyword, source_url) selection tuples produced by the URL_LLM Stage-1 candidate selector, without requiring a prior Ads run.
# Input: selected_tuples (List[tuple[str, str]]) — (keyword, source_url) pairs; run_id (str) — used only for log scoping
# Output: Optional[tuple[Dict[str, List[str]], int]] — (selected_kw_by_url, total_selected) or None when the selection is empty
# Side Effects: Sets st.session_state.processed_data to a DataFrame covering every selected keyword (extending, not clobbering, an existing processed_data that already carries real Ads metrics); leaves st.session_state.scraped_content untouched
# Business Rules: Dedupes (keyword, source_url) pairs; preserves existing processed_data rows and their metrics, adding only the selected keywords that are missing; every synthesized row is normalized to RESULT_COLUMNS so downstream render_seo_generation / render_seo_results filters and exports don't KeyError; Avg Monthly Searches defaults to None (N/A) for keywords without Ads metrics
# Failure Modes: Returns None for an empty selection; otherwise never returns None
# LINKS: requirements.xml#UC-001, app.py (URL_LLM selector handoff), components/results.py:render_seo_generation
def prepare_seo_context_from_selection(
    selected_tuples: List[tuple],
    run_id: str = "",
) -> Optional[tuple]:
    if not selected_tuples:
        return None

    run_prefix = f"[run {run_id}] " if run_id else ""

    # Collapse (keyword, source_url) tuples into {url: [keywords]}, deduped and
    # order-stable.
    selected_kw_by_url: Dict[str, List[str]] = {}
    seen_pairs: set = set()
    for pair in selected_tuples:
        keyword = str(pair[0]).strip()
        source_url = str(pair[1]).strip()
        if not keyword or not source_url:
            continue
        key = (keyword, source_url)
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        selected_kw_by_url.setdefault(source_url, []).append(keyword)

    if not selected_kw_by_url:
        return None

    total_selected = sum(len(kws) for kws in selected_kw_by_url.values())

    # Build/extend processed_data with the canonical RESULT_COLUMNS so
    # render_seo_generation (filters on Source URL + Keyword, reads
    # Avg Monthly Searches) and render_seo_results exports don't KeyError.
    existing_df = st.session_state.get("processed_data")
    base_rows: List[Dict[str, object]] = []
    if isinstance(existing_df, pd.DataFrame) and not existing_df.empty:
        base_rows = existing_df.to_dict(orient="records")

    existing_keys: set = set()
    for row in base_rows:
        existing_keys.add((str(row.get("Keyword", "")), str(row.get("Source URL", ""))))

    added = 0
    for source_url, keywords in selected_kw_by_url.items():
        for keyword in keywords:
            if (keyword, source_url) in existing_keys:
                continue
            existing_keys.add((keyword, source_url))
            new_row: Dict[str, object] = {col: None for col in RESULT_COLUMNS}
            new_row["Keyword"] = keyword
            new_row["Source URL"] = source_url
            # Avg Monthly Searches stays None (renders as N/A) until Ads runs.
            base_rows.append(new_row)
            added += 1

    if added:
        logger.info(
            f"{run_prefix}SEO context prepared from selection: "
            f"{added} keyword(s) added to processed_data, "
            f"{total_selected} total selected across {len(selected_kw_by_url)} URL(s)"
        )

    normalized_df = _ensure_result_columns(pd.DataFrame(base_rows), "")
    st.session_state.processed_data = normalized_df

    return selected_kw_by_url, total_selected


# Purpose:  generate keywords with optional cache implementation
def _generate_keywords_with_optional_cache(
    llm: Any,
    *,
    text: str,
    provider: str,
    model: str,
    max_keywords: int,
    custom_prompt: str = "",
    force_refresh: bool = False,
) -> List[str]:
    try:
        return llm.generate_keywords(
            text=text,
            provider=provider,
            model=model,
            max_keywords=max_keywords,
            custom_prompt=custom_prompt,
            force_refresh=force_refresh,
        )
    except TypeError as exc:
        if "force_refresh" not in str(exc):
            raise
        return llm.generate_keywords(
            text=text,
            provider=provider,
            model=model,
            max_keywords=max_keywords,
            custom_prompt=custom_prompt,
        )


# Purpose:  get keyword metrics with optional cache implementation
def _get_keyword_metrics_with_optional_cache(
    ads_handler: Any,
    keywords: List[str],
    force_refresh: bool = False,
) -> pd.DataFrame:
    try:
        return ads_handler.get_keyword_metrics(
            keywords,
            force_refresh=force_refresh,
        )
    except TypeError as exc:
        if "force_refresh" not in str(exc):
            raise
        return ads_handler.get_keyword_metrics(keywords)


# Purpose:  get keyword ideas with optional cache implementation
def _get_keyword_ideas_with_optional_cache(
    ads_handler: Any,
    seed_keywords: List[str],
    *,
    page_url: Optional[str] = None,
    source_url: Optional[str] = None,
    force_refresh: bool = False,
) -> pd.DataFrame:
    try:
        return ads_handler.get_keyword_ideas(
            seed_keywords,
            page_url=page_url,
            source_url=source_url,
            force_refresh=force_refresh,
        )
    except TypeError as exc:
        if "force_refresh" not in str(exc):
            raise
        return ads_handler.get_keyword_ideas(
            seed_keywords,
            page_url=page_url,
            source_url=source_url,
        )


# FUNCTION_CONTRACT: _render_invalid_url_details
# Purpose: Display skipped invalid URLs in a Streamlit expander
# Input: invalid_results (List[object]) — objects with .url and .error attributes
# Output: (none)
# Side Effects: renders Streamlit UI elements
# Business Rules: returns immediately if list is empty
# Failure Modes: never raises
# LINKS: requirements.xml#UC-001
def _render_invalid_url_details(invalid_results: List[object]) -> None:
    if not invalid_results:
        return

    with st.expander(
        _format_pipeline_message(
            "pipeline_invalid_urls_skipped", count=len(invalid_results)
        )
    ):
        for result in invalid_results:
            st.write(f"{result.url}: {result.error}")


# FUNCTION_CONTRACT: _validated_urls_for_pipeline
# Purpose: Validate URLs and render invalid URL details in one step.
# Input: urls (List[str])
# Output: List[str] - valid URLs only
# Side Effects: Renders invalid URL details through Streamlit
# Business Rules: Returns only validated URLs; invalid entries are reported to the UI.
# Failure Modes: never raises; returns empty list when nothing validates.
# LINKS: requirements.xml#UC-002
def _validated_urls_for_pipeline(urls: List[str]) -> List[str]:
    valid_urls, invalid_results = URLValidator.validate_urls(urls)
    _render_invalid_url_details(invalid_results)
    return valid_urls


# FUNCTION_CONTRACT: _validated_urls_or_error
# Purpose: Validate URLs and report the standard empty-input error in one step.
# Input: urls (List[str]), error_key (str = "pipeline_no_valid_urls")
# Output: Optional[List[str]] - validated URLs or None when none remain.
# Side Effects: Renders invalid URL details and the standard Streamlit error.
# Business Rules: Centralizes the empty-URL guard for URL workflows.
# Failure Modes: never raises; returns None when no valid URLs remain.
# LINKS: requirements.xml#UC-002
def _validated_urls_or_error(
    urls: List[str],
    error_key: str = "pipeline_no_valid_urls",
) -> Optional[List[str]]:
    valid_urls = _validated_urls_for_pipeline(urls)
    if not valid_urls:
        st.error(_format_pipeline_message(error_key))
        return None
    return valid_urls


# FUNCTION_CONTRACT: _prompt_for_valid_urls
# Purpose: Emit the standard validation status text and return validated URLs or None.
# Input: status_text (Any), urls (List[str]), error_key (str = "pipeline_no_valid_urls")
# Output: Optional[List[str]]
# Side Effects: Updates the status text and delegates to the URL validator helper.
# Business Rules: Keeps the common validation prompt consistent across URL workflows.
# Failure Modes: never raises.
# LINKS: requirements.xml#UC-002
def _prompt_for_valid_urls(
    status_text: Any,
    urls: List[str],
    error_key: str = "pipeline_no_valid_urls",
) -> Optional[List[str]]:
    status_text.text(_format_pipeline_message("pipeline_validating_urls"))
    return _validated_urls_or_error(urls, error_key=error_key)


# FUNCTION_CONTRACT: _normalize_keyword_seed_input
# Purpose: Strip whitespace and deduplicate manual keyword seed inputs preserving first-occurrence order
# Input: seed_keywords (List[str])
# Output: List[str] — cleaned unique keywords
# Side Effects: (none)
# Business Rules: skips empty strings after stripping
# Failure Modes: never raises
# LINKS: requirements.xml#UC-003
def _normalize_keyword_seed_input(seed_keywords: List[str]) -> List[str]:
    normalized: List[str] = []
    seen = set()
    for keyword in seed_keywords:
        cleaned = str(keyword).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


# FUNCTION_CONTRACT: _append_keyword_group
# Purpose: Append a cleaned keyword group and advance the group id when content exists.
# Input: groups (List[Dict[str, object]]), group_id (int), keywords (List[str])
# Output: int - updated group id after appending a non-empty group.
# Side Effects: Mutates groups when cleaned keywords are available.
# Business Rules: Empty or whitespace-only keywords are discarded.
# Failure Modes: never raises.
# LINKS: PLAN 15-01 Task 2
def _append_keyword_group(
    groups: List[Dict[str, object]],
    group_id: int,
    keywords: List[str],
) -> int:
    cleaned_keywords = [kw.strip() for kw in keywords if kw and str(kw).strip()]
    if cleaned_keywords:
        group_id += 1
        groups.append({"group_id": group_id, "keywords": cleaned_keywords})
    return group_id


# FUNCTION_CONTRACT: _split_keywords_from_text
# Purpose: Split a delimited keyword string into cleaned keyword tokens.
# Input: text (str)
# Output: List[str]
# Side Effects: none
# Business Rules: Splits on comma, semicolon, or pipe; drops empty tokens.
# Failure Modes: never raises.
# LINKS: PLAN 15-01 Task 2
def _split_keywords_from_text(text: str) -> List[str]:
    return [kw.strip() for kw in re.split(r"[,;|]", str(text).strip()) if kw.strip()]


# FUNCTION_CONTRACT: parse_keyword_groups
# Purpose: Parse textarea/TXT input into keyword groups where each non-empty line is one group
# Input: lines (List[str]) — raw lines from textarea or TXT file
# Output: List[Dict] — list of {"group_id": int, "keywords": List[str]}
# Side Effects: (none)
# Business Rules: comma/semicolon/pipe split within a line; "---" lines ignored; empty lines skipped
# Failure Modes: never raises; returns empty list for empty input
# LINKS: PLAN 15-01 Task 2
def parse_keyword_groups(lines: List[str]) -> List[Dict[str, object]]:

    groups: List[Dict[str, object]] = []
    group_id = 0

    for line in lines:
        text = str(line).strip()
        if not text or text == "---":
            continue
        group_id = _append_keyword_group(groups, group_id, _split_keywords_from_text(text))

    return groups


# FUNCTION_CONTRACT: _build_keyword_groups_from_csv_rows
# Purpose: Parse CSV rows into keyword groups respecting header presence
# Input: rows (List[object]), has_header (bool = True)
# Output: List[Dict[str, object]] - list of {"group_id": int, "keywords": List[str]}
# Side Effects: (none)
# Business Rules: Uses a 'keywords' column when present; otherwise treats non-empty cells in a row as one group.
# Failure Modes: never raises; returns empty list for empty input
# LINKS: PLAN 15-01 Task 2
def _build_keyword_groups_from_csv_rows(
    rows: List[object],
    has_header: bool = True,
) -> List[Dict[str, object]]:
    groups: List[Dict[str, object]] = []
    group_id = 0

    if not rows:
        return groups

    def _keywords_from_mapping_row(row: Dict[str, object], kw_col: Optional[str]) -> List[str]:
        if kw_col:
            return _split_keywords_from_text(row.get(kw_col, ""))
        return [str(value).strip() for value in row.values() if value and str(value).strip()]

    first_row = rows[0]

    if isinstance(first_row, dict):
        kw_col = None
        for key in first_row.keys():
            if key and str(key).strip().lower() == "keywords":
                kw_col = key
                break

        if has_header or kw_col:
            for row in rows:
                if isinstance(row, dict):
                    group_id = _append_keyword_group(
                        groups,
                        group_id,
                        _keywords_from_mapping_row(row, kw_col),
                    )
            return groups

        for row in rows:
            if isinstance(row, dict):
                group_id = _append_keyword_group(
                    groups,
                    group_id,
                    _keywords_from_mapping_row(row, None),
                )
        return groups

    if not has_header and isinstance(first_row, (list, tuple)):
        for row in rows:
            if isinstance(row, (list, tuple)):
                group_id = _append_keyword_group(
                    groups,
                    group_id,
                    [str(cell).strip() for cell in row if cell and str(cell).strip()],
                )
        return groups

    return groups


# FUNCTION_CONTRACT: parse_keyword_groups_from_csv_rows
# Purpose: Parse CSV rows into keyword groups respecting header presence
# Input: rows (List[Union[Dict, List]]) – CSV rows; has_header (bool) – whether first row is header
# Output: List[Dict] – list of {"group_id": int, "keywords": List[str]}
# Side Effects: (none)
# Business Rules: if 'keywords' column exists, split that cell per row; otherwise treat non-empty cells as one group
# Failure Modes: never raises; returns empty list for empty input
# LINKS: PLAN 15-01 Task 2
# Rationale: If a 'keywords' column exists, split that cell per row. If no header exists, treat non-empty cells in each row as one keyword group.
def parse_keyword_groups_from_csv_rows(
    rows: List[object], has_header: bool = True
) -> List[Dict[str, object]]:
    return _build_keyword_groups_from_csv_rows(rows, has_header=has_header)


# FUNCTION_CONTRACT: prepare_urls_for_seo
# Purpose: Validate and scrape URLs for the URL-seed workflow, storing results in session state for later SEO generation
# Input: urls (List[str]), run_id (str)
# Output: Dict[str, str] — mapping of URL to scraped text content
# Side Effects: renders Streamlit progress bar and status messages; stores scraped_content in session state
# Business Rules: validates URLs before scraping; returns empty dict on no valid URLs or no scraped content
# Failure Modes: logs warnings on scraping failures; returns empty dict
# LINKS: requirements.xml#UC-002
def prepare_urls_for_seo(
    urls: List[str],
    run_id: str = "",
) -> Dict[str, str]:
    progress_bar = st.progress(0)
    status_text = st.empty()
    run_prefix = f"[run {run_id}] " if run_id else ""

    valid_urls = _prompt_for_valid_urls(status_text, urls)
    if valid_urls is None:
        return {}

    status_text.text(_format_pipeline_message("pipeline_scraping_content"))
    # url_llm scrape path: requests first, then cloakbrowser fallback for URLs that failed on
    # captcha / Cloudflare Turnstile / 403 (toggle: scraper.content_browser_fallback_enabled).
    scraped_data = WebScraper.scrape_urls_with_browser_fallback(
        valid_urls,
        progress_callback=lambda progress, message: progress_bar.progress(
            progress, text=message
        ),
    )
    scraped_content = {item.url: item.text for item in scraped_data if item.success}
    st.session_state.scraped_content = scraped_content
    if not scraped_content:
        progress_bar.progress(1.0, text=_format_pipeline_message("pipeline_done"))
        warning_message = _format_pipeline_message("pipeline_no_content_scraped")
        status_text.text(warning_message)
        st.warning(warning_message)
        logger.warning(f"{run_prefix}Scraping completed without usable content")
        return {}
    progress_bar.progress(1.0, text=_format_pipeline_message("pipeline_done"))
    status_text.success(_format_pipeline_message("pipeline_analysis_complete"))
    logger.info(f"{run_prefix}Prepared {len(scraped_content)} URL(s) for SEO flow")
    return scraped_content



# FUNCTION_CONTRACT: _process_keyword_sources_for_ads
# Purpose: Process, deduplicate, and index keyword sources for Ads workflows.
# Input: source_keywords (Dict[str, List[str]])
# Output: Tuple[Dict[str, List[str]], List[str], Dict[str, str]]
# Side Effects: (none)
# Business Rules: Preserves first source URL for each keyword after deduplication.
# Failure Modes: never raises.
# LINKS: requirements.xml#UC-002
def _process_keyword_sources_for_ads(
    source_keywords: Dict[str, List[str]],
) -> Tuple[Dict[str, List[str]], List[str], Dict[str, str]]:
    processed_source_keywords: Dict[str, List[str]] = {}
    for url, keywords in source_keywords.items():
        processed_source_keywords[url] = KeywordProcessor.process_keywords(keywords)

    unique_map = KeywordProcessor.deduplicate_across_sources(processed_source_keywords)

    all_keywords: List[str] = []
    keyword_to_url: Dict[str, str] = {}
    for url, keywords in unique_map.items():
        for keyword in keywords:
            all_keywords.append(keyword)
            keyword_to_url[keyword] = url

    return processed_source_keywords, all_keywords, keyword_to_url


# FUNCTION_CONTRACT: _extract_keywords_from_source_items
# Purpose: Extract keywords from scraped source items using a shared progress/logging flow.
# Input: source_items (List[Tuple[str, str, bool]]), llm (LLMHandler), provider/model/max_keywords/custom_prompt/force_refresh, progress_bar, progress_start, progress_span, run_prefix
# Output: Dict[str, List[str]]
# Side Effects: Updates progress, logs scrape failures, and stores extracted keywords by source URL.
# Business Rules: Failed source items are skipped; successful sources preserve their original URL key.
# Failure Modes: never raises.
# LINKS: requirements.xml#UC-001, requirements.xml#UC-005
def _extract_keywords_from_source_items(
    source_items: List[Tuple[str, str, bool]],
    llm: LLMHandler,
    provider: str,
    model: str,
    max_keywords: int,
    keyword_prompt: str,
    force_refresh: bool,
    progress_bar: Any,
    progress_start: float,
    progress_span: float,
    run_prefix: str,
) -> Dict[str, List[str]]:
    source_keywords: Dict[str, List[str]] = {}
    total_items = len(source_items)
    if not total_items:
        return source_keywords

    for index, (url, text, success) in enumerate(source_items):
        progress_bar.progress(
            progress_start + ((index / total_items) * progress_span),
            text=_format_pipeline_message(
                "pipeline_analyzing_url",
                idx=index + 1,
                total=total_items,
                url=url,
            ),
        )
        if not success:
            logger.warning(f"{run_prefix}Skipping LLM for failed scrape: {url}")
            continue

        keywords = _generate_keywords_with_optional_cache(
            llm,
            text=text,
            provider=provider,
            model=model,
            max_keywords=max_keywords,
            custom_prompt=keyword_prompt,
            force_refresh=force_refresh,
        )
        if keywords:
            source_keywords[url] = keywords
            logger.info(
                f"{run_prefix}Extracted {len(keywords)} keywords from {url}"
            )

    return source_keywords


# FUNCTION_CONTRACT: _source_items_from_scraped_data
# Purpose: Convert scraped result objects into the tuple shape used by the shared keyword extraction helper.
# Input: scraped_data (List[object])
# Output: List[Tuple[str, str, bool]]
# Side Effects: none
# Business Rules: Preserves URL, text, and success flag order from the scraped results.
# Failure Modes: never raises.
# LINKS: requirements.xml#UC-001, requirements.xml#UC-005
def _source_items_from_scraped_data(
    scraped_data: List[Any],
) -> List[Tuple[str, str, bool]]:
    return [(item.url, item.text, item.success) for item in scraped_data]


# FUNCTION_CONTRACT: _finalize_keyword_metrics_workflow
# Purpose: Build, store, and report the final keyword metrics DataFrame.
# Input: all_keywords (List[str]), keyword_to_url (Dict[str, str]), metrics_df (Optional[pd.DataFrame]), currency_code (str), scraped_content (Dict[str, str]), progress_bar (Any), status_text (Any), run_prefix (str), completion_log_message (str)
# Output: pd.DataFrame
# Side Effects: Stores processed data, updates progress, and emits completion logging.
# Business Rules: Preserves the canonical result-column merge behavior used by keyword extraction workflows.
# Failure Modes: never raises.
# LINKS: requirements.xml#UC-001, requirements.xml#UC-005
def _finalize_keyword_metrics_workflow(
    all_keywords: List[str],
    keyword_to_url: Dict[str, str],
    metrics_df: Optional[pd.DataFrame],
    currency_code: str,
    scraped_content: Dict[str, str],
    progress_bar: Any,
    status_text: Any,
    run_prefix: str,
    completion_log_message: str,
) -> pd.DataFrame:
    status_text.text(
        _format_pipeline_message(
            "pipeline_fetching_metrics",
            count=len(all_keywords),
        )
    )
    progress_bar.progress(
        0.8,
        text=_format_pipeline_message("pipeline_querying_google_ads"),
    )
    base_df = pd.DataFrame(
        {
            "Keyword": all_keywords,
            "Source URL": [keyword_to_url[keyword] for keyword in all_keywords],
        }
    )
    merged_df = _merge_base_keywords_with_metrics(base_df, metrics_df, currency_code)
    _store_processed_data(merged_df, scraped_content=scraped_content)

    progress_bar.progress(1.0, text=_format_pipeline_message("pipeline_done"))
    status_text.success(_format_pipeline_message("pipeline_analysis_complete"))
    logger.info(f"{run_prefix}{completion_log_message}")
    return merged_df


# FUNCTION_CONTRACT: run_llm_keyword_stage_from_checkpoint
# Purpose: Regenerate keywords from cached scraped content without re-scraping URLs
# Input: scraped_content (Dict[str, str]), provider, model, max_keywords, location_id, language_id, currency_code, run_id, api settings
# Output: Optional[pd.DataFrame] - results dataframe
# Side Effects: Modifies st.session_state
# Business Rules: Fast path for re-extracting keywords with different LLM settings
# Failure Modes: Returns None if no content or LLM failure
# LINKS: requirements.xml#UC-005
def run_llm_keyword_stage_from_checkpoint(
    scraped_content: Dict[str, str],
    **workflow_kwargs: Any,
) -> Optional[pd.DataFrame]:
    provider = workflow_kwargs.get("provider", "")
    model = workflow_kwargs.get("model", "")
    max_keywords = workflow_kwargs.get("max_keywords", 0)
    location_id = workflow_kwargs.get("location_id", "")
    language_id = workflow_kwargs.get("language_id", "")
    currency_code = workflow_kwargs.get("currency_code", "")
    keyword_prompt = workflow_kwargs.get("keyword_prompt", "")
    api_timeout = workflow_kwargs.get("api_timeout")
    api_delay = workflow_kwargs.get("api_delay")
    api_retry_count = workflow_kwargs.get("api_retry_count")
    api_retry_delay = workflow_kwargs.get("api_retry_delay")
    run_id = workflow_kwargs.get("run_id", "")
    force_refresh = workflow_kwargs.get("force_refresh", False)

    progress_bar, status_text, run_prefix = _build_pipeline_feedback(run_id)

    if not scraped_content:
        st.warning(_format_pipeline_message("pipeline_no_keywords_found"))
        return None

    status_text.text(_format_pipeline_message("pipeline_extracting_keywords"))
    llm = LLMHandler(
        timeout_seconds=api_timeout,
        delay_between_requests_seconds=api_delay,
        retry_attempts=api_retry_count,
        retry_delay_seconds=api_retry_delay,
        run_label=run_id,
    )

    scraped_items = list(scraped_content.items())
    source_items = [(url, text, True) for url, text in scraped_items]
    source_keywords = _extract_keywords_from_source_items(
        source_items=source_items,
        llm=llm,
        provider=provider,
        model=model,
        max_keywords=max_keywords,
        keyword_prompt=keyword_prompt,
        force_refresh=force_refresh,
        progress_bar=progress_bar,
        progress_start=0.0,
        progress_span=1.0,
        run_prefix=run_prefix,
    )

    return _finalize_keyword_source_workflow(
        source_keywords,
        location_id=location_id,
        language_id=language_id,
        currency_code=currency_code,
        scraped_content=scraped_content,
        progress_bar=progress_bar,
        status_text=status_text,
        run_prefix=run_prefix,
        completion_log_message=(
            f"Checkpoint keyword regeneration completed for {len(scraped_content)} URL(s)"
        ),
        force_refresh=force_refresh,
    )


# FUNCTION_CONTRACT: run_url_seed_workflow
# Purpose: Generate keyword ideas directly from URL seeds via Google Ads without LLM extraction
# Input: urls (List[str]), location_id (str), language_id (str), currency_code (str), run_id (str)
# Output: Optional[pd.DataFrame] — keyword ideas with metrics; None if no valid URLs
# Side Effects: renders Streamlit progress; validates URLs; stores results in session state; logs progress
# Business Rules: validates URLs first; deduplicates results by Source URL/Keyword pair
# Failure Modes: returns None if no valid URLs; logs warnings on empty results
# LINKS: requirements.xml#UC-002, knowledge-graph.xml#MOD-003, PLAN 10-02 Task 6
def run_url_seed_workflow(
    urls: List[str],
    location_id: str,
    language_id: str,
    currency_code: str,
    run_id: str = "",
    force_refresh: bool = False,
) -> Optional[pd.DataFrame]:
    progress_bar = st.progress(0)
    status_text = st.empty()
    run_prefix = f"[run {run_id}] " if run_id else ""

    valid_urls = _prompt_for_valid_urls(status_text, urls)
    if valid_urls is None:
        return None

    status_text.text(_format_pipeline_message("pipeline_querying_google_ads"))
    ads_handler = GoogleAdsHandler(
        location_id=location_id,
        language_id=language_id,
        target_currency_code=currency_code,
    )
    idea_frames: List[pd.DataFrame] = []

    for index, url in enumerate(valid_urls):
        progress_bar.progress(
            index / len(valid_urls),
            text=_format_pipeline_message(
                "pipeline_analyzing_url",
                idx=index + 1,
                total=len(valid_urls),
                url=url,
            ),
        )
        ideas_df = _get_keyword_ideas_with_optional_cache(
            ads_handler,
            [],
            page_url=url,
            source_url=url,
            force_refresh=force_refresh,
        )
        if not ideas_df.empty:
            idea_frames.append(ideas_df)

    processed_df = (
        pd.concat(idea_frames, ignore_index=True)
        if idea_frames
        else _empty_results_df(currency_code)
    )
    processed_df = _ensure_result_columns(processed_df, currency_code)
    processed_df = processed_df.drop_duplicates(
        subset=["Source URL", "Keyword"], keep="first"
    ).reset_index(drop=True)

    progress_bar.progress(1.0, text=_format_pipeline_message("pipeline_done"))
    status_text.success(_format_pipeline_message("pipeline_analysis_complete"))
    logger.info(f"{run_prefix}URL seed workflow completed for {len(valid_urls)} URL(s)")
    return _store_processed_data(processed_df, scraped_content={})


# FUNCTION_CONTRACT: run_keyword_seed_workflow
# Purpose: Generate keyword ideas from manually entered keyword seeds via Google Ads Keyword Planner
# Input: seed_keywords (List[str]), location_id (str), language_id (str), currency_code (str), run_id (str), force_refresh (bool), restrict_to_input (bool)
# Output: Optional[pd.DataFrame] — keyword ideas with metrics; None if no valid seeds
# Side Effects: renders Streamlit progress; normalizes seeds; stores results in session state; logs progress
# Business Rules: normalizes and deduplicates seeds; limits to KEYWORD_SEED_SOURCE_URL as source; when restrict_to_input=True, drops Ads idea rows whose Keyword is not in the normalized input set (case-insensitive via normalize_keyword_for_lookup) so only the user-entered keywords survive
# Failure Modes: returns None if no valid seeds after normalization; returns an empty DataFrame (not None) when restrict_to_input drops every row
# LINKS: requirements.xml#UC-003, knowledge-graph.xml#MOD-003, PLAN 10-02 Task 6
def run_keyword_seed_workflow(
    seed_keywords: List[str],
    location_id: str,
    language_id: str,
    currency_code: str,
    run_id: str = "",
    force_refresh: bool = False,
    restrict_to_input: bool = False,
) -> Optional[pd.DataFrame]:
    progress_bar = st.progress(0)
    status_text = st.empty()
    normalized_keywords = _normalize_keyword_seed_input(seed_keywords)
    run_prefix = f"[run {run_id}] " if run_id else ""

    if not normalized_keywords:
        st.warning(_format_pipeline_message("pipeline_no_keywords_found"))
        return None

    status_text.text(_format_pipeline_message("pipeline_querying_google_ads"))
    ads_handler = GoogleAdsHandler(
        location_id=location_id,
        language_id=language_id,
        target_currency_code=currency_code,
    )
    progress_bar.progress(0.5, text=_format_pipeline_message("pipeline_querying_google_ads"))
    processed_df = _ensure_result_columns(
        _get_keyword_ideas_with_optional_cache(
            ads_handler,
            normalized_keywords,
            source_url=KEYWORD_SEED_SOURCE_URL,
            force_refresh=force_refresh,
        ),
        currency_code,
    )
    processed_df = processed_df.drop_duplicates(
        subset=["Source URL", "Keyword"], keep="first"
    ).reset_index(drop=True)

    if restrict_to_input:
        allowed = {normalize_keyword_for_lookup(k) for k in normalized_keywords}
        processed_df = processed_df.loc[
            processed_df["Keyword"].map(normalize_keyword_for_lookup).isin(allowed)
        ].reset_index(drop=True)
        logger.info(
            f"{run_prefix}restrict_to_input kept {len(processed_df)} of the Ads idea rows matching the input set"
        )

    progress_bar.progress(1.0, text=_format_pipeline_message("pipeline_done"))
    status_text.success(_format_pipeline_message("pipeline_analysis_complete"))
    logger.info(
        f"{run_prefix}Keyword seed workflow completed for {len(normalized_keywords)} seed keyword(s)"
    )
    return _store_processed_data(processed_df, scraped_content={})


# FUNCTION_CONTRACT: run_llm_url_workflow
# Purpose: Full URL→scrape→LLM keyword extraction→Google Ads metrics workflow
# Input: urls (List[str]), provider (str), model (str), max_keywords (int), location_id (str), language_id (str), currency_code (str), keyword_prompt (str), api settings, run_id (str), force_refresh (bool = False)
# Output: Optional[pd.DataFrame] — keywords with metrics; None if no valid URLs or no keywords extracted
# Side Effects: renders Streamlit progress bars and status messages; validates URLs; scrapes content; calls LLM and Ads API; stores results in session state; logs each step; uses cache lookup
# Business Rules: progress split across validation (0-10%), scraping (10-40%), LLM (40-70%), Ads metrics (80%), finalization; passes force_refresh to cached operations
# Failure Modes: returns None if no valid URLs or no keywords; logs warnings on scrape and LLM failures
# LINKS: requirements.xml#UC-001, requirements.xml#UC-002, knowledge-graph.xml#MOD-002, PLAN 10-02 Task 6
def run_llm_url_workflow(
    urls: List[str],
    provider: str,
    model: str,
    max_keywords: int,
    location_id: str,
    language_id: str,
    currency_code: str,
    keyword_prompt: str = "",
    api_timeout: Optional[int] = None,
    api_delay: Optional[int] = None,
    api_retry_count: Optional[int] = None,
    api_retry_delay: Optional[int] = None,
    run_id: str = "",
    force_refresh: bool = False,
) -> Optional[pd.DataFrame]:
    progress_bar, status_text, run_prefix = _build_pipeline_feedback(run_id)
    logger.info(f"{run_prefix}Starting analysis for {len(urls)} URL(s)")

    valid_urls = _prompt_for_valid_urls(status_text, urls)
    if valid_urls is None:
        return None

    status_text.text(_format_pipeline_message("pipeline_scraping_content"))
    # url_llm_ads scrape path: requests first, then cloakbrowser fallback for URLs that
    # hard-failed (403/timeout) or landed on a captcha / Cloudflare block page despite
    # success=True (toggle: scraper.content_browser_fallback_enabled). Without this a
    # site that 403-blocks the aiohttp scraper (e.g. shoptobi.com.ua) returns no keywords
    # at all because the failed scrape skips the LLM entirely.
    scraped_data = WebScraper.scrape_urls_with_browser_fallback(
        valid_urls,
        progress_callback=lambda progress, message: progress_bar.progress(
            0.1 + (progress * 0.3), text=message
        ),
    )

    status_text.text(_format_pipeline_message("pipeline_extracting_keywords"))
    llm = LLMHandler(
        timeout_seconds=api_timeout,
        delay_between_requests_seconds=api_delay,
        retry_attempts=api_retry_count,
        retry_delay_seconds=api_retry_delay,
        run_label=run_id,
    )

    scraped_content = {item.url: item.text for item in scraped_data if item.success}
    source_items = _source_items_from_scraped_data(scraped_data)
    source_keywords = _extract_keywords_from_source_items(
        source_items=source_items,
        llm=llm,
        provider=provider,
        model=model,
        max_keywords=max_keywords,
        keyword_prompt=keyword_prompt,
        force_refresh=force_refresh,
        progress_bar=progress_bar,
        progress_start=0.4,
        progress_span=0.3,
        run_prefix=run_prefix,
    )

    status_text.text(_format_pipeline_message("pipeline_processing_deduplicating"))
    return _finalize_keyword_source_workflow(
        source_keywords=source_keywords,
        location_id=location_id,
        language_id=language_id,
        currency_code=currency_code,
        scraped_content=scraped_content,
        progress_bar=progress_bar,
        status_text=status_text,
        run_prefix=run_prefix,
        completion_log_message="Analysis run completed successfully",
        force_refresh=force_refresh,
    )


# block_pipeline_cache_aware_wrappers: Cache integration for high-cost API calls
# Semantic block: Wraps SERP, Ads, LLM, and math calls with request_cache lookup/storage
# Phase 10 Task 6: Add cache-aware API call sites


# FUNCTION_CONTRACT: _serp_request_cache_key
# Purpose: Build normalized cache key for SERP requests
# Input: keywords (List[str]), serp_config (Optional[dict])
# Output: str - stable cache key
# Side Effects: calls build_cache_key with normalized params
# Business Rules: Includes provider, num_results, gl, hl, extra_params
# Failure Modes: returns empty string on error
# LINKS: PLAN 10-02 Task 6
def _serp_request_cache_key(
    keywords: List[str],
    serp_config: Optional[dict] = None,
) -> str:
    if not serp_config:
        serp_config = {}

    # Normalize and sort keywords for stable key
    normalized_keywords = sorted(
        str(k).lower().strip() for k in keywords if k and str(k).strip()
    )

    params = {
        "keywords": normalized_keywords,
        "provider": serp_config.get("provider", "serper_dev"),
        "num_results": serp_config.get("num_results", 10),
        "gl": serp_config.get("gl", "ua"),
        "hl": serp_config.get("hl", "uk"),
        "extra_params": {
            k: v for k, v in serp_config.items()
            if k in ("device", "search_type", "time_period", "google_domain", "location", "uule", "safe_search")
            and v not in (None, "", "any")
        },
    }

    return build_cache_key(
        kind="serp",
        provider=params["provider"],
        params=params,
    )


# Purpose:  serp result from payload implementation
def _serp_result_from_payload(payload: Any) -> SERPSearchResult:
    if isinstance(payload, SERPSearchResult):
        return payload
    if not isinstance(payload, dict):
        raise ValueError("cached SERP payload must be a dict")

    organic = [
        item
        if isinstance(item, SERPOrganicResult)
        else SERPOrganicResult(**item)
        for item in payload.get("organic", []) or []
        if isinstance(item, (dict, SERPOrganicResult))
    ]
    people_also_ask = [
        item
        if isinstance(item, SERPPeopleAlsoAsk)
        else SERPPeopleAlsoAsk(**item)
        for item in payload.get("people_also_ask", []) or []
        if isinstance(item, (dict, SERPPeopleAlsoAsk))
    ]
    knowledge_payload = payload.get("knowledge_graph")
    if isinstance(knowledge_payload, SERPKnowledgeGraph):
        knowledge_graph = knowledge_payload
    elif isinstance(knowledge_payload, dict):
        knowledge_graph = SERPKnowledgeGraph(**knowledge_payload)
    else:
        knowledge_graph = None

    return SERPSearchResult(
        keyword=str(payload.get("keyword", "")),
        organic=organic,
        related_searches=list(payload.get("related_searches", []) or []),
        people_also_ask=people_also_ask,
        knowledge_graph=knowledge_graph,
        provider=str(payload.get("provider", "")),
        success=bool(payload.get("success", True)),
        error=payload.get("error"),
    )


# Purpose:  serp results from cached payload implementation
def _serp_results_from_cached_payload(payload: Any) -> List[SERPSearchResult]:
    if not isinstance(payload, list):
        return []
    results: List[SERPSearchResult] = []
    for item in payload:
        try:
            results.append(_serp_result_from_payload(item))
        except Exception as exc:
            logger.warning(f"Failed to restore cached SERP result: {exc}")
            return []
    return results


# FUNCTION_CONTRACT: _serp_search_with_cache
# Purpose: Execute SERP search with cache lookup and storage
# Input: client (SERPClient), keywords (List[str]), force_refresh (bool), run_id (str), progress_callback
# Output: List[SERPSearchResult]
# Side Effects: logs cache hits, stores successful results in cache
# Business Rules: Check cache before API call, store result after success
# Failure Modes: returns failure results for all keywords on error
# LINKS: PLAN 10-02 Task 6
def _serp_search_with_cache(
    client,
    keywords: List[str],
    force_refresh: bool = False,
    run_id: str = "",
    progress_callback: Optional[Any] = None,
) -> List[SERPSearchResult]:
    run_prefix = f"[run {run_id}] " if run_id else ""

    # Build cache key from client config and keywords
    cache_key = _serp_request_cache_key(
        keywords,
        {
            "provider": client.provider,
            "num_results": client.num_results,
            "gl": client.gl,
            "hl": client.hl,
            **(client.extra_params or {}),
        },
    )

    # Check cache
    cached = request_cache.get(cache_key, force_refresh=force_refresh)
    if cached is not None:
        logger.info(
            f"{run_prefix}[GRACE:block_pipeline_cache_lookup:HIT] beliefState=serp_cache_hit kind=serp key={cache_key[:8]}... "
            f"hits={cached.get('cache_hit_count', 0)}"
        )
        payload = cached.get("result", {}).get("payload")
        cached_results = _serp_results_from_cached_payload(payload)
        if cached_results:
            if progress_callback:
                progress_callback(len(keywords), max(len(keywords), 1))
            return cached_results

    # Cache miss - execute API call
    logger.info(
        f"{run_prefix}[GRACE:block_pipeline_cache_lookup:MISS] beliefState=serp_cache_miss kind=serp key={cache_key[:8]}..."
    )

    results = client.search_batch(keywords, progress_callback=progress_callback)

    # Store successful results in cache
    if results and any(r.success for r in results):
        request_cache.set(
            kind="serp",
            cache_key=cache_key,
            request_params={"keywords": keywords},
            result=results,
            provider=client.provider,
        )

    return results


# FUNCTION_CONTRACT: _collect_serp_rows
# Purpose: Flatten SERP results into rows, related-query data, and failure tuples.
# Input: results (List[SERPSearchResult]), source_contexts (Optional[List[SourceContextKey]])
# Output: Tuple[List[Dict[str, object]], List[Dict[str, str]], List[Tuple[str, object]]]
# Side Effects: (none)
# Business Rules: Preserves the first source context when provided; keeps related-search and PAA rows separate.
# Failure Modes: never raises.
# LINKS: PLAN 09-04 Task 4
def _collect_serp_rows(
    results: List[SERPSearchResult],
    source_contexts: Optional[List[SourceContextKey]] = None,
) -> Tuple[List[Dict[str, object]], List[Dict[str, str]], List[Tuple[str, object]]]:
    rows: List[Dict[str, object]] = []
    related_data: List[Dict[str, str]] = []
    failed_keywords: List[Tuple[str, object]] = []

    for idx, result in enumerate(results):
        if not result.success:
            failed_keywords.append((result.keyword, result.error))
            continue

        source_url = EMPTY_SOURCE_URL
        if source_contexts and idx < len(source_contexts):
            source_url = normalize_source_url_for_lookup(source_contexts[idx][1])
        normalized_keyword = normalize_keyword_for_lookup(result.keyword)

        for organic_item in result.organic:
            row: Dict[str, object] = {
                "Keyword": result.keyword,
                "Position": organic_item.position,
                "Title": organic_item.title,
                "URL": organic_item.url,
                "Snippet": organic_item.snippet,
                "Displayed Link": organic_item.displayed_link,
                "Rich Snippet": organic_item.rich_snippet_text,
                "Provider": result.provider,
            }
            if source_contexts is not None:
                row["source_context_key"] = (normalized_keyword, source_url)
            rows.append(row)

        for related in result.related_searches:
            related_data.append(
                {
                    "Keyword": result.keyword,
                    "Related Query": related,
                    "Type": "related_search",
                }
            )
        for paa in result.people_also_ask:
            related_data.append(
                {
                    "Keyword": result.keyword,
                    "Related Query": paa.question,
                    "Type": "people_also_ask",
                }
            )

    return rows, related_data, failed_keywords


# FUNCTION_CONTRACT: _restore_serp_session_state
# Purpose: Restore the previous processed and related SERP state after a chained run.
# Input: previous_processed (Optional[pd.DataFrame]), previous_related (Optional[List[Dict[str, str]]])
# Output: None
# Side Effects: Restores or clears processed_data and serp_related_data in session state.
# Business Rules: Preserves existing state when available; clears keys otherwise.
# Failure Modes: never raises.
# LINKS: PLAN 09-04 Task 4
def _restore_serp_session_state(
    previous_processed: Optional[pd.DataFrame],
    previous_related: Optional[List[Dict[str, str]]],
) -> None:
    for key, value in (
        ("processed_data", previous_processed),
        ("serp_related_data", previous_related),
    ):
        if value is None:
            st.session_state.pop(key, None)
        else:
            st.session_state[key] = value


# FUNCTION_CONTRACT: _ads_request_cache_key
# Purpose: Build normalized cache key for Google Ads requests
# Input: keywords (List[str]), location_id (str), language_id (Union[str, List[str]]), target_currency_code (str)
# Output: str - stable cache key
# Side Effects: calls build_cache_key with normalized params
# Business Rules: Includes keywords, location, language, currency
# Failure Modes: returns empty string on error
# LINKS: PLAN 10-02 Task 6
def _ads_request_cache_key(
    keywords: List[str],
    location_id: str,
    language_id: str,
    target_currency_code: str,
) -> str:
    # Normalize keywords
    normalized_keywords = sorted(
        str(k).lower().strip() for k in keywords if k and str(k).strip()
    )

    # Normalize language_id (could be list or string)
    if isinstance(language_id, list):
        lang_str = ",".join(sorted(str(language) for language in language_id))
    else:
        lang_str = str(language_id)

    params = {
        "keywords": normalized_keywords,
        "location_id": str(location_id),
        "language_id": lang_str,
        "currency_code": str(target_currency_code).upper(),
    }

    return build_cache_key(
        kind="ads",
        provider="google_ads",
        params=params,
    )


# FUNCTION_CONTRACT: _llm_request_cache_key
# Purpose: Build normalized cache key for LLM keyword extraction
# Input: text_hash (str), provider (str), model (str), max_keywords (int), custom_prompt (str)
# Output: str - stable cache key
# Side Effects: calls build_cache_key with normalized params
# Business Rules: Uses text hash instead of full text for key size
# Failure Modes: returns empty string on error
# LINKS: PLAN 10-02 Task 6
def _llm_request_cache_key(
    text_hash: str,
    provider: str,
    model: str,
    max_keywords: int,
    custom_prompt: str = "",
) -> str:
    import hashlib

    return build_cache_key(
        kind="llm_extract",
        provider=str(provider).lower(),
        params={
            "text_hash": text_hash,
            "provider": str(provider).lower(),
            "model": str(model).lower(),
            "max_keywords": int(max_keywords),
            "prompt_hash": hashlib.sha256(custom_prompt.encode()).hexdigest()[:16]
            if custom_prompt
            else "",
        },
    )


# FUNCTION_CONTRACT: _llm_generate_request_cache_key
# Purpose: Build normalized cache key for LLM SEO text generation
# Input: text_hash (str), keywords_hash (str), provider (str), model (str), language (str), custom_prompt (str)
# Output: str - stable cache key
# Side Effects: calls build_cache_key with normalized params
# Business Rules: Uses hashes for text and keywords to keep key size reasonable
# Failure Modes: returns empty string on error
# LINKS: PLAN 10-02 Task 6
def _llm_generate_request_cache_key(
    text_hash: str,
    keywords_hash: str,
    provider: str,
    model: str,
    language: str,
    custom_prompt: str = "",
) -> str:
    import hashlib

    prompt_hash = ""
    if custom_prompt:
        prompt_hash = hashlib.sha256(custom_prompt.encode()).hexdigest()[:16]

    params = {
        "text_hash": text_hash,
        "keywords_hash": keywords_hash,
        "provider": str(provider).lower(),
        "model": str(model).lower(),
        "language": str(language).lower(),
        "prompt_hash": prompt_hash,
    }

    return build_cache_key(
        kind="llm_generate",
        provider=params["provider"],
        params=params,
    )


# FUNCTION_CONTRACT: _math_request_cache_key
# Purpose: Build normalized cache key for math analysis profiles
# Input: corpus_hash (str), analysis_type (str), config_overrides (dict)
# Output: str - stable cache key
# Side Effects: calls build_cache_key with normalized params
# Business Rules: Includes analysis type (ngram, tfidf, cooccurrence, intent)
# Failure Modes: returns empty string on error
# LINKS: PLAN 10-02 Task 6
def _math_request_cache_key(
    corpus_hash: str,
    analysis_type: str = "full",
    config_overrides: Optional[dict] = None,
) -> str:
    params = {
        "corpus_hash": corpus_hash,
        "analysis_type": str(analysis_type),
        "config": config_overrides or {},
    }

    return build_cache_key(
        kind="math",
        provider="local_analysis",
        params=params,
    )


# FUNCTION_CONTRACT: _crawl_request_cache_key
# Purpose: Build normalized cache key for crawl report
# Input: seed_urls (tuple[str, ...]), settings_items (tuple[tuple[str, Any], ...])
# Output: str - stable cache key
# Side Effects: calls build_cache_key with normalized params
# Business Rules: Uses same normalization as _cached_bounded_crawl
# Failure Modes: returns empty string on error
# LINKS: PLAN 10-02 Task 6
def _crawl_request_cache_key(
    seed_urls: tuple[str, ...],
    settings_items: tuple[tuple[str, Any], ...],
) -> str:
    # Sort URLs for stable key
    sorted_urls = tuple(sorted(seed_urls))

    params = {
        "seed_urls": sorted_urls,
        "settings": dict(settings_items),
    }

    return build_cache_key(
        kind="crawl",
        provider="local_crawler",
        params=params,
    )


# Purpose:  google trends request from settings implementation
def _google_trends_request_from_settings(
    keywords: List[str],
    trends_config: Optional[Dict[str, Any]] = None,
) -> GoogleTrendsRequest:
    return _canonical_trends_request_from_settings(keywords, trends_config)


# Purpose:  google trends result from payload implementation
def _google_trends_result_from_payload(payload: Any) -> Optional[GoogleTrendsResult]:
    return _canonical_restore_trends_result_from_payload(payload)


# Purpose: google trends result to tables implementation
def google_trends_result_to_tables(
    result: GoogleTrendsResult,
) -> Dict[str, pd.DataFrame]:
    request = result.request
    averages = dict(result.averages or {})
    if not averages and result.interest_over_time:
        averages = GoogleTrendsClient._calculate_averages(result.interest_over_time)

    averages_rows = [
        {
            "Keyword": keyword,
            "Average Interest": round(float(value), 2),
            "Geo": request.geo,
            "Timeframe": request.timeframe,
            "Provider": result.provider,
        }
        for keyword, value in sorted(averages.items())
    ]

    interest_rows: List[Dict[str, Any]] = []
    for point in result.interest_over_time:
        row: Dict[str, Any] = {
            "Time": point.time,
            "Formatted Time": point.formatted_time,
        }
        row.update(point.values)
        interest_rows.append(row)

    related_rows: List[Dict[str, Any]] = []
    related_groups = (
        ("query", "top", result.related_queries_top),
        ("query", "rising", result.related_queries_rising),
        ("topic", "top", result.related_topics_top),
        ("topic", "rising", result.related_topics_rising),
    )
    for item_type, rank_type, items in related_groups:
        for item in items:
            related_rows.append(
                {
                    "Related Query": item.label,
                    "Value": item.value,
                    "Type": item_type,
                    "Rank Type": rank_type,
                    "Source Keywords": ", ".join(item.source_keywords),
                }
            )

    region_rows = [
        {
            "Region": row.region,
            "Value": row.value,
            "Keyword": row.keyword,
        }
        for row in result.region_rows
    ]

    return {
        "averages": pd.DataFrame(averages_rows, columns=TRENDS_AVERAGE_COLUMNS),
        "interest": pd.DataFrame(interest_rows),
        "related": pd.DataFrame(related_rows, columns=TRENDS_RELATED_COLUMNS),
        "regions": pd.DataFrame(region_rows),
    }


# FUNCTION_CONTRACT: _run_trends_stage
# Purpose: Execute Google Trends analysis for a normalized keyword list and store results.
# Input: keywords (List[str]), trends_config (Optional[Dict[str, Any]]), run_prefix (str), force_refresh (bool)
# Output: Optional[GoogleTrendsResult]
# Side Effects: Stores google_trends_result and google_trends_tables in session state; renders progress.
# Business Rules: Filters URL-like inputs, respects the enabled flag, and keeps cache metadata logging.
# Failure Modes: Returns None if no keywords remain or Trends is disabled.
# LINKS: PLAN 10-02 Task 9
def _run_trends_stage(
    keywords: List[str],
    trends_config: Optional[Dict[str, Any]] = None,
    run_prefix: str = "",
    force_refresh: bool = False,
) -> Optional[GoogleTrendsResult]:
    normalized_keywords = _normalize_keyword_seed_input(keywords)
    trends_values = dict(trends_config or {})
    if not trends_values.get("enabled", True):
        st.warning(t("google_trends_disabled_warning"))
        return None

    trends_keywords = filter_serp_eligible_keywords(normalized_keywords)
    if len(trends_keywords) < len(normalized_keywords):
        logger.warning(
            f"{run_prefix}Filtered URL-like values from Google Trends input"
        )
    if not trends_keywords:
        st.warning(t("google_trends_keyword_warning"))
        return None

    progress_bar = st.progress(0)
    status_text = st.empty()
    status_text.text(t("google_trends_querying", count=len(trends_keywords)))
    orchestrator = TrendsOrchestrator(settings=trends_values)
    result = orchestrator.run_trends(
        trends_keywords,
        provider=trends_values.get("provider"),
        force_refresh=force_refresh,
        settings=trends_values,
    )

    cache_key = result.cache_metadata.get("cache_key", "")
    if result.cache_metadata.get("cache_hit"):
        logger.info(
            f"{run_prefix}[GRACE:block_pipeline_cache_lookup:HIT] beliefState=trends_cache_hit kind=trends "
            f"key={str(cache_key)[:8]} hits={result.cache_metadata.get('cache_hit_count', 0)}"
        )
    else:
        logger.info(
            f"{run_prefix}[GRACE:block_pipeline_cache_lookup:MISS] beliefState=trends_cache_miss kind=trends "
            f"key={str(cache_key)[:8]}"
        )

    tables = google_trends_result_to_tables(result)
    st.session_state.google_trends_result = result
    st.session_state.google_trends_tables = tables

    if result.failures and not result.has_data():
        st.warning(t("google_trends_no_results"))
    progress_bar.progress(1.0, text=t("pipeline_done"))
    status_text.success(t("google_trends_complete"))
    logger.info(
        f"{run_prefix}[GRACE:block_pipeline_trends_stage:STATE] beliefState=trends_stage_complete "
        f"Google Trends completed for {len(trends_keywords)} keyword(s)"
    )
    return result


# Purpose: run google trends workflow implementation
def run_google_trends_workflow(
    keywords: List[str],
    trends_config: Optional[Dict[str, Any]] = None,
    run_id: str = "",
    force_refresh: bool = False,
) -> Optional[GoogleTrendsResult]:
    run_prefix = f"[run {run_id}] " if run_id else ""
    return _run_trends_stage(
        keywords=keywords,
        trends_config=trends_config,
        run_prefix=run_prefix,
        force_refresh=force_refresh,
    )


# block_pipeline_serp_keyword_guard: Staged LLM URL keyword extraction without automatic Ads handoff
# Semantic block: Extract keywords from URLs via LLM and store as candidates for SERP/Ads gating


# FUNCTION_CONTRACT: run_llm_url_keyword_extraction_stage
# Purpose: Extract keywords from URLs via LLM without automatically calling Google Ads — stores candidates for gated SERP/Ads workflows
# Input: urls (List[str]), provider (str), model (str), max_keywords (int), keyword_prompt (str), api settings, run_id (str)
# Output: Optional[Dict[str, List[str]]] — mapping of source URL to extracted keywords; None if no valid URLs or no keywords extracted
# Side Effects: renders Streamlit progress bars and status messages; validates URLs; scrapes content; calls LLM; stores candidates in session state; logs each step
# Business Rules: progress split across validation (0-10%), scraping (10-50%), LLM (50-90%), finalization (90-100%); stores candidates with SOURCE_LLM_EXTRACTION type
# Failure Modes: returns None if no valid URLs or no keywords extracted; logs warnings on scrape and LLM failures
# LINKS: PLAN 08-01 Task 2
def run_llm_url_keyword_extraction_stage(
    urls: List[str],
    provider: str,
    model: str,
    max_keywords: int,
    keyword_prompt: str = "",
    api_timeout: Optional[int] = None,
    api_delay: Optional[int] = None,
    api_retry_count: Optional[int] = None,
    api_retry_delay: Optional[int] = None,
    run_id: str = "",
    force_refresh: bool = False,
) -> Optional[Dict[str, List[str]]]:
    progress_bar, status_text, run_prefix = _build_pipeline_feedback(run_id)
    logger.info(f"{run_prefix}Starting LLM keyword extraction for {len(urls)} URL(s)")

    valid_urls = _prompt_for_valid_urls(status_text, urls)
    if valid_urls is None:
        return None

    status_text.text(_format_pipeline_message("pipeline_scraping_content"))
    # url_llm scrape path: requests first, then cloakbrowser fallback for URLs that
    # hard-failed (403/timeout) or landed on a captcha / Cloudflare block page. See
    # run_llm_url_workflow for the same wiring and the rationale.
    scraped_data = WebScraper.scrape_urls_with_browser_fallback(
        valid_urls,
        progress_callback=lambda progress, message: progress_bar.progress(
            0.1 + (progress * 0.4), text=message
        ),
    )

    status_text.text(_format_pipeline_message("pipeline_extracting_keywords"))
    llm = LLMHandler(
        timeout_seconds=api_timeout,
        delay_between_requests_seconds=api_delay,
        retry_attempts=api_retry_count,
        retry_delay_seconds=api_retry_delay,
        run_label=run_id,
    )

    source_items = _source_items_from_scraped_data(scraped_data)
    source_keywords = _extract_keywords_from_source_items(
        source_items=source_items,
        llm=llm,
        provider=provider,
        model=model,
        max_keywords=max_keywords,
        keyword_prompt=keyword_prompt,
        force_refresh=force_refresh,
        progress_bar=progress_bar,
        progress_start=0.5,
        progress_span=0.4,
        run_prefix=run_prefix,
    )

    status_text.text(_format_pipeline_message("pipeline_processing_deduplicating"))
    processed_source_keywords: Dict[str, List[str]] = {}
    for url, keywords in source_keywords.items():
        processed_source_keywords[url] = KeywordProcessor.process_keywords(keywords)

    if not processed_source_keywords:
        st.warning(_format_pipeline_message("pipeline_no_keywords_found"))
        progress_bar.progress(1.0)
        return None

    # Store scraped content for potential SEO generation
    scraped_content = {item.url: item.text for item in scraped_data if item.success}
    st.session_state.scraped_content = scraped_content

    # Store keyword candidates for SERP/Ads gating
    selection_prefix = f"llm_extract_{run_id}"
    for url, keywords in processed_source_keywords.items():
        store_keyword_candidates(
            keywords=keywords,
            source_url=url,
            source_type=SOURCE_LLM_EXTRACTION,
            selection_prefix=selection_prefix,
        )

    progress_bar.progress(1.0, text=_format_pipeline_message("pipeline_done"))
    status_text.success(_format_pipeline_message("pipeline_analysis_complete"))
    logger.info(f"{run_prefix}LLM extraction stage completed for {len(processed_source_keywords)} URL(s)")
    return processed_source_keywords


# block_pipeline_phase9_staged_extraction: Staged URL LLM extraction with tupled output (M1 amendment)
# Semantic block: Wrapper that transforms existing Dict output into List[KeywordCandidate] with source context


# FUNCTION_CONTRACT: run_llm_url_keyword_extraction_tupled
# Purpose: Stage 1 extraction wrapper producing (keyword, source_url) tuples (M1 amendment)
# Input: urls (List[str]), provider (str), model (str), max_keywords (int), keyword_prompt (str), api settings, run_id (str)
# Output: List[KeywordCandidate] with (keyword, source_url) pairs
# Side Effects: Sets session state for STAGED_KEYWORDS, LAST_EXTRACTION_RUN_ID, ACTIVE_SOURCE_URLS
# Business Rules: Reuses existing extraction logic via run_llm_url_keyword_extraction_stage; transforms Dict to List
# Failure Modes: Returns empty list if extraction fails or returns None
# LINKS: PLAN 09-04 Task 3 (M1 amendment)
# Rationale: Calls existing run_llm_url_keyword_extraction_stage() and transforms Dict[str, List[str]] into List[KeywordCandidate].
def run_llm_url_keyword_extraction_tupled(
    urls: List[str],
    **workflow_kwargs: Any,
) -> List[KeywordCandidate]:
    url_to_keywords = run_llm_url_keyword_extraction_stage(
        urls=urls,
        provider=workflow_kwargs.get("provider", ""),
        model=workflow_kwargs.get("model", ""),
        max_keywords=workflow_kwargs.get("max_keywords", 0),
        keyword_prompt=workflow_kwargs.get("keyword_prompt", ""),
        api_timeout=workflow_kwargs.get("api_timeout"),
        api_delay=workflow_kwargs.get("api_delay"),
        api_retry_count=workflow_kwargs.get("api_retry_count"),
        api_retry_delay=workflow_kwargs.get("api_retry_delay"),
        run_id=workflow_kwargs.get("run_id", ""),
        force_refresh=workflow_kwargs.get("force_refresh", False),
    )

    return _store_tupled_keyword_candidate_state(
        url_to_keywords or {},
        run_id=workflow_kwargs.get("run_id", ""),
    )


# FUNCTION_CONTRACT: run_selected_keywords_to_ads_workflow
# Purpose: Stage 2 - run Google Ads for selected (keyword, source_url) tuples
# Input: selected_contexts (List[SourceContextKey]), location_id (str), language_id (str), currency_code (str), api settings, run_id (str)
# Output: Optional[pd.DataFrame] - Ads DataFrame with Keyword and Source URL columns
# Side Effects: Stores processed_data in session state
# Business Rules: Groups keywords by source_url for Ads API; uses canonical RESULT_COLUMNS
# Failure Modes: Returns None if no contexts provided or Ads API fails
# LINKS: PLAN 09-04 Task 3
# Rationale: Groups keywords by source_url and queries Google Ads API. Returns DataFrame with canonical RESULT_COLUMNS.
def run_selected_keywords_to_ads_workflow(
    selected_contexts: List[SourceContextKey],
    location_id: str,
    language_id: str,
    currency_code: str,
    api_timeout: Optional[int] = None,
    api_delay: Optional[int] = None,
    api_retry_count: Optional[int] = None,
    api_retry_delay: Optional[int] = None,
    run_id: str = "",
    force_refresh: bool = False,
) -> Optional[pd.DataFrame]:
    if not selected_contexts:
        return None

    run_prefix = f"[run {run_id}] " if run_id else ""
    progress_bar = st.progress(0)
    status_text = st.empty()

    base_df = pd.DataFrame(
        [
            {"Keyword": keyword, "Source URL": source_url}
            for keyword, source_url in selected_contexts
            if str(keyword or "").strip()
        ]
    )
    if base_df.empty:
        progress_bar.progress(1.0)
        return None

    all_keywords: List[str] = base_df["Keyword"].astype(str).tolist()

    status_text.text(
        _format_pipeline_message(
            "pipeline_fetching_metrics",
            count=len(all_keywords),
        )
    )
    progress_bar.progress(
        0.5,
        text=_format_pipeline_message("pipeline_querying_google_ads"),
    )

    ads_handler = GoogleAdsHandler(
        location_id=location_id,
        language_id=language_id,
        target_currency_code=currency_code,
    )
    metrics_df = _get_keyword_metrics_with_optional_cache(
        ads_handler,
        all_keywords,
        force_refresh=force_refresh,
    )
    if metrics_df is not None and not metrics_df.empty and "Keyword" in metrics_df.columns:
        metrics_df = metrics_df.drop_duplicates(subset=["Keyword"], keep="first")

    status_text.text(_format_pipeline_message("pipeline_finalizing_report"))
    merged_df = _merge_base_keywords_with_metrics(base_df, metrics_df, currency_code)

    # Use scraped content from session state if available
    scraped_content = st.session_state.get("scraped_content") or {}
    _store_processed_data(merged_df, scraped_content=scraped_content)

    progress_bar.progress(1.0, text=_format_pipeline_message("pipeline_done"))
    status_text.success(_format_pipeline_message("pipeline_analysis_complete"))
    logger.info(
        f"{run_prefix}Selected keywords to Ads completed for "
        f"{len(all_keywords)} keyword(s) from "
        f"{base_df['Source URL'].nunique()} source(s)"
    )

    # Clear staged keywords after downstream handoff
    st.session_state[SESSION_KEY_STAGED_KEYWORDS] = None

    return merged_df


# FUNCTION_CONTRACT: run_serp_analysis_workflow
# Purpose: Run SERP analysis for a list of keywords — query configured provider, flatten organic results into DataFrame, store related data in session state
# Input: keywords (List[str]), run_id (str), serp_config (Optional[dict]), force_refresh (bool = False)
# Output: Optional[pd.DataFrame] — SERP organic results DataFrame; None if no API key or no keywords
# Side Effects: renders Streamlit progress bar and status messages; stores processed_data and serp_related_data in session state; logs progress; uses cache lookup
# Business Rules: normalizes and deduplicates keywords; detects missing API key gracefully; logs warnings for per-keyword failures; checks cache before API call
# Failure Modes: returns None when API key missing or keywords empty after normalization
# LINKS: requirements.xml#UC-006, knowledge-graph.xml#MOD-002, PLAN 10-02 Task 6
def run_serp_analysis_workflow(
    keywords: List[str],
    run_id: str = "",
    serp_config: Optional[dict] = None,
    force_refresh: bool = False,
) -> Optional[pd.DataFrame]:
    # HIGH-3: Clear stale domain metrics from previous runs
    st.session_state.serp_domain_metrics = None

    normalized_keywords = _normalize_keyword_seed_input(keywords)
    run_prefix = f"[run {run_id}] " if run_id else ""

    if not normalized_keywords:
        st.warning(t("serp_keyword_warning"))
        return None

    # SERP keyword guard: filter out URL-like queries
    serp_eligible = filter_serp_eligible_keywords(normalized_keywords)
    if len(serp_eligible) < len(normalized_keywords):
        filtered_count = len(normalized_keywords) - len(serp_eligible)
        logger.warning(
            f"{run_prefix}Filtered {filtered_count} URL-like queries from SERP input"
        )
    if not serp_eligible:
        logger.warning(
            f"{run_prefix}[GRACE:block_workflow_keyword_gate:STATE] beliefState=serp_keyword_gate_blocked "
            "SERP blocked because no keyword candidates remained after URL filtering"
        )
        st.warning(t("serp_no_keywords_eligible"))
        return None

    normalized_keywords = serp_eligible

    client = create_serp_client(config=serp_config)
    if client is None:
        st.warning(t("serp_no_api_key"))
        return None

    progress_bar = st.progress(0)
    status_text = st.empty()
    status_text.text(t("serp_querying", count=len(normalized_keywords)))

    # Purpose:  on progress implementation
    def _on_progress(index: int, total: int) -> None:
        progress = index / total
        progress_bar.progress(
            progress,
            text=t(
                "serp_querying_keyword",
                idx=index,
                total=total,
                keyword=normalized_keywords[index - 1] if index <= len(normalized_keywords) else "",
            ),
        )

    # Phase 10 Task 6: Use cache-aware SERP search
    results = _serp_search_with_cache(
        client=client,
        keywords=normalized_keywords,
        force_refresh=force_refresh,
        run_id=run_id,
        progress_callback=_on_progress,
    )

    rows, related_data, failed_keywords = _collect_serp_rows(results)

    def _on_success(serp_df: pd.DataFrame) -> None:
        st.session_state.processed_data = serp_df

        # Compute domain metrics and store in session state (Plan 14-02)
        domain_metrics = compute_domain_metrics(serp_df)
        st.session_state.serp_domain_metrics = domain_metrics

    return _finalize_serp_results_workflow(
        rows=rows,
        related_data=related_data,
        failed_keywords=failed_keywords,
        progress_bar=progress_bar,
        status_text=status_text,
        run_prefix=run_prefix,
        result_columns=SERP_RESULT_COLUMNS,
        completion_log_message=(
            f"SERP analysis completed for {len(normalized_keywords)} keyword(s), {len(rows)} organic results"
        ),
        on_success=_on_success,
    )


# block_pipeline_phase9_serp_source_context: Source-aware SERP workflow with tuple-keyed match index
# Semantic block: SERP workflow preserving source context, match index builder, Ads enrichment with column normalization


# FUNCTION_CONTRACT: run_serp_workflow_with_source_context
# Purpose: Run SERP analysis preserving source context through the pipeline
# Input: keywords_with_sources (List[SourceContextKey]), run_id (str), serp_config (Optional[dict])
# Output: Optional[pd.DataFrame] with source_context_key column
# Side Effects: Sets SESSION_KEY_SERP_MATCH_INDEX in session state
# Business Rules: Preserves (keyword, source_url) tuple for match index lookups
# Failure Modes: Returns None if no keywords or SERP API fails
# LINKS: PLAN 09-04 Task 4
# Rationale: Returns DataFrame with source_context_key column for match index enrichment. Sets SESSION_KEY_SERP_MATCH_INDEX in session state.
def run_serp_workflow_with_source_context(
    keywords_with_sources: List[SourceContextKey],
    run_id: str = "",
    serp_config: Optional[dict] = None,
    force_refresh: bool = False,
) -> Optional[pd.DataFrame]:
    from utils.url_matcher import build_source_url_targets

    # HIGH-3: Clear stale domain metrics from previous runs
    st.session_state.serp_domain_metrics = None

    cleaned_contexts: List[SourceContextKey] = []
    serp_keywords: List[str] = []
    active_source_urls: List[str] = []
    for keyword, source_url in keywords_with_sources:
        cleaned_keyword = str(keyword or "").strip()
        cleaned_source = normalize_source_url_for_lookup(source_url)
        if not cleaned_keyword or is_url_like_query(cleaned_keyword):
            continue
        cleaned_contexts.append((cleaned_keyword, cleaned_source))
        serp_keywords.append(cleaned_keyword)
        if cleaned_source:
            active_source_urls.append(cleaned_source)

    if not cleaned_contexts:
        return None

    previous_processed = st.session_state.get("processed_data")
    previous_related = st.session_state.get("serp_related_data")

    client = create_serp_client(config=serp_config)
    if client is None:
        st.warning(t("serp_no_api_key"))
        return None

    progress_bar = st.progress(0)
    status_text = st.empty()
    run_prefix = f"[run {run_id}] " if run_id else ""
    status_text.text(t("serp_querying", count=len(serp_keywords)))

    # Purpose:  on progress implementation
    def _on_progress(index: int, total: int) -> None:
        progress_bar.progress(
            index / total,
            text=t(
                "serp_querying_keyword",
                idx=index,
                total=total,
                keyword=serp_keywords[index - 1] if index <= len(serp_keywords) else "",
            ),
        )

    results: List[SERPSearchResult] = _serp_search_with_cache(
        client=client,
        keywords=serp_keywords,
        force_refresh=force_refresh,
        run_id=run_id,
        progress_callback=_on_progress,
    )

    rows, related_data, failed_keywords = _collect_serp_rows(
        results,
        source_contexts=cleaned_contexts,
    )

    def _on_success(serp_df: pd.DataFrame) -> None:
        match_targets = build_source_url_targets(active_source_urls)
        st.session_state[SESSION_KEY_ACTIVE_SOURCE_URLS] = active_source_urls
        st.session_state[SESSION_KEY_MATCH_TARGETS] = match_targets
        match_index = build_serp_match_index(serp_df)
        st.session_state[SESSION_KEY_SERP_MATCH_INDEX] = match_index

        st.session_state["chained_serp_results"] = serp_df.copy()
        st.session_state["chained_serp_related_data"] = list(related_data)
        _restore_serp_session_state(previous_processed, previous_related)

        # Compute domain metrics and store in session state (Plan 14-02)
        domain_metrics = compute_domain_metrics(serp_df)
        st.session_state.serp_domain_metrics = domain_metrics

    return _finalize_serp_results_workflow(
        rows=rows,
        related_data=related_data,
        failed_keywords=failed_keywords,
        progress_bar=progress_bar,
        status_text=status_text,
        run_prefix=run_prefix,
        result_columns=SERP_RESULT_COLUMNS + ["source_context_key"],
        completion_log_message=(
            f"SERP analysis completed for {len(serp_keywords)} keyword(s), {len(rows)} organic results"
        ),
        on_success=_on_success,
    )


# FUNCTION_CONTRACT: build_serp_match_index
# Purpose: Build tuple-keyed match index from SERP results with source context
# Input: serp_results (pd.DataFrame with source_context_key column)
# Output: Dict[SourceContextKey, SERPMatchEvidence]
# Side Effects: (none - pure enrichment helper)
# Business Rules: Keys are (keyword, source_url), each SERP row matches only its own source URL, best rank wins per tuple
# Failure Modes: Returns empty dict if no results
# LINKS: PLAN 09-04 Task 4
# Rationale: Reads source_context_key column; classifies match type using url_matcher; stores under tuple key; keeps lowest rank on duplicates.
def build_serp_match_index(
    serp_results: pd.DataFrame,
) -> Dict[SourceContextKey, dict]:
    from utils.url_matcher import classify_url_match

    match_index: Dict[SourceContextKey, dict] = {}

    for _, row in serp_results.iterrows():
        ctx_key = row.get("source_context_key")
        if not isinstance(ctx_key, tuple) or len(ctx_key) != 2:
            continue

        keyword, source_url = ctx_key
        source_url = normalize_source_url_for_lookup(source_url)

        # Skip keyword-only entries (no source URL to match against)
        if not source_url or source_url == EMPTY_SOURCE_URL:
            continue

        # Classify match for the SERP result URL
        result_url = str(row.get("URL", ""))
        match_info = classify_url_match(result_url, [source_url])
        match_type = match_info.get("match_type", "none")
        if match_type == "none":
            continue

        rank = int(row.get("Position", 0)) if pd.notna(row.get("Position")) else 0
        current_priority = 2 if match_type == "full_url" else 1
        current_rank = rank if rank > 0 else 10**9

        evidence: dict = {
            "keyword": keyword,
            "source_url": source_url,
            "matched_serp_url": result_url,
            "match_type": match_type,
            "serp_rank": rank,
            "matched_domain": match_info.get("matched_domain", ""),
        }

        # Keep best rank per tuple key
        tuple_key = (keyword, source_url)
        existing = match_index.get(tuple_key)
        if existing is None:
            match_index[tuple_key] = evidence
            continue

        existing_priority = 2 if existing.get("match_type") == "full_url" else 1
        existing_rank = existing.get("serp_rank", 10**9)
        if current_priority > existing_priority or (
            current_priority == existing_priority and current_rank < existing_rank
        ):
            match_index[tuple_key] = evidence

    return match_index


# FUNCTION_CONTRACT: enrich_ads_dataframe_with_serp_context
# Purpose: Append SERP rank columns to Ads DataFrame using tuple-keyed match index (M2, M5 amended)
# Input: ads_df (pd.DataFrame with Keyword and Source URL columns)
# Output: pd.DataFrame with appended columns
# Side Effects: (none - returns new DataFrame)
# Business Rules: Normalize column names (M2), normalize keywords (M5), lookup in match index
# Failure Modes: Returns original DataFrame if no match index
# LINKS: PLAN 09-04 Task 4 (M2, M5 amendments)
# Rationale: M2 - Column normalization (RESULT_COLUMNS + lowercase variants). M5 - Keyword normalization before tuple lookup via normalize_keyword_for_lookup().
def enrich_ads_dataframe_with_serp_context(
    ads_df: pd.DataFrame,
) -> pd.DataFrame:
    if ads_df is None or ads_df.empty:
        return ads_df

    # Get match index from session state
    match_index = st.session_state.get(SESSION_KEY_SERP_MATCH_INDEX, {})
    if not match_index:
        return ads_df

    # Normalize column names (M2 amendment)
    keyword_col = "Keyword" if "Keyword" in ads_df.columns else (
        "keyword" if "keyword" in ads_df.columns else None
    )
    source_col = "Source URL" if "Source URL" in ads_df.columns else (
        "source_url" if "source_url" in ads_df.columns else None
    )

    if not keyword_col or not source_col:
        return ads_df

    # Build enrichment lists
    page_urls: List[str] = []
    ranks: List[Optional[int]] = []

    for _, row in ads_df.iterrows():
        raw_keyword = str(row[keyword_col])
        raw_source = str(row[source_col]) if pd.notna(row[source_col]) else ""

        # M5: Normalize keyword with same function as match index build
        norm_keyword = normalize_keyword_for_lookup(raw_keyword)
        norm_source = normalize_source_url_for_lookup(raw_source)

        # Build tuple key and lookup
        tuple_key = (norm_keyword, norm_source)
        evidence = match_index.get(tuple_key)

        if evidence and evidence.get("match_type") != "none":
            page_urls.append(evidence.get("matched_serp_url", ""))
            ranks.append(evidence.get("serp_rank", None))
        else:
            page_urls.append("")
            ranks.append(None)

    # Append new columns
    result_df = ads_df.copy()
    result_df["Page URL in SERP"] = page_urls
    result_df["SERP Rank"] = ranks

    return result_df


# FUNCTION_CONTRACT: aggregate_serp_per_keyword
# Purpose: Aggregate SERP rows per keyword and left-join aggregates onto Ads DataFrame
# Input: serp_df (Optional[pd.DataFrame]), ads_df (Optional[pd.DataFrame])
# Output: pd.DataFrame — Ads DataFrame with appended SERP aggregate columns; None if ads_df is None
# Side Effects: (none — pure function; works on copies, no session-state reads)
# Business Rules:
#   1. Guard: if serp_df is None/empty or ads_df is None/empty or either lacks "Keyword" col -> return ads_df unchanged (None if ads_df is None)
#   2. Normalize keywords on both sides via normalize_keyword_for_lookup for case-insensitive join
#   3. Aggregate per-keyword: SERP #results = row count, SERP top position = min(Position), SERP top3 domains = top 3 distinct domains by rank (best Position first), deduplicated (each domain appears once, first occurrence by best rank wins), joined with ", ". If fewer than 3 distinct domains exist, return what's available (no padding, no trailing separator). If none, empty string "".
#   4. Left-join aggregates onto ads_df; preserve ads_df column order; append ["SERP #results","SERP top position","SERP top3 domains"]
#   5. Coerce Position to numeric; if all NaN -> None for top position
#   6. Pure: no mutation of inputs
# Failure Modes: Returns ads_df unchanged on bad inputs; never raises
# LINKS: PLAN 16 Task 1 — SERP-Ads merge
def aggregate_serp_per_keyword(
    serp_df: Optional[pd.DataFrame],
    ads_df: Optional[pd.DataFrame],
) -> Optional[pd.DataFrame]:
    # Guard: ads_df None -> return None
    if ads_df is None:
        return None
    # Guard: ads_df empty or missing Keyword col -> return ads_df unchanged
    if getattr(ads_df, "empty", True) or "Keyword" not in ads_df.columns:
        return ads_df
    # Guard: serp_df None or empty -> return ads_df unchanged
    if serp_df is None or getattr(serp_df, "empty", True):
        return ads_df
    # Guard: serp_df missing Keyword col -> return ads_df unchanged
    if "Keyword" not in serp_df.columns:
        return ads_df

    # Work on copies
    serp_copy = serp_df.copy()
    ads_copy = ads_df.copy()

    # Normalize keywords on both sides
    serp_copy["_norm_kw"] = serp_copy["Keyword"].apply(normalize_keyword_for_lookup)
    ads_copy["_norm_kw"] = ads_copy["Keyword"].apply(normalize_keyword_for_lookup)

    # Coerce Position to numeric
    serp_copy["Position"] = pd.to_numeric(serp_copy["Position"], errors="coerce")

    # Group SERP by normalized keyword
    def _aggregate_group(group: pd.DataFrame) -> pd.Series:
        count = len(group)
        top_pos = group["Position"].min()
        if pd.isna(top_pos):
            top_pos = None

        # Top 3 distinct domains by rank (best Position first), deduplicated
        sorted_group = group.sort_values("Position", na_position="last")
        seen: set = set()
        collected: list = []
        for _, row in sorted_group.iterrows():
            displayed = row.get("Displayed Link", "")
            if displayed and str(displayed).strip():
                domain = str(displayed).strip()
            else:
                raw_url = row.get("URL", "")
                if raw_url:
                    try:
                        domain = urlparse(str(raw_url)).netloc
                        domain = domain.removeprefix("www.")
                    except Exception:
                        domain = ""
                else:
                    domain = ""
            if domain and domain not in seen:
                seen.add(domain)
                collected.append(domain)
                if len(collected) == 3:
                    break
        top3 = ", ".join(collected)

        return pd.Series({
            "SERP #results": count,
            "SERP top position": top_pos,
            "SERP top3 domains": top3,
        })

    aggregates = serp_copy.groupby("_norm_kw")[["Position", "URL", "Displayed Link"]].apply(_aggregate_group, include_groups=False).reset_index()

    # Left-join aggregates onto ads on normalized key
    result = ads_copy.merge(aggregates, on="_norm_kw", how="left")

    # Drop temp key
    result = result.drop(columns=["_norm_kw"])
    serp_copy = serp_copy.drop(columns=["_norm_kw"])

    # Preserve ads_df original column order, append SERP cols at end
    base_cols = [c for c in ads_df.columns if c in result.columns]
    extra_cols = [c for c in result.columns if c not in base_cols]
    result = result[base_cols + extra_cols]

    return result


# FUNCTION_CONTRACT: aggregate_trends_per_keyword
# Purpose: Left-join per-keyword Google Trends averages onto Ads DataFrame (1 trends row/keyword -> 1 ads row)
# Input: trends_df (Optional[pd.DataFrame]), ads_df (Optional[pd.DataFrame])
# Output: pd.DataFrame — Ads DataFrame widened with appended trends columns; None if ads_df is None
# Side Effects: (none — pure function; works on copies, no session-state reads)
# Business Rules:
#   1. Guard: if trends_df is None/empty or ads_df is None/empty or either lacks "Keyword" col -> return ads_df unchanged (None if ads_df is None)
#   2. Normalize keywords on both sides via normalize_keyword_for_lookup for case-insensitive join
#   3. Left-join trends averages columns onto ads_df by normalized keyword; map source -> result cols:
#      "Average Interest" -> "Trends Avg Interest", "Geo" -> "Trends Geo", "Timeframe" -> "Trends Timeframe"
#   4. Preserve ads_df column order; append ["Trends Avg Interest", "Trends Geo", "Trends Timeframe"] at end
#   5. Rows with no trends match get blank/NaN trends columns (left join semantics)
#   6. Pure: no mutation of inputs
# Failure Modes: Returns ads_df unchanged on bad inputs; never raises
# LINKS: PLAN 16 Task 1 — Trends-Ads merge (mirrors aggregate_serp_per_keyword)
def aggregate_trends_per_keyword(
    trends_df: Optional[pd.DataFrame],
    ads_df: Optional[pd.DataFrame],
) -> Optional[pd.DataFrame]:
    # Guard: ads_df None -> return None
    if ads_df is None:
        return None
    # Guard: ads_df empty or missing Keyword col -> return ads_df unchanged
    if getattr(ads_df, "empty", True) or "Keyword" not in ads_df.columns:
        return ads_df
    # Guard: trends_df None or empty -> return ads_df unchanged
    if trends_df is None or getattr(trends_df, "empty", True):
        return ads_df
    # Guard: trends_df missing Keyword col -> return ads_df unchanged
    if "Keyword" not in trends_df.columns:
        return ads_df

    # Work on copies
    trends_copy = trends_df.copy()
    ads_copy = ads_df.copy()

    # Normalize keywords on both sides for case-insensitive join
    trends_copy["_norm_kw"] = trends_copy["Keyword"].apply(normalize_keyword_for_lookup)
    ads_copy["_norm_kw"] = ads_copy["Keyword"].apply(normalize_keyword_for_lookup)

    # Select only the trends columns we want to merge, renaming source -> result cols
    trends_select = trends_copy[["_norm_kw", "Average Interest", "Geo", "Timeframe"]].rename(
        columns={
            "Average Interest": "Trends Avg Interest",
            "Geo": "Trends Geo",
            "Timeframe": "Trends Timeframe",
        }
    )

    # Left-join trends onto ads on normalized key
    result = ads_copy.merge(trends_select, on="_norm_kw", how="left")

    # Drop temp key
    result = result.drop(columns=["_norm_kw"])

    # Preserve ads_df original column order, append Trends cols at end
    base_cols = [c for c in ads_df.columns if c in result.columns]
    extra_cols = [c for c in result.columns if c not in base_cols]
    result = result[base_cols + extra_cols]

    return result


# FUNCTION_CONTRACT: run_serp_chain_to_ads_workflow
# Purpose: Run Google Ads keyword analysis for queries selected from SERP related searches/PAA, storing results separately from SERP data
# Input: selected_queries (List[str]), location_id (str), language_id (str), currency_code (str), run_id (str)
# Output: Optional[pd.DataFrame] — Ads metrics DataFrame; None if no queries or no results
# Side Effects: renders Streamlit progress; stores serp_chained_ads_data in session state; logs progress
# Business Rules: limits to SERP_CHAIN_MAX_KEYWORDS (20); uses KEYWORD_SEED_SOURCE_URL as source
# Failure Modes: returns None if no queries, Ads API returns empty, or API call raises exception
# LINKS: requirements.xml#UC-006, knowledge-graph.xml#MOD-002
def run_serp_chain_to_ads_workflow(
    selected_queries: List[str],
    location_id: str,
    language_id: str,
    currency_code: str,
    run_id: str = "",
    force_refresh: bool = False,
) -> Optional[pd.DataFrame]:
    normalized_queries = _normalize_keyword_seed_input(selected_queries)
    run_prefix = f"[run {run_id}] " if run_id else ""

    if not normalized_queries:
        st.warning(t("serp_chain_no_queries"))
        return None

    queries_to_use = normalized_queries
    if len(queries_to_use) > SERP_CHAIN_MAX_KEYWORDS:
        st.info(t("serp_chain_limit_notice", used=SERP_CHAIN_MAX_KEYWORDS, selected=len(normalized_queries)))
        queries_to_use = queries_to_use[:SERP_CHAIN_MAX_KEYWORDS]

    progress_bar = st.progress(0)
    status_text = st.empty()
    status_text.text(t("serp_chain_querying", count=len(queries_to_use)))

    ads_handler = GoogleAdsHandler(
        location_id=location_id,
        language_id=language_id,
        target_currency_code=currency_code,
    )

    try:
        ideas_df = _get_keyword_ideas_with_optional_cache(
            ads_handler,
            queries_to_use,
            source_url=KEYWORD_SEED_SOURCE_URL,
            force_refresh=force_refresh,
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"{run_prefix}Network error during SERP chain: {e}")
        st.error(f"Network error: {e}")
        return None
    except Exception as e:
        logger.exception(f"{run_prefix}SERP chain to Ads failed: {e}")
        st.error(f"Ads query failed: {e}")
        return None

    processed_df = _ensure_result_columns(ideas_df, currency_code)
    processed_df = processed_df.drop_duplicates(
        subset=["Source URL", "Keyword"], keep="first"
    ).reset_index(drop=True)

    if processed_df.empty:
        st.info(t("serp_chain_empty"))
        progress_bar.progress(1.0, text=t("pipeline_done"))
        return None

    st.session_state.serp_chained_ads_data = processed_df

    progress_bar.progress(1.0, text=t("pipeline_done"))
    status_text.success(t("serp_chain_complete", count=len(processed_df)))
    logger.info(
        f"{run_prefix}SERP chain to Ads completed for {len(queries_to_use)} query/queries, {len(processed_df)} results"
    )
    return processed_df


# FUNCTION_CONTRACT: process_flow
# Purpose: Implement the process flow helper for this module.
# Input: urls (List[str]), provider (str), model (str), max_keywords (int), location_id (str), language_id (str), currency_code (str), keyword_prompt (str = ''), api_timeout (Optional[int] = None), api_delay (Optional[int] = None), api_retry_count (Optional[int] = None), api_retry_delay (Optional[int] = None), run_id (str = '')
# Output: Optional[pd.DataFrame]
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def process_flow(*args: Any, **kwargs: Any) -> Optional[pd.DataFrame]:
    return run_llm_url_workflow(*args, **kwargs)


# FUNCTION_CONTRACT: _apply_text_analysis_profile
# Purpose: Apply the shared text-analysis stages to a corpus-backed math profile.
# Input: profile (Dict[str, Any]), corpus (List[TextSource]), config (Dict[str, Any]), strip_suffixes (bool), ngram_min (int), ngram_max (int), min_ngram_count (int), min_df (int), top_terms_limit (int)
# Output: Dict[str, Any]
# Side Effects: Mutates the provided profile with n-grams, TF-IDF, co-occurrence, intent, and BM25F results.
# Business Rules: Uses the top TF-IDF terms as the seed list for co-occurrence and BM25F scoring.
# Failure Modes: never raises.
# LINKS: PLAN 08-02 Task 6, PLAN 15 Task 3
def _apply_text_analysis_profile(
    profile: Dict[str, Any],
    corpus: List[TextSource],
    config: Dict[str, Any],
    strip_suffixes: bool,
    ngram_min: int,
    ngram_max: int,
    min_ngram_count: int,
    min_df: int,
    top_terms_limit: int,
) -> Dict[str, Any]:
    corpus_hash = _normalize_for_hashing(corpus)
    profile["total_word_count"] = sum(
        len(_tokenize_text(source.text, strip_suffixes)) for source in corpus
    )

    # Guarantee analysis ALWAYS runs when enabled: a document-frequency or raw-count
    # threshold the corpus cannot satisfy (e.g. min_df=2 on a single scraped page, the
    # url_llm_ads path) would otherwise zero out n-grams + TF-IDF — and co-occurrence /
    # BM25F cascade from TF-IDF, so the whole report except intent would vanish. When the
    # corpus is that small, relax both thresholds to 1 so every analysis executes; the
    # configured values remain in force for normal multi-document corpora.
    if len(corpus) < min_df:
        effective_min_df = 1
        effective_min_count = 1
    else:
        effective_min_df = min_df
        effective_min_count = min_ngram_count

    if config.get("analyze_ngrams", True):
        for n in range(ngram_min, ngram_max + 1):
            ngrams = extract_ngrams(
                corpus_hash=corpus_hash,
                n=n,
                min_count=effective_min_count,
                min_df=effective_min_df,
                strip_suffixes=strip_suffixes,
            )
            profile["ngrams_by_size"][n] = ngrams[:top_terms_limit]

    if config.get("analyze_tfidf", True):
        tfidf_terms = compute_tfidf(
            corpus_hash=corpus_hash,
            strip_suffixes=strip_suffixes,
            min_df=effective_min_df,
        )
        profile["tfidf_terms"] = tfidf_terms[:top_terms_limit]

    if config.get("analyze_cooccurrence", True):
        seed_terms = tuple(term.term for term in profile.get("tfidf_terms", [])[:10])
        if seed_terms:
            cooccurrence_terms = compute_cooccurrence_terms(
                corpus_hash=corpus_hash,
                seed_terms=seed_terms,
                window=5,
                top_n=top_terms_limit,
                strip_suffixes=strip_suffixes,
            )
            profile["cooccurrence_terms"] = cooccurrence_terms

    if config.get("analyze_intent", True):
        profile["intent"] = analyze_intent(
            corpus_hash=corpus_hash,
            strip_suffixes=strip_suffixes,
        )

    if config.get("analyze_bm25f", False):
        field_profile = build_field_weighted_profile(corpus, config)
        profile["field_weighted_profile"] = field_profile

        query_terms = tuple(term.term for term in profile.get("tfidf_terms", [])[:20])
        if query_terms and corpus:
            field_weights_tuple = tuple(sorted(field_profile.field_weights.items()))
            field_b_tuple = tuple(sorted(field_profile.field_b_params.items()))
            profile["bm25f_scores"] = compute_bm25f(
                corpus_hash=corpus_hash,
                query_terms=query_terms,
                field_weights=field_weights_tuple,
                field_b=field_b_tuple,
                k1=config.get("bm25f_params", {}).get("k1", 1.2),
                top_n=top_terms_limit,
                strip_suffixes=strip_suffixes,
            )

    return profile


# block_pipeline_serp_math_profile: Build SERP mathematical analysis profile from raw SERP results
# Semantic block: Constructs corpus from SERP organic results, related searches, and PAA; runs n-gram, TF-IDF, co-occurrence, intent analysis


# FUNCTION_CONTRACT: build_serp_math_profile
# Purpose: Build mathematical analysis profile from SERP results for n-gram, TF-IDF, co-occurrence, and intent analysis
# Input: serp_df (Optional[pd.DataFrame]), serp_related_data (Optional[List[Dict]])
# Output: Dict[str, Any]
# Side Effects: Reads SEO_MATH_CONFIG for feature toggles; uses memoization cache
# Business Rules: Only runs if seo_math.enabled is true; handles partial data gracefully; includes related searches and PAA when toggled on
# Failure Modes: Returns empty profile with info messages if SERP data missing or SEO math disabled
# LINKS: PLAN 08-02 Task 6
# Rationale: Args - serp_df (SERP DataFrame), serp_related_data. Returns Dict with enabled, info_message, ngrams_by_size, tfidf_terms, cooccurrence_terms, intent, related_searches, people_also_ask, has_partial_data, bm25f_scores, field_weighted_profile.
def build_serp_math_profile(
    serp_df: Optional[pd.DataFrame],
    serp_related_data: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    profile: Dict[str, Any] = {
        "enabled": SEO_MATH_CONFIG.get("enabled", False),
        "info_message": "",
        "ngrams_by_size": {},
        "tfidf_terms": [],
        "cooccurrence_terms": [],
        "intent": None,
        "related_searches": [],
        "people_also_ask": [],
        "has_partial_data": False,
        "bm25f_scores": [],
        "field_weighted_profile": None,
        "total_word_count": 0,
    }

    if not profile["enabled"]:
        profile["info_message"] = "SEO mathematical analysis is disabled in settings."
        return profile

    if serp_df is None or serp_df.empty:
        profile["info_message"] = "No SERP data available for mathematical analysis."
        return profile

    config = SEO_MATH_CONFIG
    strip_suffixes = bool(config.get("strip_suffixes", False))
    ngram_min = config.get("ngram_min", 1)
    ngram_max = config.get("ngram_max", 3)
    top_terms_limit = config.get("top_terms_limit", 30)
    min_ngram_count = config.get("min_ngram_count", 2)
    min_df = config.get("min_document_frequency", 2)
    use_related = config.get("use_related_searches", True)
    use_paa = config.get("use_people_also_ask", True)

    # Build corpus from SERP organic results
    corpus: List[TextSource] = []

    # Source weights from research
    weights = {
        "title": 3.0,
        "snippet": 1.5,
        "displayed_link": 1.0,
        "rich_snippet": 1.0,
    }

    for _, row in serp_df.iterrows():
        title = row.get("Title", "")
        snippet = row.get("Snippet", "")
        displayed_link = row.get("Displayed Link", "")
        rich_snippet = row.get("Rich Snippet", "")

        if title:
            corpus.append(TextSource(text=title, field="title", weight=weights["title"]))
        if snippet:
            corpus.append(TextSource(text=snippet, field="snippet", weight=weights["snippet"]))
        if displayed_link:
            corpus.append(TextSource(text=displayed_link, field="displayed_link", weight=weights["displayed_link"]))
        if rich_snippet:
            corpus.append(TextSource(text=rich_snippet, field="rich_snippet", weight=weights["rich_snippet"]))

    # Check for partial data
    if len(corpus) < len(serp_df) * 3:  # Expected at least 3 fields per row
        profile["has_partial_data"] = True

    # Add related searches if available and enabled
    related_searches: List[str] = []
    people_also_ask: List[str] = []

    if serp_related_data:
        for item in serp_related_data:
            query = item.get("Related Query", "")
            query_type = item.get("Type", "")
            if query_type == "related_search" and use_related:
                corpus.append(TextSource(text=query, field="related_search", weight=2.0))
                related_searches.append(query)
            elif query_type == "people_also_ask" and use_paa:
                corpus.append(TextSource(text=query, field="people_also_ask", weight=2.0))
                people_also_ask.append(query)

    # Check if we have any corpus data
    if not corpus:
        profile["info_message"] = "No text content available in SERP results for analysis."
        profile["has_partial_data"] = True
        return profile

    profile["related_searches"] = related_searches
    profile["people_also_ask"] = people_also_ask
    return _apply_text_analysis_profile(
        profile=profile,
        corpus=corpus,
        config=config,
        strip_suffixes=strip_suffixes,
        ngram_min=ngram_min,
        ngram_max=ngram_max,
        min_ngram_count=min_ngram_count,
        min_df=min_df,
        top_terms_limit=top_terms_limit,
    )


# FUNCTION_CONTRACT: build_generated_text_math_profile
# Purpose: Build a mathematical analysis profile from generated SEO text
# Input: texts_df (pd.DataFrame) — generated_seo_texts DataFrame with columns for keywords, URL, SEO text
# Output: Dict[str, Any] — profile with ngrams_by_size, tfidf_terms, cooccurrence_terms, intent, per-row sub-profiles
# Side Effects: Reads SEO_MATH_CONFIG for analysis toggles and parameters
# Business Rules: Parses META_TITLE/META_DESCRIPTION/H1/DESCRIPTION sections into TextSource corpus per row;
#                 runs same analyses as SERP math (n-grams, TF-IDF, co-occurrence, intent, BM25F);
#                 returns aggregate profile across all generated texts plus per-row sub-profiles
# Failure Modes: Returns profile with info_message when no text available or feature disabled
# LINKS: PLAN 15 Task 3
def build_generated_text_math_profile(
    texts_df: Optional[pd.DataFrame],
) -> Dict[str, Any]:
    profile: Dict[str, Any] = {
        "enabled": SEO_MATH_CONFIG.get("enabled", False),
        "analyze_generated_text": SEO_MATH_CONFIG.get("analyze_generated_text", False),
        "info_message": "",
        "ngrams_by_size": {},
        "tfidf_terms": [],
        "cooccurrence_terms": [],
        "intent": None,
        "bm25f_scores": [],
        "field_weighted_profile": None,
        "per_row_profiles": [],
        "corpus_source": "generated_text",
        "total_rows": 0,
        "total_word_count": 0,
    }

    if not profile["enabled"]:
        profile["info_message"] = "SEO mathematical analysis is disabled in settings."
        return profile

    if not profile["analyze_generated_text"]:
        return profile

    if texts_df is None or texts_df.empty:
        profile["info_message"] = "No generated text available for analysis."
        return profile

    config = SEO_MATH_CONFIG
    strip_suffixes = bool(config.get("strip_suffixes", False))
    ngram_min = config.get("ngram_min", 1)
    ngram_max = config.get("ngram_max", 3)
    top_terms_limit = config.get("top_terms_limit", 30)
    min_ngram_count = config.get("min_ngram_count", 2)
    min_df = config.get("min_document_frequency", 2)

    from utils.seo_math_analysis import _parse_generated_sections

    # Build corpus from all generated texts
    corpus: List[TextSource] = []

    # Field weights for generated text elements
    field_weights = {
        "META_TITLE": ("page_title", 3.0),
        "META_DESCRIPTION": ("meta_description", 1.5),
        "H1": ("h1", 2.5),
        "DESCRIPTION": ("body_text", 1.0),
    }

    # Detect the SEO text column (i18n-aware)
    seo_col = None
    for col in texts_df.columns:
        col_lower = str(col).lower()
        if "seo" in col_lower or "text" in col_lower or "описан" in col_lower or "опис" in col_lower:
            seo_col = col
            break
    if seo_col is None:
        # Fallback: use last column
        seo_col = texts_df.columns[-1] if len(texts_df.columns) > 0 else None
    if seo_col is None:
        profile["info_message"] = "No generated text available for analysis."
        return profile

    # Detect keyword column
    kw_col = None
    for col in texts_df.columns:
        col_lower = str(col).lower()
        if "keyword" in col_lower or "ключ" in col_lower:
            kw_col = col
            break

    # Detect URL column
    url_col = None
    for col in texts_df.columns:
        if str(col).upper() == "URL":
            url_col = col
            break

    per_row_profiles: List[Dict[str, Any]] = []

    for idx, row in texts_df.iterrows():
        generated_text = str(row.get(seo_col, ""))
        if not generated_text or generated_text == "nan":
            continue

        sections = _parse_generated_sections(generated_text)

        row_corpus: List[TextSource] = []
        for element_type, (field, weight) in field_weights.items():
            text = sections.get(element_type, "")
            if text:
                row_corpus.append(TextSource(text=text, field=field, weight=weight))

        if not row_corpus:
            continue

        # Build per-row profile
        row_profile: Dict[str, Any] = {
            "url": str(row.get(url_col, "")) if url_col else "",
            "keywords": str(row.get(kw_col, "")) if kw_col else "",
            "ngrams_by_size": {},
            "tfidf_terms": [],
            "cooccurrence_terms": [],
            "intent": None,
            "total_word_count": 0,
        }

        row_corpus_hash = _normalize_for_hashing(row_corpus)

        if config.get("analyze_ngrams", True):
            for n in range(ngram_min, ngram_max + 1):
                ngrams = extract_ngrams(
                    corpus_hash=row_corpus_hash,
                    n=n,
                    min_count=1,
                    min_df=1,
                    strip_suffixes=strip_suffixes,
                )
                row_profile["ngrams_by_size"][n] = ngrams[:top_terms_limit]

        if config.get("analyze_tfidf", True):
            tfidf_terms = compute_tfidf(
                corpus_hash=row_corpus_hash,
                strip_suffixes=strip_suffixes,
            )
            row_profile["tfidf_terms"] = tfidf_terms[:top_terms_limit]

        if config.get("analyze_cooccurrence", True):
            seed_terms = tuple(term.term for term in row_profile.get("tfidf_terms", [])[:10])
            if seed_terms:
                coocc = compute_cooccurrence_terms(
                    corpus_hash=row_corpus_hash,
                    seed_terms=seed_terms,
                    window=5,
                    top_n=top_terms_limit,
                    strip_suffixes=strip_suffixes,
                )
                row_profile["cooccurrence_terms"] = coocc

        if config.get("analyze_intent", True):
            row_profile["intent"] = analyze_intent(
                corpus_hash=row_corpus_hash,
                strip_suffixes=strip_suffixes,
            )

        per_row_profiles.append(row_profile)
        corpus.extend(row_corpus)

    profile["total_rows"] = len(per_row_profiles)
    profile["per_row_profiles"] = per_row_profiles

    if not corpus:
        profile["info_message"] = "No generated text available for analysis."
        return profile

    return _apply_text_analysis_profile(
        profile=profile,
        corpus=corpus,
        config=config,
        strip_suffixes=strip_suffixes,
        ngram_min=ngram_min,
        ngram_max=ngram_max,
        min_ngram_count=min_ngram_count,
        min_df=min_df,
        top_terms_limit=top_terms_limit,
    )


def build_scraped_text_math_profile(
    scraped_content: Optional[Dict[str, str]],
    config_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    config = {**SEO_MATH_CONFIG, **(config_override or {})}
    profile: Dict[str, Any] = {
        "enabled": config.get("enabled", False),
        "analyze_scraped_text": config.get("analyze_scraped_text", False),
        "info_message": "",
        "ngrams_by_size": {},
        "tfidf_terms": [],
        "cooccurrence_terms": [],
        "intent": None,
        "bm25f_scores": [],
        "field_weighted_profile": None,
        "corpus_source": "scraped_text",
        "total_rows": 0,
        "total_word_count": 0,
    }

    if not profile["enabled"]:
        profile["info_message"] = "SEO mathematical analysis is disabled in settings."
        return profile
    if not profile["analyze_scraped_text"]:
        return profile
    if not scraped_content:
        profile["info_message"] = "No scraped text available for analysis."
        return profile

    strip_suffixes = bool(config.get("strip_suffixes", False))
    corpus: List[TextSource] = [
        TextSource(
            text=str(text),
            field="body_text",
            weight=1.0,
            provenance_url=str(url),
        )
        for url, text in scraped_content.items()
        if str(text or "").strip()
    ]
    if not corpus:
        profile["info_message"] = "No scraped text available for analysis."
        return profile

    profile["total_rows"] = len(corpus)
    return _apply_text_analysis_profile(
        profile=profile,
        corpus=corpus,
        config=config,
        strip_suffixes=strip_suffixes,
        ngram_min=int(config.get("ngram_min", 1)),
        ngram_max=int(config.get("ngram_max", 3)),
        min_ngram_count=int(config.get("min_ngram_count", 2)),
        min_df=int(config.get("min_document_frequency", 2)),
        top_terms_limit=int(config.get("top_terms_limit", 30)),
    )


# block_pipeline_reverse_math_report: SERP and Ads outputs feed a mathematical report
# Semantic block: SERP text drives corpus math while Ads keyword metrics remain enrichment columns, never text evidence.


# FUNCTION_CONTRACT: _ads_enrichment_rows
# Purpose: Normalize Google Ads keyword metrics into report enrichment rows.
# Input: ads_df (Optional[pd.DataFrame])
# Output: List[Dict[str, Any]]
# Side Effects: none
# Business Rules: Keyword text is a candidate label; volume/competition/CPC are metadata only.
# Failure Modes: returns empty list on missing/empty dataframe.
# LINKS: PLAN 08-03 Task 5
def _ads_enrichment_rows(ads_df: Optional[pd.DataFrame]) -> List[Dict[str, Any]]:
    if ads_df is None or ads_df.empty or "Keyword" not in ads_df.columns:
        return []

    metric_columns = [
        "Avg Monthly Searches",
        "Competition",
        "Competition Index",
        "Low CPC",
        "High CPC",
        "CPC Currency",
        "Months With Data",
    ]
    rows: List[Dict[str, Any]] = []
    for _, row in ads_df.iterrows():
        keyword = str(row.get("Keyword", "")).strip()
        if not keyword:
            continue
        enrichment = {"Keyword": keyword}
        for column in metric_columns:
            if column in ads_df.columns:
                enrichment[column] = row.get(column)
        rows.append(enrichment)
    return rows


# FUNCTION_CONTRACT: _lemmatize_phrase
# Purpose: Reduce a multi-word keyword phrase to its lemma form (space-joined lemmas) using the same morphology used by the SERP math pipeline, so Ads keywords can be matched against lemmatized SERP terms.
# Input: phrase (str)
# Output: str — the lowercased lemma phrase (e.g. "seo tools" -> "seo tool"); the original phrase lowercased when lemmatization yields nothing usable
# Side Effects: (none)
# Business Rules: Tokenizes via the shared _tokenize_text chokepoint with strip_suffixes=True so it stays consistent with how SERP n-grams/tfidf terms are built; multi-word phrases join each token's lemma with a single space; when the optional lemmatizer libs are absent lemmatize_token is the identity, so this degrades gracefully to the lowercased original tokens
# Failure Modes: never raises; returns the lowercased phrase when empty or when tokenization yields no tokens
# LINKS: PLAN 08-03 Task 5, PLAN 10-02 Task 4
def _lemmatize_phrase(phrase: str) -> str:
    if not phrase:
        return ""
    tokens = _tokenize_text(phrase, True)
    if not tokens:
        return phrase.strip().lower()
    return " ".join(lemmatize_token(token) for token in tokens)


# FUNCTION_CONTRACT: _serp_text_terms_from_profile
# Purpose: Extract SERP-derived candidate terms from a math profile.
# Input: profile (Dict[str, Any])
# Output: List[str]
# Side Effects: none
# Business Rules: Includes only SERP text analysis terms; Ads metrics are excluded by construction.
# Failure Modes: never raises.
# LINKS: PLAN 08-03 Task 5
def _serp_text_terms_from_profile(profile: Dict[str, Any]) -> List[str]:
    terms: List[str] = []
    for term in profile.get("tfidf_terms", []) or []:
        terms.append(term.term)
    for ngrams in (profile.get("ngrams_by_size", {}) or {}).values():
        for ngram in ngrams:
            terms.append(ngram.ngram)
    for term in profile.get("cooccurrence_terms", []) or []:
        terms.append(term.term)
    return list(dict.fromkeys(terms))


# FUNCTION_CONTRACT: build_reverse_math_report
# Purpose: Build a combined report from SERP text profile and Ads keyword metric enrichment.
# Input: serp_df, serp_related_data, ads_df
# Output: Dict[str, Any]
# Side Effects: none
# Business Rules: Ads metrics are enrichment only and never enter TF-IDF, n-gram, or co-occurrence corpus calculations. overlap_keywords / ads_only_keywords / serp_only_terms match SERP terms against Ads keywords on a shared lemma key when SEO_MATH_CONFIG.strip_suffixes is on (so an inflected Ads keyword matches a lemmatized SERP term), and on raw lowercased form when it is off; reported values always keep the original surface form.
# Failure Modes: Empty/missing inputs return a structured info message instead of raising.
# LINKS: PLAN 08-03 Task 5, PLAN 10-02 Task 4
def build_reverse_math_report(
    serp_df: Optional[pd.DataFrame] = None,
    serp_related_data: Optional[List[Dict[str, str]]] = None,
    ads_df: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    serp_profile = build_serp_math_profile(serp_df, serp_related_data)
    ads_enrichment = _ads_enrichment_rows(ads_df)
    serp_text_terms = _serp_text_terms_from_profile(serp_profile)

    # Match SERP terms against Ads keywords on a shared key so inflectional differences
    # don't hide overlaps. When strip_suffixes is on the SERP terms are already lemmas, so
    # the Ads keywords must be lemmatized to the same form (the user's directive: ALL the
    # math must respect lemmatisation). When it is off both sides use the raw lowercased
    # form, preserving the prior verbatim matching behavior. Reported values keep the
    # original surface form so users see the keyword they typed.
    strip_suffixes = bool(SEO_MATH_CONFIG.get("strip_suffixes", False))

    def _term_match_key(text: str) -> str:
        return _lemmatize_phrase(text) if strip_suffixes else text.strip().lower()

    # Map match-key -> original surface form (first occurrence wins on collision).
    serp_by_key: Dict[str, str] = {}
    for term in serp_text_terms:
        serp_by_key.setdefault(_term_match_key(term), term)
    ads_by_key: Dict[str, str] = {}
    for row in ads_enrichment:
        keyword = row["Keyword"]
        ads_by_key.setdefault(_term_match_key(keyword), keyword)

    overlap_keys = sorted(set(serp_by_key) & set(ads_by_key))

    report = {
        "serp_profile": serp_profile,
        "ads_enrichment": ads_enrichment,
        "ads_as_enrichment": True,
        "ads_metrics_used_as_text": False,
        "text_evidence_terms": serp_text_terms,
        "overlap_keywords": [ads_by_key[key] for key in overlap_keys],
        "ads_only_keywords": [
            ads_by_key[key]
            for key in sorted(ads_by_key)
            if key not in serp_by_key
        ],
        "serp_only_terms": [
            serp_by_key[key]
            for key in sorted(serp_by_key)
            if key not in ads_by_key
        ],
        "info_message": "",
    }

    if not serp_text_terms and not ads_enrichment:
        report["info_message"] = "No SERP or Ads data available for mathematical report."
    elif not serp_text_terms:
        report["info_message"] = "Ads keyword metrics available as enrichment; no SERP text corpus available."
    return report


# block_pipeline_crawl_math_report: Crawl -> mathematical report -> keyword handoff orchestration
# Semantic block: Converts bounded crawl pages into page and aggregate text profiles, then stores selectable math keywords for SERP/Ads handoff.


# FUNCTION_CONTRACT: _crawl_settings_from_dict
# Purpose: Normalize UI/runtime crawler settings into a CrawlSettings dataclass.
# Input: settings (Optional[Dict[str, Any]])
# Output: CrawlSettings
# Side Effects: none
# Business Rules: Missing settings use conservative crawler defaults; numeric values are bounded by CrawlSettings construction.
# Failure Modes: never raises for malformed user values; falls back to defaults.
# LINKS: PLAN 08-03 Task 4
def _crawl_settings_from_dict(settings: Optional[Dict[str, Any]] = None) -> CrawlSettings:
    values = dict(settings or {})
    return CrawlSettings(
        max_pages=int(values.get("max_pages", CrawlSettings.max_pages)),
        max_depth=int(values.get("max_depth", CrawlSettings.max_depth)),
        same_domain_only=bool(values.get("same_domain_only", True)),
        timeout_seconds=int(values.get("timeout_seconds", CrawlSettings.timeout_seconds)),
        max_response_bytes=int(
            values.get("max_response_bytes", CrawlSettings.max_response_bytes)
        ),
        max_retries=int(values.get("max_retries", CrawlSettings.max_retries)),
    )


# FUNCTION_CONTRACT: _build_profile_from_sources
# Purpose: Run deterministic SEO math analysis over prepared TextSource corpus.
# Input: corpus (List[TextSource]), config (Dict[str, Any])
# Output: Dict[str, Any]
# Side Effects: uses memoized seo_math_analysis functions.
# Business Rules: Honors SEO math toggles; returns empty report when corpus is absent.
# Failure Modes: never raises for empty corpus.
# LINKS: PLAN 08-03 Task 4, PLAN 10-02 Task 4
def _build_profile_from_sources(
    corpus: List[TextSource],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    profile: Dict[str, Any] = {
        "ngrams_by_size": {},
        "tfidf_terms": [],
        "cooccurrence_terms": [],
        "intent": None,
        "bm25f_scores": [],
        "field_weighted_profile": None,
        "total_word_count": 0,
    }
    if not corpus:
        return profile

    strip_suffixes = bool(config.get("strip_suffixes", False))
    ngram_min = int(config.get("ngram_min", 1))
    ngram_max = int(config.get("ngram_max", 3))
    top_terms_limit = int(config.get("top_terms_limit", 30))
    min_ngram_count = int(config.get("min_ngram_count", 1))
    min_df = int(config.get("min_document_frequency", 1))
    corpus_hash = _normalize_for_hashing(corpus)
    profile["total_word_count"] = sum(
        len(_tokenize_text(source.text, strip_suffixes)) for source in corpus
    )

    if config.get("analyze_ngrams", True):
        for n in range(ngram_min, ngram_max + 1):
            profile["ngrams_by_size"][n] = extract_ngrams(
                corpus_hash=corpus_hash,
                n=n,
                min_count=min_ngram_count,
                min_df=min_df,
                strip_suffixes=strip_suffixes,
            )[:top_terms_limit]

    if config.get("analyze_tfidf", True):
        profile["tfidf_terms"] = compute_tfidf(
            corpus_hash=corpus_hash,
            strip_suffixes=strip_suffixes,
        )[:top_terms_limit]

    if config.get("analyze_cooccurrence", True):
        seed_terms = tuple(term.term for term in profile["tfidf_terms"][:10])
        if seed_terms:
            profile["cooccurrence_terms"] = compute_cooccurrence_terms(
                corpus_hash=corpus_hash,
                seed_terms=seed_terms,
                window=5,
                top_n=top_terms_limit,
                strip_suffixes=strip_suffixes,
            )

    if config.get("analyze_intent", True):
        profile["intent"] = analyze_intent(
            corpus_hash=corpus_hash,
            strip_suffixes=strip_suffixes,
        )

    # Run BM25F scoring (Phase 10 Task 4)
    if config.get("analyze_bm25f", False):
        # Build field-weighted profile
        field_profile = build_field_weighted_profile(corpus, config)
        profile["field_weighted_profile"] = field_profile

        # Use top TF-IDF terms as query for BM25F ranking
        query_terms = tuple(term.term for term in profile.get("tfidf_terms", [])[:20])

        if query_terms and corpus:
            # Convert profile data to tuples for memoization
            field_weights_tuple = tuple(sorted(field_profile.field_weights.items()))
            field_b_tuple = tuple(sorted(field_profile.field_b_params.items()))

            # Compute BM25F scores
            bm25f_results = compute_bm25f(
                corpus_hash=corpus_hash,
                query_terms=query_terms,
                field_weights=field_weights_tuple,
                field_b=field_b_tuple,
                k1=config.get("bm25f_params", {}).get("k1", 1.2),
                top_n=top_terms_limit,
                strip_suffixes=strip_suffixes,
            )
            profile["bm25f_scores"] = bm25f_results

    return profile


# FUNCTION_CONTRACT: _crawl_page_sources
# Purpose: Convert a crawl page into weighted TextSource entries.
# Input: page (CrawlPage)
# Output: List[TextSource]
# Side Effects: none
# Business Rules: Title/meta/headings/body remain text evidence; URL itself is not analyzed as corpus text.
# Failure Modes: never raises.
# LINKS: PLAN 08-03 Task 4
def _crawl_page_sources(page: CrawlPage) -> List[TextSource]:
    sources: List[TextSource] = []
    if page.title:
        sources.append(
            TextSource(
                text=page.title,
                field="crawl_title",
                weight=3.0,
                provenance_url=page.url,
            )
        )
    if page.meta_description:
        sources.append(
            TextSource(
                text=page.meta_description,
                field="crawl_meta_description",
                weight=1.5,
                provenance_url=page.url,
            )
        )
    for heading in page.headings:
        sources.append(
            TextSource(
                text=heading,
                field="crawl_heading",
                weight=2.0,
                provenance_url=page.url,
            )
        )
    if page.body_text:
        sources.append(
            TextSource(
                text=page.body_text,
                field="crawl_body",
                weight=1.0,
                provenance_url=page.url,
            )
        )
    return sources


# FUNCTION_CONTRACT: build_crawl_math_report
# Purpose: Build aggregate and per-page mathematical report from bounded crawl output.
# Input: crawl_result (CrawlResult)
# Output: Dict[str, Any]
# Side Effects: none
# Business Rules: Can run without LLM or Ads APIs; identified keyword candidates come from text evidence only.
# Failure Modes: Returns info_message when crawl has no usable pages or SEO math is disabled.
# LINKS: PLAN 08-03 Task 4, PLAN 10-02 Task 4
def build_crawl_math_report(crawl_result: CrawlResult) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "enabled": SEO_MATH_CONFIG.get("enabled", False),
        "info_message": "",
        "crawl": crawl_result,
        "pages": [],
        "aggregate_profile": {},
        "keyword_candidates": [],
        "signals_enabled": SEO_MATH_CONFIG.get("signals", {}).get("title_alignment", True),
    }
    if not report["enabled"]:
        report["info_message"] = "SEO mathematical analysis is disabled in settings."
        return report
    if not crawl_result.pages:
        report["info_message"] = "No crawled page text available for mathematical analysis."
        return report

    config = dict(SEO_MATH_CONFIG)
    config["min_ngram_count"] = int(config.get("min_ngram_count", 1))
    config["min_document_frequency"] = int(config.get("min_document_frequency", 1))

    # Check if signals are enabled
    signals_config = config.get("signals", {})
    signals_enabled = signals_config.get("title_alignment", True) or \
                     signals_config.get("content_effort", True) or \
                     signals_config.get("topical_overlap", True) or \
                     signals_config.get("simhash", True)

    aggregate_sources: List[TextSource] = []
    all_titles: List[str] = []  # For duplicate title detection
    pages_for_signals: List[Dict[str, Any]] = []

    for page in crawl_result.pages:
        page_sources = _crawl_page_sources(page)
        aggregate_sources.extend(page_sources)
        page_profile = _build_profile_from_sources(
            page_sources,
            {**config, "min_ngram_count": 1, "min_document_frequency": 1},
        )

        # Extract text signals (Phase 10 Task 4)
        page_signals = None
        if signals_enabled:
            page_data = {
                "title": page.title,
                "meta_description": page.meta_description,
                "h1": page.headings[0] if page.headings else "",
                "headings": {"h1": page.headings} if page.headings else {},
                "intro_text": page.body_text[:500] if page.body_text else "",
                "body": page.body_text or "",
            }
            page_signals = extract_page_text_signals(page_data)
            all_titles.append(page.title or "")

        intent = page_profile.get("intent")
        intent_type = getattr(intent, "intent_type", "") if intent else ""

        page_entry = {
            "url": page.url,
            "title": page.title,
            "meta_description": page.meta_description,
            "headings": page.headings,
            "heading_count": len(page.headings),
            "analysis_evidence": {
                "intent": intent_type,
                "top_tfidf_terms": [
                    term.term for term in page_profile.get("tfidf_terms", [])[:5]
                ],
                "top_ngrams": [
                    ngram.ngram
                    for ngram in page_profile.get("ngrams_by_size", {})
                    .get(2, [])[:5]
                ],
            },
            "profile": page_profile,
            "signals": page_signals,
        }
        report["pages"].append(page_entry)

        if signals_enabled and page_signals:
            pages_for_signals.append({
                "url": page.url,
                "title": page.title,
                "body": page.body_text or "",
            })

    aggregate_profile = _build_profile_from_sources(aggregate_sources, config)
    report["aggregate_profile"] = aggregate_profile

    # Compute aggregate signal analysis (Phase 10 Task 4)
    if signals_enabled and pages_for_signals:
        signal_summary = {
            "title_alignment": None,
            "content_effort": None,
            "topical_overlap": None,
            "simhash": None,
        }

        # Title alignment analysis
        if signals_config.get("title_alignment", True) and all_titles:
            title_alignment = compute_title_alignment(
                title=all_titles[0] if all_titles else "",
                all_titles=all_titles,
            )
            signal_summary["title_alignment"] = title_alignment

        # Content effort (aggregate across pages)
        if signals_config.get("content_effort", True):
            total_word_count = int(aggregate_profile.get("total_word_count", 0) or 0)
            total_list_count = sum(
                pg.get("signals").list_count if pg.get("signals") else 0
                for pg in report["pages"]
            )
            total_table_count = sum(
                pg.get("signals").table_count if pg.get("signals") else 0
                for pg in report["pages"]
            )
            total_citation_count = sum(
                pg.get("signals").citation_count if pg.get("signals") else 0
                for pg in report["pages"]
            )
            total_media_count = sum(
                pg.get("signals").media_count if pg.get("signals") else 0
                for pg in report["pages"]
            )
            has_answer_first = any(
                pg.get("signals").has_answer_first if pg.get("signals") else False
                for pg in report["pages"]
            )

            effort_score = compute_content_effort_score(
                word_count=total_word_count,
                list_count=total_list_count,
                table_count=total_table_count,
                citation_count=total_citation_count,
                media_count=total_media_count,
                has_answer_first=has_answer_first,
            )
            signal_summary["content_effort"] = effort_score

        # Topical overlap
        if signals_config.get("topical_overlap", True) and len(pages_for_signals) > 1:
            topical_overlap = compute_topical_centroid_overlap(pages_for_signals)
            signal_summary["topical_overlap"] = topical_overlap

        # SimHash (aggregate fingerprint)
        if signals_config.get("simhash", True):
            all_text = " ".join(pg.get("body", "") for pg in pages_for_signals)
            simhash = compute_simhash64(all_text)
            signal_summary["simhash"] = simhash

        report["signal_summary"] = signal_summary

    candidates: list[str] = []
    for term in aggregate_profile.get("tfidf_terms", [])[:15]:
        candidates.append(term.term)
    for ngram in aggregate_profile.get("ngrams_by_size", {}).get(2, [])[:10]:
        candidates.append(ngram.ngram)
    report["keyword_candidates"] = list(dict.fromkeys(candidates))
    return report


# FUNCTION_CONTRACT: _cached_bounded_crawl
# Purpose: Cache bounded crawler output across Streamlit reruns and checkbox interactions.
# Input: seed_urls (tuple[str, ...]), settings_items (tuple[tuple[str, Any], ...]), settings_hash (str)
# Output: CrawlResult
# Side Effects: performs crawl on cache miss only.
# Business Rules: Cache key is stable over seed URLs and crawler settings. settings_hash ensures cache invalidation on critical setting changes.
# Failure Modes: propagates bounded_crawl errors if the crawler itself fails unexpectedly.
# LINKS: PLAN 08-03 Task 4
@st.cache_data(show_spinner=False)
def _cached_bounded_crawl(
    seed_urls: tuple[str, ...],
    settings_items: tuple[tuple[str, Any], ...],
    settings_hash: str,
) -> CrawlResult:
    crawler_settings = _crawl_settings_from_dict(dict(settings_items))
    return bounded_crawl(list(seed_urls), crawler_settings)


# FUNCTION_CONTRACT: run_crawl_math_report_workflow
# Purpose: Execute cached bounded crawl and build crawl math report for UI rendering and keyword handoff.
# Input: seed_urls (List[str]), crawler_settings (Optional[Dict[str, Any]]), run_id (str = "")
# Output: Optional[Dict[str, Any]]
# Side Effects: writes crawl_result, crawl_math_report, and crawl keyword candidates to Streamlit session state.
# Business Rules: Does not call LLM or Ads; selected report keywords may later be handed to SERP/Ads by UI controls.
# Failure Modes: returns None when no seed URLs are supplied.
# LINKS: PLAN 08-03 Task 4
def run_crawl_math_report_workflow(
    seed_urls: List[str],
    crawler_settings: Optional[Dict[str, Any]] = None,
    run_id: str = "",
) -> Optional[Dict[str, Any]]:
    normalized_urls = _normalize_keyword_seed_input(seed_urls)
    run_prefix = f"[run {run_id}] " if run_id else ""
    if not normalized_urls:
        st.warning(t("crawl_no_seed_urls"))
        return None

    settings = _crawl_settings_from_dict(crawler_settings)
    status_text = st.empty()
    status_text.text(t("crawl_running", count=len(normalized_urls)))
    # Create hash from critical settings to ensure cache invalidation on setting changes
    settings_hash = str(
        (
            settings.max_pages,
            settings.max_depth,
            settings.same_domain_only,
            settings.timeout_seconds,
            settings.max_response_bytes,
            settings.max_retries,
        )
    )
    crawl_result = _cached_bounded_crawl(
        tuple(normalized_urls),
        tuple(sorted(settings.__dict__.items())),
        settings_hash,
    )
    report = build_crawl_math_report(crawl_result)
    st.session_state.crawl_result = crawl_result
    st.session_state.crawl_math_report = report

    keyword_candidates = report.get("keyword_candidates", [])
    if keyword_candidates:
        store_keyword_candidates(
            keywords=keyword_candidates,
            source_url="crawl_math_report",
            source_type=SOURCE_CRAWL_MATH,
            selection_prefix="crawl_math_handoff",
        )

    if report.get("info_message"):
        st.info(report["info_message"])
    else:
        status_text.success(t("crawl_report_complete", count=len(crawl_result.pages)))

    logger.info(
        f"{run_prefix}[GRACE:block_pipeline_crawl_math_report:STATE] beliefState=crawl_math_report_ready "
        f"Crawl report built from {len(crawl_result.pages)} page(s)"
    )
    return report


# block_pipeline_trends_as_stage: Google Trends as optional stage in existing workflows
# Semantic block: Trends workflow that accepts checkbox-selected keywords from various sources


# FUNCTION_CONTRACT: run_trends_stage_from_selection
# Purpose: Run Google Trends analysis on selected keywords from any keyword-producing stage
# Input: selected_contexts (List[SourceContextKey]), trends_config (Optional[Dict[str, Any]]), run_id (str), force_refresh (bool)
# Output: Optional[GoogleTrendsResult]
# Side Effects: Stores google_trends_result and google_trends_tables in session state; renders progress
# Business Rules: Accepts (keyword, source_url) tuples; filters URL-like queries; preserves source URL context
# Failure Modes: Returns None if no keywords or Trends disabled
# LINKS: PLAN 10-02 Task 9
# Rationale: Accepts (keyword, source_url) tuples, preserves source context, filters URL-like queries.
def run_trends_stage_from_selection(
    selected_contexts: List[SourceContextKey],
    trends_config: Optional[Dict[str, Any]] = None,
    run_id: str = "",
    force_refresh: bool = False,
) -> Optional[GoogleTrendsResult]:
    run_prefix = f"[run {run_id}] " if run_id else ""

    if not selected_contexts:
        st.warning(t("trends_no_keywords_selected"))
        return None

    trends_values = dict(trends_config or {})
    if not trends_values.get("enabled", True):
        st.warning(t("google_trends_disabled_warning"))
        return None

    # Extract keywords from tuples, filtering URL-like queries
    trends_keywords: List[str] = []
    for keyword, source_url in selected_contexts:
        cleaned_keyword = str(keyword or "").strip()
        if cleaned_keyword and not is_url_like_query(cleaned_keyword):
            trends_keywords.append(cleaned_keyword)

    if not trends_keywords:
        st.warning(t("google_trends_keyword_warning"))
        return None

    # Log source context preservation
    unique_sources = set(source_url for _, source_url in selected_contexts if source_url)
    if unique_sources:
        logger.info(
            f"{run_prefix}[GRACE:block_pipeline_trends_stage:STATE] beliefState=trends_source_context_preserved "
            f"Running Trends for {len(trends_keywords)} keywords from {len(unique_sources)} source(s)"
        )
    return _run_trends_stage(
        trends_keywords,
        trends_values,
        run_prefix=run_prefix,
        force_refresh=force_refresh,
    )


# FUNCTION_CONTRACT: run_trends_stage_from_keywords
# Purpose: Run Google Trends analysis on a list of keywords (without source context)
# Input: keywords (List[str]), trends_config (Optional[Dict[str, Any]]), run_id (str), force_refresh (bool)
# Output: Optional[GoogleTrendsResult]
# Side Effects: Stores google_trends_result and google_trends_tables in session state; renders progress
# Business Rules: Accepts simple keyword list; filters URL-like queries
# Failure Modes: Returns None if no keywords or Trends disabled
# LINKS: PLAN 10-02 Task 9
# Rationale: Convenience function for workflows without source URL context.
def run_trends_stage_from_keywords(
    keywords: List[str],
    trends_config: Optional[Dict[str, Any]] = None,
    run_id: str = "",
    force_refresh: bool = False,
) -> Optional[GoogleTrendsResult]:
    # Convert keywords list to tuples with empty source URL
    contexts = [(kw, EMPTY_SOURCE_URL) for kw in keywords]
    return run_trends_stage_from_selection(
        selected_contexts=contexts,
        trends_config=trends_config,
        run_id=run_id,
        force_refresh=force_refresh,
    )


# block_pipeline_keyword_to_llm: Standalone keyword-to-LLM SEO text generation workflow
# Semantic block: Keywords go directly to LLM without URL scraping; independent language config


# FUNCTION_CONTRACT: run_keyword_to_llm_workflow
# Purpose: Orchestrate keyword-to-LLM text generation without URL scraping
# Input: keywords (List[str]), provider (str), model (str), language (str), seo_prompt (str), api settings, run_id (str), force_refresh (bool), page_type (str = 'product')
# Output: Optional[pd.DataFrame] — DataFrame with keyword, SEO text, and empty URL columns
# Side Effects: renders Streamlit progress, stores generated_seo_texts and scraped_content in session state
# Business Rules: No URL scraping — keywords go directly to LLM; uses separate language config; empty URL column added for render_seo_results compatibility
# Failure Modes: returns None if no keywords; individual keyword failures logged but do not abort batch; returns partial results if some keywords succeed
# LINKS: PLAN 14-03 Task 1, HIGH-1 (URL column guard), MEDIUM-4 (per-keyword error handling)
# Rationale: Accepts flat list or grouped dicts. Grouped: one LLM call per group with group_id and columns. Individual failures caught (MEDIUM-4). Returns DataFrame with empty URL column (HIGH-1) for render_seo_results.
def run_keyword_to_llm_workflow(
    keywords: List[str],
    provider: str,
    model: str,
    language: str = "Russian",
    seo_prompt: str = "",
    api_timeout: Optional[int] = None,
    api_delay: Optional[int] = None,
    api_retry_count: Optional[int] = None,
    api_retry_delay: Optional[int] = None,
    run_id: str = "",
    force_refresh: bool = False,
    page_type: str = "product",
) -> Optional[pd.DataFrame]:
    # Detect if input is already grouped (list of dicts with 'group_id' and 'keywords')
    is_grouped = (
        len(keywords) > 0
        and isinstance(keywords[0], dict)
        and "group_id" in keywords[0]
        and "keywords" in keywords[0]
    )

    if is_grouped:
        groups = keywords  # type: ignore[assignment]
    else:
        normalized_keywords = _normalize_keyword_seed_input(keywords)
        if not normalized_keywords:
            st.warning(t("keyword_llm_warning"))
            return None
        # Build keyword groups from flat (textarea/CSV) input.
        # parse_keyword_groups splits each non-empty line on comma/semicolon/pipe
        # so a single line can carry several keywords that share one SEO text,
        # matching the documented input rule (see keyword_llm_input_help i18n).
        groups = parse_keyword_groups(normalized_keywords)
        if not groups:
            st.warning(t("keyword_llm_warning"))
            return None

    run_prefix = f"[run {run_id}] " if run_id else ""
    total = len(groups)

    if total == 0:
        st.warning(t("keyword_llm_warning"))
        return None

    progress_bar = st.progress(0)
    status_text = st.empty()
    status_text.text(t("keyword_llm_generating", count=total))

    llm = LLMHandler(
        timeout_seconds=api_timeout,
        delay_between_requests_seconds=api_delay,
        retry_attempts=api_retry_count,
        retry_delay_seconds=api_retry_delay,
        run_label=run_id,
    )

    results: List[Dict[str, str]] = []

    for idx, group in enumerate(groups):
        gid = group["group_id"]
        kw_list = group["keywords"]
        joined_kw = ", ".join(kw_list)

        progress_bar.progress(
            (idx + 1) / total,
            text=t(
                "keyword_llm_generating_keyword",
                idx=idx + 1,
                total=total,
                keyword=joined_kw,
            ),
        )
        generated_text = ""
        # Build fallback text from keywords so the user message is never empty
        # (Vertex AI via Omniroute rejects empty user content with 400)
        text_for_llm: str = "\n".join(f"- {kw}" for kw in kw_list) if kw_list else ""
        try:
            generated_text = llm.generate_seo_text(
                text=text_for_llm,
                keywords=[{"Keyword": kw, "Avg Monthly Searches": "N/A"} for kw in kw_list],
                provider=provider,
                model=model,
                language=language,
                custom_prompt=seo_prompt,
                page_type=page_type,
                force_refresh=force_refresh,
            )
        except Exception as exc:
            logger.warning(
                f"{run_prefix}LLM generation failed for group {gid} ({joined_kw}): {exc}"
            )

        results.append({
            "group_id": gid,
            t("col_keywords"): joined_kw,
            t("col_seo_text"): generated_text,
        })

    if not results:
        progress_bar.progress(1.0)
        return None

    df = pd.DataFrame(results)

    # HIGH-1: Add empty URL column for render_seo_results compatibility
    df["URL"] = ""

    # Store in session state for display compatibility
    st.session_state.generated_seo_texts = df
    st.session_state.scraped_content = {}

    progress_bar.progress(1.0, text=t("pipeline_done"))
    status_text.success(t("keyword_llm_complete", count=len(results)))
    logger.info(
        f"{run_prefix}Keyword-to-LLM workflow completed for {len(results)} group(s)"
    )
    return df
