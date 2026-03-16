from __future__ import annotations

from datetime import datetime
from typing import Protocol

from tg_digest.models import ChatRef, FetchCursor, MessageRecord


class TelegramCollector(Protocol):
    async def fetch_messages(
        self,
        chat: ChatRef,
        start_utc: datetime,
        end_utc: datetime,
        cursor: FetchCursor | None = None,
        limit: int = 100,
    ) -> tuple[list[MessageRecord], FetchCursor | None]: ...
