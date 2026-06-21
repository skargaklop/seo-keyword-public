# MODULE_CONTRACT: utils/history
# Purpose: History manager with schema v2 migration support for cache records (Phase 10 Task 5).
# Rationale: Keep the module boundary explicit for GRACE adoption and review; support both visible history and hidden cache records.
# Dependencies: json, time, datetime, pathlib, typing, config.settings, utils.logger
# Exports: HISTORY_DIR, HISTORY_FILE, MAX_HISTORY_ENTRIES, DEFAULT_RETENTION_DAYS, HISTORY_SCHEMA_VERSION, HistoryManager, migrate_history_data
# LINKS: requirements.xml#UC-001, development-plan.xml#MOD-001, PLAN 10-02 Task 5
# MODULE_MAP: utils/history.py
# Public Functions: exported callables and classes defined in this module
# Private Helpers: internal helpers and private methods defined in this module
# Key Semantic Blocks: main workflow paths and state transitions in this module
# Critical Flows: preserve existing runtime behavior and integrations; migration must be idempotent
# Verification: python -m py_compile, python -m ruff check ., python -m pytest -q
# CHANGE_SUMMARY: Phase 10 Task 5: Added schema v2 support, migration functions, cache record filtering, extended HistoryManager.

import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from config.settings import HISTORY_CONFIG
from utils.logger import logger

HISTORY_DIR = Path(__file__).parent.parent / "data"
HISTORY_FILE = HISTORY_DIR / "history.json"
MAX_HISTORY_ENTRIES = 100
DEFAULT_RETENTION_DAYS = int(HISTORY_CONFIG.get("retention_days", 30))
HISTORY_SCHEMA_VERSION = 2  # Current schema version for history/cache records

# FUNCTION_CONTRACT: migrate_history_data
# Purpose: Migrate old history schema (list) to new schema (dict with records). Idempotent.
# Input: old_data (Any)
# Output: Dict[str, Any] — migrated data with schema_version
# Side Effects: none (pure migration function)
# Business Rules: Convert old list to new dict format; preserve all existing records; idempotent (safe to run multiple times)
# Failure Modes: returns original data if migration not applicable
# LINKS: requirements.xml#UC-001, PLAN 10-02 Task 5 (HIGH-01)
def migrate_history_data(old_data: Any) -> Dict[str, Any]:
    # Already at schema version 2
    if isinstance(old_data, dict) and old_data.get("schema_version") == HISTORY_SCHEMA_VERSION:
        return old_data
    if isinstance(old_data, dict):
        schema_version = old_data.get("schema_version")
        if isinstance(schema_version, int) and schema_version > HISTORY_SCHEMA_VERSION:
            logger.warning(
                f"History schema version {schema_version} is newer than supported version {HISTORY_SCHEMA_VERSION}; leaving data unchanged."
            )
            return old_data

    # Old schema: list of history entries
    # Detect by checking if it's a list and items look like history entries (have timestamp or created_at)
    if isinstance(old_data, list) and all(isinstance(item, dict) for item in old_data):
        # Check if items have history-like timestamps
        has_history_timestamps = any("timestamp" in item or "created_at" in item for item in old_data)

        if has_history_timestamps:
            return {
                "schema_version": HISTORY_SCHEMA_VERSION,
                "records": old_data,
                "migrated_at": datetime.now().isoformat(),
            }

    # Return wrapped in new schema for empty or unexpected data
    if isinstance(old_data, list):
        return {
            "schema_version": HISTORY_SCHEMA_VERSION,
            "records": old_data,
            "migrated_at": datetime.now().isoformat(),
        }

    # Return as-is if it's already a dict but missing schema_version (edge case)
    if isinstance(old_data, dict):
        # Ensure it has records key
        if "records" not in old_data:
            old_data["records"] = []
        old_data["schema_version"] = HISTORY_SCHEMA_VERSION
        if "migrated_at" not in old_data:
            old_data["migrated_at"] = datetime.now().isoformat()
        return old_data

    # Fallback: treat as empty history
    return {
        "schema_version": HISTORY_SCHEMA_VERSION,
        "records": [],
        "migrated_at": datetime.now().isoformat(),
    }


