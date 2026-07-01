# MODULE_CONTRACT: cli.pipeline
# Purpose: Headless stage orchestration for seos-cli. Calls the 7 streamlit-free utils/ stage
#   callables in order and threads a pd.DataFrame through to the merge step. NEVER imports
#   streamlit, utils.pipeline, or config.i18n.
# Rationale: docs/cli-plan.md §3 + §7 Phase B. The Streamlit-coupled workflow wrappers in
#   utils/pipeline.py (st.progress/st.session_state) cannot run headlessly, so the CLI orchestrates
#   by calling the underlying utils/ stage functions directly. Self-contained progress is printed.
# Dependencies:
#   WHITELIST, enforced by test_cli_independence.py.
#   utils.validator, utils.scraper, utils.llm_handler, utils.google_ads_client,
#   utils.serp_client, utils.google_trends_client, utils.excel_exporter, config.settings,
#   utils.logger. NEVER streamlit, utils.pipeline, config.i18n.
# Exports: EnrichmentConfig, EnrichmentResult, run_enrichment, SERPSearchResult,
#   collect_serp_rows, trends_result_to_averages_df.
# LINKS: knowledge-graph.xml#MOD-032, verification-plan.xml#V-18-PIPELINE, docs/cli-plan.md §3
# MODULE_MAP: cli/pipeline.py
# Public Functions: run_enrichment, collect_serp_rows, trends_result_to_averages_df,
#   build_input_keywords.
# Private Helpers: _normalize_keywords, _run_stage_x helpers.
# Key Semantic Blocks: block_pipeline_validate_scrape, block_pipeline_enrich_merge_export.
# Critical Flows: validate -> scrape -> llm-extract -> ads -> serp -> trends -> seo-text -> merge
#   -> export.
# Verification: verification-plan.xml#V-18-PIPELINE
# CHANGE_SUMMARY: Phase B — headless orchestrator with EnrichmentConfig/run_enrichment; imports only
#   the 7 clean utils modules; merge delegated to cli.merge (streamlit-free copy); SERP row
#   collection + trends averages extraction reproduced here (the utils.pipeline versions are banned).
#   Stage callables routed through a _StageBindings dataclass so tests inject plain fakes via the
#   `_inject_stages` hook (subprocess-isolated) instead of unittest.mock.patch.
#   Phase C2 — CheckpointStore wired in: the paid 'ads' stage is checkpointed so --resume skips it
#   (input-hash stale-guard re-runs on changed inputs); --clean wipes the workdir before a run.
#   Bugfix (end-to-end smoke) — SEO text payload now built from ads_df rows as
#   [{'Keyword':...,'Avg Monthly Searches':...}] (capital 'Keyword'), matching the
#   LLMHandler.generate_seo_text + app keywords_payload contract (was a lowercase-dict KeyError).

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from utils.excel_exporter import ExcelExporter
from utils.google_ads_client import GoogleAdsHandler
from utils.google_trends_client import (
    GoogleTrendsClient,
    GoogleTrendsResult,
    TrendsOrchestrator,
)
from utils.llm_handler import LLMHandler
from utils.logger import logger
from utils.scraper import ScrapedContent, WebScraper
from utils.serp_client import SERPSearchResult, create_serp_client
from utils.validator import URLValidator

from cli.merge import merge_enrichment
from cli.output import write_report
from cli.checkpoint import CheckpointStore


# ---------------------------------------------------------------------------
# Configuration dataclass
# ---------------------------------------------------------------------------

ALL_STEPS: tuple[str, ...] = (
    "validate",
    "scrape",
    "llm-extract",
    "ads",
    "serp",
    "trends",
    "seo-text",
    "merge",
    "export",
)


