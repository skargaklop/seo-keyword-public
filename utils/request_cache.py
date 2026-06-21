# MODULE_CONTRACT: utils/request_cache
# Purpose: Persistent cache for API and analysis requests with stable keys and history integration (Phase 10 Task 5).
# Rationale: Reduce redundant API calls and keep normalized cache records inside the shared history store.
# Dependencies: json, hashlib, dataclasses, datetime, decimal, math, re, pathlib, typing, config.settings, utils.history, utils.logger
# Exports: CACHE_KINDS, CACHE_TTL_DEFAULT_HOURS, CACHE_KIND_TTL, RequestCache, build_cache_key, build_settings_hash, normalize_params_for_cache, get_cache_ttl_hours, is_cache_relevant_setting
# LINKS: requirements.xml#UC-001, development-plan.xml#MOD-014, PLAN 10-02 Task 5
# MODULE_MAP: utils/request_cache.py
# Public Functions: build_cache_key, build_settings_hash, normalize_params_for_cache, get_cache_ttl_hours, is_cache_relevant_setting
# Private Helpers: _extract_cache_relevant_settings, _canonicalize_for_key, _jsonable_value, _serialize_result_value, _coerce_shared_value, _coerce_object_value, _normalize_recursive_value, _build_cache_record, _is_secret_key, _read_history_bundle, _write_history_bundle, _upsert_cache_record
# Key Semantic Blocks: block_cache_key_builder, block_request_settings_hash, block_request_cache_lookup, block_request_cache_write, block_request_cache_migration
# Critical Flows: cache lookup must be stable across runs; migration must preserve old history; settings hash only includes analysis-affecting settings
# Verification: python -m py_compile, python -m ruff check ., python -m pytest -q tests/test_request_cache.py
# CHANGE_SUMMARY: Reworked the request cache to support safe serialization, secret-safe cache keys, overwrite semantics, persisted hit counts, and history-backed cache records.

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Set

from config.settings import config
from utils.history import HISTORY_FILE, HISTORY_SCHEMA_VERSION, migrate_history_data
from utils.logger import logger

try:
    import pandas as pd
except Exception:  # pragma: no cover - optional dependency guard
    pd = None


CACHE_KINDS: Set[str] = {
    "serp",
    "ads",
    "llm_extract",
    "llm_generate",
    "crawl",
    "math",
    "trends",
    "model_fetch",
}

CACHE_TTL_DEFAULT_HOURS: int = 168
CACHE_KIND_TTL: Dict[str, int] = {
    "serp": 168,
    "ads": 168,
    "llm_extract": 720,
    "llm_generate": 720,
    "crawl": 168,
    "math": 168,
    "trends": 24,
    "model_fetch": 720,
}

CACHE_RELEVANT_SETTINGS: Set[str] = {
    "seo_math.analyze_bm25f",
    "seo_math.bm25f_params",
    "seo_math.field_weights",
    "seo_math.signals",
    "llm.provider",
    "llm.model",
    "cache",
    "google_trends",
}

CACHE_SCHEMA_VERSION: int = 2
_TRENDS_CACHE_MIGRATED_KEY = "_trends_schema_v2_migrated"
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


# Purpose:  split key tokens implementation
def _split_key_tokens(key: str) -> List[str]:
    normalized = re.sub(r"(?<!^)(?=[A-Z])", "_", str(key))
    normalized = normalized.replace("-", "_").replace(".", "_")
    return [token for token in re.split(r"[^a-zA-Z0-9]+", normalized.lower()) if token]


# Purpose:  is secret key implementation
def _is_secret_key(key: str) -> bool:
    tokens = _split_key_tokens(key)
    if not tokens:
        return False
    joined = "".join(tokens)
    return any(token in _SECRET_KEY_TOKENS for token in tokens) or joined in _SECRET_KEY_TOKENS


# Purpose:  sort key implementation
def _sort_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


# Purpose:  shared recursive scalar coercion implementation
_NO_VALUE = object()


def _coerce_shared_value(value: Any, recurse: Callable[[Any], Any]) -> Any:
    if value is None:
        return None

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, timedelta):
        return value.total_seconds()

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")

    if dataclasses.is_dataclass(value):
        return recurse(dataclasses.asdict(value))

    return _NO_VALUE


