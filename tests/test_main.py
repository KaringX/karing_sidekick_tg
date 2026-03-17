from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from tg_digest.__main__ import WORKER_RETRY_DELAY_SECONDS, _run_worker_iteration
from tg_digest.config import AppConfig
from tg_digest.errors import CollectorError
from tg_digest.services.daily_digest import DailyDigestService


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


@dataclass
class FakeService:
    config: AppConfig
    should_fail: bool = False

    async def run_for_day(self, target_day: object) -> dict[str, object]:
        del target_day
        if self.should_fail:
            raise CollectorError("Bot API getUpdates request failed: ConnectError")
        return {"run_status": "ok"}


def test_worker_iteration_retries_after_collector_error() -> None:
    payload, sleep_seconds, stream = asyncio.run(
        _run_worker_iteration(
            cast(DailyDigestService, FakeService(config=_config(), should_fail=True))
        )
    )

    assert payload == {
        "status": "retrying_after_error",
        "error": "Bot API getUpdates request failed: ConnectError",
        "retry_in_seconds": WORKER_RETRY_DELAY_SECONDS,
    }
    assert sleep_seconds == WORKER_RETRY_DELAY_SECONDS
    assert stream is sys.stderr


def test_worker_iteration_uses_polling_interval_on_success() -> None:
    payload, sleep_seconds, stream = asyncio.run(
        _run_worker_iteration(cast(DailyDigestService, FakeService(config=_config())))
    )

    assert payload == {"run_status": "ok"}
    assert sleep_seconds == 30
    assert stream is sys.stdout
