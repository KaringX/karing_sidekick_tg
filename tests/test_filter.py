from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from tg_digest.config import AppConfig
from tg_digest.models import ChatRef, MessageRecord
from tg_digest.pipeline.filter import filter_candidate_messages


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
        tutorial_keywords=("教程", "步骤"),
        troubleshoot_keywords=("fix", "解决", "报错"),
        noise_keywords=("招聘", "推广"),
    )


def _message(text: str) -> MessageRecord:
    return MessageRecord(
        source="bot_api",
        chat=ChatRef(source="bot_api", chat_id="chat-1", chat_type="group"),
        message_id="1",
        posted_at_utc=datetime(2026, 3, 16, 0, 0, tzinfo=UTC),
        text=text,
        raw_text=text,
    )


def test_filter_candidate_messages_keeps_troubleshooting_text() -> None:
    messages = [
        _message(
            "fix login timeout with 3 steps to recover Android app access quickly"
        ),
        _message("今晚大家吃什么，这是闲聊消息不会被保留"),
    ]

    filtered = filter_candidate_messages(messages, _config())

    assert [item.text for item in filtered] == [messages[0].text]


def test_filter_candidate_messages_keeps_multilingual_support_dialogue() -> None:
    message = _message(
        "请问 iOS 登录报错怎么办？you can fix it by clearing cache, then relogin."
    )

    filtered = filter_candidate_messages([message], _config())

    assert filtered == [message]
