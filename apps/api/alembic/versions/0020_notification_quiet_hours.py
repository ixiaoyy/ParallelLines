"""add notification preference quiet hours

Revision ID: 0020_notification_quiet_hours
Revises: b247466f6ade
Create Date: 2026-05-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0020_notification_quiet_hours"
down_revision: str | None = "b247466f6ade"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_email_preferences",
        sa.Column(
            "quiet_hours_start",
            sa.Integer(),
            nullable=True,
            comment="免打扰开始小时（UTC，0-23）；为空表示未启用免打扰。",
        ),
    )
    op.add_column(
        "user_email_preferences",
        sa.Column(
            "quiet_hours_end",
            sa.Integer(),
            nullable=True,
            comment="免打扰结束小时（UTC，0-23）；为空表示未启用免打扰；等于开始小时表示全天免打扰。",
        ),
    )


def downgrade() -> None:
    op.drop_column("user_email_preferences", "quiet_hours_end")
    op.drop_column("user_email_preferences", "quiet_hours_start")
