from __future__ import annotations

import asyncio
import json
import socket
import tempfile
from argparse import Namespace
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pytest

import kx_sidekick.__main__ as main_module
from kx_sidekick.config import (
    AppConfig,
    DatabaseConfig,
    DedupeConfig,
    ErrorNotificationConfig,
)
from kx_sidekick.errors import ConfigError


def test_main_sends_error_notification_before_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    async def failing_main(mode: str) -> int:
        raise ConfigError(f"broken config for {mode}")

    def fake_notify_exit_error(exc: BaseException, mode: str) -> None:
        calls.append((type(exc).__name__, mode))

    monkeypatch.setattr(main_module, "_parse_args", lambda: Namespace(mode="worker"))
    monkeypatch.setattr(main_module, "_main", failing_main)
    monkeypatch.setattr(main_module, "_notify_exit_error", fake_notify_exit_error)

    exit_code = main_module.main()

    assert exit_code == 1
    assert calls == [("ConfigError", "worker")]


def test_format_telegram_error_notification_includes_runtime_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frozen_time = datetime.fromisoformat("2026-03-17T16:30:00+08:00")

    class FrozenDatetime:
        @staticmethod
        def now() -> datetime:
            return frozen_time

    monkeypatch.setattr(socket, "gethostname", lambda: "worker-01")
    monkeypatch.setattr(main_module, "datetime", FrozenDatetime)
    monkeypatch.setenv("SUPERVISOR_PROCESS_NAME", "kx-sidekick-worker")

    try:
        raise ConfigError("broken config")
    except ConfigError as exc:
        message = main_module._format_telegram_error_notification(exc, "worker")

    assert "🚨 [kx_sidekick] exit alert" in message
    assert "prog=kx-sidekick-worker mode=worker" in message
    assert "host=worker-01" in message
    assert "time=2026-03-17T16:30:00+08:00" in message
    assert "err=kx_sidekick.errors.ConfigError: broken config" in message
    assert "tb:" in message
    assert "test_format_telegram_error_notification_includes_runtime_context" in message


def test_build_traceback_excerpt_keeps_only_recent_lines() -> None:
    def level_one() -> None:
        level_two()

    def level_two() -> None:
        raise ConfigError("trim traceback")

    excerpt = ""
    try:
        level_one()
    except ConfigError as exc:
        excerpt = main_module._build_traceback_excerpt(exc)

    excerpt_lines = excerpt.splitlines()

    assert len(excerpt_lines) <= main_module.TRACEBACK_SUMMARY_LINES
    assert "trim traceback" in excerpt


def test_send_recovery_notification_uses_compact_message_and_clears_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sent_messages: list[tuple[str, str]] = []
    notification_config = ErrorNotificationConfig(
        bot_token="token",
        chat_id="-1009",
        state_dir=tmp_path,
    )
    notification_config.state_file.write_text(
        json.dumps(
            {
                "program": "kx-sidekick-worker",
                "host": "worker-01",
                "time": "2026-03-17T16:29:00+08:00",
                "mode": "worker",
                "error": "kx_sidekick.errors.ConfigError: broken config",
            }
        ),
        encoding="utf-8",
    )

    class FakeNotifier:
        def __init__(self, bot_token: str) -> None:
            assert bot_token == "token"

        async def send_message(self, chat_id: str, text: str) -> None:
            sent_messages.append((chat_id, text))

    monkeypatch.setattr(
        main_module, "load_error_notification_config", lambda: notification_config
    )
    monkeypatch.setattr(main_module, "BotApiNotifier", FakeNotifier)
    monkeypatch.setattr(socket, "gethostname", lambda: "worker-01")
    monkeypatch.setenv("SUPERVISOR_PROCESS_NAME", "kx-sidekick-worker")

    asyncio.run(main_module._send_recovery_notification("worker"))

    assert sent_messages
    assert sent_messages[0][0] == "-1009"
    assert "✅ [kx_sidekick] recovered" in sent_messages[0][1]
    assert (
        "prev_err=kx_sidekick.errors.ConfigError: broken config" in sent_messages[0][1]
    )
    assert not notification_config.state_file.exists()


