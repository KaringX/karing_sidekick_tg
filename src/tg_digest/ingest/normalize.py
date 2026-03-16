from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any

from tg_digest.models import AuthorRef, ChatRef, MessageRecord, MessageStats

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
