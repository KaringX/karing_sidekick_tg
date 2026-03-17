from __future__ import annotations

from kx_sidekick.ingest.normalize import build_fingerprint, message_from_bot_update


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


def test_message_from_bot_update_extracts_photo_media_metadata() -> None:
    update = {
        "update_id": 124,
        "message": {
            "message_id": 89,
            "date": 1710000000,
            "caption": " install steps screenshot ",
            "chat": {"id": -1001, "type": "supergroup", "title": "Support"},
            "photo": [
                {
                    "file_id": "small-photo",
                    "file_unique_id": "small-uniq",
                    "file_size": 123,
                    "width": 90,
                    "height": 90,
                },
                {
                    "file_id": "large-photo",
                    "file_unique_id": "large-uniq",
                    "file_size": 456,
                    "width": 1280,
                    "height": 720,
                },
            ],
        },
    }

    message = message_from_bot_update(update)

    assert message is not None
    assert message.media_kind == "photo"
    assert message.media == {
        "kind": "photo",
        "telegram": {
            "file_id": "large-photo",
            "file_unique_id": "large-uniq",
            "file_size": 456,
        },
        "photo": {
            "width": 1280,
            "height": 720,
            "variants": [
                {
                    "file_id": "small-photo",
                    "file_unique_id": "small-uniq",
                    "file_size": 123,
                    "width": 90,
                    "height": 90,
                },
                {
                    "file_id": "large-photo",
                    "file_unique_id": "large-uniq",
                    "file_size": 456,
                    "width": 1280,
                    "height": 720,
                },
            ],
        },
        "caption": " install steps screenshot ",
    }


def test_message_from_bot_update_extracts_video_media_metadata() -> None:
    update = {
        "update_id": 125,
        "message": {
            "message_id": 90,
            "date": 1710000000,
            "caption": "video fix walkthrough",
            "chat": {"id": -1001, "type": "supergroup", "title": "Support"},
            "video": {
                "file_id": "video-file",
                "file_unique_id": "video-uniq",
                "file_size": 98765,
                "width": 720,
                "height": 1280,
                "duration": 42,
                "mime_type": "video/mp4",
                "thumbnail": {"file_id": "thumb-file"},
            },
        },
    }

    message = message_from_bot_update(update)

    assert message is not None
    assert message.media_kind == "video"
    assert message.media == {
        "kind": "video",
        "telegram": {
            "file_id": "video-file",
            "file_unique_id": "video-uniq",
            "file_size": 98765,
        },
        "video": {
            "width": 720,
            "height": 1280,
            "duration_seconds": 42,
            "mime_type": "video/mp4",
            "thumbnail_file_id": "thumb-file",
        },
        "caption": "video fix walkthrough",
    }
