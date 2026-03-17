from __future__ import annotations

import json
import mimetypes
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Protocol

from kx_sidekick.errors import MediaDownloadError
from kx_sidekick.models import MediaDownloadRecord

DEFAULT_MEDIA_ROOT_DIR = Path("data/media")
CURSOR_FILE_NAME = "media_download_cursor.json"
DEFAULT_MEDIA_KIND = "photo"
MAX_FILE_ATTEMPTS = 3
MAX_CONSECUTIVE_FAILURES = 3
SAFE_FILE_NAME_LENGTH = 180


@dataclass(frozen=True)
class MediaDownloadCursor:
    last_message_id: int
    last_posted_at_utc: str
    updated_at_utc: str


class MediaDownloadStorage(Protocol):
    def list_media_messages_after_id(
        self,
        after_id: int,
        kinds: tuple[str, ...],
        limit: int,
    ) -> list[MediaDownloadRecord]: ...


class TelegramFileClient(Protocol):
    async def get_file(self, file_id: str) -> dict[str, str]: ...

    async def download_file(self, file_path: str) -> bytes: ...


class MediaDownloadCursorStore:
    def __init__(self, state_dir: Path) -> None:
        self._state_file = state_dir / CURSOR_FILE_NAME

    def load(self, kind: str) -> MediaDownloadCursor | None:
        payload = self._read_payload()
        entry = payload.get(kind)
        if not isinstance(entry, dict):
            return None
        last_message_id = entry.get("last_message_id")
        last_posted_at_utc = entry.get("last_posted_at_utc")
        updated_at_utc = entry.get("updated_at_utc")
        if not isinstance(last_message_id, int):
            return None
        if not isinstance(last_posted_at_utc, str) or not isinstance(
            updated_at_utc, str
        ):
            return None
        return MediaDownloadCursor(
            last_message_id=last_message_id,
            last_posted_at_utc=last_posted_at_utc,
            updated_at_utc=updated_at_utc,
        )

    def save(self, kind: str, record: MediaDownloadRecord) -> None:
        payload = self._read_payload()
        payload[kind] = {
            "last_message_id": record.id,
            "last_posted_at_utc": record.posted_at_utc.astimezone(UTC).isoformat(),
            "updated_at_utc": datetime.now(UTC).isoformat(),
        }
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _read_payload(self) -> dict[str, object]:
        if not self._state_file.exists():
            return {}
        try:
            payload = json.loads(self._state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}


