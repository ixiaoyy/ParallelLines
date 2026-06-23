"""seed frontier script publisher

Revision ID: 0057_seed_frontier_script_publisher
Revises: 0056_topic_feed_sort_indexes
Create Date: 2026-06-23
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0057_seed_frontier_script_publisher"
down_revision: str | None = "0056_topic_feed_sort_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCRIPT_PUBLISHER_USERNAME = "小小快讯"
SCRIPT_PUBLISHER_EMAIL = "frontier-script-publisher@parallellines.local"
SCRIPT_PUBLISHER_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$6I7M/tW+FglPRCAgy6MNBg"
    "$mPiNT2/vKUHzd460ZW3ky+iEykEWWaU0Zpt7t84/iHM"
)

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
    """Create or activate the dedicated API publisher account.

    Key parameters: none. Return value: none. Side effect: upserts one ordinary
    active user used by local/scheduled publishing scripts.
    """

    bind = op.get_bind()
    now = current_utc()
    existing = bind.execute(
        sa.select(users.c.id, users.c.username, users.c.email).where(
            sa.or_(
                users.c.username == SCRIPT_PUBLISHER_USERNAME,
                users.c.email == SCRIPT_PUBLISHER_EMAIL,
            )
        )
    ).first()
    if existing is None:
        bind.execute(
            users.insert().values(
                username=SCRIPT_PUBLISHER_USERNAME,
                email=SCRIPT_PUBLISHER_EMAIL,
                hashed_password=SCRIPT_PUBLISHER_PASSWORD_HASH,
                avatar_url=None,
                display_name=SCRIPT_PUBLISHER_USERNAME,
                bio="用于本地脚本与定时任务发布热点资讯。",
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
                created_at=now,
                updated_at=now,
            )
        )
        return
    if existing.username != SCRIPT_PUBLISHER_USERNAME or existing.email != SCRIPT_PUBLISHER_EMAIL:
        raise RuntimeError(
            "Script publisher username/email conflicts with an existing different user: "
            f"id={existing.id}, username={existing.username}, email={existing.email}"
        )
    bind.execute(
        users.update()
        .where(users.c.id == existing.id)
        .values(
            hashed_password=SCRIPT_PUBLISHER_PASSWORD_HASH,
            display_name=SCRIPT_PUBLISHER_USERNAME,
            bio="用于本地脚本与定时任务发布热点资讯。",
            role="user",
            status="active",
            two_factor_enabled=False,
            two_factor_secret=None,
            updated_at=now,
        )
    )


def downgrade() -> None:
    """Leave the script publisher account in place on downgrade.

    Key parameters: none. Return value: none. Side effect: intentionally none to
    avoid deleting authored content or breaking scheduled publisher credentials.
    """


def current_utc() -> datetime:
    """Return a timezone-aware UTC timestamp for migration rows.

    Key parameters: none. Return value: current UTC datetime. Side effects: none.
    """

    return datetime.now(UTC)
