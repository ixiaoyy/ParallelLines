from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, case, or_
from sqlalchemy.sql import Select

from app.core.exceptions import ValidationError
from app.models.forum import Topic


@dataclass(frozen=True)
class TopicListCursor:
    last_posted_at: datetime
    topic_id: str | None = None
    pinned: bool | None = None


def encode_topic_cursor(topic: Topic, *, include_pinned: bool = False) -> str:
    """Return an opaque cursor that stays stable when many topics share one second."""

    base_cursor = f"{topic.last_posted_at.isoformat()}|{topic.id}"
    if not include_pinned:
        return base_cursor
    pinned_rank = "1" if topic.pinned else "0"
    return f"{pinned_rank}|{base_cursor}"


def parse_topic_cursor(raw_cursor: str | datetime | None) -> TopicListCursor | None:
    if raw_cursor is None:
        return None
    if isinstance(raw_cursor, datetime):
        return TopicListCursor(last_posted_at=raw_cursor)

    value = raw_cursor.strip()
    if not value:
        return None

    pinned: bool | None = None
    parts = value.split("|", 2)
    if len(parts) == 3 and parts[0] in {"0", "1"}:
        pinned = parts[0] == "1"
        timestamp_text, separator, topic_id = parts[1], "|", parts[2]
    else:
        timestamp_text, separator, topic_id = value.partition("|")

    try:
        timestamp = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError("invalid_cursor", "Pagination cursor is invalid") from exc

    return TopicListCursor(
        last_posted_at=timestamp,
        topic_id=topic_id if separator and topic_id else None,
        pinned=pinned,
    )


def apply_latest_topic_cursor(
    statement: Select,
    cursor: TopicListCursor | None,
    *,
    include_pinned: bool = False,
) -> Select:
    """Apply the latest-feed cursor while matching the caller's ordering rules."""

    if cursor is None:
        return statement
    if include_pinned and cursor.pinned is not None:
        pinned_rank = case((Topic.pinned.is_(True), 1), else_=0)
        cursor_pinned_rank = 1 if cursor.pinned else 0
        if cursor.topic_id:
            return statement.where(
                or_(
                    pinned_rank < cursor_pinned_rank,
                    and_(
                        pinned_rank == cursor_pinned_rank,
                        Topic.last_posted_at < cursor.last_posted_at,
                    ),
                    and_(
                        pinned_rank == cursor_pinned_rank,
                        Topic.last_posted_at == cursor.last_posted_at,
                        Topic.id < cursor.topic_id,
                    ),
                )
            )
        return statement.where(
            or_(
                pinned_rank < cursor_pinned_rank,
                and_(
                    pinned_rank == cursor_pinned_rank,
                    Topic.last_posted_at < cursor.last_posted_at,
                ),
            )
        )
    if cursor.topic_id:
        return statement.where(
            or_(
                Topic.last_posted_at < cursor.last_posted_at,
                and_(
                    Topic.last_posted_at == cursor.last_posted_at,
                    Topic.id < cursor.topic_id,
                ),
            )
        )
    return statement.where(Topic.last_posted_at < cursor.last_posted_at)
