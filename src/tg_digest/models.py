from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@dataclass(frozen=True)
class ChatRef:
    source: str
    chat_id: str
    chat_type: str
    chat_title: str | None = None
    chat_username: str | None = None


@dataclass(frozen=True)
class MessageStats:
    views: int | None = None
    forwards: int | None = None
    replies: int | None = None


@dataclass(frozen=True)
class AuthorRef:
    author_id: str | None = None
    author_name: str | None = None


@dataclass(frozen=True)
class MessageRecord:
    source: str
    chat: ChatRef
    message_id: str
    posted_at_utc: datetime
    text: str
    raw_text: str
    author: AuthorRef = field(default_factory=AuthorRef)
    edited_at_utc: datetime | None = None
    media_kind: str | None = None
    stats: MessageStats = field(default_factory=MessageStats)
    link: str | None = None
    fingerprint: str | None = None
    raw_summary: dict[str, str | int | None] = field(default_factory=dict)

    @property
    def external_id(self) -> str:
        return f"{self.source}:{self.chat.chat_id}:{self.message_id}"

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["external_id"] = self.external_id
        data["posted_at_utc"] = ensure_utc(self.posted_at_utc).isoformat()
        if self.edited_at_utc is not None:
            data["edited_at_utc"] = ensure_utc(self.edited_at_utc).isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> MessageRecord:
        chat_data = data["chat"]
        author_data = data.get("author", {})
        stats_data = data.get("stats", {})
        raw_summary = data.get("raw_summary", {})
        assert isinstance(chat_data, dict)
        assert isinstance(author_data, dict)
        assert isinstance(stats_data, dict)
        assert isinstance(raw_summary, dict)
        edited_at_raw = data.get("edited_at_utc")
        return cls(
            source=str(data["source"]),
            chat=ChatRef(
                source=str(chat_data["source"]),
                chat_id=str(chat_data["chat_id"]),
                chat_type=str(chat_data["chat_type"]),
                chat_title=_optional_str(chat_data.get("chat_title")),
                chat_username=_optional_str(chat_data.get("chat_username")),
            ),
            message_id=str(data["message_id"]),
            posted_at_utc=datetime.fromisoformat(str(data["posted_at_utc"])),
            text=str(data["text"]),
            raw_text=str(data["raw_text"]),
            author=AuthorRef(
                author_id=_optional_str(author_data.get("author_id")),
                author_name=_optional_str(author_data.get("author_name")),
            ),
            edited_at_utc=(
                datetime.fromisoformat(str(edited_at_raw))
                if edited_at_raw is not None
                else None
            ),
            media_kind=_optional_str(data.get("media_kind")),
            stats=MessageStats(
                views=_optional_int(stats_data.get("views")),
                forwards=_optional_int(stats_data.get("forwards")),
                replies=_optional_int(stats_data.get("replies")),
            ),
            link=_optional_str(data.get("link")),
            fingerprint=_optional_str(data.get("fingerprint")),
            raw_summary={
                str(key): _json_scalar(value) for key, value in raw_summary.items()
            },
        )


@dataclass(frozen=True)
class ArticleCandidate:
    rank: int
    message: MessageRecord
    title_hint: str
    reasons: tuple[str, ...]
    score_total: float
    score_breakdown: dict[str, float]

    def to_dict(self) -> dict[str, object]:
        return {
            "rank": self.rank,
            "external_id": self.message.external_id,
            "title_hint": self.title_hint,
            "reasons": list(self.reasons),
            "score_total": self.score_total,
            "score_breakdown": self.score_breakdown,
            "message": self.message.to_dict(),
        }


@dataclass(frozen=True)
class FetchCursor:
    key: str
    value: str
    updated_at_utc: datetime


@dataclass(frozen=True)
class SelectionScore:
    message: MessageRecord
    total: float
    breakdown: dict[str, float]
    reasons: tuple[str, ...]


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None else None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"Unsupported integer value: {value!r}")


def _json_scalar(value: object) -> str | int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    return str(value)
