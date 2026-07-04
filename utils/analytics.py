from __future__ import annotations

# MODULE_CONTRACT: utils/analytics
# Purpose: Local analytics event store for the statistics workflow — records privacy-safe
#          structured events to data/analytics_events.json, derives summary statistics for the
#          dashboard, and manages bounded retention with thread-safe atomic writes.
# Rationale: Give SEO specialists usage analytics (runs, providers, tokens, cache, patterns) without
#            any external telemetry and without ever persisting prompts, scraped text, API keys, or
#            raw responses. Mirrors the request-cache privacy + secret-key filtering conventions.
# Dependencies: json, os, re, time, hashlib, tempfile, threading, pathlib, datetime, typing, config.settings
# Exports: ANALYTICS_FILE, SCHEMA_VERSION, record_event, record_workflow_event, load_events, load_history_analytics_events, trim_events, build_statistics_summary, build_statistics_export_sheets
# LINKS: requirements.xml#UC-001, knowledge-graph.xml#MOD-033, PLAN 19 Task 1, PLAN 19 Task 8, verification-plan.xml#V-19-ANALYTICS-STORE, verification-plan.xml#V-19-STATISTICS-DASHBOARD
# MODULE_MAP: utils/analytics.py
# Public Functions: record_event, record_workflow_event, load_events, load_history_analytics_events, trim_events, build_statistics_summary, build_statistics_export_sheets
# Private Helpers: _normalize_event, _fingerprint_values, _split_key_tokens, _is_secret_key,
#                  _load_bundle, _write_bundle_atomic, _compute_event_id, _parse_created_at,
#                  _build_overview, _build_provider_summary, _build_token_summary,
#                  _build_time_heatmap, _build_workflow_funnel, _build_repeated_patterns,
#                  _build_insights, _coerce_int
# Key Semantic Blocks: block_event_normalization, block_atomic_write, block_privacy_filtering,
#                      block_duplicate_event_handling, block_summary_building, block_prune_on_write,
#                      block_export_sheet_building
# Critical Flows: record -> normalize (privacy) -> dedupe by event_id -> prune-on-write cap ->
#                 atomic temp-file + os.replace (PermissionError retry) -> load -> build summary ->
#                 build export sheets (pure).
#                 All configurable limits come from load_config() at write time (never hardcoded, never stale).
# Verification: python -m py_compile utils/analytics.py, python -m ruff check utils/analytics.py,
#               python -m pytest -q tests/test_analytics.py
# CHANGE_SUMMARY: Added the analytics event store and statistics summary builder for the statistics workflow. statistics-workflow Task 4: added record_workflow_event() boundary recorder (no-ops when disabled, swallows internal errors, delegates to record_event for deterministic event_id dedup). Funnel fix: made `stage` a first-class persisted schema field and reworked _FUNNEL_STAGES to key stage_completed events on (event_type, stage) pairs so the workflow funnel no longer reports all-zero stage rows. statistics-workflow Task 5: _normalize_event now persists the "unknown" sentinel string for the tokens field so missing LLM usage is distinguishable from a genuine zero-token call (never a zero-dict). statistics-workflow Task 8: added build_statistics_export_sheets() pure builder producing CSV-exportable DataFrames (providers/funnel/heatmap/tokens) with stable machine column names; added pandas import. Statistics UI fix: added load_history_analytics_events() as a read-only bridge from saved history/checkpoints/cache records into aggregate-only dashboard events.

import hashlib
import json
import os
import re
import tempfile
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlsplit, urlunsplit

import pandas as pd

try:
    # PHASE-20 / STEP-2002: reuse the tldextract-backed registrable-domain helper; do NOT
    # duplicate PSL logic. Falls back to a netloc-based normalization if utils.domain is unavailable.
    from utils.domain import registrable_domain as _registrable_domain
except Exception:  # pragma: no cover - keep analytics importable even if domain helper missing
    def _registrable_domain(value: Optional[str]) -> str:  # type: ignore[misc]
        try:
            return str(urlsplit(value or "").netloc).lower()
        except Exception:
            return ""

try:
    from config.settings import load_config
except Exception:  # pragma: no cover - config layer must always be importable
    def load_config() -> Dict[str, Any]:  # type: ignore[misc]
        return {}


# Local logger for swallowed analytics errors. Imported lazily and defensively so this module
# never fails to import even if utils.logger is unavailable (analytics must be the last thing
# to ever break a workflow run).
def _analytics_log(message: str) -> None:
    try:  # pragma: no cover - logging must never break analytics
        from utils.logger import logger
        logger.warning(message)
    except Exception:
        pass


ANALYTICS_FILE: Path = Path(__file__).parent.parent / "data" / "analytics_events.json"
SCHEMA_VERSION: int = 1

# Module-level lock guarding every load-modify-write path so concurrent Streamlit
# sessions/threads cannot lose each other's events. Public + private writers all acquire it.
_WRITE_LOCK = threading.Lock()

# Privacy: canonical secret-key token set mirroring utils.request_cache._SECRET_KEY_TOKENS.
_SECRET_KEY_TOKENS = {
    "api",
    "apikey",
    "api_key",
    "auth",
    "authorization",
    "bearer",
    "clientsecret",
    "client_secret",
    "credential",
    "credentials",
    "key",
    "password",
    "privatekey",
    "private_key",
    "refresh",
    "secret",
    "session",
    "token",
}

# Privacy: raw-text fields that must never be persisted by this module (the caller may pass
# already-normalized values; our job is to never *introduce* raw url/text content).
_RAW_TEXT_FIELDS = {
    "prompt",
    "scraped_text",
    "response",
    "response_body",
    "content",
    "seo_text",
    "url",  # full url with query strings; callers pass host/path hash instead
}

# Canonical set of top-level schema fields that may appear on a normalized event.
_SCHEMA_FIELDS = {
    "event_id",
    "created_at",
    "run_id",
    "event_type",
    "stage",  # stage_completed identity (e.g. scrape_prepared/llm_completed); privacy-safe enum-like string.
    "workflow_mode",
    "provider",
    "model",
    "status",
    "duration_ms",
    "counts",
    "tokens",
    "cache",
    "fingerprints",
    "error",
    "dimensions",  # PHASE-20 / STEP-2002: processed_queries/processed_websites/processed_urls/serp_results/math_terms (whitelisted nested lists only).
}

# PHASE-20 / STEP-2002: whitelisted nested keys allowed inside the `dimensions` schema field.
# Each value must be a list of already-normalized privacy-safe scalars (queries/websites/urls are
# normalized/canonicalized by the recorder BEFORE persistence; serp_results/math_terms are reduced
# metric dicts only — no raw snippets/results). Unknown nested keys are dropped by _normalize_event.
_DIMENSION_KEYS = (
    "processed_queries",
    "processed_websites",
    "processed_urls",
    "serp_results",
    "math_terms",
)

# Workflow funnel stages: (stage_label, marker_event_type, marker_stage).
# A stage counts events where event_type == marker_event_type AND (marker_stage is None OR
# event.stage == marker_stage). Task 4 emits {"event_type": "stage_completed", "stage": <stage>},
# so the marker for instrumented stages is (stage_completed, <stage>). Uninstrumented stages use
# a never-emitted marker so their count stays 0 naturally (no invented counts).
_FUNNEL_STAGES: List[Tuple[str, str, Optional[str]]] = [
    ("submitted", "workflow_submitted", None),
    ("scrape_prepared", "stage_completed", "scrape_prepared"),
    ("llm_completed", "stage_completed", "llm_completed"),
    ("url_seed_completed", "stage_completed", "url_seed_completed"),
    ("serp_completed", "stage_completed", "serp_completed"),
    ("ads_completed", "stage_completed", "ads_completed"),
    ("trends_completed", "stage_completed", "trends_completed"),
    ("crawl_completed", "stage_completed", "crawl_completed"),
    ("seo_completed", "stage_completed", "seo_completed"),
]

# PHASE-20 / STEP-2001: fixture-event classification. Known test/manual-run provider/model
# tokens that pollute the local store when analytics-writing tests forget to redirect
# ANALYTICS_FILE. String-matched on already-recorded (privacy-safe) provider/model/run_id fields.
_FIXTURE_PROVIDERS = frozenset({"testcustom", "my-unique-provider"})
# Models that mark a fixture event regardless of provider (substring match on the model value).
_FIXTURE_MODEL_SUBSTRINGS = ("gemini-test", "fallback-model", "custom-model")
# run_id values that look like explicit test markers (substring match).
_FIXTURE_RUN_ID_MARKERS = ("test-run", "fixture-run", "iso-")


# --------------------------------------------------------------------------- #
# Privacy helpers (reuse request_cache semantics, not import-time coupling)
# --------------------------------------------------------------------------- #
# FUNCTION_CONTRACT: _split_key_tokens
# Purpose: Split a dict key into normalized lowercase tokens (camelCase -> snake, split on non-alnum).
# Input: key (str)
# Output: list[str] of tokens
# Side Effects: none
# Business Rules: mirrors utils.request_cache._split_key_tokens exactly so secret detection is consistent.
# Failure Modes: never raises; returns [] for falsy input.
# LINKS: knowledge-graph.xml#MOD-033, knowledge-graph.xml#MOD-014
def _split_key_tokens(key: str) -> List[str]:
    normalized = re.sub(r"(?<!^)(?=[A-Z])", "_", str(key))
    normalized = normalized.replace("-", "_").replace(".", "_")
    return [token for token in re.split(r"[^a-zA-Z0-9]+", normalized.lower()) if token]


# FUNCTION_CONTRACT: _is_secret_key
# Purpose: Return True if any token of the key (or the joined tokens) matches a secret token.
# Input: key (str)
# Output: bool
# Side Effects: none
# Business Rules: True if any token in _SECRET_KEY_TOKENS or the full joined form matches.
# Failure Modes: never raises.
# LINKS: knowledge-graph.xml#MOD-033, knowledge-graph.xml#MOD-014
def _is_secret_key(key: str) -> bool:
    tokens = _split_key_tokens(key)
    if not tokens:
        return False
    joined = "".join(tokens)
    return any(token in _SECRET_KEY_TOKENS for token in tokens) or joined in _SECRET_KEY_TOKENS


