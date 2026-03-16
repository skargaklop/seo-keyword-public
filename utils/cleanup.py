"""
Auto-cleanup utility for outputs/ folder — removes files older than N days (improvement #8).
"""

import time
from pathlib import Path
from typing import List

from config.settings import CLEANUP_CONFIG, LOGGING_CONFIG, load_config
from utils.history import HistoryManager
from utils.logger import LOG_DIR, logger

OUTPUTS_DIR = Path(__file__).parent.parent / "outputs"
DEFAULT_MAX_AGE_DAYS = CLEANUP_CONFIG.get("max_age_days", 30)
DEFAULT_API_LOG_RETENTION_DAYS = LOGGING_CONFIG.get("api_retention_days", 30)


def cleanup_old_files(
    directory: Path = OUTPUTS_DIR,
    max_age_days: int | None = None,
) -> List[str]:
    """
    Remove files older than max_age_days from the specified directory.

    Args:
        directory: Path to the directory to clean up.
        max_age_days: Maximum age of files in days before deletion. 0 = disabled.

    Returns:
        List of deleted file paths.
    """
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


def cleanup_api_logs(
    directory: Path = LOG_DIR,
    max_age_days: int | None = None,
) -> List[str]:
    """Remove old API log files, including rotated log files."""
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


def run_startup_cleanup() -> dict[str, int]:
    """Run all retention-based cleanup tasks before app execution."""
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
