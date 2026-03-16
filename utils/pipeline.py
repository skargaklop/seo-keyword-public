"""
Pipeline helpers for the three workflow modes.
"""

from typing import Dict, List, Optional

import pandas as pd
import streamlit as st

from config.i18n import t
from utils.google_ads_client import GoogleAdsHandler
from utils.keyword_processor import KeywordProcessor
from utils.llm_handler import LLMHandler
from utils.logger import logger
from utils.scraper import WebScraper
from utils.validator import URLValidator

KEYWORD_SEED_SOURCE_URL = "keyword-seed://manual-input"
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


def _format_pipeline_message(key: str, **kwargs: object) -> str:
    """Return a localized pipeline status message."""
    return t(key, **kwargs)


def _empty_results_df(currency_code: str) -> pd.DataFrame:
    """Create an empty DataFrame with the app's stable result columns."""
    data = {column: pd.Series(dtype="object") for column in RESULT_COLUMNS}
    empty_df = pd.DataFrame(data)
    empty_df["CPC Currency"] = pd.Series(dtype="object")
    if currency_code:
        empty_df.loc[:, "CPC Currency"] = currency_code
    return empty_df


def _ensure_result_columns(df: Optional[pd.DataFrame], currency_code: str) -> pd.DataFrame:
    """Normalize Google Ads output to the processed_data schema."""
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


def _merge_base_keywords_with_metrics(
    base_df: pd.DataFrame,
    metrics_df: Optional[pd.DataFrame],
    currency_code: str,
) -> pd.DataFrame:
    """Merge Ads metrics without letting metrics-side Source URL overwrite URL mapping."""
    if metrics_df is None or metrics_df.empty:
        return _ensure_result_columns(base_df, currency_code)

    sanitized_metrics_df = metrics_df.drop(columns=["Source URL"], errors="ignore")
    merged_df = pd.merge(base_df, sanitized_metrics_df, on="Keyword", how="left")
    return _ensure_result_columns(merged_df, currency_code)


def _store_processed_data(
    processed_df: pd.DataFrame,
    scraped_content: Optional[Dict[str, str]] = None,
) -> pd.DataFrame:
    """Persist workflow results into session state."""
    st.session_state.processed_data = processed_df
    st.session_state.scraped_content = scraped_content or {}
    return processed_df


def _render_invalid_url_details(invalid_results: List[object]) -> None:
    """Show skipped invalid URLs in a standard expander."""
    if not invalid_results:
        return

    with st.expander(
        _format_pipeline_message(
            "pipeline_invalid_urls_skipped", count=len(invalid_results)
        )
    ):
        for result in invalid_results:
            st.write(f"{result.url}: {result.error}")


def _normalize_keyword_seed_input(seed_keywords: List[str]) -> List[str]:
    """Normalize manual keyword seeds with strip + stable dedupe only."""
    normalized: List[str] = []
    seen = set()
    for keyword in seed_keywords:
        cleaned = str(keyword).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


