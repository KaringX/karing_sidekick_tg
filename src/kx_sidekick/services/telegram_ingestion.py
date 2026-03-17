from __future__ import annotations

from dataclasses import dataclass

from kx_sidekick.ingest.dedupe import dedupe_messages
from kx_sidekick.ingest.local_dedupe import LocalDedupeStore
from kx_sidekick.ports.storage import MessageStorage
from kx_sidekick.ports.telegram import TelegramCollector


@dataclass
class TelegramIngestionService:
    collector: TelegramCollector
    storage: MessageStorage
    dedupe_store: LocalDedupeStore
    polling_batch_size: int
    cursor_key: str = "bot_api:updates"

    async def run_once(self) -> dict[str, int | str]:
        cursor = self.storage.load_cursor(self.cursor_key)
        fetched_messages, next_cursor = await self.collector.fetch_messages(
            cursor=cursor,
            limit=self.polling_batch_size,
        )
        deduped_messages = dedupe_messages(fetched_messages)
        accepted_messages = [
            message
            for message in deduped_messages
            if not self.dedupe_store.is_duplicate(message)
        ]
        inserted = self.storage.save_messages(accepted_messages)
        if next_cursor is not None:
            self.storage.save_cursor(next_cursor)
        self.dedupe_store.remember(accepted_messages)
        return {
            "run_status": "ok",
            "fetched": len(fetched_messages),
            "deduped_in_batch": len(deduped_messages),
            "skipped_local_duplicates": len(deduped_messages) - len(accepted_messages),
            "stored": inserted,
        }
