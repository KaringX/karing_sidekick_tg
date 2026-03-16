from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from tg_digest.config import AppConfig
from tg_digest.models import ChatRef, MessageRecord
from tg_digest.pipeline.select import select_candidates


def _config() -> AppConfig:
    return AppConfig(
        telegram_mode="bot_api",
        bot_token="token",
        allowed_chat_ids=("chat-1", "chat-2", "chat-3"),
        data_dir=Path("data"),
        timezone="UTC",
        max_candidates=2,
        min_text_length=40,
        polling_batch_size=100,
        polling_interval_seconds=30,
        tutorial_keywords=("step",),
        troubleshoot_keywords=("fix", "timeout"),
        noise_keywords=("广告",),
    )


def _message(chat_id: str, message_id: str, text: str) -> MessageRecord:
    return MessageRecord(
        source="bot_api",
        chat=ChatRef(source="bot_api", chat_id=chat_id, chat_type="group"),
        message_id=message_id,
        posted_at_utc=datetime(2026, 3, 16, 0, 0, tzinfo=UTC),
        text=text,
        raw_text=text,
    )


def test_select_candidates_limits_count() -> None:
    messages = [
        _message(
            "chat-1",
            "1",
            "fix timeout step 1 do this and step 2 do that for login issues",
        ),
        _message(
            "chat-2",
            "2",
            "fix sync timeout step 1 reconnect and step 2 refresh token now",
        ),
        _message(
            "chat-3",
            "3",
            "fix crash step 1 clean cache and step 2 reopen the mobile app",
        ),
    ]

    candidates = select_candidates(messages, _config())

    assert len(candidates) == 2