@dataclass
class MediaDownloadService:
    storage: MediaDownloadStorage
    telegram: TelegramFileClient
    cursor_store: MediaDownloadCursorStore
    batch_size: int
    media_root_dir: Path = DEFAULT_MEDIA_ROOT_DIR

    async def run(
        self, kind: str = DEFAULT_MEDIA_KIND, start_id: int | None = None
    ) -> dict[str, int | str]:
        kinds = _expand_kind(kind)
        after_id = self._resolve_after_id(kind=kind, start_id=start_id)
        downloaded = 0
        skipped_existing = 0
        skipped_missing_media = 0
        failed = 0
        consecutive_failures = 0

        while True:
            records = self.storage.list_media_messages_after_id(
                after_id=after_id,
                kinds=kinds,
                limit=self.batch_size,
            )
            if not records:
                break

            for record in records:
                result = await self._process_record(record)
                after_id = record.id
                self.cursor_store.save(kind, record)
                if result == "downloaded":
                    downloaded += 1
                    consecutive_failures = 0
                elif result == "skipped_existing":
                    skipped_existing += 1
                    consecutive_failures = 0
                elif result == "skipped_missing_media":
                    skipped_missing_media += 1
                    consecutive_failures = 0
                else:
                    failed += 1
                    consecutive_failures += 1
                    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                        raise MediaDownloadError(
                            "Media download failed for 3 consecutive files"
                        )

            if len(records) < self.batch_size:
                break

        return {
            "run_status": "ok",
            "kind": kind,
            "start_after_id": after_id,
            "processed": downloaded + skipped_existing + skipped_missing_media + failed,
            "downloaded": downloaded,
            "skipped_existing": skipped_existing,
            "skipped_missing_media": skipped_missing_media,
            "failed": failed,
        }

    def _resolve_after_id(self, kind: str, start_id: int | None) -> int:
        if start_id is not None:
            return max(start_id - 1, 0)
        cursor = self.cursor_store.load(kind)
        if cursor is None:
            return 0
        return cursor.last_message_id

    async def _process_record(self, record: MediaDownloadRecord) -> str:
        media_telegram = _media_telegram(record.media)
        file_id = _string_value(media_telegram.get("file_id"))
        if file_id is None:
            return "skipped_missing_media"

        last_error: Exception | None = None
        for _ in range(MAX_FILE_ATTEMPTS):
            try:
                file_payload = await self.telegram.get_file(file_id)
                file_path = _string_value(file_payload.get("file_path"))
                if file_path is None:
                    raise MediaDownloadError(
                        "Telegram getFile did not return file_path "
                        f"for message {record.id}"
                    )

                target_path = self._target_path(record, file_path)
                if target_path.exists():
                    return "skipped_existing"

                content = await self.telegram.download_file(file_path)
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_bytes(content)
                return "downloaded"
            except Exception as exc:  # noqa: BLE001
                last_error = exc

        if last_error is not None:
            return "failed"
        return "failed"

    def _target_path(self, record: MediaDownloadRecord, file_path: str) -> Path:
        directory = self.media_root_dir / record.posted_at_utc.astimezone(UTC).strftime(
            "%Y%m%d"
        )
        extension = _choose_extension(file_path=file_path, media=record.media)
        file_name = _build_file_name(record.media, extension)
        return directory / file_name


def _expand_kind(kind: str) -> tuple[str, ...]:
    if kind == "all":
        return ("photo", "video", "document", "animation", "audio")
    return (kind,)


def _media_telegram(media: dict[str, object]) -> dict[str, object]:
    telegram = media.get("telegram")
    return telegram if isinstance(telegram, dict) else {}


def _string_value(value: object) -> str | None:
    return str(value) if value is not None else None


def _choose_extension(file_path: str, media: dict[str, object]) -> str:
    suffix = Path(file_path).suffix.strip()
    if suffix:
        return suffix

    mime_type = _extract_mime_type(media)
    if mime_type:
        guessed = mimetypes.guess_extension(mime_type)
        if guessed:
            return guessed

    file_name = _extract_file_name(media)
    if file_name:
        suffix = Path(file_name).suffix.strip()
        if suffix:
            return suffix

    return ""


def _extract_mime_type(media: dict[str, object]) -> str | None:
    kind = _string_value(media.get("kind"))
    if kind is None:
        return None
    details = media.get(kind)
    if not isinstance(details, dict):
        return None
    return _string_value(details.get("mime_type"))


def _extract_file_name(media: dict[str, object]) -> str | None:
    kind = _string_value(media.get("kind"))
    if kind is None:
        return None
    details = media.get(kind)
    if not isinstance(details, dict):
        return None
    return _string_value(details.get("file_name"))


def _build_file_name(media: dict[str, object], extension: str) -> str:
    telegram = _media_telegram(media)
    preferred_name = _string_value(telegram.get("file_unique_id")) or _string_value(
        telegram.get("file_id")
    )
    if preferred_name is None:
        raise MediaDownloadError("Media payload is missing file_unique_id and file_id")

    stem = preferred_name
    max_stem_length = SAFE_FILE_NAME_LENGTH - len(extension)
    if len(stem) > max_stem_length:
        digest = sha256(stem.encode("utf-8")).hexdigest()[:12]
        trimmed = stem[: max_stem_length - len(digest) - 1]
        stem = f"{trimmed}_{digest}"
    return f"{stem}{extension}"
