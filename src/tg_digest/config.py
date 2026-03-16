from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from tg_digest.errors import ConfigError


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


@dataclass(frozen=True)
class AppConfig:
    telegram_mode: str
    bot_token: str | None
    allowed_chat_ids: tuple[str, ...]
    data_dir: Path
    timezone: str
    max_candidates: int
    min_text_length: int
    polling_batch_size: int
    polling_interval_seconds: int
    tutorial_keywords: tuple[str, ...]
    troubleshoot_keywords: tuple[str, ...]
    noise_keywords: tuple[str, ...]


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


def load_config() -> AppConfig:
    _load_dotenv(Path(".env"))

    telegram_mode = os.getenv("TG_DIGEST_TELEGRAM_MODE", "bot_api")
    if telegram_mode not in {"bot_api", "mtproto", "hybrid"}:
        raise ConfigError(f"Unsupported telegram mode: {telegram_mode}")

    bot_token = os.getenv("TG_DIGEST_BOT_TOKEN")
    if telegram_mode in {"bot_api", "hybrid"} and not bot_token:
        raise ConfigError("TG_DIGEST_BOT_TOKEN is required for bot_api or hybrid mode")

    allowed_chat_ids = _split_csv(os.getenv("TG_DIGEST_BOT_ALLOWED_CHAT_IDS", ""))
    if telegram_mode in {"bot_api", "hybrid"} and not allowed_chat_ids:
        raise ConfigError(
            "TG_DIGEST_BOT_ALLOWED_CHAT_IDS is required for bot_api or hybrid mode"
        )

    return AppConfig(
        telegram_mode=telegram_mode,
        bot_token=bot_token,
        allowed_chat_ids=allowed_chat_ids,
        data_dir=Path(os.getenv("TG_DIGEST_DATA_DIR", "data")),
        timezone=os.getenv("TG_DIGEST_TIMEZONE", "UTC"),
        max_candidates=int(os.getenv("TG_DIGEST_MAX_CANDIDATES", "3")),
        min_text_length=int(os.getenv("TG_DIGEST_MIN_TEXT_LENGTH", "40")),
        polling_batch_size=int(os.getenv("TG_DIGEST_POLLING_BATCH_SIZE", "100")),
        polling_interval_seconds=int(
            os.getenv("TG_DIGEST_POLLING_INTERVAL_SECONDS", "30")
        ),
        tutorial_keywords=_split_csv(
            os.getenv(
                "TG_DIGEST_KEYWORDS_TUTORIAL",
                (
                    "how to,教程,使用方法,设置方法,步骤,指南,操作,演示,配置,教程向,"
                    "怎么用,如何使用,使用技巧,新手,入门,step by step"
                ),
            )
        ),
        troubleshoot_keywords=_split_csv(
            os.getenv(
                "TG_DIGEST_KEYWORDS_TROUBLESHOOT",
                (
                    "fix,解决,报错,无法,失败,crash,timeout,workaround,error,bug,"
                    "修复,排查,闪退,卡住,异常,重试,恢复,故障,login failed,"
                    "network error"
                ),
            )
        ),
        noise_keywords=_split_csv(
            os.getenv(
                "TG_DIGEST_KEYWORDS_NOISE",
                (
                    "招聘,抽奖,推广,广告,返现,代理,加群,互粉,闲聊,灌水,日常,"
                    "打卡,签到,红包,invite,join now,promo,giveaway,airdrop"
                ),
            )
        ),
    )
