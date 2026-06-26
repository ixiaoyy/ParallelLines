"""add sports board

Revision ID: 0059_add_sports_board
Revises: 0058_fix_frontier_script_publisher_email
Create Date: 2026-06-26
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0059_add_sports_board"
down_revision: str | None = "0058_fix_frontier_script_publisher_email"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BOARD_SLUG = "sports"
BOARD_NAME = "体坛快讯"
BOARD_DESCRIPTION = "聚合赛事新闻、球员动态、赛后热点与转会消息。"
BOARD_COLOR = "#16A34A"

boards = sa.table(
    "boards",
    sa.column("id", sa.BigInteger()),
    sa.column("slug", sa.String()),
    sa.column("name", sa.String()),
    sa.column("name_localizations", sa.JSON()),
    sa.column("description", sa.Text()),
    sa.column("color", sa.String()),
    sa.column("avatar_url", sa.String()),
    sa.column("owner_id", sa.BigInteger()),
    sa.column("parent_board_id", sa.BigInteger()),
    sa.column("visibility", sa.String()),
    sa.column("required_tags", sa.JSON()),
    sa.column("allowed_tags", sa.JSON()),
    sa.column("post_template", sa.Text()),
    sa.column("default_notification_level", sa.String()),
    sa.column("default_sort", sa.String()),
    sa.column("topic_count", sa.Integer()),
    sa.column("post_count", sa.Integer()),
    sa.column("follower_count", sa.Integer()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
board_members = sa.table(
    "board_members",
    sa.column("id", sa.BigInteger()),
    sa.column("board_id", sa.BigInteger()),
    sa.column("user_id", sa.BigInteger()),
    sa.column("role", sa.String()),
    sa.column("notification_level", sa.String()),
    sa.column("joined_at", sa.DateTime(timezone=True)),
)
users = sa.table(
    "users",
    sa.column("id", sa.BigInteger()),
    sa.column("username", sa.String()),
    sa.column("role", sa.String()),
    sa.column("status", sa.String()),
)


def upgrade() -> None:
    """Create or refresh the public sports board.

    Key parameters: none. Return value: none. Side effect: inserts or updates
    the `sports` board when the forum already has seeded/real boards.
    """

    bind = op.get_bind()
    if not table_exists(bind, "boards") or not table_exists(bind, "board_members"):
        return
    if bind.execute(sa.select(sa.func.count()).select_from(boards)).scalar_one() == 0:
        return

    author = select_migration_author(bind)
    board_id = ensure_board(bind, int(author["id"]) if author else None)
    if author is not None:
        ensure_board_owner_membership(bind, board_id, int(author["id"]))


def downgrade() -> None:
    """Keep sports board content in place on downgrade.

    Key parameters: none. Return value: none. Side effect: none, because
    deleting a public board could remove user-created topics.
    """

    return


def now() -> datetime:
    """Return the current UTC timestamp for inserted or updated rows.

    Key parameters: none. Return value: timezone-aware UTC datetime. Side
    effect: none.
    """

    return datetime.now(UTC)


def table_exists(bind: sa.Connection, table_name: str) -> bool:
    """Check whether a table exists before issuing data-migration statements.

    Key parameters: `bind` is the migration connection and `table_name` is the
    table to inspect. Return value: true when the table exists. Side effect:
    reads database metadata only.
    """

    return sa.inspect(bind).has_table(table_name)


def select_migration_author(bind: sa.Connection) -> dict[str, object] | None:
    """Select the preferred active user to own the seeded sports board.

    Key parameter: `bind` is the migration connection. Return value: a small
    user dictionary or None when no active user is available. Side effect:
    reads users only.
    """

    if not table_exists(bind, "users"):
        return None
    row = bind.execute(
        sa.select(users.c.id, users.c.username)
        .where(users.c.status == "active")
        .order_by(
            sa.case(
                (users.c.username == "多动脑子z", 0),
                (users.c.username == "大脚板", 1),
                (users.c.role == "admin", 2),
                (users.c.role == "moderator", 3),
                else_=4,
            ),
            users.c.id,
        )
        .limit(1)
    ).first()
    if row is None:
        return None
    return {"id": row.id, "username": row.username}


def ensure_board(bind: sa.Connection, owner_id: int | None) -> int:
    """Create or update the public sports board and return its database ID.

    Key parameters: `bind` is the migration connection; `owner_id` is optional
    and is used only when the board has no owner. Return value: board ID. Side
    effect: inserts or updates the `boards` row.
    """

    row = bind.execute(sa.select(boards).where(boards.c.slug == BOARD_SLUG).limit(1)).first()
    if row:
        values: dict[str, object] = {
            "name": BOARD_NAME,
            "name_localizations": None,
            "description": BOARD_DESCRIPTION,
            "color": BOARD_COLOR,
            "visibility": "public",
            "required_tags": None,
            "allowed_tags": None,
            "post_template": None,
            "default_notification_level": "normal",
            "default_sort": "latest",
            "updated_at": now(),
        }
        if owner_id is not None and row.owner_id is None:
            values["owner_id"] = owner_id
        bind.execute(boards.update().where(boards.c.id == row.id).values(**values))
        return int(row.id)

    bind.execute(
        boards.insert().values(
            slug=BOARD_SLUG,
            name=BOARD_NAME,
            name_localizations=None,
            description=BOARD_DESCRIPTION,
            color=BOARD_COLOR,
            avatar_url=None,
            owner_id=owner_id,
            parent_board_id=None,
            visibility="public",
            required_tags=None,
            allowed_tags=None,
            post_template=None,
            default_notification_level="normal",
            default_sort="latest",
            topic_count=0,
            post_count=0,
            follower_count=0,
            created_at=now(),
            updated_at=now(),
        )
    )
    return int(bind.execute(sa.select(boards.c.id).where(boards.c.slug == BOARD_SLUG)).scalar_one())


def ensure_board_owner_membership(bind: sa.Connection, board_id: int, user_id: int) -> None:
    """Ensure the selected migration author is an owner member of the sports board.

    Key parameters: `bind` is the migration connection, `board_id` identifies
    the sports board, and `user_id` identifies the owner. Return value: none.
    Side effect: may insert one `board_members` row and increment follower
    count once.
    """

    exists = bind.execute(
        sa.select(board_members.c.id)
        .where(board_members.c.board_id == board_id, board_members.c.user_id == user_id)
        .limit(1)
    ).first()
    if exists:
        return
    bind.execute(
        board_members.insert().values(
            board_id=board_id,
            user_id=user_id,
            role="owner",
            notification_level="watching",
            joined_at=now(),
        )
    )
    bind.execute(
        boards.update()
        .where(boards.c.id == board_id)
        .values(follower_count=boards.c.follower_count + 1, updated_at=now())
    )
