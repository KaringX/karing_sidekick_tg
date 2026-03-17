from __future__ import annotations

import argparse
import asyncio
import configparser
import contextlib
import json
import logging
import os
import socket
import tempfile
import traceback
from datetime import datetime
from pathlib import Path
from typing import Final

from kx_sidekick.adapters.postgres_storage import PostgresStorage
from kx_sidekick.adapters.telegram_bot_api import BotApiCollector, BotApiNotifier
from kx_sidekick.config import (
    AppConfig,
    ErrorNotificationConfig,
    load_config,
    load_error_notification_config,
)
from kx_sidekick.errors import ConfigError, KxSidekickError, UnsupportedModeError
from kx_sidekick.ingest.local_dedupe import LocalDedupeStore
from kx_sidekick.services.cleanup import CleanupService
from kx_sidekick.services.media_download import (
    DEFAULT_MEDIA_KIND,
    MediaDownloadCursorStore,
    MediaDownloadService,
)
from kx_sidekick.services.telegram_ingestion import TelegramIngestionService

LOGGER: Final = logging.getLogger("kx_sidekick")
TRACEBACK_SUMMARY_LINES: Final = 3
PASS_EMOJI: Final = "✅"
FAIL_EMOJI: Final = "❌"
WARN_EMOJI: Final = "⚠️"
SUPERVISOR_CONFIG_PATH: Final = Path("deploy/supervisor/kx_sidekick.conf")
SUPERVISOR_SECTION: Final = "program:kx_sidekick"
MEDIA_DOWN_IDLE_SECONDS: Final = 600


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _build_service(
    config: AppConfig,
    storage: PostgresStorage | None = None,
) -> TelegramIngestionService:
    if config.telegram_mode not in {"bot_api", "hybrid"}:
        raise UnsupportedModeError("Only bot_api polling is wired in the current phase")

    collector = BotApiCollector(
        bot_token=config.bot_token or "",
        allowed_chat_ids=config.allowed_chat_ids,
    )
    if storage is None:
        storage = _build_storage(config)
    dedupe_store = LocalDedupeStore(config.dedupe)
    return TelegramIngestionService(
        collector=collector,
        storage=storage,
        dedupe_store=dedupe_store,
        polling_batch_size=config.polling_batch_size,
    )


def _build_storage(config: AppConfig) -> PostgresStorage:
    storage = PostgresStorage(config.database)
    storage.ensure_connected()
    return storage


def _build_cleanup_service(
    config: AppConfig, storage: PostgresStorage
) -> CleanupService:
    return CleanupService(storage=storage, state_dir=config.dedupe.state_dir)


def _build_media_download_service(
    config: AppConfig, storage: PostgresStorage
) -> MediaDownloadService:
    return MediaDownloadService(
        storage=storage,
        telegram=BotApiNotifier(bot_token=config.bot_token or ""),
        cursor_store=MediaDownloadCursorStore(config.dedupe.state_dir),
        batch_size=config.polling_batch_size,
    )


def _print_check_result(status: str, label: str, detail: str) -> None:
    print(f"{status} {label}: {detail}")


def _require_positive_cli_int(value: int | None, name: str) -> int | None:
    if value is not None and value <= 0:
        raise ConfigError(f"{name} must be greater than 0")
    return value


def _check_directory_writable(path: Path, label: str) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path, prefix=".check-", delete=True):
            pass
    except OSError as exc:
        try:
            path.chmod(0o777)
            with tempfile.NamedTemporaryFile(dir=path, prefix=".check-", delete=True):
                pass
        except OSError as chmod_exc:
            _print_check_result(
                FAIL_EMOJI,
                label,
                f"not writable; chmod 777 failed ({chmod_exc})",
            )
            return False

        _print_check_result(
            WARN_EMOJI,
            label,
            f"permission repaired to 777 at {path} after error ({exc})",
        )
        return True

    _print_check_result(PASS_EMOJI, label, f"writable at {path}")
    return True


def _parse_supervisor_config(config_path: Path) -> configparser.ConfigParser | None:
    if not config_path.exists():
        _print_check_result(FAIL_EMOJI, "supervisor config", f"missing {config_path}")
        return None

    parser = configparser.ConfigParser()
    try:
        parser.read(config_path, encoding="utf-8")
    except configparser.Error as exc:
        _print_check_result(
            FAIL_EMOJI,
            "supervisor config",
            f"invalid format in {config_path} ({exc})",
        )
        return None

    if not parser.has_section(SUPERVISOR_SECTION):
        _print_check_result(
            FAIL_EMOJI,
            "supervisor config",
            f"missing section [{SUPERVISOR_SECTION}]",
        )
        return None

    _print_check_result(PASS_EMOJI, "supervisor config", f"found {config_path}")
    return parser


