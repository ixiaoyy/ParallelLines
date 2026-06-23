"""fix frontier script publisher email

Revision ID: 0058_fix_frontier_script_publisher_email
Revises: 0057_seed_frontier_script_publisher
Create Date: 2026-06-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0058_fix_frontier_script_publisher_email"
down_revision: str | None = "0057_seed_frontier_script_publisher"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCRIPT_PUBLISHER_USERNAME = "小小快讯"
OLD_SCRIPT_PUBLISHER_EMAIL = "frontier-script-publisher@parallellines.local"
SCRIPT_PUBLISHER_EMAIL = "frontier-script-publisher@pingxingxian.space"

users = sa.table(
    "users",
    sa.column("id", sa.BigInteger()),
    sa.column("username", sa.String()),
    sa.column("email", sa.String()),
)


def upgrade() -> None:
    """Move the script publisher to a response-schema-valid email address.

    Key parameters: none. Return value: none. Side effect: updates only the
    dedicated script publisher account created by the previous revision.
    """

    bind = op.get_bind()
    publisher = bind.execute(
        sa.select(users.c.id, users.c.email).where(users.c.username == SCRIPT_PUBLISHER_USERNAME)
    ).first()
    if publisher is None or publisher.email == SCRIPT_PUBLISHER_EMAIL:
        return
    conflict = bind.execute(
        sa.select(users.c.id).where(users.c.email == SCRIPT_PUBLISHER_EMAIL)
    ).first()
    if conflict is not None and int(conflict.id) != int(publisher.id):
        raise RuntimeError("Script publisher target email already belongs to another user")
    bind.execute(
        users.update()
        .where(users.c.id == publisher.id)
        .values(email=SCRIPT_PUBLISHER_EMAIL)
    )


def downgrade() -> None:
    """Restore the previous local-only email for the script publisher.

    Key parameters: none. Return value: none. Side effect: reverts only the
    dedicated script publisher email when no conflicting row exists.
    """

    bind = op.get_bind()
    publisher = bind.execute(
        sa.select(users.c.id).where(users.c.username == SCRIPT_PUBLISHER_USERNAME)
    ).first()
    if publisher is None:
        return
    conflict = bind.execute(
        sa.select(users.c.id).where(users.c.email == OLD_SCRIPT_PUBLISHER_EMAIL)
    ).first()
    if conflict is not None and int(conflict.id) != int(publisher.id):
        raise RuntimeError("Script publisher old email already belongs to another user")
    bind.execute(
        users.update()
        .where(users.c.id == publisher.id)
        .values(email=OLD_SCRIPT_PUBLISHER_EMAIL)
    )
