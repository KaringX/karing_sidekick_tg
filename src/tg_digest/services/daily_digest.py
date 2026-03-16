from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from tg_digest.config import AppConfig
from tg_digest.ingest.dedupe import dedupe_messages
from tg_digest.models import ArticleCandidate, ChatRef, MessageRecord
from tg_digest.pipeline.filter import filter_candidate_messages
from tg_digest.pipeline.select import select_candidates
from tg_digest.ports.storage import DailyStorage
from tg_digest.ports.telegram import TelegramCollector


@dataclass
class DailyDigestService:
    collector: TelegramCollector
    storage: DailyStorage
    config: AppConfig

    async def run_for_day(self, day: date) -> dict[str, object]:
        start_utc = datetime.combine(day, time.min, tzinfo=UTC)
        end_utc = start_utc + timedelta(days=1)
        messages: list[MessageRecord] = []

        for chat_id in self.config.allowed_chat_ids:
            chat = ChatRef(
                source=self.config.telegram_mode, chat_id=chat_id, chat_type="group"
            )
            cursor = self.storage.load_cursor(f"bot_api:{chat_id}")
            fetched, next_cursor = await self.collector.fetch_messages(
                chat=chat,
                start_utc=start_utc,
                end_utc=end_utc,
                cursor=cursor,
                limit=self.config.polling_batch_size,
            )
            messages.extend(fetched)
            if next_cursor is not None:
                self.storage.save_cursor(next_cursor)

        stored_messages = self.storage.load_messages(day)
        deduped = dedupe_messages([*stored_messages, *messages])
        filtered = filter_candidate_messages(deduped, self.config)
        candidates = select_candidates(filtered, self.config)
        self.storage.save_messages(day, deduped)
        self.storage.save_candidates(day, candidates)
        summary = _build_summary(messages, deduped, filtered, candidates)
        self.storage.save_summary(day, summary)
        return summary


def _build_summary(
    fetched: list[MessageRecord],
    deduped: list[MessageRecord],
    filtered: list[MessageRecord],
    candidates: list[ArticleCandidate],
) -> dict[str, object]:
    return {
        "stats": {
            "fetched": len(fetched),
            "deduped": len(deduped),
            "filtered_in": len(filtered),
            "selected": len(candidates),
        },
        "run_status": "ok",
    }
