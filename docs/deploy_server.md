# Server Deployment

This document describes a production-style deployment for `karing_sidekick_tg` on a Linux server using `uv` and `supervisorctl`.

## Target Path

- Repository path: `/opt/KaringX/karing_sidekick`
- Supervisor program name: `kx_sidekick`

## Prerequisites

- Python 3.12+
- `uv` installed and available in `PATH`
- `supervisor` and `supervisorctl`
- PostgreSQL reachable from the server

Check the main tools:

```bash
python3 --version
uv --version
supervisord --version
supervisorctl version
```

## Prepare the Project

```bash
mkdir -p /opt/KaringX
cd /opt/KaringX
git clone <your-repo-url> karing_sidekick
cd /opt/KaringX/karing_sidekick

mkdir -p logs state
uv venv
uv sync --extra dev
cp .env.example .env
```

Edit `.env` and fill in the real Telegram and PostgreSQL values. If you want
the worker to send a Telegram alert before exiting on failure, also set
`KX_SIDEKICK_ERROR_CHAT_ID` to the target group or chat ID.

## Initialize PostgreSQL

Run the schema in `docs/table.sql` against the target database:

```bash
psql \
  -h "$KX_SIDEKICK_DB_HOST" \
  -p "$KX_SIDEKICK_DB_PORT" \
  -U "$KX_SIDEKICK_DB_USER" \
  -d "$KX_SIDEKICK_DB_NAME" \
  -f docs/table.sql
```

If you do not want to export shell variables first, replace them with explicit values.

## Verify the Worker Manually

Run one ingestion cycle before enabling supervisor:

```bash
cd /opt/KaringX/karing_sidekick
uv run python -m kx_sidekick
```

If configuration, Telegram access, and PostgreSQL connectivity are correct, the command should print a small JSON summary.

## Install Supervisor Config

Copy the provided config:

```bash
sudo cp deploy/supervisor/kx_sidekick.conf /etc/supervisor/conf.d/kx_sidekick.conf
```

Then reload supervisor:

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl status kx_sidekick
```

Start or restart the worker:

```bash
sudo supervisorctl start kx_sidekick
sudo supervisorctl restart kx_sidekick
```

## Logs and Runtime Files

- stdout log: `/opt/KaringX/karing_sidekick/logs/kx_sidekick.stdout.log`
- stderr log: `/opt/KaringX/karing_sidekick/logs/kx_sidekick.stderr.log`
- local dedupe state: `/opt/KaringX/karing_sidekick/state/dedupe_cache.json`

Quick checks:

```bash
sudo supervisorctl status kx_sidekick
tail -f /opt/KaringX/karing_sidekick/logs/kx_sidekick.stdout.log
tail -f /opt/KaringX/karing_sidekick/logs/kx_sidekick.stderr.log
```

## Upgrade Steps

```bash
cd /opt/KaringX/karing_sidekick
git pull
uv sync --extra dev
sudo supervisorctl restart kx_sidekick
```

If the database schema changes, run `docs/table.sql` again before restarting.

## Failure Model

- Telegram API timeout: `30s`
- Telegram request attempts: `3`
- PostgreSQL connect timeout: `60s`
- PostgreSQL statement timeout: `60000 ms` by default
- PostgreSQL reconnect attempts during runtime: `3`

When retries are exhausted, the application logs the failure and exits. `supervisor` is responsible for bringing the process back up.
