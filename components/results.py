# MODULE_CONTRACT: components/results
# Purpose: Streamlit results UI for keyword analysis, keyword selection, ideas generation, SEO generation, history views, crawl reports, SERP math reports, generation quality reports, generated text math reports, and Trends-as-stage integration
# Rationale: Keep the post-analysis rendering and export workflow explicit for GRACE adoption and review
# Dependencies: pandas, streamlit, config.settings, config.i18n, utils.logger, utils.llm_handler, utils.excel_exporter, utils.history, utils.google_ads_client, utils.pipeline, utils.seo_math_analysis
# Exports: render_keyword_results, render_scraping_preview, render_keyword_selection, render_keyword_ideas_generation, render_seo_generation, render_seo_results, render_history, render_serp_results, render_serp_related_searches, render_serp_chain_to_ads, render_serp_chained_ads_results, render_keyword_candidate_selector, render_ads_keyword_serp_handoff, render_chained_serp_results, render_bidirectional_chain_buttons, render_serp_math_report, render_crawl_math_report, render_generation_quality_report, render_generated_text_math_report, render_google_trends_results, render_serp_domain_metrics
# LINKS: requirements.xml#UC-004, requirements.xml#UC-005, requirements.xml#UC-006, knowledge-graph.xml#MOD-001, PLAN 08-01, PLAN 08-02 Task 6, PLAN 08-02 Task 7, PLAN 10-02 Task 9, PLAN 15 Task 3
# MODULE_MAP: components/results.py
# Public Functions: render_keyword_results, render_scraping_preview, render_keyword_selection, render_keyword_ideas_generation, render_seo_generation, render_seo_results, render_history, render_serp_results, render_serp_related_searches, render_serp_chain_to_ads, render_serp_chained_ads_results, render_keyword_candidate_selector, render_ads_keyword_serp_handoff, render_chained_serp_results, render_bidirectional_chain_buttons, render_serp_math_report, render_crawl_math_report, render_generation_quality_report, render_generated_text_math_report, render_google_trends_results, render_serp_domain_metrics
# Private Helpers: _build_history_signature, format_source_label, build_history_metadata, _display_results_df, build_keyword_ideas_display_df, build_keyword_idea_seed_key, set_keyword_idea_seed_selection, get_selected_keyword_idea_seed_keywords, limit_keyword_idea_seed_keywords, _display_history_entry, build_history_entry_title, _build_history_checkpoint, restore_history_checkpoint, build_keyword_ideas_signature, merge_keyword_ideas_into_processed_data, deduplicate_processed_data, append_manual_keyword, build_keyword_selection_signature, _clear_keyword_ideas_state, _get_use_url_seed_flags, _save_to_history, _is_ads_keyword_results_df, _store_ads_keyword_candidates, _get_selected_ads_keyword_candidates, _run_serp_after_ads_keywords, _run_chained_serp_keywords, _render_gen_math_aggregate, _render_gen_math_row_summary, _render_gen_math_intent
# Key Semantic Blocks: block_results_display_data_table, block_results_selection_checkboxes, block_results_ideas_planner, block_results_seo_generation, block_results_history_entries, block_results_keyword_handoff_select, block_results_bidirectional_chain, block_results_trends_stage_integration, block_results_math_report_render, block_results_crawl_report_render, block_results_regenerate_quality_feedback, block_results_post_ads_serp_handoff, block_results_gen_text_math_report
# Critical Flows: pipeline execution -> results display -> keyword selection -> ideas generation -> SEO generation/Trends/SERP/Ads -> generated text math analysis -> history save; SERP/crawl results -> math profile -> math report rendering; generated text -> quality scoring -> quality report
# Verification: python -m py_compile, python -m ruff check ., python -m pytest -q
# CHANGE_SUMMARY: Restored top-of-file module contract metadata; added reusable keyword candidate selector and bidirectional chain buttons for staged workflows; Phase 8 Task 6: added SERP math report rendering; Phase 8 Task 7: added generation quality report rendering; Phase 8 Plan 03: added crawl math report rendering and keyword handoff controls; Phase 10 Task 9: added Trends-as-stage buttons after keyword-producing steps.

import io
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pandas as pd
import streamlit as st
from streamlit_shadcn_ui import metric_card
from config.i18n import t, TRANSLATIONS
from config.settings import LLM_CONFIG
from utils.excel_exporter import ExcelExporter
from utils.google_ads_client import GoogleAdsHandler
from utils.history import HistoryManager
from utils.llm_handler import LLMHandler
from utils.logger import logger
from utils.seo_math_analysis import DomainMetrics
from utils.pipeline import (
    KEYWORD_SEED_SOURCE_URL,
    SERP_RELATED_COLUMNS,
    _ensure_result_columns,
    aggregate_serp_per_keyword,
    aggregate_trends_per_keyword,
    build_reverse_math_report,
    google_trends_result_to_tables,
    run_llm_keyword_stage_from_checkpoint,
    run_serp_analysis_workflow,
    run_serp_chain_to_ads_workflow,
    run_serp_workflow_with_source_context,
)
from utils.pipeline import (
    get_selected_keyword_candidates as _pipeline_get_selected_keyword_candidates,
)

_BASE_DIR = Path(__file__).parent.parent
_BM25F_DISPLAY_COLUMN_KEYS = {
    "Doc ID": "seo_math_bm25f_doc_id_column",
    "Text": "seo_math_bm25f_text_column",
    "Score": "seo_math_bm25f_score_column",
    "Coverage": "seo_math_bm25f_coverage_column",
    "Field Contributions": "seo_math_bm25f_field_contributions_column",
    "Matched Terms": "seo_math_bm25f_matched_terms_column",
}


def _render_section_header(title: str, description: str, divider: str) -> None:
    st.subheader(title, divider=divider)
    if description:
        st.caption(description)
