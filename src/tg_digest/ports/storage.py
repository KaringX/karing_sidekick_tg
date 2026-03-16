from __future__ import annotations

from datetime import date
from typing import Protocol

from tg_digest.models import ArticleCandidate, FetchCursor, MessageRecord


class DailyStorage(Protocol):
    def load_messages(self, day: date) -> list[MessageRecord]: ...

    def save_messages(self, day: date, messages: list[MessageRecord]) -> None: ...

    def save_candidates(
        self, day: date, candidates: list[ArticleCandidate]
    ) -> None: ...

    def save_summary(self, day: date, summary: dict[str, object]) -> None: ...

    def load_cursor(self, key: str) -> FetchCursor | None: ...

    def save_cursor(self, cursor: FetchCursor) -> None: ...
