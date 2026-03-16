from __future__ import annotations

from tg_digest.config import AppConfig
from tg_digest.models import ArticleCandidate, MessageRecord
from tg_digest.pipeline.score import score_message


def select_candidates(
    messages: list[MessageRecord], config: AppConfig
) -> list[ArticleCandidate]:
    scored = sorted(
        (score_message(message, config) for message in messages),
        key=lambda item: item.total,
        reverse=True,
    )

    selected: list[ArticleCandidate] = []
    seen_chats: set[str] = set()
    for scored_message in scored:
        if scored_message.total < 55:
            continue
        if scored_message.message.chat.chat_id in seen_chats:
            continue
        rank = len(selected) + 1
        selected.append(
            ArticleCandidate(
                rank=rank,
                message=scored_message.message,
                title_hint=_build_title(scored_message.message.text),
                reasons=scored_message.reasons,
                score_total=scored_message.total,
                score_breakdown=scored_message.breakdown,
            )
        )
        seen_chats.add(scored_message.message.chat.chat_id)
        if len(selected) >= config.max_candidates:
            break

    if selected:
        return selected

    if not scored:
        return []

    fallback = scored[0]
    return [
        ArticleCandidate(
            rank=1,
            message=fallback.message,
            title_hint=_build_title(fallback.message.text),
            reasons=fallback.reasons or ("当天样本较少，保留最高分候选",),
            score_total=fallback.total,
            score_breakdown=fallback.breakdown,
        )
    ]


def _build_title(text: str) -> str:
    snippet = text.replace("\n", " ").strip()
    return snippet[:60] + ("..." if len(snippet) > 60 else "")
