from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from tg_digest.errors import CollectorError
from tg_digest.ingest.normalize import message_from_bot_update
from tg_digest.models import ChatRef, FetchCursor, MessageRecord


@dataclass
class BotApiCollector:
    bot_token: str
    allowed_chat_ids: tuple[str, ...] = ()
    base_url: str = "https://api.telegram.org"

    async def fetch_messages(
        self,
        chat: ChatRef,
        start_utc: datetime,
        end_utc: datetime,
        cursor: FetchCursor | None = None,
        limit: int = 100,
    ) -> tuple[list[MessageRecord], FetchCursor | None]:
        offset = cursor.value if cursor else None
        messages: list[MessageRecord] = []
        next_cursor = cursor

        while True:
            updates = await self._get_updates(offset=offset, limit=limit)
            if not updates:
                break

            page_messages, next_cursor = self._collect_page_messages(
                updates=updates,
                chat=chat,
                start_utc=start_utc,
                end_utc=end_utc,
            )
            messages.extend(page_messages)
            offset = str(max(int(update["update_id"]) for update in updates) + 1)

            if len(updates) < limit:
                break

        return messages, next_cursor

    def _collect_page_messages(
        self,
        updates: list[dict[str, Any]],
        chat: ChatRef,
        start_utc: datetime,
        end_utc: datetime,
    ) -> tuple[list[MessageRecord], FetchCursor | None]:
        messages: list[MessageRecord] = []
        next_cursor: FetchCursor | None = None

        for update in updates:
            message = message_from_bot_update(update)
            if message is None:
                continue
            if message.chat.chat_id != chat.chat_id:
                continue
            if (
                self.allowed_chat_ids
                and message.chat.chat_id not in self.allowed_chat_ids
            ):
                continue
            if not start_utc <= message.posted_at_utc < end_utc:
                continue

            messages.append(message)
            next_cursor = FetchCursor(
                key=f"bot_api:{chat.chat_id}",
                value=str(int(update["update_id"]) + 1),
                updated_at_utc=message.posted_at_utc,
            )

        if next_cursor is None:
            update_id = max(int(update["update_id"]) for update in updates) + 1
            next_cursor = FetchCursor(
                key=f"bot_api:{chat.chat_id}",
                value=str(update_id),
                updated_at_utc=end_utc,
            )

        return messages, next_cursor

    async def _get_updates(
        self, offset: str | None, limit: int
    ) -> list[dict[str, Any]]:
        params: dict[str, int] = {"limit": limit, "timeout": 0}
        if offset is not None:
            params["offset"] = int(offset)

        url = f"{self.base_url}/bot{self.bot_token}/getUpdates"
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(url, params=params)

        if response.status_code >= 400:
            raise CollectorError(
                f"Bot API getUpdates failed with status {response.status_code}"
            )

        payload = response.json()
        if not payload.get("ok"):
            raise CollectorError(f"Bot API getUpdates failed: {payload}")
        result = payload.get("result", [])
        if not isinstance(result, list):
            raise CollectorError("Bot API getUpdates returned a non-list result")
        return result
