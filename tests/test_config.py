from __future__ import annotations

from pathlib import Path

import pytest

from tg_digest.config import load_config


def test_load_config_reads_values_from_dotenv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "\n".join(
            [
                "TG_DIGEST_TELEGRAM_MODE=bot_api",
                "TG_DIGEST_BOT_TOKEN=test-token",
                "TG_DIGEST_BOT_ALLOWED_CHAT_IDS=-1001,-1002",
                "TG_DIGEST_DATA_DIR=data-local",
                "TG_DIGEST_POLLING_BATCH_SIZE=55",
                "TG_DIGEST_POLLING_INTERVAL_SECONDS=9",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TG_DIGEST_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TG_DIGEST_BOT_ALLOWED_CHAT_IDS", raising=False)
    monkeypatch.delenv("TG_DIGEST_DATA_DIR", raising=False)
    monkeypatch.delenv("TG_DIGEST_POLLING_BATCH_SIZE", raising=False)
    monkeypatch.delenv("TG_DIGEST_POLLING_INTERVAL_SECONDS", raising=False)

    config = load_config()

    assert config.bot_token == "test-token"
    assert config.allowed_chat_ids == ("-1001", "-1002")
    assert config.data_dir == Path("data-local")
    assert config.polling_batch_size == 55
    assert config.polling_interval_seconds == 9
