from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from tg_digest.adapters.telegram_bot_api import BotApiCollector
from tg_digest.errors import CollectorError
from tg_digest.models import ChatRef


def test_bot_api_adapter_fetches_allowed_chat_messages() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/getUpdates")
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": [
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
                            "from": {"id": 9, "first_name": "Alice"},
                        },
                    }
                ],
            },
        )

    transport = httpx.MockTransport(handler)

    class PatchedCollector(BotApiCollector):
        async def _get_updates(
            self, offset: str | None, limit: int
        ) -> list[dict[str, Any]]:
            del offset, limit
            async with httpx.AsyncClient(transport=transport) as client:
                response = await client.get("https://api.telegram.org/botx/getUpdates")
            payload = response.json()
            assert isinstance(payload, dict)
            result = payload["result"]
            assert isinstance(result, list)
            return result

    collector = PatchedCollector(bot_token="token", allowed_chat_ids=("-1001",))
    chat = ChatRef(source="bot_api", chat_id="-1001", chat_type="group")

    messages, cursor = asyncio.run(
        collector.fetch_messages(
            chat=chat,
            start_utc=datetime(2026, 3, 16, 0, 0, tzinfo=UTC),
            end_utc=datetime(2026, 3, 17, 0, 0, tzinfo=UTC),
        )
    )

    assert len(messages) == 1
    assert cursor is not None
    assert cursor.value == "11"


def test_bot_api_adapter_keeps_fetching_until_offset_catches_up() -> None:
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
                            "message_id": 1,
                            "date": 1773619200,
                            "text": "fix login issue step 1 clear cache and retry",
                            "chat": {"id": -1001, "type": "supergroup"},
                        },
                    },
                    {
                        "update_id": 11,
                        "message": {
                            "message_id": 2,
                            "date": 1773619260,
                            "text": "fix sync issue step 1 reconnect and retry",
                            "chat": {"id": -1001, "type": "supergroup"},
                        },
                    },
                ]
            if offset == "12":
                return [
                    {
                        "update_id": 12,
                        "message": {
                            "message_id": 3,
                            "date": 1773619320,
                            "text": "fix crash step 1 reset and step 2 reopen app",
                            "chat": {"id": -1001, "type": "supergroup"},
                        },
                    }
                ]
            return []

    collector = PatchedCollector(bot_token="token", allowed_chat_ids=("-1001",))
    chat = ChatRef(source="bot_api", chat_id="-1001", chat_type="group")

    messages, cursor = asyncio.run(
        collector.fetch_messages(
            chat=chat,
            start_utc=datetime(2026, 3, 16, 0, 0, tzinfo=UTC),
            end_utc=datetime(2026, 3, 17, 0, 0, tzinfo=UTC),
            limit=2,
        )
    )

    assert len(messages) == 3
    assert calls == [None, "12"]
    assert cursor is not None
    assert cursor.value == "13"


def test_bot_api_adapter_wraps_connect_error() -> None:
    class PatchedCollector(BotApiCollector):
        async def _request_updates(
            self, url: str, params: dict[str, int]
        ) -> httpx.Response:
            request = httpx.Request("GET", url, params=params)
            raise httpx.ConnectError("network down", request=request)

    collector = PatchedCollector(bot_token="token")

    with pytest.raises(CollectorError) as exc_info:
        asyncio.run(collector._get_updates(offset=None, limit=1))

    assert str(exc_info.value) == "Bot API getUpdates request failed: ConnectError"
