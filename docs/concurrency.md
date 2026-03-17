# Concurrency Notes

`kx_sidekick` is designed to run as a single active worker for one shared Telegram polling stream and one shared cursor namespace.

## Recommended Mode

- Run exactly one `kx_sidekick` worker per Telegram bot token and cursor set.
- Let `supervisor` keep that one worker alive.

## Why Single Worker Is Recommended

- Telegram Bot API polling uses a shared offset stream.
- The app stores a single logical cursor key, `bot_api:updates`.
- The local dedupe cache is process-local plus one local state file.
- Multiple workers against the same bot token can race on offset updates and duplicate intake windows.

## Current Runtime Concurrency Model

- One long-running event loop
- One polling cycle at a time
- One PostgreSQL connection object in the storage layer
- No internal parallel fan-out for chat ingestion

This keeps behavior deterministic and easier to recover after network or database errors.

## If You Start Multiple Workers Anyway

Possible side effects:

- duplicated Telegram fetch windows
- cursor overwrite races
- reduced effectiveness of local dedupe memory
- extra PostgreSQL write pressure
- harder debugging during incident recovery

The database unique constraint on `kx_telegram_messages.external_id` still protects final storage integrity, but it will not prevent unnecessary duplicate work.

## Safe Scale-Out Direction

If you need higher throughput later, do not simply start more identical workers. Instead, change the design first, for example:

- shard by bot token
- shard by explicitly separated chat groups
- use different cursor namespaces per shard
- move dedupe memory to a shared external store
- make supervisor manage multiple named shard programs

Until that refactor exists, keep deployment at one worker instance.