def _check_supervisor_rotation(config_path: Path) -> bool:
    parser = _parse_supervisor_config(config_path)
    if parser is None:
        return False

    maxbytes_keys = ("stdout_logfile_maxbytes", "stderr_logfile_maxbytes")
    backup_keys = ("stdout_logfile_backups", "stderr_logfile_backups")
    all_ok = True

    for key in maxbytes_keys:
        value = parser.get(SUPERVISOR_SECTION, key, fallback="").strip()
        if not value:
            _print_check_result(FAIL_EMOJI, f"supervisor {key}", "missing")
            all_ok = False
            continue
        _print_check_result(PASS_EMOJI, f"supervisor {key}", value)

    for key in backup_keys:
        value = parser.get(SUPERVISOR_SECTION, key, fallback="").strip()
        try:
            parsed_value = int(value)
        except ValueError:
            _print_check_result(
                FAIL_EMOJI,
                f"supervisor {key}",
                f"invalid integer ({value or 'missing'})",
            )
            all_ok = False
            continue

        if parsed_value <= 0:
            _print_check_result(
                FAIL_EMOJI,
                f"supervisor {key}",
                f"must be > 0 (got {parsed_value})",
            )
            all_ok = False
            continue

        _print_check_result(PASS_EMOJI, f"supervisor {key}", str(parsed_value))

    return all_ok


async def _check_telegram(config: AppConfig) -> bool:
    notifier = BotApiNotifier(bot_token=config.bot_token or "")

    try:
        bot = await notifier.get_me()
    except Exception as exc:
        _print_check_result(FAIL_EMOJI, "telegram", str(exc))
        return False

    username = bot.get("username", "unknown") if isinstance(bot, dict) else "unknown"
    _print_check_result(PASS_EMOJI, "telegram", f"bot reachable @{username}")

    configured_chat_ids = list(config.allowed_chat_ids)
    if config.error_chat_id is not None:
        configured_chat_ids.append(config.error_chat_id)
    chat_ids = list(dict.fromkeys(configured_chat_ids))
    all_ok = True
    for chat_id in chat_ids:
        try:
            chat = await notifier.get_chat(chat_id)
        except Exception as exc:
            _print_check_result(FAIL_EMOJI, f"telegram chat {chat_id}", str(exc))
            all_ok = False
            continue

        title = chat.get("title") or chat.get("username") or chat.get("type", "unknown")
        _print_check_result(
            PASS_EMOJI,
            f"telegram chat {chat_id}",
            f"reachable ({title})",
        )

    if config.error_chat_id is None:
        _print_check_result(
            WARN_EMOJI,
            "error alert chat",
            "KX_SIDEKICK_ERROR_CHAT_ID not set",
        )

    return all_ok


def _check_database(config: AppConfig) -> bool:
    storage = PostgresStorage(config.database)
    try:
        storage.ensure_connected()
    except Exception as exc:
        _print_check_result(FAIL_EMOJI, "database", str(exc))
        return False
    finally:
        storage.close()

    _print_check_result(
        PASS_EMOJI,
        "database",
        (
            "connected to "
            f"{config.database.host}:{config.database.port}/{config.database.name}"
        ),
    )
    return True


async def _run_check() -> int:
    try:
        config = load_config()
    except KxSidekickError as exc:
        _print_check_result(FAIL_EMOJI, "config", str(exc))
        return 1

    _print_check_result(PASS_EMOJI, "config", "loaded .env and required settings")

    checks = [
        _check_directory_writable(config.dedupe.state_dir, "cache dir"),
        _check_directory_writable(Path("logs"), "log dir"),
        _check_supervisor_rotation(SUPERVISOR_CONFIG_PATH),
        _check_database(config),
        await _check_telegram(config),
    ]
    failed = sum(1 for result in checks if not result)
    if failed:
        _print_check_result(FAIL_EMOJI, "summary", f"{failed} check(s) failed")
        return 1

    _print_check_result(PASS_EMOJI, "summary", "all checks passed")
    return 0


def _build_traceback_excerpt(exc: BaseException) -> str:
    traceback_summary = "".join(
        traceback.format_exception(type(exc), exc, exc.__traceback__)
    )
    traceback_lines = traceback_summary.strip().splitlines()
    return "\n".join(traceback_lines[-TRACEBACK_SUMMARY_LINES:])


