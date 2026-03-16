from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

from tg_digest.config import AppConfig
from tg_digest.models import ChatRef, FetchCursor, MessageRecord
from tg_digest.services.daily_digest import DailyDigestService


@dataclass
class FakeCollector:
    messages: list[MessageRecord]

    async def fetch_messages(
        self,
        chat: ChatRef,
        start_utc: datetime,
        end_utc: datetime,
        cursor: FetchCursor | None = None,
        limit: int = 100,
    ) -> tuple[list[MessageRecord], FetchCursor | None]:
        del start_utc, end_utc, cursor, limit
        return [
            message for message in self.messages if message.chat.chat_id == chat.chat_id
        ], None


@dataclass
class FakeStorage:
    messages: list[MessageRecord] = field(default_factory=list)
    cursors: dict[str, FetchCursor] = field(default_factory=dict)
    candidates: list[Any] = field(default_factory=list)
    summary: dict[str, object] = field(default_factory=dict)

    def load_messages(self, day: date) -> list[MessageRecord]:
        del day
        return self.messages

    def save_messages(self, day: date, messages: list[MessageRecord]) -> None:
        del day
        self.messages = messages

    def save_candidates(self, day: date, candidates: list[Any]) -> None:
        del day
        self.candidates = candidates

    def save_summary(self, day: date, summary: dict[str, object]) -> None:
        del day
        self.summary = summary

    def load_cursor(self, key: str) -> FetchCursor | None:
        return self.cursors.get(key)

    def save_cursor(self, cursor: FetchCursor) -> None:
        self.cursors[cursor.key] = cursor


def _config() -> AppConfig:
    return AppConfig(
        telegram_mode="bot_api",
        bot_token="token",
        allowed_chat_ids=("chat-1",),
        data_dir=Path("data"),
        timezone="UTC",
        max_candidates=3,
        min_text_length=40,
        polling_batch_size=100,
        polling_interval_seconds=30,
        tutorial_keywords=("step",),
        troubleshoot_keywords=("fix", "timeout"),
        noise_keywords=("广告",),
    )


def test_daily_digest_runs_end_to_end() -> None:
    message = MessageRecord(
        source="bot_api",
        chat=ChatRef(source="bot_api", chat_id="chat-1", chat_type="group"),
        message_id="1",
        posted_at_utc=datetime(2026, 3, 16, 8, 0, tzinfo=UTC),
        text="fix login timeout step 1 clear cache step 2 relogin step 3 retry sync",
        raw_text=(
            "fix login timeout step 1 clear cache step 2 relogin step 3 retry sync"
        ),
    )
    service = DailyDigestService(FakeCollector([message]), FakeStorage(), _config())

    summary = asyncio.run(service.run_for_day(date(2026, 3, 16)))
    stats = cast(dict[str, int], summary["stats"])

    assert summary["run_status"] == "ok"
    assert stats["selected"] == 1
