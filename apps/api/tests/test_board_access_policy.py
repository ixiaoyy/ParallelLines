from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.forum import Board
from app.models.user import User
from app.services.board_access import board_visible_condition, can_access_board


def user(*, user_id: str, role: str) -> User:
    """Build a minimal role-bearing user for policy tests.

    Key parameters identify the user and role. Return value is a typed test
    double; side effect is none.
    """

    return cast(User, SimpleNamespace(id=user_id, role=role))


def board(*, slug: str, visibility: str, owner_id: str | None = None) -> Board:
    """Build a minimal board object for direct-access policy tests.

    Key parameters provide slug, visibility, and optional owner ID. Return
    value is a typed test double; side effect is none.
    """

    return cast(
        Board,
        SimpleNamespace(id="board-1", slug=slug, visibility=visibility, owner_id=owner_id),
    )


@pytest.mark.asyncio
async def test_admin_only_board_rejects_anonymous_regular_and_owner_users() -> None:
    """Verify protected boards ignore ordinary private-board ownership rules."""

    session_scalar = AsyncMock()
    session = cast(AsyncSession, SimpleNamespace(scalar=session_scalar))
    regular = user(user_id="1", role="user")
    protected = board(slug="private-space", visibility="public", owner_id=regular.id)

    assert await can_access_board(session, protected, None) is False
    assert await can_access_board(session, protected, regular) is False
    assert await can_access_board(session, protected, user(user_id="2", role="admin")) is True
    session_scalar.assert_not_awaited()


@pytest.mark.asyncio
async def test_internal_admin_visibility_is_not_granted_to_regular_members() -> None:
    """Verify the internal visibility marker cannot be bypassed by membership."""

    session_scalar = AsyncMock(return_value="membership-1")
    session = cast(AsyncSession, SimpleNamespace(scalar=session_scalar))
    protected = board(slug="renamed-private-space", visibility="admin")

    assert await can_access_board(session, protected, user(user_id="1", role="user")) is False
    assert await can_access_board(session, protected, user(user_id="2", role="admin")) is True
    session_scalar.assert_not_awaited()


@pytest.mark.asyncio
async def test_ordinary_private_board_keeps_owner_and_member_access() -> None:
    """Verify the shared policy preserves existing private-board semantics."""

    session_scalar = AsyncMock(return_value="membership-1")
    session = cast(AsyncSession, SimpleNamespace(scalar=session_scalar))
    private_board = board(slug="team-room", visibility="private", owner_id="1")

    assert (
        await can_access_board(session, private_board, user(user_id="1", role="user"))
        is True
    )
    assert (
        await can_access_board(session, private_board, user(user_id="2", role="user"))
        is True
    )
    assert await can_access_board(session, private_board, None) is False
    session_scalar.assert_awaited_once()


def test_query_visibility_condition_contains_admin_and_slug_guards() -> None:
    """Verify list/feed predicates carry the same admin-only protections."""

    anonymous_sql = str(
        select(Board.id)
        .where(board_visible_condition(None))
        .compile(compile_kwargs={"literal_binds": True})
    )
    regular_sql = str(
        select(Board.id)
        .where(board_visible_condition(user(user_id="1", role="user")))
        .compile(compile_kwargs={"literal_binds": True})
    )
    admin_sql = str(
        select(Board.id)
        .where(board_visible_condition(user(user_id="2", role="admin")))
        .compile(compile_kwargs={"literal_binds": True})
    )

    assert "private-space" in anonymous_sql and "public" in anonymous_sql
    assert "private-space" in regular_sql and "admin" in regular_sql
    assert "private-space" in admin_sql and "admin" in admin_sql
