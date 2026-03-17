from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from kx_sidekick.config import DedupeConfig
from kx_sidekick.models import MessageRecord

LOGGER = logging.getLogger(__name__)


@dataclass
class LocalDedupeStore:
    config: DedupeConfig
    external_ids: dict[str, float] = field(default_factory=dict)
    fingerprints: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._load()
        self._prune()

    def is_duplicate(self, message: MessageRecord) -> bool:
        self._prune()
        if message.external_id in self.external_ids:
            return True
        return (
            message.fingerprint is not None and message.fingerprint in self.fingerprints
        )

    def remember(self, messages: list[MessageRecord]) -> None:
        seen_at = datetime.now(UTC).timestamp()
        for message in messages:
            self.external_ids[message.external_id] = seen_at
            if message.fingerprint is not None:
                self.fingerprints[message.fingerprint] = seen_at
        self._prune()
        self.flush()

    def flush(self) -> None:
        payload = {
            "updated_at": datetime.now(UTC).isoformat(),
            "external_ids": self.external_ids,
            "fingerprints": self.fingerprints,
        }
        try:
            self.config.state_dir.mkdir(parents=True, exist_ok=True)
            self.config.state_file.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except OSError as exc:
            LOGGER.warning(
                "dedupe_state_flush_failed error_type=%s error=%s",
                exc.__class__.__name__,
                exc,
            )

    def _load(self) -> None:
        path = self.config.state_file
        if not path.exists():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            LOGGER.warning(
                "dedupe_state_load_failed error_type=%s error=%s",
                exc.__class__.__name__,
                exc,
            )
            return

        external_ids = payload.get("external_ids", {})
        fingerprints = payload.get("fingerprints", {})
        if isinstance(external_ids, dict):
            self.external_ids = {
                str(key): float(value)
                for key, value in external_ids.items()
                if isinstance(value, int | float)
            }
        if isinstance(fingerprints, dict):
            self.fingerprints = {
                str(key): float(value)
                for key, value in fingerprints.items()
                if isinstance(value, int | float)
            }

    def _prune(self) -> None:
        cutoff = datetime.now(UTC).timestamp() - self.config.ttl_seconds
        self.external_ids = self._prune_bucket(self.external_ids, cutoff)
        self.fingerprints = self._prune_bucket(self.fingerprints, cutoff)

    def _prune_bucket(
        self, bucket: dict[str, float], cutoff: float
    ) -> dict[str, float]:
        filtered = {
            key: seen_at for key, seen_at in bucket.items() if seen_at >= cutoff
        }
        if len(filtered) <= self.config.max_keys:
            return filtered
        ordered = sorted(filtered.items(), key=lambda item: item[1], reverse=True)
        return dict(ordered[: self.config.max_keys])
