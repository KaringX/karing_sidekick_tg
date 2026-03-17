from __future__ import annotations

from typing import Protocol

from kx_sidekick.models import FetchCursor, MessageRecord


class MessageStorage(Protocol):
    def ensure_connected(self) -> None: ...

    def save_messages(self, messages: list[MessageRecord]) -> int: ...

    def load_cursor(self, key: str) -> FetchCursor | None: ...

    def save_cursor(self, cursor: FetchCursor) -> None: ...
