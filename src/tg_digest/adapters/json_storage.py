from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from tg_digest.models import ArticleCandidate, FetchCursor, MessageRecord


class JsonDailyStorage:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.daily_root = self.data_dir / "daily"
        self.cursor_path = self.data_dir / "cursors.json"

    def save_messages(self, day: date, messages: list[MessageRecord]) -> None:
        payload = {
            "date": day.isoformat(),
            "generated_at": datetime.now(UTC).isoformat(),
            "items": [message.to_dict() for message in messages],
        }
        self._write_json(self._day_dir(day) / "messages.json", payload)

    def load_messages(self, day: date) -> list[MessageRecord]:
        path = self._day_dir(day) / "messages.json"
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = payload.get("items", [])
        if not isinstance(items, list):
            return []
        return [
            MessageRecord.from_dict(item)
            for item in items
            if isinstance(item, dict)
        ]

    def save_candidates(self, day: date, candidates: list[ArticleCandidate]) -> None:
        payload = {
            "date": day.isoformat(),
            "selected_count": len(candidates),
            "items": [candidate.to_dict() for candidate in candidates],
        }
        self._write_json(self._day_dir(day) / "candidates.json", payload)

    def save_summary(self, day: date, summary: dict[str, object]) -> None:
        payload = {"date": day.isoformat(), **summary}
        self._write_json(self._day_dir(day) / "summary.json", payload)

    def load_cursor(self, key: str) -> FetchCursor | None:
        if not self.cursor_path.exists():
            return None
        payload = json.loads(self.cursor_path.read_text(encoding="utf-8"))
        item = payload.get("items", {}).get(key)
        if item is None:
            return None
        return FetchCursor(
            key=key,
            value=str(item["value"]),
            updated_at_utc=datetime.fromisoformat(str(item["updated_at_utc"])),
        )

    def save_cursor(self, cursor: FetchCursor) -> None:
        payload: dict[str, object]
        if self.cursor_path.exists():
            payload = json.loads(self.cursor_path.read_text(encoding="utf-8"))
        else:
            payload = {"updated_at": None, "items": {}}

        items = payload.setdefault("items", {})
        assert isinstance(items, dict)
        items[cursor.key] = {
            "value": cursor.value,
            "updated_at_utc": cursor.updated_at_utc.isoformat(),
        }
        payload["updated_at"] = datetime.now(UTC).isoformat()
        self._write_json(self.cursor_path, payload)

    def _day_dir(self, day: date) -> Path:
        path = self.daily_root / day.isoformat()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _write_json(self, path: Path, payload: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
