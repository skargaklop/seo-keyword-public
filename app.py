"""
Auto SEO Keyword Planner - main Streamlit application.
"""

from datetime import datetime
from typing import Any, Dict, List

import streamlit as st

from components.results import (
    render_history,
    render_keyword_ideas_generation,
    render_keyword_results,
    render_keyword_selection,
    render_scraping_preview,
    render_seo_generation,
    render_seo_results,
)
from components.sidebar import render_sidebar
from config.i18n import t
from utils.cleanup import run_startup_cleanup
from utils.file_handler import FileHandler, FileParsingError
from utils.logger import APP_LOG, logger
from utils.pipeline import (
    run_keyword_seed_workflow,
    run_llm_url_workflow,
    run_url_seed_workflow,
    prepare_urls_for_seo,
)
from utils.validator import validate_api_keys

st.set_page_config(page_title="Auto SEO Keyword Planner", page_icon=":rocket:", layout="wide")

WORKFLOW_MODE_URL_LLM = "url_llm"
WORKFLOW_MODE_URL_SEED = "url_seed"
WORKFLOW_MODE_KEYWORD_SEED = "keyword_seed"
WORKFLOW_MODES = (
    WORKFLOW_MODE_URL_LLM,
    WORKFLOW_MODE_URL_SEED,
    WORKFLOW_MODE_KEYWORD_SEED,
)
WORKFLOW_MODE_WIDGET_KEY = "workflow_mode_widget"
DYNAMIC_STATE_PREFIXES = (
    "kw_",
    "select_all_",
    "use_url_seed::",
    "idea_kw::",
    "idea_seed::",
    "select_all_idea_seed::",
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
)


def _ensure_session_defaults() -> None:
    """Initialize root session state values."""
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
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _reset_run_state() -> None:
    """Clear aggregated and dynamic workflow state before a new run."""
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


def _normalize_entries(values: List[str]) -> List[str]:
    """Strip and deduplicate textarea/file inputs while preserving order."""
    normalized: List[str] = []
    seen = set()
    for value in values:
        cleaned = str(value).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


def _build_submission_signature(
    selected_mode: str,
    manual_input: str,
    uploaded_file: Any,
) -> tuple[str, str, str, int, str]:
    """Build a stable signature to suppress duplicate submit reruns."""
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


def _workflow_options() -> Dict[str, str]:
    """Build localized workflow labels."""
    return {
        t("workflow_mode_url_llm"): WORKFLOW_MODE_URL_LLM,
        t("workflow_mode_url_seed"): WORKFLOW_MODE_URL_SEED,
        t("workflow_mode_keyword_seed"): WORKFLOW_MODE_KEYWORD_SEED,
    }


def _workflow_mode_label(mode: str) -> str:
    """Translate a workflow mode value into the current UI label."""
    options = {
        WORKFLOW_MODE_URL_LLM: t("workflow_mode_url_llm"),
        WORKFLOW_MODE_URL_SEED: t("workflow_mode_url_seed"),
        WORKFLOW_MODE_KEYWORD_SEED: t("workflow_mode_keyword_seed"),
    }
    return options.get(mode, mode)


def _sync_workflow_mode_from_widget() -> None:
    """Persist the currently selected workflow mode from the selectbox widget."""
    selected_mode = st.session_state.get(
        WORKFLOW_MODE_WIDGET_KEY, WORKFLOW_MODE_URL_LLM
    )
    if selected_mode not in WORKFLOW_MODES:
        selected_mode = WORKFLOW_MODE_URL_LLM
    st.session_state.workflow_mode = selected_mode


def _render_input_form() -> tuple[str, str, Any, bool]:
    """Render the workflow selector and main input form."""
    current_mode = st.session_state.get("workflow_mode", WORKFLOW_MODE_URL_LLM)
    if current_mode not in WORKFLOW_MODES:
        current_mode = WORKFLOW_MODE_URL_LLM

    widget_mode = st.session_state.get(WORKFLOW_MODE_WIDGET_KEY, current_mode)
    if widget_mode not in WORKFLOW_MODES or widget_mode != current_mode:
        widget_mode = current_mode
        if WORKFLOW_MODE_WIDGET_KEY in st.session_state:
            st.session_state[WORKFLOW_MODE_WIDGET_KEY] = widget_mode

    col1, col2 = st.columns([2, 1])
    with col1:
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
        with col1:
            if selected_mode == WORKFLOW_MODE_KEYWORD_SEED:
                st.subheader(t("keyword_seed_header"))
                manual_input = st.text_area(
                    t("keyword_seed_placeholder"),
                    height=150,
                )
                uploaded_file = st.file_uploader(t("upload_file"), type=["txt", "csv"])
            else:
                st.subheader(t("enter_url_header"))
                manual_input = st.text_area(t("enter_url_placeholder"), height=150)
                uploaded_file = st.file_uploader(t("upload_file"), type=["txt", "csv"])

        with col2:
            st.subheader(t("status_header"))
            show_logs = st.checkbox(t("show_logs"))
            if show_logs and APP_LOG.exists():
                with open(APP_LOG, "r", encoding="utf-8") as log_file:
                    st.code("".join(log_file.readlines()[-20:]), language="text")

        submitted = st.form_submit_button(t("start_analysis"), type="primary")

    return selected_mode, manual_input, uploaded_file, submitted


def main() -> None:
    _ensure_session_defaults()
    settings: Dict[str, Any] = render_sidebar()
    logger.close_handlers()
    cleanup_stats = run_startup_cleanup()
    logger.refresh_config()

    st.title(t("app_title"))
    st.markdown(t("app_description"))
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

    selected_mode, manual_input, uploaded_file, submitted = _render_input_form()

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

        input_mode = "keyword" if selected_mode == WORKFLOW_MODE_KEYWORD_SEED else "url"
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

        if selected_mode == WORKFLOW_MODE_KEYWORD_SEED:
            if not normalized_inputs:
                st.warning(t("keyword_seed_warning"))
            else:
                run_keyword_seed_workflow(
                    seed_keywords=normalized_inputs,
                    location_id=location_id,
                    language_id=language_id,
                    currency_code=currency_code,
                    run_id=run_id,
                )
        else:
            if not normalized_inputs:
                st.warning(t("enter_url_warning"))
            elif selected_mode == WORKFLOW_MODE_URL_LLM:
                run_llm_url_workflow(
                    normalized_inputs,
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
                    run_id=run_id,
                )
            else:
                run_url_seed_workflow(
                    urls=normalized_inputs,
                    location_id=location_id,
                    language_id=language_id,
                    currency_code=currency_code,
                    run_id=run_id,
                )

    render_keyword_results(auto_save_excel)

    workflow_mode = st.session_state.get("workflow_mode", WORKFLOW_MODE_URL_LLM)
    if workflow_mode != WORKFLOW_MODE_KEYWORD_SEED:
        render_scraping_preview()

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
                )
            render_seo_generation(
                provider,
                model_name,
                selected_kw_by_url,
                total_selected,
                seo_prompt=seo_prompt,
                api_timeout=api_timeout,
                api_delay=api_delay,
                api_retry_count=api_retry_count,
                api_retry_delay=api_retry_delay,
            )

    render_seo_results(auto_save_excel)
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


if __name__ == "__main__":
    main()
