# MODULE_CONTRACT: app
# Purpose: Main Streamlit entrypoint, session state management, workflow routing with keyword-gated SERP, crawl reports, and Trends-as-stage integration
# Rationale: Central coordinator for workflow modes (URL→LLM→Ads, URL→Ads, Keyword→Ads, SERP, Crawl, Trends) with SERP/Ads/Trends chaining
# Dependencies: streamlit, components.*, utils.pipeline, config.settings
# Exports: main(), _ensure_session_defaults(), _reset_run_state(), _render_input_form()
# LINKS: requirements.xml#UC-001, requirements.xml#UC-002, requirements.xml#UC-003, development-plan.xml#MOD-001, PLAN 08-01, PLAN 10-02 Task 9
# MODULE_MAP: app
# Public Functions: main(), _ensure_session_defaults(), _reset_run_state(), _render_input_form()
# Private Helpers: _normalize_entries(), _build_submission_signature(), _workflow_options(), _workflow_mode_label(), _sync_workflow_mode_from_widget()
# Key Semantic Blocks: block_workflow_route_mode_select, block_workflow_keyword_gate, block_workflow_chain_order_route, block_workflow_crawl_report_route, block_workflow_trends_stage_integration
# Critical Flows: User Input -> Keyword/Crawl Extraction -> Checkbox Selection -> SERP/Ads/Trends/SEO -> Export
# Verification: verification-plan.xml#V-001, verification-plan.xml#V-003
# CHANGE_SUMMARY: Added keyword-gated SERP workflows; SERP pre-step disabled for URL modes until keyword extraction; staged LLM extraction for SERP/Ads chaining; Phase 8 Plan 03: added crawl/report workflow routing; Phase 9 review fix: initial SERP pre-step is visible only for keyword-seed mode; Phase 10 Task 9: added Trends-as-stage buttons after keyword-producing steps.

import html
from datetime import datetime
from typing import Any, Dict, List

import streamlit as st
from components.results import (
    render_chained_serp_results,
    render_crawl_math_report,
    render_generated_text_math_report,
    render_google_trends_results,
    render_history,
    render_keyword_candidate_selector_with_sources,
    render_keyword_ideas_generation,
    render_keyword_results,
    render_keyword_selection,
    render_scraping_preview,
    render_seo_generation,
    render_seo_results,
    render_serp_chain_to_ads,
    render_serp_chained_ads_results,
    render_merged_ads_serp_results,
    render_merged_ads_trends_results,
    render_chained_trends_results,
    render_serp_math_report,
    render_serp_related_searches,
    render_serp_results,
)
from components.sidebar import render_sidebar
from config.i18n import t
from streamlit_shadcn_ui import metric_card
from utils.cleanup import run_startup_cleanup
from utils.file_handler import FileHandler, FileParsingError
from utils.logger import APP_LOG, logger
from utils.pipeline import (
    prepare_seo_context_from_selection,
    prepare_urls_for_seo,
    run_crawl_math_report_workflow,
    run_google_trends_workflow,
    run_keyword_seed_workflow,
    run_keyword_to_llm_workflow,
    run_llm_url_keyword_extraction_tupled,  # Phase 9 Task 9: staged extraction wrapper
    run_selected_keywords_to_ads_workflow,
    run_serp_analysis_workflow,
    run_serp_workflow_with_source_context,
    run_url_seed_workflow,
)
from utils.validator import validate_api_keys

st.set_page_config(page_title="Auto SEO Keyword Planner", page_icon=":rocket:", layout="wide")


def _render_section_header(title: str, description: str, divider: str) -> None:
    st.subheader(title, divider=divider)
    if description:
        st.caption(description)


