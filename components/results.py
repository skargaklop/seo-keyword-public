"""
Results display UI component - keyword results, keyword selection,
SEO text generation, and export buttons.
"""

import io
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Project root directory for resolving relative paths
_BASE_DIR = Path(__file__).parent.parent

import pandas as pd
import streamlit as st

from config.settings import LLM_CONFIG
from config.i18n import t
from utils.logger import logger
from utils.llm_handler import LLMHandler
from utils.excel_exporter import ExcelExporter
from utils.history import HistoryManager
from utils.google_ads_client import GoogleAdsHandler
from utils.pipeline import (
    KEYWORD_SEED_SOURCE_URL,
    run_llm_keyword_stage_from_checkpoint,
)


def _build_history_signature(
    run_id: str, urls: List[str], keywords: List[str]
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """Build a run-aware signature to suppress only same-run rerun duplicates."""
    return (run_id or "", tuple(urls), tuple(keywords))


def format_source_label(source_url: str) -> str:
    """Map synthetic internal sources to UI-friendly labels."""
    if source_url == KEYWORD_SEED_SOURCE_URL:
        return t("keyword_seed_source_label")
    return source_url


def build_history_metadata(workflow_mode: str) -> Dict[str, str]:
    """Build minimal metadata for history entries across workflow modes."""
    seed_strategy_by_mode = {
        "url_llm": "llm_keywords",
        "url_seed": "url_seed",
        "keyword_seed": "keyword_seed",
    }
    return {
        "workflow_mode": workflow_mode,
        "seed_strategy": seed_strategy_by_mode.get(workflow_mode, workflow_mode),
    }


def _display_results_df(df: pd.DataFrame) -> pd.DataFrame:
    """Prepare a UI-only copy of results with friendly source labels."""
    display_df = df.copy()
    if "Source URL" in display_df.columns:
        display_df["Source URL"] = display_df["Source URL"].map(format_source_label)
    return display_df


def build_keyword_ideas_display_df(df: pd.DataFrame) -> pd.DataFrame:
    """Render Keyword Planner ideas with the same metric columns as analysis results."""
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


def build_keyword_idea_seed_key(url: str, keyword: str) -> str:
    """Return the session-state key for one Keyword Planner seed checkbox."""
    return f"idea_seed::{url}::{keyword}"


def set_keyword_idea_seed_selection(
    url: str,
    keywords: List[str],
    selected: bool,
) -> None:
    """Apply bulk selection state for all Keyword Planner seed checkboxes of one URL."""
    for keyword in keywords:
        st.session_state[build_keyword_idea_seed_key(url, keyword)] = selected


def get_selected_keyword_idea_seed_keywords(
    url: str,
    keywords: List[str],
) -> List[str]:
    """Collect checked keyword seeds for one URL, defaulting to all selected."""
    selected_keywords: List[str] = []
    for keyword in keywords:
        seed_key = build_keyword_idea_seed_key(url, keyword)
        if seed_key not in st.session_state:
            st.session_state[seed_key] = True
        if st.session_state.get(seed_key, True):
            selected_keywords.append(keyword)
    return selected_keywords


def limit_keyword_idea_seed_keywords(
    keywords: List[str],
    max_keywords: int = 20,
) -> List[str]:
    """Respect Google Ads keyword_seed limit while preserving the current order."""
    return list(keywords[:max_keywords])


def _display_history_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare a UI-only copy of a history entry."""
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


def build_history_entry_title(entry: Dict[str, Any]) -> str:
    """Build a compact human-readable title for one history item."""
    return (
        f"{entry.get('timestamp', 'N/A')} - {entry.get('url_count', 0)} URL, "
        f"{entry.get('keyword_count', 0)} {t('keywords_count')}"
    )


def _build_history_checkpoint(df: pd.DataFrame, workflow_mode: str) -> Dict[str, Any]:
    """Capture enough state to resume or regenerate without re-scraping."""
    scraped_content = st.session_state.get("scraped_content") or {}
    active_inputs = (
        st.session_state.get("active_inputs") or df["Source URL"].unique().tolist()
    )
    return {
        "workflow_mode": workflow_mode,
        "active_inputs": list(active_inputs),
        "scraped_content": dict(scraped_content),
        "processed_data": json.loads(df.to_json(orient="records")),
    }


def restore_history_checkpoint(entry: Dict[str, Any]) -> bool:
    """Restore a saved history checkpoint into session state."""
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


def build_keyword_ideas_signature(
    selected_kw_by_url: Dict[str, List[str]],
    use_url_seed_by_url: Dict[str, bool],
) -> tuple[tuple[str, tuple[str, ...], bool], ...]:
    """Build a deterministic signature for invalidating stale keyword ideas."""
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


def merge_keyword_ideas_into_processed_data(
    processed_df: pd.DataFrame,
    keyword_ideas_df: pd.DataFrame,
) -> pd.DataFrame:
    """Append selected keyword ideas without duplicating the same URL/keyword pair."""
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


def deduplicate_processed_data(
    processed_df: Optional[pd.DataFrame],
) -> Optional[pd.DataFrame]:
    """Remove duplicate URL/keyword pairs while preserving the first row."""
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


def append_manual_keyword(
    processed_df: Optional[pd.DataFrame],
    target_url: str,
    keyword: str,
) -> tuple[pd.DataFrame, bool]:
    """Append a manual keyword only when the URL/keyword pair does not already exist."""
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


def build_keyword_selection_signature(
    processed_df: Optional[pd.DataFrame],
) -> tuple[str, tuple[tuple[str, tuple[str, ...]], ...]]:
    """Build a run-aware signature so new result sets do not inherit stale checkbox state."""
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


def _clear_keyword_ideas_state() -> None:
    st.session_state.keyword_ideas_data = None
    st.session_state.keyword_ideas_signature = None


def _get_use_url_seed_flags(urls: List[str]) -> Dict[str, bool]:
    flags: Dict[str, bool] = {}
    for url in urls:
        session_key = f"use_url_seed::{url}"
        if session_key not in st.session_state:
            st.session_state[session_key] = False
        flags[url] = bool(st.session_state.get(session_key, False))
    st.session_state.keyword_ideas_use_url_seed = flags
    return flags


def render_keyword_results(auto_save_excel: bool) -> None:
    """Render keyword analysis results with export options."""
    if st.session_state.processed_data is None:
        return

    st.divider()
    st.subheader(t("results_header"))

    utils_col1, utils_col2 = st.columns([3, 1])
    df: pd.DataFrame = st.session_state.processed_data
    display_df = _display_results_df(df)

    with utils_col1:
        st.dataframe(display_df, width="stretch")

    with utils_col2:
        if auto_save_excel and not st.session_state.keywords_excel_saved:
            timestamp: str = datetime.now().strftime("%Y%m%d-%H%M%S")
            filename: str = f"keywords_export_{timestamp}.xlsx"
            output_path: Path = _BASE_DIR / "outputs" / filename
            output_path.parent.mkdir(exist_ok=True)

            if ExcelExporter.export(df, str(output_path)):
                st.session_state.keywords_excel_saved = True
                logger.info(f"Keywords auto-saved: {output_path}")
            else:
                st.error(t("autosave_error"))

        try:
            buffer: io.BytesIO = io.BytesIO()
            ExcelExporter.export_to_buffer(df, buffer)
            st.download_button(
                label=t("download_excel"),
                data=buffer.getvalue(),
                file_name=f"keywords_export_{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as e:
            st.error(f"{t('export_error')}: {e}")

        try:
            csv_data: bytes = ExcelExporter.export_csv_to_bytes(df)
            st.download_button(
                label=t("download_csv"),
                data=csv_data,
                file_name=f"keywords_export_{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv",
                mime="text/csv",
                key="download_keywords_csv",
            )
        except Exception as e:
            st.error(f"{t('csv_error')}: {e}")

    st.info(
        t(
            "total_keywords_stat",
            count=len(df),
            sources=display_df["Source URL"].nunique(),
        )
    )
    _save_to_history(df)


def render_scraping_preview() -> None:
    """Show scraped content preview before keyword generation."""
    if (
        "scraped_content" not in st.session_state
        or not st.session_state.scraped_content
    ):
        return

    st.divider()
    st.subheader(t("scraping_preview"))

    for url, content in st.session_state.scraped_content.items():
        with st.expander(f"{url} ({len(content)} {t('chars')})"):
            st.code(content, language=None, wrap_lines=True)


def render_keyword_selection() -> None:
    """Render keyword selection UI for SEO text generation."""
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

    st.divider()
    st.subheader(t("keyword_selection_header"))

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

    def _on_select_all_change(url: str, keywords: List[str]) -> None:
        select_all_key = f"select_all_{url}"
        new_value = st.session_state[select_all_key]
        for kw in keywords:
            st.session_state[f"kw_{url}_{kw}"] = new_value

    for url in unique_urls:
        url_keywords: List[str] = df[df["Source URL"] == url]["Keyword"].tolist()

        with st.expander(
            f"{url} ({len(url_keywords)} {t('keywords_count')})", expanded=False
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


def render_keyword_ideas_generation(
    location_id: str,
    language_id: Any,
    currency_code: str,
    selected_kw_by_url: Dict[str, List[str]],
    total_selected: int,
) -> None:
    """Render optional keyword idea generation step before SEO text generation."""
    st.divider()
    st.subheader(t("keyword_ideas_header"))
    st.write(t("keyword_ideas_desc"))

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

    def _on_seed_select_all_change(url: str, keywords: List[str]) -> None:
        select_all_key = f"select_all_idea_seed::{url}"
        set_keyword_idea_seed_selection(
            url,
            keywords,
            selected=bool(st.session_state.get(select_all_key, False)),
        )

    for url in selected_urls:
        with st.expander(url, expanded=False):
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
            f"{url} ({len(url_df)} {t('keywords_count')})", expanded=False
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


def render_seo_generation(
    provider: str,
    model_name: str,
    selected_kw_by_url: Dict[str, List[str]],
    total_selected: int,
    seo_prompt: str = "",
    api_timeout: Optional[int] = None,
    api_delay: Optional[int] = None,
    api_retry_count: Optional[int] = None,
    api_retry_delay: Optional[int] = None,
) -> None:
    """Render SEO text generation section with per-URL progress."""
    df: pd.DataFrame = st.session_state.processed_data

    st.divider()
    st.subheader(t("seo_generation_header"))

    if st.button(
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

            gen_lang: str = LLM_CONFIG.get("generation_language", "Russian")

            seo_text: str = llm_gen.generate_seo_text(
                text=content,
                keywords=keywords_payload,
                provider=provider,
                model=model_name,
                language=gen_lang,
                custom_prompt=seo_prompt,
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
        st.success(t("seo_success"))
        st.rerun()


def render_seo_results(auto_save_excel: bool) -> None:
    """Render generated SEO text results with export options."""
    if st.session_state.generated_seo_texts is None:
        return

    st.divider()
    st.subheader(t("seo_results_header"))

    gen_col1, gen_col2 = st.columns([3, 1])
    gen_df: pd.DataFrame = st.session_state.generated_seo_texts

    gen_df_export: pd.DataFrame = gen_df.copy()
    gen_df_export["Page Content"] = gen_df_export["URL"].map(
        lambda u: st.session_state.scraped_content.get(u, "")
    )

    with gen_col1:
        st.dataframe(gen_df, width="stretch")

    with gen_col2:
        if auto_save_excel and not st.session_state.seo_excel_saved:
            timestamp_gen: str = datetime.now().strftime("%Y%m%d-%H%M%S")
            filename_gen: str = f"seo_texts_export_{timestamp_gen}.xlsx"
            output_path_gen: Path = _BASE_DIR / "outputs" / filename_gen
            output_path_gen.parent.mkdir(exist_ok=True)

            try:
                if ExcelExporter.export(gen_df_export, str(output_path_gen)):
                    st.session_state.seo_excel_saved = True
                    logger.info(f"SEO texts auto-saved: {output_path_gen}")
            except Exception as e:
                st.error(f"{t('seo_autosave_error')}: {e}")

        try:
            buffer_gen: io.BytesIO = io.BytesIO()
            ExcelExporter.export_to_buffer(gen_df_export, buffer_gen)
            st.download_button(
                label=t("download_texts_excel"),
                data=buffer_gen.getvalue(),
                file_name=f"seo_texts_export_{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_seo_texts",
            )
        except Exception as e:
            st.error(f"{t('export_error_generic')}: {e}")

        try:
            csv_data: bytes = ExcelExporter.export_csv_to_bytes(gen_df_export)
            st.download_button(
                label=t("download_texts_csv"),
                data=csv_data,
                file_name=f"seo_texts_export_{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv",
                mime="text/csv",
                key="download_seo_texts_csv",
            )
        except Exception as e:
            st.error(f"{t('csv_export_error')}: {e}")


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
    """Render query history section."""
    st.divider()
    st.subheader(t("history_header"))
    flash_message = st.session_state.pop("history_flash_message", None)
    if flash_message:
        st.success(flash_message)

    history = HistoryManager.load_history()
    if not history:
        st.info(t("history_empty"))
        return

    for entry in reversed(history[-10:]):
        display_entry = _display_history_entry(entry)
        with st.expander(build_history_entry_title(entry)):
            checkpoint = (
                entry.get("checkpoint")
                if isinstance(entry.get("checkpoint"), dict)
                else None
            )
            action_col1, action_col2 = st.columns(2)

            with action_col1:
                if checkpoint and st.button(
                    t("history_restore_checkpoint"),
                    key=f"history-restore::{entry.get('timestamp', 'na')}",
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
                if can_regenerate and st.button(
                    t("history_regenerate_keywords"),
                    key=f"history-regenerate::{entry.get('timestamp', 'na')}",
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

            st.json(display_entry)


def _save_to_history(df: pd.DataFrame) -> None:
    """Save current analysis to history."""
    try:
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
