from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any

from kx_sidekick.models import AuthorRef, ChatRef, MessageRecord, MessageStats

WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    cleaned = WHITESPACE_RE.sub(" ", text).strip()
    return cleaned


def build_fingerprint(text: str) -> str | None:
    normalized = normalize_text(text).casefold()
    if len(normalized) < 40:
        return None
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def message_from_bot_update(update: dict[str, Any]) -> MessageRecord | None:
    message = update.get("message") or update.get("channel_post")
    if message is None:
        return None

    raw_text = message.get("text") or message.get("caption") or ""
    text = normalize_text(raw_text)
    if not text:
        return None

    chat = message["chat"]
    date_value = datetime.fromtimestamp(message["date"], tz=UTC)
    edited_value = message.get("edit_date")
    edited_at_utc = (
        datetime.fromtimestamp(edited_value, tz=UTC)
        if edited_value is not None
        else None
    )
    media_kind = _detect_media_kind(message)
    media = _extract_media_payload(message, media_kind)
    username = chat.get("username")
    message_id = str(message["message_id"])
    chat_id = str(chat["id"])
    link = f"https://t.me/{username}/{message_id}" if username else None

    return MessageRecord(
        source="bot_api",
        chat=ChatRef(
            source="bot_api",
            chat_id=chat_id,
            chat_type=str(chat.get("type", "unknown")),
            chat_title=chat.get("title"),
            chat_username=username,
        ),
        message_id=message_id,
        posted_at_utc=date_value,
        edited_at_utc=edited_at_utc,
        text=text,
        raw_text=raw_text,
        author=AuthorRef(
            author_id=str(message["from"]["id"]) if message.get("from") else None,
            author_name=_author_name(message.get("from")),
        ),
        media_kind=media_kind,
        media=media,
        stats=MessageStats(),
        link=link,
        fingerprint=build_fingerprint(text),
        raw_summary={
            "update_id": int(update.get("update_id", 0)),
            "chat_type": str(chat.get("type", "unknown")),
        },
    )


def _author_name(author: dict[str, Any] | None) -> str | None:
    if author is None:
        return None
    full_name = " ".join(
        part for part in [author.get("first_name"), author.get("last_name")] if part
    )
    if full_name:
        return full_name
    username = author.get("username")
    return str(username) if username is not None else None


def _detect_media_kind(message: dict[str, Any]) -> str | None:
    for key in ("photo", "video", "document", "animation", "audio"):
        if key in message:
            return key
    return None


def _extract_media_payload(
    message: dict[str, Any], media_kind: str | None
) -> dict[str, object] | None:
    if media_kind is None:
        return None

    if media_kind == "photo":
        return _extract_photo_payload(message)

    media_value = message.get(media_kind)
    if not isinstance(media_value, dict):
        return None

    payload: dict[str, object] = {
        "kind": media_kind,
        "telegram": _compact_dict(
            {
                "file_id": _optional_string(media_value.get("file_id")),
                "file_unique_id": _optional_string(media_value.get("file_unique_id")),
                "file_size": _optional_integer(media_value.get("file_size")),
            }
        ),
        media_kind: _compact_dict(
            {
                "width": _optional_integer(media_value.get("width")),
                "height": _optional_integer(media_value.get("height")),
                "duration_seconds": _optional_integer(media_value.get("duration")),
                "mime_type": _optional_string(media_value.get("mime_type")),
                "file_name": _optional_string(media_value.get("file_name")),
                "thumbnail_file_id": _thumbnail_file_id(media_value),
            }
        ),
    }
    caption = message.get("caption")
    if isinstance(caption, str) and caption:
        payload["caption"] = caption
    return payload


def _extract_photo_payload(message: dict[str, Any]) -> dict[str, object] | None:
    photo_sizes = message.get("photo")
    if not isinstance(photo_sizes, list) or not photo_sizes:
        return None

    best_photo = next(
        (
            item
            for item in reversed(photo_sizes)
            if isinstance(item, dict) and item.get("file_id")
        ),
        None,
    )
    if best_photo is None:
        return None

    payload: dict[str, object] = {
        "kind": "photo",
        "telegram": _compact_dict(
            {
                "file_id": _optional_string(best_photo.get("file_id")),
                "file_unique_id": _optional_string(best_photo.get("file_unique_id")),
                "file_size": _optional_integer(best_photo.get("file_size")),
            }
        ),
        "photo": _compact_dict(
            {
                "width": _optional_integer(best_photo.get("width")),
                "height": _optional_integer(best_photo.get("height")),
                "variants": _photo_variants(photo_sizes),
            }
        ),
    }
    caption = message.get("caption")
    if isinstance(caption, str) and caption:
        payload["caption"] = caption
    return payload


def _photo_variants(photo_sizes: list[object]) -> list[dict[str, object]]:
    variants: list[dict[str, object]] = []
    for item in photo_sizes:
        if not isinstance(item, dict):
            continue
        file_id = _optional_string(item.get("file_id"))
        if file_id is None:
            continue
        variant = _compact_dict(
            {
                "file_id": file_id,
                "file_unique_id": _optional_string(item.get("file_unique_id")),
                "file_size": _optional_integer(item.get("file_size")),
                "width": _optional_integer(item.get("width")),
                "height": _optional_integer(item.get("height")),
            }
        )
        variants.append(variant)
    return variants


def _thumbnail_file_id(media_value: dict[str, Any]) -> str | None:
    thumbnail = media_value.get("thumbnail") or media_value.get("thumb")
    if not isinstance(thumbnail, dict):
        return None
    return _optional_string(thumbnail.get("file_id"))


def _optional_string(value: object) -> str | None:
    return str(value) if value is not None else None


def _optional_integer(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    return None


def _compact_dict(values: dict[str, object | None]) -> dict[str, object]:
    return {key: value for key, value in values.items() if value is not None}