def _inject_console_styles() -> None:
    upload_btn_text = html.escape(t("upload_button"))
    css = """
<style>
/* CSS hack to translate Streamlit's native 'Browse files' / 'Upload' button inside st.file_uploader */
[data-testid="stFileUploader"] button * {
    display: none !important;
}
[data-testid="stFileUploader"] button::after {
    content: "\\2B06  __UPLOAD_BTN_TEXT__";
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--console-text, #0f172a);
}

:root {
  color-scheme: light;
  --console-bg: #f8fafc;
  --console-surface: #ffffff;
  --console-surface-alt: #f1f5f9;
  --console-border: #d6deea;
  --console-border-strong: #bfd1ea;
  --console-text: #0f172a;
  --console-muted: #475569;
  --console-blue: #1d4ed8;
  --console-blue-soft: #dbeafe;
  --console-teal: #0f766e;
  --console-teal-soft: #ccfbf1;
  --console-amber: #d97706;
  --console-amber-soft: #fef3c7;
  --console-sidebar-bg: #f1f5f9;
  --console-input-bg: #ffffff;
  --console-input-border: #cbd5e1;
  --console-input-border-focus: #1d4ed8;
}

section.main > div.block-container {
  max-width: none;
  padding-top: 1rem;
  padding-left: 1.15rem;
  padding-right: 1.15rem;
  padding-bottom: 1.15rem;
}

html, body, [data-testid="stAppViewContainer"] {
  background: var(--console-bg);
  color: var(--console-text);
}

[data-testid="stHeader"] {
  background: rgba(248, 250, 252, 0.94);
  border-bottom: 1px solid var(--console-border);
}

[data-testid="stSidebar"] {
  background: var(--console-sidebar-bg);
  border-right: 1px solid var(--console-border);
}

[data-testid="stSidebar"] .block-container {
  padding-top: 1rem;
  padding-left: 1rem;
  padding-right: 1rem;
}

div[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
  gap: 0.8rem;
}

/*
 * Input-field visibility (sidebar + main).
 * The sidebar is now a distinct off-white panel, so every input control gets an
 * explicit white fill + border to read unambiguously as an interactive field
 * rather than blending into the panel surface.
 */
div[data-testid="stSidebar"] div[data-testid="stTextInput"],
div[data-testid="stSidebar"] div[data-testid="stTextArea"],
div[data-testid="stSidebar"] div[data-testid="stSelectbox"],
div[data-testid="stSidebar"] div[data-testid="stNumberInput"],
div[data-testid="stSidebar"] div[data-testid="stDateInput"],
div[data-testid="stSidebar"] div[data-testid="stTimeInput"],
div[data-testid="stSidebar"] div[data-testid="stMultiSelect"] {
  background: var(--console-input-bg);
  border: 1px solid var(--console-input-border);
  border-radius: 0.7rem;
  padding: 0.18rem 0.5rem;
}

div[data-testid="stSidebar"] div[data-testid="stTextInput"]:focus-within,
div[data-testid="stSidebar"] div[data-testid="stTextArea"]:focus-within,
div[data-testid="stSidebar"] div[data-testid="stSelectbox"]:focus-within,
div[data-testid="stSidebar"] div[data-testid="stNumberInput"]:focus-within,
div[data-testid="stSidebar"] div[data-testid="stDateInput"]:focus-within,
div[data-testid="stSidebar"] div[data-testid="stTimeInput"]:focus-within,
div[data-testid="stSidebar"] div[data-testid="stMultiSelect"]:focus-within {
  border-color: var(--console-input-border-focus);
  box-shadow: 0 0 0 2px var(--console-blue-soft);
}

/* Main-panel inputs: same treatment so the form fields are obvious everywhere. */
section.main div[data-testid="stTextInput"],
section.main div[data-testid="stTextArea"],
section.main div[data-testid="stSelectbox"],
section.main div[data-testid="stNumberInput"],
section.main div[data-testid="stDateInput"],
section.main div[data-testid="stMultiSelect"] {
  background: var(--console-input-bg);
  border: 1px solid var(--console-input-border);
  border-radius: 0.7rem;
  padding: 0.18rem 0.5rem;
}

section.main div[data-testid="stTextInput"]:focus-within,
section.main div[data-testid="stTextArea"]:focus-within,
section.main div[data-testid="stSelectbox"]:focus-within,
section.main div[data-testid="stNumberInput"]:focus-within,
section.main div[data-testid="stDateInput"]:focus-within,
section.main div[data-testid="stMultiSelect"]:focus-within {
  border-color: var(--console-input-border-focus);
  box-shadow: 0 0 0 2px var(--console-blue-soft);
}

div[data-testid="stVerticalBlockBorderWrapper"] {
  background: var(--console-surface);
  border: 1px solid var(--console-border);
  border-radius: 0.95rem;
}

div[data-testid="stExpander"] {
  border: 1px solid var(--console-border);
  border-radius: 0.95rem;
  background: #ffffff;
}

div[data-testid="stExpander"] summary {
  padding: 0.7rem 0.9rem;
}

div[data-testid="stButton"] > button {
  min-height: 44px;
  border-radius: 0.85rem;
  border: 1px solid var(--console-border-strong);
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  color: var(--console-blue);
  font-weight: 600;
  box-shadow: none;
}

div[data-testid="stButton"] > button:hover {
  border-color: #93c5fd;
  background: linear-gradient(180deg, #ffffff 0%, #eff6ff 100%);
}

div[data-testid="stButton"] > button[kind="primary"] {
  background: linear-gradient(180deg, #2f5ddb 0%, #2448bf 100%);
  border-color: #2448bf;
  color: #ffffff;
}

div[data-testid="stButton"] > button[kind="primary"]:hover {
  background: linear-gradient(180deg, #365fdc 0%, #1d3fbc 100%);
}

div[data-testid="stMetric"] {
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  border: 1px solid var(--console-border);
  border-radius: 0.95rem;
  padding: 0.8rem 0.9rem;
  box-shadow: none;
}

div[data-testid="stMetric"] [data-testid="stMetricLabel"] {
  color: var(--console-muted);
  font-size: 0.82rem;
}

div[data-testid="stMetric"] [data-testid="stMetricValue"] {
  color: var(--console-blue);
  font-size: 1.8rem;
  line-height: 1;
}

div[data-testid="stMetric"] [data-testid="stMetricDelta"] {
  color: var(--console-teal);
}

div[data-testid="stDataFrame"] {
  border: 1px solid var(--console-border);
  border-radius: 0.95rem;
  overflow: hidden;
}

div[data-testid="stTabs"] button {
  color: var(--console-muted);
}

div[data-testid="stTabs"] button[aria-selected="true"] {
  color: var(--console-blue);
}

.st-key-app-shell,
.st-key-workflow-strip,
.st-key-input-panel,
.st-key-summary-panel,
.st-key-results-panel,
.st-key-history-panel,
.st-key-status-panel,
.st-key-sidebar-shell,
.st-key-sidebar-group {
  background: var(--console-surface);
  border: 1px solid var(--console-border);
  border-radius: 1rem;
  padding: 1rem 1rem 0.85rem;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  padding-bottom: 0.85rem;
}

.sidebar-brand-mark {
  width: 2.6rem;
  height: 2.6rem;
  border-radius: 0.95rem;
  background: linear-gradient(135deg, #1d4ed8 0%, #3b82f6 100%);
  color: #ffffff;
  display: grid;
  place-items: center;
  font-weight: 800;
  letter-spacing: 0;
  flex: 0 0 auto;
}

.sidebar-brand-copy {
  min-width: 0;
}

.sidebar-brand-title {
  font-size: 0.96rem;
  font-weight: 800;
  color: var(--console-text);
  line-height: 1.15;
}

.sidebar-brand-desc {
  margin-top: 0.18rem;
  color: var(--console-muted);
  font-size: 0.82rem;
  line-height: 1.3;
}

.console-shell-title {
  font-size: 1.85rem;
  line-height: 1.1;
  font-weight: 800;
  letter-spacing: 0;
  color: var(--console-text);
  margin: 0 0 0.35rem 0;
}

.console-shell-meta,
.console-chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin: 0.65rem 0 0.25rem;
}

.console-chip {
  display: inline-flex;
  align-items: center;
  min-height: 2rem;
  padding: 0.28rem 0.7rem;
  border-radius: 999px;
  border: 1px solid var(--console-border);
  background: var(--console-surface-alt);
  color: var(--console-muted);
  font-size: 0.8rem;
  font-weight: 700;
}

.console-chip--blue {
  border-color: #bfdbfe;
  background: var(--console-blue-soft);
  color: var(--console-blue);
}

.console-chip--teal {
  border-color: #99f6e4;
  background: var(--console-teal-soft);
  color: var(--console-teal);
}

.console-chip--amber {
  border-color: #fde68a;
  background: var(--console-amber-soft);
  color: var(--console-amber);
}

.console-section {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  margin: 0.1rem 0 0.35rem;
}

.console-section::before {
  content: "";
  width: 0.4rem;
  height: 1.45rem;
  border-radius: 999px;
  background: var(--console-blue);
}

.console-section--teal::before {
  background: var(--console-teal);
}

.console-section--amber::before {
  background: var(--console-amber);
}

.console-section-title {
  color: var(--console-text);
  font-size: 0.98rem;
  font-weight: 800;
  letter-spacing: 0;
}

.console-step {
  height: 100%;
  border: 1px solid var(--console-border);
  border-radius: 0.95rem;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  padding: 0.95rem 0.95rem 0.85rem;
}

.console-step-number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.8rem;
  height: 1.8rem;
  border-radius: 999px;
  background: var(--console-blue-soft);
  color: var(--console-blue);
  font-weight: 700;
  margin-bottom: 0.65rem;
}

.console-step-title {
  font-size: 0.96rem;
  font-weight: 700;
  color: var(--console-text);
  margin-bottom: 0.25rem;
}

.console-step-copy {
  color: var(--console-muted);
  font-size: 0.86rem;
  line-height: 1.35;
}

.console-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  min-height: 2rem;
  padding: 0.3rem 0.65rem;
  border-radius: 999px;
  border: 1px solid var(--console-border);
  background: var(--console-surface-alt);
  color: var(--console-muted);
  font-size: 0.78rem;
  font-weight: 600;
}

.console-badge--blue {
  border-color: #bfdbfe;
  background: var(--console-blue-soft);
  color: var(--console-blue);
}

.console-badge--teal {
  border-color: #99f6e4;
  background: var(--console-teal-soft);
  color: var(--console-teal);
}

.console-badge--amber {
  border-color: #fde68a;
  background: var(--console-amber-soft);
  color: var(--console-amber);
}

.st-key-workflow-strip {
  padding-top: 0.85rem;
}
</style>
"""
    css = css.replace("__UPLOAD_BTN_TEXT__", upload_btn_text)
    st.markdown(css, unsafe_allow_html=True)