# --------------------------------------------------------------------------- #
# Event normalization + privacy filtering
# --------------------------------------------------------------------------- #
# FUNCTION_CONTRACT: _fingerprint_values
# Purpose: Produce a deterministic order-independent sha256 fingerprint for a sequence of values.
# Input: values (Sequence[str]) — any iterable of string-coercible values
# Output: str — "sha256:" + 64 hex chars
# Side Effects: none
# Business Rules: lowercased, deduplicated, sorted join joined by "\n"; empty input hashes to a stable value.
# Failure Modes: never raises; coerces non-str via str().
# LINKS: knowledge-graph.xml#MOD-033
def _fingerprint_values(values: Sequence[str]) -> str:
    # block_privacy_filtering: fingerprint must be deterministic and order-independent.
    items: List[str] = []
    seen: set = set()
    for raw in values or []:
        cleaned = str(raw).strip().lower()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        items.append(cleaned)
    items.sort()
    payload = "\n".join(items)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


# FUNCTION_CONTRACT: _normalize_event
# Purpose: Build a privacy-safe event dict containing only schema fields, dropping secrets and raw text.
# Input: event (dict) — raw caller-provided event
# Output: dict — normalized event with only allowed fields
# Side Effects: none (pure transformation)
# Business Rules: block_event_normalization + block_privacy_filtering — drop secret-like keys at every
#                 nesting level, drop raw-text fields, keep only _SCHEMA_FIELDS plus sanitized sub-dicts.
#                 created_at is filled from `now` only inside record_event, not here.
# Failure Modes: never raises; missing fields default to empty/None per schema.
# LINKS: knowledge-graph.xml#MOD-033, PLAN 19 Task 1
def _normalize_event(event: dict) -> dict:
    # block_privacy_filtering: recursively strip secret keys from any nested sub-dict.
    def _strip_secrets(value: Any) -> Any:
        if isinstance(value, dict):
            cleaned: Dict[str, Any] = {}
            for key, item in value.items():
                key_str = str(key)
                if _is_secret_key(key_str):
                    continue
                cleaned_item = _strip_secrets(item)
                cleaned[key_str] = cleaned_item
            return cleaned
        if isinstance(value, list):
            return [_strip_secrets(item) for item in value]
        return value

    raw = event if isinstance(event, dict) else {}
    normalized: Dict[str, Any] = {}

    # block_event_normalization: keep only schema fields, sanitize sub-dicts.
    for field in _SCHEMA_FIELDS:
        if field not in raw:
            continue
        value = raw[field]
        # Drop raw-text fields entirely even if they appear under a schema-like name.
        if field in _RAW_TEXT_FIELDS:
            continue
        if field in {"counts", "tokens", "cache", "fingerprints"}:
            if isinstance(value, dict):
                normalized[field] = _strip_secrets(value)
            elif field == "tokens" and value == "unknown":
                # block_token_capture: missing usage is persisted as the "unknown" sentinel
                # string (NEVER a zero-dict) so callers can distinguish "no usage reported"
                # from a genuine zero-token call.
                normalized[field] = "unknown"
            continue
        if field == "dimensions":
            # block_analytics_processed_dimensions: keep only whitelisted nested keys as lists;
            # secret-strip each item; drop unknown keys so no raw text leaks under dimensions.
            if isinstance(value, dict):
                safe_dims: Dict[str, Any] = {}
                for dim_key in _DIMENSION_KEYS:
                    if dim_key not in value:
                        continue
                    dim_val = value[dim_key]
                    if isinstance(dim_val, list):
                        safe_dims[dim_key] = _strip_secrets(dim_val)
                if safe_dims:
                    normalized[field] = safe_dims
            continue
        normalized[field] = value

    normalized.setdefault("error", "")
    return normalized


