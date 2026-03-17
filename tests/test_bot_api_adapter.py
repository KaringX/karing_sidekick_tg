from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from kx_sidekick.adapters.telegram_bot_api import BotApiCollector, BotApiNotifier
from kx_sidekick.errors import CollectorError, NotificationError


def test_bot_api_adapter_fetches_allowed_chat_messages() -> None:
    calls: list[str | None] = []

    class PatchedCollector(BotApiCollector):
        async def _get_updates(
            self, offset: str | None, limit: int
        ) -> list[dict[str, Any]]:
            del limit
            calls.append(offset)
            if offset is None:
                return [
                    {
                        "update_id": 10,
                        "message": {
                            "message_id": 3,
                            "date": 1773619200,
                            "text": (
                                "fix login timeout step 1 clear cache and retry now"
                            ),
                            "photo": [
                                {
                                    "file_id": "photo-small",
                                    "file_unique_id": "photo-uniq-small",
                                    "file_size": 64,
                                    "width": 40,
                                    "height": 40,
                                },
                                {
                                    "file_id": "photo-large",
                                    "file_unique_id": "photo-uniq-large",
                                    "file_size": 256,
                                    "width": 400,
                                    "height": 400,
                                },
                            ],
                            "chat": {
                                "id": -1001,
                                "type": "supergroup",
                                "title": "Support",
                            },
                        },
                    },
                    {
                        "update_id": 11,
                        "message": {
                            "message_id": 4,
                            "date": 1773619200,
                            "text": "this chat should be filtered out",
                            "chat": {"id": -1002, "type": "supergroup"},
                        },
                    },
                ]
            return []

    collector = PatchedCollector(bot_token="token", allowed_chat_ids=("-1001",))

    messages, cursor = asyncio.run(collector.fetch_messages(limit=100))

    assert calls == [None]
    assert len(messages) == 1
    assert messages[0].chat.chat_id == "-1001"
    assert messages[0].media_kind == "photo"
    assert messages[0].media == {
        "kind": "photo",
        "telegram": {
            "file_id": "photo-large",
            "file_unique_id": "photo-uniq-large",
            "file_size": 256,
        },
        "photo": {
            "width": 400,
            "height": 400,
            "variants": [
                {
                    "file_id": "photo-small",
                    "file_unique_id": "photo-uniq-small",
                    "file_size": 64,
                    "width": 40,
                    "height": 40,
                },
                {
                    "file_id": "photo-large",
                    "file_unique_id": "photo-uniq-large",
                    "file_size": 256,
                    "width": 400,
                    "height": 400,
                },
            ],
        },
    }
    assert cursor is not None
    assert cursor.value == "12"


def test_bot_api_adapter_retries_three_times_on_connect_error() -> None:
    attempts: list[int] = []

    class PatchedCollector(BotApiCollector):
        async def _request_updates(
            self, url: str, params: dict[str, int]
        ) -> httpx.Response:
            del params
            attempts.append(1)
            request = httpx.Request("GET", url)
            raise httpx.ConnectError("network down", request=request)

    collector = PatchedCollector(bot_token="token")

    with pytest.raises(CollectorError) as exc_info:
        asyncio.run(collector._get_updates(offset=None, limit=1))

    assert str(exc_info.value) == "Bot API getUpdates request failed after 3 attempts"
    assert len(attempts) == 3


def test_bot_api_notifier_raises_on_http_error() -> None:
    class PatchedNotifier(BotApiNotifier):
        async def _post_message(
            self, url: str, payload: dict[str, object]
        ) -> httpx.Response:
            del payload
            request = httpx.Request("POST", url)
            raise httpx.ConnectError("network down", request=request)

    notifier = PatchedNotifier(bot_token="token")

    with pytest.raises(NotificationError) as exc_info:
        asyncio.run(notifier.send_message(chat_id="-1001", text="failure"))

    assert str(exc_info.value) == "Telegram sendMessage request failed"


def test_bot_api_notifier_get_me_reads_bot_profile() -> None:
    class PatchedNotifier(BotApiNotifier):
        async def _post_message(
            self, url: str, payload: dict[str, object]
        ) -> httpx.Response:
            del url, payload
            request = httpx.Request("POST", "https://api.telegram.org")
            return httpx.Response(
                200,
                request=request,
                json={"ok": True, "result": {"id": 1, "username": "sidekick_bot"}},
            )

    notifier = PatchedNotifier(bot_token="token")

    profile = asyncio.run(notifier.get_me())

    assert profile["username"] == "sidekick_bot"