# Per-workflow stage labels: stage 4 (export) is shared, stages 1-3 adapt to the route.
# Each entry: (number, title_key, desc_key, accent). The mapping is resolved at call time
# so it always reflects the currently selected workflow mode.
def _render_step_strip(selected_mode: str) -> None:
    if selected_mode == WORKFLOW_MODE_URL_LLM:
        step_specs = (
            ("1", "stage_url_input_title", "stage_url_input_desc", "blue"),
            ("2", "stage_llm_keywords_title", "stage_llm_keywords_desc", "teal"),
            ("3", "stage_ads_metrics_title", "stage_ads_metrics_desc", "amber"),
            ("4", "stage_export_seo_title", "stage_export_seo_desc", "blue"),
        )
    elif selected_mode == WORKFLOW_MODE_URL_SEED:
        step_specs = (
            ("1", "stage_url_input_title", "stage_url_input_desc", "blue"),
            ("2", "stage_ads_ideas_title", "stage_ads_ideas_desc", "teal"),
            ("3", "stage_select_title", "stage_select_desc", "amber"),
            ("4", "app_stage_4_title", "stage_export_desc", "blue"),
        )
    elif selected_mode == WORKFLOW_MODE_KEYWORD_SEED:
        step_specs = (
            ("1", "stage_keywords_title", "stage_keywords_desc", "blue"),
            ("2", "stage_ads_ideas_title", "stage_ads_ideas_desc", "teal"),
            ("3", "stage_serp_ads_title", "stage_serp_ads_desc", "amber"),
            ("4", "app_stage_4_title", "stage_export_desc", "blue"),
        )
    elif selected_mode == WORKFLOW_MODE_KEYWORD_LLM:
        step_specs = (
            ("1", "stage_keywords_title", "stage_keywords_desc", "blue"),
            ("2", "stage_seo_gen_title", "stage_seo_gen_desc", "teal"),
            ("3", "stage_quality_report_title", "stage_quality_report_desc", "amber"),
            ("4", "stage_export_seo_title", "stage_export_seo_desc", "blue"),
        )
    elif selected_mode == WORKFLOW_MODE_SERP_ANALYSIS:
        step_specs = (
            ("1", "stage_keywords_title", "stage_keywords_desc", "blue"),
            ("2", "stage_collect_serp_title", "stage_collect_serp_desc", "teal"),
            ("3", "stage_serp_review_title", "stage_serp_review_desc", "amber"),
            ("4", "app_stage_4_title", "stage_export_desc", "blue"),
        )
    elif selected_mode == WORKFLOW_MODE_CRAWL_REPORT:
        step_specs = (
            ("1", "stage_url_input_title", "stage_url_input_desc", "blue"),
            ("2", "stage_crawl_title", "stage_crawl_desc", "teal"),
            ("3", "stage_math_report_title", "stage_math_report_desc", "amber"),
            ("4", "app_stage_4_title", "stage_export_desc", "blue"),
        )
    elif selected_mode == WORKFLOW_MODE_TRENDS:
        step_specs = (
            ("1", "stage_keywords_title", "stage_keywords_desc", "blue"),
            ("2", "stage_trends_request_title", "stage_trends_request_desc", "teal"),
            ("3", "stage_trends_analysis_title", "stage_trends_analysis_desc", "amber"),
            ("4", "app_stage_4_title", "stage_export_desc", "blue"),
        )
    else:
        # Fallback to the legacy shared set for any unknown mode.
        step_specs = (
            ("1", "app_step_discover_seeds_title", "app_step_discover_seeds_desc", "blue"),
            ("2", "app_step_score_cluster_title", "app_step_score_cluster_desc", "teal"),
            ("3", "app_step_review_serps_title", "app_step_review_serps_desc", "amber"),
            ("4", "app_step_export_artifacts_title", "app_step_export_artifacts_desc", "blue"),
        )
    with st.container(key="workflow-strip"):
        cols = st.columns(4)
        for col, (number, title_key, desc_key, accent) in zip(cols, step_specs):
            with col:
                st.markdown(
                    f"""
<div class="console-step console-step--{accent}">
  <div class="console-step-number">{number}</div>
  <div class="console-step-title">{html.escape(t(title_key))}</div>
  <div class="console-step-copy">{html.escape(t(desc_key))}</div>
</div>
""",
                    unsafe_allow_html=True,
                )


def _render_app_summary(
    selected_mode: str,
    provider: str,
    model_name: str,
    auto_save_excel: bool,
) -> None:
    workflow_label = _workflow_mode_label(selected_mode)
    auto_save_label = t("ui_enabled") if auto_save_excel else t("ui_disabled")
    st.markdown(
        """
<div class="console-chip-row">
  <span class="console-chip console-chip--blue">""" + html.escape(workflow_label) + """</span>
  <span class="console-chip console-chip--teal">""" + html.escape(provider) + """</span>
  <span class="console-chip console-chip--amber">""" + html.escape(auto_save_label) + """</span>
</div>
""",
        unsafe_allow_html=True,
    )
    summary_cols = st.columns(3)
    with summary_cols[0]:
        metric_card(
            title=t("app_summary_workflow_title"),
            content=workflow_label,
            description=t("app_summary_current_route_desc"),
            key="app_summary_workflow",
        )
    with summary_cols[1]:
        metric_card(
            title=t("app_summary_provider_title"),
            content=provider,
            description=model_name or t("app_summary_model_not_set_desc"),
            key="app_summary_provider",
        )
    with summary_cols[2]:
        metric_card(
            title=t("app_summary_exports_title"),
            content=auto_save_label,
            description=t("app_summary_excel_output_desc"),
            key="app_summary_exports",
        )

