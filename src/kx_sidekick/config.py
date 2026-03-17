from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from kx_sidekick.errors import ConfigError


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        cleaned_key = key.strip()
        cleaned_value = value.strip().strip('"').strip("'")
        if cleaned_key:
            os.environ.setdefault(cleaned_key, cleaned_value)


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ConfigError(f"{name} is required")
    return value


def _get_positive_int(name: str, default: str) -> int:
    raw_value = os.getenv(name, default)
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ConfigError(f"{name} must be greater than 0")
    return value


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    name: str
    user: str
    password: str
    sslmode: str
    connect_timeout_seconds: int
    statement_timeout_ms: int


@dataclass(frozen=True)
class DedupeConfig:
    state_dir: Path
    ttl_seconds: int
    max_keys: int

    @property
    def state_file(self) -> Path:
        return self.state_dir / "dedupe_cache.json"


@dataclass(frozen=True)
class AppConfig:
    telegram_mode: str
    bot_token: str | None
    allowed_chat_ids: tuple[str, ...]
    error_chat_id: str | None
    polling_batch_size: int
    polling_interval_seconds: int
    database: DatabaseConfig
    dedupe: DedupeConfig


@dataclass(frozen=True)
class ErrorNotificationConfig:
    bot_token: str
    chat_id: str
    state_dir: Path

    @property
    def state_file(self) -> Path:
        return self.state_dir / "error_notification_state.json"


def load_error_notification_config() -> ErrorNotificationConfig | None:
    _load_dotenv(Path(".env"))

    bot_token = os.getenv("KX_SIDEKICK_BOT_TOKEN")
    chat_id = os.getenv("KX_SIDEKICK_ERROR_CHAT_ID")
    if not bot_token or not chat_id:
        return None
    return ErrorNotificationConfig(
        bot_token=bot_token,
        chat_id=chat_id,
        state_dir=Path(os.getenv("KX_SIDEKICK_STATE_DIR", "state")),
    )


def load_config() -> AppConfig:
    _load_dotenv(Path(".env"))

    telegram_mode = os.getenv("KX_SIDEKICK_TELEGRAM_MODE", "bot_api")
    if telegram_mode not in {"bot_api", "mtproto", "hybrid"}:
        raise ConfigError(f"Unsupported telegram mode: {telegram_mode}")

    bot_token = os.getenv("KX_SIDEKICK_BOT_TOKEN")
    if telegram_mode in {"bot_api", "hybrid"} and not bot_token:
        raise ConfigError(
            "KX_SIDEKICK_BOT_TOKEN is required for bot_api or hybrid mode"
        )

    allowed_chat_ids = _split_csv(os.getenv("KX_SIDEKICK_BOT_ALLOWED_CHAT_IDS", ""))
    if telegram_mode in {"bot_api", "hybrid"} and not allowed_chat_ids:
        raise ConfigError(
            "KX_SIDEKICK_BOT_ALLOWED_CHAT_IDS is required for bot_api or hybrid mode"
        )

    database = DatabaseConfig(
        host=_get_required_env("KX_SIDEKICK_DB_HOST"),
        port=_get_positive_int("KX_SIDEKICK_DB_PORT", "5432"),
        name=_get_required_env("KX_SIDEKICK_DB_NAME"),
        user=_get_required_env("KX_SIDEKICK_DB_USER"),
        password=_get_required_env("KX_SIDEKICK_DB_PASSWORD"),
        sslmode=os.getenv("KX_SIDEKICK_DB_SSLMODE", "disable"),
        connect_timeout_seconds=60,
        statement_timeout_ms=_get_positive_int(
            "KX_SIDEKICK_DB_STATEMENT_TIMEOUT_MS", "60000"
        ),
    )
    dedupe = DedupeConfig(
        state_dir=Path(os.getenv("KX_SIDEKICK_STATE_DIR", "state")),
        ttl_seconds=_get_positive_int("KX_SIDEKICK_DEDUPE_TTL_SECONDS", "86400"),
        max_keys=_get_positive_int("KX_SIDEKICK_DEDUPE_MAX_KEYS", "10000"),
    )

    return AppConfig(
        telegram_mode=telegram_mode,
        bot_token=bot_token,
        allowed_chat_ids=allowed_chat_ids,
        error_chat_id=os.getenv("KX_SIDEKICK_ERROR_CHAT_ID"),
        polling_batch_size=_get_positive_int("KX_SIDEKICK_POLLING_BATCH_SIZE", "100"),
        polling_interval_seconds=_get_positive_int(
            "KX_SIDEKICK_POLLING_INTERVAL_SECONDS", "30"
        ),
        database=database,
        dedupe=dedupe,
    )
