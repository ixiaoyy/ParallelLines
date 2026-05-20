"""add user level

Revision ID: 0007_add_user_level
Revises: 0006_email_verification
Create Date: 2026-05-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_add_user_level"
down_revision: str | None = "0006_email_verification"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "level",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="用户等级，默认 0，用于成长体系和权限展示。",
        ),
    )

def downgrade() -> None:
    op.drop_column("users", "level")
