from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
from datetime import UTC, datetime

from tg_digest.adapters.json_storage import JsonDailyStorage
from tg_digest.adapters.telegram_bot_api import BotApiCollector
from tg_digest.config import load_config
from tg_digest.errors import UnsupportedModeError
from tg_digest.services.daily_digest import DailyDigestService


def _build_service() -> DailyDigestService:
    config = load_config()
    if config.telegram_mode not in {"bot_api", "hybrid"}:
        raise UnsupportedModeError("Only bot_api polling is wired in the first phase")

    collector = BotApiCollector(
        bot_token=config.bot_token or "",
        allowed_chat_ids=config.allowed_chat_ids,
    )
    storage = JsonDailyStorage(config.data_dir)
    return DailyDigestService(collector=collector, storage=storage, config=config)


async def _run_once(service: DailyDigestService) -> int:
    target_day = datetime.now(UTC).date()
    summary = await service.run_for_day(target_day)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


async def _run_worker(service: DailyDigestService) -> int:
    print(
        json.dumps(
            {
                "status": "worker_started",
                "polling_interval_seconds": service.config.polling_interval_seconds,
                "allowed_chat_ids": service.config.allowed_chat_ids,
            },
            ensure_ascii=False,
        )
    )
    while True:
        target_day = datetime.now(UTC).date()
        summary = await service.run_for_day(target_day)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        await asyncio.sleep(service.config.polling_interval_seconds)


async def _main(mode: str) -> int:
    service = _build_service()
    if mode == "worker":
        return await _run_worker(service)
    return await _run_once(service)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Telegram digest worker")
    parser.add_argument(
        "mode",
        nargs="?",
        default="run-once",
        choices=("run-once", "worker"),
        help="run once or stay in long-running polling mode",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    with contextlib.suppress(KeyboardInterrupt):
        return asyncio.run(_main(args.mode))
    return 130


if __name__ == "__main__":
    raise SystemExit(main())