WORKFLOW_MODE_URL_LLM = "url_llm"
WORKFLOW_MODE_URL_SEED = "url_seed"
WORKFLOW_MODE_KEYWORD_SEED = "keyword_seed"
WORKFLOW_MODE_KEYWORD_LLM = "keyword_llm"
WORKFLOW_MODE_SERP_ANALYSIS = "serp_analysis"
WORKFLOW_MODE_CRAWL_REPORT = "crawl_report"
WORKFLOW_MODE_TRENDS = "google_trends"
WORKFLOW_MODES = (
    WORKFLOW_MODE_URL_LLM,
    WORKFLOW_MODE_URL_SEED,
    WORKFLOW_MODE_KEYWORD_SEED,
    WORKFLOW_MODE_KEYWORD_LLM,
    WORKFLOW_MODE_SERP_ANALYSIS,
    WORKFLOW_MODE_CRAWL_REPORT,
    WORKFLOW_MODE_TRENDS,
)
WORKFLOW_MODE_WIDGET_KEY = "workflow_mode_widget"
DYNAMIC_STATE_PREFIXES = (
    "kw_",
    "select_all_",
    "use_url_seed::",
    "idea_kw::",
    "idea_seed::",
    "select_all_idea_seed::",
    "llm_extract_",
    "url_llm_ads_serp::",
    "url_seed_ads_serp::",
    "keyword_seed_ads_serp::",
    # Phase 9 dynamic key prefixes (M4 amendment)
    "url_llm_staged::",
    "serp_match::",
    "keyword_select_::",
)
EXACT_STATE_KEYS = (
    "processed_data",
    "execution_logs",
    "scraped_content",
    "generated_seo_texts",
    "keyword_ideas_data",
    "keyword_ideas_signature",
    "keyword_selection_signature",
    "keyword_ideas_use_url_seed",
    "keyword_ideas_flash_message",
    "keywords_excel_saved",
    "seo_excel_saved",
    "selected_keywords",
    "last_history_signature",
    "active_inputs",
    "serp_related_data",
    "serp_results_saved",
    "serp_chained_ads_data",
    "serp_chain_ads_saved",
    "serp_pre_step_results",
    "chained_serp_results",
    "chained_serp_related_data",
    "crawl_result",
    "crawl_math_report",
    "google_trends_result",
    "google_trends_tables",
    "google_trends_chained_ads_data",
    "google_trends_averages_saved",
    "google_trends_interest_saved",
    "google_trends_ads_saved",
    "chained_serp_results_saved",
    "serp_domain_metrics",
    # Phase 9 exact state keys (M4 amendment)
    "serp_match_targets",
    "serp_match_index",
    "url_llm_staged_keywords",
    "last_extraction_run_id",
    "active_source_urls",
    "merged_ads_serp_data",
    "merged_ads_trends_data",
)



