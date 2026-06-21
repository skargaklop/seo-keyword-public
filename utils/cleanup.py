import time
from pathlib import Path
from typing import List

from config.settings import CLEANUP_CONFIG, LOGGING_CONFIG, load_config
from utils.history import HistoryManager
from utils.logger import LOG_DIR, logger

OUTPUTS_DIR = Path(__file__).parent.parent / "outputs"
DEFAULT_MAX_AGE_DAYS = CLEANUP_CONFIG.get("max_age_days", 30)
DEFAULT_API_LOG_RETENTION_DAYS = LOGGING_CONFIG.get("api_retention_days", 30)


# MODULE_CONTRACT: utils/cleanup
# Purpose: Retention-based file cleanup for outputs/, API logs, and history entries
# Rationale: Prevents unbounded disk growth by removing aged artifacts at startup
# Dependencies: config.settings, utils.history, utils.logger
# Exports: cleanup_old_files, cleanup_api_logs, run_startup_cleanup
# LINKS: requirements.xml#UC-001, knowledge-graph.xml#MOD-001
# MODULE_MAP: utils/cleanup.py
# Public Functions: cleanup_old_files, cleanup_api_logs, run_startup_cleanup
# Private Helpers: (none)
# Key Semantic Blocks: block_cleanup_outputs_file_retention, block_cleanup_startup_all_tasks
# Critical Flows: run_startup_cleanup called at app startup to enforce retention policies
# Verification: V-SUITE
# CHANGE_SUMMARY: Added module-level contracts; added FUNCTION_CONTRACT blocks for all three functions; removed post-declaration docstrings
# FUNCTION_CONTRACT: cleanup_old_files
# Purpose: Delete files older than a configured age from a directory, with symlink and path-traversal protection
# Input: directory (Path), max_age_days (int | None) — 0 disables cleanup; None reads from config
# Output: List[str] — paths of deleted files
# Side Effects: deletes files on disk; logs deletions and warnings
# Business Rules: skips symlinks; resolves paths to prevent traversal; 0 disables
# Failure Modes: logs warnings on per-file deletion errors; never raises
# LINKS: requirements.xml#UC-001
def cleanup_old_files(
    directory: Path = OUTPUTS_DIR,
    max_age_days: int | None = None,
) -> List[str]:
    if max_age_days is None:
        max_age_days = int(
            load_config().get("cleanup", {}).get("max_age_days", DEFAULT_MAX_AGE_DAYS)
        )

    if max_age_days <= 0:
        return []

    if not directory.exists():
        return []

    deleted: List[str] = []
    cutoff_time: float = time.time() - (max_age_days * 86400)

    # Resolve the directory to prevent symlink-based path traversal
    resolved_dir = directory.resolve()

    for file_path in directory.iterdir():
        if file_path.is_file() and not file_path.is_symlink():
            # Ensure the resolved path is still within the target directory
            try:
                file_path.resolve().relative_to(resolved_dir)
            except ValueError:
                logger.warning(f"Skipping file outside target directory: {file_path}")
                continue
            try:
                file_mtime: float = file_path.stat().st_mtime
                if file_mtime < cutoff_time:
                    file_path.unlink()
                    deleted.append(str(file_path))
                    logger.info(f"Cleaned up old file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete {file_path}: {e}")

    if deleted:
        logger.info(f"Cleanup: removed {len(deleted)} old files from {directory}")

    return deleted


# FUNCTION_CONTRACT: cleanup_api_logs
# Purpose: Delete aged API request log files including rotated backups
# Input: directory (Path), max_age_days (int | None) — 0 disables; None reads from config
# Output: List[str] — paths of deleted log files
# Side Effects: deletes files on disk; logs warnings on errors
# Business Rules: only targets api_requests.log and its rotated siblings; skips symlinks
# Failure Modes: logs warnings on per-file errors; never raises
# LINKS: requirements.xml#UC-001
def cleanup_api_logs(
    directory: Path = LOG_DIR,
    max_age_days: int | None = None,
) -> List[str]:
    if max_age_days is None:
        max_age_days = int(
            load_config().get("logging", {}).get(
                "api_retention_days", DEFAULT_API_LOG_RETENTION_DAYS
            )
        )

    if max_age_days <= 0 or not directory.exists():
        return []

    deleted: List[str] = []
    cutoff_time: float = time.time() - (max_age_days * 86400)
    for file_path in directory.iterdir():
        if not file_path.is_file() or file_path.is_symlink():
            continue
        if file_path.name != "api_requests.log" and not file_path.name.startswith(
            "api_requests.log."
        ):
            continue
        try:
            if file_path.stat().st_mtime < cutoff_time:
                file_path.unlink()
                deleted.append(str(file_path))
        except Exception as exc:
            logger.warning(f"Failed to delete API log {file_path}: {exc}")

    return deleted


# FUNCTION_CONTRACT: run_startup_cleanup
# Purpose: Execute all retention-based cleanup tasks at application startup
# Input: (none)
# Output: dict[str, int] — counts of deleted outputs, API logs, and history entries
# Side Effects: delegates to cleanup_old_files, cleanup_api_logs, HistoryManager.trim_history_entries
# Business Rules: reads retention settings from current config each call
# Failure Modes: delegates error handling to sub-functions
# LINKS: requirements.xml#UC-001
def run_startup_cleanup() -> dict[str, int]:
    config = load_config()
    outputs_deleted = cleanup_old_files(
        directory=OUTPUTS_DIR,
        max_age_days=int(config.get("cleanup", {}).get("max_age_days", DEFAULT_MAX_AGE_DAYS)),
    )
    api_logs_deleted = cleanup_api_logs(
        directory=LOG_DIR,
        max_age_days=int(
            config.get("logging", {}).get(
                "api_retention_days", DEFAULT_API_LOG_RETENTION_DAYS
            )
        ),
    )
    history_removed = HistoryManager.trim_history_entries(
        max_age_days=int(config.get("history", {}).get("retention_days", 30))
    )
    return {
        "outputs_deleted": len(outputs_deleted),
        "api_logs_deleted": len(api_logs_deleted),
        "history_removed": history_removed,
    }