def _local_timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _runtime_context(mode: str) -> tuple[str, str, str, str]:
    return (
        os.getenv("SUPERVISOR_PROCESS_NAME", "kx_sidekick"),
        socket.gethostname(),
        _local_timestamp(),
        mode,
    )


def _format_telegram_error_notification(exc: BaseException, mode: str) -> str:
    supervisor_program, hostname, timestamp_local, runtime_mode = _runtime_context(mode)
    exception_summary = "".join(traceback.format_exception_only(type(exc), exc)).strip()
    traceback_excerpt = _build_traceback_excerpt(exc)
    return "\n".join(
        [
            "🚨 [kx_sidekick] exit alert",
            f"prog={supervisor_program} mode={runtime_mode}",
            f"host={hostname}",
            f"time={timestamp_local}",
            f"err={exception_summary}",
            "tb:",
            traceback_excerpt,
        ]
    )


def _build_error_state_payload(exc: BaseException, mode: str) -> dict[str, str]:
    supervisor_program, hostname, timestamp_local, runtime_mode = _runtime_context(mode)
    exception_summary = "".join(traceback.format_exception_only(type(exc), exc)).strip()
    return {
        "program": supervisor_program,
        "host": hostname,
        "time": timestamp_local,
        "mode": runtime_mode,
        "error": exception_summary,
    }


def _write_pending_error_state(
    notification_config: ErrorNotificationConfig, exc: BaseException, mode: str
) -> None:
    notification_config.state_dir.mkdir(parents=True, exist_ok=True)
    notification_config.state_file.write_text(
        json.dumps(_build_error_state_payload(exc, mode), sort_keys=True),
        encoding="utf-8",
    )


def _read_pending_error_state(state_file: Path) -> dict[str, str] | None:
    if not state_file.exists():
        return None

    try:
        payload = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        LOGGER.exception("error_notification_state_read_failed path=%s", state_file)
        return None

    if not isinstance(payload, dict):
        return None
    if not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in payload.items()
    ):
        return None
    return payload


def _format_telegram_recovery_notification(
    pending_error: dict[str, str], mode: str
) -> str:
    supervisor_program, hostname, timestamp_local, runtime_mode = _runtime_context(mode)
    previous_error = pending_error.get("error", "unknown")
    previous_time = pending_error.get("time", "unknown")
    previous_mode = pending_error.get("mode", "unknown")
    return "\n".join(
        [
            "✅ [kx_sidekick] recovered",
            f"prog={supervisor_program} mode={runtime_mode}",
            f"host={hostname}",
            f"time={timestamp_local}",
            f"prev_mode={previous_mode}",
            f"prev_time={previous_time}",
            f"prev_err={previous_error}",
        ]
    )


async def _send_error_notification(exc: BaseException, mode: str) -> None:
    notification_config = load_error_notification_config()
    if notification_config is None:
        LOGGER.info("error_notification_skipped reason=missing_config")
        return

    notifier = BotApiNotifier(bot_token=notification_config.bot_token)
    message = _format_telegram_error_notification(exc, mode)
    await notifier.send_message(notification_config.chat_id, message)
    LOGGER.info(
        "error_notification_sent chat_id=%s mode=%s",
        notification_config.chat_id,
        mode,
    )


async def _send_recovery_notification(mode: str) -> None:
    notification_config = load_error_notification_config()
    if notification_config is None:
        return

    pending_error = _read_pending_error_state(notification_config.state_file)
    if pending_error is None:
        return

    notifier = BotApiNotifier(bot_token=notification_config.bot_token)
    message = _format_telegram_recovery_notification(pending_error, mode)
    await notifier.send_message(notification_config.chat_id, message)
    notification_config.state_file.unlink(missing_ok=True)
    LOGGER.info(
        "recovery_notification_sent chat_id=%s mode=%s",
        notification_config.chat_id,
        mode,
    )


def _notify_exit_error(exc: BaseException, mode: str) -> None:
    notification_config = load_error_notification_config()
    if notification_config is not None:
        try:
            _write_pending_error_state(notification_config, exc, mode)
        except OSError:
            LOGGER.exception("error_notification_state_write_failed")

    try:
        asyncio.run(_send_error_notification(exc, mode))
    except Exception:
        LOGGER.exception("error_notification_failed")


async def _notify_recovery(mode: str) -> None:
    try:
        await _send_recovery_notification(mode)
    except Exception:
        LOGGER.exception("recovery_notification_failed")


