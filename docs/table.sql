BEGIN;

CREATE TABLE IF NOT EXISTS kx_telegram_messages (
    id BIGSERIAL PRIMARY KEY,
    external_id TEXT NOT NULL,
    source TEXT NOT NULL,
    chat_id TEXT NOT NULL,
    chat_type TEXT NOT NULL,
    chat_title TEXT,
    chat_username TEXT,
    message_id TEXT NOT NULL,
    posted_at_utc TIMESTAMPTZ NOT NULL,
    edited_at_utc TIMESTAMPTZ,
    text TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    author_id TEXT,
    author_name TEXT,
    media_kind TEXT,
    media JSONB,
    link TEXT,
    fingerprint TEXT,
    raw_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    ingested_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT kx_telegram_messages_external_id_key UNIQUE (external_id)
);

CREATE INDEX IF NOT EXISTS kx_telegram_messages_chat_posted_idx
    ON kx_telegram_messages (chat_id, posted_at_utc DESC);

CREATE INDEX IF NOT EXISTS kx_telegram_messages_posted_at_idx
    ON kx_telegram_messages (posted_at_utc DESC);

CREATE INDEX IF NOT EXISTS kx_telegram_messages_fingerprint_idx
    ON kx_telegram_messages (fingerprint);

CREATE INDEX IF NOT EXISTS kx_telegram_messages_chat_message_idx
    ON kx_telegram_messages (chat_id, message_id);

CREATE INDEX IF NOT EXISTS kx_telegram_messages_ingested_at_idx
    ON kx_telegram_messages (ingested_at_utc DESC);

CREATE TABLE IF NOT EXISTS kx_telegram_cursors (
    cursor_key TEXT PRIMARY KEY,
    cursor_value TEXT NOT NULL,
    updated_at_utc TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS kx_telegram_cursors_updated_at_idx
    ON kx_telegram_cursors (updated_at_utc DESC);

COMMENT ON TABLE kx_telegram_messages IS 'Normalized Telegram messages collected by the kx_sidekick worker.';
COMMENT ON COLUMN kx_telegram_messages.id IS 'Internal database primary key.';
COMMENT ON COLUMN kx_telegram_messages.external_id IS 'Idempotency key built as source:chat_id:message_id.';
COMMENT ON COLUMN kx_telegram_messages.source IS 'Collector source label such as bot_api.';
COMMENT ON COLUMN kx_telegram_messages.chat_id IS 'Telegram chat identifier from message.chat.id.';
COMMENT ON COLUMN kx_telegram_messages.chat_type IS 'Telegram chat type from message.chat.type.';
COMMENT ON COLUMN kx_telegram_messages.chat_title IS 'Telegram chat title when available.';
COMMENT ON COLUMN kx_telegram_messages.chat_username IS 'Telegram public username used to build links when available.';
COMMENT ON COLUMN kx_telegram_messages.message_id IS 'Telegram message.message_id value.';
COMMENT ON COLUMN kx_telegram_messages.posted_at_utc IS 'Telegram message.date normalized to UTC.';
COMMENT ON COLUMN kx_telegram_messages.edited_at_utc IS 'Telegram message.edit_date normalized to UTC.';
COMMENT ON COLUMN kx_telegram_messages.text IS 'Normalized message text with condensed whitespace.';
COMMENT ON COLUMN kx_telegram_messages.raw_text IS 'Original Telegram text or caption before normalization.';
COMMENT ON COLUMN kx_telegram_messages.author_id IS 'Telegram sender identifier when available.';
COMMENT ON COLUMN kx_telegram_messages.author_name IS 'Sender display name derived from first_name, last_name, or username.';
COMMENT ON COLUMN kx_telegram_messages.media_kind IS 'Detected media kind such as photo, video, document, animation, or audio.';
COMMENT ON COLUMN kx_telegram_messages.media IS 'Telegram media metadata used for later file retrieval, including file_id and type-specific details.';
COMMENT ON COLUMN kx_telegram_messages.link IS 'Public t.me link built from chat username and message id when possible.';
COMMENT ON COLUMN kx_telegram_messages.fingerprint IS 'Hash of normalized long text used for lightweight duplicate detection.';
COMMENT ON COLUMN kx_telegram_messages.raw_summary IS 'Compact JSONB payload with selected raw Telegram metadata such as update_id.';
COMMENT ON COLUMN kx_telegram_messages.ingested_at_utc IS 'Database insertion time in UTC.';

COMMENT ON TABLE kx_telegram_cursors IS 'Incremental Telegram polling cursors.';
COMMENT ON COLUMN kx_telegram_cursors.cursor_key IS 'Cursor identifier such as bot_api:updates.';
COMMENT ON COLUMN kx_telegram_cursors.cursor_value IS 'Telegram offset value, usually update_id + 1.';
COMMENT ON COLUMN kx_telegram_cursors.updated_at_utc IS 'Last successful cursor update time in UTC.';

COMMIT;
