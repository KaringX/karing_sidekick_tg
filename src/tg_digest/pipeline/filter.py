from __future__ import annotations

from tg_digest.config import AppConfig
from tg_digest.models import MessageRecord

QUESTION_HINTS = (
    "怎么",
    "如何",
    "吗",
    "why",
    "what",
    "how",
    "can i",
    "有没有",
    "求助",
    "请问",
)

ANSWER_HINTS = (
    "可以这样",
    "解决方法",
    "步骤如下",
    "you can",
    "try this",
    "workaround",
    "fix",
    "先",
    "然后",
)


def filter_candidate_messages(
    messages: list[MessageRecord], config: AppConfig
) -> list[MessageRecord]:
    selected: list[MessageRecord] = []
    keywords = tuple(
        word.casefold()
        for word in (*config.tutorial_keywords, *config.troubleshoot_keywords)
    )
    noise_keywords = tuple(word.casefold() for word in config.noise_keywords)
    for message in messages:
        text = message.text.casefold()
        if len(message.text) < config.min_text_length:
            continue
        if any(noise in text for noise in noise_keywords):
            continue
        if text.startswith("http"):
            continue
        if _looks_like_support_dialogue(text):
            selected.append(message)
            continue
        if any(keyword.casefold() in text for keyword in keywords):
            selected.append(message)
    return selected


def _looks_like_support_dialogue(text: str) -> bool:
    has_question = any(marker in text for marker in QUESTION_HINTS)
    has_answer = any(marker in text for marker in ANSWER_HINTS)
    return has_question and has_answer
