from __future__ import annotations

from kx_sidekick.models import MessageRecord


def dedupe_messages(messages: list[MessageRecord]) -> list[MessageRecord]:
    by_external_id: dict[str, MessageRecord] = {}
    for message in messages:
        existing = by_external_id.get(message.external_id)
        if existing is None or _is_better(message, existing):
            by_external_id[message.external_id] = message

    by_fingerprint: dict[str, MessageRecord] = {}
    for message in by_external_id.values():
        if message.fingerprint is None:
            by_fingerprint[message.external_id] = message
            continue

        existing = by_fingerprint.get(message.fingerprint)
        if existing is None or _is_better(message, existing):
            by_fingerprint[message.fingerprint] = message

    return sorted(by_fingerprint.values(), key=lambda item: item.posted_at_utc)


def _is_better(candidate: MessageRecord, current: MessageRecord) -> bool:
    return len(candidate.text) > len(current.text)
