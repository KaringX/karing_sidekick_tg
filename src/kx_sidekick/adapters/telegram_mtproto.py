from __future__ import annotations

from dataclasses import dataclass

from kx_sidekick.errors import UnsupportedModeError
from kx_sidekick.models import FetchCursor, MessageRecord


@dataclass
class MtprotoCollector:
    async def fetch_messages(
        self,
        cursor: FetchCursor | None = None,
        limit: int = 100,
    ) -> tuple[list[MessageRecord], FetchCursor | None]:
        del cursor, limit
        raise UnsupportedModeError("MTProto collector is reserved for a later phase")
