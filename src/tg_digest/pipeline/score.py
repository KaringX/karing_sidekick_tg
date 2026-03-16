from __future__ import annotations

from tg_digest.config import AppConfig
from tg_digest.models import MessageRecord, SelectionScore

STEP_MARKERS = ("1.", "2.", "步骤", "step", "首先", "然后")
PROBLEM_MARKERS = ("fix", "解决", "报错", "失败", "无法", "timeout", "crash")


def score_message(message: MessageRecord, config: AppConfig) -> SelectionScore:
    text = message.text.casefold()
    topic_fit = _count_keyword_hits(
        text, (*config.tutorial_keywords, *config.troubleshoot_keywords), 35.0
    )
    actionability = 25.0 if any(marker in text for marker in STEP_MARKERS) else 8.0
    problem_strength = (
        20.0 if any(marker in text for marker in PROBLEM_MARKERS) else 6.0
    )
    clarity = min(10.0, max(4.0, len(message.text) / 40.0))
    engagement = 0.0
    if message.stats.replies:
        engagement += min(6.0, float(message.stats.replies))
    if message.stats.views:
        engagement += min(4.0, float(message.stats.views) / 500.0)

    total = round(
        topic_fit + actionability + problem_strength + clarity + engagement, 2
    )
    reasons: list[str] = []
    if topic_fit >= 20:
        reasons.append("主题贴合教程或排障")
    if actionability >= 20:
        reasons.append("包含明确步骤")
    if problem_strength >= 15:
        reasons.append("包含问题与修复线索")
    breakdown = {
        "topic_fit": round(topic_fit, 2),
        "actionability": round(actionability, 2),
        "problem_strength": round(problem_strength, 2),
        "clarity": round(clarity, 2),
        "engagement": round(engagement, 2),
    }
    return SelectionScore(
        message=message,
        total=total,
        breakdown=breakdown,
        reasons=tuple(reasons),
    )


def _count_keyword_hits(
    text: str, keywords: tuple[str, ...], max_score: float
) -> float:
    hits = sum(1 for keyword in keywords if keyword.casefold() in text)
    if hits <= 0:
        return 0.0
    return min(max_score, 10.0 + (hits * 6.0))
