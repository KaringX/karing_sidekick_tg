from __future__ import annotations

from datetime import UTC, datetime

from tg_digest.ingest.dedupe import dedupe_messages
from tg_digest.models import ChatRef, MessageRecord


def _message(message_id: str, text: str, fingerprint: str | None) -> MessageRecord:
    return MessageRecord(
        source="bot_api",
        chat=ChatRef(source="bot_api", chat_id="chat-1", chat_type="group"),
        message_id=message_id,
        posted_at_utc=datetime(2026, 3, 16, 0, 0, tzinfo=UTC),
        text=text,
        raw_text=text,
        fingerprint=fingerprint,
    )


def test_dedupe_messages_prefers_longer_text() -> None:
    messages = [
        _message("1", "fix login issue", "sha256:abc"),
        _message("2", "fix login issue with 3 steps and screenshots", "sha256:abc"),
    ]

    deduped = dedupe_messages(messages)

    assert len(deduped) == 1
    assert deduped[0].message_id == "2"
