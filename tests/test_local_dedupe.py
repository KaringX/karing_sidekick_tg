from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from kx_sidekick.config import DedupeConfig
from kx_sidekick.ingest.local_dedupe import LocalDedupeStore
from kx_sidekick.models import ChatRef, MessageRecord


def _message(
    message_id: str, text: str, fingerprint: str | None = None
) -> MessageRecord:
    return MessageRecord(
        source="bot_api",
        chat=ChatRef(source="bot_api", chat_id="chat-1", chat_type="group"),
        message_id=message_id,
        posted_at_utc=datetime(2026, 3, 16, 0, 0, tzinfo=UTC),
        text=text,
        raw_text=text,
        fingerprint=fingerprint,
    )


def test_local_dedupe_store_persists_state(tmp_path: Path) -> None:
    config = DedupeConfig(state_dir=tmp_path / "state", ttl_seconds=3600, max_keys=100)
    store = LocalDedupeStore(config)
    message = _message("1", "fix login timeout", "sha256:abc")

    assert store.is_duplicate(message) is False

    store.remember([message])
    reloaded = LocalDedupeStore(config)

    assert reloaded.is_duplicate(message) is True
