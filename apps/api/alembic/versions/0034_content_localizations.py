"""add content localization maps

Revision ID: 0034_content_localizations
Revises: 0033_push_subscriptions
Create Date: 2026-05-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0034_content_localizations"
down_revision: str | None = "0033_push_subscriptions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "boards",
        sa.Column(
            "name_localizations",
            sa.JSON(),
            nullable=True,
            comment="版块名称本地化映射，键为 BCP47 locale；为空表示使用 name。",
        ),
    )
    op.add_column(
        "topics",
        sa.Column(
            "title_localizations",
            sa.JSON(),
            nullable=True,
            comment="主题标题本地化映射，键为 BCP47 locale；为空表示使用 title。",
        ),
    )


def downgrade() -> None:
    op.drop_column("topics", "title_localizations")
    op.drop_column("boards", "name_localizations")
