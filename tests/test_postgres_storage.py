from __future__ import annotations

from datetime import UTC, datetime
from types import MethodType
from typing import Any, cast

import pytest
from psycopg.types.json import Jsonb

from kx_sidekick.adapters.postgres_storage import PostgresStorage
from kx_sidekick.config import DatabaseConfig
from kx_sidekick.models import ChatRef, MessageRecord


class RecoverableError(Exception):
    pass


class FakeConnection:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _config() -> DatabaseConfig:
    return DatabaseConfig(
        host="127.0.0.1",
        port=5432,
        name="sidekick",
        user="postgres",
        password="secret",
        sslmode="disable",
        connect_timeout_seconds=60,
        statement_timeout_ms=60000,
    )


def test_postgres_storage_retries_recoverable_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = PostgresStorage(_config())
    connections = [FakeConnection(), FakeConnection(), FakeConnection()]
    connect_calls: list[int] = []

    def fake_connect(self: PostgresStorage) -> FakeConnection:
        connect_calls.append(1)
        return connections[len(connect_calls) - 1]

    monkeypatch.setattr(storage, "_connect", MethodType(fake_connect, storage))
    monkeypatch.setattr(
        storage,
        "_recoverable_errors",
        staticmethod(lambda: (RecoverableError,)),
    )

    attempts = 0

    def operation(connection: FakeConnection) -> int:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RecoverableError(f"boom:{connection}")
        return 7

    assert storage._run_with_retry("save_messages", cast(Any, operation)) == 7
    assert len(connect_calls) == 3


def test_postgres_storage_save_messages_writes_media_jsonb() -> None:
    storage = PostgresStorage(_config())
    captured_params: list[dict[str, object]] = []

    class FakeCursor:
        def __enter__(self) -> FakeCursor:
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            del exc_type, exc, tb

        def execute(self, query: str, params: dict[str, object]) -> None:
            del query
            captured_params.append(params)

        def fetchone(self) -> tuple[int]:
            return (1,)

    class SaveConnection(FakeConnection):
        def cursor(self) -> FakeCursor:
            return FakeCursor()

    storage._connection = cast(Any, SaveConnection())

    message = MessageRecord(
        source="bot_api",
        chat=ChatRef(source="bot_api", chat_id="chat-1", chat_type="supergroup"),
        message_id="42",
        posted_at_utc=datetime(2026, 3, 17, tzinfo=UTC),
        text="video walkthrough",
        raw_text="video walkthrough",
        media_kind="video",
        media={
            "kind": "video",
            "telegram": {
                "file_id": "video-file",
                "file_unique_id": "video-uniq",
            },
        },
    )

    inserted = storage.save_messages([message])

    assert inserted == 1
    assert len(captured_params) == 1
    assert captured_params[0]["media_kind"] == "video"
    assert isinstance(captured_params[0]["media"], Jsonb)
    assert captured_params[0]["media"].obj == message.media