# Purpose:  shared recursive object coercion implementation
def _coerce_object_value(value: Any, recurse: Callable[[Any], Any]) -> Any:
    if hasattr(value, "to_dict") and callable(getattr(value, "to_dict")):
        try:
            return recurse(value.to_dict())
        except Exception:
            pass

    if hasattr(value, "model_dump") and callable(getattr(value, "model_dump")):
        try:
            return recurse(value.model_dump())
        except Exception:
            pass

    if hasattr(value, "_asdict") and callable(getattr(value, "_asdict")):
        try:
            return recurse(value._asdict())
        except Exception:
            pass

    if hasattr(value, "__dict__") and not isinstance(value, type):
        public_attrs = {
            key: getattr(value, key)
            for key in dir(value)
            if not key.startswith("_")
            and not callable(getattr(value, key, None))
        }
        if public_attrs:
            return recurse(public_attrs)

    if hasattr(value, "item") and callable(getattr(value, "item")):
        try:
            return recurse(value.item())
        except Exception:
            pass

    return _NO_VALUE


# Purpose:  shared recursive normalization implementation
def _normalize_recursive_value(
    value: Any,
    recurse: Callable[[Any], Any],
    *,
    transform_scalar: Callable[[Any], Any],
    transform_key: Callable[[str], str] = str,
    skip_secret_keys: bool = False,
    sort_lists: bool = False,
    sort_sets: bool = True,
) -> Any:
    if isinstance(value, dict):
        normalized: Dict[str, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            if skip_secret_keys and _is_secret_key(key_str):
                continue
            normalized[transform_key(key_str)] = recurse(item)
        return normalized

    if isinstance(value, (list, tuple)):
        items = [recurse(item) for item in value]
        if sort_lists:
            try:
                return sorted(items, key=_sort_key)
            except TypeError:
                return items
        return items

    if isinstance(value, (set, frozenset)):
        items = [recurse(item) for item in value]
        if sort_sets:
            try:
                return sorted(items, key=_sort_key)
            except TypeError:
                return items
        return items

    object_value = _coerce_object_value(value, recurse)
    if object_value is not _NO_VALUE:
        return object_value

    return transform_scalar(value)


# Purpose:  jsonable value implementation
def _jsonable_value(value: Any) -> Any:
    if isinstance(value, (str, int, bool)):
        return value

    shared_value = _coerce_shared_value(value, _jsonable_value)
    if shared_value is not _NO_VALUE:
        return shared_value

    if pd is not None:
        if isinstance(value, pd.DataFrame):
            columns = [str(column) for column in value.columns.tolist()]
            records: List[Dict[str, Any]] = []
            for row in value.to_dict(orient="records"):
                records.append({str(key): _jsonable_value(cell) for key, cell in row.items()})
            return {
                "columns": columns,
                "data": records,
            }
        if isinstance(value, pd.Series):
            return {
                "name": str(value.name) if value.name is not None else None,
                "index": [_jsonable_value(item) for item in value.index.tolist()],
                "data": [_jsonable_value(item) for item in value.tolist()],
            }
        if isinstance(value, pd.Timestamp):
            if pd.isna(value):
                return None
            return value.isoformat()

    if isinstance(value, dict):
        return {str(key): _jsonable_value(item) for key, item in value.items()}

    if isinstance(value, (list, tuple)):
        return [_jsonable_value(item) for item in value]

    if isinstance(value, set):
        items = [_jsonable_value(item) for item in value]
        return sorted(items, key=_sort_key)

    return _normalize_recursive_value(
        value,
        _jsonable_value,
        transform_scalar=lambda item: str(item),
    )


# Purpose:  canonicalize for key implementation
def _canonicalize_for_key(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, (str, int, bool)):
        return value.strip().lower() if isinstance(value, str) else value

    shared_value = _coerce_shared_value(value, _canonicalize_for_key)
    if shared_value is not _NO_VALUE:
        return shared_value

    if pd is not None and isinstance(value, pd.DataFrame):
        payload = _jsonable_value(value)
        return payload

    if pd is not None and isinstance(value, pd.Series):
        payload = _jsonable_value(value)
        return payload

    if isinstance(value, dict):
        canonical: Dict[str, Any] = {}
        for key in sorted(value.keys(), key=str):
            if _is_secret_key(str(key)):
                continue
            canonical[str(key)] = _canonicalize_for_key(value[key])
        return canonical

    if isinstance(value, (list, tuple, set, frozenset)):
        canonical_items = [_canonicalize_for_key(item) for item in value]
        try:
            return sorted(canonical_items, key=_sort_key)
        except TypeError:
            return canonical_items

    return _normalize_recursive_value(
        value,
        _canonicalize_for_key,
        transform_scalar=lambda item: str(item).strip().lower(),
        skip_secret_keys=True,
        sort_lists=True,
    )


# Purpose:  hash canonical json implementation
def _hash_canonical_json(data: Any) -> str:
    canonical = json.dumps(
        data,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=_jsonable_value,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# Purpose:  extract cache relevant settings implementation
def _extract_cache_relevant_settings(settings_dict: Dict[str, Any]) -> Dict[str, Any]:
    # Purpose:  copy without secrets implementation
    def _copy_without_secrets(value: Any) -> Any:
        if isinstance(value, dict):
            copied: Dict[str, Any] = {}
            for key, item in value.items():
                key_str = str(key)
                if _is_secret_key(key_str):
                    continue
                copied[key_str] = _copy_without_secrets(item)
            return copied
        if isinstance(value, (list, tuple)):
            return [_copy_without_secrets(item) for item in value]
        return value

    # Purpose:  extract recursive implementation
    def _extract_recursive(obj: Any, path: str = "") -> Any:
        if isinstance(obj, dict):
            result: Dict[str, Any] = {}
            for key, value in obj.items():
                current_path = f"{path}.{key}" if path else str(key)
                if is_cache_relevant_setting(current_path):
                    if _is_secret_key(str(key)):
                        continue
                    result[str(key)] = _copy_without_secrets(value)
                    continue

                child = _extract_recursive(value, current_path)
                if isinstance(child, dict) and child:
                    result[str(key)] = child
            return result
        return obj

    return _extract_recursive(settings_dict)


# Purpose: is cache relevant setting implementation
def is_cache_relevant_setting(setting_path: str) -> bool:
    parts = str(setting_path).split(".")
    for i in range(len(parts), 0, -1):
        prefix = ".".join(parts[:i])
        if prefix in CACHE_RELEVANT_SETTINGS:
            return True
    return False


# Purpose: build settings hash implementation
def build_settings_hash(settings_dict: Optional[Dict[str, Any]] = None) -> str:
    if settings_dict is None:
        settings_dict = config

    try:
        relevant = _extract_cache_relevant_settings(settings_dict)
        canonical = _canonicalize_for_key(relevant)
        return _hash_canonical_json(canonical)
    except Exception as exc:
        logger.warning(f"Failed to build settings hash: {exc}")
        return ""


# Purpose:  sanitize params implementation
def _sanitize_params(params: Dict[str, Any]) -> Dict[str, Any]:
    # Purpose:  sanitize implementation
    def _sanitize(value: Any) -> Any:
        if dataclasses.is_dataclass(value):
            return _sanitize(dataclasses.asdict(value))
        if pd is not None and isinstance(value, pd.DataFrame):
            return _jsonable_value(value)
        if pd is not None and isinstance(value, pd.Series):
            return _jsonable_value(value)
        return _normalize_recursive_value(
            value,
            _sanitize,
            transform_scalar=_canonicalize_for_key,
            skip_secret_keys=True,
        )

    return _sanitize(params if isinstance(params, dict) else {})


# Purpose: normalize params for cache implementation
def normalize_params_for_cache(kind: str, provider: str, params: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = _sanitize_params(params)
    normalized = _canonicalize_for_key(sanitized)
    return {
        "kind": str(kind).strip().lower(),
        "provider": str(provider).strip().lower(),
        "params": normalized,
    }


# Purpose: build cache key implementation
def build_cache_key(
    kind: str,
    provider: str,
    params: Dict[str, Any],
    settings_hash: Optional[str] = None,
) -> str:
    try:
        if settings_hash is None:
            settings_hash = build_settings_hash()
        normalized = normalize_params_for_cache(kind, provider, params)
        key_data = {
            "normalized": normalized,
            "settings_hash": settings_hash,
        }
        return _hash_canonical_json(key_data)
    except Exception as exc:
        logger.warning(f"Failed to build cache key: {exc}")
        return ""


# Purpose:  normalize trends keywords implementation
def _normalize_trends_keywords(values: Any) -> List[str]:
    if values is None:
        return []
    if not isinstance(values, (list, tuple, set, frozenset)):
        values = [values]

    seen: Set[str] = set()
    normalized: List[str] = []
    for item in values:
        cleaned = str(item).strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(lowered)
    return sorted(normalized)


# Purpose:  hash batch composition implementation
def _hash_batch_composition(value: Any) -> str:
    sanitized = _sanitize_params({"batch_composition": value}).get("batch_composition")
    if sanitized is None:
        return ""
    return _hash_canonical_json(_canonicalize_for_key(sanitized))


# Purpose: build trends cache key implementation
def build_trends_cache_key(
    provider: str,
    endpoint_mode: str,
    params: Dict[str, Any],
) -> str:
    try:
        normalized_keywords = _normalize_trends_keywords(
            params.get("normalized_keywords", params.get("keywords", []))
        )
        key_data = {
            "provider": str(provider).strip().lower(),
            "endpoint_mode": str(endpoint_mode).strip().lower(),
            "normalized_keywords": normalized_keywords,
            "timeframe": _canonicalize_for_key(params.get("timeframe")),
            "geo": str(params.get("geo", "") or "").strip().upper(),
            "category": int(params.get("category", 0) or 0),
            "property": _canonicalize_for_key(params.get("property", params.get("gprop", ""))),
            "language": _canonicalize_for_key(params.get("language", params.get("hl", ""))),
            "timezone": int(params.get("timezone", params.get("tz", 0)) or 0),
            "batch_composition": _hash_batch_composition(
                params.get(
                    "batch_composition",
                    {
                        "keywords": normalized_keywords,
                        "batch_size": params.get("batch_size"),
                        "anchor_keyword": params.get("anchor_keyword"),
                    },
                )
            ),
            "provider_version": _canonicalize_for_key(
                params.get("provider_version", params.get("version", ""))
            ),
            "schema_version": int(
                params.get("schema_version", CACHE_SCHEMA_VERSION) or CACHE_SCHEMA_VERSION
            ),
        }
        return _hash_canonical_json(key_data)
    except Exception as exc:
        logger.warning(f"Failed to build Trends cache key: {exc}")
        return ""


# Purpose: get cache ttl hours implementation
def get_cache_ttl_hours(kind: str) -> int:
    return CACHE_KIND_TTL.get(kind, CACHE_TTL_DEFAULT_HOURS)


# Purpose:  read history bundle implementation
def _read_history_bundle() -> Dict[str, Any]:
    if not HISTORY_FILE.exists():
        return {
            "schema_version": HISTORY_SCHEMA_VERSION,
            "records": [],
            "migrated_at": None,
        }

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as exc:
        logger.warning(f"Failed to read history bundle: {exc}")
        return {
            "schema_version": HISTORY_SCHEMA_VERSION,
            "records": [],
            "migrated_at": None,
        }

    migrated = migrate_history_data(data)
    if isinstance(migrated, dict):
        if "records" not in migrated:
            migrated["records"] = []
        return migrated

    return {
        "schema_version": HISTORY_SCHEMA_VERSION,
        "records": migrated if isinstance(migrated, list) else [],
        "migrated_at": None,
    }


# Purpose:  write history bundle implementation
def _write_history_bundle(records: List[Dict[str, Any]], migrated_at: Optional[str] = None) -> None:
    HISTORY_FILE.parent.mkdir(exist_ok=True, parents=True)
    payload = {
        "schema_version": HISTORY_SCHEMA_VERSION,
        "records": records,
        "migrated_at": migrated_at,
    }
    with open(HISTORY_FILE, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


# Purpose:  history records implementation
def _history_records(bundle: Dict[str, Any]) -> List[Dict[str, Any]]:
    records = bundle.get("records", [])
    return records if isinstance(records, list) else []


# Purpose:  cache record matches implementation
def _cache_record_matches(cache_key: str, record: Dict[str, Any]) -> bool:
    return record.get("record_type") == "cache" and record.get("cache_key") == cache_key


# Purpose:  upsert cache record implementation
def _upsert_cache_record(new_record: Dict[str, Any]) -> bool:
    bundle = _read_history_bundle()
    records = _history_records(bundle)
    cache_key = str(new_record.get("cache_key", ""))
    updated_records = [record for record in records if not _cache_record_matches(cache_key, record)]
    updated_records.append(new_record)

    max_records = int(config.get("cache", {}).get("max_cache_records", 10000))
    if len(updated_records) > max_records:
        cache_records = [record for record in updated_records if record.get("record_type") == "cache"]
        visible_records = [record for record in updated_records if record.get("record_type") != "cache"]
        if len(cache_records) > max_records:
            cache_records = cache_records[-max_records:]
        updated_records = visible_records + cache_records

    _write_history_bundle(updated_records, bundle.get("migrated_at"))
    return True


# Purpose:  update cache record implementation
def _update_cache_record(cache_key: str, mutator: Any) -> Optional[Dict[str, Any]]:
    bundle = _read_history_bundle()
    records = _history_records(bundle)
    updated_record: Optional[Dict[str, Any]] = None
    changed = False

    for index, record in enumerate(records):
        if _cache_record_matches(cache_key, record):
            record_copy = dict(record)
            mutator(record_copy)
            records[index] = record_copy
            updated_record = record_copy
            changed = True
            break

    if changed:
        _write_history_bundle(records, bundle.get("migrated_at"))
    return updated_record


# Purpose:  load cache record implementation
def _load_cache_record(cache_key: str) -> Optional[Dict[str, Any]]:
    bundle = _read_history_bundle()
    records = _history_records(bundle)
    found: Optional[Dict[str, Any]] = None
    for record in records:
        if _cache_record_matches(cache_key, record):
            found = record
    return dict(found) if found is not None else None


# Purpose:  serialize result value implementation
def _serialize_result_value(result: Any) -> Dict[str, Any]:
    if pd is not None and isinstance(result, pd.DataFrame):
        payload = _jsonable_value(result)
        return {
            "type": "dataframe",
            "payload": payload,
        }
    if pd is not None and isinstance(result, pd.Series):
        return {
            "type": "series",
            "payload": _jsonable_value(result),
        }
    if isinstance(result, str):
        return {
            "type": "text",
            "payload": result,
        }
    if isinstance(result, dict):
        return {
            "type": "json",
            "payload": _jsonable_value(result),
        }
    if isinstance(result, list):
        return {
            "type": "json",
            "payload": _jsonable_value(result),
        }
    if dataclasses.is_dataclass(result):
        return {
            "type": "json",
            "payload": _jsonable_value(dataclasses.asdict(result)),
        }
    if hasattr(result, "model_dump") and callable(getattr(result, "model_dump")):
        try:
            return {
                "type": "json",
                "payload": _jsonable_value(result.model_dump()),
            }
        except Exception:
            pass
    if hasattr(result, "to_dict") and callable(getattr(result, "to_dict")):
        try:
            payload = result.to_dict()
            if pd is not None and hasattr(result, "columns"):
                return {
                    "type": "dataframe",
                    "payload": _jsonable_value(pd.DataFrame(payload)),
                }
            return {
                "type": "json",
                "payload": _jsonable_value(payload),
            }
        except Exception:
            pass
    if hasattr(result, "_asdict") and callable(getattr(result, "_asdict")):
        try:
            return {
                "type": "json",
                "payload": _jsonable_value(result._asdict()),
            }
        except Exception:
            pass
    return {
        "type": "json",
        "payload": _jsonable_value(result),
    }


# Purpose:  build cache record implementation
def _build_cache_record(
    kind: str,
    cache_key: str,
    request_params: Dict[str, Any],
    result: Any,
    source_urls: Optional[Sequence[str]] = None,
    keywords: Optional[Sequence[str]] = None,
    provider: str = "",
    ttl_hours: Optional[int] = None,
) -> Dict[str, Any]:
    ttl_value = get_cache_ttl_hours(kind) if ttl_hours is None else max(0, int(ttl_hours))
    created_at = datetime.now()
    expires_at = created_at + timedelta(hours=ttl_value)
    normalized_request = normalize_params_for_cache(kind, provider, request_params)
    serialized_result = _serialize_result_value(result)
    serialized_payload = serialized_result.get("payload")
    result_provider_metadata = None
    result_data_confidence = None
    if isinstance(serialized_payload, dict):
        result_provider_metadata = serialized_payload.get("provider_metadata")
        result_data_confidence = serialized_payload.get("data_confidence")

    cache_record = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "record_type": "cache",
        "kind": kind,
        "cache_key": cache_key,
        "request": {
            "normalized_params": normalized_request["params"],
            "kind": normalized_request["kind"],
            "provider": normalized_request["provider"],
        },
        "settings_hash": build_settings_hash(),
        "result": serialized_result,
        "created_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "source_urls": _jsonable_value(list(source_urls or []))[:100],
        "keywords": _jsonable_value(list(keywords or []))[:100],
        "provider": str(provider),
        "cache_hit_count": 0,
    }
    if result_provider_metadata is not None:
        cache_record["provider_metadata"] = _sanitize_params(
            _jsonable_value(result_provider_metadata)
        )
    if result_data_confidence is not None:
        cache_record["data_confidence"] = str(result_data_confidence)

    return cache_record


# Purpose: Invalidate pre-Phase-13 trends cache records that lack schema_version or use schema_version < 2.
# Old cache keys did not include provider_name, so stale hits could serve
# data fetched by a different provider.  This runs once per history file.
def _migrate_old_trends_cache_keys() -> None:
    try:
        bundle = _read_history_bundle()
        records = _history_records(bundle)
        if not records:
            return

        # Check if migration already ran
        if bundle.get(_TRENDS_CACHE_MIGRATED_KEY):
            return

        retained: List[Dict[str, Any]] = []
        removed = 0
        for record in records:
            if record.get("record_type") != "cache":
                retained.append(record)
                continue
            if record.get("kind") != "trends":
                retained.append(record)
                continue
            schema_ver = record.get("schema_version")
            if schema_ver is None or int(schema_ver) < CACHE_SCHEMA_VERSION:
                removed += 1
                continue
            retained.append(record)

        if removed:
            bundle[_TRENDS_CACHE_MIGRATED_KEY] = True
            _write_history_bundle(retained, bundle.get("migrated_at"))
            logger.info(
                f"Migrated trends cache: removed {removed} old-format records"
            )
        else:
            # Mark as migrated even when nothing to remove
            bundle[_TRENDS_CACHE_MIGRATED_KEY] = True
            _write_history_bundle(records, bundle.get("migrated_at"))
    except Exception as exc:
        logger.warning(f"Failed to migrate old trends cache keys: {exc}")


# Purpose: RequestCache implementation
class RequestCache:
    # Purpose:   init   implementation
    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled
        self._cache_index: Dict[str, Dict[str, Any]] = {}
        _migrate_old_trends_cache_keys()
        self._load_cache_index()

    # Purpose:  load cache index implementation
    def _load_cache_index(self) -> None:
        self._cache_index = {}
        bundle = _read_history_bundle()
        for record in _history_records(bundle):
            if record.get("record_type") != "cache":
                continue
            cache_key = record.get("cache_key")
            if cache_key:
                self._cache_index[str(cache_key)] = {
                    "created_at": record.get("created_at"),
                    "expires_at": record.get("expires_at"),
                    "kind": record.get("kind"),
                    "hit_count": record.get("cache_hit_count", 0),
                }

    # Purpose:  is expired implementation
    def _is_expired(self, record: Dict[str, Any]) -> bool:
        expires_at_str = record.get("expires_at")
        if not expires_at_str:
            return False
        try:
            return datetime.fromisoformat(str(expires_at_str)) < datetime.now()
        except ValueError:
            return False

    # Purpose: get implementation
    def get(self, cache_key: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        # SEMANTIC_BLOCK: block_request_cache_lookup
        self._load_cache_index()

        if not self._enabled or force_refresh:
            logger.info(
                f"[GRACE:block_request_cache_lookup:STATE] beliefState=cache_lookup_bypassed kind=unknown hit=false bypass=true key={cache_key}"
            )
            return None

        cache_info = self._cache_index.get(cache_key)
        if not cache_info:
            logger.info(
                f"[GRACE:block_request_cache_lookup:STATE] beliefState=cache_lookup_miss kind=unknown hit=false key={cache_key}"
            )
            return None

        record = _load_cache_record(cache_key)
        if record is None:
            logger.info(
                f"[GRACE:block_request_cache_lookup:STATE] beliefState=cache_record_missing kind=unknown hit=false key={cache_key}"
            )
            return None

        if self._is_expired(record):
            logger.info(
                f"[GRACE:block_request_cache_lookup:STATE] beliefState=cache_record_expired kind={record.get('kind', 'unknown')} hit=false expired=true key={cache_key}"
            )
            return None

        # Purpose:  increment hit count implementation
        def _increment_hit_count(target: Dict[str, Any]) -> None:
            target["cache_hit_count"] = int(target.get("cache_hit_count", 0)) + 1

        updated_record = _update_cache_record(cache_key, _increment_hit_count)
        if updated_record is None:
            updated_record = record
            updated_record["cache_hit_count"] = int(updated_record.get("cache_hit_count", 0)) + 1

        kind = updated_record.get("kind", "unknown")
        hits = updated_record.get("cache_hit_count", 0)
        self._cache_index[cache_key] = {
            "created_at": updated_record.get("created_at"),
            "expires_at": updated_record.get("expires_at"),
            "kind": kind,
            "hit_count": hits,
        }
        logger.info(
            f"[GRACE:block_request_cache_lookup:STATE] beliefState=cache_lookup_hit kind={kind} hit=true key={cache_key} hits={hits}"
        )
        return updated_record

    # Purpose: set implementation
    def set(
        self,
        kind: str,
        cache_key: str,
        request_params: Dict[str, Any],
        result: Any,
        source_urls: Optional[Sequence[str]] = None,
        keywords: Optional[Sequence[str]] = None,
        provider: str = "",
        ttl_hours: Optional[int] = None,
    ) -> bool:
        if not self._enabled:
            return False

        if kind not in CACHE_KINDS:
            logger.warning(f"Invalid cache kind: {kind}")
            return False

        try:
            # SEMANTIC_BLOCK: block_request_cache_write
            cache_record = _build_cache_record(
                kind=kind,
                cache_key=cache_key,
                request_params=request_params,
                result=result,
                source_urls=source_urls,
                keywords=keywords,
                provider=provider,
                ttl_hours=ttl_hours,
            )

            _upsert_cache_record(cache_record)
            self._cache_index[cache_key] = {
                "created_at": cache_record["created_at"],
                "expires_at": cache_record["expires_at"],
                "kind": kind,
                "hit_count": 0,
            }
            return True
        except Exception as exc:
            logger.warning(f"Failed to store cache record: {exc}")
            return False

    # Purpose: invalidate implementation
    def invalidate(self, cache_key: str) -> bool:
        try:
            bundle = _read_history_bundle()
            records = _history_records(bundle)
            filtered = [record for record in records if not _cache_record_matches(cache_key, record)]
            if len(filtered) == len(records):
                return False
            _write_history_bundle(filtered, bundle.get("migrated_at"))
            self._cache_index.pop(cache_key, None)
            logger.info(f"Invalidated cache key: {cache_key}")
            return True
        except Exception as exc:
            logger.warning(f"Failed to invalidate cache: {exc}")
            return False

    # Purpose: clear implementation
    def clear(self) -> bool:
        try:
            bundle = _read_history_bundle()
            records = _history_records(bundle)
            visible_records = [record for record in records if record.get("record_type") != "cache"]
            _write_history_bundle(visible_records, bundle.get("migrated_at"))
            self._cache_index.clear()
            logger.info("Cleared cache records")
            return True
        except Exception as exc:
            logger.warning(f"Failed to clear cache: {exc}")
            return False

    # Purpose: cleanup expired implementation
    def cleanup_expired(self) -> int:
        try:
            bundle = _read_history_bundle()
            records = _history_records(bundle)
            retained: List[Dict[str, Any]] = []
            removed = 0

            for record in records:
                if record.get("record_type") != "cache":
                    retained.append(record)
                    continue

                if self._is_expired(record):
                    removed += 1
                    continue
                retained.append(record)

            if removed:
                _write_history_bundle(retained, bundle.get("migrated_at"))
                self._load_cache_index()
            return removed
        except Exception as exc:
            logger.warning(f"Failed to cleanup expired cache: {exc}")
            return 0

    # Purpose: get cache records implementation
    def get_cache_records(self, kind: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            bundle = _read_history_bundle()
            records = [record for record in _history_records(bundle) if record.get("record_type") == "cache"]
            if kind:
                records = [record for record in records if record.get("kind") == kind]
            return records
        except Exception as exc:
            logger.warning(f"Failed to get cache records: {exc}")
            return []

    # Purpose:  load cache record implementation
    def _load_cache_record(self, cache_key: str) -> Optional[Dict[str, Any]]:
        return _load_cache_record(cache_key)


request_cache = RequestCache(enabled=config.get("cache", {}).get("enabled", True))
