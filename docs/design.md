# Design Notes

- Normalize Telegram payloads before they reach service logic.
- Keep Bot API polling as the active integration path and reserve MTProto for a later phase.
- Use PostgreSQL as the primary system of record for messages and cursors.
- Use in-memory plus local state-file deduplication to reduce duplicate writes to a remote database.
- Exit cleanly after repeated Telegram or PostgreSQL failures so `supervisor` can restart the worker.
