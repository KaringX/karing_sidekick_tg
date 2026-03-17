from __future__ import annotations

from typing import Protocol

from kx_sidekick.models import FetchCursor, MessageRecord


class TelegramCollector(Protocol):
    async def fetch_messages(
        self,
        cursor: FetchCursor | None = None,
        limit: int = 100,
    ) -> tuple[list[MessageRecord], FetchCursor | None]: ...
