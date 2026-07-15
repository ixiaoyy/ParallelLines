from __future__ import annotations

from sqlalchemy import and_, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.core.permissions import is_admin
from app.models.forum import Board, BoardMember
from app.models.user import User

ADMIN_ONLY_BOARD_VISIBILITY = "admin"
ADMIN_ONLY_BOARD_SLUGS = frozenset({"private-space"})


def is_admin_only_board(board: Board) -> bool:
    """Return whether a board is reserved for global administrators.

    Key parameter `board` is the loaded forum board. Return value is true for
    the internal visibility marker or a protected slug. The protected slug is
    a defense-in-depth guard against accidental visibility edits; no side
    effects are performed.
    """

    return (
        board.visibility == ADMIN_ONLY_BOARD_VISIBILITY
        or board.slug in ADMIN_ONLY_BOARD_SLUGS
    )


def board_visible_condition(current_user: User | None) -> ColumnElement[bool]:
    """Build the SQL predicate for boards visible to the current requester.

    Key parameter `current_user` is the optional authenticated user. Return
    value is a SQLAlchemy expression that exposes protected boards only to
    global admins while preserving member access for ordinary private boards.
    The function has no side effects.
    """

    admin_only = or_(
        Board.visibility == ADMIN_ONLY_BOARD_VISIBILITY,
        Board.slug.in_(ADMIN_ONLY_BOARD_SLUGS),
    )
    if current_user is None:
        return and_(not_(admin_only), Board.visibility == "public")

    member_exists = (
        select(BoardMember.id)
        .where(
            BoardMember.board_id == Board.id,
            BoardMember.user_id == current_user.id,
        )
        .exists()
    )
    public_or_member = or_(Board.visibility == "public", member_exists)
    if is_admin(current_user):
        return or_(admin_only, public_or_member)
    return and_(not_(admin_only), public_or_member)


async def can_access_board(
    session: AsyncSession,
    board: Board,
    current_user: User | None,
) -> bool:
    """Check direct access to a loaded board without leaking protected boards.

    Key parameters are the active async `session`, loaded `board`, and optional
    `current_user`. Return value grants protected boards only to global admins,
    public boards to everyone, and ordinary private boards to owners/members.
    Side effect: may perform one membership lookup for a private board.
    """

    if is_admin_only_board(board):
        return current_user is not None and is_admin(current_user)
    if board.visibility == "public":
        return True
    if current_user is None:
        return False
    if board.owner_id == current_user.id:
        return True
    member = await session.scalar(
        select(BoardMember.id).where(
            BoardMember.board_id == board.id,
            BoardMember.user_id == current_user.id,
        )
    )
    return member is not None
