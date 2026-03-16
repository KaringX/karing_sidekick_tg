from __future__ import annotations

from tg_digest.ingest.normalize import build_fingerprint, message_from_bot_update


def test_message_from_bot_update_normalizes_text() -> None:
    update = {
        "update_id": 123,
        "message": {
            "message_id": 88,
            "date": 1710000000,
            "text": "  fix login timeout  \n on Android  ",
            "chat": {"id": -1001, "type": "supergroup", "title": "Support"},
            "from": {"id": 9, "first_name": "Alice"},
        },
    }

    message = message_from_bot_update(update)

    assert message is not None
    assert message.text == "fix login timeout on Android"
    assert message.raw_text == "  fix login timeout  \n on Android  "
    assert message.external_id == "bot_api:-1001:88"


def test_build_fingerprint_ignores_short_text() -> None:
    assert build_fingerprint("short text") is None
