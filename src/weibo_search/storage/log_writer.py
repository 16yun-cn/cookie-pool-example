"""Debug log writer for JSONL output."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from weibo_search.config import get_logger, get_settings

logger = get_logger("storage")


class LogWriter:
    """Write debug logs to JSONL files."""

    def __init__(self, log_name: str):
        self.log_name = log_name
        self._log_path: Optional[Path] = None

    @property
    def log_dir(self) -> Path:
        """Get log directory."""
        settings = get_settings()
        path = Path(settings.log_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def log_path(self) -> Path:
        """Get log file path."""
        if self._log_path is None:
            self._log_path = self.log_dir / f"{self.log_name}.jsonl"
        return self._log_path

    def write(self, action: str, data: dict[str, Any], job_id: Optional[str] = None) -> None:
        """Write a log entry."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "job_id": job_id,
            "data": data,
        }
        
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to write log: {e}")

    def write_cookie(self, bundle_id: str, success: bool, error: Optional[str] = None, full_data: Optional[dict] = None) -> None:
        """Write cookie generation log.
        
        Args:
            bundle_id: Cookie bundle ID
            success: Whether generation was successful
            error: Error message if failed
            full_data: Complete cookie bundle data (for debugging/audit)
        """
        data = {
            "bundle_id": bundle_id,
            "success": success,
        }
        if error:
            data["error"] = error
        if full_data:
            data["full_data"] = full_data
        self.write("cookie_generated", data)

    def write_search(
        self,
        keyword: str,
        page: int,
        posts_count: int,
        cookie_id: str,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """Write search result log."""
        data = {
            "keyword": keyword,
            "page": page,
            "posts_count": posts_count,
            "cookie_id": cookie_id,
            "success": success,
        }
        if error:
            data["error"] = error
        self.write("search_completed", data)

    def write_search_result(
        self,
        keyword: str,
        page: int,
        data: dict[str, Any],
        cookie_id: str,
    ) -> None:
        """Write full search result data.
        
        This saves the raw API response for debugging/replay.
        """
        entry = {
            "keyword": keyword,
            "page": page,
            "cookie_id": cookie_id,
            "data": data,
        }
        self.write("search_result_raw", entry)

    def write_debug(self, message: str, extra: Optional[dict] = None) -> None:
        """Write debug message."""
        data = {"message": message}
        if extra:
            data["extra"] = extra
        self.write("debug", data)


# Singleton instances for each log type
_cookie_log: Optional[LogWriter] = None
_search_log: Optional[LogWriter] = None


def get_cookie_log() -> LogWriter:
    """Get cookie log writer."""
    global _cookie_log
    if _cookie_log is None:
        _cookie_log = LogWriter("cookie")
    return _cookie_log


def get_search_log() -> LogWriter:
    """Get search log writer."""
    global _search_log
    if _search_log is None:
        _search_log = LogWriter("search")
    return _search_log
