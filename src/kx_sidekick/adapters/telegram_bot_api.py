from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from json import JSONDecodeError
from typing import Any

import httpx

from kx_sidekick.errors import CollectorError
from kx_sidekick.ingest.normalize import message_from_bot_update
from kx_sidekick.models import FetchCursor, MessageRecord

LOGGER = logging.getLogger(__name__)
CURSOR_KEY = "bot_api:updates"
REQUEST_TIMEOUT_SECONDS = 30.0
MAX_REQUEST_ATTEMPTS = 3


@dataclass
class BotApiCollector:
    bot_token: str
    allowed_chat_ids: tuple[str, ...] = ()
    base_url: str = "https://api.telegram.org"

    async def fetch_messages(
        self,
        cursor: FetchCursor | None = None,
        limit: int = 100,
    ) -> tuple[list[MessageRecord], FetchCursor | None]:
        offset = cursor.value if cursor else None
        messages: list[MessageRecord] = []
        next_cursor = cursor

        while True:
            updates = await self._get_updates(offset=offset, limit=limit)
            if not updates:
                break

            page_messages, next_cursor = self._collect_page_messages(updates)
            messages.extend(page_messages)
            offset = str(max(int(update["update_id"]) for update in updates) + 1)

            if len(updates) < limit:
                break

        return messages, next_cursor

    def _collect_page_messages(
        self,
        updates: list[dict[str, Any]],
    ) -> tuple[list[MessageRecord], FetchCursor]:
        messages: list[MessageRecord] = []

        for update in updates:
            message = message_from_bot_update(update)
            if message is None:
                continue
            if (
                self.allowed_chat_ids
                and message.chat.chat_id not in self.allowed_chat_ids
            ):
                continue
            messages.append(message)

        updated_at_utc = messages[-1].posted_at_utc if messages else datetime.now(UTC)
        next_cursor = FetchCursor(
            key=CURSOR_KEY,
            value=str(max(int(update["update_id"]) for update in updates) + 1),
            updated_at_utc=updated_at_utc,
        )
        return messages, next_cursor

    async def _get_updates(
        self, offset: str | None, limit: int
    ) -> list[dict[str, Any]]:
        params: dict[str, int] = {"limit": limit, "timeout": 0}
        if offset is not None:
            params["offset"] = int(offset)

        url = f"{self.base_url}/bot{self.bot_token}/getUpdates"
        for attempt in range(1, MAX_REQUEST_ATTEMPTS + 1):
            try:
                response = await self._request_updates(url=url, params=params)
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                LOGGER.warning(
                    "telegram_request_retry attempt=%s max_attempts=%s "
                    "error_type=%s error=%s",
                    attempt,
                    MAX_REQUEST_ATTEMPTS,
                    exc.__class__.__name__,
                    exc,
                )
                if attempt == MAX_REQUEST_ATTEMPTS:
                    raise CollectorError(
                        "Bot API getUpdates request failed after "
                        f"{MAX_REQUEST_ATTEMPTS} attempts"
                    ) from exc
                continue

            if response.status_code >= 500:
                LOGGER.warning(
                    "telegram_request_retry attempt=%s max_attempts=%s status=%s",
                    attempt,
                    MAX_REQUEST_ATTEMPTS,
                    response.status_code,
                )
                if attempt == MAX_REQUEST_ATTEMPTS:
                    raise CollectorError(
                        f"Bot API getUpdates failed with status {response.status_code}"
                    )
                continue

            if response.status_code >= 400:
                LOGGER.error(
                    "telegram_request_failed status=%s body=%s",
                    response.status_code,
                    response.text,
                )
                raise CollectorError(
                    f"Bot API getUpdates failed with status {response.status_code}"
                )

            try:
                payload = response.json()
            except JSONDecodeError as exc:
                LOGGER.exception("telegram_invalid_json")
                raise CollectorError(
                    "Bot API getUpdates returned invalid JSON"
                ) from exc

            if not payload.get("ok"):
                LOGGER.error("telegram_api_error payload=%s", payload)
                raise CollectorError(f"Bot API getUpdates failed: {payload}")

            result = payload.get("result", [])
            if not isinstance(result, list):
                LOGGER.error(
                    "telegram_invalid_result_type result_type=%s", type(result).__name__
                )
                raise CollectorError("Bot API getUpdates returned a non-list result")
            return result

        raise CollectorError("Bot API getUpdates failed unexpectedly")

    async def _request_updates(
        self, url: str, params: dict[str, int]
    ) -> httpx.Response:
        timeout = httpx.Timeout(REQUEST_TIMEOUT_SECONDS)
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.get(url, params=params)