# --------------------------------------------------------------------------- #
# Bundle I/O (atomic, Windows-safe)
# --------------------------------------------------------------------------- #
# FUNCTION_CONTRACT: _load_bundle
# Purpose: Read and parse the analytics JSON bundle, returning an empty bundle on any problem.
# Input: (none) — reads module-level ANALYTICS_FILE
# Output: dict — {"schema_version": int, "events": list}
# Side Effects: reads filesystem
# Business Rules: never raises; missing/corrupt/non-list events => empty events list.
# Failure Modes: swallowed json/IO errors => empty bundle.
# LINKS: knowledge-graph.xml#MOD-033
def _load_bundle() -> Dict[str, Any]:
    if not ANALYTICS_FILE.exists():
        return {"schema_version": SCHEMA_VERSION, "events": []}
    try:
        with open(ANALYTICS_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return {"schema_version": SCHEMA_VERSION, "events": []}
    if not isinstance(data, dict):
        return {"schema_version": SCHEMA_VERSION, "events": []}
    events = data.get("events", [])
    if not isinstance(events, list):
        events = []
    return {"schema_version": SCHEMA_VERSION, "events": events}


# FUNCTION_CONTRACT: _write_bundle_atomic
# Purpose: Write the bundle to ANALYTICS_FILE atomically via a same-directory temp file + os.replace,
#          retrying on Windows PermissionError file-lock races.
# Input: events (list[dict])
# Output: bool — True on success
# Side Effects: creates data/ dir (parents=True), writes a temp file, os.replace onto target
# Business Rules: block_atomic_write — temp file in SAME dir as target via tempfile.mkstemp, close fd
#                 before replace; retry PermissionError a few times with time.sleep; re-raise if persistent.
# Failure Modes: PermissionError after retries re-raises; other IO errors propagate.
# LINKS: knowledge-graph.xml#MOD-033, PLAN 19 Task 1
def _write_bundle_atomic(events: List[Dict[str, Any]]) -> bool:
    # block_atomic_write: mkdir, mkstemp in same dir, close fd, os.replace with retry.
    ANALYTICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": SCHEMA_VERSION, "events": events}
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)

    fd, tmp_path = tempfile.mkstemp(
        prefix=".analytics_events_", suffix=".tmp", dir=str(ANALYTICS_FILE.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(serialized)
        # Windows file-lock race: retry os.replace a few times before giving up.
        last_exc: Optional[Exception] = None
        for attempt in range(5):
            try:
                os.replace(tmp_path, ANALYTICS_FILE)
                return True
            except PermissionError as exc:
                last_exc = exc
                time.sleep(0.05 * (attempt + 1))
        # Exhausted retries: re-raise the last PermissionError so callers see the failure.
        if last_exc is not None:
            raise last_exc
        return False
    except Exception:
        # Clean up the temp file on any non-replace failure path.
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise


# --------------------------------------------------------------------------- #
# Config access (live read at write time — no module-level snapshot staleness)
# --------------------------------------------------------------------------- #
# FUNCTION_CONTRACT: _max_events_cap
# Purpose: Read analytics.max_events from live config at write time.
# Input: (none)
# Output: int — max events cap (default 5000)
# Side Effects: reads settings.yaml via load_config()
# Business Rules: default 5000 when absent/malformed; never hardcoded at module import.
# Failure Modes: config read errors => default.
# LINKS: knowledge-graph.xml#MOD-033
def _max_events_cap() -> int:
    try:
        raw = load_config().get("analytics", {}).get("max_events", 5000)
        value = int(raw)
        return value if value > 0 else 5000
    except Exception:
        return 5000


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
# FUNCTION_CONTRACT: record_event
# Purpose: Append a privacy-safe normalized event to the analytics store, deduping by event_id and
#          pruning to the configured cap; thread-safe and atomic.
# Input: event (dict), now (datetime | None = None)
# Output: bool — True if appended, False if a duplicate event_id was rejected
# Side Effects: creates data/ dir, writes ANALYTICS_FILE atomically
# Business Rules: block_duplicate_event_handling rejects duplicate event_ids; block_prune_on_write keeps
#                 total <= max_events (keep newest cap before append); created_at filled from `now` when absent;
#                 `now` defaults to datetime.now() inside the body (never a def-time default).
# Failure Modes: write errors propagate after retry; duplicate => False without raising.
# LINKS: knowledge-graph.xml#MOD-033, PLAN 19 Task 1, verification-plan.xml#V-19-ANALYTICS-STORE
def record_event(event: dict, now: Optional[datetime] = None) -> bool:
    if now is None:
        now = datetime.now()

    normalized = _normalize_event(event)
    # block_event_normalization: fill created_at from injected now when the caller omitted it.
    if not normalized.get("created_at"):
        normalized["created_at"] = now.isoformat()

    with _WRITE_LOCK:
        bundle = _load_bundle()
        events = bundle["events"]

        # block_duplicate_event_handling: reject duplicate event_id without appending.
        event_id = normalized.get("event_id")
        if event_id:
            for existing in events:
                if isinstance(existing, dict) and existing.get("event_id") == event_id:
                    return False

        events.append(normalized)

        # block_prune_on_write: if appending exceeded the cap, keep the newest (cap) before the new event.
        cap = _max_events_cap()
        if len(events) > cap:
            events = events[-cap:]

        _write_bundle_atomic(events)
        return True


# FUNCTION_CONTRACT: record_workflow_event
# Purpose: Privacy-safe boundary recorder for the statistics workflow — a thin public wrapper
#          around record_event() that no-ops when analytics is disabled and swallows any internal
#          error so a call site can NEVER break a workflow run. Reads analytics config at call time.
# Input: event_type (str), **fields — caller-supplied privacy-safe fields (run_id, workflow_mode,
#        provider, model, status, counts, duration_ms, stage, error message key). The `stage` field is a
#        first-class persisted schema field used by the workflow funnel. Never prompts/scraped text/keys.
# Output: bool — True if appended; False if disabled, rejected as duplicate, or swallowed an error
# Side Effects: delegates to record_event() (writes ANALYTICS_FILE atomically) when enabled
# Business Rules: reads analytics.enabled from live config at call time; always routes through
#                 record_event() so deterministic event_id dedup applies; never raises — a logging
#                 failure must not propagate to app/pipeline callers (so no broad try/except is needed
#                 at call sites). The `stage` field is a first-class schema field and is persisted so the
#                 workflow funnel can key stage_completed events on it.
# Failure Modes: any internal error => logged via utils.logger and returns False; never raises.
# LINKS: knowledge-graph.xml#MOD-033, PLAN 19 Task 4, verification-plan.xml#V-19-ANALYTICS-INSTRUMENTATION
def record_workflow_event(event_type: str, **fields: Any) -> bool:
    try:
        if not load_config().get("analytics", {}).get("enabled", True):
            return False
        payload: Dict[str, Any] = {"event_type": event_type, **fields}
        return record_event(payload)
    except Exception as exc:  # pragma: no cover - robustness path; analytics must never break runs
        _analytics_log(f"analytics record_workflow_event swallowed error: {exc!r}")
        return False


# FUNCTION_CONTRACT: load_events
# Purpose: Return the list of stored analytics events; never raises.
# Input: (none)
# Output: list[dict]
# Side Effects: reads filesystem under the write lock for consistency
# Business Rules: missing/corrupt file => [] ; returns a shallow copy so callers cannot mutate the store.
# Failure Modes: never raises.
# LINKS: knowledge-graph.xml#MOD-033
def load_events() -> List[Dict[str, Any]]:
    with _WRITE_LOCK:
        bundle = _load_bundle()
    return list(bundle.get("events", []))


# FUNCTION_CONTRACT: load_history_analytics_events
# Purpose: Build read-only synthetic analytics events from saved history/checkpoints/cache records.
# Input: records (list[dict] | None) - optional injected records for tests; None loads HistoryManager.
# Output: list[dict] - aggregate-safe events for summary building only
# Side Effects: reads data/history.json when records is None; never writes analytics_events.json.
# Business Rules: never reads scraped_content; only emits workflow_completed counts,
#                 processed_dimensions from checkpoint processed_data, and LLM cache provider usage
#                 with tokens="unknown" because old cache records do not contain token usage.
# Failure Modes: never raises; malformed history/cache records are skipped.
# LINKS: knowledge-graph.xml#MOD-033, PHASE-20 STEP-2002, PHASE-20 STEP-2005
def load_history_analytics_events(
    records: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    try:
        if records is None:
            from utils.history import HistoryManager

            records = HistoryManager.load_history(include_cache=True)
    except Exception as exc:  # pragma: no cover - history fallback must never break stats
        _analytics_log(f"analytics load_history_analytics_events swallowed error: {exc!r}")
        return []

    try:
        analytics_cfg = load_config().get("analytics", {})
        per_event_limit = _coerce_int(
            analytics_cfg.get("max_dimension_items_per_event", 250)
        ) or 250
    except Exception:
        per_event_limit = 250

    synthetic: List[Dict[str, Any]] = []
    for index, record in enumerate(records or []):
        if not isinstance(record, dict):
            continue
        created_at = str(record.get("created_at") or record.get("timestamp") or "")
        record_type = str(record.get("record_type") or "history")

        if record_type == "cache":
            kind = str(record.get("kind") or "")
            if kind not in {"llm_extract", "llm_generate"}:
                continue
            request = record.get("request") if isinstance(record.get("request"), dict) else {}
            params = (
                request.get("normalized_params")
                if isinstance(request.get("normalized_params"), dict)
                else {}
            )
            provider = (
                record.get("provider")
                or request.get("provider")
                or params.get("provider")
                or ""
            )
            provider = str(provider).strip()
            if not provider or "MagicMock" in provider:
                continue
            model = str(record.get("model") or params.get("model") or "")
            synthetic.append(
                {
                    "event_id": _fingerprint_values(
                        ["history-cache", str(index), kind, provider, model, created_at]
                    ),
                    "event_type": "llm_call",
                    "source": "history",
                    "run_id": f"history-cache-{index}",
                    "workflow_mode": "history_cache",
                    "provider": provider,
                    "model": model,
                    "status": "success",
                    "tokens": "unknown",
                    "cache": {
                        "kind": kind,
                        "hit": _coerce_int(record.get("cache_hit_count")) > 0,
                    },
                    "created_at": created_at,
                }
            )
            continue

        metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
        checkpoint = (
            record.get("checkpoint") if isinstance(record.get("checkpoint"), dict) else {}
        )
        workflow_mode = str(
            metadata.get("workflow_mode") or checkpoint.get("workflow_mode") or "history"
        )
        processed_data = checkpoint.get("processed_data")
        rows_count = len(processed_data) if isinstance(processed_data, list) else 0
        synthetic.append(
            {
                "event_id": _fingerprint_values(
                    ["history", str(index), workflow_mode, created_at]
                ),
                "event_type": "workflow_completed",
                "source": "history",
                "run_id": f"history-{index}",
                "workflow_mode": workflow_mode,
                "status": "success",
                "counts": {
                    "urls": _coerce_int(record.get("url_count")),
                    "keywords": _coerce_int(record.get("keyword_count")),
                    "rows": rows_count,
                },
                "created_at": created_at,
            }
        )

        queries, websites, urls = _extract_processed_dimensions(
            processed_data,
            per_event_limit,
        )
        if queries or websites or urls:
            synthetic.append(
                {
                    "event_id": _fingerprint_values(
                        ["history-processed", str(index), workflow_mode, created_at]
                    ),
                    "event_type": "processed_dimensions",
                    "source": "history",
                    "run_id": f"history-{index}",
                    "workflow_mode": workflow_mode,
                    "stage": "history_checkpoint",
                    "dimensions": {
                        "processed_queries": queries,
                        "processed_websites": websites,
                        "processed_urls": urls,
                    },
                    "created_at": created_at,
                }
            )
    return synthetic


# FUNCTION_CONTRACT: trim_events
# Purpose: Remove events older than max_age_days (by created_at), never removing current-day events.
# Input: max_age_days (int), now (datetime | None = None)
# Output: int — count of removed events
# Side Effects: rewrites ANALYTICS_FILE atomically under the write lock (same path as record_event)
# Business Rules: events whose created_at date == now date are always kept; older events beyond
#                 max_age_days are dropped; `now` defaults to datetime.now() in body.
# Failure Modes: unparseable created_at => treated as keep (never dropped on a parse error).
# LINKS: knowledge-graph.xml#MOD-033, PLAN 19 Task 1
def trim_events(max_age_days: int, now: Optional[datetime] = None) -> int:
    if now is None:
        now = datetime.now()

    with _WRITE_LOCK:
        bundle = _load_bundle()
        events = bundle["events"]
        now_date = now.date()
        cutoff = now - timedelta(days=max_age_days)

        retained: List[Dict[str, Any]] = []
        removed = 0
        for event in events:
            created = _parse_created_at(event.get("created_at")) if isinstance(event, dict) else None
            if created is None:
                # Unparseable timestamp => keep (do not silently delete).
                retained.append(event)
                continue
            # Never remove current-day events even if max_age_days is 0/tiny.
            if created.date() == now_date:
                retained.append(event)
                continue
            if created < cutoff:
                removed += 1
                continue
            retained.append(event)

        if removed:
            _write_bundle_atomic(retained)
        return removed


# FUNCTION_CONTRACT: clear_analytics_store
# Purpose: Wipe the local analytics event store to an empty events list atomically, guarded by the
#          write lock. Used by the dashboard "clear local analytics store" action. No-ops (returns
#          False) when analytics is disabled; never raises so the dashboard cannot be broken.
# Input: (none)
# Output: bool — True if the store was wiped; False if disabled or an error was swallowed
# Side Effects: rewrites ANALYTICS_FILE atomically under _WRITE_LOCK with an empty events list
# Business Rules: reads analytics.enabled from live config; only writes when enabled; all internal
#                 errors are swallowed and logged (analytics must never break the dashboard).
# Failure Modes: any internal error => logged via utils.logger and returns False; never raises.
# LINKS: knowledge-graph.xml#MOD-033, PHASE-20 STEP-2001, verification-plan.xml#V-20-ANALYTICS-TEST-ISOLATION
def clear_analytics_store() -> bool:
    try:
        if not load_config().get("analytics", {}).get("enabled", True):
            return False
        with _WRITE_LOCK:
            _write_bundle_atomic([])
        return True
    except Exception as exc:  # pragma: no cover - robustness path; analytics must never break UI
        _analytics_log(f"analytics clear_analytics_store swallowed error: {exc!r}")
        return False


# --------------------------------------------------------------------------- #
# Summary building helpers
# --------------------------------------------------------------------------- #
# FUNCTION_CONTRACT: _parse_created_at
# Purpose: Parse a created_at ISO string into a datetime (naive local assumed if no tz).
# Input: value (Any)
# Output: datetime | None
# Side Effects: none
# Business Rules: returns None on unparseable input; strips tz to compare on local calendar date/hour.
# Failure Modes: never raises.
# LINKS: knowledge-graph.xml#MOD-033
def _parse_created_at(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None
    # Normalize to naive local time for weekday/hour bucketing.
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed


# FUNCTION_CONTRACT: _coerce_int
# Purpose: Coerce a value to int safely, returning 0 on failure.
# Input: value (Any)
# Output: int
# Side Effects: none
# Business Rules: never raises.
# Failure Modes: non-numeric => 0.
# LINKS: knowledge-graph.xml#MOD-033
def _coerce_int(value: Any) -> int:
    try:
        if value is None:
            return 0
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0


# --------------------------------------------------------------------------- #
# PHASE-20 / STEP-2001: fixture-event classification + diagnostics
# --------------------------------------------------------------------------- #
# FUNCTION_CONTRACT: _is_fixture_event
# Purpose: Classify an analytics event as a known test/manual-run fixture so it can be hidden from
#          summaries without being deleted from the store (view-only filtering). Privacy-safe: only
#          string-matches on already-recorded provider/model/run_id fields.
# Input: event (dict) — a normalized analytics event
# Output: bool — True when the event matches a known fixture provider/model/run_id pattern
# Side Effects: none (pure predicate)
# Business Rules: returns True when provider is in _FIXTURE_PROVIDERS, OR the model value contains
#                 any _FIXTURE_MODEL_SUBSTRINGS token, OR the run_id contains any
#                 _FIXTURE_RUN_ID_MARKERS token. Never raises; falsy/missing fields => False.
# Failure Modes: never raises; non-str fields coerced via str().
# LINKS: knowledge-graph.xml#MOD-033, PHASE-20 STEP-2001, verification-plan.xml#V-20-ANALYTICS-TEST-ISOLATION
def _is_fixture_event(event: dict) -> bool:
    if not isinstance(event, dict):
        return False
    provider = str(event.get("provider") or "").strip().lower()
    if provider in _FIXTURE_PROVIDERS:
        return True
    model = str(event.get("model") or "").strip().lower()
    if any(token in model for token in _FIXTURE_MODEL_SUBSTRINGS):
        return True
    run_id = str(event.get("run_id") or "").strip().lower()
    if any(marker in run_id for marker in _FIXTURE_RUN_ID_MARKERS):
        return True
    return False


# FUNCTION_CONTRACT: _hide_fixture_events_enabled
# Purpose: Read analytics.hide_fixture_events from live config (or an injected config dict).
# Input: config (dict | None) — when None, load_config() is read live
# Output: bool — whether fixture events are hidden from summaries (default True)
# Side Effects: reads settings.yaml via load_config() when config is None
# Business Rules: default True when absent/malformed; never hardcoded at module import.
# Failure Modes: config read errors => default True.
# LINKS: knowledge-graph.xml#MOD-033, PHASE-20 STEP-2001
def _hide_fixture_events_enabled(config: Optional[Dict[str, Any]] = None) -> bool:
    try:
        if config is None:
            config = load_config()
        raw = config.get("analytics", {}).get("hide_fixture_events", True)
        return bool(raw)
    except Exception:
        return True


# FUNCTION_CONTRACT: _filter_fixture_events
# Purpose: Return a view-only filtered event list with known fixture events removed when the
#          hide_fixture_events flag is on. NEVER mutates or deletes from the store.
# Input: events (list[dict]), hide (bool)
# Output: list[dict] — events with fixture entries excluded when hide is True; unchanged otherwise
# Side Effects: none (pure filter; the on-disk store is untouched)
# Business Rules: view-only filtering; the caller still owns the full events list for the Events tab.
# Failure Modes: never raises.
# LINKS: knowledge-graph.xml#MOD-033, PHASE-20 STEP-2001, verification-plan.xml#V-20-ANALYTICS-TEST-ISOLATION
def _filter_fixture_events(events: List[Dict[str, Any]], hide: bool) -> List[Dict[str, Any]]:
    if not hide:
        return list(events)
    return [e for e in events if not _is_fixture_event(e)]


# FUNCTION_CONTRACT: _build_diagnostics
# Purpose: Compute the diagnostics block: counts, the analytics file basename, custom-provider
#          count, hidden-fixture count, and the hide_fixture_events flag.
# Input: all_events (list[dict]) — the FULL unfiltered event list, filtered_events (list[dict]),
#        hide (bool)
# Output: dict with event_count, llm_call_count, unknown_token_calls, analytics_file,
#         custom_provider_count, hidden_fixture_events, hide_fixture_events_enabled
# Side Effects: none (pure aggregation; reads ANALYTICS_FILE path basename only)
# Business Rules: diagnostics describes the STORE TOTAL — counts run over all_events (the full
#                 unfiltered list) so the dashboard can show provenance about everything recorded,
#                 while the aggregate views (overview/provider/tokens/etc) already use the filtered
#                 list. hidden_fixture_events = len(all_events) - len(filtered_events). The file
#                 basename is reported for provenance (no full path).
# Failure Modes: never raises.
# LINKS: knowledge-graph.xml#MOD-033, PHASE-20 STEP-2001, verification-plan.xml#V-20-ANALYTICS-TEST-ISOLATION
def _build_diagnostics(
    all_events: List[Dict[str, Any]],
    filtered_events: List[Dict[str, Any]],
    hide: bool,
) -> Dict[str, Any]:
    # Counts describe the STORE TOTAL (all_events), not the filtered view — the dashboard views
    # already use the filtered summaries; diagnostics exposes provenance over everything recorded.
    llm_calls = [e for e in all_events if e.get("event_type") == "llm_call"]
    unknown_token_calls = sum(
        1 for e in llm_calls if isinstance(e.get("tokens"), str) and e["tokens"] == "unknown"
    )
    providers = {str(e.get("provider") or "") for e in llm_calls if e.get("provider")}
    # "custom" = any provider id not in the canonical settings llm.models keys; here we treat any
    # provider that is NOT one of the well-known built-in provider names as custom.
    _KNOWN_PROVIDERS = {
        "google", "openai", "anthropic", "xai", "groq", "deepseek", "minimax",
        "moonshot", "openrouter", "cerebras", "zai",
    }
    custom_provider_count = sum(
        1 for p in providers if p.lower() not in _KNOWN_PROVIDERS and p
    )
    return {
        "event_count": len(all_events),
        "llm_call_count": len(llm_calls),
        "unknown_token_calls": unknown_token_calls,
        "analytics_file": ANALYTICS_FILE.name,
        "custom_provider_count": custom_provider_count,
        "hidden_fixture_events": len(all_events) - len(filtered_events),
        "hide_fixture_events_enabled": hide,
    }


# --------------------------------------------------------------------------- #
# PHASE-20 / STEP-2002: processed-dimensions normalization + recording
# --------------------------------------------------------------------------- #
# FUNCTION_CONTRACT: _normalize_query
# Purpose: Normalize a processed-query scalar to a privacy-safe comparable form (strip/collapse
#          whitespace, lowercase) so duplicate queries across runs aggregate correctly.
# Input: value (Any) — raw query scalar from a DataFrame cell
# Output: str — normalized query ("" for falsy/non-str input)
# Side Effects: none (pure)
# Business Rules: collapse internal whitespace; lowercase; strip leading/trailing whitespace.
# Failure Modes: never raises; non-str/falsy => "".
# LINKS: knowledge-graph.xml#MOD-033, PHASE-20 STEP-2002, verification-plan.xml#V-20-PROCESSED-DIMENSIONS
def _normalize_query(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).lower()


# FUNCTION_CONTRACT: _normalize_domain
# Purpose: Normalize a processed-website/domain scalar to its registrable domain (eTLD+1) via the
#          shared utils.domain helper, so subdomains aggregate to the same site.
# Input: value (Any) — raw domain/URL scalar from a DataFrame cell
# Output: str — registrable domain ("" for falsy/unresolvable)
# Side Effects: none (pure; delegates to utils.domain.registrable_domain which is PSL-backed)
# Business Rules: reuse the tldextract-backed helper — never duplicate PSL logic.
# Failure Modes: never raises; unresolvable => "".
# LINKS: knowledge-graph.xml#MOD-033, PHASE-20 STEP-2002, verification-plan.xml#V-20-PROCESSED-DIMENSIONS
def _normalize_domain(value: Any) -> str:
    if value is None:
        return ""
    return _registrable_domain(str(value))


# FUNCTION_CONTRACT: _canonical_url
# Purpose: Canonicalize a processed-URL scalar by stripping the query string AND fragment, lower-
#          casing scheme+host, and keeping scheme+host+path only. Prevents PII leakage via URL
#          query params and stabilizes duplicate-URL aggregation.
# Input: value (Any) — raw URL scalar from a DataFrame cell
# Output: str — canonical URL (scheme://host/path) or "" for falsy/non-http(s)
# Side Effects: none (pure)
# Business Rules: http/https only; query and fragment always removed; scheme+host lowercased.
# Failure Modes: never raises; invalid/non-http(s) => "".
# LINKS: knowledge-graph.xml#MOD-033, PHASE-20 STEP-2002, verification-plan.xml#V-20-PROCESSED-DIMENSIONS
def _canonical_url(value: Any) -> str:
    if value is None:
        return ""
    try:
        parts = urlsplit(str(value).strip())
    except Exception:
        return ""
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        return ""
    canonical = urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path or "", "", "")
    )
    return canonical


# FUNCTION_CONTRACT: _bounded_list
# Purpose: Deduplicate (preserving first-seen order) and cap a list of scalars to a configured limit.
# Input: values (Iterable[Any]), limit (int) — max items to keep after dedup
# Output: list — order-preserving deduped list, capped to `limit` items
# Side Effects: none (pure)
# Business Rules: empty/falsy values are dropped; first occurrence wins; limit <= 0 => [].
# Failure Modes: never raises.
# LINKS: knowledge-graph.xml#MOD-033, PHASE-20 STEP-2002, verification-plan.xml#V-20-PROCESSED-DIMENSIONS
def _bounded_list(values: Any, limit: int) -> List[Any]:
    if limit <= 0:
        return []
    seen: List[Any] = []
    seen_set: set = set()
    for item in values or []:
        if item is None or (isinstance(item, str) and not item.strip()):
            continue
        marker = item
        if isinstance(item, str):
            marker = item
        elif isinstance(item, dict):
            marker = json.dumps(item, sort_keys=True, ensure_ascii=True)
        if marker in seen_set:
            continue
        seen_set.add(marker)
        seen.append(item)
        if len(seen) >= limit:
            break
    return seen


# DataFrame column-name aliases (case-insensitive exact match) for processed-dimension extraction.
# PHASE-20 / STEP-2002: exact-name matching only — never guess columns by substring.
_QUERY_COLUMN_ALIASES = {"keyword", "search query", "query", "related query"}
_WEBSITE_COLUMN_ALIASES = {"domain", "website", "displayed link", "url", "source url"}
_URL_COLUMN_ALIASES = {"url", "source url", "link"}
_POSITION_COLUMN_ALIASES = {"position", "rank"}
_TITLE_COLUMN_ALIASES = {"title"}


# FUNCTION_CONTRACT: _html_to_text
# Purpose: Strip HTML tags/entities from optional SERP result titles before persistence.
# Input: value (Any)
# Output: str - collapsed plain text, max 80 chars, "" for empty input
# Side Effects: none
# Business Rules: titles are optional; snippets are never persisted; title text is capped to 80 chars.
# Failure Modes: never raises.
# LINKS: knowledge-graph.xml#MOD-033, PHASE-20 STEP-2004, verification-plan.xml#V-20-SERP-TRACKING
def _html_to_text(value: Any) -> str:
    if value is None:
        return ""
    text = re.sub(r"<[^>]+>", " ", str(value))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:80]


# FUNCTION_CONTRACT: _coerce_position
# Purpose: Convert a SERP rank/position scalar to a positive integer.
# Input: value (Any)
# Output: int | None
# Side Effects: none
# Business Rules: non-positive, missing, or malformed positions are ignored.
# Failure Modes: never raises.
# LINKS: knowledge-graph.xml#MOD-033, PHASE-20 STEP-2004, verification-plan.xml#V-20-SERP-TRACKING
def _coerce_position(value: Any) -> Optional[int]:
    try:
        pos = int(float(value))
    except (TypeError, ValueError):
        return None
    return pos if pos > 0 else None


# FUNCTION_CONTRACT: _column_by_alias
# Purpose: Return the original DataFrame column name matching one of several lowercase aliases.
# Input: frame (pd.DataFrame), aliases (set[str])
# Output: str | None
# Side Effects: none
# Business Rules: exact case-insensitive match only; no substring guessing.
# Failure Modes: never raises.
# LINKS: knowledge-graph.xml#MOD-033, PHASE-20 STEP-2002, PHASE-20 STEP-2004
def _column_by_alias(frame: pd.DataFrame, aliases: set) -> Optional[str]:
    lowered = {str(c).strip().lower(): c for c in frame.columns}
    for alias in aliases:
        col = lowered.get(alias)
        if col is not None:
            return col
    return None


# FUNCTION_CONTRACT: _iter_processed_frames
# Purpose: Normalize processed_data shapes from runtime state or history checkpoints into DataFrames.
# Input: processed_data (Any)
# Output: list[pd.DataFrame]
# Side Effects: none
# Business Rules: Accept dict values, a single DataFrame, or list-of-dicts checkpoint payloads.
# Failure Modes: never raises; malformed values are skipped.
# LINKS: knowledge-graph.xml#MOD-033, PHASE-20 STEP-2002
def _iter_processed_frames(processed_data: Any) -> List[pd.DataFrame]:
    if isinstance(processed_data, pd.DataFrame):
        return [processed_data]
    values: List[Any]
    if isinstance(processed_data, dict):
        values = list(processed_data.values())
    elif isinstance(processed_data, list):
        values = [processed_data]
    else:
        return []

    frames: List[pd.DataFrame] = []
    for value in values:
        if isinstance(value, pd.DataFrame):
            frames.append(value)
            continue
        if isinstance(value, list):
            try:
                frame = pd.DataFrame(value)
            except Exception:
                continue
            if not frame.empty:
                frames.append(frame)
    return frames


# FUNCTION_CONTRACT: _extract_processed_dimensions
# Purpose: Extract bounded normalized processed queries, domains, and URLs from processed_data.
# Input: processed_data (Any), per_event_limit (int)
# Output: tuple[list[str], list[str], list[str]]
# Side Effects: none
# Business Rules: exact alias matching only; query/fragment stripped from URLs; no raw text fields read.
# Failure Modes: never raises; malformed frames produce empty lists.
# LINKS: knowledge-graph.xml#MOD-033, PHASE-20 STEP-2002
def _extract_processed_dimensions(
    processed_data: Any,
    per_event_limit: int,
) -> Tuple[List[str], List[str], List[str]]:
    raw_queries: List[Any] = []
    raw_websites: List[Any] = []
    raw_urls: List[Any] = []

    for frame in _iter_processed_frames(processed_data):
        if frame.empty:
            continue
        lowered = {str(c).strip().lower(): c for c in frame.columns}
        for alias in _QUERY_COLUMN_ALIASES:
            col = lowered.get(alias)
            if col is not None:
                raw_queries.extend(frame[col].dropna().tolist())
        for alias in _WEBSITE_COLUMN_ALIASES:
            col = lowered.get(alias)
            if col is not None:
                raw_websites.extend(frame[col].dropna().tolist())
        for alias in _URL_COLUMN_ALIASES:
            col = lowered.get(alias)
            if col is not None:
                raw_urls.extend(frame[col].dropna().tolist())

    queries = _bounded_list(
        [_normalize_query(q) for q in raw_queries],
        per_event_limit,
    )
    websites = _bounded_list(
        [_normalize_domain(w) for w in raw_websites],
        per_event_limit,
    )
    urls = _bounded_list([_canonical_url(u) for u in raw_urls], per_event_limit)
    return queries, websites, urls


# FUNCTION_CONTRACT: record_processed_dimensions_event
# Purpose: Extract privacy-safe processed queries/websites/urls from the post-workflow processed_data
#          DataFrames and persist a single deduped processed_dimensions analytics event per
#          (run_id, event_type, stage). Emits nothing when no recognized columns exist.
# Input: run_id (str), workflow_mode (str), processed_data (dict[str, DataFrame] | None),
#        source (str), stage (str, default "processed_data")
# Output: bool — True if an event was recorded; False if disabled, no recognized columns, or error
# Side Effects: writes one analytics event (under _WRITE_LOCK via record_event) when recognized
#               columns are found
# Business Rules: no-op when analytics.enabled is false; limits read from analytics config
#                 (max_dimension_items_per_event default 250, display_top_n default 20) — never
#                 hardcoded; dedup via deterministic event_id (first-write-wins on
#                 (run_id, event_type, stage)); exact column-name match only (no substring guess);
#                 queries normalized, domains via registrable_domain, urls canonicalized (no
#                 query/fragment).
# Failure Modes: any internal error is swallowed and returns False (analytics must never break the
#                workflow); missing recognized columns => return False, log, emit nothing.
# LINKS: knowledge-graph.xml#MOD-033, PHASE-20 STEP-2002, verification-plan.xml#V-20-PROCESSED-DIMENSIONS
def record_processed_dimensions_event(
    run_id: str,
    workflow_mode: str,
    processed_data: Optional[Dict[str, Any]],
    source: str,
    stage: str = "processed_data",
    config: Optional[Dict[str, Any]] = None,
) -> bool:
    try:
        analytics_cfg = load_config().get("analytics", {})
        if not analytics_cfg.get("enabled", True):
            return False
        if not processed_data:
            return False

        # PHASE-20 / STEP-2002: per-event bound is config-driven. Caller may inject config
        # (tests); otherwise live load_config() is authoritative. Default 250, never hardcoded.
        merged = dict(analytics_cfg)
        if config is not None:
            merged.update(config.get("analytics", {}))
        per_event_limit = _coerce_int(merged.get("max_dimension_items_per_event", 250)) or 250

        queries, websites, urls = _extract_processed_dimensions(
            processed_data,
            per_event_limit,
        )

        if not queries and not websites and not urls:
            # No recognized columns produced any dimension — emit nothing, never guess.
            _analytics_log(
                "analytics record_processed_dimensions_event: no recognized columns; emitting nothing"
            )
            return False

        return record_event(
            {
                # block_analytics_processed_dimensions: deterministic event_id over (run_id,
                # event_type, stage) so repeated calls for the same run dedup first-write-wins.
                "event_id": _fingerprint_values(
                    [run_id, "processed_dimensions", stage]
                ),
                "event_type": "processed_dimensions",
                "run_id": run_id,
                "workflow_mode": workflow_mode,
                "stage": stage,
                "dimensions": {
                    "processed_queries": queries,
                    "processed_websites": websites,
                    "processed_urls": urls,
                },
            }
        )
    except Exception as exc:  # pragma: no cover - analytics must never break the workflow
        _analytics_log(f"analytics record_processed_dimensions_event swallowed error: {exc!r}")
        return False


# FUNCTION_CONTRACT: record_serp_math_snapshot_event
# Purpose: Persist a reduced SERP/math snapshot event for statistics tracking.
# Input: run_id (str), workflow_mode (str), serp_df (pd.DataFrame | None), math_profile (dict | None),
#        config (dict | None), stage (str)
# Output: bool - True when a snapshot event is recorded
# Side Effects: writes one analytics event through record_event when enabled and non-empty
# Business Rules: honors seo_math.enabled and seo_math.track_serp_math_statistics; tracked website/query
#                 lists filter rows when non-empty; stores only domain, canonical_url, position, query,
#                 optional stripped title, and reduced math terms; never persists snippets.
# Failure Modes: swallows internal errors and returns False.
# LINKS: knowledge-graph.xml#MOD-033, PHASE-20 STEP-2004, verification-plan.xml#V-20-SERP-TRACKING
def record_serp_math_snapshot_event(
    run_id: str,
    workflow_mode: str,
    serp_df: Optional[pd.DataFrame],
    math_profile: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
    stage: str = "serp_math",
) -> bool:
    try:
        live_config = load_config()
        analytics_cfg = dict((live_config.get("analytics") or {}))
        seo_math_cfg = dict((live_config.get("seo_math") or {}))
        if config:
            analytics_cfg.update(config.get("analytics", {}) or {})
            seo_math_cfg.update(config.get("seo_math", {}) or {})

        if not analytics_cfg.get("enabled", True):
            return False
        if not seo_math_cfg.get("enabled", True):
            return False
        if not seo_math_cfg.get("track_serp_math_statistics", True):
            return False
        if serp_df is None or not isinstance(serp_df, pd.DataFrame) or serp_df.empty:
            return False

        per_event_limit = _coerce_int(
            analytics_cfg.get("max_dimension_items_per_event", 250)
        ) or 250
        tracked_limit = _coerce_int(analytics_cfg.get("tracked_list_limit", 100)) or 100
        capture_titles = bool(analytics_cfg.get("capture_result_titles", False))

        tracked_domains = set(
            _bounded_list(
                [_normalize_domain(item) for item in seo_math_cfg.get("tracked_websites", [])],
                tracked_limit,
            )
        )
        tracked_queries = set(
            _bounded_list(
                [_normalize_query(item) for item in seo_math_cfg.get("tracked_search_queries", [])],
                tracked_limit,
            )
        )

        query_col = _column_by_alias(serp_df, _QUERY_COLUMN_ALIASES)
        domain_col = _column_by_alias(serp_df, _WEBSITE_COLUMN_ALIASES)
        url_col = _column_by_alias(serp_df, _URL_COLUMN_ALIASES)
        pos_col = _column_by_alias(serp_df, _POSITION_COLUMN_ALIASES)
        title_col = _column_by_alias(serp_df, _TITLE_COLUMN_ALIASES)

        serp_rows: List[Dict[str, Any]] = []
        for _, row in serp_df.iterrows():
            query = _normalize_query(row.get(query_col)) if query_col else ""
            canonical_url = _canonical_url(row.get(url_col)) if url_col else ""
            domain = _normalize_domain(row.get(domain_col)) if domain_col else ""
            if not domain and canonical_url:
                domain = _normalize_domain(canonical_url)
            position = _coerce_position(row.get(pos_col)) if pos_col else None
            if not query or not domain or position is None:
                continue
            if tracked_domains and domain not in tracked_domains:
                continue
            if tracked_queries and query not in tracked_queries:
                continue
            item: Dict[str, Any] = {
                "domain": domain,
                "canonical_url": canonical_url,
                "position": position,
                "query": query,
            }
            if capture_titles and title_col:
                title = _html_to_text(row.get(title_col))
                if title:
                    item["title"] = title
            serp_rows.append(item)
            if len(serp_rows) >= per_event_limit:
                break

        math_terms: List[Dict[str, Any]] = []
        profile = math_profile if isinstance(math_profile, dict) else {}
        for term_obj in profile.get("tfidf_terms", []) or []:
            term = _normalize_query(getattr(term_obj, "term", ""))
            count = _coerce_int(getattr(term_obj, "raw_count", 0))
            if term:
                math_terms.append({"term": term, "count": count})
        for terms in (profile.get("ngrams_by_size", {}) or {}).values():
            for term_obj in terms or []:
                term = _normalize_query(getattr(term_obj, "ngram", ""))
                count = _coerce_int(getattr(term_obj, "raw_count", 0))
                if term:
                    math_terms.append({"term": term, "count": count})
        for term_obj in profile.get("cooccurrence_terms", []) or []:
            term = _normalize_query(getattr(term_obj, "term", ""))
            count = _coerce_int(getattr(term_obj, "cooccurrence_count", 0))
            if term:
                math_terms.append({"term": term, "count": count})
        math_terms = _bounded_list(math_terms, per_event_limit)

        if not serp_rows and not math_terms:
            return False

        return record_event(
            {
                "event_id": _fingerprint_values([run_id, "serp_math_snapshot", stage]),
                "event_type": "serp_math_snapshot",
                "run_id": run_id,
                "workflow_mode": workflow_mode,
                "stage": stage,
                "dimensions": {
                    "serp_results": serp_rows,
                    "math_terms": math_terms,
                },
            }
        )
    except Exception as exc:  # pragma: no cover - analytics must never break workflows
        _analytics_log(f"analytics record_serp_math_snapshot_event swallowed error: {exc!r}")
        return False


# FUNCTION_CONTRACT: _build_overview
# Purpose: Compute the overview metrics block of the statistics summary.
# Input: events (list[dict])
# Output: dict with total_runs, success_rate, workflows_used, cache_hit_rate, total_urls,
#         total_keywords, total_rows, total_llm_calls, total_tokens, favorite_provider
# Side Effects: none
# Business Rules: total_runs = workflow_completed events; success_rate over workflow_completed;
#                 cache_hit_rate = hits/cache events; favorite_provider by successful llm_call then total.
# Failure Modes: never raises.
# LINKS: knowledge-graph.xml#MOD-033
def _build_overview(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    workflow_runs = [e for e in events if e.get("event_type") == "workflow_completed"]
    total_runs = len(workflow_runs)
    successful_runs = sum(1 for e in workflow_runs if e.get("status") == "success")
    success_rate = (successful_runs / total_runs) if total_runs else 0.0
    # workflows_used: distinct workflow modes seen across ALL events (not just completed runs),
    # since a workflow may be observed via llm_call/other stage events even without a completed marker.
    workflows_used = len({e.get("workflow_mode") for e in events if e.get("workflow_mode")})

    cache_events = [e for e in events if isinstance(e.get("cache"), dict)]
    cache_hits = sum(1 for e in cache_events if e.get("cache", {}).get("hit"))
    cache_hit_rate = (cache_hits / len(cache_events)) if cache_events else 0.0

    total_urls = sum(_coerce_int(e.get("counts", {}).get("urls")) for e in workflow_runs if isinstance(e.get("counts"), dict))
    total_keywords = sum(
        _coerce_int(e.get("counts", {}).get("keywords")) for e in workflow_runs if isinstance(e.get("counts"), dict)
    )
    total_rows = sum(_coerce_int(e.get("counts", {}).get("rows")) for e in workflow_runs if isinstance(e.get("counts"), dict))

    llm_calls = [e for e in events if e.get("event_type") == "llm_call"]
    total_llm_calls = len(llm_calls)
    total_tokens = sum(
        _coerce_int(e.get("tokens", {}).get("total_tokens"))
        for e in events
        if isinstance(e.get("tokens"), dict) and e.get("tokens", {}).get("total_tokens") is not None
    )

    favorite_provider = _select_favorite_provider(llm_calls)

    return {
        "total_runs": total_runs,
        "success_rate": success_rate,
        "workflows_used": workflows_used,
        "cache_hit_rate": cache_hit_rate,
        "total_urls": total_urls,
        "total_keywords": total_keywords,
        "total_rows": total_rows,
        "total_llm_calls": total_llm_calls,
        "total_tokens": total_tokens,
        "favorite_provider": favorite_provider,
    }


def _select_favorite_provider(llm_calls: List[Dict[str, Any]]) -> Optional[str]:
    # Favorite by successful calls first, then total calls as tie-break.
    success_counts: Dict[str, int] = {}
    total_counts: Dict[str, int] = {}
    for event in llm_calls:
        provider = str(event.get("provider") or "")
        if not provider:
            continue
        total_counts[provider] = total_counts.get(provider, 0) + 1
        if event.get("status") == "success":
            success_counts[provider] = success_counts.get(provider, 0) + 1
    if not total_counts:
        return None
    best = max(
        total_counts.keys(),
        key=lambda p: (success_counts.get(p, 0), total_counts.get(p, 0)),
    )
    return best


# FUNCTION_CONTRACT: _build_provider_summary
# Purpose: Build DataFrame-compatible provider summary rows.
# Input: events (list[dict])
# Output: list[dict] — each {provider, model, calls, success, errors, total_tokens, avg_latency_ms}
# Side Effects: none
# Business Rules: aggregates llm_call events by (provider, model); avg latency over calls with duration.
# Failure Modes: never raises.
# LINKS: knowledge-graph.xml#MOD-033
def _build_provider_summary(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for event in events:
        if event.get("event_type") != "llm_call":
            continue
        provider = str(event.get("provider") or "")
        model = str(event.get("model") or "")
        key = (provider, model)
        bucket = groups.setdefault(
            key,
            {"provider": provider, "model": model, "calls": 0, "success": 0, "errors": 0,
             "total_tokens": 0, "latency_sum": 0, "latency_count": 0},
        )
        bucket["calls"] += 1
        if event.get("status") == "success":
            bucket["success"] += 1
        else:
            bucket["errors"] += 1
        if isinstance(event.get("tokens"), dict):
            bucket["total_tokens"] += _coerce_int(event["tokens"].get("total_tokens"))
        duration = event.get("duration_ms")
        if duration is not None:
            bucket["latency_sum"] += _coerce_int(duration)
            bucket["latency_count"] += 1

    rows: List[Dict[str, Any]] = []
    for bucket in groups.values():
        avg_latency = (
            bucket["latency_sum"] / bucket["latency_count"]
            if bucket["latency_count"]
            else 0
        )
        rows.append(
            {
                "provider": bucket["provider"],
                "model": bucket["model"],
                "calls": bucket["calls"],
                "success": bucket["success"],
                "errors": bucket["errors"],
                "total_tokens": bucket["total_tokens"],
                "avg_latency_ms": avg_latency,
            }
        )
    rows.sort(key=lambda r: (r["provider"], r["model"]))
    return rows


# FUNCTION_CONTRACT: _build_token_summary
# Purpose: Sum present token fields across all events carrying a tokens sub-dict.
# Input: events (list[dict])
# Output: dict {prompt_tokens, completion_tokens, total_tokens} — canonical producer key names.
# Side Effects: none
# Business Rules: reads the canonical producer keys (prompt_tokens/completion_tokens/total_tokens)
#                 that utils.llm_handler._extract_usage_tokens emits; sums only present values; the
#                 string "unknown" sentinel (missing usage) is skipped by the isinstance(tokens, dict)
#                 guard so it never breaks aggregation; total_tokens overview uses the same present-only sum.
# Failure Modes: never raises.
# LINKS: knowledge-graph.xml#MOD-033, PLAN 19 Task 5
def _build_token_summary(events: List[Dict[str, Any]], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    prompt = completion = total = 0
    llm_call_count = known_token_calls = unknown_token_calls = 0
    for event in events:
        if event.get("event_type") != "llm_call":
            continue
        llm_call_count += 1
        tokens = event.get("tokens")
        if tokens == "unknown":
            unknown_token_calls += 1
            continue
        if not isinstance(tokens, dict):
            continue
        known_token_calls += 1
        if tokens.get("prompt_tokens") is not None:
            prompt += _coerce_int(tokens.get("prompt_tokens"))
        if tokens.get("completion_tokens") is not None:
            completion += _coerce_int(tokens.get("completion_tokens"))
        if tokens.get("total_tokens") is not None:
            total += _coerce_int(tokens.get("total_tokens"))
    try:
        if config is None:
            config = load_config()
        capture_tokens_enabled = bool(config.get("analytics", {}).get("capture_tokens", True))
    except Exception:
        capture_tokens_enabled = True
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "llm_call_count": llm_call_count,
        "known_token_calls": known_token_calls,
        "unknown_token_calls": unknown_token_calls,
        "capture_tokens_enabled": capture_tokens_enabled,
    }


# FUNCTION_CONTRACT: _build_time_heatmap
# Purpose: Build the weekday x hour heatmap grid (all 7x24 cells, zero-filled).
# Input: events (list[dict])
# Output: list[dict] — each {weekday, hour, count}
# Side Effects: none
# Business Rules: bucket by created_at local weekday() and hour; always emit every (weekday,hour) cell.
# Failure Modes: never raises; unparseable timestamps skipped.
# LINKS: knowledge-graph.xml#MOD-033
def _build_time_heatmap(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    counts: Dict[Tuple[int, int], int] = {}
    for event in events:
        created = _parse_created_at(event.get("created_at"))
        if created is None:
            continue
        key = (created.weekday(), created.hour)
        counts[key] = counts.get(key, 0) + 1

    cells: List[Dict[str, Any]] = []
    for weekday in range(7):
        for hour in range(24):
            cells.append({"weekday": weekday, "hour": hour, "count": counts.get((weekday, hour), 0)})
    return cells


# FUNCTION_CONTRACT: _build_workflow_funnel
# Purpose: Count events matching each workflow funnel stage.
# Input: events (list[dict])
# Output: list[dict] — each {stage, count}
# Side Effects: none
# Business Rules: for each (stage_label, marker_event_type, marker_stage) triple, count events where
#                 event_type == marker_event_type AND (marker_stage is None OR event.stage == marker_stage).
#                 Stages with no matching event report 0 (never invented).
# Failure Modes: never raises.
# LINKS: knowledge-graph.xml#MOD-033
def _build_workflow_funnel(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    funnel: List[Dict[str, Any]] = []
    for stage, marker_type, marker_stage in _FUNNEL_STAGES:
        count = 0
        for event in events:
            event_type = str(event.get("event_type") or "")
            if event_type != marker_type:
                continue
            if marker_stage is not None and str(event.get("stage") or "") != marker_stage:
                continue
            count += 1
        funnel.append({"stage": stage, "count": count})
    return funnel


# FUNCTION_CONTRACT: _build_repeated_patterns
# Purpose: Collect input signatures, keyword signatures, and workflow/provider/model combos with >=2 uses.
# Input: events (list[dict])
# Output: dict {input_signatures, keywords, workflow_combos}
# Side Effects: none
# Business Rules: repeated = at least 2 occurrences.
# Failure Modes: never raises.
# LINKS: knowledge-graph.xml#MOD-033
def _build_repeated_patterns(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    input_counts: Dict[str, int] = {}
    keyword_counts: Dict[str, int] = {}
    combo_counts: Dict[str, int] = {}

    for event in events:
        fingerprints = event.get("fingerprints")
        if isinstance(fingerprints, dict):
            sig = fingerprints.get("input_signature")
            if isinstance(sig, str) and sig:
                input_counts[sig] = input_counts.get(sig, 0) + 1
            kw = fingerprints.get("keyword_signature")
            if isinstance(kw, str) and kw:
                keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
        combo_key = "|".join(
            [
                str(event.get("workflow_mode") or ""),
                str(event.get("provider") or ""),
                str(event.get("model") or ""),
            ]
        )
        combo_counts[combo_key] = combo_counts.get(combo_key, 0) + 1

    workflow_combos: List[Dict[str, Any]] = []
    for combo_key, count in combo_counts.items():
        if count < 2:
            continue
        parts = combo_key.split("|")
        workflow_combos.append(
            {
                "workflow_mode": parts[0] if len(parts) > 0 else "",
                "provider": parts[1] if len(parts) > 1 else "",
                "model": parts[2] if len(parts) > 2 else "",
                "count": count,
            }
        )

    return {
        "input_signatures": [sig for sig, c in input_counts.items() if c >= 2],
        "keywords": [kw for kw, c in keyword_counts.items() if c >= 2],
        "workflow_combos": workflow_combos,
    }


# FUNCTION_CONTRACT: _build_processed_summary
# Purpose: Aggregate processed_dimensions events into bounded top-N lists of queries/websites/urls,
#          each row carrying {value, count, workflows} (workflows = sorted unique workflow_modes).
# Input: events (list[dict]), config (dict | None) — display_top_n read from analytics config
# Output: dict — {"top_queries": [...], "top_websites": [...], "top_urls": [...]}
# Side Effects: none (pure aggregation over already-recorded normalized dimensions)
# Business Rules: values are already normalized at record time (queries lowercased, domains via
#                 registrable_domain, urls canonicalized); count per distinct value across events;
#                 workflows is the sorted unique set of workflow_modes that produced the value;
#                 each list bounded by analytics.display_top_n (default 20, never hardcoded);
#                 empty buckets => [].
# Failure Modes: never raises; malformed dimensions => skipped.
# LINKS: knowledge-graph.xml#MOD-033, PHASE-20 STEP-2002, verification-plan.xml#V-20-PROCESSED-DIMENSIONS
def _build_processed_summary(
    events: List[Dict[str, Any]], config: Optional[Dict[str, Any]] = None
) -> Dict[str, List[Dict[str, Any]]]:
    try:
        if config is None:
            config = load_config()
        display_top_n = _coerce_int(config.get("analytics", {}).get("display_top_n", 20)) or 20
    except Exception:
        display_top_n = 20

    # bucket_key -> {"count": int, "workflows": set}
    buckets: Dict[str, Dict[str, Dict[str, Any]]] = {
        "top_queries": {},
        "top_websites": {},
        "top_urls": {},
    }
    bucket_field = {
        "top_queries": "processed_queries",
        "top_websites": "processed_websites",
        "top_urls": "processed_urls",
    }

    for event in events:
        if event.get("event_type") != "processed_dimensions":
            continue
        dims = event.get("dimensions")
        if not isinstance(dims, dict):
            continue
        workflow_mode = str(event.get("workflow_mode") or "")
        for bucket_name, field_name in bucket_field.items():
            values = dims.get(field_name)
            if not isinstance(values, list):
                continue
            bucket = buckets[bucket_name]
            for raw in values:
                # Normalize at aggregation time too (defensive): events may be built directly
                # rather than via the recorder, so canonicalize here so duplicates aggregate.
                if field_name == "processed_queries":
                    value = _normalize_query(raw)
                elif field_name == "processed_websites":
                    value = _normalize_domain(raw)
                else:
                    value = _canonical_url(raw)
                if not value:
                    continue
                entry = bucket.get(value)
                if entry is None:
                    bucket[value] = {"count": 1, "workflows": {workflow_mode} if workflow_mode else set()}
                else:
                    entry["count"] += 1
                    if workflow_mode:
                        entry["workflows"].add(workflow_mode)

    result: Dict[str, List[Dict[str, Any]]] = {}
    for bucket_name in ("top_queries", "top_websites", "top_urls"):
        bucket = buckets[bucket_name]
        # Sort by count desc, then value asc for determinism; bound to display_top_n.
        ordered = sorted(bucket.items(), key=lambda kv: (-kv[1]["count"], kv[0]))
        rows = [
            {"value": value, "count": entry["count"], "workflows": sorted(entry["workflows"])}
            for value, entry in ordered[:display_top_n]
        ]
        result[bucket_name] = rows
    return result


# FUNCTION_CONTRACT: _build_serp_tracking_summary
# Purpose: Aggregate serp_math_snapshot events into SERP tracking leaderboards.
# Input: events (list[dict]), config (dict | None)
# Output: dict with top_websites, tracked_queries, top_keywords, top_results lists
# Side Effects: none
# Business Rules: display limit comes from analytics.display_top_n; positions are averaged from
#                 reduced SERP rows; no snippets/raw results are emitted.
# Failure Modes: never raises; malformed snapshot rows are skipped.
# LINKS: knowledge-graph.xml#MOD-033, PHASE-20 STEP-2004, verification-plan.xml#V-20-SERP-TRACKING
def _build_serp_tracking_summary(
    events: List[Dict[str, Any]], config: Optional[Dict[str, Any]] = None
) -> Dict[str, List[Dict[str, Any]]]:
    try:
        if config is None:
            config = load_config()
        display_top_n = _coerce_int(config.get("analytics", {}).get("display_top_n", 20)) or 20
    except Exception:
        display_top_n = 20

    domain_counts: Dict[str, Dict[str, Any]] = {}
    query_counts: Dict[str, Dict[str, Any]] = {}
    keyword_counts: Dict[str, int] = {}
    result_rows: List[Dict[str, Any]] = []

    for event in events:
        if event.get("event_type") != "serp_math_snapshot":
            continue
        dims = event.get("dimensions")
        if not isinstance(dims, dict):
            continue

        for raw_row in dims.get("serp_results", []) or []:
            if not isinstance(raw_row, dict):
                continue
            domain = _normalize_domain(raw_row.get("domain"))
            query = _normalize_query(raw_row.get("query"))
            position = _coerce_position(raw_row.get("position"))
            canonical_url = _canonical_url(raw_row.get("canonical_url"))
            if not domain or not query or position is None:
                continue

            domain_entry = domain_counts.setdefault(domain, {"count": 0, "position_sum": 0})
            domain_entry["count"] += 1
            domain_entry["position_sum"] += position

            query_entry = query_counts.setdefault(query, {"result_count": 0, "position_sum": 0})
            query_entry["result_count"] += 1
            query_entry["position_sum"] += position

            top_result = {
                "domain": domain,
                "canonical_url": canonical_url,
                "position": position,
                "query": query,
            }
            title = _html_to_text(raw_row.get("title"))
            if title:
                top_result["title"] = title
            result_rows.append(top_result)

        for raw_term in dims.get("math_terms", []) or []:
            if not isinstance(raw_term, dict):
                continue
            term = _normalize_query(raw_term.get("term"))
            if not term:
                continue
            keyword_counts[term] = keyword_counts.get(term, 0) + _coerce_int(
                raw_term.get("count")
            )

    top_websites = [
        {
            "domain": domain,
            "count": entry["count"],
            "avg_position": round(entry["position_sum"] / entry["count"], 2),
        }
        for domain, entry in sorted(
            domain_counts.items(), key=lambda kv: (-kv[1]["count"], kv[0])
        )[:display_top_n]
    ]
    tracked_queries = [
        {
            "query": query,
            "result_count": entry["result_count"],
            "avg_position": round(entry["position_sum"] / entry["result_count"], 2),
        }
        for query, entry in sorted(
            query_counts.items(), key=lambda kv: (-kv[1]["result_count"], kv[0])
        )[:display_top_n]
    ]
    top_keywords = [
        {"term": term, "count": count}
        for term, count in sorted(
            keyword_counts.items(), key=lambda kv: (-kv[1], kv[0])
        )[:display_top_n]
    ]
    top_results = sorted(
        result_rows,
        key=lambda row: (
            _coerce_position(row.get("position")) or 999999,
            str(row.get("domain", "")),
            str(row.get("canonical_url", "")),
        ),
    )[:display_top_n]

    return {
        "top_websites": top_websites,
        "tracked_queries": tracked_queries,
        "top_keywords": top_keywords,
        "top_results": top_results,
    }


# FUNCTION_CONTRACT: _build_insights
# Purpose: Emit deterministic (template_key, params) insight tuples; never free-form prose; never
#          hallucinate fractions from zero denominators; empty when data is sparse.
# Input: events (list[dict]), overview (dict), provider_rows (list[dict])
# Output: list[tuple[str, dict]]
# Side Effects: none
# Business Rules: each insight uses an insight_* template key; share insights only when a real fraction > 0.
# Failure Modes: never raises.
# LINKS: knowledge-graph.xml#MOD-033
def _build_insights(
    events: List[Dict[str, Any]],
    overview: Dict[str, Any],
    provider_rows: List[Dict[str, Any]],
) -> List[Tuple[str, Dict[str, Any]]]:
    insights: List[Tuple[str, Dict[str, Any]]] = []

    # Favorite provider share: only when there is at least one llm_call and a clear favorite.
    total_llm_calls = overview.get("total_llm_calls", 0)
    favorite = overview.get("favorite_provider")
    if total_llm_calls and favorite:
        favorite_calls = sum(
            row["calls"] for row in provider_rows if row["provider"] == favorite
        )
        if favorite_calls > 0:
            pct = round(favorite_calls * 100 / total_llm_calls)
            insights.append(("insight_provider_share", {"provider": favorite, "pct": pct}))

    # Cache hit insight: only when there are cache events.
    cache_events = [e for e in events if isinstance(e.get("cache"), dict)]
    if cache_events:
        rate = overview.get("cache_hit_rate", 0.0)
        if rate > 0:
            insights.append(
                ("insight_cache_hit_rate", {"pct": round(rate * 100)})
            )

    # Peak heatmap cell: only when there is at least one timestamped event.
    peak = None
    peak_count = 0
    cell_counts: Dict[Tuple[int, int], int] = {}
    for event in events:
        created = _parse_created_at(event.get("created_at"))
        if created is None:
            continue
        key = (created.weekday(), created.hour)
        cell_counts[key] = cell_counts.get(key, 0) + 1
        if cell_counts[key] > peak_count:
            peak_count = cell_counts[key]
            peak = key
    if peak is not None and peak_count > 0:
        insights.append(
            (
                "insight_peak_time",
                {"weekday": peak[0], "hour": peak[1], "count": peak_count},
            )
        )

    return insights


# FUNCTION_CONTRACT: build_statistics_summary
# Purpose: Compute the full statistics summary dict (overview, providers, tokens, heatmap, funnel,
#          repeated patterns, insights, diagnostics) from a list of analytics events. When
#          analytics.hide_fixture_events is enabled (default true), known test/manual-run fixture
#          events are excluded from the aggregate views (view-only — never deleted from the store).
# Input: events (list[dict]), config (dict | None = None) — when config is None, load_config() is
#        read live to resolve analytics.hide_fixture_events. Backward compatible: callers passing
#        only events still work and get the default hide behavior.
# Output: dict — {overview, provider_summary, token_summary, time_heatmap, workflow_funnel,
#                 repeated_patterns, insights, diagnostics}
# Side Effects: none (pure aggregation; may read load_config() when config is None)
# Business Rules: block_summary_building — real computed values, not placeholders; heatmap always full
#                 7x24 grid; insights are deterministic template tuples; empty data => [] insights.
#                 Fixture filtering is VIEW-ONLY: the on-disk store is never modified during summary
#                 building; the diagnostics.hidden_fixture_events count exposes how many were hidden.
# Failure Modes: never raises; sparse data => zeros/empty.
# LINKS: knowledge-graph.xml#MOD-033, PHASE-20 STEP-2001, verification-plan.xml#V-19-ANALYTICS-STORE, verification-plan.xml#V-20-ANALYTICS-TEST-ISOLATION
def build_statistics_summary(events: list[dict], config: Optional[dict] = None) -> dict:
    # block_summary_building: pure functions, real math, no placeholders.
    safe_events: List[Dict[str, Any]] = [e for e in (events or []) if isinstance(e, dict)]
    hide = _hide_fixture_events_enabled(config)
    filtered_events = _filter_fixture_events(safe_events, hide)

    overview = _build_overview(filtered_events)
    provider_rows = _build_provider_summary(filtered_events)
    token_summary = _build_token_summary(filtered_events, config)
    heatmap = _build_time_heatmap(filtered_events)
    funnel = _build_workflow_funnel(filtered_events)
    repeated = _build_repeated_patterns(filtered_events)
    insights = _build_insights(filtered_events, overview, provider_rows)
    diagnostics = _build_diagnostics(safe_events, filtered_events, hide)
    processed = _build_processed_summary(filtered_events, config)
    serp_tracking = _build_serp_tracking_summary(filtered_events, config)

    return {
        "overview": overview,
        "provider_summary": provider_rows,
        "token_summary": token_summary,
        "time_heatmap": heatmap,
        "workflow_funnel": funnel,
        "repeated_patterns": repeated,
        "insights": insights,
        "diagnostics": diagnostics,
        "processed_summary": processed,
        "serp_tracking": serp_tracking,
    }


# FUNCTION_CONTRACT: build_statistics_export_sheets
# Purpose: Build CSV-exportable pandas DataFrames for each dashboard aggregate (providers,
#          funnel, heatmap, tokens) from a statistics summary dict. A pure function with no
#          side effects; always returns all four well-formed frames even when the summary is
#          empty so the dashboard export buttons never raise on sparse data.
# Input: summary (dict) — the dict produced by build_statistics_summary()
# Output: dict[str, pd.DataFrame] with stable lowercase snake_case keys:
#         "providers", "funnel", "heatmap", "tokens". Export frames use machine/stable column
#         names (NOT localized): providers -> provider/model/calls/success/errors/total_tokens/
#         avg_latency_ms; funnel -> stage/count; heatmap -> weekday/hour/count (long form);
#         tokens -> prompt_tokens/completion_tokens/total_tokens (single row).
# Side Effects: none (pure transformation; never reads/writes files or config).
# Business Rules: All four keys always present. Empty summary => empty-but-well-formed frames
#                 (correct columns, 0 rows), except heatmap which always carries the full
#                 7*24 zero-filled long-form grid. Canonical token keys (prompt_tokens/
#                 completion_tokens/total_tokens) match the producer (utils.llm_handler).
# Failure Modes: never raises; missing/None summary blocks default to empty well-formed frames.
# LINKS: knowledge-graph.xml#MOD-033, PLAN 19 Task 8, verification-plan.xml#V-19-STATISTICS-DASHBOARD
def build_statistics_export_sheets(summary: dict) -> dict:
    safe = summary if isinstance(summary, dict) else {}

    provider_rows = safe.get("provider_summary", [])
    if not isinstance(provider_rows, list):
        provider_rows = []
    providers_frame = pd.DataFrame(
        provider_rows,
        columns=[
            "provider",
            "model",
            "calls",
            "success",
            "errors",
            "total_tokens",
            "avg_latency_ms",
        ],
    )

    funnel_rows = safe.get("workflow_funnel", [])
    if not isinstance(funnel_rows, list):
        funnel_rows = []
    funnel_frame = pd.DataFrame(funnel_rows, columns=["stage", "count"])

    heatmap_rows = safe.get("time_heatmap", [])
    if not isinstance(heatmap_rows, list):
        heatmap_rows = []
    # Heatmap long form: always 7*24 cells. If the summary provided a full grid use it,
    # otherwise synthesize a zero-filled grid so the export is never empty/malformed.
    if len(heatmap_rows) == 7 * 24:
        heatmap_frame = pd.DataFrame(heatmap_rows, columns=["weekday", "hour", "count"])
    else:
        heatmap_frame = pd.DataFrame(
            [
                {"weekday": w, "hour": h, "count": 0}
                for w in range(7)
                for h in range(24)
            ],
            columns=["weekday", "hour", "count"],
        )

    token_summary = safe.get("token_summary", {})
    if not isinstance(token_summary, dict):
        token_summary = {}
    tokens_frame = pd.DataFrame(
        [
            {
                "prompt_tokens": token_summary.get("prompt_tokens", 0),
                "completion_tokens": token_summary.get("completion_tokens", 0),
                "total_tokens": token_summary.get("total_tokens", 0),
            }
        ],
        columns=["prompt_tokens", "completion_tokens", "total_tokens"],
    )

    # PHASE-20 / STEP-2002: processed-dimensions export — long form with a `dimension` discriminator
    # column (query/website/url) so all three top-N lists share one stable frame. No raw text.
    processed_summary = safe.get("processed_summary", {})
    if not isinstance(processed_summary, dict):
        processed_summary = {}
    processed_records = []
    for dim_name, bucket in (
        ("query", processed_summary.get("top_queries", [])),
        ("website", processed_summary.get("top_websites", [])),
        ("url", processed_summary.get("top_urls", [])),
    ):
        if not isinstance(bucket, list):
            continue
        for row in bucket:
            if not isinstance(row, dict):
                continue
            workflows = row.get("workflows", [])
            workflows_str = ",".join(workflows) if isinstance(workflows, list) else ""
            processed_records.append(
                {
                    "kind": dim_name,
                    "value": row.get("value", ""),
                    "count": row.get("count", 0),
                    "workflows": workflows_str,
                }
            )
    processed_frame = pd.DataFrame(
        processed_records, columns=["kind", "value", "count", "workflows"]
    )

    serp_tracking = safe.get("serp_tracking", {})
    if not isinstance(serp_tracking, dict):
        serp_tracking = {}
    serp_records: List[Dict[str, Any]] = []
    for row in serp_tracking.get("top_websites", []) or []:
        if isinstance(row, dict):
            serp_records.append(
                {
                    "section": "top_websites",
                    "domain": row.get("domain", ""),
                    "canonical_url": "",
                    "position": "",
                    "query": "",
                    "title": "",
                    "term": "",
                    "count": row.get("count", 0),
                    "result_count": "",
                    "avg_position": row.get("avg_position", 0),
                }
            )
    for row in serp_tracking.get("tracked_queries", []) or []:
        if isinstance(row, dict):
            serp_records.append(
                {
                    "section": "tracked_queries",
                    "domain": "",
                    "canonical_url": "",
                    "position": "",
                    "query": row.get("query", ""),
                    "title": "",
                    "term": "",
                    "count": "",
                    "result_count": row.get("result_count", 0),
                    "avg_position": row.get("avg_position", 0),
                }
            )
    for row in serp_tracking.get("top_keywords", []) or []:
        if isinstance(row, dict):
            serp_records.append(
                {
                    "section": "top_keywords",
                    "domain": "",
                    "canonical_url": "",
                    "position": "",
                    "query": "",
                    "title": "",
                    "term": row.get("term", ""),
                    "count": row.get("count", 0),
                    "result_count": "",
                    "avg_position": "",
                }
            )
    for row in serp_tracking.get("top_results", []) or []:
        if isinstance(row, dict):
            serp_records.append(
                {
                    "section": "top_results",
                    "domain": row.get("domain", ""),
                    "canonical_url": row.get("canonical_url", ""),
                    "position": row.get("position", ""),
                    "query": row.get("query", ""),
                    "title": row.get("title", ""),
                    "term": "",
                    "count": "",
                    "result_count": "",
                    "avg_position": "",
                }
            )
    serp_tracking_frame = pd.DataFrame(
        serp_records,
        columns=[
            "section",
            "domain",
            "canonical_url",
            "position",
            "query",
            "title",
            "term",
            "count",
            "result_count",
            "avg_position",
        ],
    )

    return {
        "providers": providers_frame,
        "funnel": funnel_frame,
        "heatmap": heatmap_frame,
        "tokens": tokens_frame,
        "processed": processed_frame,
        "serp_tracking": serp_tracking_frame,
    }