# CLASS_CONTRACT: HistoryManager
# Purpose: Persist, load, clear, and trim keyword analysis history entries with schema v2 support.
# LINKS: requirements.xml#UC-001, PLAN 10-02 Task 5
class HistoryManager:
    # FUNCTION_CONTRACT: _ensure_dir
    # Purpose: Implement the  ensure dir helper for this module.
    # Input: (none)
    # Output: None
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    def _ensure_dir() -> None:
        HISTORY_DIR.mkdir(exist_ok=True, parents=False)
    # FUNCTION_CONTRACT: load_history
    # Purpose: Implement the load history helper for this module with migration support.
    # Input: (none)
    # Output: List[Dict[str, Any]] — visible history entries only (excluding cache records)
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path; migrates old schema automatically; filters out cache records.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001, PLAN 10-02 Task 5 (HIGH-01)
    @staticmethod
    def load_history(include_cache: bool = False) -> List[Dict[str, Any]]:
        try:
            if not HISTORY_FILE.exists():
                return []
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Migrate if needed
            migrated = migrate_history_data(data)

            # Extract records list
            if isinstance(migrated, dict):
                records = migrated.get("records", [])
            else:
                records = data if isinstance(data, list) else []

            # Return visible history (optionally include cache records)
            if include_cache:
                visible_records = records
            else:
                visible_records = [r for r in records if r.get("record_type") != "cache"]

            return visible_records if isinstance(visible_records, list) else []
        except Exception as e:
            logger.warning(f"Failed to load history: {e}")
            return []
    # FUNCTION_CONTRACT: save_entry
    # Purpose: Implement the save entry helper for this module with schema v2 support.
    # Input: urls (List[str]), keywords (List[str]), keyword_count (int), url_count (int), metadata (Optional[Dict[str, Any]] = None), checkpoint (Optional[Dict[str, Any]] = None)
    # Output: bool
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path; writes schema v2 format.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001, PLAN 10-02 Task 5
    @staticmethod
    def save_entry(
        urls: List[str],
        keywords: List[str],
        keyword_count: int,
        url_count: int,
        metadata: Optional[Dict[str, Any]] = None,
        checkpoint: Optional[Dict[str, Any]] = None,
    ) -> bool:
        try:
            HistoryManager._ensure_dir()

            # Load full history (including cache records) to preserve them
            if HISTORY_FILE.exists():
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                migrated = migrate_history_data(data)
                records = migrated.get("records", []) if isinstance(migrated, dict) else []
            else:
                records = []

            # Create new visible history entry
            entry: Dict[str, Any] = {
                "schema_version": HISTORY_SCHEMA_VERSION,
                "record_type": "history",  # Distinguish from cache records
                "created_at": datetime.now().isoformat(),
                "urls": urls,
                "keywords": keywords[:50],  # Limit stored keywords
                "keyword_count": keyword_count,
                "url_count": url_count,
            }
            if metadata:
                entry["metadata"] = metadata
            if checkpoint:
                entry["checkpoint"] = checkpoint

            # Append to records
            records.append(entry)

            # Trim old visible history entries (not cache records)
            visible_history = [r for r in records if r.get("record_type") != "cache"]
            cache_records = [r for r in records if r.get("record_type") == "cache"]

            if len(visible_history) > MAX_HISTORY_ENTRIES:
                # Keep only recent visible history, preserve all cache records
                visible_history = visible_history[-MAX_HISTORY_ENTRIES:]

            # Merge back
            records = visible_history + cache_records

            # Save with schema v2
            output_data = {
                "schema_version": HISTORY_SCHEMA_VERSION,
                "records": records,
                "migrated_at": migrated.get("migrated_at") if "migrated" in locals() and isinstance(migrated, dict) else None,
            }

            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)

            logger.info(f"History entry saved ({keyword_count} keywords, {url_count} URLs)")
            return True
        except Exception as e:
            logger.warning(f"Failed to save history entry: {e}")
            return False
    # FUNCTION_CONTRACT: clear_history
    # Purpose: Implement the clear history helper for this module with cache handling.
    # Input: clear_cache (bool = False) — whether to also clear cache records
    # Output: bool
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path; optionally preserves cache records.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001, PLAN 10-02 Task 5
    @staticmethod
    def clear_history(clear_cache: bool = False) -> bool:
        try:
            HistoryManager._ensure_dir()

            if clear_cache:
                # Clear everything
                output_data = {
                    "schema_version": HISTORY_SCHEMA_VERSION,
                    "records": [],
                    "migrated_at": None,
                }
            else:
                # Preserve cache records, clear visible history only
                if HISTORY_FILE.exists():
                    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    migrated = migrate_history_data(data)
                    cache_records = [
                        r for r in migrated.get("records", [])
                        if r.get("record_type") == "cache"
                    ]
                else:
                    cache_records = []

                output_data = {
                    "schema_version": HISTORY_SCHEMA_VERSION,
                    "records": cache_records,
                    "migrated_at": migrated.get("migrated_at") if HISTORY_FILE.exists() else None,
                }

            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.warning(f"Failed to clear history: {e}")
            return False
    # FUNCTION_CONTRACT: trim_history_entries
    # Purpose: Implement the trim history entries helper for this module with cache TTL preservation.
    # Input: max_age_days (int = DEFAULT_RETENTION_DAYS), now_ts (Optional[float] = None)
    # Output: int
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path; does NOT delete unexpired cache records; preserves cache records based on their own TTL.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001, PLAN 10-02 Task 5
    @staticmethod
    def trim_history_entries(
        max_age_days: int = DEFAULT_RETENTION_DAYS,
        now_ts: Optional[float] = None,
    ) -> int:
        if max_age_days <= 0:
            return 0

        # Load full history including cache records
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            migrated = migrate_history_data(data)
            all_records = migrated.get("records", []) if isinstance(migrated, dict) else []
        else:
            all_records = []

        if not all_records:
            return 0

        cutoff_ts = (now_ts if now_ts is not None else time.time()) - (
            max_age_days * 86400
        )
        retained_records: List[Dict[str, Any]] = []
        removed = 0

        now = datetime.now()

        for record in all_records:
            # Cache records use their own TTL, not history retention
            if record.get("record_type") == "cache":
                # Keep cache if not expired based on its own expires_at
                expires_at_str = record.get("expires_at")
                if expires_at_str:
                    try:
                        expires_at = datetime.fromisoformat(expires_at_str)
                        if expires_at >= now:
                            retained_records.append(record)
                        else:
                            # Expired cache record
                            removed += 1
                    except ValueError:
                        retained_records.append(record)
                else:
                    retained_records.append(record)
                continue

            # Visible history entries use retention cutoff
            raw_timestamp = record.get("timestamp") or record.get("created_at")
            try:
                entry_ts = datetime.fromisoformat(str(raw_timestamp)).timestamp()
            except Exception:
                retained_records.append(record)
                continue

            if entry_ts < cutoff_ts:
                removed += 1
                continue
            retained_records.append(record)

        if removed:
            HistoryManager._ensure_dir()
            output_data = {
                "schema_version": HISTORY_SCHEMA_VERSION,
                "records": retained_records,
                "migrated_at": migrated.get("migrated_at") if isinstance(migrated, dict) else None,
            }
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)

        return removed

    # FUNCTION_CONTRACT: load_all_records
    # Purpose: Load all records including cache records (for inspection/export).
    # Input: (none)
    # Output: List[Dict[str, Any]] — all records including cache
    # Side Effects: reads HISTORY_FILE
    # Business Rules: Return complete record list with migration
    # Failure Modes: returns empty list on error
    # LINKS: requirements.xml#UC-001, PLAN 10-02 Task 5
    @staticmethod
    def load_all_records() -> List[Dict[str, Any]]:
        try:
            if not HISTORY_FILE.exists():
                return []
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            migrated = migrate_history_data(data)
            return migrated.get("records", []) if isinstance(migrated, dict) else []
        except Exception as e:
            logger.warning(f"Failed to load all records: {e}")
            return []

    # FUNCTION_CONTRACT: get_cache_stats
    # Purpose: Get statistics about cached records.
    # Input: (none)
    # Output: Dict[str, Any] — cache statistics
    # Side Effects: reads HISTORY_FILE
    # Business Rules: Return counts by kind, hit rates, size info
    # Failure Modes: returns empty dict on error
    # LINKS: requirements.xml#UC-001, PLAN 10-02 Task 5
    @staticmethod
    def get_cache_stats() -> Dict[str, Any]:
        try:
            records = HistoryManager.load_all_records()
            cache_records = [r for r in records if r.get("record_type") == "cache"]

            stats = {
                "total_cache_records": len(cache_records),
                "total_visible_history": len(records) - len(cache_records),
                "by_kind": {},
                "total_hits": 0,
                "expired_count": 0,
            }

            now = datetime.now()

            for record in cache_records:
                kind = record.get("kind", "unknown")
                stats["by_kind"][kind] = stats["by_kind"].get(kind, 0) + 1

                hits = record.get("cache_hit_count", 0)
                stats["total_hits"] += hits

                # Check expiration
                expires_at_str = record.get("expires_at")
                if expires_at_str:
                    try:
                        expires_at = datetime.fromisoformat(expires_at_str)
                        if expires_at < now:
                            stats["expired_count"] += 1
                    except ValueError:
                        pass

            return stats
        except Exception as e:
            logger.warning(f"Failed to get cache stats: {e}")
            return {}