async def _run_once(service: TelegramIngestionService) -> int:
    summary = await service.run_once()
    await _notify_recovery("run-once")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


async def _run_media_down(args: argparse.Namespace) -> int:
    start_id = _require_positive_cli_int(args.start_id, "--start-id")
    config = load_config()
    storage = _build_storage(config)
    try:
        service = _build_media_download_service(config, storage)
        next_start_id = start_id
        while True:
            summary = await service.run(
                kind=args.kind,
                start_id=next_start_id,
            )
            await _notify_recovery("media-down")
            print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
            next_start_id = None

            processed = summary.get("processed")
            if processed != 0:
                continue

            LOGGER.info(
                "media_down_idle_wait kind=%s wait_seconds=%s",
                args.kind,
                MEDIA_DOWN_IDLE_SECONDS,
            )
            await asyncio.sleep(MEDIA_DOWN_IDLE_SECONDS)
    finally:
        storage.close()
    return 0


async def _run_clear(args: argparse.Namespace) -> int:
    config = load_config()
    messages_days = (
        _require_positive_cli_int(args.messages_days, "--messages-days")
        or config.clear_messages_days
    )
    media_days = (
        _require_positive_cli_int(args.media_days, "--media-days")
        or config.clear_media_days
    )
    storage = _build_storage(config)
    try:
        service = _build_cleanup_service(config, storage)
        summary = service.run(
            messages_days=messages_days,
            media_days=media_days,
        )
    finally:
        storage.close()
    await _notify_recovery("clear")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


async def _run_worker(
    service: TelegramIngestionService,
    cleanup_service: CleanupService,
    clear_messages_days: int | None,
    clear_media_days: int | None,
    interval_seconds: int,
) -> int:
    LOGGER.info(
        "worker_started polling_interval_seconds=%s polling_batch_size=%s",
        interval_seconds,
        service.polling_batch_size,
    )
    while True:
        cleanup_summary = cleanup_service.run_daily_if_due(
            messages_days=clear_messages_days,
            media_days=clear_media_days,
        )
        if cleanup_summary is not None:
            LOGGER.info(
                "worker_cleanup_completed stats=%s",
                json.dumps(cleanup_summary, sort_keys=True),
            )
        summary = await service.run_once()
        await _notify_recovery("worker")
        LOGGER.info(
            "worker_iteration_completed stats=%s", json.dumps(summary, sort_keys=True)
        )
        await asyncio.sleep(interval_seconds)


async def _main(args: argparse.Namespace) -> int:
    if args.mode == "check":
        return await _run_check()
    if args.mode == "media-down":
        return await _run_media_down(args)
    if args.mode == "clear":
        return await _run_clear(args)

    config = load_config()
    storage = _build_storage(config)
    service = _build_service(config, storage=storage)
    if args.mode == "worker":
        return await _run_worker(
            service,
            _build_cleanup_service(config, storage),
            config.clear_messages_days,
            config.clear_media_days,
            config.polling_interval_seconds,
        )
    return await _run_once(service)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Telegram ingestion worker")
    parser.add_argument(
        "mode",
        nargs="?",
        default="run-once",
        choices=("run-once", "worker", "check", "media-down", "clear"),
        help="run once, stay in polling mode, or validate runtime dependencies",
    )
    parser.add_argument(
        "--start-id",
        type=int,
        default=None,
        help="start downloading media from this message id",
    )
    parser.add_argument(
        "--kind",
        choices=("photo", "all"),
        default=DEFAULT_MEDIA_KIND,
        help="limit media-down to one media kind or all supported kinds",
    )
    parser.add_argument(
        "--messages-days",
        type=int,
        default=None,
        help="delete database messages older than this many days during clear",
    )
    parser.add_argument(
        "--media-days",
        type=int,
        default=None,
        help="delete media directories older than this many days during clear",
    )
    return parser.parse_args()


def main() -> int:
    _configure_logging()
    args = _parse_args()
    with contextlib.suppress(KeyboardInterrupt):
        try:
            return asyncio.run(_main(args))
        except KxSidekickError as exc:
            LOGGER.exception("application_failed error=%s", exc)
            _notify_exit_error(exc, args.mode)
            return 1
        except Exception as exc:
            LOGGER.exception("unhandled_exception")
            _notify_exit_error(exc, args.mode)
            return 1
    LOGGER.info("worker_stopped reason=keyboard_interrupt")
    return 130


if __name__ == "__main__":
    raise SystemExit(main())
