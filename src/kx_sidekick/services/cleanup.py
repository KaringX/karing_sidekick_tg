from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Protocol

DEFAULT_MEDIA_ROOT_DIR = Path("data/media")
DATE_DIR_RE = re.compile(r"^\d{8}$")
STATE_FILE_NAME = "daily_cleanup_state.json"


class CleanupStorage(Protocol):
    def delete_messages_older_than(self, days: int) -> int: ...


@dataclass
class CleanupService:
    storage: CleanupStorage
    state_dir: Path
    media_root_dir: Path = DEFAULT_MEDIA_ROOT_DIR

    def run(
        self,
        messages_days: int | None,
        media_days: int | None,
    ) -> dict[str, int | str]:
        deleted_messages = 0
        if messages_days is not None:
            deleted_messages = self.storage.delete_messages_older_than(messages_days)

        deleted_media_dirs = 0
        if media_days is not None:
            deleted_media_dirs = self._delete_media_dirs_older_than(media_days)

        return {
            "run_status": "ok",
            "deleted_messages": deleted_messages,
            "deleted_media_dirs": deleted_media_dirs,
        }

    def run_daily_if_due(
        self,
        messages_days: int | None,
        media_days: int | None,
        today: date | None = None,
    ) -> dict[str, int | str] | None:
        if messages_days is None and media_days is None:
            return None
        current_day = today or datetime.now(UTC).date()
        if self._last_run_date() == current_day:
            return None
        summary = self.run(messages_days=messages_days, media_days=media_days)
        self._write_last_run_date(current_day)
        return summary

    def _delete_media_dirs_older_than(self, days: int) -> int:
        if not self.media_root_dir.exists():
            return 0

        cutoff_day = datetime.now(UTC).date() - timedelta(days=days)
        deleted = 0
        for path in self.media_root_dir.iterdir():
            if not path.is_dir() or not DATE_DIR_RE.match(path.name):
                continue
            directory_day = datetime.strptime(path.name, "%Y%m%d").date()
            if directory_day >= cutoff_day:
                continue
            shutil.rmtree(path)
            deleted += 1
        return deleted

    @property
    def _state_file(self) -> Path:
        return self.state_dir / STATE_FILE_NAME

    def _last_run_date(self) -> date | None:
        if not self._state_file.exists():
            return None
        try:
            payload = json.loads(self._state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        raw_date = payload.get("last_run_date")
        if not isinstance(raw_date, str):
            return None
        try:
            return date.fromisoformat(raw_date)
        except ValueError:
            return None

    def _write_last_run_date(self, value: date) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(
            json.dumps({"last_run_date": value.isoformat()}, sort_keys=True),
            encoding="utf-8",
        )
