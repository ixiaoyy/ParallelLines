"""seed xiaoxiao chick user

Revision ID: 0060_seed_xiaoxiao_chick_user
Revises: 0059_add_sports_board
Create Date: 2026-06-26
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0060_seed_xiaoxiao_chick_user"
down_revision: str | None = "0059_add_sports_board"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHICK_USERNAME = "小小鸡仔"
CHICK_EMAIL = "xiaoxiao-jizai@pingxingxian.space"
CHICK_AVATAR_URL = "/avatars/xiaoxiao-jizai.png"
CHICK_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$GdocmU1MNeMWGPoB9corfw"
    "$px0zxHlhr+yg6zJpghqfiuTB1vMh1T8QaUvo/5Qjg04"
)
CHICK_BIO = "小小鸡仔，偶尔啄两句。"

users = sa.table(
    "users",
    sa.column("id", sa.BigInteger()),
    sa.column("username", sa.String()),
    sa.column("email", sa.String()),
    sa.column("hashed_password", sa.String()),
    sa.column("avatar_url", sa.String()),
    sa.column("display_name", sa.String()),
    sa.column("bio", sa.Text()),
    sa.column("website_url", sa.String()),
    sa.column("location", sa.String()),
    sa.column("role", sa.String()),
    sa.column("level", sa.Integer()),
    sa.column("trust_level", sa.Integer()),
    sa.column("trust_level_changed_at", sa.DateTime(timezone=True)),
    sa.column("points_balance", sa.Integer()),
    sa.column("experience_total", sa.Integer()),
    sa.column("status", sa.String()),
    sa.column("last_seen_at", sa.DateTime(timezone=True)),
    sa.column("two_factor_enabled", sa.Boolean()),
    sa.column("two_factor_secret", sa.String()),
    sa.column("profile_visibility", sa.String()),
    sa.column("show_activity", sa.Boolean()),
    sa.column("interface_theme", sa.String()),
    sa.column("locale", sa.String()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    """Create or refresh the Xiaoxiao Chick persona account.

    Key parameters: none. Return value: none. Side effect: inserts or updates
    one ordinary active user with a fixed avatar URL and login password hash.
    """

    bind = op.get_bind()
    if not table_exists(bind, "users"):
        return
    current_time = current_utc()
    existing = bind.execute(
        sa.select(users.c.id, users.c.username, users.c.email).where(
            sa.or_(users.c.username == CHICK_USERNAME, users.c.email == CHICK_EMAIL)
        )
    ).first()
    if existing is None:
        bind.execute(
            users.insert().values(
                username=CHICK_USERNAME,
                email=CHICK_EMAIL,
                hashed_password=CHICK_PASSWORD_HASH,
                avatar_url=CHICK_AVATAR_URL,
                display_name=CHICK_USERNAME,
                bio=CHICK_BIO,
                website_url=None,
                location=None,
                role="user",
                level=0,
                trust_level=0,
                trust_level_changed_at=None,
                points_balance=0,
                experience_total=0,
                status="active",
                last_seen_at=None,
                two_factor_enabled=False,
                two_factor_secret=None,
                profile_visibility="public",
                show_activity=True,
                interface_theme="system",
                locale="zh-CN",
                created_at=current_time,
                updated_at=current_time,
            )
        )
        return
    if existing.username != CHICK_USERNAME or existing.email != CHICK_EMAIL:
        raise RuntimeError(
            "Xiaoxiao Chick username/email conflicts with an existing different user: "
            f"id={existing.id}, username={existing.username}, email={existing.email}"
        )
    bind.execute(
        users.update()
        .where(users.c.id == existing.id)
        .values(
            hashed_password=CHICK_PASSWORD_HASH,
            avatar_url=CHICK_AVATAR_URL,
            display_name=CHICK_USERNAME,
            bio=CHICK_BIO,
            role="user",
            status="active",
            two_factor_enabled=False,
            two_factor_secret=None,
            profile_visibility="public",
            show_activity=True,
            interface_theme="system",
            locale="zh-CN",
            updated_at=current_time,
        )
    )


def downgrade() -> None:
    """Leave the Xiaoxiao Chick account in place on downgrade.

    Key parameters: none. Return value: none. Side effect: none, because this
    account may own user-created topics, posts, or moderation records.
    """

    return


def table_exists(bind: sa.Connection, table_name: str) -> bool:
    """Check table presence before running data-migration statements.

    Key parameters: `bind` is the migration connection and `table_name` is the
    table name. Return value: true when the table exists. Side effect: reads
    database metadata only.
    """

    return sa.inspect(bind).has_table(table_name)


def current_utc() -> datetime:
    """Return a timezone-aware UTC timestamp for migration writes.

    Key parameters: none. Return value: current UTC datetime. Side effect:
    none.
    """

    return datetime.now(UTC)
