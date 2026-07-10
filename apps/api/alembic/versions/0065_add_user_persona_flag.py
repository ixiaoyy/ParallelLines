"""add user persona flag

Revision ID: 0065_add_user_persona_flag
Revises: 0064_rebuild_persona_login_accounts
Create Date: 2026-07-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0065_add_user_persona_flag"
down_revision: str | None = "0064_rebuild_persona_login_accounts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERSONA_EMAILS: tuple[str, ...] = (
    "no-coriander-cat@pingxingxian.space",
    "iced-americano@pingxingxian.space",
    "waimai-note@pingxingxian.space",
    "half-cola@pingxingxian.space",
    "offwork-no-push@pingxingxian.space",
    "fog-mountain@pingxingxian.space",
    "yuanshan-shop@pingxingxian.space",
    "old-huai-tree@pingxingxian.space",
    "oldhuai@pingxingxian.space",
    "huai-07@pingxingxian.space",
    "aki-slow@pingxingxian.space",
    "momo-offline@pingxingxian.space",
    "kk-offline@pingxingxian.space",
    "nate-passby@pingxingxian.space",
    "xiaok-look@pingxingxian.space",
    "rain404@pingxingxian.space",
    "zzz-awake@pingxingxian.space",
    "beta-passer@pingxingxian.space",
    "loop-once@pingxingxian.space",
    "cat-boots@pingxingxian.space",
    "xiaomanjia@pingxingxian.space",
    "xiaoxiao-zixun@pingxingxian.space",
    "xiaoxiao-jizai@pingxingxian.space",
)

users = sa.table(
    "users",
    sa.column("email", sa.String()),
    sa.column("is_persona", sa.Boolean()),
)


def upgrade() -> None:
    """Add the persona marker and flag the 23 canonical seeded accounts.

    Key parameters: none. Return value: none. Side effect: adds one indexed
    non-null users column and updates only the exact emails established by 0064.
    """

    op.add_column(
        "users",
        sa.Column(
            "is_persona",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="是否为运营维护的马甲账号；真实用户增长统计必须排除。",
        ),
    )
    op.create_index(
        "ix_users_is_persona_created_at",
        "users",
        ["is_persona", "created_at"],
        unique=False,
    )
    op.get_bind().execute(
        users.update().where(users.c.email.in_(PERSONA_EMAILS)).values(is_persona=True)
    )


def downgrade() -> None:
    """Remove the persona marker and its analytics index.

    Key parameters: none. Return value: none. Side effect: drops the index and
    users column; account rows and authored content remain unchanged.
    """

    op.drop_index("ix_users_is_persona_created_at", table_name="users")
    op.drop_column("users", "is_persona")