def prepare_urls_for_seo(
    urls: List[str],
    run_id: str = "",
) -> Dict[str, str]:
    """Scrape URLs lazily before showing the SEO flow."""
    progress_bar = st.progress(0)
    status_text = st.empty()
    run_prefix = f"[run {run_id}] " if run_id else ""

    status_text.text(_format_pipeline_message("pipeline_validating_urls"))
    valid_urls, invalid_results = URLValidator.validate_urls(urls)
    _render_invalid_url_details(invalid_results)

    if not valid_urls:
        st.error(_format_pipeline_message("pipeline_no_valid_urls"))
        return {}

    status_text.text(_format_pipeline_message("pipeline_scraping_content"))
    scraped_data = WebScraper.scrape_urls(
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


def run_llm_keyword_stage_from_checkpoint(
    scraped_content: Dict[str, str],
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
) -> Optional[pd.DataFrame]:
    """Regenerate keywords from cached scraped content without re-scraping URLs."""
    progress_bar = st.progress(0)
    status_text = st.empty()
    run_prefix = f"[run {run_id}] " if run_id else ""

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

    source_keywords: Dict[str, List[str]] = {}
    scraped_items = list(scraped_content.items())
    total_scraped = len(scraped_items)

    for index, (url, text) in enumerate(scraped_items):
        progress_bar.progress(
            index / total_scraped,
            text=_format_pipeline_message(
                "pipeline_analyzing_url",
                idx=index + 1,
                total=total_scraped,
                url=url,
            ),
        )
        keywords = llm.generate_keywords(
            text=text,
            provider=provider,
            model=model,
            max_keywords=max_keywords,
            custom_prompt=keyword_prompt,
        )
        if keywords:
            source_keywords[url] = keywords

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

    if not all_keywords:
        st.warning(_format_pipeline_message("pipeline_no_keywords_found"))
        progress_bar.progress(1.0)
        return None

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
    ads_handler = GoogleAdsHandler(
        location_id=location_id,
        language_id=language_id,
        target_currency_code=currency_code,
    )
    metrics_df = ads_handler.get_keyword_metrics(all_keywords)

    status_text.text(_format_pipeline_message("pipeline_finalizing_report"))
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
    logger.info(
        f"{run_prefix}Checkpoint keyword regeneration completed for {len(scraped_content)} URL(s)"
    )
    return merged_df


def run_url_seed_workflow(
    urls: List[str],
    location_id: str,
    language_id: str,
    currency_code: str,
    run_id: str = "",
) -> Optional[pd.DataFrame]:
    """Generate keyword ideas directly from URL seeds."""
    progress_bar = st.progress(0)
    status_text = st.empty()
    run_prefix = f"[run {run_id}] " if run_id else ""

    status_text.text(_format_pipeline_message("pipeline_validating_urls"))
    valid_urls, invalid_results = URLValidator.validate_urls(urls)
    _render_invalid_url_details(invalid_results)

    if not valid_urls:
        st.error(_format_pipeline_message("pipeline_no_valid_urls"))
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
        ideas_df = ads_handler.get_keyword_ideas(
            [],
            page_url=url,
            source_url=url,
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


def run_keyword_seed_workflow(
    seed_keywords: List[str],
    location_id: str,
    language_id: str,
    currency_code: str,
    run_id: str = "",
) -> Optional[pd.DataFrame]:
    """Generate keyword ideas from manual keyword seeds."""
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
        ads_handler.get_keyword_ideas(
            normalized_keywords,
            source_url=KEYWORD_SEED_SOURCE_URL,
        ),
        currency_code,
    )
    processed_df = processed_df.drop_duplicates(
        subset=["Source URL", "Keyword"], keep="first"
    ).reset_index(drop=True)

    progress_bar.progress(1.0, text=_format_pipeline_message("pipeline_done"))
    status_text.success(_format_pipeline_message("pipeline_analysis_complete"))
    logger.info(
        f"{run_prefix}Keyword seed workflow completed for {len(normalized_keywords)} seed keyword(s)"
    )
    return _store_processed_data(processed_df, scraped_content={})


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
) -> Optional[pd.DataFrame]:
    """
    Main URL -> scrape -> LLM -> Google Ads workflow.
    """
    progress_bar = st.progress(0)
    status_text = st.empty()
    run_prefix = f"[run {run_id}] " if run_id else ""
    logger.info(f"{run_prefix}Starting analysis for {len(urls)} URL(s)")

    status_text.text(_format_pipeline_message("pipeline_validating_urls"))
    valid_urls, invalid_results = URLValidator.validate_urls(urls)
    _render_invalid_url_details(invalid_results)

    if not valid_urls:
        st.error(_format_pipeline_message("pipeline_no_valid_urls"))
        return None

    status_text.text(_format_pipeline_message("pipeline_scraping_content"))
    scraped_data = WebScraper.scrape_urls(
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
    source_keywords: Dict[str, List[str]] = {}
    total_scraped = len(scraped_data)

    for index, item in enumerate(scraped_data):
        progress_bar.progress(
            0.4 + ((index / total_scraped) * 0.3),
            text=_format_pipeline_message(
                "pipeline_analyzing_url",
                idx=index + 1,
                total=total_scraped,
                url=item.url,
            ),
        )
        if not item.success:
            logger.warning(f"{run_prefix}Skipping LLM for failed scrape: {item.url}")
            continue

        keywords = llm.generate_keywords(
            text=item.text,
            provider=provider,
            model=model,
            max_keywords=max_keywords,
            custom_prompt=keyword_prompt,
        )
        if keywords:
            source_keywords[item.url] = keywords
            logger.info(
                f"{run_prefix}Extracted {len(keywords)} keywords from {item.url}"
            )

    status_text.text(_format_pipeline_message("pipeline_processing_deduplicating"))
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

    if not all_keywords:
        st.warning(_format_pipeline_message("pipeline_no_keywords_found"))
        progress_bar.progress(1.0)
        return None

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
    ads_handler = GoogleAdsHandler(
        location_id=location_id,
        language_id=language_id,
        target_currency_code=currency_code,
    )
    metrics_df = ads_handler.get_keyword_metrics(all_keywords)

    status_text.text(_format_pipeline_message("pipeline_finalizing_report"))
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
    logger.info(f"{run_prefix}Analysis run completed successfully")
    return merged_df


def process_flow(
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
) -> Optional[pd.DataFrame]:
    """Backward-compatible alias for the legacy default workflow."""
    return run_llm_url_workflow(
        urls=urls,
        provider=provider,
        model=model,
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
