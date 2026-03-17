from __future__ import annotations

from pathlib import Path

import pytest

from kx_sidekick.config import load_config


def test_load_config_reads_values_and_defaults(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "\n".join(
            [
                "KX_SIDEKICK_TELEGRAM_MODE=bot_api",
                "KX_SIDEKICK_BOT_TOKEN=test-token",
                "KX_SIDEKICK_BOT_ALLOWED_CHAT_IDS=-1001,-1002",
                "KX_SIDEKICK_POLLING_BATCH_SIZE=55",
                "KX_SIDEKICK_POLLING_INTERVAL_SECONDS=9",
                "KX_SIDEKICK_DB_HOST=127.0.0.1",
                "KX_SIDEKICK_DB_NAME=sidekick",
                "KX_SIDEKICK_DB_USER=postgres",
                "KX_SIDEKICK_DB_PASSWORD=secret",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    for key in [
        "KX_SIDEKICK_BOT_TOKEN",
        "KX_SIDEKICK_BOT_ALLOWED_CHAT_IDS",
        "KX_SIDEKICK_POLLING_BATCH_SIZE",
        "KX_SIDEKICK_POLLING_INTERVAL_SECONDS",
        "KX_SIDEKICK_DB_HOST",
        "KX_SIDEKICK_DB_PORT",
        "KX_SIDEKICK_DB_NAME",
        "KX_SIDEKICK_DB_USER",
        "KX_SIDEKICK_DB_PASSWORD",
        "KX_SIDEKICK_DB_SSLMODE",
        "KX_SIDEKICK_DB_STATEMENT_TIMEOUT_MS",
        "KX_SIDEKICK_STATE_DIR",
        "KX_SIDEKICK_DEDUPE_TTL_SECONDS",
        "KX_SIDEKICK_DEDUPE_MAX_KEYS",
    ]:
        monkeypatch.delenv(key, raising=False)

    config = load_config()

    assert config.bot_token == "test-token"
    assert config.allowed_chat_ids == ("-1001", "-1002")
    assert config.polling_batch_size == 55
    assert config.polling_interval_seconds == 9
    assert config.database.port == 5432
    assert config.database.sslmode == "disable"
    assert config.database.statement_timeout_ms == 60000
    assert config.dedupe.state_file == Path("state") / "dedupe_cache.json"
