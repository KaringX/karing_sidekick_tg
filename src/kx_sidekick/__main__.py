from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
from typing import Final

from kx_sidekick.adapters.postgres_storage import PostgresStorage
from kx_sidekick.adapters.telegram_bot_api import BotApiCollector
from kx_sidekick.config import AppConfig, load_config
from kx_sidekick.errors import KxSidekickError, UnsupportedModeError
from kx_sidekick.ingest.local_dedupe import LocalDedupeStore
from kx_sidekick.services.telegram_ingestion import TelegramIngestionService

LOGGER: Final = logging.getLogger("kx_sidekick")


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _build_service(config: AppConfig) -> TelegramIngestionService:
    if config.telegram_mode not in {"bot_api", "hybrid"}:
        raise UnsupportedModeError("Only bot_api polling is wired in the current phase")

    collector = BotApiCollector(
        bot_token=config.bot_token or "",
        allowed_chat_ids=config.allowed_chat_ids,
    )
    storage = PostgresStorage(config.database)
    storage.ensure_connected()
    dedupe_store = LocalDedupeStore(config.dedupe)
    return TelegramIngestionService(
        collector=collector,
        storage=storage,
        dedupe_store=dedupe_store,
        polling_batch_size=config.polling_batch_size,
    )


async def _run_once(service: TelegramIngestionService) -> int:
    summary = await service.run_once()
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


async def _run_worker(service: TelegramIngestionService, interval_seconds: int) -> int:
    LOGGER.info(
        "worker_started polling_interval_seconds=%s polling_batch_size=%s",
        interval_seconds,
        service.polling_batch_size,
    )
    while True:
        summary = await service.run_once()
        LOGGER.info(
            "worker_iteration_completed stats=%s", json.dumps(summary, sort_keys=True)
        )
        await asyncio.sleep(interval_seconds)


async def _main(mode: str) -> int:
    config = load_config()
    service = _build_service(config)
    if mode == "worker":
        return await _run_worker(service, config.polling_interval_seconds)
    return await _run_once(service)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Telegram ingestion worker")
    parser.add_argument(
        "mode",
        nargs="?",
        default="run-once",
        choices=("run-once", "worker"),
        help="run once or stay in long-running polling mode",
    )
    return parser.parse_args()


def main() -> int:
    _configure_logging()
    args = _parse_args()
    with contextlib.suppress(KeyboardInterrupt):
        try:
            return asyncio.run(_main(args.mode))
        except KxSidekickError as exc:
            LOGGER.exception("application_failed error=%s", exc)
            return 1
        except Exception:
            LOGGER.exception("unhandled_exception")
            return 1
    LOGGER.info("worker_stopped reason=keyboard_interrupt")
    return 130


if __name__ == "__main__":
    raise SystemExit(main())
