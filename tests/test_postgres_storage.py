from __future__ import annotations

from types import MethodType
from typing import Any, cast

import pytest

from kx_sidekick.adapters.postgres_storage import PostgresStorage
from kx_sidekick.config import DatabaseConfig


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