# FUNCTION_CONTRACT: _ensure_session_defaults
# Purpose: Initialize root session state values
# Input: None
# Output: None
# Side Effects: Updates st.session_state with default keys if missing
# Business Rules: Enforces stable session keys for all workflows
# Failure Modes: None
# LINKS: requirements.xml#UC-005, development-plan.xml#MOD-001
def _ensure_session_defaults() -> None:
    defaults = {
        "processed_data": None,
        "execution_logs": [],
        "scraped_content": {},
        "generated_seo_texts": None,
        "keyword_ideas_data": None,
        "keyword_ideas_signature": None,
        "keyword_selection_signature": None,
        "keyword_ideas_use_url_seed": {},
        "keyword_ideas_flash_message": None,
        "keywords_excel_saved": False,
        "seo_excel_saved": False,
        "select_all_urls": True,
        "selected_keywords": {},
        "workflow_mode": WORKFLOW_MODE_URL_LLM,
        "active_inputs": [],
        "pending_submission_signature": None,
        "serp_related_data": None,
        "serp_results_saved": False,
        "serp_chained_ads_data": None,
        "serp_chain_ads_saved": False,
        "serp_pre_step_results": None,
        "serp_domain_metrics": None,
        "chained_serp_results": None,
        "chained_serp_related_data": None,
        "crawl_result": None,
        "crawl_math_report": None,
        "google_trends_result": None,
        "google_trends_tables": None,
        "google_trends_chained_ads_data": None,
        "google_trends_averages_saved": False,
        "google_trends_interest_saved": False,
        "google_trends_ads_saved": False,
        "chained_serp_results_saved": False,
        # Phase 9 session state defaults
        "serp_match_targets": None,
        "serp_match_index": None,
        "url_llm_staged_keywords": None,
        "last_extraction_run_id": None,
        "active_source_urls": None,
        # SERP-Ads merge (Phase 16)
        "merged_ads_serp_data": None,
        # Trends-Ads merge
        "merged_ads_trends_data": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value



# FUNCTION_CONTRACT: _reset_run_state
# Purpose: Clear aggregated and dynamic workflow state before a new run
# Input: None
# Output: None
# Side Effects: Modifies st.session_state
# Business Rules: Ensures no state leak between different runs
# Failure Modes: None
# LINKS: development-plan.xml#MOD-001
def _reset_run_state() -> None:
    for key in EXACT_STATE_KEYS:
        if key in st.session_state:
            if key.endswith("_saved"):
                st.session_state[key] = False
            elif key in ("execution_logs", "active_inputs"):
                st.session_state[key] = []
            elif key in ("scraped_content", "keyword_ideas_use_url_seed", "selected_keywords"):
                st.session_state[key] = {}
            else:
                st.session_state[key] = None

    for key in list(st.session_state.keys()):
        if key.startswith(DYNAMIC_STATE_PREFIXES):
            del st.session_state[key]

    for key in ("manual_keyword_input", "manual_kw_url"):
        if key in st.session_state:
            del st.session_state[key]



# FUNCTION_CONTRACT: _normalize_entries
# Purpose: Strip and deduplicate textarea/file inputs while preserving order
# Input: values (List[str]) - raw lines from text area or file
# Output: List[str] - cleaned and deduplicated lines
# Side Effects: None
# Business Rules: Preserves original order; ignores empty lines
# Failure Modes: None
# LINKS: requirements.xml#UC-001
def _normalize_entries(values: List[str]) -> List[str]:

    normalized: List[str] = []
    seen = set()
    for value in values:
        cleaned = str(value).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized



# FUNCTION_CONTRACT: _build_submission_signature
# Purpose: Build a stable signature to suppress duplicate submit reruns
# Input: selected_mode (str), manual_input (str), uploaded_file (Any)
# Output: tuple - stable identifier for the input state
# Side Effects: None
# Business Rules: Prevents redundant workflow execution on UI reruns
# Failure Modes: None
# LINKS: development-plan.xml#MOD-001
def _build_submission_signature(
    selected_mode: str,
    manual_input: str,
    uploaded_file: Any,
) -> tuple[str, str, str, int, str]:
    uploaded_name = getattr(uploaded_file, "name", "") if uploaded_file else ""
    uploaded_size = int(getattr(uploaded_file, "size", 0) or 0) if uploaded_file else 0
    uploaded_type = getattr(uploaded_file, "type", "") if uploaded_file else ""
    return (
        selected_mode,
        str(manual_input or ""),
        str(uploaded_name),
        uploaded_size,
        str(uploaded_type),
    )



# FUNCTION_CONTRACT: _workflow_options
# Purpose: Build localized workflow labels
# Input: None
# Output: Dict[str, str] - mapping of label to mode value
# Side Effects: None
# Business Rules: Uses i18n translations
# Failure Modes: None
# LINKS: technology.xml#DEP-001
def _workflow_options() -> Dict[str, str]:

    return {
        t("workflow_mode_url_llm"): WORKFLOW_MODE_URL_LLM,
        t("workflow_mode_url_seed"): WORKFLOW_MODE_URL_SEED,
        t("workflow_mode_keyword_seed"): WORKFLOW_MODE_KEYWORD_SEED,
        t("workflow_mode_keyword_llm"): WORKFLOW_MODE_KEYWORD_LLM,
        t("serp_mode_label"): WORKFLOW_MODE_SERP_ANALYSIS,
        t("crawl_mode_label"): WORKFLOW_MODE_CRAWL_REPORT,
        t("workflow_mode_trends"): WORKFLOW_MODE_TRENDS,
    }



# FUNCTION_CONTRACT: _workflow_mode_label
# Purpose: Translate a workflow mode value into the current UI label
# Input: mode (str) - internal mode identifier
# Output: str - localized label
# Side Effects: None
# Business Rules: Falls back to mode id if translation missing
# Failure Modes: None
# LINKS: technology.xml#DEP-001
def _workflow_mode_label(mode: str) -> str:

    options = {
        WORKFLOW_MODE_URL_LLM: t("workflow_mode_url_llm"),
        WORKFLOW_MODE_URL_SEED: t("workflow_mode_url_seed"),
        WORKFLOW_MODE_KEYWORD_SEED: t("workflow_mode_keyword_seed"),
        WORKFLOW_MODE_KEYWORD_LLM: t("workflow_mode_keyword_llm"),
        WORKFLOW_MODE_SERP_ANALYSIS: t("serp_mode_label"),
        WORKFLOW_MODE_CRAWL_REPORT: t("crawl_mode_label"),
        WORKFLOW_MODE_TRENDS: t("workflow_mode_trends"),
    }
    return options.get(mode, mode)



# FUNCTION_CONTRACT: _sync_workflow_mode_from_widget
# Purpose: Persist the currently selected workflow mode from the selectbox widget
# Input: None (reads from st.session_state)
# Output: None (updates st.session_state)
# Side Effects: Modifies st.session_state.workflow_mode
# Business Rules: Syncs internal state with UI selection
# Failure Modes: None
# LINKS: development-plan.xml#MOD-001
def _sync_workflow_mode_from_widget() -> None:

    selected_mode = st.session_state.get(
        WORKFLOW_MODE_WIDGET_KEY, WORKFLOW_MODE_URL_LLM
    )
    if selected_mode not in WORKFLOW_MODES:
        selected_mode = WORKFLOW_MODE_URL_LLM
    st.session_state.workflow_mode = selected_mode



# FUNCTION_CONTRACT: _render_input_form
# Purpose: Render the workflow selector and main input form
# Input: None
# Output: tuple (selected_mode, manual_input, uploaded_file, submitted)
# Side Effects: Renders Streamlit widgets
# Business Rules: Handles conditional rendering based on mode
# Failure Modes: None
# LINKS: requirements.xml#UC-001, requirements.xml#UC-002, requirements.xml#UC-003
def _render_input_form() -> tuple[str, str, Any, bool]:

    current_mode = st.session_state.get("workflow_mode", WORKFLOW_MODE_URL_LLM)
    if current_mode not in WORKFLOW_MODES:
        current_mode = WORKFLOW_MODE_URL_LLM

    widget_mode = st.session_state.get(WORKFLOW_MODE_WIDGET_KEY, current_mode)
    if widget_mode not in WORKFLOW_MODES or widget_mode != current_mode:
        widget_mode = current_mode
        if WORKFLOW_MODE_WIDGET_KEY in st.session_state:
            st.session_state[WORKFLOW_MODE_WIDGET_KEY] = widget_mode

    with st.container(key="input-panel"):
        _render_section_header(t("workflow_mode_label"), t("app_workflow_intro"), "blue")
        selectbox_kwargs = {
            "index": WORKFLOW_MODES.index(widget_mode),
        } if WORKFLOW_MODE_WIDGET_KEY not in st.session_state else {}
        selected_mode = st.selectbox(
            t("workflow_mode_label"),
            list(WORKFLOW_MODES),
            key=WORKFLOW_MODE_WIDGET_KEY,
            format_func=_workflow_mode_label,
            on_change=_sync_workflow_mode_from_widget,
            **selectbox_kwargs,
        )
        st.session_state.workflow_mode = selected_mode

        with st.form("analysis_form"):
            if selected_mode == WORKFLOW_MODE_KEYWORD_SEED:
                st.subheader(t("keyword_seed_header"))
                manual_input = st.text_area(
                    t("keyword_seed_placeholder"),
                    height=150,
                )
                uploaded_file = st.file_uploader(t("upload_file"), type=["txt", "csv"])
            elif selected_mode == WORKFLOW_MODE_KEYWORD_LLM:
                st.subheader(t("keyword_llm_input_header"))
                manual_input = st.text_area(
                    t("keyword_llm_input_placeholder"),
                    height=150,
                    help=t("keyword_llm_input_help"),
                )
                uploaded_file = st.file_uploader(t("upload_file"), type=["txt", "csv"])
            elif selected_mode == WORKFLOW_MODE_SERP_ANALYSIS:
                st.subheader(t("serp_keyword_input_header"))
                manual_input = st.text_area(
                    t("serp_keyword_input_placeholder"),
                    height=150,
                )
                uploaded_file = st.file_uploader(t("upload_file"), type=["txt", "csv"])
            elif selected_mode == WORKFLOW_MODE_TRENDS:
                st.subheader(t("google_trends_keyword_input_header"))
                manual_input = st.text_area(
                    t("google_trends_keyword_input_placeholder"),
                    height=150,
                )
                uploaded_file = st.file_uploader(t("upload_file"), type=["txt", "csv"])
            elif selected_mode == WORKFLOW_MODE_CRAWL_REPORT:
                st.subheader(t("crawl_seed_input_header"))
                manual_input = st.text_area(
                    t("crawl_seed_input_placeholder"),
                    height=150,
                )
                uploaded_file = st.file_uploader(t("upload_file"), type=["txt", "csv"])
            else:
                st.subheader(t("enter_url_header"))
                manual_input = st.text_area(t("enter_url_placeholder"), height=150)
                uploaded_file = st.file_uploader(t("upload_file"), type=["txt", "csv"])

            submitted = st.form_submit_button(t("start_analysis"), type="primary")

    return selected_mode, manual_input, uploaded_file, submitted



# FUNCTION_CONTRACT: main
# Purpose: Main entry point for the Streamlit application
# Input: None
# Output: None
# Side Effects: Orchestrates full application lifecycle
# Business Rules: Validates API keys; manages workflow lifecycle; renders results
# Failure Modes: Displays error if file parsing fails
# LINKS: requirements.xml#UC-001, requirements.xml#UC-002, requirements.xml#UC-003, requirements.xml#UC-004, requirements.xml#UC-005
def main() -> None:
    _ensure_session_defaults()

    settings: Dict[str, Any] = render_sidebar()
    logger.close_handlers()
    cleanup_stats = run_startup_cleanup()
    logger.refresh_config()

    if any(cleanup_stats.values()):
        logger.info(
            "Startup cleanup completed: "
            f"outputs={cleanup_stats['outputs_deleted']}, "
            f"api_logs={cleanup_stats['api_logs_deleted']}, "
            f"history_entries={cleanup_stats['history_removed']}"
        )

    if "api_keys_status" not in st.session_state:
        st.session_state.api_keys_status = validate_api_keys()
    api_keys_status: Dict[str, bool] = st.session_state.api_keys_status
    available_count: int = sum(1 for value in api_keys_status.values() if value)
    if available_count == 0:
        st.warning(t("no_api_keys"))

    provider: str = settings["provider"]
    model_name: str = settings["model_name"]
    max_keywords: int = settings["max_keywords"]
    location_id: str = settings["location_id"]
    language_id = settings["language_id"]
    currency_code: str = settings["currency_code"]
    auto_save_excel: bool = settings["auto_save_excel"]
    keyword_prompt: str = settings.get("keyword_prompt", "")
    seo_prompt: str = settings.get("seo_prompt", "")
    api_timeout: int = settings.get("api_timeout", 10)
    api_delay: int = settings.get("api_delay", 2)
    api_retry_count: int = settings.get("api_retry_count", 4)
    api_retry_delay: int = settings.get("api_retry_delay", 4)
    upload_max_file_size_mb: int = settings.get("upload_max_file_size_mb", 5)
    upload_max_rows: int = settings.get("upload_max_rows", 1000)
    crawler_settings: dict = settings.get("crawler_settings", {})
    trends_settings: dict = settings.get("google_trends_settings", {})
    force_refresh: bool = bool(settings.get("cache_force_refresh", False))
    keyword_llm_language: str = settings.get("keyword_llm_generation_language", "Russian")
    page_type: str = settings.get("page_type", "product")

    _inject_console_styles()

    with st.container(key="app-shell"):
        # Pinned header: app title + a single chip for the active workflow mode.
        # Everything else (description, provider/autosave chips, metric cards, 4-stage strip)
        # lives in the collapsible expander below and is hidden by default.
        current_mode = st.session_state.get("workflow_mode", WORKFLOW_MODE_URL_LLM)
        workflow_label = _workflow_mode_label(current_mode)
        header_cols = st.columns([3, 2])
        with header_cols[0]:
            st.markdown(
                f'<div class="console-shell-title">{html.escape(t("app_console_title"))}</div>',
                unsafe_allow_html=True,
            )
        with header_cols[1]:
            st.markdown(
                '<div class="console-chip-row" style="justify-content:flex-end;">'
                f'<span class="console-chip console-chip--blue">{html.escape(workflow_label)}</span>'
                '</div>',
                unsafe_allow_html=True,
            )

        with st.expander(t("app_top_show_details"), expanded=False):
            st.caption(t("app_description"))
            _render_app_summary(
                current_mode,
                provider,
                model_name,
                auto_save_excel,
            )
            _render_step_strip(current_mode)

    # Live SERP settings from sidebar — passed to SERP workflow instead of stale disk config
    serp_settings: dict = {
        "provider": settings.get("serp_provider", "serper_dev"),
        "num_results": settings.get("serp_num_results", 10),
        "gl": settings.get("serp_gl", "ua"),
        "hl": settings.get("serp_hl", "uk"),
        "timeout_seconds": 30,
        "device": settings.get("serp_device", ""),
        "search_type": settings.get("serp_search_type", "web"),
        "time_period": settings.get("serp_time_period", "any"),
        "safe_search": settings.get("serp_safe_search", "off"),
        "google_domain": settings.get("serp_google_domain", "google.com"),
        "location": settings.get("serp_city", ""),
        "uule": settings.get("serp_uule", ""),
    }

    selected_mode, manual_input, uploaded_file, submitted = _render_input_form()

    # SERP pre-step (Path A) is disabled.
    # SERP↔Ads enrichment is handled by the bidirectional Chain buttons (Path B); pre-step path (A) disabled.
    enable_serp_pre_step = False

    if not submitted and st.session_state.get("pending_submission_signature") is not None:
        st.session_state.pending_submission_signature = None

    if submitted:
        submission_signature = _build_submission_signature(
            selected_mode,
            manual_input,
            uploaded_file,
        )
        if st.session_state.get("pending_submission_signature") == submission_signature:
            return

        st.session_state.pending_submission_signature = submission_signature
        _reset_run_state()
        run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        st.session_state.current_run_id = run_id
        st.session_state.workflow_mode = selected_mode

        input_mode = (
            "keyword"
            if selected_mode
            in (
                WORKFLOW_MODE_KEYWORD_SEED,
                WORKFLOW_MODE_KEYWORD_LLM,
                WORKFLOW_MODE_SERP_ANALYSIS,
                WORKFLOW_MODE_TRENDS,
            )
            else "url"
        )
        inputs: List[str] = []
        if manual_input:
            inputs.extend(manual_input.splitlines())
        if uploaded_file:
            try:
                inputs.extend(
                    FileHandler.parse_file(
                        uploaded_file,
                        input_mode=input_mode,
                        max_file_size_mb=upload_max_file_size_mb,
                        max_rows=upload_max_rows,
                    )
                )
            except FileParsingError as exc:
                st.error(t(exc.message_key, **exc.message_kwargs))
                return

        normalized_inputs = _normalize_entries(inputs)
        st.session_state.active_inputs = normalized_inputs

        # SERP pre-step: run SERP analysis before primary workflow (keyword-gated).
        # URL -> LLM always stages extraction first, then lets the user choose SERP or Ads.
        serp_pre_step_results = None
        skip_primary_workflow = False
        if enable_serp_pre_step and normalized_inputs:
            if selected_mode == WORKFLOW_MODE_KEYWORD_SEED:
                serp_pre_step_results = run_serp_analysis_workflow(
                    keywords=normalized_inputs,
                    run_id=run_id,
                    serp_config=serp_settings,
                    force_refresh=force_refresh,
                )
                st.session_state.serp_pre_step_results = serp_pre_step_results
            elif selected_mode == WORKFLOW_MODE_URL_LLM:
                # Phase 9 Task 9: Use staged extraction wrapper with tuple-keyed candidates
                staged_keywords = run_llm_url_keyword_extraction_tupled(
                    urls=normalized_inputs,
                    provider=provider,
                    model=model_name,
                    max_keywords=max_keywords,
                    keyword_prompt=keyword_prompt,
                    api_timeout=api_timeout,
                    api_delay=api_delay,
                    api_retry_count=api_retry_count,
                    api_retry_delay=api_retry_delay,
                    run_id=run_id,
                    force_refresh=force_refresh,
                )
                # Store for backward compatibility with render_keyword_candidate_selector
                selection_prefix = f"llm_extract_{run_id}"
                st.session_state[f"kw_candidates_{selection_prefix}"] = staged_keywords
                st.info(t("keyword_stage_ready"))
                st.session_state.serp_pre_step_results = None
                skip_primary_workflow = True
            elif selected_mode == WORKFLOW_MODE_URL_SEED:
                logger.warning(
                    f"[run {run_id}] [GRACE:block_workflow_keyword_gate:STATE] "
                    "SERP pre-step blocked for URL seed workflow; Ads keyword ideas required"
                    ', beliefState="no_keywords_extracted"'
                )
                st.warning(t("serp_needs_keywords_warning"))
                st.session_state.serp_pre_step_results = None

        if skip_primary_workflow:
            pass
        elif selected_mode == WORKFLOW_MODE_KEYWORD_SEED:
            if not normalized_inputs:
                st.warning(t("keyword_seed_warning"))
            else:
                run_keyword_seed_workflow(
                    seed_keywords=normalized_inputs,
                    location_id=location_id,
                    language_id=language_id,
                    currency_code=currency_code,
                    run_id=run_id,
                    force_refresh=force_refresh,
                )
        elif selected_mode == WORKFLOW_MODE_KEYWORD_LLM:
            if not normalized_inputs:
                st.warning(t("keyword_llm_warning"))
            else:
                run_keyword_to_llm_workflow(
                    keywords=normalized_inputs,
                    provider=provider,
                    model=model_name,
                    language=keyword_llm_language,
                    seo_prompt=seo_prompt,
                    api_timeout=api_timeout,
                    api_delay=api_delay,
                    api_retry_count=api_retry_count,
                    api_retry_delay=api_retry_delay,
                    run_id=run_id,
                    force_refresh=force_refresh,
                    page_type=page_type,
                )
        elif selected_mode == WORKFLOW_MODE_SERP_ANALYSIS:
            if not normalized_inputs:
                st.warning(t("serp_keyword_warning"))
            else:
                run_serp_analysis_workflow(
                    keywords=normalized_inputs,
                    run_id=run_id,
                    serp_config=serp_settings,
                    force_refresh=force_refresh,
                )
        elif selected_mode == WORKFLOW_MODE_TRENDS:
            if not normalized_inputs:
                st.warning(t("google_trends_keyword_warning"))
            else:
                run_google_trends_workflow(
                    keywords=normalized_inputs,
                    trends_config=trends_settings,
                    run_id=run_id,
                    force_refresh=force_refresh,
                )
        elif selected_mode == WORKFLOW_MODE_CRAWL_REPORT:
            if not normalized_inputs:
                st.warning(t("crawl_no_seed_urls"))
            elif not crawler_settings.get("enabled", False):
                st.warning(t("crawl_disabled_warning"))
            else:
                run_crawl_math_report_workflow(
                    seed_urls=normalized_inputs,
                    crawler_settings=crawler_settings,
                    run_id=run_id,
                )
        else:
            if not normalized_inputs:
                st.warning(t("enter_url_warning"))
            elif selected_mode == WORKFLOW_MODE_URL_LLM:
                staged_keywords = run_llm_url_keyword_extraction_tupled(
                    normalized_inputs,
                    provider,
                    model_name,
                    max_keywords,
                    keyword_prompt=keyword_prompt,
                    api_timeout=api_timeout,
                    api_delay=api_delay,
                    api_retry_count=api_retry_count,
                    api_retry_delay=api_retry_delay,
                    run_id=run_id,
                    force_refresh=force_refresh,
                )
                selection_prefix = f"llm_extract_{run_id}"
                st.session_state[f"kw_candidates_{selection_prefix}"] = staged_keywords
                st.session_state.serp_pre_step_results = None
            else:
                run_url_seed_workflow(
                    urls=normalized_inputs,
                    location_id=location_id,
                    language_id=language_id,
                    currency_code=currency_code,
                    run_id=run_id,
                    force_refresh=force_refresh,
                )

    workflow_mode = st.session_state.get("workflow_mode", WORKFLOW_MODE_URL_LLM)

    if workflow_mode == WORKFLOW_MODE_SERP_ANALYSIS:
        render_serp_results(auto_save_excel)
        render_serp_related_searches()
        render_serp_math_report(
            st.session_state.get("processed_data"),
            st.session_state.get("serp_related_data"),
        )
        render_serp_chain_to_ads(
            location_id=location_id,
            language_id=language_id,
            currency_code=currency_code,
            auto_save_excel=auto_save_excel,
            force_refresh=force_refresh,
            trends_config=trends_settings,
        )
        render_serp_chained_ads_results(auto_save_excel)
        render_chained_serp_results()
        render_merged_ads_serp_results()
        render_chained_trends_results()
        render_merged_ads_trends_results()
    elif workflow_mode == WORKFLOW_MODE_CRAWL_REPORT:
        render_crawl_math_report(
            location_id=location_id,
            language_id=language_id,
            currency_code=currency_code,
            trends_config=trends_settings,  # Phase 10 Task 9: Trends stage
        )
        render_merged_ads_serp_results()
        render_chained_trends_results()
        render_merged_ads_trends_results()
    elif workflow_mode == WORKFLOW_MODE_TRENDS:
        render_google_trends_results(
            auto_save_excel=auto_save_excel,
            location_id=location_id,
            language_id=language_id,
            currency_code=currency_code,
            serp_config=serp_settings,
            force_refresh=force_refresh,
            trends_config=trends_settings,  # Phase 10 Task 9: Trends stage
        )
        render_chained_serp_results()
    else:
        render_keyword_results(
            auto_save_excel,
            serp_config=serp_settings,
            force_refresh=force_refresh,
            trends_config=trends_settings,  # Phase 10 Task 9: Trends stage
        )
        render_chained_serp_results()
        # Bidirectional SERP↔Ads merge view (1 Ads row/keyword widened with SERP aggregates).
        # Built by build_and_store_merged_ads_serp() once both processed_data and
        # chained_serp_results exist; no-op render guard handles the absent case.
        render_merged_ads_serp_results()
        # Trends-Ads views: raw averages from the handoff, then the merged Ads+Trends table.
        render_chained_trends_results()
        render_merged_ads_trends_results()
    if workflow_mode not in (
        WORKFLOW_MODE_KEYWORD_SEED,
        WORKFLOW_MODE_KEYWORD_LLM,
        WORKFLOW_MODE_CRAWL_REPORT,
        WORKFLOW_MODE_TRENDS,
    ):
        render_scraping_preview()

    if workflow_mode == WORKFLOW_MODE_URL_LLM:
        run_id = str(st.session_state.get("current_run_id", ""))
        selection_prefix = f"llm_extract_{run_id}"
        candidates = st.session_state.get(f"kw_candidates_{selection_prefix}", [])
        selector_result = render_keyword_candidate_selector_with_sources(
            candidates,
            selection_prefix=selection_prefix,
            title=t("select_keywords_for_serp"),
        )
        if selector_result:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button(t("send_selected_to_serp"), key=f"{selection_prefix}_send_to_serp"):
                    result = run_serp_workflow_with_source_context(
                        selector_result,
                        run_id=run_id,
                        serp_config=serp_settings,
                        force_refresh=force_refresh,
                    )
                    if result is not None:
                        st.success(t("serp_analysis_complete"))
                        st.rerun()
            with col2:
                if st.button(t("send_selected_to_ads"), key=f"{selection_prefix}_send_to_ads"):
                    # Leaving the direct-SEO view; clear it so the Ads -> SEO flow
                    # can take over with the fresh metric-bearing processed_data.
                    st.session_state.pop("seo_context_ready", None)
                    st.session_state.pop("seo_auto_generate", None)
                    result = run_selected_keywords_to_ads_workflow(
                        selector_result,
                        location_id=location_id,
                        language_id=language_id,
                        currency_code=currency_code,
                        api_timeout=api_timeout,
                        api_delay=api_delay,
                        api_retry_count=api_retry_count,
                        api_retry_delay=api_retry_delay,
                        run_id=run_id,
                        force_refresh=force_refresh,
                    )
                    if result is not None:
                        st.success(t("generation_complete"))
                        st.rerun()
            with col3:
                if st.button(t("send_selected_to_trends"), key=f"{selection_prefix}_send_to_trends"):
                    selected_keywords = [keyword for keyword, _ in selector_result]
                    result = run_google_trends_workflow(
                        selected_keywords,
                        trends_config=trends_settings,
                        run_id=run_id,
                        force_refresh=force_refresh,
                    )
                    if result is not None:
                        st.success(t("google_trends_complete"))
                        st.rerun()
            with col4:
                if st.button(t("send_selected_to_seo"), key=f"{selection_prefix}_send_to_seo"):
                    seo_context = prepare_seo_context_from_selection(
                        selector_result, run_id=run_id
                    )
                    if seo_context is not None:
                        st.session_state["seo_context_ready"] = seo_context
                        # Arm immediate generation on the next render so the LLM runs
                        # without an extra inner-button click. Without this, the
                        # handoff only stages context (auto-saving a keywords Excel)
                        # but produces no SEO text.
                        st.session_state["seo_auto_generate"] = True
                        st.rerun()

    # URL_LLM: SEO text generation from the Stage-1 candidate selection, without
    # requiring a prior Ads run. prepare_seo_context_from_selection already built
    # processed_data + selected_kw_by_url; render the generation UI from them.
    if (
        workflow_mode == WORKFLOW_MODE_URL_LLM
        and st.session_state.get("seo_context_ready")
        and st.session_state.processed_data is not None
        and st.session_state.scraped_content
    ):
        selected_kw_by_url, total_selected = st.session_state["seo_context_ready"]
        render_seo_generation(
            provider,
            model_name,
            selected_kw_by_url,
            total_selected,
            seo_prompt=seo_prompt,
            language=keyword_llm_language,
            api_timeout=api_timeout,
            api_delay=api_delay,
            api_retry_count=api_retry_count,
            api_retry_delay=api_retry_delay,
            page_type=page_type,
        )

    if (
        workflow_mode == WORKFLOW_MODE_URL_SEED
        and st.session_state.processed_data is not None
        and not st.session_state.scraped_content
    ):
        if st.button(t("url_seed_start_seo"), help=t("url_seed_start_seo_help")):
            urls_for_seo = (
                st.session_state.processed_data["Source URL"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )
            prepare_urls_for_seo(
                urls_for_seo,
                run_id=st.session_state.get("current_run_id", ""),
            )
            st.rerun()

    if (
        workflow_mode in (WORKFLOW_MODE_URL_LLM, WORKFLOW_MODE_URL_SEED)
        and st.session_state.processed_data is not None
        and st.session_state.scraped_content
        # The direct-SEO path (seo_context_ready) renders its own generation UI
        # above; skip this scraped-content selector path to avoid a double render.
        and not st.session_state.get("seo_context_ready")
    ):
        result = render_keyword_selection()
        if result:
            selected_kw_by_url, total_selected = result
            if workflow_mode == WORKFLOW_MODE_URL_LLM:
                render_keyword_ideas_generation(
                    location_id,
                    language_id,
                    currency_code,
                    selected_kw_by_url,
                    total_selected,
                    force_refresh=force_refresh,
                    trends_config=trends_settings,  # Phase 10 Task 9: Trends stage
                )
            render_seo_generation(
                provider,
                model_name,
                selected_kw_by_url,
                total_selected,
                seo_prompt=seo_prompt,
                language=keyword_llm_language,
                api_timeout=api_timeout,
                api_delay=api_delay,
                api_retry_count=api_retry_count,
                api_retry_delay=api_retry_delay,
                page_type=page_type,
            )

    render_seo_results(auto_save_excel)

    # Keyword LLM regeneration handler — consumes force-regenerate flag for keyword_llm workflow
    # (URL workflows consume the flag inside render_seo_generation above)
    if workflow_mode == WORKFLOW_MODE_KEYWORD_LLM:
        seo_force_regen = bool(st.session_state.pop("seo_force_regenerate", False))
        if seo_force_regen and st.session_state.get("active_inputs"):
            run_id = str(st.session_state.get("current_run_id", ""))
            run_keyword_to_llm_workflow(
                keywords=st.session_state.active_inputs,
                provider=provider,
                model=model_name,
                language=keyword_llm_language,
                seo_prompt=seo_prompt,
                api_timeout=api_timeout,
                api_delay=api_delay,
                api_retry_count=api_retry_count,
                api_retry_delay=api_retry_delay,
                run_id=run_id,
                force_refresh=True,
                page_type=page_type,
            )
            st.success(t("regenerate_seo_success"))
            st.rerun()
        elif seo_force_regen:
            # Flag was set but no active inputs — clear silently
            pass

    render_generated_text_math_report()
    render_history(
        provider,
        model_name,
        max_keywords,
        location_id,
        language_id,
        currency_code,
        keyword_prompt=keyword_prompt,
        api_timeout=api_timeout,
        api_delay=api_delay,
        api_retry_count=api_retry_count,
        api_retry_delay=api_retry_delay,
    )

    # Status / Logs — after History block
    with st.container(key="status-panel"):
        _render_section_header(t("status_header"), t("status_desc"), "orange")
        with st.expander(t("show_logs"), expanded=False):
            if APP_LOG.exists():
                with open(APP_LOG, "r", encoding="utf-8") as log_file:
                    log_lines = log_file.readlines()
                    # Show last 50 lines by default
                    st.code("".join(log_lines[-50:]), language="text")
            else:
                st.info(t("no_logs_yet"))


if __name__ == "__main__":
    main()
