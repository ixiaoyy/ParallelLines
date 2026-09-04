"""Add an optional public subtype for operator-managed accounts.

Revision ID: 0072_add_user_persona_kind
Revises: 0071_seed_page_margin_light_persona
Create Date: 2026-09-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0072_add_user_persona_kind"
down_revision: str | None = "0071_seed_page_margin_light_persona"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add a nullable subtype without classifying or changing existing accounts.

    No parameters or return value. The only schema effect is one new column;
    account ownership, permissions, and stored operator flags are unchanged.
    """

    op.add_column(
        "users",
        sa.Column(
            "persona_kind",
            sa.String(length=24),
            nullable=True,
            comment=(
                "运营身份细分：editorial 栏目、automation 自动账号、fictional 创作角色；"
                "NULL 为未细分，仅 is_persona=true 生效。"
            ),
        ),
    )


def downgrade() -> None:
    """Drop subtype storage only on an explicitly authorized schema downgrade.

    No parameters or return value. Dropping this column loses saved subtype
    selections, so application rollback should normally leave the column intact.
    """

    op.drop_column("users", "persona_kind")
