# karing_sidekick_tg

Follow the Telegram group to listen to the concerns of everyone.

`karing_sidekick_tg` is a Telegram ingestion worker focused on collecting real user feedback from selected groups or channels. It pulls messages through the Telegram Bot API, normalizes the content, applies lightweight deduplication, and stores the results in PostgreSQL.

## What it does

- Polls Telegram updates from allowed chats only
- Normalizes message text and preserves raw text
- Uses in-memory and local state-file deduplication before database writes
- Stores messages and polling cursors in PostgreSQL
- Runs under `supervisor` so the process can exit cleanly on repeated failures

## Runtime behavior

- Telegram request timeout: `30s`
- Telegram request retries: `3`
- PostgreSQL connect timeout: `60s`
- PostgreSQL statement timeout: default `60000 ms`
- PostgreSQL reconnect retries during runtime: `3`
- On repeated Telegram or PostgreSQL failures, the worker logs the full traceback locally, sends a compact Telegram exit alert, and exits; `supervisor` should restart it
- After the next successful cycle, the worker sends a one-time Telegram recovery alert

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
python -m kx_sidekick check
python -m kx_sidekick
```

## Run modes

- Run once: `python -m kx_sidekick`
- Long-running worker: `python -m kx_sidekick worker`
- Environment check: `python -m kx_sidekick check`

`check` validates config loading, Telegram bot/chat access, PostgreSQL connectivity,
cache and log directory writability, and Supervisor log rotation settings. If a
required runtime directory is not writable, the checker will try `chmod 777`
once and report that repair attempt in the output.

## Environment variables

The app loads `.env` from the repository root, then falls back to shell environment variables.

Telegram:

- `KX_SIDEKICK_TELEGRAM_MODE`: currently `bot_api`
- `KX_SIDEKICK_BOT_TOKEN`: Telegram bot token
- `KX_SIDEKICK_BOT_ALLOWED_CHAT_IDS`: comma-separated allowed chat IDs
- `KX_SIDEKICK_ERROR_CHAT_ID`: optional chat or group ID for exit-error alerts
- `KX_SIDEKICK_POLLING_BATCH_SIZE`: Bot API `getUpdates` batch size
- `KX_SIDEKICK_POLLING_INTERVAL_SECONDS`: delay between polling cycles

PostgreSQL:

- `KX_SIDEKICK_DB_HOST`: required
- `KX_SIDEKICK_DB_PORT`: default `5432`
- `KX_SIDEKICK_DB_NAME`: required
- `KX_SIDEKICK_DB_USER`: required
- `KX_SIDEKICK_DB_PASSWORD`: required
- `KX_SIDEKICK_DB_SSLMODE`: default `disable`
- `KX_SIDEKICK_DB_STATEMENT_TIMEOUT_MS`: default `60000`

Local dedupe state:

- `KX_SIDEKICK_STATE_DIR`: default `state`
- `KX_SIDEKICK_DEDUPE_TTL_SECONDS`: default `86400`
- `KX_SIDEKICK_DEDUPE_MAX_KEYS`: default `10000`

Never commit real credentials.

## PostgreSQL schema

- Table SQL: `docs/table.sql`
- Main tables:
  - `kx_telegram_messages`
  - `kx_telegram_cursors`

The message table stores both normalized `text` and original `raw_text`, plus lightweight Telegram metadata in `raw_summary`.

## Supervisor

Recommended deploy path:

- `/opt/KaringX/karing_sidekick`

Example supervisor config:

- `deploy/supervisor/kx_sidekick.conf`
- Server deployment guide: `docs/deploy_server.md`
- Concurrency notes: `docs/concurrency.md`

Reload steps after copying the config:

```bash
supervisorctl reread
supervisorctl update
supervisorctl restart kx_sidekick
```

## Project layout

```text
src/kx_sidekick/          application code
tests/                    automated tests
docs/table.sql            PostgreSQL schema
deploy/supervisor/        supervisor example config
state/                    local dedupe cache state
logs/                     supervisor-managed logs
```

## Theme

This project is intentionally narrow: follow the Telegram group to listen to the concerns of everyone, keep the raw discussion intact, and make sure useful feedback is stored reliably for later analysis.
