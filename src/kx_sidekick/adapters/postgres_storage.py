from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, TypeVar

import psycopg
from psycopg import errors as psycopg_errors
from psycopg.types.json import Jsonb

from kx_sidekick.config import DatabaseConfig
from kx_sidekick.errors import DatabaseError
from kx_sidekick.models import FetchCursor, MediaDownloadRecord, MessageRecord

LOGGER = logging.getLogger(__name__)
MAX_DB_RECONNECT_ATTEMPTS = 3
T = TypeVar("T")


class PostgresStorage:
    def __init__(self, config: DatabaseConfig) -> None:
        self.config = config
        self._connection: psycopg.Connection[Any] | None = None

    def ensure_connected(self) -> None:
        if self._connection is not None and not self._connection.closed:
            return
        self._connection = self._connect()

    def close(self) -> None:
        self._reset_connection()

    def save_messages(self, messages: list[MessageRecord]) -> int:
        if not messages:
            return 0

        def operation(connection: psycopg.Connection[Any]) -> int:
            inserted = 0
            with connection.cursor() as cursor:
                for message in messages:
                    cursor.execute(
                        """
                        INSERT INTO kx_telegram_messages (
                            external_id,
                            source,
                            chat_id,
                            chat_type,
                            chat_title,
                            chat_username,
                            message_id,
                            posted_at_utc,
                            edited_at_utc,
                            text,
                            raw_text,
                            author_id,
                            author_name,
                            media_kind,
                            media,
                            link,
                            fingerprint,
                            raw_summary
                        )
                        VALUES (
                            %(external_id)s,
                            %(source)s,
                            %(chat_id)s,
                            %(chat_type)s,
                            %(chat_title)s,
                            %(chat_username)s,
                            %(message_id)s,
                            %(posted_at_utc)s,
                            %(edited_at_utc)s,
                            %(text)s,
                            %(raw_text)s,
                            %(author_id)s,
                            %(author_name)s,
                            %(media_kind)s,
                            %(media)s,
                            %(link)s,
                            %(fingerprint)s,
                            %(raw_summary)s
                        )
                        ON CONFLICT (external_id) DO NOTHING
                        RETURNING 1
                        """,
                        {
                            "external_id": message.external_id,
                            "source": message.source,
                            "chat_id": message.chat.chat_id,
                            "chat_type": message.chat.chat_type,
                            "chat_title": message.chat.chat_title,
                            "chat_username": message.chat.chat_username,
                            "message_id": message.message_id,
                            "posted_at_utc": message.posted_at_utc,
                            "edited_at_utc": message.edited_at_utc,
                            "text": message.text,
                            "raw_text": message.raw_text,
                            "author_id": message.author.author_id,
                            "author_name": message.author.author_name,
                            "media_kind": message.media_kind,
                            "media": Jsonb(message.media) if message.media else None,
                            "link": message.link,
                            "fingerprint": message.fingerprint,
                            "raw_summary": Jsonb(message.raw_summary),
                        },
                    )
                    inserted += 1 if cursor.fetchone() is not None else 0
            return inserted

        return self._run_with_retry("save_messages", operation)

    def load_cursor(self, key: str) -> FetchCursor | None:
        def operation(connection: psycopg.Connection[Any]) -> FetchCursor | None:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT cursor_value, updated_at_utc
                    FROM kx_telegram_cursors
                    WHERE cursor_key = %s
                    """,
                    (key,),
                )
                row = cursor.fetchone()
            if row is None:
                return None
            value, updated_at_utc = row
            return FetchCursor(key=key, value=str(value), updated_at_utc=updated_at_utc)

        return self._run_with_retry("load_cursor", operation)

    def save_cursor(self, cursor: FetchCursor) -> None:
        def operation(connection: psycopg.Connection[Any]) -> None:
            with connection.cursor() as db_cursor:
                db_cursor.execute(
                    """
                    INSERT INTO kx_telegram_cursors (
                        cursor_key,
                        cursor_value,
                        updated_at_utc
                    )
                    VALUES (%s, %s, %s)
                    ON CONFLICT (cursor_key) DO UPDATE
                    SET cursor_value = EXCLUDED.cursor_value,
                        updated_at_utc = EXCLUDED.updated_at_utc
                    """,
                    (cursor.key, cursor.value, cursor.updated_at_utc),
                )

        self._run_with_retry("save_cursor", operation)

    def list_media_messages_after_id(
        self,
        after_id: int,
        kinds: tuple[str, ...],
        limit: int,
    ) -> list[MediaDownloadRecord]:
        def operation(connection: psycopg.Connection[Any]) -> list[MediaDownloadRecord]:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, posted_at_utc, media_kind, media
                    FROM kx_telegram_messages
                    WHERE id > %(after_id)s
                      AND media_kind = ANY(%(kinds)s)
                      AND media IS NOT NULL
                    ORDER BY id ASC
                    LIMIT %(limit)s
                    """,
                    {
                        "after_id": after_id,
                        "kinds": list(kinds),
                        "limit": limit,
                    },
                )
                rows = cursor.fetchall()

            records: list[MediaDownloadRecord] = []
            for row in rows:
                message_id, posted_at_utc, media_kind, media = row
                if not isinstance(message_id, int):
                    raise DatabaseError("Media query returned a non-integer id")
                if not isinstance(media_kind, str):
                    raise DatabaseError("Media query returned a non-string media_kind")
                if not isinstance(media, dict):
                    raise DatabaseError(
                        "Media query returned a non-object media payload"
                    )
                records.append(
                    MediaDownloadRecord(
                        id=message_id,
                        posted_at_utc=posted_at_utc,
                        media_kind=media_kind,
                        media=media,
                    )
                )
            return records

        return self._run_with_retry("list_media_messages_after_id", operation)

    def delete_messages_older_than(self, days: int) -> int:
        def operation(connection: psycopg.Connection[Any]) -> int:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM kx_telegram_messages
                    WHERE posted_at_utc < NOW() - (%s * INTERVAL '1 day')
                    RETURNING 1
                    """,
                    (days,),
                )
                rows = cursor.fetchall()
            return len(rows)

        return self._run_with_retry("delete_messages_older_than", operation)

    def _connect(self) -> psycopg.Connection[Any]:
        try:
            connection = psycopg.connect(
                host=self.config.host,
                port=self.config.port,
                dbname=self.config.name,
                user=self.config.user,
                password=self.config.password,
                sslmode=self.config.sslmode,
                connect_timeout=self.config.connect_timeout_seconds,
                options=f"-c statement_timeout={self.config.statement_timeout_ms}",
                autocommit=True,
            )
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return connection
        except psycopg.Error as exc:
            LOGGER.exception(
                "database_connect_failed host=%s port=%s db=%s error_type=%s error=%s",
                self.config.host,
                self.config.port,
                self.config.name,
                exc.__class__.__name__,
                exc,
            )
            raise DatabaseError("Failed to connect to PostgreSQL") from exc

    def _reset_connection(self) -> None:
        if self._connection is not None and not self._connection.closed:
            self._connection.close()
        self._connection = None

    def _run_with_retry(
        self,
        action_name: str,
        operation: Callable[[psycopg.Connection[Any]], T],
    ) -> T:
        for attempt in range(1, MAX_DB_RECONNECT_ATTEMPTS + 1):
            try:
                self.ensure_connected()
            except DatabaseError as exc:
                LOGGER.warning(
                    "database_reconnect_retry action=%s attempt=%s max_attempts=%s "
                    "error=%s",
                    action_name,
                    attempt,
                    MAX_DB_RECONNECT_ATTEMPTS,
                    exc,
                )
                self._reset_connection()
                if attempt == MAX_DB_RECONNECT_ATTEMPTS:
                    raise
                continue
            assert self._connection is not None
            try:
                return operation(self._connection)
            except self._recoverable_errors() as exc:
                LOGGER.warning(
                    "database_reconnect_retry action=%s attempt=%s max_attempts=%s "
                    "error_type=%s error=%s",
                    action_name,
                    attempt,
                    MAX_DB_RECONNECT_ATTEMPTS,
                    exc.__class__.__name__,
                    exc,
                )
                self._reset_connection()
                if attempt == MAX_DB_RECONNECT_ATTEMPTS:
                    LOGGER.exception(
                        "database_reconnect_exhausted action=%s error_type=%s error=%s",
                        action_name,
                        exc.__class__.__name__,
                        exc,
                    )
                    raise DatabaseError(
                        "Database operation failed after "
                        f"{MAX_DB_RECONNECT_ATTEMPTS} attempts"
                    ) from exc
            except psycopg.Error as exc:
                LOGGER.exception(
                    "database_operation_failed action=%s error_type=%s error=%s",
                    action_name,
                    exc.__class__.__name__,
                    exc,
                )
                raise DatabaseError(
                    f"Database operation failed: {action_name}"
                ) from exc

        raise DatabaseError(f"Database operation failed unexpectedly: {action_name}")

    @staticmethod
    def _recoverable_errors() -> tuple[type[BaseException], ...]:
        return (
            psycopg.OperationalError,
            psycopg.InterfaceError,
            psycopg_errors.QueryCanceled,
        )
