from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class UtcClock:
    def now(self) -> datetime:
        return datetime.now(UTC)
