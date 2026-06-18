from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interaction import Notification
from app.models.user import User
from app.services.interactions import InteractionService


def _public_board() -> SimpleNamespace:
    """Build a minimal public board object for notification access checks."""

    return SimpleNamespace(visibility="public", owner_id="owner")


def _topic(
    *,
    deleted_at: datetime | None = None,
    status: str = "open",
    visibility: str = "public",
) -> SimpleNamespace:
    """Build a minimal topic object with the fields used by stale-notification checks."""

    return SimpleNamespace(
        deleted_at=deleted_at,
        status=status,
        visibility=visibility,
        board=_public_board(),
    )


def _notification(
    *,
    kind: str = "board_new_topic",
    topic: SimpleNamespace | None,
    post: SimpleNamespace | None = None,
) -> Notification:
    """Build a minimal notification-like object and cast it to the ORM type for unit tests."""

    return cast(
        Notification,
        SimpleNamespace(
            type=kind,
            topic_id="topic-1" if topic is not None else None,
            topic=topic,
            post_id="post-1" if post is not None else None,
            post=post,
        ),
    )


@pytest.mark.asyncio
async def test_notification_target_cleanup_detects_deleted_and_hidden_content() -> None:
    """Stale detection removes notifications whose linked topic or post can no longer open."""

    service = InteractionService(cast(AsyncSession, object()))
    current_user = cast(User, SimpleNamespace(id="user-1"))
    live_topic = _topic()

    assert (
        await service._notification_target_is_stale(
            _notification(topic=_topic(deleted_at=datetime.now(UTC))),
            current_user,
        )
        is True
    )
    assert (
        await service._notification_target_is_stale(
            _notification(topic=_topic(status="hidden")),
            current_user,
        )
        is True
    )
    assert (
        await service._notification_target_is_stale(
            _notification(
                topic=live_topic,
                post=SimpleNamespace(deleted_at=datetime.now(UTC), topic=live_topic),
            ),
            current_user,
        )
        is True
    )

    assert (
        await service._notification_target_is_stale(_notification(topic=live_topic), current_user)
        is False
    )


@pytest.mark.asyncio
async def test_notification_target_cleanup_keeps_non_topic_notifications() -> None:
    """Notifications without a topic/post target, such as board invites, are not deleted."""

    service = InteractionService(cast(AsyncSession, object()))
    current_user = cast(User, SimpleNamespace(id="user-1"))
    board_invite = _notification(kind="board_invite", topic=None)
    moderation = _notification(kind="moderation", topic=_topic(deleted_at=datetime.now(UTC)))

    assert await service._notification_target_is_stale(board_invite, current_user) is False
    assert await service._notification_target_is_stale(moderation, current_user) is False