@dataclass
# Inputs/options for a single `seos-cli run` enrichment invocation.
class EnrichmentConfig:

    keywords: List[str] = field(default_factory=list)
    urls: List[str] = field(default_factory=list)
    language: str = "en"
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    serp_provider: Optional[str] = None
    out: str = "report.xlsx"
    fmt: str = "xlsx"
    max_keywords: Optional[int] = None
    steps: Optional[List[str]] = None  # None == all applicable
    # Google Ads context (optional overrides; defaults read from settings.yaml)
    ads_location_id: Optional[str] = None
    ads_language_id: Optional[str] = None
    ads_currency_code: Optional[str] = None
    # LLM tuning (optional)
    seo_page_type: str = "product"
    custom_prompt: str = ""
    # Checkpoint / resume (Phase C2) — passed through to the checkpoint store.
    workdir: str = ".seos"
    resume: Optional[str] = None  # run id to resume (or "last")
    clean: bool = False


@dataclass
# Outcome of run_enrichment — the merged DataFrame plus per-stage artifacts.
class EnrichmentResult:

    merged: Optional[pd.DataFrame]
    keywords: List[str] = field(default_factory=list)
    serp_df: Optional[pd.DataFrame] = None
    trends_df: Optional[pd.DataFrame] = None
    seo_text: str = ""
    out_path: Optional[str] = None
    export_failed: bool = False


# ---------------------------------------------------------------------------
# Pure helpers (reproduced from utils/pipeline.py because importing it is banned)
# ---------------------------------------------------------------------------

