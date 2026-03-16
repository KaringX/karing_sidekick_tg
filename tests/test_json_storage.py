from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from tg_digest.adapters.json_storage import JsonDailyStorage
from tg_digest.models import ChatRef, FetchCursor, MessageRecord


def test_json_storage_saves_messages_and_cursor(tmp_path: Path) -> None:
    storage = JsonDailyStorage(tmp_path)
    day = date(2026, 3, 16)
    message = MessageRecord(
        source="bot_api",
        chat=ChatRef(source="bot_api", chat_id="chat-1", chat_type="group"),
        message_id="1",
        posted_at_utc=datetime(2026, 3, 16, 8, 0, tzinfo=UTC),
        text="fix login timeout with 3 steps for Android app users right now",
        raw_text="fix login timeout with 3 steps for Android app users right now",
    )

    storage.save_messages(day, [message])
    storage.save_cursor(
        FetchCursor(
            key="bot_api:chat-1",
            value="200",
            updated_at_utc=message.posted_at_utc,
        )
    )

    messages_path = tmp_path / "daily" / "2026-03-16" / "messages.json"
    payload = json.loads(messages_path.read_text(encoding="utf-8"))
    loaded_messages = storage.load_messages(day)

    assert payload["items"][0]["external_id"] == "bot_api:chat-1:1"
    assert payload["items"][0]["raw_text"] == message.raw_text
    assert loaded_messages[0].raw_text == message.raw_text
    assert storage.load_cursor("bot_api:chat-1") is not None
