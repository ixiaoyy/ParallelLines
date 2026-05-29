from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, or_
from sqlalchemy.sql import Select

from app.core.exceptions import ValidationError
from app.models.forum import Topic


@dataclass(frozen=True)
class TopicListCursor:
    last_posted_at: datetime
    topic_id: str | None = None


def encode_topic_cursor(topic: Topic) -> str:
    """Return an opaque cursor that stays stable when many topics share one second."""

    return f"{topic.last_posted_at.isoformat()}|{topic.id}"


def parse_topic_cursor(raw_cursor: str | datetime | None) -> TopicListCursor | None:
    if raw_cursor is None:
        return None
    if isinstance(raw_cursor, datetime):
        return TopicListCursor(last_posted_at=raw_cursor)

    value = raw_cursor.strip()
    if not value:
        return None

    timestamp_text, separator, topic_id = value.partition("|")
    try:
        timestamp = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError("invalid_cursor", "Pagination cursor is invalid") from exc

    return TopicListCursor(
        last_posted_at=timestamp,
        topic_id=topic_id if separator and topic_id else None,
    )


def apply_latest_topic_cursor(statement: Select, cursor: TopicListCursor | None) -> Select:
    if cursor is None:
        return statement
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
