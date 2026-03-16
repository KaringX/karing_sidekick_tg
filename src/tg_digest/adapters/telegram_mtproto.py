from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from tg_digest.errors import UnsupportedModeError
from tg_digest.models import ChatRef, FetchCursor, MessageRecord


@dataclass
class MtprotoCollector:
    async def fetch_messages(
        self,
        chat: ChatRef,
        start_utc: datetime,
        end_utc: datetime,
        cursor: FetchCursor | None = None,
        limit: int = 100,
    ) -> tuple[list[MessageRecord], FetchCursor | None]:
        del chat, start_utc, end_utc, cursor, limit
        raise UnsupportedModeError("MTProto collector is reserved for a later phase")
