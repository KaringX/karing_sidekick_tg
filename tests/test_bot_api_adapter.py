from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from kx_sidekick.adapters.telegram_bot_api import BotApiCollector
from kx_sidekick.errors import CollectorError


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
