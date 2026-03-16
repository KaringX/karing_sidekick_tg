from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from tg_digest.config import AppConfig
from tg_digest.models import ChatRef, MessageRecord
from tg_digest.pipeline.score import score_message


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
        tutorial_keywords=("步骤",),
        troubleshoot_keywords=("fix", "timeout"),
        noise_keywords=("广告",),
    )


def test_score_message_rewards_actionable_fix() -> None:
    message = MessageRecord(
        source="bot_api",
        chat=ChatRef(source="bot_api", chat_id="chat-1", chat_type="group"),
        message_id="1",
        posted_at_utc=datetime(2026, 3, 16, 0, 0, tzinfo=UTC),
        text="Fix login timeout: step 1 clear cache, step 2 relogin, step 3 retry sync",
        raw_text=(
            "Fix login timeout: step 1 clear cache, step 2 relogin, step 3 retry sync"
        ),
    )

    score = score_message(message, _config())

    assert score.total >= 55
    assert "包含明确步骤" in score.reasons
