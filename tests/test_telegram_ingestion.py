from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from kx_sidekick.config import DedupeConfig
from kx_sidekick.ingest.local_dedupe import LocalDedupeStore
from kx_sidekick.models import ChatRef, FetchCursor, MessageRecord
from kx_sidekick.services.telegram_ingestion import TelegramIngestionService


@dataclass
class FakeCollector:
    messages: list[MessageRecord]
    cursor: FetchCursor | None = None

    async def fetch_messages(
        self,
        cursor: FetchCursor | None = None,
        limit: int = 100,
    ) -> tuple[list[MessageRecord], FetchCursor | None]:
        del cursor, limit
        return self.messages, self.cursor


@dataclass
class FakeStorage:
    cursor: FetchCursor | None = None
    saved_messages: list[MessageRecord] = field(default_factory=list)
    saved_cursor: FetchCursor | None = None

    def ensure_connected(self) -> None:
        return None

    def save_messages(self, messages: list[MessageRecord]) -> int:
        self.saved_messages.extend(messages)
        return len(messages)

    def load_cursor(self, key: str) -> FetchCursor | None:
        assert key == "bot_api:updates"
        return self.cursor

    def save_cursor(self, cursor: FetchCursor) -> None:
        self.saved_cursor = cursor


def _message(
    message_id: str, text: str, fingerprint: str | None = None
) -> MessageRecord:
    return MessageRecord(
        source="bot_api",
        chat=ChatRef(source="bot_api", chat_id="chat-1", chat_type="group"),
        message_id=message_id,
        posted_at_utc=datetime(2026, 3, 16, 0, 0, tzinfo=UTC),
        text=text,
        raw_text=text,
        fingerprint=fingerprint,
    )


def test_telegram_ingestion_service_saves_unique_messages(tmp_path: Path) -> None:
    dedupe_store = LocalDedupeStore(
        DedupeConfig(state_dir=tmp_path / "state", ttl_seconds=3600, max_keys=100)
    )
    messages = [
        _message("1", "fix login timeout step 1 clear cache", "sha256:aaa"),
        _message("2", "fix login timeout step 1 clear cache and retry", "sha256:aaa"),
    ]
    cursor = FetchCursor(
        key="bot_api:updates",
        value="11",
        updated_at_utc=datetime(2026, 3, 16, 0, 0, tzinfo=UTC),
    )
    storage = FakeStorage()
    service = TelegramIngestionService(
        collector=FakeCollector(messages=messages, cursor=cursor),
        storage=storage,
        dedupe_store=dedupe_store,
        polling_batch_size=100,
    )

    summary = asyncio.run(service.run_once())

    assert summary == {
        "run_status": "ok",
        "fetched": 2,
        "deduped_in_batch": 1,
        "skipped_local_duplicates": 0,
        "stored": 1,
    }
    assert len(storage.saved_messages) == 1
    assert storage.saved_messages[0].message_id == "2"
    assert storage.saved_cursor == cursor
