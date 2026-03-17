from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kx_sidekick.errors import MediaDownloadError
from kx_sidekick.models import MediaDownloadRecord
from kx_sidekick.services.media_download import (
    MediaDownloadCursorStore,
    MediaDownloadService,
)


@dataclass
class FakeStorage:
    records: list[MediaDownloadRecord]
    calls: list[int] = field(default_factory=list)

    def list_media_messages_after_id(
        self,
        after_id: int,
        kinds: tuple[str, ...],
        limit: int,
    ) -> list[MediaDownloadRecord]:
        del kinds, limit
        self.calls.append(after_id)
        return [record for record in self.records if record.id > after_id]


@dataclass
class FakeTelegram:
    file_path: str = "photos/test-file.jpg"
    fail_download: bool = False
    get_file_calls: list[str] = field(default_factory=list)

    async def get_file(self, file_id: str) -> dict[str, str]:
        self.get_file_calls.append(file_id)
        return {"file_path": self.file_path}

    async def download_file(self, file_path: str) -> bytes:
        if self.fail_download:
            raise RuntimeError(f"download failed for {file_path}")
        return b"image-bytes"


def _record(message_id: int, day: int = 18) -> MediaDownloadRecord:
    return MediaDownloadRecord(
        id=message_id,
        posted_at_utc=datetime(2026, 3, day, 8, 0, tzinfo=UTC),
        media_kind="photo",
        media={
            "kind": "photo",
            "telegram": {
                "file_id": f"file-{message_id}",
                "file_unique_id": f"uniq-{message_id}",
            },
        },
    )


def test_media_download_uses_posted_date_directories_and_saves_cursor(
    tmp_path: Path,
) -> None:
    state_dir = tmp_path / "state"
    media_root = tmp_path / "data" / "media"
    service = MediaDownloadService(
        storage=FakeStorage(records=[_record(10)]),
        telegram=FakeTelegram(),
        cursor_store=MediaDownloadCursorStore(state_dir),
        batch_size=100,
        media_root_dir=media_root,
    )

    summary = asyncio.run(service.run())

    assert summary["downloaded"] == 1
    assert (media_root / "20260318" / "uniq-10.jpg").read_bytes() == b"image-bytes"
    cursor_payload = json.loads((state_dir / "media_download_cursor.json").read_text())
    assert cursor_payload["photo"]["last_message_id"] == 10


def test_media_download_uses_kind_specific_cursor_when_start_id_missing(
    tmp_path: Path,
) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "media_download_cursor.json").write_text(
        json.dumps(
            {
                "photo": {
                    "last_message_id": 12,
                    "last_posted_at_utc": "2026-03-18T08:00:00+00:00",
                    "updated_at_utc": "2026-03-18T08:10:00+00:00",
                },
                "all": {
                    "last_message_id": 99,
                    "last_posted_at_utc": "2026-03-18T08:00:00+00:00",
                    "updated_at_utc": "2026-03-18T08:10:00+00:00",
                },
            }
        ),
        encoding="utf-8",
    )
    storage = FakeStorage(records=[_record(13)])
    service = MediaDownloadService(
        storage=storage,
        telegram=FakeTelegram(),
        cursor_store=MediaDownloadCursorStore(state_dir),
        batch_size=100,
        media_root_dir=tmp_path / "data" / "media",
    )

    summary = asyncio.run(service.run(kind="photo"))

    assert summary["downloaded"] == 1
    assert storage.calls == [12]


def test_media_download_exits_after_three_consecutive_failures(tmp_path: Path) -> None:
    service = MediaDownloadService(
        storage=FakeStorage(records=[_record(1), _record(2), _record(3)]),
        telegram=FakeTelegram(fail_download=True),
        cursor_store=MediaDownloadCursorStore(tmp_path / "state"),
        batch_size=100,
        media_root_dir=tmp_path / "data" / "media",
    )

    with pytest.raises(MediaDownloadError) as exc_info:
        asyncio.run(service.run())

    assert str(exc_info.value) == "Media download failed for 3 consecutive files"