# FUNCTION_CONTRACT: _build_history_signature
# Purpose: Implement the  build history signature helper for this module.
# Input: run_id (str), urls (List[str]), keywords (List[str])
# Output: tuple[str, tuple[str, ...], tuple[str, ...]]
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def _build_history_signature(
    run_id: str, urls: List[str], keywords: List[str]
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    return (run_id or "", tuple(urls), tuple(keywords))


# Purpose: Check if an i18n key is defined in TRANSLATIONS.
def _i18n_key_exists(key: str) -> bool:
    return key in TRANSLATIONS


# Purpose:  history key part implementation
def _history_key_part(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    safe = "".join(char if char.isalnum() or char in "-_." else "-" for char in text)
    return safe.strip("-")[:80]


# Purpose:  build history action key implementation
def _build_history_action_key(action_prefix: str, entry: Dict[str, Any], index: int) -> str:
    checkpoint = entry.get("checkpoint") if isinstance(entry.get("checkpoint"), dict) else {}
    metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
    timestamp = entry.get("timestamp") or entry.get("created_at")
    cache_key = entry.get("cache_key") or checkpoint.get("cache_key")
    workflow_mode = (
        entry.get("workflow_mode")
        or metadata.get("workflow_mode")
        or checkpoint.get("workflow_mode")
    )
    identity_payload = {
        "record_id": entry.get("record_id") or entry.get("id"),
        "timestamp": timestamp,
        "cache_key": cache_key,
        "record_type": entry.get("record_type"),
        "kind": entry.get("kind"),
        "workflow_mode": workflow_mode,
        "seed_strategy": metadata.get("seed_strategy") or checkpoint.get("seed_strategy"),
        "run_id": entry.get("run_id") or checkpoint.get("run_id"),
        "urls": entry.get("urls") or checkpoint.get("urls"),
        "keywords": entry.get("keywords") or checkpoint.get("keywords"),
        "index": index,
    }
    identity_json = json.dumps(identity_payload, sort_keys=True, default=str, ensure_ascii=True)
    digest = hashlib.sha1(identity_json.encode("utf-8")).hexdigest()[:12]
    parts = [
        entry.get("record_id") or entry.get("id"),
        timestamp,
        cache_key,
        workflow_mode,
        metadata.get("seed_strategy") or checkpoint.get("seed_strategy"),
        entry.get("record_type") or entry.get("kind"),
    ]
    key_parts = [_history_key_part(part) for part in parts]
    key_parts = [part for part in key_parts if part]
    key_parts.extend([f"idx-{index}", digest])
    return f"{action_prefix}::{'::'.join(key_parts)}"
# FUNCTION_CONTRACT: format_source_label
# Purpose: Implement the format source label helper for this module.
# Input: source_url (str)
# Output: str
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def format_source_label(source_url: str) -> str:
    if source_url == KEYWORD_SEED_SOURCE_URL:
        return t("keyword_seed_source_label")
    return source_url


# FUNCTION_CONTRACT: _render_grouped_keyword_candidate_selector
# Purpose: Render grouped keyword candidates with stable checkbox keys and collect selections by source.
# Input: candidates (List[Dict[str, object]]), selection_prefix (str), title (str), source_for_candidate (Callable), expander_key_for_source (Callable), checkbox_key_for_candidate (Callable), selected_value_for_candidate (Callable), render_header (bool)
# Output: Dict[str, List[Any]]
# Side Effects: Renders Streamlit widgets and updates session-state checkbox keys.
# Business Rules: Groups candidates by source label; select-all checkboxes remain source-scoped; checkbox keys are delegated so callers can preserve keyword-only or source-aware identity.
# Failure Modes: Returns an empty mapping when no selections are checked.
# LINKS: PLAN 08-01 Task 5, PLAN 09-04 Task 5
def _render_grouped_keyword_candidate_selector(
    candidates: List[Dict[str, object]],
    selection_prefix: str,
    title: str,
    source_for_candidate: Callable[[Dict[str, object]], str],
    expander_key_for_source: Callable[[str], str],
    checkbox_key_for_candidate: Callable[[Dict[str, object]], str],
    selected_value_for_candidate: Callable[[Dict[str, object]], Any],
    render_header: bool = True,
) -> Dict[str, List[Any]]:
    if render_header:
        _render_section_header(title, t("candidate_selector_desc"), "blue")

    # FUNCTION_CONTRACT: _on_group_select_all - callback for group select all
    def _on_group_select_all(source: str, group_candidates: List[Dict[str, object]]) -> None:
        select_all_key = f"{selection_prefix}_select_all_{source}"
        new_value = st.session_state.get(select_all_key, False)
        for candidate in group_candidates:
            st.session_state[checkbox_key_for_candidate(candidate)] = new_value

    groups: Dict[str, List[Dict[str, object]]] = {}
    for candidate in candidates:
        source = source_for_candidate(candidate)
        if source not in groups:
            groups[source] = []
        groups[source].append(candidate)

    for source, group_candidates in groups.items():
        source_label = format_source_label(source)
        with st.expander(
            f"{source_label} ({len(group_candidates)} keywords)",
            expanded=False,
            key=expander_key_for_source(source),
        ):
            select_all_key = f"{selection_prefix}_select_all_{source}"
            if select_all_key not in st.session_state:
                st.session_state[select_all_key] = False

            st.checkbox(
                "Select all",
                key=select_all_key,
                on_change=_on_group_select_all,
                args=(source, group_candidates),
            )

            for candidate in group_candidates:
                checkbox_key = checkbox_key_for_candidate(candidate)
                if checkbox_key not in st.session_state:
                    st.session_state[checkbox_key] = False
                st.checkbox(str(candidate.get("keyword", "")), key=checkbox_key)

    selected_by_source: Dict[str, List[Any]] = {}
    for source, group_candidates in groups.items():
        selected: List[Any] = []
        for candidate in group_candidates:
            checkbox_key = checkbox_key_for_candidate(candidate)
            if st.session_state.get(checkbox_key, False):
                selected.append(selected_value_for_candidate(candidate))
        if selected:
            selected_by_source[source] = selected

    st.info(
        f"Selected: {sum(len(values) for values in selected_by_source.values())} / {len(candidates)} keywords"
    )
    return selected_by_source
# FUNCTION_CONTRACT: build_history_metadata
# Purpose: Implement the build history metadata helper for this module.
# Input: workflow_mode (str)
# Output: Dict[str, str]
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def build_history_metadata(workflow_mode: str) -> Dict[str, str]:
    seed_strategy_by_mode = {
        "url_llm": "llm_keywords",
        "url_seed": "url_seed",
        "keyword_seed": "keyword_seed",
    }
    return {
        "workflow_mode": workflow_mode,
        "seed_strategy": seed_strategy_by_mode.get(workflow_mode, workflow_mode),
    }
# FUNCTION_CONTRACT: _display_results_df
# Purpose: Implement the  display results df helper for this module.
# Input: df (pd.DataFrame)
# Output: pd.DataFrame
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def _display_results_df(df: pd.DataFrame) -> pd.DataFrame:
    display_df = df.copy()
    if "Source URL" in display_df.columns:
        display_df["Source URL"] = display_df["Source URL"].map(format_source_label)
    return display_df
# FUNCTION_CONTRACT: build_keyword_ideas_display_df
# Purpose: Implement the build keyword ideas display df helper for this module.
# Input: df (pd.DataFrame)
# Output: pd.DataFrame
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def build_keyword_ideas_display_df(df: pd.DataFrame) -> pd.DataFrame:
    display_df = _display_results_df(df)
    display_columns = [
        "Keyword",
        "Avg Monthly Searches",
        "Competition",
        "Competition Index",
        "Low CPC",
        "High CPC",
        "CPC Currency",
        "Months With Data",
    ]
    existing_columns = [column for column in display_columns if column in display_df.columns]
    return display_df.reindex(columns=existing_columns)
# FUNCTION_CONTRACT: build_keyword_idea_seed_key
# Purpose: Implement the build keyword idea seed key helper for this module.
# Input: url (str), keyword (str)
# Output: str
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def build_keyword_idea_seed_key(url: str, keyword: str) -> str:
    return f"idea_seed::{url}::{keyword}"
# FUNCTION_CONTRACT: set_keyword_idea_seed_selection
# Purpose: Implement the set keyword idea seed selection helper for this module.
# Input: url (str), keywords (List[str]), selected (bool)
# Output: None
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def set_keyword_idea_seed_selection(
    url: str,
    keywords: List[str],
    selected: bool,
) -> None:
    for keyword in keywords:
        st.session_state[build_keyword_idea_seed_key(url, keyword)] = selected
# FUNCTION_CONTRACT: get_selected_keyword_idea_seed_keywords
# Purpose: Implement the get selected keyword idea seed keywords helper for this module.
# Input: url (str), keywords (List[str])
# Output: List[str]
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def get_selected_keyword_idea_seed_keywords(
    url: str,
    keywords: List[str],
) -> List[str]:
    selected_keywords: List[str] = []
    for keyword in keywords:
        seed_key = build_keyword_idea_seed_key(url, keyword)
        if seed_key not in st.session_state:
            st.session_state[seed_key] = True
        if st.session_state.get(seed_key, True):
            selected_keywords.append(keyword)
    return selected_keywords
# FUNCTION_CONTRACT: limit_keyword_idea_seed_keywords
# Purpose: Implement the limit keyword idea seed keywords helper for this module.
# Input: keywords (List[str]), max_keywords (int = 20)
# Output: List[str]
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def limit_keyword_idea_seed_keywords(
    keywords: List[str],
    max_keywords: int = 20,
) -> List[str]:
    return list(keywords[:max_keywords])
# FUNCTION_CONTRACT: _display_history_entry
# Purpose: Implement the  display history entry helper for this module.
# Input: entry (Dict[str, Any])
# Output: Dict[str, Any]
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def _display_history_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    display_entry = dict(entry)
    urls = display_entry.get("urls", [])
    if isinstance(urls, list):
        display_entry["urls"] = [format_source_label(url) for url in urls]
    checkpoint = display_entry.get("checkpoint")
    if isinstance(checkpoint, dict):
        checkpoint = dict(checkpoint)
        scraped_content = checkpoint.get("scraped_content")
        if isinstance(scraped_content, dict):
            checkpoint["scraped_content"] = {
                format_source_label(url): content
                for url, content in scraped_content.items()
            }
        processed_data = checkpoint.get("processed_data")
        if isinstance(processed_data, list):
            checkpoint["processed_data"] = [
                {
                    **row,
                    "Source URL": format_source_label(row.get("Source URL", "")),
                }
                for row in processed_data
            ]
        display_entry["checkpoint"] = checkpoint
    return display_entry
# FUNCTION_CONTRACT: build_history_entry_title
# Purpose: Implement the build history entry title helper for this module.
# Input: entry (Dict[str, Any])
# Output: str
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def build_history_entry_title(entry: Dict[str, Any]) -> str:
    record_type = str(entry.get("record_type", "history")).strip().lower()
    timestamp = entry.get("timestamp") or entry.get("created_at") or entry.get("cache_created_at")
    metadata = entry.get("metadata") or {}
    workflow_mode = metadata.get("workflow_mode", "")

    # Format timestamp nicely
    formatted_time = ""
    if timestamp:
        try:
            dt = datetime.fromisoformat(str(timestamp))
            formatted_time = dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            formatted_time = str(timestamp)

    if record_type == "cache":
        # Use kind-based i18n for cache entries
        kind = str(entry.get("kind", "")).strip().lower()
        kind_key = f"history_card_kind_{kind}" if kind else ""
        kind_label = t(kind_key) if kind_key and _i18n_key_exists(kind_key) else t("history_card_kind_unknown")
        provider = entry.get("provider", "")
        hits = entry.get("cache_hit_count") or entry.get("hits")
        parts = [formatted_time] if formatted_time else []
        parts.append(kind_label)
        if provider:
            parts.append(provider)
        if hits is not None:
            parts.append(f"{t('history_cache_hits_label')}: {hits}")
        return f"💾 {' | '.join(parts)}"
    # History record — use workflow mode i18n
    mode_key = f"history_card_workflow_{workflow_mode}" if workflow_mode else ""
    workflow_label = t(mode_key) if mode_key and _i18n_key_exists(mode_key) else t("history_card_workflow_unknown")
    kw_count = entry.get("keyword_count", 0)
    url_count = entry.get("url_count", 0)
    parts = [formatted_time] if formatted_time else []
    parts.append(workflow_label)
    if url_count:
        parts.append(f"{url_count} URL")
    if kw_count:
        parts.append(f"{kw_count} {t('keywords_count')}")
    return " | ".join(parts)
# FUNCTION_CONTRACT: _build_history_checkpoint
# Purpose: Implement the  build history checkpoint helper for this module.
# Input: df (pd.DataFrame), workflow_mode (str)
# Output: Dict[str, Any]
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def _build_history_checkpoint(df: pd.DataFrame, workflow_mode: str) -> Dict[str, Any]:
    scraped_content = st.session_state.get("scraped_content") or {}
    active_inputs = st.session_state.get("active_inputs") or []
    if not active_inputs and "Source URL" in df.columns:
        active_inputs = df["Source URL"].unique().tolist()
    return {
        "workflow_mode": workflow_mode,
        "active_inputs": list(active_inputs),
        "scraped_content": dict(scraped_content),
        "processed_data": json.loads(df.to_json(orient="records")),
    }
# FUNCTION_CONTRACT: restore_history_checkpoint
# Purpose: Implement the restore history checkpoint helper for this module.
# Input: entry (Dict[str, Any])
# Output: bool
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def restore_history_checkpoint(entry: Dict[str, Any]) -> bool:
    checkpoint = entry.get("checkpoint")
    if not isinstance(checkpoint, dict):
        return False

    for key in list(st.session_state.keys()):
        if key.startswith(
            (
                "kw_",
                "select_all_",
                "use_url_seed::",
                "idea_kw::",
                "idea_seed::",
                "select_all_idea_seed::",
            )
        ):
            del st.session_state[key]

    processed_rows = checkpoint.get("processed_data") or []
    processed_df = pd.DataFrame(processed_rows) if processed_rows else None

    st.session_state.workflow_mode = checkpoint.get(
        "workflow_mode",
        entry.get("metadata", {}).get("workflow_mode", "url_llm"),
    )
    st.session_state.active_inputs = list(
        checkpoint.get("active_inputs") or entry.get("urls", [])
    )
    st.session_state.scraped_content = dict(checkpoint.get("scraped_content") or {})
    st.session_state.processed_data = processed_df
    st.session_state.generated_seo_texts = None
    st.session_state.keyword_ideas_data = None
    st.session_state.keyword_ideas_signature = None
    st.session_state.keyword_selection_signature = None
    st.session_state.keyword_ideas_use_url_seed = {}
    st.session_state.keyword_ideas_flash_message = None
    st.session_state.selected_keywords = {}
    st.session_state.keywords_excel_saved = False
    st.session_state.seo_excel_saved = False
    st.session_state.last_history_signature = None
    st.session_state.current_run_id = f"history-{entry.get('timestamp', 'restored')}"
    return True
# FUNCTION_CONTRACT: build_keyword_ideas_signature
# Purpose: Implement the build keyword ideas signature helper for this module.
# Input: selected_kw_by_url (Dict[str, List[str]]), use_url_seed_by_url (Dict[str, bool])
# Output: tuple[tuple[str, tuple[str, ...], bool], ...]
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def build_keyword_ideas_signature(
    selected_kw_by_url: Dict[str, List[str]],
    use_url_seed_by_url: Dict[str, bool],
) -> tuple[tuple[str, tuple[str, ...], bool], ...]:
    return tuple(
        sorted(
            (
                url,
                tuple(sorted(keywords)),
                bool(use_url_seed_by_url.get(url, False)),
            )
            for url, keywords in selected_kw_by_url.items()
        )
    )
# FUNCTION_CONTRACT: merge_keyword_ideas_into_processed_data
# Purpose: Implement the merge keyword ideas into processed data helper for this module.
# Input: processed_df (pd.DataFrame), keyword_ideas_df (pd.DataFrame)
# Output: pd.DataFrame
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def merge_keyword_ideas_into_processed_data(
    processed_df: pd.DataFrame,
    keyword_ideas_df: pd.DataFrame,
) -> pd.DataFrame:
    if keyword_ideas_df is None or keyword_ideas_df.empty:
        return processed_df
    if processed_df is None or processed_df.empty:
        return keyword_ideas_df.drop_duplicates(
            subset=["Source URL", "Keyword"], keep="first"
        ).reset_index(drop=True)

    all_columns: List[str] = list(processed_df.columns)
    for column in keyword_ideas_df.columns:
        if column not in all_columns:
            all_columns.append(column)

    combined_df = pd.concat(
        [
            processed_df.reindex(columns=all_columns),
            keyword_ideas_df.reindex(columns=all_columns),
        ],
        ignore_index=True,
    )
    return combined_df.drop_duplicates(
        subset=["Source URL", "Keyword"], keep="first"
    ).reset_index(drop=True)
# FUNCTION_CONTRACT: deduplicate_processed_data
# Purpose: Implement the deduplicate processed data helper for this module.
# Input: processed_df (Optional[pd.DataFrame])
# Output: Optional[pd.DataFrame]
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def deduplicate_processed_data(
    processed_df: Optional[pd.DataFrame],
) -> Optional[pd.DataFrame]:
    if processed_df is None:
        return None
    if processed_df.empty:
        return processed_df.reset_index(drop=True)
    if (
        "Source URL" not in processed_df.columns
        or "Keyword" not in processed_df.columns
    ):
        return processed_df.reset_index(drop=True)

    return processed_df.drop_duplicates(
        subset=["Source URL", "Keyword"], keep="first"
    ).reset_index(drop=True)
# FUNCTION_CONTRACT: append_manual_keyword
# Purpose: Implement the append manual keyword helper for this module.
# Input: processed_df (Optional[pd.DataFrame]), target_url (str), keyword (str)
# Output: tuple[pd.DataFrame, bool]
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def append_manual_keyword(
    processed_df: Optional[pd.DataFrame],
    target_url: str,
    keyword: str,
) -> tuple[pd.DataFrame, bool]:
    cleaned_keyword = str(keyword).strip()
    base_df = deduplicate_processed_data(processed_df)

    if base_df is not None and not base_df.empty:
        existing_mask = (base_df["Source URL"].astype(str) == str(target_url)) & (
            base_df["Keyword"].astype(str) == cleaned_keyword
        )
        if existing_mask.any():
            return base_df, False

    all_columns: List[str] = []
    if base_df is not None:
        all_columns = list(base_df.columns)
    for required_column in ("Keyword", "Source URL"):
        if required_column not in all_columns:
            all_columns.append(required_column)

    new_row = pd.DataFrame(
        [{"Keyword": cleaned_keyword, "Source URL": target_url}]
    ).reindex(columns=all_columns)

    if base_df is None or base_df.empty:
        return new_row.reset_index(drop=True), True

    combined_df = pd.concat([base_df, new_row], ignore_index=True)
    return deduplicate_processed_data(combined_df), True
# FUNCTION_CONTRACT: build_keyword_selection_signature
# Purpose: Implement the build keyword selection signature helper for this module.
# Input: processed_df (Optional[pd.DataFrame])
# Output: tuple[str, tuple[tuple[str, tuple[str, ...]], ...]]
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def build_keyword_selection_signature(
    processed_df: Optional[pd.DataFrame],
) -> tuple[str, tuple[tuple[str, tuple[str, ...]], ...]]:
    run_id = str(st.session_state.get("current_run_id", ""))
    if processed_df is None or processed_df.empty:
        return run_id, tuple()

    df = deduplicate_processed_data(processed_df)
    grouped: Dict[str, set[str]] = {}
    for _, row in df.iterrows():
        url = str(row.get("Source URL", "") or "").strip()
        keyword = str(row.get("Keyword", "") or "").strip()
        if not url or not keyword:
            continue
        grouped.setdefault(url, set()).add(keyword)

    return (
        run_id,
        tuple(
            sorted(
                (url, tuple(sorted(keywords)))
                for url, keywords in grouped.items()
            )
        ),
    )
# FUNCTION_CONTRACT: _clear_keyword_ideas_state
# Purpose: Implement the  clear keyword ideas state helper for this module.
# Input: (none)
# Output: None
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def _clear_keyword_ideas_state() -> None:
    st.session_state.keyword_ideas_data = None
    st.session_state.keyword_ideas_signature = None
# FUNCTION_CONTRACT: _get_use_url_seed_flags
# Purpose: Implement the  get use url seed flags helper for this module.
# Input: urls (List[str])
# Output: Dict[str, bool]
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def _get_use_url_seed_flags(urls: List[str]) -> Dict[str, bool]:
    flags: Dict[str, bool] = {}
    for url in urls:
        session_key = f"use_url_seed::{url}"
        if session_key not in st.session_state:
            st.session_state[session_key] = False
        flags[url] = bool(st.session_state.get(session_key, False))
    st.session_state.keyword_ideas_use_url_seed = flags
    return flags
# FUNCTION_CONTRACT: _render_table_preview_with_exports
# Purpose: Reusable helper for full-width table preview with export buttons below
# Input: df (pd.DataFrame), display_df (pd.DataFrame), auto_save_excel (bool), save_key (str), excel_filename_prefix (str)
# Output: None
# Side Effects: Renders Streamlit UI; handles auto-save and downloads
# Business Rules: Full-width table, export buttons stacked below
# Failure Modes: Handles exceptions gracefully
# LINKS: PLAN 09-04 Task 6
def _render_table_preview_with_exports(
    df: pd.DataFrame,
    display_df: pd.DataFrame,
    auto_save_excel: bool,
    save_key: str,
    excel_filename_prefix: str,
    csv_download_key: str = "",
) -> None:
    """Render full-width table preview with export buttons below (Phase 9 layout)."""
    with st.container():
        if auto_save_excel and not st.session_state.get(save_key, False):
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            filename = f"{excel_filename_prefix}_{timestamp}.xlsx"
            output_path = _BASE_DIR / "outputs" / filename
            output_path.parent.mkdir(exist_ok=True)

            if ExcelExporter.export(df, str(output_path)):
                st.session_state[save_key] = True
                logger.info(f"Auto-saved: {output_path}")
            else:
                st.error(t("autosave_error"))

        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            try:
                buffer = io.BytesIO()
                ExcelExporter.export_to_buffer(df, buffer)
                st.download_button(
                    label=t("download_excel"),
                    data=buffer.getvalue(),
                    file_name=f"{excel_filename_prefix}_{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            except Exception as e:
                st.error(f"{t('export_error')}: {e}")
        with btn_col2:
            try:
                csv_data = ExcelExporter.export_csv_to_bytes(df)
                st.download_button(
                    label=t("download_csv"),
                    data=csv_data,
                    file_name=f"{excel_filename_prefix}_{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv",
                    mime="text/csv",
                    key=csv_download_key or f"download_{excel_filename_prefix}_csv",
                )
            except Exception as e:
                st.error(f"{t('csv_error')}: {e}")

    # Full-width table
    st.dataframe(display_df, use_container_width=True, hide_index=True)


def _render_metric_row(items: List[Dict[str, str]]) -> None:
    if not items:
        return
    cols = st.columns(len(items))
    for col, item in zip(cols, items):
        with col:
            metric_card(
                title=item.get("title", ""),
                content=item.get("content", ""),
                description=item.get("description", ""),
                key=item.get("key"),
            )


# FUNCTION_CONTRACT: render_keyword_results
# Purpose: Implement the render keyword results helper for this module.
# Input: auto_save_excel (bool)
# Output: None
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001, PLAN 10-02 Task 9
def render_keyword_results(
    auto_save_excel: bool,
    serp_config: Optional[dict] = None,
    force_refresh: bool = False,
    trends_config: Optional[dict] = None,
) -> None:
    if st.session_state.processed_data is None:
        return

    _render_section_header(t("results_header"), t("results_spreadsheet_desc"), "blue")

    df: pd.DataFrame = st.session_state.processed_data

    # SERP match enrichment for URL workflows (Task 8)
    match_index = st.session_state.get("serp_match_index")
    if (
        match_index
        and "Keyword" in df.columns
        and "Source URL" in df.columns
    ):
        from utils.pipeline import enrich_ads_dataframe_with_serp_context
        enriched_df = enrich_ads_dataframe_with_serp_context(df)
        if enriched_df is not None:
            df = enriched_df
            st.session_state.processed_data = df

    display_df = _display_results_df(df)

    _render_metric_row(
        [
            {
                "title": t("keyword_results_rows_title"),
                "content": f"{len(display_df):,}",
                "description": t("keyword_results_rows_desc"),
                "key": "keyword_results_rows_metric",
            },
            {
                "title": t("keyword_results_sources_title"),
                "content": f"{display_df['Source URL'].nunique() if 'Source URL' in display_df.columns else 0:,}",
                "description": t("keyword_results_sources_desc"),
                "key": "keyword_results_sources_metric",
            },
            {
                "title": t("keyword_results_autosave_title"),
                "content": t("ui_enabled") if auto_save_excel else t("ui_disabled"),
                "description": t("keyword_results_autosave_desc"),
                "key": "keyword_results_autosave_metric",
            },
        ]
    )

    _render_table_preview_with_exports(
        df=df,
        display_df=display_df,
        auto_save_excel=auto_save_excel,
        save_key="keywords_excel_saved",
        excel_filename_prefix="keywords_export",
        csv_download_key="download_keywords_csv",
    )

    st.caption(
        t(
            "total_keywords_stat",
            count=len(df),
            sources=display_df["Source URL"].nunique() if "Source URL" in display_df.columns else 0,
        )
    )
    workflow_mode = st.session_state.get("workflow_mode")
    if workflow_mode in ("url_llm", "url_seed", "keyword_seed") and _is_ads_keyword_results_df(df):
        run_id = str(st.session_state.get("current_run_id", ""))
        render_ads_keyword_serp_handoff(
            df,
            selection_prefix=f"{workflow_mode}_ads_serp::{run_id}",
            title=t("select_keywords_for_serp"),
            run_id=run_id,
            serp_config=serp_config,
            force_refresh=force_refresh,
            trends_config=trends_config,  # Phase 10 Task 9: Trends stage
        )
    _save_to_history(df)
# FUNCTION_CONTRACT: render_scraping_preview
# Purpose: Implement the render scraping preview helper for this module.
# Input: (none)
# Output: None
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def render_scraping_preview() -> None:
    if (
        "scraped_content" not in st.session_state
        or not st.session_state.scraped_content
    ):
        return

    _render_section_header(t("scraping_preview"), t("scraping_preview_desc"), "orange")

    for url, content in st.session_state.scraped_content.items():
        with st.expander(f"{url} ({len(content)} {t('chars')})"):
            st.code(content, language=None, wrap_lines=True)
# FUNCTION_CONTRACT: render_keyword_selection
# Purpose: Implement the render keyword selection helper for this module.
# Input: (none)
# Output: None
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def render_keyword_selection() -> None:
    if st.session_state.processed_data is None:
        return

    if (
        "scraped_content" not in st.session_state
        or not st.session_state.scraped_content
    ):
        return

    df: pd.DataFrame = deduplicate_processed_data(st.session_state.processed_data)
    st.session_state.processed_data = df
    current_signature = build_keyword_selection_signature(df)
    stored_signature = st.session_state.get("keyword_selection_signature")
    if stored_signature != current_signature:
        for state_key in list(st.session_state.keys()):
            if state_key.startswith(("kw_", "select_all_")):
                del st.session_state[state_key]
        st.session_state.keyword_selection_signature = current_signature

    _render_section_header(t("keyword_selection_header"), t("keyword_selection_desc"), "green")

    unique_urls: List[str] = df["Source URL"].unique().tolist()

    st.write(t("select_keywords_desc"))

    new_keyword: str = st.text_input(
        t("add_keyword_manual"),
        key="manual_keyword_input",
    )
    if new_keyword and new_keyword.strip():
        target_url: str = st.selectbox(
            t("for_which_url"), unique_urls, key="manual_kw_url"
        )
        if st.button(t("add_button"), key="add_manual_kw"):
            cleaned_keyword = new_keyword.strip()
            kw_key: str = f"kw_{target_url}_{cleaned_keyword}"
            updated_df, added = append_manual_keyword(
                st.session_state.processed_data,
                target_url=target_url,
                keyword=cleaned_keyword,
            )
            st.session_state.processed_data = updated_df
            if added:
                st.session_state[kw_key] = True
            _clear_keyword_ideas_state()
            st.rerun()
    # FUNCTION_CONTRACT: _on_select_all_change
    # Purpose: Implement the  on select all change helper for this module.
    # Input: url (str), keywords (List[str])
    # Output: None
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def _on_select_all_change(url: str, keywords: List[str]) -> None:
        select_all_key = f"select_all_{url}"
        new_value = st.session_state[select_all_key]
        for kw in keywords:
            st.session_state[f"kw_{url}_{kw}"] = new_value

    for url in unique_urls:
        url_keywords: List[str] = df[df["Source URL"] == url]["Keyword"].tolist()

        with st.expander(
            f"{url} ({len(url_keywords)} {t('keywords_count')})", expanded=False,
            key=f"kw_sel_expander::{url}",
        ):
            select_all_key: str = f"select_all_{url}"
            if select_all_key not in st.session_state:
                st.session_state[select_all_key] = True

            st.checkbox(
                t("select_all"),
                key=select_all_key,
                on_change=_on_select_all_change,
                args=(url, url_keywords),
            )

            for kw in url_keywords:
                kw_key = f"kw_{url}_{kw}"
                if kw_key not in st.session_state:
                    st.session_state[kw_key] = True

                st.checkbox(kw, key=kw_key)

    selected_kw_by_url: Dict[str, List[str]] = {}
    for url in unique_urls:
        url_keywords = df[df["Source URL"] == url]["Keyword"].tolist()
        selected: List[str] = []
        for kw in url_keywords:
            kw_key = f"kw_{url}_{kw}"
            if st.session_state.get(kw_key, True):
                selected.append(kw)
        if selected:
            selected_kw_by_url[url] = selected

    st.session_state.selected_keywords = selected_kw_by_url

    total_selected: int = sum(len(v) for v in selected_kw_by_url.values())
    st.info(
        t(
            "selected_keywords_stat",
            selected=total_selected,
            total=len(df),
            urls=len(selected_kw_by_url),
        )
    )

    return selected_kw_by_url, total_selected
# FUNCTION_CONTRACT: render_keyword_ideas_generation
# Purpose: Implement the render keyword ideas generation helper for this module.
# Input: location_id (str), language_id (Any), currency_code (str), selected_kw_by_url (Dict[str, List[str]]), total_selected (int)
# Output: None
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def render_keyword_ideas_generation(
    location_id: str,
    language_id: Any,
    currency_code: str,
    selected_kw_by_url: Dict[str, List[str]],
    total_selected: int,
    force_refresh: bool = False,
    trends_config: Optional[dict] = None,  # Phase 10 Task 9: Trends stage
) -> None:
    _render_section_header(t("keyword_ideas_header"), t("keyword_ideas_desc"), "green")

    flash_message = st.session_state.pop("keyword_ideas_flash_message", None)
    if flash_message:
        st.success(flash_message)

    if total_selected == 0:
        return

    selected_urls: List[str] = list(selected_kw_by_url.keys())
    use_url_seed_by_url = _get_use_url_seed_flags(selected_urls)
    selected_seed_keywords_by_url: Dict[str, List[str]] = {}
    for url in selected_urls:
        selected_seed_keywords_by_url[url] = get_selected_keyword_idea_seed_keywords(
            url,
            selected_kw_by_url[url],
        )
    current_signature = build_keyword_ideas_signature(
        selected_seed_keywords_by_url,
        use_url_seed_by_url,
    )

    stored_signature = st.session_state.get("keyword_ideas_signature")
    if stored_signature is not None and stored_signature != current_signature:
        _clear_keyword_ideas_state()
    # FUNCTION_CONTRACT: _on_seed_select_all_change
    # Purpose: Implement the  on seed select all change helper for this module.
    # Input: url (str), keywords (List[str])
    # Output: None
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def _on_seed_select_all_change(url: str, keywords: List[str]) -> None:
        select_all_key = f"select_all_idea_seed::{url}"
        set_keyword_idea_seed_selection(
            url,
            keywords,
            selected=bool(st.session_state.get(select_all_key, False)),
        )

    for url in selected_urls:
        with st.expander(url, expanded=False, key=f"kw_idea_seed_expander::{url}"):
            url_keywords = selected_kw_by_url[url]
            select_all_key = f"select_all_idea_seed::{url}"
            if select_all_key not in st.session_state:
                st.session_state[select_all_key] = True

            st.caption(t("keyword_ideas_seed_keywords"))
            st.checkbox(
                t("select_all"),
                key=select_all_key,
                on_change=_on_seed_select_all_change,
                args=(url, url_keywords),
            )
            for keyword in url_keywords:
                seed_key = build_keyword_idea_seed_key(url, keyword)
                if seed_key not in st.session_state:
                    st.session_state[seed_key] = True
                st.checkbox(str(keyword), key=seed_key)

            selected_seed_count = len(
                get_selected_keyword_idea_seed_keywords(url, url_keywords)
            )
            st.caption(
                t(
                    "keyword_ideas_seed_keywords_stat",
                    selected=selected_seed_count,
                    total=len(url_keywords),
                    limit=20,
                )
            )
            st.checkbox(
                t("use_url_as_seed"),
                key=f"use_url_seed::{url}",
            )

    if st.button(
        t("generate_keyword_ideas_button"),
        type="primary",
        key="generate_keyword_ideas",
        disabled=total_selected == 0,
    ):
        ideas_status = st.status(t("keyword_ideas_generating"), expanded=True)
        ideas_frames: List[pd.DataFrame] = []
        ads_handler = GoogleAdsHandler(
            location_id=location_id,
            language_id=language_id,
            target_currency_code=currency_code,
        )

        for url in selected_urls:
            use_url_seed = bool(st.session_state.get(f"use_url_seed::{url}", False))
            selected_seed_keywords = get_selected_keyword_idea_seed_keywords(
                url,
                selected_kw_by_url[url],
            )
            request_seed_keywords = limit_keyword_idea_seed_keywords(selected_seed_keywords)
            ideas_status.write(
                t(
                    "keyword_ideas_processing_url",
                    url=url,
                    mode=t("use_url_as_seed")
                    if use_url_seed
                    else t("keyword_only_seed"),
                )
            )
            if not request_seed_keywords and not use_url_seed:
                ideas_status.write(
                    t("keyword_ideas_skip_no_seed_keywords", url=url)
                )
                continue
            if len(selected_seed_keywords) > len(request_seed_keywords):
                ideas_status.write(
                    t(
                        "keyword_ideas_seed_limit_notice",
                        url=url,
                        selected=len(selected_seed_keywords),
                        used=len(request_seed_keywords),
                        limit=20,
                    )
                )
            ideas_df = ads_handler.get_keyword_ideas(
                request_seed_keywords,
                page_url=url if use_url_seed else None,
                source_url=url,
                force_refresh=force_refresh,
            )
            if not ideas_df.empty:
                ideas_frames.append(ideas_df)

        if ideas_frames:
            keyword_ideas_df = pd.concat(ideas_frames, ignore_index=True)
            keyword_ideas_df = keyword_ideas_df.drop_duplicates(
                subset=["Source URL", "Keyword"], keep="first"
            ).reset_index(drop=True)
        else:
            keyword_ideas_df = pd.DataFrame()

        st.session_state.keyword_ideas_data = keyword_ideas_df
        st.session_state.keyword_ideas_signature = build_keyword_ideas_signature(
            selected_seed_keywords_by_url,
            _get_use_url_seed_flags(selected_urls),
        )
        ideas_status.update(
            label=t("keyword_ideas_generation_complete"),
            state="complete",
            expanded=False,
        )
        st.rerun()

    keyword_ideas_df = st.session_state.get("keyword_ideas_data")
    if keyword_ideas_df is None:
        return

    if keyword_ideas_df.empty:
        st.info(t("keyword_ideas_empty"))
        return

    for url in selected_urls:
        url_df = keyword_ideas_df[keyword_ideas_df["Source URL"] == url]
        if url_df.empty:
            continue

        with st.expander(
            f"{url} ({len(url_df)} {t('keywords_count')})", expanded=False,
            key=f"kw_ideas_gen_expander::{url}",
        ):
            st.dataframe(build_keyword_ideas_display_df(url_df), width="stretch")
            for _, row in url_df.iterrows():
                idea_key = f"idea_kw::{row['Source URL']}::{row['Keyword']}"
                if idea_key not in st.session_state:
                    st.session_state[idea_key] = True
                st.checkbox(
                    str(row["Keyword"]),
                    key=idea_key,
                )

    run_id = str(st.session_state.get("current_run_id", ""))
    render_ads_keyword_serp_handoff(
        keyword_ideas_df,
        selection_prefix=f"llm_ads_serp::{run_id}",
        title=t("select_keywords_for_serp"),
        run_id=run_id,
        trends_config=trends_config,  # Phase 10 Task 9: Trends stage
    )

    if st.button(
        t("keyword_ideas_add_button"),
        key="apply_keyword_ideas",
        disabled=keyword_ideas_df.empty,
    ):
        selected_rows: List[Dict[str, Any]] = []
        for _, row in keyword_ideas_df.iterrows():
            idea_key = f"idea_kw::{row['Source URL']}::{row['Keyword']}"
            if st.session_state.get(idea_key, True):
                selected_rows.append(row.to_dict())

        if not selected_rows:
            st.warning(t("keyword_ideas_select_warning"))
            return

        existing_pairs = set()
        processed_df = st.session_state.processed_data
        if processed_df is not None and not processed_df.empty:
            existing_pairs = set(
                zip(processed_df["Source URL"], processed_df["Keyword"])
            )

        selected_df = pd.DataFrame(selected_rows)
        st.session_state.processed_data = merge_keyword_ideas_into_processed_data(
            st.session_state.processed_data,
            selected_df,
        )

        added_count = 0
        for row in selected_rows:
            row_pair = (row["Source URL"], row["Keyword"])
            if row_pair not in existing_pairs:
                added_count += 1
                st.session_state[f"kw_{row['Source URL']}_{row['Keyword']}"] = True

        # Force the SEO keyword picker to rebuild from the updated processed_data
        # on the next rerun, so newly added ideas become selectable immediately.
        st.session_state.keyword_selection_signature = None
        st.session_state.selected_keywords = {}
        st.session_state.keyword_ideas_flash_message = t(
            "keyword_ideas_added_success",
            count=added_count,
        )
        _clear_keyword_ideas_state()
        st.rerun()
# FUNCTION_CONTRACT: render_seo_generation
# Purpose: Implement the render seo generation helper for this module.
# Input: provider (str), model_name (str), selected_kw_by_url (Dict[str, List[str]]), total_selected (int), seo_prompt (str = ''), language (str = ''), api_timeout (Optional[int] = None), api_delay (Optional[int] = None), api_retry_count (Optional[int] = None), api_retry_delay (Optional[int] = None), page_type (str = 'product')
# Output: None
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Uses passed language parameter for generation; falls back to LLM_CONFIG generation_language
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def render_seo_generation(
    provider: str,
    model_name: str,
    selected_kw_by_url: Dict[str, List[str]],
    total_selected: int,
    seo_prompt: str = "",
    language: str = "",
    api_timeout: Optional[int] = None,
    api_delay: Optional[int] = None,
    api_retry_count: Optional[int] = None,
    api_retry_delay: Optional[int] = None,
    page_type: str = "product",
) -> None:
    df: pd.DataFrame = st.session_state.processed_data

    _render_section_header(t("seo_generation_header"), t("seo_generation_desc"), "blue")

    force_refresh = bool(st.session_state.pop("seo_force_regenerate", False))
    # The URL_LLM "Generate SEO text" handoff button stages the SEO context then
    # arms seo_auto_generate so the LLM runs on the next render WITHOUT requiring
    # an extra inner-button click. Consumed here, mirroring seo_force_regenerate.
    auto_generate = bool(st.session_state.pop("seo_auto_generate", False))

    if force_refresh or auto_generate or st.button(
        t("generate_seo_button"),
        type="primary",
        disabled=total_selected == 0,
    ):
        st.session_state.seo_excel_saved = False
        text_progress = st.status(t("generating"), expanded=True)

        llm_gen = LLMHandler(
            timeout_seconds=api_timeout,
            delay_between_requests_seconds=api_delay,
            retry_attempts=api_retry_count,
            retry_delay_seconds=api_retry_delay,
            run_label=st.session_state.get("current_run_id", ""),
        )
        generated_results: List[Dict[str, str]] = []

        selected_urls: List[str] = list(selected_kw_by_url.keys())
        url_progress = st.progress(0, text=t("generating_progress"))

        for idx, url in enumerate(selected_urls):
            url_progress.progress(
                (idx) / len(selected_urls),
                text=t(
                    "generating_url", idx=idx + 1, total=len(selected_urls), url=url
                ),
            )
            text_progress.write(t("processing_url", url=url))

            content: str = st.session_state.scraped_content.get(url, "")
            if not content:
                text_progress.warning(t("no_content_for_url", url=url))
                continue

            selected_kws: List[str] = selected_kw_by_url[url]
            url_df = df[(df["Source URL"] == url) & (df["Keyword"].isin(selected_kws))]

            keywords_payload: List[Dict[str, Any]] = []
            keywords_list_str: List[str] = []
            for _, row in url_df.iterrows():
                vol = row.get("Avg Monthly Searches")
                keywords_payload.append(
                    {
                        "Keyword": row["Keyword"],
                        "Avg Monthly Searches": int(vol) if pd.notna(vol) else "N/A",
                    }
                )
                keywords_list_str.append(row["Keyword"])

            gen_lang: str = language or LLM_CONFIG.get("keyword_llm_generation_language") or LLM_CONFIG.get("generation_language", "Russian")

            seo_text: str = llm_gen.generate_seo_text(
                text=content,
                keywords=keywords_payload,
                provider=provider,
                model=model_name,
                language=gen_lang,
                custom_prompt=seo_prompt,
                page_type=page_type,
                force_refresh=force_refresh,
            )

            generated_results.append(
                {
                    t("col_keywords"): ", ".join(keywords_list_str),
                    "URL": url,
                    t("col_seo_text"): seo_text,
                }
            )

        url_progress.progress(1.0, text=t("generation_complete"))

        if generated_results:
            st.session_state.generated_seo_texts = pd.DataFrame(generated_results)

        text_progress.update(
            label=t("generation_complete"), state="complete", expanded=False
        )
        if force_refresh:
            st.success(t("regenerate_seo_success"))
        else:
            st.success(t("seo_success"))
        st.rerun()
# FUNCTION_CONTRACT: render_seo_results
# Purpose: Render generated SEO texts with table preview, exports, and regenerate button
# Input: auto_save_excel (bool)
# Output: None
# Side Effects: May set seo_force_regenerate in session state and trigger st.rerun()
# Business Rules: Regenerate bypasses cache/history for fresh LLM generation; clears force flag on each render
# Failure Modes: Returns silently when no generated texts exist
# LINKS: requirements.xml#UC-001
def render_seo_results(auto_save_excel: bool) -> None:
    if st.session_state.generated_seo_texts is None:
        return

    _render_section_header(t("seo_results_header"), t("seo_results_desc"), "blue")

    gen_df: pd.DataFrame = st.session_state.generated_seo_texts

    gen_df_export: pd.DataFrame = gen_df.copy()
    gen_df_export["Page Content"] = gen_df_export["URL"].map(
        lambda u: st.session_state.scraped_content.get(u, "")
    )

    _render_table_preview_with_exports(
        df=gen_df_export,
        display_df=gen_df,
        auto_save_excel=auto_save_excel,
        save_key="seo_excel_saved",
        excel_filename_prefix="seo_texts_export",
        csv_download_key="download_seo_texts_csv",
    )

    # Regenerate button — bypasses cache for fresh LLM generation
    if st.button(t("regenerate_seo_button"), key="seo_regenerate_btn"):
        st.session_state["seo_force_regenerate"] = True
        st.info(t("regenerate_seo_started"))
        st.rerun()
# FUNCTION_CONTRACT: _deserialize_cache_payload
# Purpose: Deserialize a cache payload back into its original Python object.
# Input: payload (Any) — a cached payload from history or session storage
# Output: Any — the restored Python object, including DataFrame, list, or original payload
# Side Effects: None
# Business Rules: Treat serialized DataFrame payloads with columns/data keys as DataFrames when rows exist; pass through other payloads unchanged
# Failure Modes: Returns the input payload unchanged when it cannot be specialized
def _deserialize_cache_payload(payload: Any) -> Any:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        # DataFrame serialized as {"columns": [...], "data": [...]}
        if "columns" in payload and "data" in payload:
            columns = payload["columns"]
            rows = payload["data"]
            if isinstance(columns, list) and isinstance(rows, list) and rows:
                return pd.DataFrame(rows, columns=columns)
        return payload
    return payload


# Purpose: Flatten raw SERP API response list into a processed_data DataFrame.
# Each element in payload is a dict with keys: keyword, organic, related_searches, etc.
# The organic list contains per-position result dicts.
def _flatten_serp_payload(payload: list) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        keyword = item.get("keyword", "")
        provider = item.get("provider", "")
        for organic_item in item.get("organic", []):
            if not isinstance(organic_item, dict):
                continue
            rows.append({
                "Keyword": keyword,
                "Position": organic_item.get("position"),
                "Title": organic_item.get("title", ""),
                "URL": organic_item.get("url", ""),
                "Snippet": organic_item.get("snippet", ""),
                "Displayed Link": organic_item.get("displayed_link", ""),
                "Rich Snippet": organic_item.get("rich_snippet_text", organic_item.get("rich_snippet", "")),
                "Provider": provider,
            })
    if rows:
        return pd.DataFrame(rows)
    return pd.DataFrame()


# Purpose: Extract related_searches and people_also_ask from SERP payload.
def _restore_serp_related_data(payload: list) -> List[Dict[str, str]]:
    related: List[Dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        keyword = item.get("keyword", "")
        for rs in item.get("related_searches", []):
            related.append({"Keyword": keyword, "Related Query": rs, "Type": "related_search"})
        for paa in item.get("people_also_ask", []):
            paa_text = paa if isinstance(paa, str) else paa.get("question", str(paa))
            related.append({"Keyword": keyword, "Related Query": paa_text, "Type": "people_also_ask"})
    return related


# FUNCTION_CONTRACT: _restore_cache_to_session
# Purpose: Restore a cache record's result payload into session state based on its kind.
# Input: entry (Dict[str, Any]) — a cache record from history
# Output: bool — True if restore succeeded, False if kind is unsupported or payload is missing
# Side Effects: Writes to st.session_state (processed_data, trends_results, serp_math_profile, serp_related_data, serp_domain_metrics)
# Business Rules: Only restores for supported kinds (serp, ads, crawl, math, trends, llm_extract)
# Failure Modes: Returns False for missing/unsupported payloads without crashing
# LINKS: PLAN 15-03 Task 2
def _restore_cache_to_session(entry: Dict[str, Any]) -> bool:
    kind = str(entry.get("kind", "")).strip().lower()
    result_obj = entry.get("result")
    if not isinstance(result_obj, dict):
        return False
    payload = result_obj.get("payload")
    if not payload:
        return False

    try:
        deserialized = _deserialize_cache_payload(payload)

        if kind == "serp":
            # SERP payload is a list of {keyword, organic: [...], ...} dicts
            # Need to flatten into DataFrame with proper columns
            if isinstance(deserialized, list) and deserialized:
                serp_df = _flatten_serp_payload(deserialized)
                if not serp_df.empty:
                    st.session_state.processed_data = serp_df
                    # Also restore related data
                    st.session_state.serp_related_data = _restore_serp_related_data(deserialized)
                    # Recompute domain metrics
                    from utils.seo_math_analysis import compute_domain_metrics
                    st.session_state.serp_domain_metrics = compute_domain_metrics(serp_df)
                    return True
            elif isinstance(deserialized, pd.DataFrame) and not deserialized.empty:
                st.session_state.processed_data = deserialized
                return True
        elif kind in ("ads", "crawl", "llm_extract"):
            if isinstance(deserialized, pd.DataFrame) and not deserialized.empty:
                st.session_state.processed_data = deserialized
                return True
            if isinstance(deserialized, list) and deserialized:
                st.session_state.processed_data = pd.DataFrame(deserialized)
                return True
        elif kind == "trends":
            if isinstance(deserialized, pd.DataFrame) and not deserialized.empty:
                st.session_state.trends_results = deserialized
                return True
            if isinstance(deserialized, list) and deserialized:
                st.session_state.trends_results = pd.DataFrame(deserialized)
                return True
            # Trends payload may be a dict with nested structure
            if isinstance(deserialized, dict):
                st.session_state.trends_results = deserialized
                return True
        elif kind == "math":
            if isinstance(deserialized, dict):
                st.session_state.serp_math_profile = deserialized
                return True
        return False
    except Exception as e:
        logger.warning(f"Cache restore failed for kind={kind}: {e}")
        return False


# FUNCTION_CONTRACT: _render_paginated_history
# Purpose: Render history records with "Load more" pagination.
# Input: records (List[Dict]), tab_id (str), index_offset (int)
# Output: None
# Side Effects: Reads/writes st.session_state for page tracking; renders cards and Load More button
# Business Rules: Shows 10 records per page; preserves page state across reruns
# Failure Modes: Gracefully handles empty records
# LINKS: Phase 15
def _render_paginated_history(
    records: List[Dict[str, Any]],
    tab_id: str,
    index_offset: int,
    card_renderer: Any = None,
) -> None:
    if not records:
        return

    page_size = 10
    page_key = f"history_page_{tab_id}"
    current_page = int(st.session_state.get(page_key, 1))

    # Most recent first
    reversed_records = list(reversed(records))
    total = len(reversed_records)
    end_idx = current_page * page_size
    visible = reversed_records[:end_idx]

    for idx, entry in enumerate(visible):
        if card_renderer is not None:
            card_renderer(entry, index_offset + idx)

    remaining = total - end_idx
    if remaining > 0:
        if st.button(
            t("history_load_more", remaining=remaining),
            key=f"load_more_{tab_id}",
        ):
            st.session_state[page_key] = current_page + 1
            st.rerun()
    else:
        st.caption(t("history_showing_all"))


# FUNCTION_CONTRACT: render_clear_cache_dialog_body
# Purpose: Render the body of the clear-cache confirmation modal and run the destructive clear on confirm.
# Input: None (reads i18n via t() and HistoryManager from module scope).
# Output: None
# Side Effects: On user confirmation ("Yes, clear"), calls HistoryManager.clear_history(clear_cache=True),
#   sets st.session_state["history_flash_message"] on success (or st.error on failure), and calls st.rerun().
#   On cancel, calls st.rerun() to close the dialog. Does NOT clear anything until the confirm button is pressed.
# Business Rules:
#   1. Two-button modal: a primary "Yes, clear" (type="primary") and a secondary "Cancel".
#   2. Only the confirm button triggers the clear; the main "Clear history and cache" button outside the
#      dialog only opens this popup (see show_clear_cache_confirm_dialog).
#   3. Mirrors the pre-gate success/failure contract: success flash via history_flash_message + st.rerun();
#      failure via st.error(history_clear_cache_error).
# Failure Modes: If HistoryManager.clear_history returns False, shows st.error and does not rerun.
# LINKS: requirements.xml#UC-001, history_clear_cache_button handler in render_history.
def render_clear_cache_dialog_body() -> None:
    st.write(t("history_clear_cache_confirm_body"))
    col_yes, col_cancel = st.columns(2)
    with col_yes:
        if st.button(t("history_clear_cache_confirm_yes"), key="history_clear_cache_confirm_yes", type="primary"):
            if HistoryManager.clear_history(clear_cache=True):
                st.session_state.history_flash_message = t("history_clear_cache_success")
                st.rerun()
            else:
                st.error(t("history_clear_cache_error"))
    with col_cancel:
        if st.button(t("history_clear_cache_confirm_cancel"), key="history_clear_cache_confirm_cancel"):
            st.rerun()


# FUNCTION_CONTRACT: show_clear_cache_confirm_dialog
# Purpose: Open the modal confirmation popup before the destructive history+cache clear.
# Input: None.
# Output: None
# Side Effects: Opens a modal dialog whose body (render_clear_cache_dialog_body) performs the actual
#   confirmation buttons and clear. The clear itself only runs when the user confirms inside the dialog.
# Business Rules: Thin @st.dialog wrapper around render_clear_cache_dialog_body; separated so the body
#   logic is unit-testable without Streamlit's dialog runtime.
# Failure Modes: None of its own; delegates to render_clear_cache_dialog_body.
# LINKS: requirements.xml#UC-001, history_clear_cache_button handler in render_history.
@st.dialog(t("history_clear_cache_confirm_title"))
def show_clear_cache_confirm_dialog() -> None:
    render_clear_cache_dialog_body()


# FUNCTION_CONTRACT: render_history
# Purpose: Implement the render history helper for this module.
# Input: provider (str), model_name (str), max_keywords (int), location_id (str), language_id (Any), currency_code (str), keyword_prompt (str = ''), api_timeout (Optional[int] = None), api_delay (Optional[int] = None), api_retry_count (Optional[int] = None), api_retry_delay (Optional[int] = None)
# Output: None
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def render_history(
    provider: str,
    model_name: str,
    max_keywords: int,
    location_id: str,
    language_id: Any,
    currency_code: str,
    keyword_prompt: str = "",
    api_timeout: Optional[int] = None,
    api_delay: Optional[int] = None,
    api_retry_count: Optional[int] = None,
    api_retry_delay: Optional[int] = None,
) -> None:
    _render_section_header(t("history_header"), t("history_header_desc"), "green")
    flash_message = st.session_state.pop("history_flash_message", None)
    if flash_message:
        st.success(flash_message)

    all_history = HistoryManager.load_history(include_cache=True)

    # Filter tabs
    if all_history:
        col_clear, col_filter = st.columns([1, 3])
        with col_clear:
            if st.button(
                t("history_clear_cache_button"),
                key="history_clear_cache_button",
            ):
                show_clear_cache_confirm_dialog()

    if not all_history:
        st.info(t("history_empty"))
        return

    # Filter tabs for history / cache / all
    history_records = [r for r in all_history if r.get("record_type") != "cache"]
    cache_records = [r for r in all_history if r.get("record_type") == "cache"]

    _render_metric_row(
        [
            {
                "title": t("history_runs_title"),
                "content": f"{len(history_records):,}",
                "description": t("history_runs_desc"),
                "key": "history_runs_metric",
            },
            {
                "title": t("history_cache_title"),
                "content": f"{len(cache_records):,}",
                "description": t("history_cache_desc"),
                "key": "history_cache_metric",
            },
            {
                "title": t("history_total_title"),
                "content": f"{len(all_history):,}",
                "description": t("history_total_desc"),
                "key": "history_total_metric",
            },
        ]
    )

    tab_all, tab_history, tab_cache = st.tabs([
        f"{t('history_filter_all')} ({len(all_history)})",
        f"{t('history_filter_history')} ({len(history_records)})",
        f"{t('history_filter_cache')} ({len(cache_records)})",
    ])

    # Purpose: Render one human-readable history/cache card.
    def _render_history_card(entry: Dict[str, Any], history_index: int) -> None:
        record_type = str(entry.get("record_type", "history")).strip().lower()
        metadata = entry.get("metadata") or {}
        workflow_mode = metadata.get("workflow_mode", "")
        checkpoint = entry.get("checkpoint") if isinstance(entry.get("checkpoint"), dict) else None
        timestamp = entry.get("timestamp") or entry.get("created_at") or entry.get("cache_created_at")
        kind = str(entry.get("kind", "")).strip().lower() if record_type == "cache" else ""

        # Resolve process label: for history use workflow_mode, for cache use kind
        if record_type == "cache":
            kind_key = f"history_card_kind_{kind}" if kind else ""
            process_label = t(kind_key) if kind_key and _i18n_key_exists(kind_key) else t("history_card_kind_unknown")
        else:
            mode_key = f"history_card_workflow_{workflow_mode}" if workflow_mode else ""
            process_label = t(mode_key) if mode_key and _i18n_key_exists(mode_key) else t("history_card_workflow_unknown")

        with st.expander(build_history_entry_title(entry)):
            # --- Status + Process Type row ---
            stat_col, proc_col = st.columns(2)

            with stat_col:
                if record_type == "cache":
                    st.markdown(f"**{t('history_card_status')}**: {t('history_card_status_cached')}")
                elif entry.get("error"):
                    st.markdown(f"**{t('history_card_status')}**: {t('history_card_status_error')}")
                elif checkpoint:
                    st.markdown(f"**{t('history_card_status')}**: {t('history_card_status_success')}")
                else:
                    st.markdown(f"**{t('history_card_status')}**: {t('history_card_status_partial')}")

            with proc_col:
                type_label = t("history_card_record_type_cache") if record_type == "cache" else t("history_card_record_type_history")
                st.markdown(f"**{t('history_card_process_type')}**: {process_label}")
                st.caption(type_label)

            st.divider()

            # --- Processed Data section ---
            st.markdown(f"**{t('history_card_processed_data')}**:")

            # Timestamp
            if timestamp:
                try:
                    dt = datetime.fromisoformat(str(timestamp))
                    formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    formatted = str(timestamp)
                st.markdown(f"• {t('history_card_timestamp')}: `{formatted}`")

            # Cache-specific metadata (kind, provider, hits, request params)
            if record_type == "cache":
                cache_provider = entry.get("provider")
                hits = entry.get("cache_hit_count") or entry.get("hits")
                if cache_provider:
                    st.markdown(f"• {t('history_card_cache_provider')}: `{cache_provider}`")
                if hits is not None:
                    st.markdown(f"• {t('history_card_cache_hits')}: **{hits}**")

                # Request parameters summary
                request_obj = entry.get("request") or {}
                request_params = request_obj.get("normalized_params") or {}
                if request_params:
                    st.markdown(f"• {t('history_card_cache_request_summary')}:")
                    for param_key, param_val in request_params.items():
                        if isinstance(param_val, (list, tuple)):
                            val_preview = ", ".join(str(v) for v in param_val[:5])
                            if len(param_val) > 5:
                                val_preview += f" ... (+{len(param_val)-5})"
                            st.markdown(f"  — **{param_key}**: {val_preview}")
                        else:
                            st.markdown(f"  — **{param_key}**: `{param_val}`")

            # URLs processed
            urls = entry.get("urls") or entry.get("source_urls") or []
            if urls:
                url_count = entry.get("url_count", len(urls))
                st.markdown(f"• {t('history_card_cache_urls_count') if record_type == 'cache' else t('history_card_urls')}: **{url_count}**")
                for url in urls[:5]:
                    st.markdown(f"  — `{format_source_label(url)}`")
                if len(urls) > 5:
                    st.markdown(f"  — ... {t('history_card_keyword_preview_more').format(count=len(urls) - 5)}")

            # Keywords processed
            keywords = entry.get("keywords", [])
            kw_count = entry.get("keyword_count", len(keywords))
            if keywords:
                st.markdown(f"• {t('history_card_cache_keywords_count') if record_type == 'cache' else t('history_card_keywords')}: **{kw_count}**")
                preview = ", ".join(keywords[:8])
                remaining = kw_count - min(8, len(keywords))
                if remaining > 0:
                    preview += f" ... {t('history_card_keyword_preview_more').format(count=remaining)}"
                st.markdown(f"  {preview}")

            # Error info if present
            error_msg = entry.get("error")
            if error_msg:
                st.error(f"```\n{error_msg}\n```")

            st.divider()

            # --- Action buttons ---
            action_col1, action_col2 = st.columns(2)

            # Restore from cache: supported for serp, ads, crawl, math, trends, llm_extract
            cache_restorable_kinds = {"serp", "ads", "crawl", "math", "trends", "llm_extract"}

            with action_col1:
                if record_type == "cache" and kind in cache_restorable_kinds:
                    if st.button(
                        t("history_restore_cache"),
                        key=_build_history_action_key("cache-restore", entry, history_index),
                    ):
                        restored = _restore_cache_to_session(entry)
                        if restored:
                            st.session_state.history_flash_message = t("history_restore_cache_success")
                            st.rerun()
                        else:
                            st.warning(t("history_restore_cache_unsupported"))
                elif record_type != "cache" and checkpoint and st.button(
                    t("history_restore_checkpoint"),
                    key=_build_history_action_key("history-restore", entry, history_index),
                ):
                    restore_history_checkpoint(entry)
                    st.session_state.history_flash_message = t(
                        "history_restore_success"
                    )
                    st.rerun()

            with action_col2:
                can_regenerate = bool(
                    checkpoint
                    and checkpoint.get("workflow_mode") == "url_llm"
                    and checkpoint.get("scraped_content")
                )
                if record_type != "cache" and can_regenerate and st.button(
                    t("history_regenerate_keywords"),
                    key=_build_history_action_key("history-regenerate", entry, history_index),
                ):
                    restore_history_checkpoint(entry)
                    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
                    st.session_state.current_run_id = run_id
                    run_llm_keyword_stage_from_checkpoint(
                        scraped_content=st.session_state.scraped_content,
                        provider=provider,
                        model=model_name,
                        max_keywords=max_keywords,
                        location_id=location_id,
                        language_id=language_id,
                        currency_code=currency_code,
                        keyword_prompt=keyword_prompt,
                        api_timeout=api_timeout,
                        api_delay=api_delay,
                        api_retry_count=api_retry_count,
                        api_retry_delay=api_retry_delay,
                        run_id=run_id,
                    )
                    st.rerun()

    with tab_all:
        _render_paginated_history(all_history, "all", 0, card_renderer=_render_history_card)

    with tab_history:
        _render_paginated_history(history_records, "history", 1000, card_renderer=_render_history_card)

    with tab_cache:
        _render_paginated_history(cache_records, "cache", 2000, card_renderer=_render_history_card)
# FUNCTION_CONTRACT: _save_to_history
# Purpose: Implement the  save to history helper for this module.
# Input: df (pd.DataFrame)
# Output: None
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def _save_to_history(df: pd.DataFrame) -> None:
    try:
        if "Source URL" not in df.columns:
            return
        urls: List[str] = df["Source URL"].unique().tolist()
        keywords: List[str] = df["Keyword"].tolist()
        signature = _build_history_signature(
            st.session_state.get("current_run_id", ""),
            urls,
            keywords,
        )
        if st.session_state.get("last_history_signature") == signature:
            return
        workflow_mode = st.session_state.get("workflow_mode", "url_llm")
        HistoryManager.save_entry(
            urls=urls,
            keywords=keywords,
            keyword_count=len(keywords),
            url_count=len(urls),
            metadata=build_history_metadata(workflow_mode),
            checkpoint=_build_history_checkpoint(df, workflow_mode),
        )
        st.session_state.last_history_signature = signature
    except Exception as e:
        logger.warning(f"Failed to save history: {e}")


# FUNCTION_CONTRACT: render_serp_results
# Purpose: Display SERP organic results in a DataFrame with Excel/CSV download buttons and auto-save
# Input: auto_save_excel (bool)
# Output: None
# Side Effects: renders Streamlit UI elements; writes auto-saved Excel file; modifies st.session_state.serp_results_saved
# Business Rules: guards on workflow_mode == "serp_analysis" to prevent rendering stale Ads data; follows existing render_keyword_results column/download pattern
# Failure Modes: never raises; returns early when no data or wrong workflow mode
# LINKS: requirements.xml#UC-006, knowledge-graph.xml#MOD-007
def render_serp_results(auto_save_excel: bool) -> None:
    if st.session_state.processed_data is None:
        return

    # Guard against rendering Ads data in SERP mode or vice versa
    if st.session_state.get("workflow_mode") != "serp_analysis":
        return

    df: pd.DataFrame = st.session_state.processed_data
    _render_section_header(t("serp_results_header"), t("serp_results_desc"), "blue")

    # URL match highlighting for source-aware workflows
    display_df = df.copy()
    match_targets = st.session_state.get("serp_match_targets")
    style_rules = None

    if match_targets and "URL" in display_df.columns:
        from utils.url_matcher import classify_url_match
        source_urls = [t["original"] for t in match_targets]

        # Add match metadata columns
        match_types = []
        matched_sources = []
        matched_domains = []
        for _, row in display_df.iterrows():
            result_url = str(row.get("URL", ""))
            match_info = classify_url_match(result_url, source_urls)
            match_types.append(match_info["match_type"])
            matched_sources.append(match_info.get("matched_target", ""))
            matched_domains.append(match_info.get("matched_domain", ""))

        display_df["URL Match Type"] = match_types
        display_df["Matched Source URL"] = matched_sources
        display_df["Matched Source Domain"] = matched_domains

        # FUNCTION_CONTRACT: _style_url_column - style URL column based on match type
        def _style_url_column(s):
            styles = []
            for i, val in enumerate(s):
                if i < len(match_types):
                    mt = match_types[i]
                    if mt == "full_url":
                        styles.append("font-weight: bold; text-decoration: underline")
                    elif mt == "domain":
                        styles.append("font-weight: bold")
                    else:
                        styles.append("")
                else:
                    styles.append("")
            return styles

        # Build Styler for URL highlighting (WR-01: removed dead _highlight_url function)
        has_matches = any(m != "none" for m in match_types)
        if has_matches:
            # Use pandas Styler for UI highlighting
            display_df_styled = display_df.style.apply(
                _style_url_column, subset=["URL"]
            )

            # Show legend when matches exist
            st.caption(t("serp_results_legend"))

            st.dataframe(display_df_styled, use_container_width=True)

            # Build style rules for Excel export
            style_rules = {
                "URL": {
                    "condition": lambda row: row.get("URL Match Type") == "full_url",
                    "font": {"bold": True, "underline": True},
                },
            }
            # Also add domain-only bold rule
            domain_rule = {
                "target_column": "URL",
                "condition": lambda row: (
                    row.get("URL Match Type") == "domain"
                ),
                "font": {"bold": True},
            }
            style_rules["URL_domain"] = domain_rule
        else:
            st.dataframe(display_df, use_container_width=True)
    else:
        st.dataframe(display_df, use_container_width=True)

    match_count = sum(
        1
        for value in display_df.get("URL Match Type", [])
        if value and value != "none"
    )
    _render_metric_row(
        [
            {
                "title": t("serp_results_rows_title"),
                "content": f"{len(df):,}",
                "description": t("serp_results_rows_desc"),
                "key": "serp_results_rows_metric",
            },
            {
                "title": t("serp_results_keywords_title"),
                "content": f"{df['Keyword'].nunique():,}",
                "description": t("serp_results_keywords_desc"),
                "key": "serp_results_keywords_metric",
            },
            {
                "title": t("serp_results_matches_title"),
                "content": f"{match_count:,}",
                "description": t("serp_results_matches_desc"),
                "key": "serp_results_matches_metric",
            },
        ]
    )

    # Export buttons below table (one row: Excel left, CSV right)
    with st.container():
        if auto_save_excel and not st.session_state.get("serp_results_saved", False):
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            filename = f"serp_results_export_{timestamp}.xlsx"
            output_path = _BASE_DIR / "outputs" / filename
            output_path.parent.mkdir(exist_ok=True)

            if ExcelExporter.export(display_df, str(output_path), style_rules=style_rules):
                st.session_state.serp_results_saved = True
                logger.info(f"SERP results auto-saved: {output_path}")
            else:
                st.error(t("autosave_error"))

        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            try:
                buffer = io.BytesIO()
                ExcelExporter.export_to_buffer(display_df, buffer, style_rules=style_rules)
                st.download_button(
                    label=t("download_excel"),
                    data=buffer.getvalue(),
                    file_name=f"serp_results_export_{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            except Exception as e:
                st.error(f"{t('export_error')}: {e}")
        with btn_col2:
            try:
                csv_data = ExcelExporter.export_csv_to_bytes(display_df)
                st.download_button(
                    label=t("download_csv"),
                    data=csv_data,
                    file_name=f"serp_results_export_{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv",
                    mime="text/csv",
                    key="download_serp_results_csv",
                )
            except Exception as e:
                st.error(f"{t('csv_error')}: {e}")

    st.caption(
        t(
            "serp_total_stat",
            count=len(df),
            keywords=df["Keyword"].nunique(),
        )
    )


# FUNCTION_CONTRACT: render_serp_related_searches
# Purpose: Display Related Searches and People Also Ask in expandable sections with export buttons and chaining checkboxes
# Input: (none)
# Output: None
# Side Effects: renders Streamlit UI elements; reads st.session_state.serp_related_data; renders export download buttons; renders checkboxes for query selection in session state
# Business Rules: returns early if no related data; splits data by Type for separate display; groups by keyword in expandable sections; checkbox state keys use serp_chain_select:: prefix
# Failure Modes: never raises; returns early when no data
# LINKS: requirements.xml#UC-006, knowledge-graph.xml#MOD-007
def render_serp_related_searches() -> None:
    related_data = st.session_state.get("serp_related_data")
    if not related_data:
        return

    df = pd.DataFrame(related_data, columns=SERP_RELATED_COLUMNS)
    if df.empty:
        return

    _render_section_header(t("serp_related_header"), t("serp_related_desc"), "green")

    # FUNCTION_CONTRACT: _on_select_all_related - callback for select all checkbox
    def _on_select_all_related() -> None:
        new_val = st.session_state[select_all_key]
        for _, row in df.iterrows():
            st.session_state[
                f"serp_chain_select::{row['Keyword']}::{row['Related Query']}"
            ] = new_val

    # Select All checkbox for all related queries
    select_all_key = "serp_chain_select_all"
    if select_all_key not in st.session_state:
        st.session_state[select_all_key] = True

    st.checkbox(
        t("select_all"),
        key=select_all_key,
        on_change=_on_select_all_related,
    )

    related_searches = df[df["Type"] == "related_search"]
    people_also_ask = df[df["Type"] == "people_also_ask"]

    if not related_searches.empty:
        for keyword in related_searches["Keyword"].unique():
            keyword_related = related_searches[related_searches["Keyword"] == keyword]
            with st.expander(
                f"{t('serp_related_header')} — {keyword} ({len(keyword_related)})",
                key=f"serp_related_expander::{keyword}",
            ):
                for _, row in keyword_related.iterrows():
                    query = row["Related Query"]
                    st.checkbox(
                        query,
                        value=True,
                        key=f"serp_chain_select::{keyword}::{query}",
                    )
                st.dataframe(
                    keyword_related[["Related Query"]].reset_index(drop=True),
                    width="stretch",
                )

    if not people_also_ask.empty:
        for keyword in people_also_ask["Keyword"].unique():
            keyword_paa = people_also_ask[people_also_ask["Keyword"] == keyword]
            with st.expander(
                f"{t('serp_paa_header')} — {keyword} ({len(keyword_paa)})",
                key=f"serp_paa_expander::{keyword}",
            ):
                for _, row in keyword_paa.iterrows():
                    query = row["Related Query"]
                    st.checkbox(
                        query,
                        value=True,
                        key=f"serp_chain_select::{keyword}::{query}",
                    )
                st.dataframe(
                    keyword_paa[["Related Query"]].reset_index(drop=True),
                    width="stretch",
                )

    # Export buttons below the expanders
    exp_col1, exp_col2 = st.columns(2)
    with exp_col1:
        try:
            buffer = io.BytesIO()
            ExcelExporter.export_to_buffer(df, buffer)
            st.download_button(
                label=t("serp_export_related"),
                data=buffer.getvalue(),
                file_name=f"serp_related_export_{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_serp_related_xlsx",
            )
        except Exception as e:
            st.error(f"{t('export_error')}: {e}")
    with exp_col2:
        try:
            csv_data = ExcelExporter.export_csv_to_bytes(df)
            st.download_button(
                label=t("serp_export_related_csv"),
                data=csv_data,
                file_name=f"serp_related_export_{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv",
                mime="text/csv",
                key="download_serp_related_csv",
            )
        except Exception as e:
            st.error(f"{t('csv_error')}: {e}")


# FUNCTION_CONTRACT: render_serp_chain_to_ads
# Purpose: Display "Chain to Ads" and "Chain to Trends" buttons that collect selected queries from checkboxes and trigger analysis
# Input: location_id (str), language_id (str), currency_code (str), auto_save_excel (bool), trends_config (Optional[dict])
# Output: None
# Side Effects: renders Streamlit UI; reads checkbox session state; triggers pipeline via button click; calls st.rerun()
# Business Rules: guards on workflow_mode == "serp_analysis" and serp_related_data existence; deduplicates selected queries
# Failure Modes: never raises; returns early when wrong mode or no data
# LINKS: requirements.xml#UC-006, knowledge-graph.xml#MOD-007, PLAN 10-02 Task 9
def render_serp_chain_to_ads(
    location_id: str,
    language_id: str,
    currency_code: str,
    auto_save_excel: bool,
    force_refresh: bool = False,
    trends_config: Optional[dict] = None,
) -> None:
    if st.session_state.get("workflow_mode") != "serp_analysis":
        return

    related_data = st.session_state.get("serp_related_data")
    if not related_data:
        return

    _render_section_header(t("serp_chain_header"), t("serp_chain_desc"), "blue")

    total_queries = len(related_data)
    selected_queries: List[str] = []
    malformed_keys = []
    for key, value in st.session_state.items():
        if key.startswith("serp_chain_select::") and value:
            parts = key.split("::", 2)
            if len(parts) == 3:
                selected_queries.append(parts[2])
            else:
                malformed_keys.append(key)

    if malformed_keys and selected_queries:
        logger.warning(f"Malformed SERP chain keys detected: {malformed_keys[:3]}")

    selected_queries = list(dict.fromkeys(selected_queries))
    st.info(
        t("serp_chain_selected_stat", selected=len(selected_queries), total=total_queries)
        if total_queries
        else f"Selected: {len(selected_queries)} queries"
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button(t("serp_chain_button"), type="primary", key="serp_chain_ads_btn"):
            if not selected_queries:
                st.warning(t("serp_chain_no_queries"))
                return
            run_serp_chain_to_ads_workflow(
                selected_queries=selected_queries,
                location_id=location_id,
                language_id=language_id,
                currency_code=currency_code,
                force_refresh=force_refresh,
            )
            st.rerun()

    with col2:
        # Phase 10 Task 9: Trends stage button for SERP related/PAA candidates
        if st.button(t("send_related_to_trends"), key="serp_chain_trends_btn"):
            if not selected_queries:
                st.warning(t("serp_chain_no_queries"))
                return
            from utils.pipeline import run_trends_stage_from_keywords
            run_id = str(st.session_state.get("current_run_id", ""))
            result = run_trends_stage_from_keywords(
                keywords=selected_queries,
                trends_config=trends_config,
                run_id=run_id,
                force_refresh=force_refresh,
            )
            if result is not None:
                st.success(t("google_trends_complete"))
                st.rerun()


# FUNCTION_CONTRACT: render_serp_chained_ads_results
# Purpose: Display chained Ads analysis results for SERP-related queries with Excel/CSV download
# Input: auto_save_excel (bool)
# Output: None
# Side Effects: renders Streamlit UI; writes auto-saved file; modifies st.session_state.serp_chain_ads_saved
# Business Rules: guards on workflow_mode == "serp_analysis"; follows render_keyword_results export pattern
# Failure Modes: never raises; returns early when no data or wrong mode
# LINKS: requirements.xml#UC-006, knowledge-graph.xml#MOD-007
def render_serp_chained_ads_results(auto_save_excel: bool) -> None:
    if st.session_state.get("workflow_mode") != "serp_analysis":
        return

    df = st.session_state.get("serp_chained_ads_data")
    if df is None:
        return

    _render_section_header(t("serp_chain_results_header"), t("serp_chain_results_desc"), "blue")

    _render_table_preview_with_exports(
        df=df,
        display_df=df,
        auto_save_excel=auto_save_excel,
        save_key="serp_chain_ads_saved",
        excel_filename_prefix="serp_chained_ads_export",
        csv_download_key="download_serp_chain_csv",
    )

    st.info(
        t(
            "total_keywords_stat",
            count=len(df),
            sources=df["Source URL"].nunique() if "Source URL" in df.columns else 0,
        )
    )


# block_results_keyword_handoff_select: Reusable keyword candidate checkbox selection for staged handoffs
# Semantic block: Generic checkbox selector for keyword candidates with stable session state


# FUNCTION_CONTRACT: render_keyword_candidate_selector
# Purpose: Render reusable checkbox selector for keyword candidates with group-by-source
# Input: candidates_key (str), selection_prefix (str), title (str)
# Output: Optional[Dict[str, List[str]]] — mapping of source to selected keywords
# Side Effects: Reads st.session_state for candidates; renders checkboxes; stores selections
# Business Rules: Groups by source_url; provides select-all per group; uses stable state keys
# Failure Modes: Returns None if no candidates
# LINKS: PLAN 08-01 Task 5
def render_keyword_candidate_selector(
    candidates_key: str,
    selection_prefix: str,
    title: str,
) -> Optional[Dict[str, List[str]]]:
    candidates: Optional[List[Dict[str, object]]] = st.session_state.get(candidates_key)
    if not candidates:
        return None
    selected_by_source = _render_grouped_keyword_candidate_selector(
        candidates=candidates,
        selection_prefix=selection_prefix,
        title=title,
        source_for_candidate=lambda candidate: candidate.get("source_url", "unknown"),
        expander_key_for_source=lambda source: f"{selection_prefix}_expander::{source}",
        checkbox_key_for_candidate=lambda candidate: f"{selection_prefix}::{candidate['keyword']}",
        selected_value_for_candidate=lambda candidate: candidate["keyword"],
    )
    return selected_by_source if selected_by_source else None


# block_results_source_aware_selectors: Source-aware checkbox selectors with tuple-keyed widgets
# Semantic block: Checkbox rendering that includes source URL in key hash to prevent duplicate keyword collisions


# FUNCTION_CONTRACT: render_keyword_candidate_selector_with_sources
# Purpose: Render checkbox selector for keyword candidates with source context
# Input: candidates (List[Dict]), selection_prefix (str), title (str)
# Output: Optional[List[Tuple[str, str]]] - selected (keyword, source_url) tuples
# Side Effects: Renders checkboxes; stores selections with tuple-keyed state keys
# Business Rules: Groups by source_url; tuple-keyed widgets prevent collisions
# Failure Modes: Returns None if no candidates
# LINKS: PLAN 09-04 Task 5
def render_keyword_candidate_selector_with_sources(
    candidates: List[Dict[str, object]],
    selection_prefix: str,
    title: str,
) -> Optional[List[tuple]]:
    """
    Render checkbox selector for keyword candidates with source context.

    Checkbox keys include both keyword and source_url hash to prevent
    collisions when the same keyword appears from multiple source URLs.

    Also exposes a manual-keyword input so the user can add their own keywords
    to the LLM-gathered set before sending to Ads / SEO generation. Manually
    added keywords persist in the staged candidates session state and appear as
    selectable candidates on rerun.

    Returns:
        List of (keyword, source_url) tuples for selected items
    """
    from utils.pipeline import (
        SESSION_KEY_STAGED_KEYWORDS,
        make_selection_key,
    )

    # ---- Merge any persisted manual candidates into the working list ----
    # Manual keywords live in SESSION_KEY_STAGED_KEYWORDS so they survive reruns.
    persisted: List[Dict[str, object]] = []
    staged_candidates = st.session_state.get(SESSION_KEY_STAGED_KEYWORDS) or []
    for cand in staged_candidates:
        if isinstance(cand, dict) and cand.get("source_type") == "manual_keyword":
            persisted.append(cand)
    # Working candidate set = LLM/extraction candidates + persisted manual keywords
    # (dedup by (keyword, source_url) so a re-extraction doesn't double-list them).
    working_candidates: List[Dict[str, object]] = list(candidates) + list(persisted)
    seen: set = set()
    deduped: List[Dict[str, object]] = []
    for cand in working_candidates:
        cand_key = (str(cand.get("keyword", "")), str(cand.get("source_url", "")))
        if cand_key in seen:
            continue
        seen.add(cand_key)
        deduped.append(cand)

    if not deduped:
        return None

    _render_section_header(title, t("candidate_selector_desc"), "blue")

    def _on_add_manual_keyword() -> None:
        """Button on_click callback. Streamlit forbids assigning to a widget's
        session-state key after the widget is instantiated in the same script run,
        so all widget-key writes (auto-select checkbox, clear the textarea) must
        live here вЂ” on_click fires at the start of the next run, before any widget
        is re-instantiated, which is the only safe place to mutate widget state.

        The textarea holds one or several keywords, one per line. Each non-empty
        line becomes its own candidate."""
        typed = str(st.session_state.get(manual_input_key, "") or "")
        if not typed.strip():
            return
        picked_url = str(st.session_state.get(manual_url_key, "") or "")
        if not picked_url:
            picked_url = unique_urls[0] if unique_urls else ""
        if not picked_url:
            return
        # One keyword per non-empty line. Blank / whitespace-only lines are ignored.
        raw_keywords: List[str] = [
            line.strip() for line in typed.splitlines() if line.strip()
        ]
        if not raw_keywords:
            return
        current_staged: List[Dict[str, object]] = (
            list(st.session_state.get(SESSION_KEY_STAGED_KEYWORDS) or [])
        )
        for cleaned_keyword in raw_keywords:
            # Persist as a manual-keyword candidate so it survives reruns and shows
            # in the candidate list with its own checkbox.
            already_present = any(
                str(c.get("keyword", "")) == cleaned_keyword
                and str(c.get("source_url", "")) == picked_url
                for c in current_staged
            )
            if not already_present:
                current_staged.append(
                    {
                        "keyword": cleaned_keyword,
                        "source_url": picked_url,
                        "source_stage": picked_url,
                        "source_type": "manual_keyword",
                        "selection_prefix": selection_prefix,
                    }
                )
            st.session_state[
                make_selection_key(cleaned_keyword, picked_url, selection_prefix)
            ] = True
        st.session_state[SESSION_KEY_STAGED_KEYWORDS] = current_staged
        # Clear the textarea so the user can add another batch without re-submitting
        # the old text on the next rerun.
        st.session_state[manual_input_key] = ""

    # ---- Manual keyword addition (restored capability) ----
    # Lets the user add their own keywords to the LLM-gathered set before SEO generation.
    unique_urls: List[str] = sorted(
        {str(c.get("source_url", "")) for c in deduped if str(c.get("source_url", ""))}
    )
    manual_input_key = f"manual_keyword_input_{selection_prefix}"
    manual_url_key = f"manual_kw_url_{selection_prefix}"
    add_button_key = f"add_manual_kw_{selection_prefix}"

    new_keyword: str = st.text_area(
        t("add_keyword_manual"),
        key=manual_input_key,
        height=120,
    )


    if new_keyword and new_keyword.strip() and unique_urls:
        st.selectbox(t("for_which_url"), unique_urls, key=manual_url_key)
        st.button(
            t("add_button"), key=add_button_key, on_click=_on_add_manual_keyword
        )

    # Re-merge persisted manual candidates after a potential add, so this render
    # reflects the new keyword immediately.
    final_candidates = deduped
    staged_after = st.session_state.get(SESSION_KEY_STAGED_KEYWORDS) or []
    for cand in staged_after:
        if isinstance(cand, dict) and cand.get("source_type") == "manual_keyword":
            c_key = (str(cand.get("keyword", "")), str(cand.get("source_url", "")))
            if c_key not in seen:
                final_candidates.append(cand)
                seen.add(c_key)

    candidates = final_candidates

    selected_by_source = _render_grouped_keyword_candidate_selector(
        candidates=candidates,
        selection_prefix=selection_prefix,
        title=title,
        source_for_candidate=lambda candidate: str(candidate.get("source_url", "unknown") or "unknown"),
        expander_key_for_source=lambda source: f"{selection_prefix}_src_expander::{source}",
        checkbox_key_for_candidate=lambda candidate: make_selection_key(
            str(candidate.get("keyword", "")),
            str(candidate.get("source_url", "")),
            selection_prefix,
        ),
        selected_value_for_candidate=lambda candidate: (
            str(candidate.get("keyword", "")),
            str(candidate.get("source_url", "")),
        ),
        render_header=False,
    )

    selected_tuples: List[tuple] = []
    for values in selected_by_source.values():
        selected_tuples.extend(tuple(value) for value in values)
    return selected_tuples if selected_tuples else None


# FUNCTION_CONTRACT: _store_ads_keyword_candidates
# Purpose: Persist Ads keyword ideas as selectable candidates for post-Ads SERP handoff
# Input: df (pd.DataFrame), selection_prefix (str)
# Output: None
# Side Effects: Writes keyword candidates into st.session_state
# Business Rules: Uses stable selection keys and preserves source URL grouping
# Failure Modes: Returns silently when the DataFrame is empty or missing keyword data
# LINKS: PLAN 08-01 Task 5
def _store_ads_keyword_candidates(df: pd.DataFrame, selection_prefix: str) -> None:
    candidates_key = f"kw_candidates_{selection_prefix}"
    candidates: List[Dict[str, object]] = []

    if df is None or df.empty or "Keyword" not in df.columns:
        st.session_state[candidates_key] = candidates
        return

    for _, row in df.iterrows():
        keyword = str(row.get("Keyword", "") or "").strip()
        if not keyword:
            continue
        source_url = str(row.get("Source URL", KEYWORD_SEED_SOURCE_URL) or KEYWORD_SEED_SOURCE_URL)
        candidates.append(
            {
                "keyword": keyword,
                "source_url": source_url,
                "source_stage": source_url,
                "source_type": "ads_keyword_ideas",
                "selection_prefix": selection_prefix,
            }
        )

    st.session_state[candidates_key] = candidates


# FUNCTION_CONTRACT: _is_ads_keyword_results_df
# Purpose: Detect Ads keyword result tables that can be handed to SERP after Ads completes
# Input: df (pd.DataFrame)
# Output: bool
# Side Effects: None
# Business Rules: Requires keyword column and Ads metric columns; excludes SERP organic result tables
# Failure Modes: Returns False for empty or malformed data
# LINKS: PLAN 08-01 Task 5
def _is_ads_keyword_results_df(df: pd.DataFrame) -> bool:
    if df is None or df.empty:
        return False
    if "Keyword" not in df.columns or "Position" in df.columns:
        return False
    ads_columns = {
        "Avg Monthly Searches",
        "Competition",
        "Competition Index",
        "Low Top of Page Bid",
        "High Top of Page Bid",
    }
    return bool(ads_columns & set(df.columns))


# FUNCTION_CONTRACT: _get_selected_ads_keyword_candidates
# Purpose: Collect selected keyword ideas for a post-Ads SERP handoff
# Input: selection_prefix (str)
# Output: List[str]
# Side Effects: Reads st.session_state checkbox values
# Business Rules: Returns selected keyword strings only, never URLs
# Failure Modes: Returns an empty list if no candidates or no selections exist
# LINKS: PLAN 08-01 Task 5
def _get_selected_ads_keyword_candidates(selection_prefix: str) -> List[str]:
    candidates_key = f"kw_candidates_{selection_prefix}"
    candidates: Optional[List[Dict[str, object]]] = st.session_state.get(candidates_key)
    if not candidates:
        return []

    selected_keywords: List[str] = []
    for candidate in candidates:
        keyword = str(candidate.get("keyword", "") or "").strip()
        if not keyword:
            continue
        checkbox_key = f"{selection_prefix}::{keyword}"
        if st.session_state.get(checkbox_key, False):
            selected_keywords.append(keyword)
    return selected_keywords


# FUNCTION_CONTRACT: _run_serp_after_ads_keywords
# Purpose: Send selected Ads keyword ideas to SERP analysis
# Input: df (pd.DataFrame), selection_prefix (str), run_id (str = ''), serp_config (Optional[dict] = None)
# Output: Optional[pd.DataFrame]
# Side Effects: Calls run_serp_analysis_workflow with selected keyword strings
# Business Rules: Keyword strings are selected from Ads results and passed to SERP only after filtering
# Failure Modes: Returns None when no keywords are selected
# LINKS: PLAN 08-01 Task 5
def _run_serp_after_ads_keywords(
    df: pd.DataFrame,
    selection_prefix: str,
    run_id: str = "",
    serp_config: Optional[dict] = None,
    force_refresh: bool = False,
) -> Optional[pd.DataFrame]:
    _store_ads_keyword_candidates(df, selection_prefix)
    selected_keywords = _get_selected_ads_keyword_candidates(selection_prefix)
    if not selected_keywords:
        st.warning(t("serp_chain_no_queries"))
        return None

    return _run_chained_serp_keywords(
        selected_keywords,
        run_id=run_id,
        serp_config=serp_config,
        restore_processed_data=df,
        force_refresh=force_refresh,
    )


# FUNCTION_CONTRACT: _run_chained_serp_keywords
# Purpose: Run SERP for selected keywords from a non-SERP workflow without replacing the active Ads table
# Input: selected_keywords (List[str]), run_id (str = ''), serp_config (Optional[dict] = None), restore_processed_data (Optional[pd.DataFrame] = None)
# Output: Optional[pd.DataFrame]
# Side Effects: Stores chained SERP results and related data in st.session_state; restores processed_data
# Business Rules: Non-SERP workflows keep Ads/keyword results visible while showing SERP results in a separate section
# Failure Modes: Returns None when no keywords are selected or SERP workflow returns no data
# LINKS: PLAN 08-01 Task 5
def _run_chained_serp_keywords(
    selected_keywords: List[str],
    run_id: str = "",
    serp_config: Optional[dict] = None,
    restore_processed_data: Optional[pd.DataFrame] = None,
    force_refresh: bool = False,
) -> Optional[pd.DataFrame]:
    if not selected_keywords:
        st.warning(t("serp_chain_no_queries"))
        return None

    previous_processed = st.session_state.get("processed_data")
    previous_related = st.session_state.get("serp_related_data")
    result = run_serp_analysis_workflow(
        selected_keywords,
        run_id=run_id,
        serp_config=serp_config,
        force_refresh=force_refresh,
    )
    if result is not None:
        st.session_state["chained_serp_results"] = result
        st.session_state["chained_serp_related_data"] = st.session_state.get(
            "serp_related_data"
        )

    if restore_processed_data is not None:
        st.session_state["processed_data"] = restore_processed_data
    elif previous_processed is not None:
        st.session_state["processed_data"] = previous_processed
    else:
        st.session_state.pop("processed_data", None)

    if previous_related is not None:
        st.session_state["serp_related_data"] = previous_related
    else:
        st.session_state.pop("serp_related_data", None)

    # SERP-Ads merge: if processed_data exists after restore, build merged view
    if st.session_state.get("processed_data") is not None:
        build_and_store_merged_ads_serp()

    return result


# FUNCTION_CONTRACT: render_ads_keyword_serp_handoff
# Purpose: Render post-Ads keyword candidates and buttons to send selected keywords to SERP or Trends
# Input: df (pd.DataFrame), selection_prefix (str), title (str), run_id (str = ''), serp_config (Optional[dict] = None), trends_config (Optional[dict] = None)
# Output: None
# Side Effects: Renders Streamlit widgets and may trigger SERP or Trends workflow
# Business Rules: Reuses Ads result keywords as selectable SERP/Trends inputs; never forwards bare URLs
# Failure Modes: Returns early when the DataFrame is empty or no candidates exist
# LINKS: PLAN 08-01 Task 5, PLAN 10-02 Task 9
def render_ads_keyword_serp_handoff(
    df: pd.DataFrame,
    selection_prefix: str,
    title: str,
    run_id: str = "",
    serp_config: Optional[dict] = None,
    force_refresh: bool = False,
    trends_config: Optional[dict] = None,
) -> None:
    if df is None or df.empty:
        return
    if "Keyword" not in df.columns:
        return

    _store_ads_keyword_candidates(df, selection_prefix)
    candidates = st.session_state.get(f"kw_candidates_{selection_prefix}", [])
    selected_tuples = render_keyword_candidate_selector_with_sources(
        candidates,
        selection_prefix,
        title,
    )
    if not selected_tuples:
        return

    col1, col2 = st.columns(2)
    with col1:
        if st.button(t("send_selected_to_serp"), key=f"{selection_prefix}_send_to_serp"):
            result = run_serp_workflow_with_source_context(
                selected_tuples,
                run_id=run_id,
                serp_config=serp_config,
                force_refresh=force_refresh,
            )
            if result is not None:
                # Build the bidirectional SERP↔Ads merge now that both datasets exist:
                # run_serp_workflow_with_source_context stored chained_serp_results and
                # restored processed_data (Ads). No-op if either is missing.
                build_and_store_merged_ads_serp()
                st.success(t("serp_analysis_complete"))
                st.rerun()

    with col2:
        # Phase 10 Task 9: Trends stage button for Ads keyword candidates
        if st.button(t("send_selected_to_trends"), key=f"{selection_prefix}_send_to_trends"):
            from utils.pipeline import run_trends_stage_from_selection
            result = run_trends_stage_from_selection(
                selected_contexts=selected_tuples,
                trends_config=trends_config,
                run_id=run_id,
                force_refresh=force_refresh,
            )
            if result is not None:
                # Build the merged Ads+Trends view now that both datasets exist
                # (run_trends_stage_from_selection stored google_trends_tables; processed_data survives).
                build_and_store_merged_ads_trends()
                st.success(t("google_trends_complete"))
                st.rerun()


# FUNCTION_CONTRACT: render_chained_serp_results
# Purpose: Render SERP results produced from Ads/keyword handoff without changing workflow mode
# Input: None
# Output: None
# Side Effects: Renders Streamlit dataframe sections from st.session_state
# Business Rules: Used by URL/keyword workflows after SERP is run from selected keyword candidates
# Failure Modes: Returns silently when no chained SERP data exists
# LINKS: PLAN 08-01 Task 5
def render_chained_serp_results() -> None:
    serp_df = st.session_state.get("chained_serp_results")
    if serp_df is None or getattr(serp_df, "empty", True):
        return

    _render_section_header(t("serp_results_after_ads_header"), t("serp_results_after_ads_desc"), "blue")
    _render_table_preview_with_exports(
        df=serp_df,
        display_df=serp_df,
        auto_save_excel=False,
        save_key="chained_serp_results_saved",
        excel_filename_prefix="chained_serp_results_export",
        csv_download_key="download_chained_serp_csv",
    )

    related_data = st.session_state.get("chained_serp_related_data") or []
    if related_data:
        with st.expander(t("serp_related_header")):
            st.dataframe(pd.DataFrame(related_data), width="stretch")


# FUNCTION_CONTRACT: build_and_store_merged_ads_serp
# Purpose: Build merged Ads+SERP DataFrame by calling aggregate_serp_per_keyword and store in session state
# Input: None (reads st.session_state["processed_data"] and st.session_state["chained_serp_results"])
# Output: Optional[pd.DataFrame] — merged DataFrame or None if either input is missing
# Side Effects: Stores/clears st.session_state["merged_ads_serp_data"]
# Business Rules: Guards against None/empty inputs; stores None if inputs unavailable
# Failure Modes: Returns None silently if inputs missing; never raises
# LINKS: PLAN 16 Task 1 — SERP-Ads merge
def build_and_store_merged_ads_serp() -> Optional[pd.DataFrame]:
    ads_df = getattr(st.session_state, "processed_data", None)
    serp_df = getattr(st.session_state, "chained_serp_results", None)
    if ads_df is None or getattr(ads_df, "empty", True) or serp_df is None or getattr(serp_df, "empty", True):
        setattr(st.session_state, "merged_ads_serp_data", None)
        return None
    merged = aggregate_serp_per_keyword(serp_df, ads_df)
    setattr(st.session_state, "merged_ads_serp_data", merged)
    return merged


# FUNCTION_CONTRACT: render_merged_ads_serp_results
# Purpose: Render the merged Ads+SERP results table in the UI
# Input: None (reads st.session_state["merged_ads_serp_data"])
# Output: None
# Side Effects: Renders Streamlit section header and data table with export buttons
# Business Rules: No-ops when merged data is None or empty
# Failure Modes: Returns silently when no data; never raises
# LINKS: PLAN 16 Task 1 — SERP-Ads merge
def render_merged_ads_serp_results() -> None:
    df = st.session_state.get("merged_ads_serp_data")
    if df is None or getattr(df, "empty", True):
        return
    _render_section_header(t("merged_ads_serp_header"), t("merged_ads_serp_desc"), "blue")
    _render_table_preview_with_exports(
        df=df, display_df=df, auto_save_excel=False,
        save_key="merged_ads_serp_saved",
        excel_filename_prefix="merged_ads_serp_export",
        csv_download_key="download_merged_ads_serp_csv",
    )


# FUNCTION_CONTRACT: build_and_store_merged_ads_trends
# Purpose: Build merged Ads+Trends DataFrame by calling aggregate_trends_per_keyword and store in session state
# Input: None (reads st.session_state["processed_data"] and st.session_state["google_trends_tables"]["averages"])
# Output: Optional[pd.DataFrame] — merged DataFrame or None if either input is missing
# Side Effects: Stores/clears st.session_state["merged_ads_trends_data"]
# Business Rules: Guards against None/empty inputs; treats missing or empty "averages" table as absent; stores None if inputs unavailable
# Failure Modes: Returns None silently if inputs missing; never raises
# LINKS: PLAN 16 Task 1 — Trends-Ads merge (mirrors build_and_store_merged_ads_serp)
def build_and_store_merged_ads_trends() -> Optional[pd.DataFrame]:
    ads_df = getattr(st.session_state, "processed_data", None)
    tables = getattr(st.session_state, "google_trends_tables", None)
    # Extract the averages table; treat as missing unless it is a non-empty DataFrame
    trends_df = None
    if isinstance(tables, dict) and not getattr(tables, "empty", False):
        averages = tables.get("averages")
        if averages is not None and not getattr(averages, "empty", True):
            trends_df = averages
    if ads_df is None or getattr(ads_df, "empty", True) or trends_df is None or getattr(trends_df, "empty", True):
        setattr(st.session_state, "merged_ads_trends_data", None)
        return None
    merged = aggregate_trends_per_keyword(trends_df, ads_df)
    setattr(st.session_state, "merged_ads_trends_data", merged)
    return merged


# FUNCTION_CONTRACT: render_merged_ads_trends_results
# Purpose: Render the merged Ads+Trends results table in the UI
# Input: None (reads st.session_state["merged_ads_trends_data"])
# Output: None
# Side Effects: Renders Streamlit section header and data table with export buttons
# Business Rules: No-ops when merged data is None or empty
# Failure Modes: Returns silently when no data; never raises
# LINKS: PLAN 16 Task 1 — Trends-Ads merge (mirrors render_merged_ads_serp_results)
def render_merged_ads_trends_results() -> None:
    df = st.session_state.get("merged_ads_trends_data")
    if df is None or getattr(df, "empty", True):
        return
    _render_section_header(t("merged_ads_trends_header"), t("merged_ads_trends_desc"), "blue")
    _render_table_preview_with_exports(
        df=df, display_df=df, auto_save_excel=False,
        save_key="merged_ads_trends_saved",
        excel_filename_prefix="merged_ads_trends_export",
        csv_download_key="download_merged_ads_trends_csv",
    )


# FUNCTION_CONTRACT: render_chained_trends_results
# Purpose: Render Google Trends averages produced from the Ads handoff without changing workflow mode
# Input: None
# Output: None
# Side Effects: Renders Streamlit dataframe section from st.session_state["google_trends_tables"]["averages"]
# Business Rules: Used by URL/keyword/SERP/crawl workflows after Trends is run from selected keyword candidates; focused on averages only (not the heavy render_google_trends_results)
# Failure Modes: Returns silently when no chained trends tables or averages exist
# LINKS: PLAN 16 Task 1 — Trends-Ads merge (mirrors render_chained_serp_results)
def render_chained_trends_results() -> None:
    tables = st.session_state.get("google_trends_tables")
    if not tables:
        return
    averages = tables.get("averages") if isinstance(tables, dict) else None
    if averages is None or getattr(averages, "empty", True):
        return
    _render_section_header(t("trends_results_after_ads_header"), t("trends_results_after_ads_desc"), "blue")
    _render_table_preview_with_exports(
        df=averages,
        display_df=averages,
        auto_save_excel=False,
        save_key="chained_trends_results_saved",
        excel_filename_prefix="chained_trends_results_export",
        csv_download_key="download_chained_trends_csv",
    )


# FUNCTION_CONTRACT: render_google_trends_results
# Purpose: Render Google Trends results in the UI
# Input: auto_save_excel, location_id, language_id, currency_code, serp_config, force_refresh, trends_config
# Output: None (renders UI)
# Side Effects: Displays Streamlit widgets, may trigger downloads
# Business Rules: Shows interest over time, related queries, regional data
def render_google_trends_results(
    auto_save_excel: bool,
    location_id: str,
    language_id: Any,
    currency_code: str,
    serp_config: Optional[dict] = None,
    force_refresh: bool = False,
    trends_config: Optional[dict] = None,  # Phase 10 Task 9: Trends stage
) -> None:
    result = st.session_state.get("google_trends_result")
    tables = st.session_state.get("google_trends_tables")
    if result is None:
        return
    if not tables:
        tables = google_trends_result_to_tables(result)
        st.session_state.google_trends_tables = tables

    _render_section_header(t("google_trends_results_header"), t("google_trends_results_desc"), "green")
    provider = getattr(result, "provider", "")
    data_confidence = str(getattr(result, "data_confidence", "") or "")
    integrity_warnings = list(getattr(result, "integrity_warnings", []) or [])
    provider_metadata = dict(getattr(result, "provider_metadata", {}) or {})
    cache_metadata = dict(getattr(result, "cache_metadata", {}) or {})

    _render_metric_row(
        [
            {
                "title": t("google_trends_provider_label"),
                "content": provider or "—",
                "description": "Backend provider",
                "key": "google_trends_provider_metric",
            },
            {
                "title": t("google_trends_data_confidence_label"),
                "content": data_confidence or "unknown",
                "description": "Result confidence",
                "key": "google_trends_confidence_metric",
            },
            {
                "title": "Cache",
                "content": "Warm" if cache_metadata else "Cold",
                "description": "Metadata present",
                "key": "google_trends_cache_metric",
            },
        ]
    )

    metric_cols = st.columns(3)
    with metric_cols[0]:
        st.metric(t("google_trends_provider_label"), provider or "—")
    with metric_cols[1]:
        st.metric(t("google_trends_data_confidence_label"), data_confidence or "unknown")
    with metric_cols[2]:
        st.metric("Cache", "Warm" if cache_metadata else "Cold")

    if data_confidence in {"blocked", "degraded"}:
        warning_key = (
            "google_trends_blocked_warning"
            if data_confidence == "blocked"
            else "google_trends_degraded_warning"
        )
        st.warning(t(warning_key))

    if provider_metadata:
        with st.expander(t("google_trends_provider_metadata_header"), expanded=False):
            st.json(provider_metadata)

    if cache_metadata:
        with st.expander(t("google_trends_cache_metadata_header"), expanded=False):
            st.json(cache_metadata)

    for warning in integrity_warnings:
        st.warning(warning)
    for warning in getattr(result, "warnings", []) or []:
        st.info(warning)

    _render_google_trends_export_button(result, tables)

    averages_df = tables.get("averages")
    if averages_df is not None and not averages_df.empty:
        _render_table_preview_with_exports(
            df=ExcelExporter.add_trends_columns(
                averages_df,
                _build_google_trends_export_metadata(result),
            ),
            display_df=ExcelExporter.add_trends_columns(
                averages_df,
                _build_google_trends_export_metadata(result),
            ),
            auto_save_excel=auto_save_excel,
            save_key="google_trends_averages_saved",
            excel_filename_prefix="google_trends_averages_export",
            csv_download_key="download_google_trends_averages_csv",
        )

    interest_df = tables.get("interest")
    if interest_df is not None and not interest_df.empty:
        with st.expander(t("google_trends_interest_header"), expanded=False):
            _render_table_preview_with_exports(
                df=ExcelExporter.add_trends_columns(
                    interest_df,
                    _build_google_trends_export_metadata(result),
                ),
                display_df=ExcelExporter.add_trends_columns(
                    interest_df,
                    _build_google_trends_export_metadata(result),
                ),
                auto_save_excel=False,
                save_key="google_trends_interest_saved",
                excel_filename_prefix="google_trends_interest_export",
                csv_download_key="download_google_trends_interest_csv",
            )

    related_df = tables.get("related")
    if related_df is not None and not related_df.empty:
        _render_section_header(t("google_trends_related_header"), t("google_trends_related_desc"), "green")
        related_display_df = ExcelExporter.add_trends_columns(
            related_df,
            _build_google_trends_export_metadata(result),
        )
        st.dataframe(related_display_df, width="stretch")

        # FUNCTION_CONTRACT: _on_select_all_trends_related - callback for trends select all
        def _on_select_all_trends_related() -> None:
            new_value = bool(st.session_state.get(select_all_key, False))
            for idx, row in related_df.iterrows():
                query = str(row.get("Related Query", "")).strip()
                if query:
                    st.session_state[f"google_trends_related_select::{idx}::{query}"] = new_value

        select_all_key = "google_trends_related_select_all"

        st.checkbox(
            t("select_all"),
            key=select_all_key,
            on_change=_on_select_all_trends_related,
        )

        selected_queries: List[str] = []
        for idx, row in related_df.iterrows():
            query = str(row.get("Related Query", "")).strip()
            if not query:
                continue
            key = f"google_trends_related_select::{idx}::{query}"
            if key not in st.session_state:
                st.session_state[key] = False
            if st.checkbox(query, key=key):
                selected_queries.append(query)

        selected_queries = list(dict.fromkeys(selected_queries))
        st.info(
            t(
                "google_trends_selected_stat",
                selected=len(selected_queries),
                total=len(related_df),
            )
        )

        col1, col2 = st.columns(2)
        run_id = str(st.session_state.get("current_run_id", ""))
        with col1:
            if st.button(t("send_selected_to_serp"), key="google_trends_to_serp"):
                if not selected_queries:
                    st.warning(t("serp_chain_no_queries"))
                else:
                    _run_chained_serp_keywords(
                        selected_queries,
                        run_id=run_id,
                        serp_config=serp_config,
                        restore_processed_data=st.session_state.get("processed_data"),
                        force_refresh=force_refresh,
                    )
                    st.rerun()
        with col2:
            if st.button(t("send_selected_to_ads"), key="google_trends_to_ads"):
                if not selected_queries:
                    st.warning(t("serp_chain_no_queries"))
                else:
                    ads_handler = GoogleAdsHandler(
                        location_id=location_id,
                        language_id=language_id,
                        target_currency_code=currency_code,
                    )
                    ideas_df = ads_handler.get_keyword_ideas(
                        selected_queries,
                        source_url="google-trends://related",
                        force_refresh=force_refresh,
                    )
                    processed_df = _ensure_result_columns(ideas_df, currency_code)
                    st.session_state.google_trends_chained_ads_data = processed_df
                    st.rerun()

    region_df = tables.get("regions")
    if region_df is not None and not region_df.empty:
        with st.expander(t("google_trends_region_header"), expanded=False):
            st.dataframe(
                ExcelExporter.add_trends_columns(
                    region_df,
                    _build_google_trends_export_metadata(result),
                ),
                width="stretch",
            )

    ads_df = st.session_state.get("google_trends_chained_ads_data")
    if ads_df is not None and not getattr(ads_df, "empty", True):
        _render_section_header(t("google_trends_ads_results_header"), t("google_trends_ads_results_desc"), "green")
        _render_table_preview_with_exports(
            df=ExcelExporter.add_trends_columns(
                ads_df,
                _build_google_trends_export_metadata(result),
            ),
            display_df=ExcelExporter.add_trends_columns(
                ads_df,
                _build_google_trends_export_metadata(result),
            ),
            auto_save_excel=auto_save_excel,
            save_key="google_trends_ads_saved",
            excel_filename_prefix="google_trends_ads_export",
            csv_download_key="download_google_trends_ads_csv",
        )
        render_ads_keyword_serp_handoff(
            ads_df,
            selection_prefix=f"google_trends_ads_serp::{st.session_state.get('current_run_id', '')}",
            title=t("select_keywords_for_serp"),
            run_id=str(st.session_state.get("current_run_id", "")),
            serp_config=serp_config,
            force_refresh=force_refresh,
            trends_config=trends_config,  # Phase 10 Task 9: Trends stage
        )


# FUNCTION_CONTRACT: render_bidirectional_chain_buttons
# Purpose: Render bidirectional chain buttons for SERP, Ads, and Trends workflows
# Input: selection_prefix (str), location_id (str), language_id (str), currency_code (str), trends_config (Optional[dict])
# Output: None
# Side Effects: Renders chain buttons; handles submit actions; updates session state
# Business Rules: Provides buttons for SERP-first, Ads-first, and Trends workflows
# Failure Modes: None
# LINKS: PLAN 08-01 Task 5, PLAN 10-02 Task 9
def render_bidirectional_chain_buttons(
    selection_prefix: str,
    location_id: str,
    language_id: str,
    currency_code: str,
    trends_config: Optional[dict] = None,
) -> None:
    _render_section_header(t("chain_to_analysis"), t("chain_to_analysis_desc"), "orange")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button(t("serp_then_ads"), key=f"{selection_prefix}_serp_first"):
            selected = _pipeline_get_selected_keyword_candidates(selection_prefix)
            if selected:
                run_id = st.session_state.get("current_run_id", "")
                results = _run_chained_serp_keywords(
                    selected,
                    run_id=run_id,
                )
                if results is not None:
                    st.success(t("serp_analysis_complete"))
                st.rerun()
            else:
                st.warning(t("no_keywords_selected"))

    with col2:
        if st.button(t("ads_then_serp"), key=f"{selection_prefix}_ads_first"):
            selected = _pipeline_get_selected_keyword_candidates(selection_prefix)
            if selected:
                run_id = st.session_state.get("current_run_id", "")
                ads_handler = GoogleAdsHandler(
                    location_id=location_id,
                    language_id=language_id,
                    target_currency_code=currency_code,
                )
                metrics_df = ads_handler.get_keyword_metrics(selected)
                if metrics_df is not None and not metrics_df.empty:
                    st.session_state.processed_data = _ensure_result_columns(
                        metrics_df, currency_code
                    )
                    # SERP-Ads merge: if chained SERP data exists, build merged view
                    if st.session_state.get("chained_serp_results") is not None:
                        build_and_store_merged_ads_serp()
                    st.success(f"Ads analysis completed for {len(selected)} keywords")
                    st.rerun()
                else:
                    st.warning(t("no_ads_metrics_for_keywords"))
            else:
                st.warning(t("no_keywords_selected"))

    with col3:
        # Phase 10 Task 9: Trends stage button for crawl math and other candidates
        if st.button(t("send_selected_to_trends"), key=f"{selection_prefix}_send_to_trends"):
            selected = _pipeline_get_selected_keyword_candidates(selection_prefix)
            if selected:
                from utils.pipeline import run_trends_stage_from_keywords
                run_id = st.session_state.get("current_run_id", "")
                result = run_trends_stage_from_keywords(
                    keywords=selected,
                    trends_config=trends_config,
                    run_id=run_id,
                )
                if result is not None:
                    st.success(t("google_trends_complete"))
                    st.rerun()
            else:
                st.warning(t("no_keywords_selected"))


# Purpose:  profile value implementation
def _profile_value(item: Any, field: str, default: Any = "") -> Any:
    if isinstance(item, dict):
        return item.get(field, default)
    return getattr(item, field, default)


# Purpose:  format field contributions implementation
def _format_field_contributions(contributions: Any) -> str:
    if not isinstance(contributions, dict):
        return str(contributions or "")
    formatted = []
    for field, value in sorted(contributions.items()):
        try:
            formatted.append(f"{field}: {float(value):.4f}")
        except (TypeError, ValueError):
            formatted.append(f"{field}: {value}")
    return ", ".join(formatted)


# Purpose:  format matched terms implementation
def _format_matched_terms(terms: Any) -> str:
    if isinstance(terms, str):
        return terms
    return ", ".join(str(term) for term in (terms or []))


# Purpose:  rounded profile float implementation
def _rounded_profile_float(value: Any) -> float:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return 0.0


# Purpose:  build bm25f scores df implementation
def _build_bm25f_scores_df(bm25f_scores: Any) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for score in bm25f_scores or []:
        rows.append(
            {
                "Doc ID": _profile_value(score, "doc_id", ""),
                "Text": _profile_value(score, "doc_text", ""),
                "Score": _rounded_profile_float(_profile_value(score, "score", 0.0)),
                "Coverage": _rounded_profile_float(
                    _profile_value(score, "query_coverage", 0.0)
                ),
                "Field Contributions": _format_field_contributions(
                    _profile_value(score, "field_contributions", {})
                ),
                "Matched Terms": _format_matched_terms(
                    _profile_value(score, "matched_terms", [])
                ),
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "Doc ID",
            "Text",
            "Score",
            "Coverage",
            "Field Contributions",
            "Matched Terms",
        ],
    )


# Purpose:  localize bm25f scores df implementation
def _localize_bm25f_scores_df(bm25f_df: pd.DataFrame) -> pd.DataFrame:
    return bm25f_df.rename(
        columns={
            column: t(key)
            for column, key in _BM25F_DISPLAY_COLUMN_KEYS.items()
        }
    )


# Purpose:  render bm25f scores section implementation
def _render_bm25f_scores_section(
    profile: Dict[str, Any],
    header_key: str = "seo_math_bm25f_scores_header",
) -> None:
    bm25f_df = _build_bm25f_scores_df(profile.get("bm25f_scores", []))
    if bm25f_df.empty:
        return
    _render_section_header(t(header_key), t("seo_math_bm25f_scores_desc"), "green")
    st.dataframe(_localize_bm25f_scores_df(bm25f_df), width="stretch")


# Purpose:  select export csv sheet implementation
def _select_export_csv_sheet(
    sheets: Dict[str, pd.DataFrame],
    preferred_names: List[str],
) -> Optional[pd.DataFrame]:
    for sheet_name in preferred_names:
        df = sheets.get(sheet_name)
        if isinstance(df, pd.DataFrame) and not df.empty:
            return df
    for df in sheets.values():
        if isinstance(df, pd.DataFrame) and not df.empty:
            return df
    return None


# FUNCTION_CONTRACT: _build_math_analysis_export_sheets
# Purpose: Build full math-analysis export sheets without UI truncation.
# Input: profile (Dict[str, Any]), related_searches (Optional[List[str]]), people_also_ask (Optional[List[str]]), trends_metadata (Optional[Dict[str, Any]])
# Output: Dict[str, pd.DataFrame]
# Side Effects: None
# Business Rules: Keeps the export workbook aligned with the full profile payload instead of the on-screen slices
# Failure Modes: Returns empty sheets when profile sections are missing
# LINKS: PLAN 13-03
def _build_math_analysis_export_sheets(
    profile: Dict[str, Any],
    related_searches: Optional[List[str]] = None,
    people_also_ask: Optional[List[str]] = None,
    trends_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, pd.DataFrame]:
    ngram_rows: List[Dict[str, Any]] = []
    for gram_size, items in sorted((profile.get("ngrams_by_size") or {}).items()):
        for item in items or []:
            ngram_rows.append(
                {
                    "Gram Size": gram_size,
                    "N-Gram": getattr(item, "ngram", ""),
                    "Count": getattr(item, "raw_count", 0),
                    "Weighted Count": round(float(getattr(item, "weighted_count", 0.0)), 4),
                    "DF": getattr(item, "doc_frequency", 0),
                }
            )

    tfidf_rows = [
        {
            "Term": getattr(term, "term", ""),
            "TF-IDF": round(float(getattr(term, "tfidf", 0.0)), 4),
            "DF": getattr(term, "doc_frequency", 0),
        }
        for term in profile.get("tfidf_terms", []) or []
    ]

    cooccurrence_rows = [
        {
            "Term": getattr(term, "term", ""),
            "Count": getattr(term, "cooccurrence_count", 0),
            "Jaccard": round(float(getattr(term, "jaccard_similarity", 0.0)), 4),
            "Context Terms": ", ".join(getattr(term, "context_terms", []) or []),
        }
        for term in profile.get("cooccurrence_terms", []) or []
    ]

    intent = profile.get("intent")
    intent_rows: List[Dict[str, Any]] = []
    if intent:
        intent_rows.append(
            {
                "Intent Type": getattr(intent, "intent_type", ""),
                "Score": round(float(getattr(intent, "score", 0.0)), 4),
                "Confidence": round(float(getattr(intent, "confidence", 0.0)), 4),
                "Signals": ", ".join(getattr(intent, "signals", []) or []),
            }
        )

    related_rows = [
        {"Related Query": query}
        for query in (related_searches if related_searches is not None else profile.get("related_searches", []) or [])
        if str(query).strip()
    ]
    paa_rows = [
        {"Question": question}
        for question in (
            people_also_ask
            if people_also_ask is not None
            else profile.get("people_also_ask", []) or []
        )
        if str(question).strip()
    ]

    sheets = {
        "N-Grams": pd.DataFrame(
            ngram_rows,
            columns=["Gram Size", "N-Gram", "Count", "Weighted Count", "DF"],
        ),
        "TF-IDF Terms": pd.DataFrame(
            tfidf_rows,
            columns=["Term", "TF-IDF", "DF"],
        ),
        "Co-occurrence": pd.DataFrame(
            cooccurrence_rows,
            columns=["Term", "Count", "Jaccard", "Context Terms"],
        ),
        "BM25F Scores": _build_bm25f_scores_df(profile.get("bm25f_scores", [])),
        "Intent": pd.DataFrame(
            intent_rows,
            columns=["Intent Type", "Score", "Confidence", "Signals"],
        ),
        "Related Searches": pd.DataFrame(
            related_rows,
            columns=["Related Query"],
        ),
        "PAA": pd.DataFrame(
            paa_rows,
            columns=["Question"],
        ),
    }

    if trends_metadata:
        sheets["Trends Provider Metadata"] = ExcelExporter.build_trends_provider_metadata_df(
            trends_metadata
        )

    # Domain metrics sheet (Plan 14-02)
    domain_metrics: Optional[List[DomainMetrics]] = st.session_state.get("serp_domain_metrics")
    if domain_metrics:
        domain_rows = []
        for dm in domain_metrics:
            domain_rows.append({
                "Domain": dm.domain,
                "Avg Position": round(dm.avg_position, 1),
                "Keyword SERPs": f"{dm.keyword_serp_count}/{dm.total_keyword_serps}",
                "Total Keywords": dm.total_keyword_serps,
                "Result Count": dm.result_count,
                "Total Results": dm.total_results,
            })
        sheet_name = t("serp_domain_export_sheet") if t("serp_domain_export_sheet") else "SERP Domains"
        sheets[sheet_name] = pd.DataFrame(
            domain_rows,
            columns=["Domain", "Avg Position", "Keyword SERPs", "Total Keywords", "Result Count", "Total Results"],
        )

    return sheets


# FUNCTION_CONTRACT: _render_math_analysis_export_button
# Purpose: Render an export button for math analysis reports.
# Input: profile (Dict[str, Any]), file_prefix (str), related_searches (Optional[List[str]]), people_also_ask (Optional[List[str]]), trends_metadata (Optional[Dict[str, Any]])
# Output: None
# Side Effects: Renders a download button for a multi-sheet Excel workbook
# Business Rules: Export uses the full profile payload and includes provider metadata when supplied
# Failure Modes: Shows export errors in the UI
# LINKS: PLAN 13-03
def _render_math_analysis_export_button(
    profile: Dict[str, Any],
    file_prefix: str,
    related_searches: Optional[List[str]] = None,
    people_also_ask: Optional[List[str]] = None,
    trends_metadata: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        sheets = _build_math_analysis_export_sheets(
            profile=profile,
            related_searches=related_searches,
            people_also_ask=people_also_ask,
            trends_metadata=trends_metadata,
        )
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            try:
                buffer = io.BytesIO()
                if not ExcelExporter.export_multi_sheet_to_buffer(sheets, buffer):
                    raise ValueError("Workbook export failed")
                st.download_button(
                    label=t("export_math_analysis"),
                    data=buffer.getvalue(),
                    file_name=f"{file_prefix}_{timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"download_{file_prefix}_xlsx",
                )
            except Exception as e:
                st.error(f"{t('export_error')}: {e}")
        with btn_col2:
            try:
                csv_df = _select_export_csv_sheet(
                    sheets,
                    [
                        "BM25F Scores",
                        "TF-IDF Terms",
                        "N-Grams",
                        "Co-occurrence",
                        "Related Searches",
                        "PAA",
                    ],
                )
                if csv_df is not None:
                    st.download_button(
                        label=t("download_csv"),
                        data=ExcelExporter.export_csv_to_bytes(csv_df),
                        file_name=f"{file_prefix}_{timestamp}.csv",
                        mime="text/csv",
                        key=f"download_{file_prefix}_csv",
                    )
            except Exception as e:
                st.error(f"{t('csv_error')}: {e}")
    except Exception as e:
        st.error(f"{t('export_error')}: {e}")


# block_results_math_report_render: SERP mathematical analysis report rendering
# Semantic block: Renders n-gram, TF-IDF, co-occurrence, intent, gap analysis, and domain metrics results from SERP profile


# FUNCTION_CONTRACT: render_serp_domain_metrics
# Purpose: Render per-domain metrics from SERP analysis (avg position, keyword SERP frequency, result frequency)
# Input: (none - reads from st.session_state.serp_domain_metrics)
# Output: None
# Side Effects: Renders Streamlit subheader and dataframe
# Business Rules: Returns immediately if no domain metrics; formats avg_position to 1 decimal; uses t() for all display strings
# Failure Modes: Returns silently if session state is None or empty
# LINKS: PLAN 14-02 Task 2
def render_serp_domain_metrics() -> None:
    domain_metrics: Optional[List[DomainMetrics]] = st.session_state.get("serp_domain_metrics")
    if not domain_metrics:
        return

    _render_section_header(t("serp_domain_math_header"), t("serp_domain_math_desc"), "blue")

    rows = []
    for dm in domain_metrics:
        rows.append({
            "Domain": dm.domain,
            t("serp_domain_avg_position"): round(dm.avg_position, 1),
            t("serp_domain_keyword_serps"): f"{dm.keyword_serp_count}/{dm.total_keyword_serps}",
            t("serp_domain_result_frequency"): f"{dm.result_count}/{dm.total_results}",
            t("serp_domain_mentioned"): dm.domain_mentioned,
            t("serp_domain_visibility"): f"{dm.domain_visibility}%",
        })

    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

        # Export domain metrics to Excel and CSV (one row: Excel left, CSV right)
        try:
            domain_df = pd.DataFrame(rows)
            timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            sheet_name = t("serp_domain_export_sheet") if t("serp_domain_export_sheet") else "SERP Domains"
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                export_buffer = io.BytesIO()
                if ExcelExporter.export_multi_sheet_to_buffer({sheet_name: domain_df}, export_buffer):
                    st.download_button(
                        label=t("download_excel"),
                        data=export_buffer.getvalue(),
                        file_name=f"serp_domains_export_{timestamp}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="download_serp_domain_metrics_excel",
                    )
            with btn_col2:
                csv_buffer = ExcelExporter.export_csv_to_bytes(domain_df)
                st.download_button(
                    label=t("download_csv"),
                    data=csv_buffer,
                    file_name=f"serp_domains_export_{timestamp}.csv",
                    mime="text/csv",
                    key="download_serp_domain_metrics_csv",
                )
        except Exception as e:
            logger.warning(f"Domain metrics export failed: {e}")


# FUNCTION_CONTRACT: render_serp_math_report
# Purpose: Render SERP mathematical analysis report with partial-data handling and selectable terms
# Input: serp_df (Optional[pd.DataFrame]), serp_related_data (Optional[List[Dict[str, str]]])
# Output: (none)
# Side Effects: Renders Streamlit UI components; stores selected math terms in session state
# Business Rules: Only renders when seo_math.enabled is true; shows info message for partial data; terms are checkbox-selectable for handoff to Ads/SERP
# Failure Modes: Shows info message and returns silently if SERP data missing or SEO math disabled
# LINKS: PLAN 08-02 Task 6
def render_serp_math_report(
    serp_df: Optional[pd.DataFrame] = None,
    serp_related_data: Optional[List[Dict[str, str]]] = None,
) -> None:
    """Render SERP mathematical analysis report.

    Args:
        serp_df: SERP organic results DataFrame
        serp_related_data: Related searches and PAA data

    Displays:
    - Info message if disabled or no data
    - Top n-grams by gram size
    - Top TF-IDF terms with scores
    - Co-occurrence candidates (related topical terms)
    - Intent summary with confidence metric
    - Related/PAA term list
    - Selectable mathematically identified keywords
    """
    reverse_report = build_reverse_math_report(
        serp_df=serp_df,
        serp_related_data=serp_related_data,
        ads_df=st.session_state.get("serp_chained_ads_data"),
    )
    profile = reverse_report["serp_profile"]

    # Show info message if disabled or no data
    if profile.get("info_message"):
        st.info(profile["info_message"])
        if not profile.get("enabled"):
            return

    # Partial data warning
    if profile.get("has_partial_data"):
        st.warning(t("seo_math_partial_data_warning"))

    # Display n-grams by size
    ngrams_by_size = profile.get("ngrams_by_size", {})
    if ngrams_by_size:
        _render_section_header(t("seo_math_top_ngrams_header"), t("seo_math_top_ngrams_desc"), "green")

        tabs = []
        tab_values = []

        for n in sorted(ngrams_by_size.keys()):
            tabs.append(f"{n}-grams")
            tab_values.append(n)

        if tabs:
            current_tabs = st.tabs(tabs)

            for tab, n in zip(current_tabs, tab_values):
                with tab:
                    ngrams = ngrams_by_size[n]
                    if ngrams:
                        for ngram in ngrams:
                            col1, col2, col3 = st.columns([3, 2, 2])
                            with col1:
                                st.write(f"**{ngram.ngram}**")
                            with col2:
                                st.write(f"Count: {ngram.raw_count}")
                            with col3:
                                st.write(f"DF: {ngram.doc_frequency}")
                    else:
                        st.write(f"No {n}-grams found.")

    # Display TF-IDF terms
    tfidf_terms = profile.get("tfidf_terms", [])
    selection_prefix = "math_tfidf_select"

    if tfidf_terms:
        _render_section_header(t("seo_math_tfidf_header"), t("seo_math_tfidf_desc"), "blue")

        # Create selectable checkbox list
        selected_tfidf = []

        for i, term in enumerate(tfidf_terms):
            checkbox_key = f"{selection_prefix}::{i}"
            is_checked = st.checkbox(
                term.term,
                value=False,
                key=checkbox_key,
                help=f"TF-IDF: {term.tfidf:.3f} | DF: {term.doc_frequency}",
            )
            if is_checked:
                selected_tfidf.append(term.term)

        # Store selected terms for handoff
        if selected_tfidf:
            st.session_state[f"{selection_prefix}_selected"] = selected_tfidf

    # Display co-occurrence terms
    cooccurrence_terms = profile.get("cooccurrence_terms", [])
    if cooccurrence_terms:
        _render_section_header(t("seo_math_cooccurrence_header"), t("seo_math_cooccurrence_desc"), "green")

        for term in cooccurrence_terms:
            col1, col2, col3 = st.columns([3, 2, 2])
            with col1:
                st.write(f"**{term.term}**")
            with col2:
                st.write(f"Count: {term.cooccurrence_count}")
            with col3:
                st.write(f"Jaccard: {term.jaccard_similarity:.2f}")

    _render_bm25f_scores_section(profile)

    # Display intent analysis
    intent = profile.get("intent")
    if intent:
        _render_section_header(t("seo_math_intent_header"), t("seo_math_intent_desc"), "orange")

        # Localized intent type name
        intent_label_key = f"seo_math_intent_{intent.intent_type}"
        intent_label = t(intent_label_key) if _i18n_key_exists(intent_label_key) else intent.intent_type.title()

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(t("seo_math_intent_type"), intent_label)
        with col2:
            st.metric(t("seo_math_intent_score"), f"{intent.score:.1f}")
        with col3:
            st.metric(t("seo_math_intent_confidence"), f"{intent.confidence:.1%}")

        if intent.signals:
            st.write(f"**{t('seo_math_intent_matched_signals')}**")
            st.write(", ".join(intent.signals[:20]))  # Show first 20

    # Display related searches and PAA
    related = profile.get("related_searches", [])
    paa = profile.get("people_also_ask", [])

    if related or paa:
        _render_section_header(t("seo_math_related_queries_header"), t("seo_math_related_queries_desc"), "green")

        if related:
            st.write(f"**{t('seo_math_related_searches_label')}:**")
            st.write(", ".join(related))

        if paa:
            st.write(f"**{t('seo_math_paa_label')}:**")
            for question in paa[:5]:
                st.write(f"- {question}")

    ads_enrichment = reverse_report.get("ads_enrichment", [])
    if ads_enrichment:
        _render_section_header(t("ads_metric_enrichment"), t("ads_metric_enrichment_desc"), "blue")
        st.dataframe(pd.DataFrame(ads_enrichment), width="stretch")

    if reverse_report.get("overlap_keywords") or reverse_report.get("ads_only_keywords"):
        _render_section_header(t("serp_ads_overlap_gaps"), t("serp_ads_overlap_gaps_desc"), "orange")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write("**Overlap**")
            st.write(", ".join(reverse_report.get("overlap_keywords", [])[:10]) or "None")
        with col2:
            st.write("**Ads-only**")
            st.write(", ".join(reverse_report.get("ads_only_keywords", [])[:10]) or "None")
        with col3:
            st.write("**SERP-only**")
            st.write(", ".join(reverse_report.get("serp_only_terms", [])[:10]) or "None")

    _render_math_analysis_export_button(
        profile=profile,
        file_prefix="serp_math_report_export",
        related_searches=related,
        people_also_ask=paa,
    )

    # Domain metrics section (Plan 14-02)
    render_serp_domain_metrics()

    # Handoff options
    if tfidf_terms or cooccurrence_terms:
        _render_section_header(t("handoff_to_analysis"), t("handoff_to_analysis_desc"), "blue")

        col1, col2 = st.columns(2)

        with col1:
            if st.button(t("send_selected_to_google_ads"), key="math_to_ads"):
                selected_tfidf = st.session_state.get(f"{selection_prefix}_selected", [])
                if selected_tfidf:
                    st.info(t("math_ads_started", count=len(selected_tfidf)))
                    from config.settings import GOOGLE_ADS_CONFIG
                    ads_location = str(GOOGLE_ADS_CONFIG.get("location_id", "2840"))
                    raw_lang = GOOGLE_ADS_CONFIG.get("language_id", "1000")
                    ads_language = raw_lang if isinstance(raw_lang, list) else str(raw_lang)
                    ads_currency = str(GOOGLE_ADS_CONFIG.get("currency_code", "USD"))
                    run_id = str(st.session_state.get("current_run_id", ""))
                    result = run_serp_chain_to_ads_workflow(
                        selected_queries=selected_tfidf,
                        location_id=ads_location,
                        language_id=ads_language,
                        currency_code=ads_currency,
                        run_id=run_id,
                    )
                    if result is not None:
                        st.success(t("math_ads_complete"))
                        st.rerun()
                else:
                    st.warning(t("select_terms_first"))

        with col2:
            if st.button(t("send_selected_to_serp"), key="math_to_serp"):
                selected_tfidf = st.session_state.get(f"{selection_prefix}_selected", [])
                if selected_tfidf:
                    st.info(t("math_serp_started", count=len(selected_tfidf)))
                    run_id = str(st.session_state.get("current_run_id", ""))
                    result = _run_chained_serp_keywords(
                        selected_keywords=selected_tfidf,
                        run_id=run_id,
                    )
                    if result is not None:
                        st.success(t("math_serp_complete"))
                        st.rerun()
                else:
                    st.warning(t("select_terms_first"))


# block_results_crawl_report_render: Crawl mathematical report rendering
# Semantic block: Shows page and aggregate crawl profiles and exposes crawl-derived terms for SERP/Ads handoff.


# FUNCTION_CONTRACT: render_crawl_math_report
# Purpose: Render crawl math report with aggregate/page sections and selected keyword handoff controls.
# Input: report (Optional[Dict[str, Any]]), location_id (str), language_id (str), currency_code (str), trends_config (Optional[dict])
# Output: None
# Side Effects: Renders Streamlit UI; reads keyword candidate checkbox state; may trigger SERP/Ads/Trends chain buttons.
# Business Rules: Ads metrics are not required; crawl report uses text evidence from crawled pages only.
# Failure Modes: Returns silently if no crawl report exists; shows info messages for empty/disabled reports.
# LINKS: PLAN 08-03 Task 4, PLAN 10-02 Task 9
def render_crawl_math_report(
    report: Optional[Dict[str, Any]] = None,
    location_id: str = "",
    language_id: str = "",
    currency_code: str = "",
    trends_config: Optional[dict] = None,
) -> None:
    report = report or st.session_state.get("crawl_math_report")
    if not report:
        return

    _render_section_header(t("crawl_report_header"), t("crawl_report_desc"), "green")
    if report.get("info_message"):
        st.info(report["info_message"])
        if not report.get("pages"):
            return

    crawl_result = report.get("crawl")
    if crawl_result:
        # Handle both CrawlResult objects and dict representations
        if isinstance(crawl_result, dict):
            pages = crawl_result.get("pages", [])
            visited_count = crawl_result.get("visited_count", 0)
            errors = crawl_result.get("errors", [])
        else:
            pages = getattr(crawl_result, "pages", [])
            visited_count = getattr(crawl_result, "visited_count", 0)
            errors = getattr(crawl_result, "errors", [])

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(t("crawl_pages_stat"), len(pages))
        with col2:
            st.metric(t("crawl_visited_stat"), visited_count)
        with col3:
            st.metric(t("crawl_errors_stat"), len(errors))

    aggregate_profile = report.get("aggregate_profile", {})
    tfidf_terms = aggregate_profile.get("tfidf_terms", [])
    ngrams_by_size = aggregate_profile.get("ngrams_by_size", {})

    if tfidf_terms:
        _render_section_header(t("crawl_aggregate_terms"), t("crawl_aggregate_terms_desc"), "green")
        terms_df = pd.DataFrame(
            [
                {
                    "Term": term.term,
                    "TF-IDF": round(term.tfidf, 4),
                    "DF": term.doc_frequency,
                }
                for term in tfidf_terms
            ]
        )
        st.dataframe(terms_df, width="stretch")

    _render_bm25f_scores_section(
        aggregate_profile,
        header_key="crawl_bm25f_scores_header",
    )

    if ngrams_by_size:
        with st.expander(t("crawl_ngram_details")):
            for n, ngrams in sorted(ngrams_by_size.items()):
                if not ngrams:
                    continue
                st.write(f"**{n}-grams**")
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "N-gram": item.ngram,
                                "Count": item.raw_count,
                                "Weighted": round(item.weighted_count, 2),
                                "DF": item.doc_frequency,
                            }
                            for item in ngrams
                        ]
                    ),
                    width="stretch",
                )

    pages = report.get("pages", [])
    if pages:
        with st.expander(t("crawl_page_details")):
            for index, page in enumerate(pages, start=1):
                title = page.get("title") or ""
                url = page.get("url") or ""
                meta_description = page.get("meta_description") or ""
                headings = page.get("headings") or []
                analysis_evidence = page.get("analysis_evidence") or {}

                st.markdown(f"**{index}. {t('crawl_page_title_label')}:** {title or '—'}")
                st.markdown(f"**{t('crawl_page_url_label')}:** {url}")
                st.markdown(
                    f"**{t('crawl_page_meta_description_label')}:** "
                    f"{meta_description or '—'}"
                )
                st.markdown(f"**{t('crawl_page_heading_count_label')}:** {len(headings)}")
                if headings:
                    st.markdown(f"**{t('crawl_page_headings_label')}:**")
                    for heading in headings[:10]:
                        st.markdown(f"- {heading}")

                st.markdown(f"**{t('crawl_page_analysis_evidence_label')}:**")
                intent = analysis_evidence.get("intent")
                top_tfidf_terms = analysis_evidence.get("top_tfidf_terms") or []
                top_ngrams = analysis_evidence.get("top_ngrams") or []
                if intent:
                    st.markdown(f"- {t('crawl_page_intent_label')}: {intent}")
                if top_tfidf_terms:
                    st.markdown(
                        f"- {t('crawl_page_tfidf_terms_label')}: "
                        f"{', '.join(top_tfidf_terms)}"
                    )
                if top_ngrams:
                    st.markdown(
                        f"- {t('crawl_page_top_ngrams_label')}: "
                        f"{', '.join(top_ngrams)}"
                    )

    _render_math_analysis_export_button(
        profile=aggregate_profile,
        file_prefix="crawl_math_report_export",
    )

    selector_result = render_keyword_candidate_selector(
        candidates_key="kw_candidates_crawl_math_handoff",
        selection_prefix="crawl_math_handoff",
        title=t("crawl_select_keywords"),
    )
    if selector_result:
        render_bidirectional_chain_buttons(
            selection_prefix="crawl_math_handoff",
            location_id=location_id,
            language_id=language_id,
            currency_code=currency_code,
            trends_config=trends_config,  # Phase 10 Task 9: Trends stage
        )


# FUNCTION_CONTRACT: _build_google_trends_export_metadata
# Purpose: Build metadata payload for Google Trends exports.
# Input: result (Any)
# Output: Dict[str, Any]
# Side Effects: None
# Business Rules: Preserves provider confidence, averages, geo/timeframe, cache metadata, integrity warnings, and caveats for export surfaces
# Failure Modes: Returns empty fields when metadata is missing
# LINKS: PLAN 13-03
def _build_google_trends_export_metadata(result: Any) -> Dict[str, Any]:
    return {
        "provider": getattr(result, "provider", ""),
        "data_confidence": getattr(result, "data_confidence", ""),
        "averages": dict(getattr(result, "averages", {}) or {}),
        "geo": getattr(getattr(result, "request", None), "geo", "")
        or getattr(result, "geo", ""),
        "timeframe": getattr(getattr(result, "request", None), "timeframe", "")
        or getattr(result, "timeframe", ""),
        "warnings": list(getattr(result, "warnings", []) or []),
        "integrity_warnings": list(getattr(result, "integrity_warnings", []) or []),
        "provider_metadata": dict(getattr(result, "provider_metadata", {}) or {}),
        "cache_metadata": dict(getattr(result, "cache_metadata", {}) or {}),
        "caveats": [
            t("google_trends_relative_scale_caveat"),
            t("google_trends_official_alpha_caveat"),
        ],
    }


# FUNCTION_CONTRACT: _render_google_trends_export_button
# Purpose: Render a full Google Trends workbook export button.
# Input: result (Any), tables (Dict[str, pd.DataFrame])
# Output: None
# Side Effects: Renders a download button with a multi-sheet workbook and metadata sheet
# Business Rules: Export should keep provider metadata visible alongside the content tables
# Failure Modes: Shows export errors in the UI
# LINKS: PLAN 13-03
def _render_google_trends_export_button(
    result: Any,
    tables: Dict[str, pd.DataFrame],
) -> None:
    try:
        trends_metadata = _build_google_trends_export_metadata(result)
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        sheets = {
            "Averages": ExcelExporter.add_trends_columns(
                tables.get("averages", pd.DataFrame()),
                trends_metadata,
            ),
            "Interest Over Time": ExcelExporter.add_trends_columns(
                tables.get("interest", pd.DataFrame()),
                trends_metadata,
            ),
            "Related Queries": ExcelExporter.add_trends_columns(
                tables.get("related", pd.DataFrame()),
                trends_metadata,
            ),
            "Regions": ExcelExporter.add_trends_columns(
                tables.get("regions", pd.DataFrame()),
                trends_metadata,
            ),
            "Trends Provider Metadata": ExcelExporter.build_trends_provider_metadata_df(
                trends_metadata
            ),
        }
        # Export buttons (one row: Excel left, CSV right)
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            try:
                buffer = io.BytesIO()
                if not ExcelExporter.export_multi_sheet_to_buffer(sheets, buffer):
                    raise ValueError("Workbook export failed")
                st.download_button(
                    label=t("export_math_analysis"),
                    data=buffer.getvalue(),
                    file_name=f"google_trends_export_{timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="download_google_trends_export_xlsx",
                )
            except Exception as e:
                st.error(f"{t('export_error')}: {e}")
        with btn_col2:
            try:
                csv_df = _select_export_csv_sheet(
                    sheets,
                    [
                        "Averages",
                        "Interest Over Time",
                        "Related Queries",
                        "Regions",
                    ],
                )
                if csv_df is not None:
                    st.download_button(
                        label=t("download_csv"),
                        data=ExcelExporter.export_csv_to_bytes(csv_df),
                        file_name=f"google_trends_export_{timestamp}.csv",
                        mime="text/csv",
                        key="download_google_trends_export_csv",
                    )
            except Exception as e:
                st.error(f"{t('csv_error')}: {e}")
    except Exception as e:
        st.error(f"{t('export_error')}: {e}")


# block_results_regenerate_quality_feedback: Generation quality scoring and regenerate feedback rendering
# Semantic block: Renders element-specific quality scores for generated SEO text with regenerate controls


# FUNCTION_CONTRACT: render_generation_quality_report
# Purpose: Render generation quality report with element-specific scoring and regenerate button
# Input: generated_text (str), primary_keyword (str), serp_profile (Dict[str, Any])
# Output: (none)
# Side Effects: Renders Streamlit UI components; displays quality scores and issues
# Business Rules: Parses generated text into sections; scores each against SERP profile; shows issues; provides regenerate button
# Failure Modes: Shows empty state if no generated text; never raises
# LINKS: PLAN 08-02 Task 7
def render_generation_quality_report(
    generated_text: str,
    primary_keyword: str,
    serp_profile: Dict[str, Any],
) -> None:
    """Render generation quality report with element-specific scoring.

    Args:
        generated_text: Full generated SEO text output
        primary_keyword: Primary target keyword
        serp_profile: SERP analysis profile with top_ngrams, tfidf_terms, etc.

    Displays:
    - Per-element quality scores (META_TITLE, META_DESCRIPTION, H1, DESCRIPTION)
    - Issues list for each element
    - Length compliance status
    - Keyword coverage
    - Overall quality assessment
    """
    if not generated_text:
        st.info(t("no_generated_text_to_analyze"))
        return

    from utils.seo_math_analysis import score_generated_text

    # Build serp profile for scoring
    scoring_profile = {
        "top_ngrams": [ngram.ngram for ngram in serp_profile.get("ngrams_by_size", {}).get(1, [])],
        "tfidf_terms": [term.term for term in serp_profile.get("tfidf_terms", [])],
        "cooccurrence_terms": [term.term for term in serp_profile.get("cooccurrence_terms", [])],
        "tfidf_overlap": 0.5,  # Default, should be calculated from actual overlap
        "cooccurrence_coverage": 0.6,  # Default
        "meta_title": "",
    }

    # Score generated text
    scores = score_generated_text(generated_text, primary_keyword, scoring_profile)

    _render_section_header(t("generation_quality_report"), t("generation_quality_report_desc"), "orange")

    # Overall score
    element_scores = [s.score for s in scores.values()]
    overall_score = sum(element_scores) / len(element_scores) if element_scores else 0

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Overall Score", f"{overall_score:.0f}/100")
    with col2:
        status = "Good" if overall_score >= 70 else "Fair" if overall_score >= 50 else "Needs Work"
        st.metric("Status", status)
    with col3:
        compliant_count = sum(1 for s in scores.values() if s.length_compliant)
        st.metric("Length Compliant", f"{compliant_count}/{len(scores)}")

    st.divider()

    # Element-specific scores
    for element_type in ["META_TITLE", "META_DESCRIPTION", "H1", "DESCRIPTION"]:
        element_score = scores.get(element_type)
        if not element_score:
            continue

        element_name = element_type.replace("_", " ").title()

        with st.expander(f"{element_name}: {element_score.score:.0f}/100", expanded=(element_score.score < 70)):
            # Metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**Length Compliant:** {'✓' if element_score.length_compliant else '✗'}")
            with col2:
                st.write(f"**Keyword Present:** {'✓' if element_score.primary_keyword_present else '✗'}")
            with col3:
                st.write(f"**Keyword Coverage:** {element_score.keyword_coverage:.1%}")

            # Issues
            if element_score.issues:
                st.write("**Issues:**")
                for issue in element_score.issues:
                    # Convert issue key to readable text
                    issue_text = issue.replace("_", " ").title()
                    st.write(f"- {issue_text}")
            else:
                st.write("**No issues detected**")

    # Tips for improvement
    if overall_score < 70:
        st.divider()
        _render_section_header(t("improvement_suggestions"), t("improvement_suggestions_desc"), "orange")

        suggestions = []

        for element_type, element_score in scores.items():
            if element_score.score < 70:
                element_name = element_type.replace("_", " ").title()

                if not element_score.primary_keyword_present:
                    suggestions.append(f"{element_name}: Add primary keyword")

                if not element_score.length_compliant:
                    if element_type == "META_TITLE":
                        suggestions.append(f"{element_name}: Keep between 50-60 characters")
                    elif element_type == "META_DESCRIPTION":
                        suggestions.append(f"{element_name}: Keep between 150-160 characters")
                    elif element_type == "H1":
                        suggestions.append(f"{element_name}: Keep between 30-70 characters")
                    elif element_type == "DESCRIPTION":
                        suggestions.append(f"{element_name}: Aim for 500+ characters")

                if element_score.keyword_coverage < 0.3:
                    suggestions.append(f"{element_name}: Include more top n-grams from SERP analysis")

        if suggestions:
            for suggestion in suggestions[:5]:  # Show top 5
                st.write(f"- {suggestion}")

    # Regenerate button with bounded feedback
    if overall_score < 70:
        st.divider()

        # Check regenerate attempts
        max_attempts = 3
        regenerate_key = "seo_generation_regenerate_attempts"
        current_attempts = st.session_state.get(regenerate_key, 0)

        if current_attempts < max_attempts:
            col1, col2 = st.columns(2)

            with col1:
                if st.button(t("regenerate_with_quality_feedback"), key="regenerate_with_feedback"):
                    # Build feedback payload
                    feedback_issues = []

                    for element_type, element_score in scores.items():
                        if element_score.score < 70:
                            feedback_issues.extend([
                                f"{element_type}: " + ", ".join(element_score.issues)
                            ])

                    feedback = {
                        "overall_score": overall_score,
                        "issues": feedback_issues,
                        "suggestions": suggestions[:5],
                    }

                    # Store feedback in session state for LLM
                    st.session_state["seo_generation_feedback"] = feedback
                    st.session_state[regenerate_key] = current_attempts + 1

                    st.info(f"Regeneration queued (attempt {current_attempts + 1} of {max_attempts})")
                    st.rerun()

            with col2:
                attempts_remaining = max_attempts - current_attempts
                st.write(f"Attempts remaining: {attempts_remaining}")
        else:
            st.warning(t("max_regeneration_reached"))


# block_results_gen_text_math_report: Generated text math analysis rendering
# Semantic block: Shows aggregate and per-row math profiles for generated SEO text.

# FUNCTION_CONTRACT: render_generated_text_math_report
# Purpose: Render math analysis report for generated SEO text with aggregate and per-row profiles
# Input: None (reads generated_seo_texts from session state)
# Output: None
# Side Effects: Renders Streamlit UI; may store gen_text_math_profile in session state
# Business Rules: Only renders when analyze_generated_text is enabled in config and generated text exists
# Failure Modes: Returns silently when disabled or no text available
# LINKS: PLAN 15 Task 3
def render_generated_text_math_report() -> None:
    from config.settings import SEO_MATH_CONFIG

    if not SEO_MATH_CONFIG.get("enabled", False):
        return
    if not SEO_MATH_CONFIG.get("analyze_generated_text", False):
        return

    texts_df = st.session_state.get("generated_seo_texts")
    if texts_df is None or (isinstance(texts_df, pd.DataFrame) and texts_df.empty):
        return

    from utils.pipeline import build_generated_text_math_profile

    profile = build_generated_text_math_profile(texts_df)

    if profile.get("info_message"):
        if not profile.get("total_rows"):
            return

        _render_section_header(t("gen_math_report_header"), t("gen_math_report_desc"), "green")
    st.caption(t("gen_math_corpus_source"))

    # Aggregate section
    _render_gen_math_aggregate(profile)

    # Per-row section — shows metadata summary only; full analysis is in the aggregate above
    per_row = profile.get("per_row_profiles", [])
    if per_row:
        with st.expander(
            t("gen_math_elements") + f" ({len(per_row)})",
            expanded=False,
        ):
            for i, row_profile in enumerate(per_row):
                url = row_profile.get("url", "")
                keywords = row_profile.get("keywords", "")
                label = url if url else keywords if keywords else f"#{i + 1}"
                with st.expander(f"📄 {label}", expanded=False):
                    if keywords:
                        st.caption(f"{t('gen_math_keyword_label')}: {keywords}")
                    _render_gen_math_row_summary(row_profile)


def _render_gen_math_aggregate(profile: Dict[str, Any]) -> None:
    """Render aggregate math analysis sections from a profile dict."""
    tfidf_terms = profile.get("tfidf_terms", [])
    ngrams_by_size = profile.get("ngrams_by_size", {})
    cooccurrence_terms = profile.get("cooccurrence_terms", [])
    intent = profile.get("intent")

    # N-grams
    if ngrams_by_size:
        tabs = st.tabs([f"{n}-grams" for n in sorted(ngrams_by_size.keys())])
        for tab, n in zip(tabs, sorted(ngrams_by_size.keys())):
            ngrams = ngrams_by_size[n]
            if ngrams:
                df = pd.DataFrame([
                    {
                        "N-gram": ng.ngram,
                        "Count": ng.raw_count,
                        "Weighted": round(ng.weighted_count, 2),
                        "DF": ng.doc_frequency,
                    }
                    for ng in ngrams
                ])
                tab.dataframe(df, use_container_width=True, hide_index=True)
            else:
                tab.info("—")

    # TF-IDF
    if tfidf_terms:
        _render_section_header(t("seo_math_tfidf_header"), t("gen_math_tfidf_desc"), "blue")
        df = pd.DataFrame([
            {
                "Term": term.term,
                "TF-IDF": round(term.tfidf, 4),
                "TF": round(term.raw_tf, 4),
                "IDF": round(term.idf, 4),
                "DF": term.doc_frequency,
            }
            for term in tfidf_terms
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)

    # Co-occurrence
    if cooccurrence_terms:
        _render_section_header(t("seo_math_cooccurrence_header"), t("gen_math_cooccurrence_desc"), "green")
        df = pd.DataFrame([
            {
                "Term": ct.term,
                "Co-occurrence": ct.cooccurrence_count,
                "Jaccard": round(ct.jaccard_similarity, 4),
            }
            for ct in cooccurrence_terms
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)

    # Intent
    if intent:
        _render_gen_math_intent(intent)

    # BM25F
    bm25f_scores = profile.get("bm25f_scores", [])
    if bm25f_scores:
        _render_bm25f_scores_section(
            profile,
            header_key="seo_math_bm25f_scores_header",
        )

    # Export
    if tfidf_terms or ngrams_by_size or cooccurrence_terms:
        _render_math_analysis_export_button(
            profile=profile,
            file_prefix="gen_text_math_report_export",
        )


def _render_gen_math_row_summary(row_profile: Dict[str, Any]) -> None:
    """Render a lightweight summary for a single per-row profile — avoids duplicating the full aggregate."""
    ngrams_by_size = row_profile.get("ngrams_by_size", {})
    tfidf_terms = row_profile.get("tfidf_terms", [])
    intent = row_profile.get("intent")

    # Top n-grams quick preview (top 5 per size)
    if ngrams_by_size:
        for n in sorted(ngrams_by_size.keys()):
            ngrams = ngrams_by_size[n]
            if ngrams:
                top5 = ngrams[:5]
                preview = ", ".join(f"{ng.ngram} ({ng.raw_count})" for ng in top5)
                st.caption(f"**{n}-grams**: {preview}")

    # Top TF-IDF terms quick preview (top 5)
    if tfidf_terms:
        top5 = tfidf_terms[:5]
        preview = ", ".join(f"{term.term} ({round(term.tfidf, 3)})" for term in top5)
        st.caption(f"**TF-IDF**: {preview}")

    # Intent summary
    if intent:
        intent_type = intent.intent_type if hasattr(intent, "intent_type") else "undetermined"
        confidence = intent.confidence if hasattr(intent, "confidence") else 0.0
        intent_label = t(f"seo_math_intent_{intent_type}")
        st.caption(f"**{t('seo_math_intent_type')}**: {intent_label} ({confidence:.0%})")


def _render_gen_math_intent(intent) -> None:
    """Render intent analysis block for generated text math report."""
    intent_type = intent.intent_type if hasattr(intent, "intent_type") else "undetermined"
    confidence = intent.confidence if hasattr(intent, "confidence") else 0.0
    score = intent.score if hasattr(intent, "score") else 0.0
    signals = intent.signals if hasattr(intent, "signals") else []

    intent_label = t(f"seo_math_intent_{intent_type}")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(t("seo_math_intent_type"), intent_label)
    with col2:
        st.metric(t("seo_math_intent_confidence"), f"{confidence:.0%}")
    with col3:
        st.metric(t("seo_math_intent_score"), f"{score:.2f}")

    if signals:
        st.caption(f"{t('seo_math_intent_matched_signals')}: {', '.join(signals[:15])}")
