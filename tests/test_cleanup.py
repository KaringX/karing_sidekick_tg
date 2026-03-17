from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from kx_sidekick.services.cleanup import CleanupService


@dataclass
class FakeStorage:
    deleted_days: list[int]

    def delete_messages_older_than(self, days: int) -> int:
        self.deleted_days.append(days)
        return 7


def test_cleanup_service_deletes_old_messages_and_media_dirs(tmp_path: Path) -> None:
    media_root = tmp_path / "data" / "media"
    (media_root / "20260201").mkdir(parents=True)
    (media_root / "20260317").mkdir(parents=True)
    (media_root / "keep-me").mkdir(parents=True)
    storage = FakeStorage(deleted_days=[])
    service = CleanupService(
        storage=storage,
        state_dir=tmp_path / "state",
        media_root_dir=media_root,
    )

    summary = service.run(messages_days=30, media_days=1)

    assert summary["deleted_messages"] == 7
    assert summary["deleted_media_dirs"] == 1
    assert storage.deleted_days == [30]
    assert not (media_root / "20260201").exists()
    assert (media_root / "keep-me").exists()


def test_cleanup_service_runs_only_once_per_day(tmp_path: Path) -> None:
    storage = FakeStorage(deleted_days=[])
    service = CleanupService(storage=storage, state_dir=tmp_path / "state")

    first_summary = service.run_daily_if_due(
        messages_days=30,
        media_days=None,
        today=date(2026, 3, 18),
    )
    second_summary = service.run_daily_if_due(
        messages_days=30,
        media_days=None,
        today=date(2026, 3, 18),
    )

    assert first_summary is not None
    assert second_summary is None
    assert storage.deleted_days == [30]
