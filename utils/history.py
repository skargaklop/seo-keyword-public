"""
History manager — saves and loads analysis history to/from JSON (improvement #11).
"""

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


class HistoryManager:
    @staticmethod
    def _ensure_dir() -> None:
        """Ensure the data directory exists."""
        HISTORY_DIR.mkdir(exist_ok=True, parents=False)

    @staticmethod
    def load_history() -> List[Dict[str, Any]]:
        """Load analysis history from JSON file."""
        try:
            if not HISTORY_FILE.exists():
                return []
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.warning(f"Failed to load history: {e}")
            return []

    @staticmethod
    def save_entry(
        urls: List[str],
        keywords: List[str],
        keyword_count: int,
        url_count: int,
        metadata: Optional[Dict[str, Any]] = None,
        checkpoint: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Save a new analysis entry to history."""
        try:
            HistoryManager._ensure_dir()
            history = HistoryManager.load_history()

            entry: Dict[str, Any] = {
                "timestamp": datetime.now().isoformat(),
                "urls": urls,
                "keywords": keywords[:50],  # Limit stored keywords
                "keyword_count": keyword_count,
                "url_count": url_count,
            }
            if metadata:
                entry["metadata"] = metadata
            if checkpoint:
                entry["checkpoint"] = checkpoint

            history.append(entry)

            # Trim old entries
            if len(history) > MAX_HISTORY_ENTRIES:
                history = history[-MAX_HISTORY_ENTRIES:]

            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)

            logger.info(f"History entry saved ({keyword_count} keywords, {url_count} URLs)")
            return True
        except Exception as e:
            logger.warning(f"Failed to save history entry: {e}")
            return False

    @staticmethod
    def clear_history() -> bool:
        """Clear all history."""
        try:
            HistoryManager._ensure_dir()
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)
            return True
        except Exception as e:
            logger.warning(f"Failed to clear history: {e}")
            return False

    @staticmethod
    def trim_history_entries(
        max_age_days: int = DEFAULT_RETENTION_DAYS,
        now_ts: Optional[float] = None,
    ) -> int:
        """Remove history entries older than the configured retention window."""
        if max_age_days <= 0:
            return 0

        history = HistoryManager.load_history()
        if not history:
            return 0

        cutoff_ts = (now_ts if now_ts is not None else time.time()) - (
            max_age_days * 86400
        )
        retained: List[Dict[str, Any]] = []
        removed = 0

        for entry in history:
            raw_timestamp = entry.get("timestamp")
            try:
                entry_ts = datetime.fromisoformat(str(raw_timestamp)).timestamp()
            except Exception:
                retained.append(entry)
                continue

            if entry_ts < cutoff_ts:
                removed += 1
                continue
            retained.append(entry)

        if removed:
            HistoryManager._ensure_dir()
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(retained, f, ensure_ascii=False, indent=2)

        return removed