# Lowercase-stripped, de-duplicated keyword list (drops empties).
def _normalize_keywords(values: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for v in values:
        if v is None:
            continue
        kw = str(v).strip().strip('"').strip("'").strip()
        if not kw:
            continue
        key = kw.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(kw)
    return out


# Build the SERP table (Keyword/Position/URL/Displayed Link/...) from search results.
#
# Mirrors the row schema of utils/pipeline.py _collect_serp_rows (line ~1611) — the schema the
# merge logic consumes — reproduced here without importing the banned module.
def collect_serp_rows(results: List[SERPSearchResult]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for result in results:
        if not result.success:
            continue
        for item in result.organic:
            rows.append(
                {
                    "Keyword": result.keyword,
                    "Position": item.position,
                    "Title": item.title,
                    "URL": item.url,
                    "Snippet": item.snippet,
                    "Displayed Link": item.displayed_link,
                    "Rich Snippet": getattr(item, "rich_snippet_text", None),
                    "Provider": result.provider,
                }
            )
    return pd.DataFrame(rows)


# Extract per-keyword Trends averages table from a GoogleTrendsResult.
#
# Mirrors the averages-rows logic of utils/pipeline.py google_trends_result_to_tables (line ~1862),
# reproduced here without importing the banned module. Returns None if no averages available.
def trends_result_to_averages_df(result: Optional[GoogleTrendsResult]) -> Optional[pd.DataFrame]:
    if result is None:
        return None
    averages: Dict[str, float] = dict(result.averages or {})
    if not averages and result.interest_over_time:
        try:
            averages = GoogleTrendsClient._calculate_averages(result.interest_over_time)
        except Exception as exc:  # noqa: BLE001 — never crash the pipeline on trends math
            logger.warning(f"cli: trends average calculation failed: {exc}")
            return None
    if not averages:
        return None
    request = result.request
    geo = getattr(request, "geo", "") if request is not None else ""
    timeframe = getattr(request, "timeframe", "") if request is not None else ""
    rows = [
        {
            "Keyword": keyword,
            "Average Interest": round(float(value), 2),
            "Geo": geo,
            "Timeframe": timeframe,
            "Provider": result.provider,
        }
        for keyword, value in sorted(averages.items())
    ]
    return pd.DataFrame(rows)


# Combine explicit keywords + from-URL content into the working keyword list.
#
# For the CLI, URL content is produced by scrape->llm-extract; direct keyword seeds are used as-is.
def build_input_keywords(config: EnrichmentConfig) -> List[str]:
    return _normalize_keywords(config.keywords)


# ---------------------------------------------------------------------------
# Progress helper (self-contained — replaces st.progress / st.status)
# ---------------------------------------------------------------------------

# EN-first bilingual user-message helper: returns "<English> / <Russian>" (space-slash-space).
def _bi(en: str, ru: str) -> str:
    return f"{en} / {ru}"


def _progress(msg: str) -> None:
    print(f"[seos-cli / сеос-кли] {msg}")
    logger.info(f"cli: {msg}")


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def _resolve_steps(steps: Optional[List[str]]) -> set[str]:
    if not steps:
        return set(ALL_STEPS)
    return {s.strip() for s in steps if s and s.strip()}


@dataclass
# Holds the stage callables run_enrichment orchestrates.
#
# Defaults bind the real streamlit-free utils/ callables; tests override individual entries via
# run_enrichment(..., _inject_stages={...}) so the orchestrator can be exercised with plain fakes
# in an isolated subprocess, WITHOUT unittest.mock.patch (which perturbs shared global state that
# later streamlit-based tests depend on, causing ordering-dependent failures).
class _StageBindings:

    validate_urls: Any = URLValidator.validate_urls
    # Use the browser-fallback scrape path so a URL that 403-blocks the requests/aiohttp
    # scraper is retried via cloakbrowser (toggle: scraper.content_browser_fallback_enabled).
    # Without this, a 403 is terminal -> the LLM is skipped -> no keywords (production bug).
    scrape_urls: Any = WebScraper.scrape_urls_with_browser_fallback
    LLMHandler: Any = LLMHandler
    GoogleAdsHandler: Any = GoogleAdsHandler
    create_serp_client: Any = create_serp_client
    TrendsOrchestrator: Any = TrendsOrchestrator
    merge_enrichment: Any = merge_enrichment
    write_report: Any = write_report


# Build the keywords payload for LLMHandler.generate_seo_text from the ads DataFrame.
#
# generate_seo_text reads k['Keyword'] (capital K) and k.get('Avg Monthly Searches') — i.e. it
# expects Ads-DataFrame rows, matching the app's keywords_payload contract (components/results.py).
# Falls back to plain {'Keyword': kw} rows when ads_df lacks the columns.
def _seo_text_payload(ads_df: pd.DataFrame, keywords: List[str]) -> List[Dict[str, Any]]:
    if ads_df is None or ads_df.empty or "Keyword" not in ads_df.columns:
        return [{"Keyword": k} for k in keywords]
    rows: List[Dict[str, Any]] = []
    for _, row in ads_df.iterrows():
        vol = row.get("Avg Monthly Searches")
        entry: Dict[str, Any] = {"Keyword": row["Keyword"]}
        if "Avg Monthly Searches" in ads_df.columns:
            entry["Avg Monthly Searches"] = int(vol) if pd.notna(vol) else "N/A"
        rows.append(entry)
    return rows[:20]  # the handler only hashes the first 20 anyway


def run_enrichment(
    config: EnrichmentConfig,
    _inject_stages: Optional[Dict[str, Any]] = None,
) -> EnrichmentResult:
    """Run the headless enrichment pipeline. Returns stage artifacts + export status.

    Honors config.steps (subset of ALL_STEPS). Calls only the 7 streamlit-free utils/ callables.
    Honors config.resume/clean (Phase C2): the paid 'ads' stage is checkpointed under config.workdir
    so a resumed run with matching inputs reuses it; --clean wipes the workdir first.

    `_inject_stages` (optional, leading-underscore = test-only hook) overrides stage callables by
    name — used by tests/test_cli_pipeline.py to inject plain fakes in a subprocess.
    """
    steps = _resolve_steps(config.steps)
    result = EnrichmentResult(merged=None)

    stages = _StageBindings()
    if _inject_stages:
        for _name, _fn in _inject_stages.items():
            if hasattr(stages, _name):
                setattr(stages, _name, _fn)

    # --- Checkpoint store (Phase C2): resume skips done steps; clean wipes; stale-input guards. ---
    run_id = getattr(config, "run_id", config.resume) or "default"
    checkpoint = CheckpointStore(
        workdir=Path(config.workdir),
        run_id=run_id,
        keywords=config.keywords,
        urls=config.urls,
    )
    if config.clean or not config.resume:
        # A fresh (non-resume) run starts clean so prior artifacts don't leak in; --clean is explicit.
        checkpoint.clean()
    if config.resume:
        _progress(_bi(f"Resuming run {run_id} from checkpoint...", f"Возобновление выполнения {run_id} из контрольной точки..."))

    # --- Stage 1: validate URLs (and scrape content if URLs given) ---
    scraped: List[ScrapedContent] = []
    if config.urls:
        if "validate" in steps:
            _progress(_bi(f"Validating {len(config.urls)} URL(s)...", f"Проверка {len(config.urls)} URL-адресов..."))
        valid, invalid = stages.validate_urls(config.urls)
        if invalid:
            _progress(_bi(f"  {len(invalid)} invalid URL(s) skipped", f"  {len(invalid)} недействительных URL-адресов пропущено"))
        if "scrape" in steps and valid:
            _progress(_bi(f"Scraping {len(valid)} URL(s)...", f"Сбор данных с {len(valid)} URL-адресов..."))
            scraped = stages.scrape_urls(valid)
            _progress(_bi(f"  scraped {sum(1 for s in scraped if s.success)} OK", f"  собрано успешно: {sum(1 for s in scraped if s.success)}"))

    # --- Stage 2: assemble keywords (explicit seed + LLM extraction from scraped content) ---
    keywords = build_input_keywords(config)

    if "llm-extract" in steps and scraped:
        _progress(_bi("Extracting keywords from scraped content via LLM...", "Извлечение ключевых слов из собранного контента через LLM..."))
        handler = stages.LLMHandler()
        for content in scraped:
            if not getattr(content, "success", False) or not getattr(content, "text", ""):
                continue
            try:
                extracted = handler.generate_keywords(
                    content.text,
                    provider=config.llm_provider,
                    model=config.llm_model,
                    max_keywords=config.max_keywords or 15,
                    custom_prompt=config.custom_prompt,
                )
                keywords.extend(extracted)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"cli: llm-extract failed for {getattr(content, 'url', '?')}: {exc}")
        keywords = _normalize_keywords(keywords)

    if config.max_keywords:
        keywords = keywords[: config.max_keywords]

    result.keywords = keywords
    if not keywords:
        _progress(_bi("No keywords to enrich; nothing to do.", "Нет ключевых слов для обогащения; нечего делать."))
        return result

    # --- Stage 3: Google Ads metrics (paid API — checkpointed so resume skips it) ---
    ads_df: Optional[pd.DataFrame] = None
    if "ads" in steps:
        if config.resume and checkpoint.is_done("ads"):
            ads_df = checkpoint.load("ads")
            if ads_df is not None:
                _progress(_bi(f"  ads: reused checkpointed artifact ({len(ads_df)} row(s))", f"  ads: использован сохранённый артефакт ({len(ads_df)} строк)"))
            else:
                # Marked done but artifact missing — fall through and re-run.
                _progress(_bi("  ads: checkpoint marked done but artifact missing; re-running", "  ads: контрольная точка отмечена готовой, но артефакт отсутствует; перезапуск"))
                ads_df = None
        if ads_df is None:
            _progress(_bi(f"Fetching Google Ads metrics for {len(keywords)} keyword(s)...", f"Получение метрик Google Ads для {len(keywords)} ключевых слов..."))
            ads_handler = stages.GoogleAdsHandler(
                location_id=config.ads_location_id,
                language_id=config.ads_language_id,
                target_currency_code=config.ads_currency_code,
            )
            try:
                ads_df = ads_handler.get_keyword_metrics(keywords)
                if ads_df is not None and not ads_df.empty:
                    _progress(_bi(f"  ads returned {len(ads_df)} row(s)", f"  ads вернул {len(ads_df)} строк"))
                    checkpoint.save("ads", artifact=ads_df)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"cli: ads metrics failed: {exc}")
                ads_df = None

    # Ensure ads_df always has a Keyword column for the merge
    if ads_df is None:
        ads_df = pd.DataFrame({"Keyword": keywords})

    # --- Stage 4: SERP analysis ---
    serp_df: Optional[pd.DataFrame] = None
    if "serp" in steps:
        _progress(_bi(f"Running SERP analysis for {len(keywords)} keyword(s)...", f"Выполнение SERP-анализа для {len(keywords)} ключевых слов..."))
        client = stages.create_serp_client()
        if client is not None:
            try:
                serp_results = client.search_batch(keywords)
                serp_df = collect_serp_rows(serp_results)
                _progress(_bi(f"  serp collected {0 if serp_df is None else len(serp_df)} row(s)", f"  serp собрано {0 if serp_df is None else len(serp_df)} строк"))
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"cli: serp failed: {exc}")
                serp_df = None
        else:
            _progress(_bi("  no SERP client (provider/key unavailable); skipping SERP", "  нет SERP-клиента (провайдер/ключ недоступен); пропуск SERP"))
    result.serp_df = serp_df

    # --- Stage 5: Google Trends ---
    trends_df: Optional[pd.DataFrame] = None
    if "trends" in steps:
        _progress(_bi(f"Running Google Trends for {len(keywords)} keyword(s)...", f"Выполнение Google Trends для {len(keywords)} ключевых слов..."))
        try:
            orchestrator = stages.TrendsOrchestrator()
            trends_result = orchestrator.run_trends(keywords)
            trends_df = trends_result_to_averages_df(trends_result)
            _progress(_bi(f"  trends averages: {0 if trends_df is None else len(trends_df)} row(s)", f"  trends средние значения: {0 if trends_df is None else len(trends_df)} строк"))
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"cli: trends failed: {exc}")
            trends_df = None
    result.trends_df = trends_df

    # --- Stage 6: LLM SEO text ---
    seo_text = ""
    if "seo-text" in steps:
        _progress(_bi("Generating SEO text via LLM...", "Генерация SEO-текста через LLM..."))
        handler = stages.LLMHandler()
        # generate_seo_text expects Ads-DataFrame rows: [{'Keyword': str, 'Avg Monthly Searches': ...}]
        # (capital 'Keyword' — see utils/llm_handler.py:1165 k['Keyword']). Build from ads_df so the
        # payload matches the app's keywords_payload contract (components/results.py:1462).
        kw_dicts = _seo_text_payload(ads_df, keywords)
        # Use the richest available content as the source text (first scraped, else joined keywords)
        source_text = next(
            (c.text for c in scraped if getattr(c, "success", False) and getattr(c, "text", "")),
            ", ".join(keywords),
        )
        try:
            seo_text = handler.generate_seo_text(
                source_text,
                keywords=kw_dicts,
                provider=config.llm_provider,
                model=config.llm_model,
                language=config.language,
                custom_prompt=config.custom_prompt,
                page_type=config.seo_page_type,
            )
            _progress(_bi("  seo text generated", "  SEO-текст сгенерирован"))
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"cli: seo-text failed: {exc}")
    result.seo_text = seo_text

    # --- Stage 7: merge (SERP + Trends aggregates onto ads) ---
    merged = ads_df
    if "merge" in steps:
        _progress(_bi("Merging SERP/Trends aggregates onto metrics...", "Слияние агрегатов SERP/Trends с метриками..."))
        merged = stages.merge_enrichment(ads_df, serp_df=serp_df, trends_df=trends_df)
    result.merged = merged

    # --- Stage 8: export ---
    out_path: Optional[str] = None
    if "export" in steps and merged is not None:
        _progress(_bi(f"Writing report -> {config.out} ({config.fmt})...", f"Запись отчёта -> {config.out} ({config.fmt})..."))
        out_path = stages.write_report(merged, config.out, config.fmt, seo_text=seo_text)
        if out_path:
            _progress(_bi(f"  wrote {out_path}", f"  записано {out_path}"))
        else:
            result.export_failed = True
    result.out_path = out_path

    return result