def test_run_once_awaits_recovery_notification(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[str] = []

    class FakeService:
        async def run_once(self) -> dict[str, object]:
            return {"run_status": "ok", "stored": 1}

    async def fake_notify_recovery(mode: str) -> None:
        calls.append(mode)

    monkeypatch.setattr(main_module, "_notify_recovery", fake_notify_recovery)

    exit_code = asyncio.run(main_module._run_once(cast(Any, FakeService())))
    output = capsys.readouterr().out

    assert exit_code == 0
    assert calls == ["run-once"]
    assert '"stored": 1' in output


def test_run_check_reports_success_for_ready_dependencies(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = AppConfig(
        telegram_mode="bot_api",
        bot_token="token",
        allowed_chat_ids=("-1001",),
        error_chat_id="-1009",
        polling_batch_size=100,
        polling_interval_seconds=30,
        database=DatabaseConfig(
            host="127.0.0.1",
            port=5432,
            name="sidekick",
            user="postgres",
            password="secret",
            sslmode="disable",
            connect_timeout_seconds=60,
            statement_timeout_ms=60000,
        ),
        dedupe=DedupeConfig(
            state_dir=tmp_path / "state",
            ttl_seconds=86400,
            max_keys=10000,
        ),
    )

    class FakeNotifier:
        def __init__(self, bot_token: str) -> None:
            assert bot_token == "token"

        async def get_me(self) -> dict[str, object]:
            return {"username": "sidekick_bot"}

        async def get_chat(self, chat_id: str) -> dict[str, object]:
            return {"title": f"chat-{chat_id}"}

    class FakeStorage:
        def __init__(self, database_config: DatabaseConfig) -> None:
            assert database_config is config.database

        def ensure_connected(self) -> None:
            return None

        def close(self) -> None:
            return None

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main_module, "load_config", lambda: config)
    monkeypatch.setattr(main_module, "BotApiNotifier", FakeNotifier)
    monkeypatch.setattr(main_module, "PostgresStorage", FakeStorage)
    supervisor_config = tmp_path / "kx_sidekick.conf"
    supervisor_config.write_text(
        "\n".join(
            [
                "[program:kx_sidekick]",
                "stdout_logfile_maxbytes=20MB",
                "stdout_logfile_backups=5",
                "stderr_logfile_maxbytes=20MB",
                "stderr_logfile_backups=5",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(main_module, "SUPERVISOR_CONFIG_PATH", supervisor_config)

    exit_code = asyncio.run(main_module._run_check())
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "✅ config: loaded .env and required settings" in output
    assert "✅ cache dir:" in output
    assert "✅ log dir:" in output
    assert "✅ supervisor config:" in output
    assert "✅ supervisor stdout_logfile_maxbytes: 20MB" in output
    assert "✅ database:" in output
    assert "✅ telegram: bot reachable @sidekick_bot" in output
    assert "✅ telegram chat -1001:" in output
    assert "✅ telegram chat -1009:" in output
    assert "✅ summary: all checks passed" in output


def test_check_directory_writable_repairs_permissions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "state"
    target.mkdir()
    chmod_calls: list[int] = []
    original_named_temporary_file = tempfile.NamedTemporaryFile

    def fake_chmod(self: Path, mode: int) -> None:
        assert self == target
        chmod_calls.append(mode)

    def fake_named_temporary_file(*args: Any, **kwargs: Any) -> Any:
        if len(chmod_calls) == 0:
            raise PermissionError("denied")
        return original_named_temporary_file(*args, **kwargs)

    monkeypatch.setattr(Path, "chmod", fake_chmod)
    monkeypatch.setattr(tempfile, "NamedTemporaryFile", fake_named_temporary_file)

    result = main_module._check_directory_writable(target, "cache dir")
    output = capsys.readouterr().out

    assert result is True
    assert chmod_calls == [0o777]
    assert "⚠️ cache dir: permission repaired to 777" in output


def test_check_supervisor_rotation_reports_missing_file(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    result = main_module._check_supervisor_rotation(tmp_path / "missing.conf")
    output = capsys.readouterr().out

    assert result is False
    assert "❌ supervisor config: missing" in output
