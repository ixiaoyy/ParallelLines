"""add administrator-only private space board

Revision ID: 0067_add_private_space_board
Revises: 0066_retire_comics_board
Create Date: 2026-07-15
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0067_add_private_space_board"
down_revision: str | None = "0066_retire_comics_board"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BOARD_SLUG = "private-space"
BOARD_NAME = "私密空间"
BOARD_DESCRIPTION = "用于 ParallelLines 与 AI 项目联动的内部筹备、配置和验证；当前仅管理员可见。"
BOARD_COLOR = "#475569"

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


def upgrade() -> None:
    """Create or refresh the administrator-only private space board.

    Key parameters: none. Return value: none. Side effect: inserts or updates
    `private-space` only when an existing forum board dataset is present.
    """

    bind = op.get_bind()
    if not table_exists(bind, "boards"):
        return
    if bind.execute(sa.select(sa.func.count()).select_from(boards)).scalar_one() == 0:
        return
    ensure_board(bind)


def downgrade() -> None:
    """Preserve private-space content when downgrading the migration.

    Key parameters: none. Return value: none. Side effect: none, because the
    internal board may already contain administrator-authored content.
    """

    return


def now() -> datetime:
    """Return the current UTC timestamp for migrated board rows.

    Key parameters: none. Return value: timezone-aware UTC datetime. Side
    effect: reads the system clock only.
    """

    return datetime.now(UTC)


def table_exists(bind: sa.Connection, table_name: str) -> bool:
    """Check whether a required table exists before migrating data.

    Key parameters are the migration `bind` and `table_name`. Return value is
    true when the table exists. Side effect: reads database metadata only.
    """

    return sa.inspect(bind).has_table(table_name)


def ensure_board(bind: sa.Connection) -> int:
    """Create or refresh the protected board and return its database ID.

    Key parameter `bind` is the migration connection. Return value is the
    private-space board ID. Side effect: inserts or updates one `boards` row
    without resetting counters or deleting existing content.
    """

    row = bind.execute(sa.select(boards).where(boards.c.slug == BOARD_SLUG).limit(1)).first()
    values: dict[str, object] = {
        "name": BOARD_NAME,
        "name_localizations": None,
        "description": BOARD_DESCRIPTION,
        "color": BOARD_COLOR,
        "owner_id": None,
        "parent_board_id": None,
        "visibility": "admin",
        "required_tags": None,
        "allowed_tags": None,
        "post_template": None,
        "default_notification_level": "normal",
        "default_sort": "latest",
        "updated_at": now(),
    }
    if row:
        bind.execute(boards.update().where(boards.c.id == row.id).values(**values))
        return int(row.id)

    bind.execute(
        boards.insert().values(
            slug=BOARD_SLUG,
            avatar_url=None,
            topic_count=0,
            post_count=0,
            follower_count=0,
            created_at=now(),
            **values,
        )
    )
    return int(bind.execute(sa.select(boards.c.id).where(boards.c.slug == BOARD_SLUG)).scalar_one())
