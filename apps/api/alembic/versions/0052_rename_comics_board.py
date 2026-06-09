"""rename comics board

Revision ID: 0052_rename_comics_board
Revises: 0051_calendar_event_status
Create Date: 2026-06-09
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0052_rename_comics_board"
down_revision: str | None = "0051_calendar_event_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BOARD_SLUG = "comics"
OLD_BOARD_NAME = "漫画分享"
NEW_BOARD_NAME = "漫画梗图"

boards = sa.table(
    "boards",
    sa.column("slug", sa.String()),
    sa.column("name", sa.String()),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    """Rename the existing comics board to its new display name.

    Key parameters: none. Return value: none. Side effect: updates the board
    row whose slug is `comics` when the boards table exists.
    """

    bind = op.get_bind()
    if not table_exists(bind, "boards"):
        return
    bind.execute(
        boards.update()
        .where(boards.c.slug == BOARD_SLUG)
        .values(name=NEW_BOARD_NAME, updated_at=now())
    )


def downgrade() -> None:
    """Restore the previous comics board display name on downgrade.

    Key parameters: none. Return value: none. Side effect: renames only the
    board row that still has the migrated name.
    """

    bind = op.get_bind()
    if not table_exists(bind, "boards"):
        return
    bind.execute(
        boards.update()
        .where(boards.c.slug == BOARD_SLUG, boards.c.name == NEW_BOARD_NAME)
        .values(name=OLD_BOARD_NAME, updated_at=now())
    )


def now() -> datetime:
    """Return the current UTC timestamp for board update bookkeeping.

    Key parameters: none. Return value: timezone-aware UTC datetime. Side
    effect: none.
    """

    return datetime.now(UTC)


def table_exists(bind: sa.Connection, table_name: str) -> bool:
    """Check table existence before running the data migration.

    Key parameter: `table_name` is the SQL table to inspect. Return value:
    true when the table exists. Side effect: reads database metadata.
    """

    return sa.inspect(bind).has_table(table_name)
